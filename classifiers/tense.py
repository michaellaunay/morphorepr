# classifiers/tense.py
# v6.10.0 — classifieur DÉTERMINISTE de temps verbal (propriété robuste `tense`).
# Définition opérationnelle (identique aux prompts prédicteurs) : "shift toward past vs
# non-past tense verb forms". Heuristique v1 pure-python (aucune dépendance lourde) :
# densité de formes verbales au passé (réguliers en -ed filtrés + irréguliers fréquents).
# À CALIBRER avant pilot via classifiers/calibration (matrices de confusion sur 50 features,
# Section 4.2 du papier) ; un tagger POS pourra remplacer l'heuristique sans changer l'interface.
import re

_IRREGULAR_PAST = {
    "was","were","had","did","went","said","made","took","saw","came","got","gave","knew",
    "thought","found","told","became","left","felt","brought","began","kept","held","wrote",
    "stood","heard","meant","met","ran","paid","sat","spoke","lay","led","grew","lost","fell",
    "sent","built","understood","drew","broke","spent","rose","drove","bought","wore","chose",
    "ate","slept","won","sang","threw","caught","taught","fought","sold","forgot","flew",
}
# Faux positifs -ed fréquents (noms/adjectifs/lexèmes non verbaux)
_ED_STOPLIST = {"need","seed","speed","feed","indeed","red","bed","deed","weed","bleed",
                "breed","exceed","proceed","succeed","hundred","naked","wicked","sacred"}
_TOKEN_RE = re.compile(r"[A-Za-z']+")
THRESHOLD = 0.02


def _past_density(text: str) -> float:
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    if not tokens:
        return 0.0
    score = 0.0
    for t in tokens:
        if t in _IRREGULAR_PAST:
            score += 1.0
        elif t.endswith("ed") and len(t) > 3 and t not in _ED_STOPLIST:
            score += 1.0
    return score / len(tokens)


def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before = sum(_past_density(t) for t in texts_before) / len(texts_before)
    after  = sum(_past_density(t) for t in texts_after)  / len(texts_after)
    delta  = after - before
    return {
        "property":  "tense",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": ("INCREASE" if delta >  THRESHOLD else
                      "DECREASE" if delta < -THRESHOLD else
                      "NO_CHANGE"),
    }
