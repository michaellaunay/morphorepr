# classifiers/negation.py
import spacy

nlp = spacy.load("en_core_web_sm")

NEG_LEXICON = {
    "no","not","never","neither","nor","nobody","nothing",
    "nowhere","none","without","lack","lacking","absent",
    "fail","fails","failed","failure","missing","unable",
    "impossible","prevent","prevents","prevented","deny",
    "denies","denied","refuse","refuses","refused"
}
NEG_PREFIXES = ("un", "non", "dis", "mis")
# Préfixes morphologiques : signal FAIBLE et bruité (display, mission, discussion, union…).
# v6 : ils ne contribuent PLUS au score ROBUSTE de négation. Ils sont mesurés séparément
# comme "weak_morphological" (hors métrique primaire), pour analyse seulement.
# (v4 incluait aussi "a"/"in"/"im"/"il"/"ir" — faux positifs massifs, supprimés en v5.)

def count_negation_signals(text: str) -> float:
    """Signal ROBUSTE de négation : dépendance syntaxique 'neg' + lexique explicite UNIQUEMENT.
    Les préfixes morphologiques sont exclus (voir count_weak_morph_neg)."""
    doc    = nlp(text)
    tokens = [t for t in doc if not t.is_space]
    if not tokens:
        return 0.0
    score = 0.0
    for t in tokens:
        if t.dep_ == "neg":
            score += 1.0
        elif t.lower_ in NEG_LEXICON:
            score += 0.7
    return score / len(tokens)

def count_weak_morph_neg(text: str) -> float:
    """Signal FAIBLE morphologique (préfixes) — RAPPORTÉ HORS métrique robuste."""
    doc    = nlp(text)
    tokens = [t for t in doc if not t.is_space]
    if not tokens:
        return 0.0
    score = sum(
        0.3 for t in tokens
        if any(t.lower_.startswith(p) for p in NEG_PREFIXES) and len(t.text) > 4
    )
    return score / len(tokens)

def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before    = sum(count_negation_signals(t) for t in texts_before) / len(texts_before)
    after     = sum(count_negation_signals(t) for t in texts_after)  / len(texts_after)
    delta     = after - before
    # Signal faible morphologique : rapporté séparément, n'affecte PAS la direction robuste.
    weak_before = sum(count_weak_morph_neg(t) for t in texts_before) / len(texts_before)
    weak_after  = sum(count_weak_morph_neg(t) for t in texts_after)  / len(texts_after)
    THRESHOLD = 0.02
    return {
        "property":  "negation_presence",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "weak_morphological_delta": round(weak_after - weak_before, 4),
        "direction": ("INCREASE" if delta >  THRESHOLD else
                      "DECREASE" if delta < -THRESHOLD else
                      "NO_CHANGE")
    }
