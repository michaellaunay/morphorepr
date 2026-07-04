# classifiers/modality.py
# v6.10.0 — classifieur DÉTERMINISTE de modalité conditionnelle (`conditional_modality`).
# Définition opérationnelle : "presence of conditional/hypothetical modality (if, would,
# could, ...)". Heuristique v1 pure-python : densité lexicale de marqueurs conditionnels/
# hypothétiques + motif « if … would/could ». À CALIBRER avant pilot (classifiers/calibration).
import re

_CONDITIONAL_LEXICON = {
    "if","would","could","might","may","unless","whether","suppose","supposing",
    "hypothetically","otherwise","assuming","provided",
}
_IF_WOULD_RE = re.compile(r"\bif\b[^.!?]*\b(would|could|might)\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z']+")
THRESHOLD = 0.02


def _conditional_density(text: str) -> float:
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    if not tokens:
        return 0.0
    score = sum(1.0 for t in tokens if t in _CONDITIONAL_LEXICON)
    score += 0.5 * len(_IF_WOULD_RE.findall(text))
    return score / len(tokens)


def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before = sum(_conditional_density(t) for t in texts_before) / len(texts_before)
    after  = sum(_conditional_density(t) for t in texts_after)  / len(texts_after)
    delta  = after - before
    return {
        "property":  "conditional_modality",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": ("INCREASE" if delta >  THRESHOLD else
                      "DECREASE" if delta < -THRESHOLD else
                      "NO_CHANGE"),
    }
