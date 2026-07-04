# ─────────────────────────────────────────────
# tests/test_pipeline_phase4_e2e.py  (v6.10.0 étape 2 — ADR-001)
# Test d'orchestration END-TO-END de la Phase 4 sur le VRAI orchestrateur
# (run_pipeline → initialize_run → p1…p5), configs/dev_phase4.yaml.
#
#   • Les phases p1–p3 (agents non implémentés) sont REMPLACÉES par des fakes qui
#     sèment un corpus dev déterministe : 4 features cibles (une par propriété
#     robuste) + 2 candidates de même couche pour les contrôles.
#   • Modèle, SAE et ModelProvider sont monkeypatchés (aucun téléchargement,
#     aucune clé API) ; steer_feature est remplacé par un fake par-feature dont
#     les textes steerés portent le signal de LA propriété cible.
#   • Le scoring passe par les VRAIS classifieurs tense / code_presence /
#     conditional_modality (pure-python) ; negation_presence utilise un lexique
#     local (classifiers/negation.py charge spaCy à l'import, stubé en test).
#   • Tout le reste est RÉEL : initialize_run (hash config/prompts/lexique),
#     steerer.run, predictor.run, baseline_predictor.run, causal_scorer.run,
#     run_intervention_controls (+ gardes), dev_summary, reprise (--resume).
#
# Le run réel (gpt2 + SAE gpt2-small-res-jb, téléchargements HF) est OPT-IN :
#   MORPHOREPR_RUN_DEV_PHASE4=1 python3 -m pytest tests/test_pipeline_phase4_e2e.py -k real
# ─────────────────────────────────────────────
import json
import os
import sqlite3
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

os.makedirs("logs", exist_ok=True)   # orchestrator ouvre logs/pipeline.log à l'import
import orchestrator
import agents.steerer as stz
import agents.causal_scorer as cs
import agents.predictor as predictor_mod
import agents.baseline_predictor as bp
import classifiers.tense
import classifiers.code_presence
import classifiers.modality
from utils.db_utils import get_conn, save_agent_output

CFG_PATH = "configs/dev_phase4.yaml"
LAYER = 3

# ── Corpus dev : feature_index → (propriété robuste, expression MorphoRepr) ──
TARGETS = {
    101: ("negation_presence",    "0.90·mal-o + 0.40·ne-a"),
    102: ("tense",                "0.90·ag-is"),
    103: ("code_presence",        "0.92·dat-ad-o"),
    104: ("conditional_modality", "0.85·sci-us"),
}
EXTRAS = [105, 106]                  # même couche : pools des contrôles d'intervention

NEUTRAL_CONT  = " The plan continues as usual this afternoon."
NEUTRAL_CONT2 = " Everything remains calm and routine around here."
# Textes steerés : signal FORT sur la propriété cible, ZÉRO signal sur les trois autres.
STEERED = {
    101: "No, never — nothing is possible without loss, and nobody agrees.",
    102: "He walked and talked, she finished, arrived, waited and rested.",
    103: "def add(x): return x + 1  # print(x) == y",
    104: "If it would rain, we could stay inside, unless it might clear.",
}


def _uid(idx: int) -> str:
    return f"gpt2:res-jb:{LAYER}:hook_resid_post:{idx}"


# ── Fakes : modèle / SAE / provider / classifieur négation ─────────────────────────────
class _FakeSAE:
    def __init__(self, n=512, d=8):
        import torch
        self.W_dec = torch.ones(n, d)
        class _C:
            hook_name = f"blocks.{LAYER}.hook_resid_post"
        self.cfg = _C()


class _FakeModel:
    def generate(self, prompt, **kw):
        return str(prompt) + NEUTRAL_CONT2


