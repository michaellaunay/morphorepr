# tests/test_orchestrator_phases.py
# v6.10.0 étape 2 — fige l'inventaire des phases APRÈS correction de l'ordre Phase 4
# (ADR-001) : p4_steer → p4_predict → p4_predict_baselines → p4_score → p4_controls
# → p4_qualitative → p4_dev_summary → p5_report. Le tripwire xfail STRICT posé à
# l'étape 1 a rempli son rôle (l'ordre cible est appliqué → il serait passé XPASS et
# aurait fait échouer la suite) : le marqueur est retiré et le test d'ordre devient
# un test PASSANT, bloquant toute régression d'ordonnancement.
import os

os.makedirs("logs", exist_ok=True)  # orchestrator ouvre logs/pipeline.log à l'import
import orchestrator

PHASE_IDS = [p[0] for p in orchestrator.PHASES]

EXPECTED_PHASE_IDS = [
    "p1_load", "p1_rank", "p1_freeze_corpus",
    "p2_cluster", "p2_label", "p2_consistency",
    "p3_encode", "p3_fidelity", "p3_baselines", "p3_shuffle",
    "p4_steer", "p4_predict", "p4_predict_baselines",
    "p4_score", "p4_controls", "p4_qualitative", "p4_dev_summary",
    "p5_report",
]


def test_inventaire_phases():
    assert PHASE_IDS == EXPECTED_PHASE_IDS
    assert len(set(PHASE_IDS)) == len(PHASE_IDS), "identifiants de phase dupliqués"


def test_ordre_phase4():
    """Ordre cible v6.10.0 (ADR-001) : les prédictions et le steering primaire précèdent
    p4_score ET p4_controls (assert_intervention_controls_ready exige les deux en DB)."""
    pos = {pid: i for i, pid in enumerate(PHASE_IDS)}
    assert (
        pos["p4_steer"]
        < pos["p4_predict"]
        < pos["p4_predict_baselines"]
        < pos["p4_score"]
        < pos["p4_controls"]
        < pos["p4_qualitative"]
        < pos["p4_dev_summary"]
        < pos["p5_report"]
    )
