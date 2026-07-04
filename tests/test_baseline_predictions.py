# ─────────────────────────────────────────────
# tests/test_baseline_predictions.py  (v6.8.0 — prédictions baselines Option B)
# nl_labels (supériorité) et semantic_regex (non-infériorité). Tout est déterministe : le provider
# primaire et/ou la prédiction sont monkeypatchés, et les classifieurs via cs.CLASSIFIER_BY_PROPERTY.
# ─────────────────────────────────────────────
import json as _json
import sqlite3 as _sqlite3
import pytest as _pytest
import agents.baseline_predictor as bp
import agents.causal_scorer as cs
from agents.baseline_predictor import (run as bp_run, _parse_prediction_response,
                                       _load_baseline_annotations)
from agents.causal_scorer import (_load_pairs, run as causal_run,
                                  assert_baseline_predictions_ready, _extract_predicted_directions)

_CFG_BP = {
    "primary_split": "random",
    "prompts": {"predictor_nl_labels": "prompts/predictor_nl_labels_v1.txt",
                "predictor_semantic_regex": "prompts/predictor_semantic_regex_v1.txt"},
    "model_providers": {"primary_reproducible": {"backend": "vllm", "model_name": "m",
                                                 "generation_params": {"temperature": 0.0}}},
    "baseline_predictions": {"enabled": True, "methods": ["nl_labels", "semantic_regex"],
                             "run_number": 1, "require_existing_baseline_annotations": True,
                             "skip_missing_annotations": False},
    "steering": {"magnitude_mode": "p99_relative", "primary_magnitude_rel": 1.0,
                 "primary_probe_family": "neutral", "exclude_ood_from_primary": True,
                 "intervention_space": "residual_add_decoder"},
    "stats": {"bootstrap_resamples": 50, "superiority_vs": ["nl_labels"],
              "non_inferiority_vs": ["semantic_regex"]},
    "thresholds": {"nim_delta": 0.05},
    "causal_scoring": {"run_baseline_comparisons": True, "strict_baselines": True},
    "seed": 42,
    "_runtime": {"model_run_ids": {"primary": "mrP"}},
}


class _FakeProvider:
    """Provider déterministe : renvoie un JSON canonique (négation INCREASE, reste NO_CHANGE)."""
    def __init__(self, direction="INCREASE"): self.direction = direction
    def generate(self, messages, system_prompt, max_tokens, generation_params):
        return _json.dumps({"status": "ok", "method": "x", "predictions": [
            {"property": "negation_presence", "direction": self.direction, "confidence": 0.8},
            {"property": "tense", "direction": "NO_CHANGE", "confidence": 0.5},
            {"property": "code_presence", "direction": "NO_CHANGE", "confidence": 0.5},
            {"property": "conditional_modality", "direction": "NO_CHANGE", "confidence": 0.5}]})


def _mk_run(conn, run_id="r1"):
    conn.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,
        lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,started_at,
        completed_at,status,last_phase,total_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, 'c', 'h', '{}', 'v1', 'lh', 'ch', '{}', 0, None, 42, None, '2026-01-01', None,
         'running', None, 0.0))


def _mk_model_run(conn, run_id, mrid, name="primary", tier="B_open_weight"):
    conn.execute("""INSERT INTO model_runs (model_run_id, run_id, provider_name, provider_tier,
        backend, model_name, generation_params_json, created_at)
        VALUES (?,?,?,?,?,?,'{}','2026-01-01')""", (mrid, run_id, "p", tier, "vllm", name))


