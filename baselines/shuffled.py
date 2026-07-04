# baselines/shuffled.py
"""
Contrôle MorphoRepr mélangé.
- Intra-split uniquement (pas de contamination croisée)
- Longueur d'expression appariée ±1 terme
- shuffle_id déterministe : {run_id}_{sha1(feature_uid)[:12]}_{shuffle_number}
  (fondé sur feature_uid, PAS feature_index — évite les collisions inter-couches, Règle 10)
- UNIQUE(run_id, feature_uid, shuffle_number) empêche les doublons
- Généré et évalué pour evaluation_split UNIQUEMENT
- Scoré par le MÊME chemin déterministe que le primaire (scored_by='deterministic') ;
  une fraction (llm_qualitative_audit_fraction) est marquée 'llm_qualitative' pour audit
- Répétitions agrégées avant calcul des IC
"""
import hashlib
import logging
import random
from datetime import datetime
from typing import Optional
from utils.db_utils import get_conn

logger = logging.getLogger(__name__)


def _count_terms(expression: str) -> int:
    return len([t for t in expression.split("+") if "·" in t])


def generate_shuffles(run_id: str, config: dict, n_repeats: Optional[int] = None):
    """Génère les annotations mélangées intra-split. Config passée explicitement.

    v6 : (a) ne génère QUE pour evaluation_split (pas tous les splits) ; (b) assigne
    scored_by ('deterministic' par défaut, 'llm_qualitative' pour une fraction d'audit
    = llm_qualitative_audit_fraction) ; (c) insère scored_by et feature_uid."""
    sc        = config["shuffle_control"]
    n_repeats = n_repeats if n_repeats is not None else sc["n_repeats"]
    max_diff  = sc["max_term_diff"]
    eval_split = sc.get("evaluation_split", "random")
    audit_frac = sc.get("llm_qualitative_audit_fraction", 0.0)
    seed      = config.get("seed", 42)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_uid,
                   f.feature_index,
                   f.split,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id = ?
              AND ao.agent_name = 'encoder'
              AND ao.run_number = 1
              AND ao.status = 'ok'
              AND f.split = ?
        """, (run_id, eval_split)).fetchall()

    features = []
    for r in rows:
        if r["expression"]:
            features.append({
                "feature_index": r["feature_index"],
                "feature_uid":   r["feature_uid"],
                "expression":    r["expression"],
                "n_terms":       _count_terms(r["expression"]),
            })

    rng     = random.Random(seed)
    inserts = []
    for feat in features:        # un seul split (eval_split) — pas de contamination croisée
        n_feat     = feat["n_terms"]
        candidates = [
            f for f in features
            if f["feature_uid"] != feat["feature_uid"]
            and abs(f["n_terms"] - n_feat) <= max_diff
        ]
        if len(candidates) < 3:
            logger.warning(
                f"Feature {feat['feature_uid']} : "
                f"seulement {len(candidates)} candidats pour shuffle"
            )
            continue
        uid_short = hashlib.sha1(feat["feature_uid"].encode()).hexdigest()[:12]
        for shuffle_num in range(1, n_repeats + 1):
            source     = rng.choice(candidates)
            shuffle_id = f"{run_id}_{uid_short}_{shuffle_num}"
            scored_by  = "llm_qualitative" if rng.random() < audit_frac else "deterministic"
            inserts.append({
                "shuffle_id":           shuffle_id,
                "feature_uid":          feat["feature_uid"],
                "feature_index":        feat["feature_index"],
                "shuffle_number":       shuffle_num,
                "source_feature_uid":   source["feature_uid"],
                "source_feature_index": source["feature_index"],
                "annotation":           source["expression"],
                "scored_by":            scored_by,
            })

    with get_conn() as conn:
        for s in inserts:
            conn.execute("""
                INSERT OR IGNORE INTO shuffle_controls (
                    shuffle_id, run_id, feature_uid, feature_index, shuffle_number,
                    source_feature_uid, source_feature_index, annotation,
                    causal_score, causal_outcome, scored_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """, (
                s["shuffle_id"], run_id,
                s["feature_uid"], s["feature_index"], s["shuffle_number"],
                s["source_feature_uid"], s["source_feature_index"],
                s["annotation"], s["scored_by"],
                datetime.utcnow().isoformat()
            ))

    logger.info(f"Shuffles générés : {len(inserts)} ({n_repeats}/feature, split={eval_split})")
