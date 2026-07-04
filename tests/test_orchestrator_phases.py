# tests/test_orchestrator_phases.py
# v6.10.0 cleanup — fige l'inventaire des phases et pose un tripwire (xfail strict)
# sur l'ordre Phase 4 CIBLE. Le bug d'ordonnancement (p4_controls avant p4_predict/
# p4_score) est documenté dans la note d'étape (§4) ; sa correction est le chantier
# orchestrateur (v6.10.0 étape 2). Quand l'ordre sera corrigé, le test xfail strict
# passera (XPASS) et fera échouer la suite : retirer alors le marqueur et mettre à
# jour EXPECTED_PHASE_IDS_CURRENT (double tripwire volontaire).
import os

import pytest

os.makedirs("logs", exist_ok=True)  # orchestrator ouvre logs/pipeline.log à l'import
import orchestrator

PHASE_IDS = [p[0] for p in orchestrator.PHASES]

# Ordre ACTUEL (v6.10.0 étape 1, hérité du bloc v6.9.0) — bug d'ordre Phase 4 inclus.
EXPECTED_PHASE_IDS_CURRENT = [
    "p1_load", "p1_rank", "p1_freeze_corpus",
    "p2_cluster", "p2_label", "p2_consistency",
    "p3_encode", "p3_fidelity", "p3_baselines", "p3_shuffle",
    "p4_steer", "p4_controls", "p4_predict", "p4_predict_baselines",
    "p4_score", "p4_qualitative",
    "p5_report",
]


def test_inventaire_phases_courant():
    assert PHASE_IDS == EXPECTED_PHASE_IDS_CURRENT
    assert len(set(PHASE_IDS)) == len(PHASE_IDS), "identifiants de phase dupliqués"


@pytest.mark.xfail(
    strict=True,
    reason="Ordre Phase 4 cible non encore appliqué (note d'étape §4) : "
    "p4_steer → p4_predict → p4_predict_baselines → p4_score → p4_controls "
    "(+ p4_dev_summary). Correction prévue au chantier orchestrateur (étape 2).",
)
def test_ordre_phase4_cible():
    pos = {pid: i for i, pid in enumerate(PHASE_IDS)}
    assert (
        pos["p4_steer"]
        < pos["p4_predict"]
        < pos["p4_predict_baselines"]
        < pos["p4_score"]
        < pos["p4_controls"]
    )
    assert "p4_dev_summary" in pos