def _fake_steer(model, sae, feature_index, magnitude, probe_sentences, feature_stats, config):
    """Contrat de steer_feature (REQUIRED_STEER_FIELDS + probe_id 1-based) ; textes
    steerés par-feature. magnitude 0.0 = condition contrôle (after == before)."""
    out = []
    for pid, s in enumerate(probe_sentences, 1):
        before = s + NEUTRAL_CONT
        if magnitude and magnitude > 0 and feature_index in STEERED:
            after = s + " " + STEERED[feature_index]
        elif magnitude and magnitude > 0:
            after = s + NEUTRAL_CONT2
        else:
            after = before
        out.append({"probe_id": pid, "text_before": before, "text_after": after,
                    "activation_before": 1.0,
                    "activation_after": 1.0 + float(magnitude or 0.0),
                    "achieved_delta": float(magnitude or 0.0),
                    "ood_flag": 0})
    return out


def _neg_measure(texts_before, texts_after):
    """Négation lexicale locale (classifiers/negation.py exige spaCy, stubé en test).
    Même forme de sortie que les classifieurs matérialisés."""
    lex = {"no", "not", "never", "nothing", "nowhere", "nobody", "none", "without"}
    def dens(t):
        toks = [w.strip(".,;:!?—").lower() for w in t.split()]
        return (sum(1.0 for w in toks if w in lex) / len(toks)) if toks else 0.0
    b = sum(dens(t) for t in texts_before) / len(texts_before)
    a = sum(dens(t) for t in texts_after) / len(texts_after)
    delta = a - b
    return {"property": "negation_presence", "tier": "robust",
            "before": round(b, 4), "after": round(a, 4), "delta": round(delta, 4),
            "direction": ("INCREASE" if delta > 0.02 else
                          "DECREASE" if delta < -0.02 else "NO_CHANGE")}


CLASSIFIERS_DEV = {
    "negation_presence":    _neg_measure,
    "tense":                classifiers.tense.measure,
    "code_presence":        classifiers.code_presence.measure,
    "conditional_modality": classifiers.modality.measure,
}


class _FakeProvider:
    """Provider déterministe : mappe le contenu utilisateur (expression MorphoRepr ou
    annotation baseline) vers la propriété cible → INCREASE, le reste NO_CHANGE."""
    _KEYS = (("mal-o", "negation_presence"), ("ag-is", "tense"),
             ("dat-ad-o", "code_presence"), ("sci-us", "conditional_modality"),
             ("negation", "negation_presence"), ("past", "tense"),
             ("source code", "code_presence"), ("conditional", "conditional_modality"))

    def generate(self, messages, system_prompt, max_tokens, generation_params):
        content = messages[0]["content"]
        prop = next((p for k, p in self._KEYS if k in content), None)
        preds = [{"property": q,
                  "direction": "INCREASE" if q == prop else "NO_CHANGE",
                  "confidence": 0.9}
                 for q in ("negation_presence", "tense", "code_presence",
                           "conditional_modality")]
        return json.dumps({"status": "ok", "method": "dev-fake", "predictions": preds})


# ── Fakes p1–p3 : sèment le corpus dev via la DB (env MORPHOREPR_DB_PATH) ─────────────
def _primary_mrid():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT model_run_id FROM model_runs WHERE is_primary_scientific=1").fetchone()
    assert row is not None, "model_run primaire absent (initialize_run)"
    return row["model_run_id"]


