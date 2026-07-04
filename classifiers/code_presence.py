# classifiers/code_presence.py
# v6.10.0 — classifieur DÉTERMINISTE de présence de code (propriété robuste `code_presence`).
# Heuristique v1 pure-python : densité de signaux lexicaux (mots-clés de langages) et
# symboliques (opérateurs, ponctuation de code) au niveau token. À CALIBRER avant pilot
# via classifiers/calibration (Section 4.2 du papier).
import re

# Mots-clés NON ambigus uniquement : les mots-clés de langages qui sont aussi des mots
# anglais fréquents (this, class, return, print, let, none, true, ...) sont EXCLUS — faux
# positifs massifs en prose (détecté par la porte de qualité des sondes neutres). Le pouvoir
# discriminant vient surtout des SYMBOLES (regex ci-dessous) ; calibration avant pilot.
_CODE_KEYWORDS = {
    "def","elif","lambda","printf","struct","typedef","sizeof","endif",
    "func","println","const","var","if(","for(","while(","null",
}
_CODE_SYMBOL_RE = re.compile(r"(==|!=|<=|>=|->|=>|::|\+=|-=|\(\)|\{\}|\[\]|;|`|#include)")
_TOKEN_RE = re.compile(r"\S+")
THRESHOLD = 0.02


def _code_density(text: str) -> float:
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return 0.0
    score = 0.0
    for t in tokens:
        low = t.lower()
        if low.strip("():;,.") in _CODE_KEYWORDS or low in _CODE_KEYWORDS:
            score += 1.0
    score += 0.7 * len(_CODE_SYMBOL_RE.findall(text))
    return score / len(tokens)


def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before = sum(_code_density(t) for t in texts_before) / len(texts_before)
    after  = sum(_code_density(t) for t in texts_after)  / len(texts_after)
    delta  = after - before
    return {
        "property":  "code_presence",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": ("INCREASE" if delta >  THRESHOLD else
                      "DECREASE" if delta < -THRESHOLD else
                      "NO_CHANGE"),
    }
