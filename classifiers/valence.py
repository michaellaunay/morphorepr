# classifiers/valence.py
"""
Utilise cardiffnlp/twitter-roberta-base-sentiment-latest plutôt que SST-2.
SST-2 est entraîné sur des critiques de films et peu performant sur du texte
technique ou narratif. Le modèle Cardiff est plus robuste sur des domaines variés.
"""
from transformers import pipeline as hf_pipeline

_pipe = None

def get_pipe():
    global _pipe
    if _pipe is None:
        _pipe = hf_pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True,
            max_length=512,
            top_k=None          # renvoie la distribution complète des labels (pas le seul top)
        )
    return _pipe

def _neg_score(text: str) -> float:
    # Avec top_k=None, la pipeline renvoie la liste de tous les labels avec leur score.
    # On lit DIRECTEMENT le score du label 'negative' (au lieu d'approximer 1 - top_score,
    # qui surévaluait la négativité quand le top label était 'neutral').
    scores = get_pipe()(text)[0]
    for s in scores:
        if s["label"].lower() in ("negative", "neg", "label_0"):
            return float(s["score"])
    return 0.0

def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before    = sum(_neg_score(t) for t in texts_before) / len(texts_before)
    after     = sum(_neg_score(t) for t in texts_after)  / len(texts_after)
    delta     = after - before
    THRESHOLD = 0.05
    return {
        "property":         "negative_valence",
        "tier":             "semi-robust",
        "before":           round(before, 4),
        "after":            round(after, 4),
        "delta":            round(delta, 4),
        "direction":        ("INCREASE" if delta >  THRESHOLD else
                             "DECREASE" if delta < -THRESHOLD else
                             "NO_CHANGE"),
        "reliability_note": ("Semi-robuste : interpréter avec prudence sur du texte "
                             "technique, ironique ou à forte densité de code.")
    }