def _seed_features(*_a):
    rows = []
    for idx in list(TARGETS) + EXTRAS:
        freq = {105: 0.049, 106: 0.20}.get(idx, 0.05)
        rows.append((_uid(idx), "gpt2", "res-jb", LAYER, "hook_resid_post", idx, "random",
                     f"dev feature {idx}", "[]", 0.8, freq, 2.0, 0.8, 0.4, str(LAYER),
                     "x", datetime.utcnow().isoformat()))
    with get_conn() as conn:
        conn.executemany("""INSERT INTO features (feature_uid, model_name, sae_release,
            layer_index, hook_name, feature_index, split, nl_description, top_examples,
            score_interp, activation_freq, activation_p99, activation_mean, activation_std,
            layer, neuronpedia_url, loaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows)


def _fake_encode(rid):
    mrid = _primary_mrid()
    for idx, (_prop, expr) in TARGETS.items():
        save_agent_output(rid, idx, "encoder", 1,
                          {"status": "encoded", "expression": expr}, "", "ok", None,
                          0, 0, None, 0.0, feature_uid=_uid(idx), model_run_id=mrid)


_NL_ANNOT = {101: "mentions of negation and refusal",
             102: "past tense verb forms",
             103: "colors and painting scenes",       # FAUSSE exprès → F1(nl) < 1
             104: "conditional hypothetical clauses"}
_SR_ANNOT = {101: "sem:(negation markers)", 102: "sem:(past tense verbs)",
             103: "sem:(source code tokens)", 104: "sem:(conditional clauses)"}


def _fake_baselines(rid):
    mrid = _primary_mrid()
    with get_conn() as conn:
        for idx in TARGETS:
            for name, annot in (("nl_labels", _NL_ANNOT[idx]),
                                ("semantic_regex", _SR_ANNOT[idx])):
                conn.execute("""INSERT INTO baselines (baseline_id, run_id, model_run_id,
                    feature_uid, feature_index, baseline_name, annotation_run1,
                    annotation_run2, fidelity_auc, causal_score, causal_outcome, created_at)
                    VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL,NULL,?)""",
                    (str(uuid4()), rid, mrid, _uid(idx), idx, name, annot,
                     datetime.utcnow().isoformat()))


def _wire(monkeypatch):
    """Câble tous les fakes ; tout le reste (orchestrateur, gardes, agents Phase 4) est réel."""
    monkeypatch.setattr(orchestrator.loader, "run", lambda rid, cfg: _seed_features())
    monkeypatch.setattr(orchestrator.ranker, "run", lambda rid, cfg: None)
    monkeypatch.setattr(orchestrator, "hash_corpus_canonical", lambda path: "devcorpus")
    monkeypatch.setattr(orchestrator.cluster, "run", lambda rid: None)
    monkeypatch.setattr(orchestrator.labeler, "run", lambda rid: None)
    monkeypatch.setattr(orchestrator.consistency, "run", lambda rid: None)
    monkeypatch.setattr(orchestrator.encoder, "run", _fake_encode)
    monkeypatch.setattr(orchestrator.fidelity, "run", lambda rid: None)
    monkeypatch.setattr(orchestrator, "_run_baselines", _fake_baselines)
    monkeypatch.setattr(orchestrator.shuffled_baseline, "generate_shuffles",
                        lambda rid, cfg: None)
    monkeypatch.setattr(orchestrator.reporter, "run", lambda rid: None)
    monkeypatch.setattr(stz, "steer_feature", _fake_steer)
    monkeypatch.setattr(stz, "_get_model", lambda cfg: _FakeModel())
    monkeypatch.setattr(stz, "_get_sae", lambda cfg, layer: _FakeSAE())
    monkeypatch.setattr(stz, "_generate_text",
                        lambda model, sentence, cfg, hook_fn=None: str(sentence) + NEUTRAL_CONT2)
    monkeypatch.setattr(stz, "_measure_feature_activation", lambda *a, **k: 1.0)
    monkeypatch.setattr(stz, "_tokens_from_prompt", lambda m, s: object())
    monkeypatch.setattr(predictor_mod, "_build_primary_provider", lambda cfg: _FakeProvider())
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider())
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", dict(CLASSIFIERS_DEV))


def _args(config=CFG_PATH, resume=False, run_id=None):
    return SimpleNamespace(config=config, n_features=None, resume=resume, run_id=run_id)


def _db():
    conn = sqlite3.connect(os.environ["MORPHOREPR_DB_PATH"])
    conn.row_factory = sqlite3.Row
    return conn


def _snapshot(conn):
    q = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "steering":  q("SELECT COUNT(*) FROM steering_results"),
        "controls":  q("SELECT COUNT(*) FROM intervention_control_results"),
        "preds":     q("SELECT COUNT(*) FROM agent_outputs WHERE agent_name LIKE 'predictor%'"),
        "metrics":   q("SELECT COUNT(*) FROM metrics"),
    }


# ─────────────────────────── 1. Pipeline complet (fakes) ───────────────────────────
def test_pipeline_dev_phase4_end_to_end(test_db, monkeypatch):
    _wire(monkeypatch)
    orchestrator.run_pipeline(_args())

    conn = _db()
    run = conn.execute("SELECT * FROM runs").fetchone()
    assert run["status"] == "completed"
    assert run["last_phase"] == "p5_report"
    rid = run["run_id"]

    # Steering : 4 features × 4 sondes à la magnitude primaire (et autant au contrôle 0.0)
    n_prim = conn.execute("SELECT COUNT(*) FROM steering_results WHERE magnitude_key='rel:1.0'"
                          ).fetchone()[0]
    n_zero = conn.execute("SELECT COUNT(*) FROM steering_results WHERE magnitude_key='rel:0.0'"
                          ).fetchone()[0]
    assert n_prim == 16 and n_zero == 16

    # Prédictions : MorphoRepr + 2 baselines, 4 features chacune, status ok
    for agent in ("predictor", "predictor_nl_labels", "predictor_semantic_regex"):
        n = conn.execute("SELECT COUNT(*) FROM agent_outputs WHERE agent_name=? AND status='ok'",
                         (agent,)).fetchone()[0]
        assert n == 4, f"{agent}: {n} sorties ok (attendu 4)"

    # Score primaire : MorphoRepr parfait par construction ; NL < 1 (annotation 103 fausse)
    f1 = {r["baseline"]: r["value"] for r in conn.execute(
        "SELECT baseline, value FROM metrics WHERE metric_name='causal_macro_f1_global'")}
    assert f1[None] == pytest.approx(1.0), f"macro-F1 MorphoRepr = {f1[None]}"
    assert f1["nl_labels"] < 1.0
    assert f1["semantic_regex"] == pytest.approx(1.0)
    diffs = {r["baseline"]: r["value"] for r in conn.execute(
        "SELECT baseline, value FROM metrics WHERE metric_name='causal_macro_f1_paired_diff'")}
    assert diffs["nl_labels"] > 0
    assert diffs["semantic_regex"] == pytest.approx(0.0)

    # Contrôles d'intervention : 5 contrôles produits ET scorés (métriques secondaires)
    names = [r["control_name"] for r in conn.execute(
        "SELECT DISTINCT control_name FROM intervention_control_results ORDER BY control_name")]
    assert names == ["matched_activation_freq", "negative_steering", "prompt_only",
                     "random_direction_same_norm", "random_feature_same_layer"]
    per_control = dict(conn.execute(
        "SELECT control_name, COUNT(*) FROM intervention_control_results GROUP BY control_name"
    ).fetchall())
    assert all(v > 0 for v in per_control.values())
    for c in names:
        for m in (f"intervention_control_macro_f1:{c}", f"intervention_control_paired_diff:{c}"):
            row = conn.execute("SELECT value FROM metrics WHERE metric_name=?", (m,)).fetchone()
            assert row is not None, f"métrique manquante : {m}"
    # Un contrôle sans signal ne doit PAS égaler le primaire (câblage discriminant)
    c_f1 = conn.execute("SELECT value FROM metrics WHERE metric_name=?",
                        ("intervention_control_macro_f1:prompt_only",)).fetchone()[0]
    assert c_f1 < f1[None]

    # Récapitulatif dev : fichier + métrique, et AUCUN claim
    summary_path = f"logs/dev_summary_{rid}.json"
    assert os.path.exists(summary_path)
    summary = json.loads(open(summary_path, encoding="utf-8").read())
    assert summary["no_scientific_claim"] is True
    assert summary["counts"]["steering_results_primary_magnitude"] == 16
    assert summary["counts"]["predictions_ok_by_agent"] == {
        "predictor": 4, "predictor_nl_labels": 4, "predictor_semantic_regex": 4}
    assert conn.execute("SELECT COUNT(*) FROM metrics WHERE phase='p4_dev_summary'"
                        ).fetchone()[0] == 1
    conn.close()


# ─────────────────────────── 2. Reprise idempotente (--resume) ─────────────────────
def test_pipeline_dev_phase4_resume_idempotent(test_db, monkeypatch):
    _wire(monkeypatch)
    orchestrator.run_pipeline(_args())
    conn = _db()
    rid = conn.execute("SELECT run_id FROM runs").fetchone()["run_id"]
    before = _snapshot(conn)
    conn.close()

    orchestrator.run_pipeline(_args(resume=True, run_id=rid))   # toutes phases déjà complètes

    conn = _db()
    assert _snapshot(conn) == before, "la reprise a modifié les données (non idempotente)"
    run = conn.execute("SELECT status, last_phase FROM runs").fetchone()
    assert run["status"] == "completed" and run["last_phase"] == "p5_report"
    conn.close()


# ─────────────────────────── 3. Garde strict_baselines (échec contrôlé) ────────────
def test_guard_strict_baselines_fails_run(test_db, monkeypatch, tmp_path):
    """run_baseline_comparisons=true + strict_baselines=true SANS prédictions baselines
    (baseline_predictions.enabled=false) → p4_score échoue, le run est archivé 'failed'."""
    _wire(monkeypatch)
    cfg = yaml.safe_load(open(CFG_PATH, encoding="utf-8"))
    cfg["baseline_predictions"]["enabled"] = False
    variant = tmp_path / "dev_phase4_no_baseline_preds.yaml"
    variant.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with pytest.raises(SystemExit):
        orchestrator.run_pipeline(_args(config=str(variant)))

    conn = _db()
    run = conn.execute("SELECT status, last_phase FROM runs").fetchone()
    assert run["status"] == "failed"
    assert run["last_phase"] == "p4_predict_baselines"   # dernière phase COMPLÉTÉE avant p4_score
    conn.close()


# ─────────────────────────── 4. Sondes neutres pré-enregistrées ────────────────────
def test_probes_neutral_have_zero_property_signal():
    """Porte de qualité du jeu de sondes dev : ZÉRO signal sur les 4 propriétés robustes
    (sinon les text_before contaminent les deltas des classifieurs)."""
    lines = [l.strip() for l in open("data/probes/probes_neutral.txt", encoding="utf-8")
             if l.strip()]
    assert len(lines) >= 20
    neg_lex = {"no", "not", "never", "neither", "nor", "nobody", "nothing", "nowhere",
               "none", "without", "lack", "lacking", "absent", "fail", "fails", "failed",
               "missing", "unable", "impossible"}
    for i, p in enumerate(lines, 1):
        assert classifiers.tense._past_density(p) == 0, f"ligne {i} : signal tense"
        assert classifiers.code_presence._code_density(p) == 0, f"ligne {i} : signal code"
        assert classifiers.modality._conditional_density(p) == 0, f"ligne {i} : signal modalité"
        toks = {t.strip(".,;").lower() for t in p.split()}
        assert not (toks & neg_lex), f"ligne {i} : signal négation"
        assert 10 <= len(p.split()) <= 30, f"ligne {i} : hors 10–30 tokens"


# ─────────────────────────── 5. Smoke RÉEL opt-in (gpt2 + SAE) ──────────────────────
@pytest.mark.skipif(os.environ.get("MORPHOREPR_RUN_DEV_PHASE4") != "1",
                    reason="opt-in : MORPHOREPR_RUN_DEV_PHASE4=1 (téléchargements HF gpt2 + "
                           "gpt2-small-res-jb via transformer_lens/sae_lens)")
def test_real_proxy_steering_smoke(test_db):
    """Chemin proxy RÉEL (Règle 9) : assert_steering_ready sur une vraie feature avec le
    vrai gpt2 + SAE. Aucun fake steering ; à lancer dans un environnement équipé."""
    cfg = yaml.safe_load(open("configs/dev_phase4_minimal.yaml", encoding="utf-8"))
    with get_conn() as conn:
        conn.execute("""INSERT INTO features (feature_uid, model_name, sae_release,
            layer_index, hook_name, feature_index, split, nl_description, top_examples,
            score_interp, activation_freq, activation_p99, activation_mean, activation_std,
            layer, neuronpedia_url, loaded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("gpt2:res-jb:5:hook_resid_pre:33", "gpt2", "gpt2-small-res-jb", 5,
             "hook_resid_pre", 33, "random", "real smoke", "[]", 0.8, 0.05, 2.0, 0.8, 0.4,
             "5", "x", datetime.utcnow().isoformat()))
    stz.assert_steering_ready(cfg, n_probe=3)
