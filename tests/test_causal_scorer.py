# tests/test_causal_scorer.py  (v6.1)
# Prouve que le macro-F1 est GLOBAL sur couples, et que le bootstrap est clusterisé.
# ─────────────────────────────────────────────

from agents.causal_scorer import (compute_global_macro_f1,
                                   feature_clustered_bootstrap, paired_diff_bootstrap)


def test_macro_f1_global_pas_par_feature():
    """Le score est calculé sur l'ENSEMBLE des couples. Une feature avec une seule classe
    observée ne rend pas le score instable (contrairement à un macro-F1 par feature)."""
    pairs = [
        {"feature_uid": "u1", "property": "tense",            "predicted": "INCREASE",  "observed": "INCREASE"},
        {"feature_uid": "u1", "property": "negation_presence","predicted": "DECREASE",  "observed": "DECREASE"},
        {"feature_uid": "u2", "property": "tense",            "predicted": "NO_CHANGE", "observed": "NO_CHANGE"},
        {"feature_uid": "u2", "property": "code_presence",    "predicted": "INCREASE",  "observed": "INCREASE"},
    ]
    r = compute_global_macro_f1(pairs)
    assert r["n_pairs"] == 4
    assert r["macro_f1"] == 1.0 and r["accuracy"] == 1.0   # toutes les directions correctes


def test_macro_f1_penalise_erreurs():
    pairs = [
        {"feature_uid": "u1", "property": "tense",            "predicted": "INCREASE",  "observed": "INCREASE"},
        {"feature_uid": "u1", "property": "negation_presence","predicted": "INCREASE",  "observed": "DECREASE"},
        {"feature_uid": "u2", "property": "tense",            "predicted": "NO_CHANGE", "observed": "NO_CHANGE"},
    ]
    r = compute_global_macro_f1(pairs)
    assert 0.0 < r["macro_f1"] < 1.0


def test_bootstrap_clusterise_par_feature():
    pairs = [{"feature_uid": f"u{i}", "property": "tense",
              "predicted": "INCREASE", "observed": "INCREASE"} for i in range(20)]
    ci = feature_clustered_bootstrap(pairs, n_resamples=200, seed=1)
    assert ci["n_features"] == 20 and ci["ci_low"] <= ci["ci_high"]


def test_paired_diff_sur_features_partagees():
    a = [{"feature_uid": f"u{i}", "property": "tense", "predicted": "INCREASE",
          "observed": "INCREASE"} for i in range(10)]
    b = [{"feature_uid": f"u{i}", "property": "tense",
          "predicted": ("INCREASE" if i < 5 else "DECREASE"), "observed": "INCREASE"}
         for i in range(10)]
    d = paired_diff_bootstrap(a, b, n_resamples=200, seed=1)
    assert d["n_shared_features"] == 10 and d["diff"] > 0   # A (parfait) > B


# ─────────────────────────────────────────────
# v6.7.0 : _load_pairs() — assemblage réel prédiction/observation (métrique primaire)
# ─────────────────────────────────────────────
import json as _json
import sqlite3 as _sqlite3
import pytest as _pytest
import agents.causal_scorer as cs
from agents.causal_scorer import (
    _load_pairs, _extract_predicted_directions, _normalize_direction,
    _primary_magnitude_key, _observe_property_direction, run as causal_run,
)

_CFG_CAUSAL = {
    "primary_split": "random",
    "steering": {"magnitude_mode": "p99_relative", "primary_magnitude_rel": 1.0,
                 "legacy_absolute_magnitude": 5, "primary_probe_family": "neutral",
                 "exclude_ood_from_primary": True},
    "stats": {"bootstrap_resamples": 50, "superiority_vs": ["nl_labels"],
              "non_inferiority_vs": ["semantic_regex"]},
    "thresholds": {"nim_delta": 0.05},
    "causal_scoring": {"run_baseline_comparisons": False},
    "seed": 42,
}


def _mk_run(conn, run_id="r1"):
    conn.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,
        lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,started_at,
        completed_at,status,last_phase,total_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, 'c', 'h', '{}', 'v1', 'lh', 'ch', '{}', 0, None, 42, None,
         '2026-01-01', None, 'running', None, 0.0))


def _mk_model_run(conn, run_id, mrid, name="primary", tier="B_open_weight"):
    conn.execute("""INSERT INTO model_runs (model_run_id, run_id, provider_name, provider_tier,
        backend, model_name, generation_params_json, created_at)
        VALUES (?,?,?,?,?,?,'{}','2026-01-01')""", (mrid, run_id, "p", tier, "vllm", name))


