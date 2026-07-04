# classifiers/calibration/run_calibration.py
"""
Doit passer avant le pilot run. Toutes les propriétés robustes requièrent une calibration.
v6.1 : rapporte n, équilibre des classes, matrice de confusion, accuracy ET macro-F1, et
précision/rappel par direction ; BLOQUE sur le macro-F1 (pas seulement l'accuracy) ; archive
chaque rapport (avec dataset_hash) dans la table classifier_calibrations.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

DIRECTIONS = ["INCREASE", "DECREASE", "NO_CHANGE"]


def _macro_f1(confusion: dict) -> tuple[float, dict]:
    per_dir = {}
    f1s = []
    for d in DIRECTIONS:
        tp = confusion[d][d]
        fp = sum(confusion[o][d] for o in DIRECTIONS if o != d)
        fn = sum(confusion[d][o] for o in DIRECTIONS if o != d)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_dir[d] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}
        # n'inclure dans la moyenne que les classes présentes dans la vérité terrain
        if (tp + fn) > 0:
            f1s.append(f1)
    macro = sum(f1s) / len(f1s) if f1s else 0.0
    return macro, per_dir


def calibrate(measure_fn, test_file: str, property_name: str,
              model_version: str = "unknown",
              min_macro_f1: float = 0.80,
              min_accuracy: float = 0.85,
              persist_db: bool = True) -> dict:
    raw = Path(test_file).read_bytes()
    dataset_hash = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    n = len(data)
    class_balance = dict(Counter(ex["expected_direction"] for ex in data))
    confusion = {a: {b: 0 for b in DIRECTIONS} for a in DIRECTIONS}
    correct = 0
    for ex in data:
        pred = measure_fn([ex["text_before"]], [ex["text_after"]])["direction"]
        true = ex["expected_direction"]
        confusion[true][pred] += 1
        correct += int(pred == true)
    accuracy = correct / n if n else 0.0
    macro_f1, per_dir = _macro_f1(confusion)
    passed = (macro_f1 >= min_macro_f1) and (accuracy >= min_accuracy)
    report = {
        "property": property_name,
        "model_version": model_version,
        "dataset_hash": dataset_hash,
        "n": n,
        "class_balance": class_balance,
        "accuracy": round(accuracy, 3),
        "macro_f1": round(macro_f1, 3),
        "per_direction": per_dir,
        "confusion_matrix": confusion,
        "thresholds": {"min_macro_f1": min_macro_f1, "min_accuracy": min_accuracy},
        "passed": passed,
    }
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} {property_name}: acc={accuracy:.1%} macro-F1={macro_f1:.3f} "
          f"(n={n}, équilibre={class_balance})")
    Path("calibration/reports").mkdir(parents=True, exist_ok=True)
    Path(f"calibration/reports/{property_name}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    if persist_db:
        _persist_calibration(report)
    return report


def _persist_calibration(report: dict, run_id: str | None = None):
    """Archive un rapport de calibration dans la table classifier_calibrations."""
    from utils.db_utils import get_conn
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO classifier_calibrations (
                calibration_id, run_id, property, classifier_name, classifier_version,
                dataset_hash, n, class_balance_json, threshold_json,
                confusion_matrix_json, macro_f1, accuracy, passed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, report["property"], report["property"],
            report["model_version"], report["dataset_hash"], report["n"],
            json.dumps(report["class_balance"]), json.dumps(report["thresholds"]),
            json.dumps(report["confusion_matrix"]), report["macro_f1"],
            report["accuracy"], int(report["passed"]),
            datetime.utcnow().isoformat()
        ))


if __name__ == "__main__":
    from classifiers import negation, tense, code_presence, modality, valence

    reports = [
        calibrate(negation.measure,      "calibration/negation_test.json",
                  "negation_presence",    min_macro_f1=0.80, min_accuracy=0.85),
        calibrate(tense.measure,          "calibration/tense_test.json",
                  "tense",                min_macro_f1=0.80, min_accuracy=0.85),
        calibrate(code_presence.measure,  "calibration/code_presence_test.json",
                  "code_presence",        min_macro_f1=0.85, min_accuracy=0.90),
        calibrate(modality.measure,       "calibration/modality_test.json",
                  "conditional_modality", min_macro_f1=0.80, min_accuracy=0.85),
        calibrate(valence.measure,        "calibration/valence_test.json",
                  "negative_valence",     min_macro_f1=0.75, min_accuracy=0.80),
    ]
    if not all(r["passed"] for r in reports):
        raise SystemExit(
            "Calibration échouée (macro-F1 ou accuracy insuffisant) — "
            "corriger les classifieurs avant le pilot run."
        )
    print("\nTous les classifieurs calibrés (macro-F1 OK) — prêt pour le pilot run.")
