# agents/dev_summary.py
"""
Récapitulatif DEV de la Phase 4 (p4_dev_summary) — v6.10.0, étape 2.

Écrit logs/dev_summary_{run_id}.json : comptes (steering primaire, prédictions par agent,
contrôles d'intervention) et métriques p4_score / p4_controls telles qu'en DB, avec un
DISCLAIMER explicite : un dev run ne produit AUCUN claim scientifique (run_mode=dev
n'exige aucun modèle ouvert — utils/model_policy — et la volumétrie est réduite).
Refuse de s'exécuter hors run_mode=dev (double garde, en plus de celle de l'orchestrateur).
Une seule métrique numérique est écrite (phase='p4_dev_summary',
metric_name='dev_run_completed', value=1.0) — jamais un macro-F1 présenté comme claim.
"""
import json
import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from utils.db_utils import get_conn, ensure_legacy_model_run

logger = logging.getLogger(__name__)

DISCLAIMER = ("DEV RUN — aucune valeur scientifique : résultats de câblage uniquement "
              "(run_mode=dev : modèle non nécessairement ouvert/épinglé, volumétrie réduite, "
              "fakes possibles). Ne citer ni comparer ces chiffres (Règles 8 et 11).")


def _primary_magnitude_key(config: dict) -> str:
    """Clé TEXTE de la magnitude primaire — cohérente avec steerer._primary_magnitude_key
    et causal_scorer._primary_magnitude_key (même logique, dupliquée localement comme eux)."""
    st = config.get("steering", {})
    if st.get("magnitude_mode", "p99_relative") == "absolute":
        return f"abs:{st.get('legacy_absolute_magnitude', 5)}"
    return f"rel:{st.get('primary_magnitude_rel', 1.0)}"


def run(run_id: str, config: dict):
    if config.get("run_mode") != "dev":
        raise RuntimeError(
            "dev_summary : réservé à run_mode=dev (aucun claim pilot/full). "
            "Hors dev, la phase p4_dev_summary est ignorée par l'orchestrateur.")
    model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                    or ensure_legacy_model_run(run_id))
    mag_key = _primary_magnitude_key(config)

    with get_conn() as conn:
        n_steer = conn.execute(
            "SELECT COUNT(*) FROM steering_results "
            "WHERE run_id=? AND model_run_id=? AND magnitude_key=?",
            (run_id, model_run_id, mag_key)).fetchone()[0]
        pred_counts = {r["agent_name"]: r["n"] for r in conn.execute(
            """SELECT agent_name, COUNT(*) AS n FROM agent_outputs
               WHERE run_id=? AND model_run_id=? AND status='ok'
                 AND agent_name IN ('predictor','predictor_morphorepr',
                                    'predictor_nl_labels','predictor_semantic_regex')
               GROUP BY agent_name""", (run_id, model_run_id)).fetchall()}
        n_controls = conn.execute(
            "SELECT COUNT(*) FROM intervention_control_results "
            "WHERE run_id=? AND model_run_id=?",
            (run_id, model_run_id)).fetchone()[0]
        metrics = [dict(r) for r in conn.execute(
            """SELECT phase, metric_name, value, ci_low, ci_high, n_samples, baseline
               FROM metrics WHERE run_id=? AND phase IN ('p4_score','p4_controls')
               ORDER BY phase, metric_name, baseline""", (run_id,)).fetchall()]

    summary = {
        "run_id": run_id,
        "model_run_id": model_run_id,
        "run_mode": "dev",
        "no_scientific_claim": True,
        "disclaimer": DISCLAIMER,
        "primary_magnitude_key": mag_key,
        "counts": {
            "steering_results_primary_magnitude": n_steer,
            "predictions_ok_by_agent": pred_counts,
            "intervention_control_results": n_controls,
        },
        "metrics_p4": metrics,
        "generated_at": datetime.utcnow().isoformat(),
    }
    Path("logs").mkdir(exist_ok=True)
    out = Path(f"logs/dev_summary_{run_id}.json")
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    with get_conn() as conn:
        conn.execute("""INSERT INTO metrics (metric_id, run_id, model_run_id, phase, split,
                        metric_name, value, ci_low, ci_high, n_samples, baseline, computed_at)
                        VALUES (?, ?, ?, 'p4_dev_summary', ?, 'dev_run_completed', 1.0,
                                NULL, NULL, NULL, NULL, ?)""",
                     (str(uuid4()), run_id, model_run_id,
                      config.get("primary_split", "random"),
                      datetime.utcnow().isoformat()))
    logger.warning(DISCLAIMER)
    logger.info(f"Récapitulatif dev écrit : {out}")
    return summary