def _mk_feature(conn, idx, split="random"):
    uid = f"gpt2:res-jb:6:hook_resid_post:{idx}"
    conn.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,
        feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,
        activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES
        (?, 'gpt2','res-jb',6,'hook_resid_post',?,?,'d','[]',0.8,0.5,2.0,0.8,0.4,'6','x','2026-01-01')""",
        (uid, idx, split))
    return uid


def _mk_prediction(conn, run_id, mrid, uid, idx, props, agent="predictor"):
    conn.execute("""INSERT INTO agent_outputs (output_id,run_id,model_run_id,feature_uid,feature_index,
        agent_name,run_number,output_json,raw_output,status,error_msg,tokens_input,tokens_output,
        batch_id,cost_usd,coefficient_type,created_at) VALUES
        (?,?,?,?,?,?,1,?,?,'ok',NULL,1,1,NULL,0.0,'confidence','2026-01-01')""",
        (f"p-{mrid}-{idx}-{agent}", run_id, mrid, uid, idx, agent,
         _json.dumps({"status": "ok", "properties": props}), "raw"))


def _mk_steer(conn, run_id, mrid, uid, idx, before, after, mag_key="rel:1.0",
              ood=0, gen=0, family="neutral", cat=None):
    conn.execute("""INSERT INTO steering_results (result_id,run_id,model_run_id,feature_uid,
        feature_index,intervention_space,magnitude,magnitude_rel,magnitude_key,probe_id,probe_family,
        probe_category,generation_index,text_before,text_after,layer,token_position,activation_before,
        activation_after,achieved_delta,ood_flag,created_at) VALUES
        (?,?,?,?,?, 'residual_add_decoder', 2.0, 1.0, ?, ?, ?, ?, ?, ?, ?, '6','all',1.0,2.0,1.0,?,'2026-01-01')""",
        (f"s-{mrid}-{idx}-{gen}-{family}-{cat}", run_id, mrid, uid, idx, mag_key, idx, family, cat,
         gen, before, after, ood))


# 1-3. Extraction / normalisation des directions prédites
def test_extract_predictions_canonical():
    out = _extract_predicted_directions({"status": "ok", "predictions": [
        {"property": "negation_presence", "direction": "increase", "confidence": 0.8},
        {"property": "tense", "direction": "NO_CHANGE"}]})
    assert out == {"negation_presence": "INCREASE", "tense": "NO_CHANGE"}


def test_extract_predictions_dict_and_objects():
    assert _extract_predicted_directions(
        {"properties": {"negation_presence": "increase", "tense": "down"}}
    ) == {"negation_presence": "INCREASE", "tense": "DECREASE"}
    assert _extract_predicted_directions(
        {"properties": {"negation_presence": {"direction": "INCREASE", "confidence": 0.8}}}
    ) == {"negation_presence": "INCREASE"}


def test_extract_rejects_invalid_directions():
    out = _extract_predicted_directions({"properties": {
        "negation_presence": "UNKNOWN", "tense": None, "code_presence": "",
        "conditional_modality": "increase"}})
    assert out == {"conditional_modality": "INCREASE"}     # seules les directions valides retenues
    assert _normalize_direction("UNKNOWN") is None
    assert _normalize_direction(None) is None and _normalize_direction("") is None


# 4. Observation via classifieur déterministe
def test_observe_property_direction():
    rows = [{"text_before": "a", "text_after": "b"}, {"text_before": "c", "text_after": "d"},
            {"text_before": None, "text_after": "x"}]
    obs = _observe_property_direction(rows, "tense", lambda tb, ta: {"direction": "INCREASE"})
    assert obs["direction"] == "INCREASE" and obs["n_observations"] == 2   # paire None ignorée


def test_observe_invalid_direction_raises():
    with _pytest.raises(ValueError):
        _observe_property_direction([{"text_before": "a", "text_after": "b"}], "tense",
                                    lambda tb, ta: {"direction": "WUT"})


# 5. Clé de magnitude primaire
def test_primary_magnitude_key():
    assert _primary_magnitude_key({"steering": {"magnitude_mode": "p99_relative",
                                                 "primary_magnitude_rel": 1.0}}) == "rel:1.0"
    assert _primary_magnitude_key({"steering": {"magnitude_mode": "absolute",
                                                 "legacy_absolute_magnitude": 5}}) == "abs:5"


# 6. OOD exclu/inclus selon la config
def test_load_pairs_ood_filter(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", uid, 1, {"negation_presence": "INCREASE"})
    _mk_steer(conn, "r1", "mrP", uid, 1, "x", "y", ood=0, gen=0)
    _mk_steer(conn, "r1", "mrP", uid, 1, "x2", "y2", ood=1, gen=1)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    p1 = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert len(p1) == 1 and p1[0]["n_observations"] == 1           # OOD exclu
    cfg2 = _json.loads(_json.dumps(_CFG_CAUSAL)); cfg2["steering"]["exclude_ood_from_primary"] = False
    p2 = _load_pairs("r1", "morphorepr", config=cfg2, model_run_id="mrP", split="random")
    assert p2[0]["n_observations"] == 2                            # OOD inclus


# 7. Strictement model-aware
def test_load_pairs_model_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn)
    _mk_model_run(conn, "r1", "mrP", "primary"); _mk_model_run(conn, "r1", "mrS", "secondary", "C_proprietary_api")
    uid = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", uid, 1, {"negation_presence": "INCREASE"})
    _mk_prediction(conn, "r1", "mrS", uid, 1, {"negation_presence": "DECREASE"})
    _mk_steer(conn, "r1", "mrP", uid, 1, "a", "b")
    _mk_steer(conn, "r1", "mrS", uid, 1, "c", "d")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert len(pairs) == 1 and pairs[0]["model_run_id"] == "mrP" and pairs[0]["predicted"] == "INCREASE"
    # le primaire ne charge jamais la prédiction DECREASE du secondaire


# 8. Strictement split-aware
def test_load_pairs_split_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    ur = _mk_feature(conn, 1, "random"); ue = _mk_feature(conn, 2, "easy")
    _mk_prediction(conn, "r1", "mrP", ur, 1, {"tense": "INCREASE"})
    _mk_prediction(conn, "r1", "mrP", ue, 2, {"tense": "INCREASE"})
    _mk_steer(conn, "r1", "mrP", ur, 1, "a", "b"); _mk_steer(conn, "r1", "mrP", ue, 2, "c", "d")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"tense": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert {p["feature_uid"] for p in pairs} == {ur}               # easy exclu


# 9-10. Absences explicites
def test_load_pairs_no_steering_raises(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random"); _mk_prediction(conn, "r1", "mrP", uid, 1, {"tense": "INCREASE"})
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"tense": lambda tb, ta: {"direction": "INCREASE"}})
    with _pytest.raises(RuntimeError, match="p4_steer"):
        _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")


def test_load_pairs_no_predictor_raises(test_db):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random"); _mk_steer(conn, "r1", "mrP", uid, 1, "a", "b")
    conn.commit(); conn.close()
    with _pytest.raises(RuntimeError, match="No predictor outputs"):
        _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")


def test_load_pairs_unknown_method_raises():
    with _pytest.raises(NotImplementedError):
        _load_pairs("r1", "does_not_exist", config=_CFG_CAUSAL, model_run_id="mrP")


# 11. Couple final assemblé
def test_load_pairs_assembles_pair(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", uid, 1, {"negation_presence": "INCREASE"})
    _mk_steer(conn, "r1", "mrP", uid, 1, "no problems", "not a problem, no issues")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {
        "negation_presence": lambda tb, ta: {"property": "negation_presence", "direction": "INCREASE"}})
    pairs = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert len(pairs) == 1
    p = pairs[0]
    assert (p["predicted"] == "INCREASE" and p["observed"] == "INCREASE"
            and p["property"] == "negation_presence" and p["method"] == "morphorepr")


# 12-13. run() minimal : métrique écrite avec model_run_id ; baselines non comparées (run_baseline_comparisons=false)
def test_run_minimal_writes_metric_and_skips_baselines(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):
        uid = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", uid, i, {"negation_presence": "INCREASE"})
        _mk_steer(conn, "r1", "mrP", uid, i, "a", "b")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    cfg = _json.loads(_json.dumps(_CFG_CAUSAL))
    cfg["_runtime"] = {"model_run_ids": {"primary": "mrP"}}        # run() lit le primaire
    res = causal_run("r1", cfg)
    assert res["morphorepr"]["macro_f1"] == 1.0                    # toutes prédictions == observations
    assert res["comparisons"] == {}                                # run_baseline_comparisons=false : aucune comparaison
    conn = _sqlite3.connect(test_db)
    row = conn.execute("""SELECT model_run_id, split FROM metrics
                          WHERE metric_name='causal_macro_f1_global'""").fetchone()
    n_diff = conn.execute("""SELECT COUNT(*) FROM metrics
                             WHERE metric_name='causal_macro_f1_paired_diff'""").fetchone()[0]
    conn.close()
    assert row[0] == "mrP" and row[1] == "random"                  # metrics.model_run_id renseigné
    assert n_diff == 0                                             # aucun verdict baseline (pas de faux pass/fail)