def _mk_feature(conn, idx, split="random"):
    uid = f"gpt2:res-jb:6:hook_resid_post:{idx}"
    conn.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,
        feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,
        activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES
        (?, 'gpt2','res-jb',6,'hook_resid_post',?,?,'a feature about negation','[]',0.8,0.5,2.0,0.8,0.4,'6','x','2026-01-01')""",
        (uid, idx, split))
    return uid


def _mk_baseline(conn, run_id, mrid, uid, idx, name, annot="negation label"):
    conn.execute("""INSERT INTO baselines (baseline_id,run_id,model_run_id,feature_uid,feature_index,
        baseline_name,annotation_run1,created_at) VALUES (?,?,?,?,?,?,?,'2026-01-01')""",
        (f"b-{mrid}-{idx}-{name}", run_id, mrid, uid, idx, name, annot))


def _mk_prediction(conn, run_id, mrid, uid, idx, props, agent):
    conn.execute("""INSERT INTO agent_outputs (output_id,run_id,model_run_id,feature_uid,feature_index,
        agent_name,run_number,output_json,raw_output,status,error_msg,tokens_input,tokens_output,
        batch_id,cost_usd,coefficient_type,created_at) VALUES
        (?,?,?,?,?,?,1,?,?,'ok',NULL,1,1,NULL,0.0,'confidence','2026-01-01')""",
        (f"p-{mrid}-{idx}-{agent}", run_id, mrid, uid, idx, agent,
         _json.dumps({"status": "ok", "method": agent, "predictions":
                      [{"property": k, "direction": v} for k, v in props.items()]}), "raw"))


def _mk_steer(conn, run_id, mrid, uid, idx, before="a", after="b"):
    conn.execute("""INSERT INTO steering_results (result_id,run_id,model_run_id,feature_uid,
        feature_index,intervention_space,magnitude,magnitude_rel,magnitude_key,probe_id,probe_family,
        probe_category,generation_index,text_before,text_after,layer,token_position,activation_before,
        activation_after,achieved_delta,ood_flag,created_at) VALUES
        (?,?,?,?,?, 'residual_add_decoder', 2.0, 1.0, 'rel:1.0', ?, 'neutral', NULL, 0, ?, ?,
         '6','all',1.0,2.0,1.0,0,'2026-01-01')""",
        (f"s-{mrid}-{idx}", run_id, mrid, uid, idx, idx, before, after))


# 1. Chargement des annotations baselines (model/split-aware)
def test_load_baseline_annotations(test_db):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random")
    _mk_baseline(conn, "r1", "mrP", u, 1, "nl_labels", "a negation label")
    _mk_baseline(conn, "r1", "mrP", u, 1, "semantic_regex", "/(no|not)/")
    conn.commit(); conn.close()
    nl = _load_baseline_annotations("r1", "mrP", "nl_labels", "random")
    sr = _load_baseline_annotations("r1", "mrP", "semantic_regex", "random")
    assert len(nl) == 1 and nl[0]["annotation"] == "a negation label"
    assert len(sr) == 1 and sr[0]["annotation"] == "/(no|not)/"


# 2-3. Sauvegarde prédiction nl_labels + format accepté par _extract_predicted_directions
def test_bp_saves_nl_prediction_canonical(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random"); _mk_baseline(conn, "r1", "mrP", u, 1, "nl_labels")
    conn.commit(); conn.close()
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider("INCREASE"))
    monkeypatch.setattr(bp, "load_prompt", lambda p: "SYS")          # pas de fichier en test
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["baseline_predictions"]["methods"] = ["nl_labels"]
    summary = bp_run("r1", cfg)
    assert summary["nl_labels"]["ok"] == 1 and summary["nl_labels"]["error"] == 0
    conn = _sqlite3.connect(test_db); conn.row_factory = _sqlite3.Row
    row = conn.execute("""SELECT agent_name, model_run_id, feature_uid, status, output_json
                          FROM agent_outputs WHERE agent_name='predictor_nl_labels'""").fetchone()
    conn.close()
    assert row["agent_name"] == "predictor_nl_labels" and row["model_run_id"] == "mrP"
    assert row["feature_uid"] == u and row["status"] == "ok"
    dirs = _extract_predicted_directions(row["output_json"])        # format canonique accepté
    assert dirs["negation_presence"] == "INCREASE"


# 4. Sauvegarde prédiction semantic_regex
def test_bp_saves_semantic_regex_prediction(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random"); _mk_baseline(conn, "r1", "mrP", u, 1, "semantic_regex", "/(no|not)/")
    conn.commit(); conn.close()
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider("INCREASE"))
    monkeypatch.setattr(bp, "load_prompt", lambda p: "SYS")
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["baseline_predictions"]["methods"] = ["semantic_regex"]
    bp_run("r1", cfg)
    conn = _sqlite3.connect(test_db)
    n = conn.execute("""SELECT COUNT(*) FROM agent_outputs
                        WHERE agent_name='predictor_semantic_regex' AND status='ok'""").fetchone()[0]
    conn.close()
    assert n == 1


# 5. Absence d'annotation + require_existing_baseline_annotations=true → RuntimeError (pas de prédiction factice)
def test_bp_missing_annotations_raises(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    _mk_feature(conn, 1, "random"); conn.commit(); conn.close()      # AUCUNE ligne baselines
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider())
    monkeypatch.setattr(bp, "load_prompt", lambda p: "SYS")
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["baseline_predictions"]["methods"] = ["nl_labels"]
    with _pytest.raises(RuntimeError, match="No baseline annotations"):
        bp_run("r1", cfg)
    conn = _sqlite3.connect(test_db)
    assert conn.execute("SELECT COUNT(*) FROM agent_outputs").fetchone()[0] == 0   # rien de fabriqué
    conn.close()


# 6. assert_baseline_predictions_ready : passe si prédictions présentes, échoue sinon
def test_assert_baseline_predictions_ready(test_db):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random"); _mk_baseline(conn, "r1", "mrP", u, 1, "nl_labels")
    conn.commit()
    with _pytest.raises(RuntimeError, match="non prête"):            # pas encore de prédiction
        assert_baseline_predictions_ready("r1", "mrP", ["nl_labels"], "random")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    conn.commit(); conn.close()
    assert_baseline_predictions_ready("r1", "mrP", ["nl_labels"], "random")   # passe désormais


# 7-8. _load_pairs sur les baselines
def test_load_pairs_nl_and_semantic(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_semantic_regex")
    _mk_steer(conn, "r1", "mrP", u, 1); conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    for method in ("nl_labels", "semantic_regex"):
        pairs = _load_pairs("r1", method, config=_CFG_BP, model_run_id="mrP", split="random")
        assert len(pairs) == 1 and pairs[0]["predicted"] == "INCREASE" and pairs[0]["method"] == method


# 9. run() avec comparaisons activées : scores + paired diff + verdicts
def test_run_with_baseline_comparisons(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):
        u = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor")               # MorphoRepr
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "DECREASE"}, "predictor_nl_labels")     # NL (faux)
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_semantic_regex")# SemReg (vrai)
        _mk_steer(conn, "r1", "mrP", u, i)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    res = causal_run("r1", _json.loads(_json.dumps(_CFG_BP)))
    assert res["morphorepr"]["macro_f1"] == 1.0
    assert res["baseline_scores"]["nl_labels"]["macro_f1"] == 0.0          # NL tout faux
    assert res["baseline_scores"]["semantic_regex"]["macro_f1"] == 1.0     # SemReg tout vrai
    assert res["comparisons"]["nl_labels"]["mode"] == "superiority" and res["comparisons"]["nl_labels"]["verdict"] == "pass"
    assert res["comparisons"]["semantic_regex"]["mode"] == "non_inferiority" and res["comparisons"]["semantic_regex"]["verdict"] == "pass"
    assert res["comparisons"]["nl_labels"]["coverage"]["n_shared_features"] == 3
    conn = _sqlite3.connect(test_db)
    n_global = conn.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='causal_macro_f1_global'").fetchone()[0]
    n_diff = conn.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='causal_macro_f1_paired_diff'").fetchone()[0]
    null_mrid = conn.execute("SELECT COUNT(*) FROM metrics WHERE model_run_id IS NULL").fetchone()[0]
    conn.close()
    assert n_global == 3 and n_diff == 2 and null_mrid == 0   # MorphoRepr + 2 baselines ; 2 paired diff ; jamais NULL


# 10. Baseline absente + comparaisons activées : strict raise / non-strict skip SANS verdict
def test_run_missing_baseline_no_false_verdict(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):
        u = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_semantic_regex")
        _mk_steer(conn, "r1", "mrP", u, i)                       # NL ABSENT
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    strict = _json.loads(_json.dumps(_CFG_BP))                  # strict_baselines=true
    with _pytest.raises(RuntimeError, match="non prête"):
        causal_run("r1", strict)
    lax = _json.loads(_json.dumps(_CFG_BP)); lax["causal_scoring"]["strict_baselines"] = False
    res = causal_run("r1", lax)
    assert "nl_labels" not in res["comparisons"]                # skip sans verdict
    assert res["comparisons"]["semantic_regex"]["verdict"] in ("pass", "fail")


# 11. model-aware : le primaire ne charge pas les prédictions baselines du secondaire
def test_baseline_load_pairs_model_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn)
    _mk_model_run(conn, "r1", "mrP", "primary"); _mk_model_run(conn, "r1", "mrS", "sec", "C_proprietary_api")
    u = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    _mk_prediction(conn, "r1", "mrS", u, 1, {"negation_presence": "DECREASE"}, "predictor_nl_labels")
    _mk_steer(conn, "r1", "mrP", u, 1); _mk_steer(conn, "r1", "mrS", u, 1)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "nl_labels", config=_CFG_BP, model_run_id="mrP", split="random")
    assert len(pairs) == 1 and pairs[0]["predicted"] == "INCREASE"   # jamais la prédiction DECREASE du secondaire


# 12. split-aware : split=random ne charge que random
def test_baseline_load_pairs_split_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    ur = _mk_feature(conn, 1, "random"); ue = _mk_feature(conn, 2, "easy")
    for u, i in ((ur, 1), (ue, 2)):
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
        _mk_steer(conn, "r1", "mrP", u, i)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "nl_labels", config=_CFG_BP, model_run_id="mrP", split="random")
    assert {p["feature_uid"] for p in pairs} == {ur}


# 13. couverture : comparaison appariée sur features partagées uniquement
def test_baseline_coverage_shared_features(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):                                          # MorphoRepr sur 3 features
        u = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor")
        _mk_steer(conn, "r1", "mrP", u, i)
        if i < 3:                                                # NL seulement sur 2 features
            _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["stats"]["non_inferiority_vs"] = []   # NL seul
    res = causal_run("r1", cfg)
    cov = res["comparisons"]["nl_labels"]["coverage"]
    assert cov["morphorepr_pairs"] == 3 and cov["baseline_pairs"] == 2 and cov["n_shared_features"] == 2
