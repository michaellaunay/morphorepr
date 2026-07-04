# utils/db_utils.py
"""
Seul point d'accès à features.db.
Toute opération directe sur la DB en dehors de ce module est interdite.
DB_PATH configurable via MORPHOREPR_DB_PATH pour l'isolation des tests.
"""
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("MORPHOREPR_DB_PATH", "db/features.db"))


@contextmanager
def get_conn(db_path: Optional[Path] = None):
    # Relire l'env à CHAQUE appel : garantit l'isolation des tests même si ce module
    # a été importé avant que le fixture ne fixe MORPHOREPR_DB_PATH (sinon DB_PATH,
    # figé à l'import, pointerait sur la DB de production).
    path = db_path or Path(os.environ.get("MORPHOREPR_DB_PATH", DB_PATH))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_features(split: Optional[str] = None) -> list[dict]:
    with get_conn() as conn:
        q = "SELECT * FROM features WHERE 1=1"
        p = []
        if split:
            q += " AND split = ?"
            p.append(split)
        rows = conn.execute(q, p).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["top_examples"] = json.loads(d["top_examples"])
        result.append(d)
    return result


def load_features_not_processed(run_id: str,
                                 agent_name: str,
                                 run_number: int,
                                 model_run_id: Optional[str] = None,
                                 split: Optional[str] = None) -> list[dict]:
    """Retourne les features sans output pour cet agent/run_number ET CE MODÈLE. Idempotent.
    Clés logiques : feature_uid (Règle 10) + model_run_id (Règle 11). SANS le filtre modèle,
    un 2ᵉ modèle (réplication/secondaire) croirait toutes les features déjà traitées par le
    1ᵉʳ. model_run_id par défaut = model_run legacy explicite (chemin mono-modèle)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        done = {
            r["feature_uid"]
            for r in conn.execute("""
                SELECT feature_uid FROM agent_outputs
                WHERE run_id = ? AND model_run_id = ? AND agent_name = ? AND run_number = ?
            """, (run_id, model_run_id, agent_name, run_number)).fetchall()
        }
        q = "SELECT * FROM features WHERE 1=1"
        p = []
        if split:
            q += " AND split = ?"
            p.append(split)
        rows = conn.execute(q, p).fetchall()

    result = []
    for r in rows:
        if r["feature_uid"] not in done:
            d = dict(r)
            d["top_examples"] = json.loads(d["top_examples"])
            result.append(d)
    return result


def save_agent_output(run_id: str,
                      feature_index: int,
                      agent_name: str,
                      run_number: int,
                      output_json: Optional[dict],
                      raw_output: str,
                      status: str,
                      error_msg: Optional[str],
                      tokens_input: int,
                      tokens_output: int,
                      batch_id: Optional[str],
                      cost_usd: float,
                      coefficient_type: str = "confidence",
                      feature_uid: Optional[str] = None,
                      model_run_id: Optional[str] = None):
    """Persistance idempotente MAIS NON SILENCIEUSE en cas de divergence.
    Clés logiques : feature_uid (Règle 10, REQUIS) + model_run_id (Règle 11, modèle producteur).

    - Si aucune sortie n'existe pour (run_id, model_run_id, feature_uid, agent_name, run_number) → INSERT.
    - Si une sortie IDENTIQUE existe (même output_json, raw_output, status) → ignorer (reprise).
    - Si une sortie DIFFÉRENTE existe → RuntimeError (ne pas masquer une divergence).
    Évite le piège du INSERT OR IGNORE qui avale silencieusement une sortie différente.
    NB : model_run_id peut être NULL (chemin legacy mono-modèle) ; la comparaison utilise IS."""
    if feature_uid is None:
        raise ValueError("save_agent_output : feature_uid est requis (identité logique, Règle 10).")
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)   # colonne NOT NULL : jamais de NULL (Règle 11)
    new_json = json.dumps(output_json) if output_json is not None else None
    with get_conn() as conn:
        existing = conn.execute("""
            SELECT output_json, raw_output, status FROM agent_outputs
            WHERE run_id=? AND model_run_id=? AND feature_uid=? AND agent_name=? AND run_number=?
        """, (run_id, model_run_id, feature_uid, agent_name, run_number)).fetchone()
        if existing is not None:
            same = (existing["output_json"] == new_json
                    and existing["raw_output"] == raw_output
                    and existing["status"] == status)
            if same:
                return                       # reprise idempotente
            raise RuntimeError(
                f"Divergence de sortie pour (run={run_id}, model_run={model_run_id}, "
                f"feature_uid={feature_uid}, agent={agent_name}, run_number={run_number}) : "
                f"une sortie DIFFÉRENTE est déjà persistée. Run bloqué (ne pas écraser silencieusement)."
            )
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, model_run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, model_run_id, feature_uid, feature_index, agent_name, run_number,
            new_json, raw_output, status, error_msg,
            tokens_input, tokens_output, batch_id, cost_usd,
            coefficient_type,
            datetime.utcnow().isoformat()
        ))


def register_batch(batch_id: str, run_id: str, phase: str,
                   agent_name: str, run_number: int, n_requests: int,
                   model_run_id: Optional[str] = None):
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO batches (
                batch_id, run_id, model_run_id, phase, agent_name, run_number,
                n_requests, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
        """, (batch_id, run_id, model_run_id, phase, agent_name, run_number,
              n_requests, datetime.utcnow().isoformat()))


def register_batch_with_items(batch_id: str, run_id: str, phase: str,
                              agent_name: str, run_number: int, n_requests: int,
                              items: list[dict], model_run_id: Optional[str] = None):
    """Enregistre le batch ET son mapping custom_id → feature_uid dans UNE SEULE transaction
    (crash-safe : pas de fenêtre où le batch existe sans sa map). items : [{custom_id,
    feature_uid, feature_index, model_run_id?}, …]. model_run_id (paramètre) est la valeur
    par défaut des items qui n'en portent pas. Idempotent côté items (INSERT OR IGNORE)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO batches (
                batch_id, run_id, model_run_id, phase, agent_name, run_number,
                n_requests, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
        """, (batch_id, run_id, model_run_id, phase, agent_name, run_number,
              n_requests, datetime.utcnow().isoformat()))
        for it in items:
            # Fallback CORRECT : it.get(k, default) renvoie None si la clé existe AVEC None
            # (cas de build_batch_item_rows(features) sans model_run_id). On utilise `or` pour
            # retomber sur le model_run_id du batch, sinon batch_items (NOT NULL) insérerait NULL.
            item_model_run_id = it.get("model_run_id") or model_run_id
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid,
                                                   feature_index, model_run_id)
                VALUES (?, ?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"],
                  item_model_run_id))


def mark_batch_consumed(batch_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE batches SET status='consumed', consumed_at=?
            WHERE batch_id=?
        """, (datetime.utcnow().isoformat(), batch_id))


def save_batch_items(batch_id: str, items: list[dict], model_run_id: Optional[str] = None):
    """Persiste la correspondance custom_id → feature_uid d'un batch (table batch_items).
    items : [{custom_id, feature_uid, feature_index, model_run_id?}, …]. model_run_id (param)
    est la valeur par défaut. Idempotent (INSERT OR IGNORE)."""
    with get_conn() as conn:
        for it in items:
            # `or` (et non get(k, default)) : la clé peut exister avec None (build_batch_item_rows
            # sans model_run_id) ; on retombe alors sur le model_run_id du batch.
            mr = it.get("model_run_id") or model_run_id
            if mr is None:
                raise ValueError("save_batch_items : model_run_id requis (batch_items NOT NULL, Règle 11).")
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid,
                                                   feature_index, model_run_id)
                VALUES (?, ?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"], mr))


def load_batch_item_map(batch_id: str) -> dict[str, dict]:
    """Recharge la map custom_id → {feature_uid, feature_index, model_run_id} pour ce batch."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT custom_id, feature_uid, feature_index, model_run_id
            FROM batch_items WHERE batch_id=?
        """, (batch_id,)).fetchall()
    return {r["custom_id"]: {"feature_uid": r["feature_uid"],
                             "feature_index": r["feature_index"],
                             "model_run_id": r["model_run_id"]} for r in rows}


# Mapping tier déclaré (config) → valeur stockée en DB (provider_tier).
_TIER_DB = {
    "A_fully_open":      "A_fully_open",
    "A_or_B_open":       "A_fully_open",      # à préciser au gel ; rétrogradé vers B si poids seuls
    "B_open_weight":     "B_open_weight",
    "C_proprietary_api": "C_proprietary_api",
}


def register_model_run(run_id: str, provider_cfg: dict,
                       is_primary_scientific: bool = False,
                       use_for_primary_claims: Optional[bool] = None) -> str:
    """Enregistre un model_run (Règle 11) et retourne son model_run_id. Archive révisions,
    hashes, env d'inférence et paramètres de génération. Pour un fournisseur Tier C
    (propriétaire), use_for_primary_claims est forcé à False par défaut."""
    tier_decl = provider_cfg.get("tier", "C_proprietary_api")
    tier_db   = _TIER_DB.get(tier_decl, tier_decl)
    is_proprietary = tier_db == "C_proprietary_api"
    if use_for_primary_claims is None:
        # Par défaut : un Tier C n'est jamais admissible aux claims primaires (Règle 11).
        use_for_primary_claims = (not is_proprietary) and is_primary_scientific
    if is_proprietary and use_for_primary_claims:
        raise ValueError("Un fournisseur Tier C (propriétaire) ne peut pas porter de claim primaire (Règle 11).")
    gen = provider_cfg.get("deterministic_generation",
                           provider_cfg.get("generation_params", {}))
    model_run_id = str(uuid4())
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO model_runs (
                model_run_id, run_id, provider_name, provider_tier, backend,
                model_name, model_revision, tokenizer_revision,
                weights_sha256, tokenizer_sha256, inference_env_hash,
                precision, quantization, license,
                is_primary_scientific, use_for_primary_claims,
                generation_params_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_run_id, run_id, provider_cfg.get("provider", "unknown"), tier_db,
            provider_cfg.get("backend"), provider_cfg.get("model_name", "unknown"),
            provider_cfg.get("model_revision"), provider_cfg.get("tokenizer_revision"),
            provider_cfg.get("weights_sha256"), provider_cfg.get("tokenizer_sha256"),
            provider_cfg.get("inference_container_hash", provider_cfg.get("inference_env_hash")),
            provider_cfg.get("precision"), provider_cfg.get("quantization"),
            provider_cfg.get("license"),
            int(is_primary_scientific), int(use_for_primary_claims),
            json.dumps(gen), datetime.utcnow().isoformat()
        ))
    return model_run_id


def load_model_runs(run_id: str) -> list[dict]:
    """Tous les model_runs d'un run (pour le reporting par modèle/tier)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM model_runs WHERE run_id=?", (run_id,)).fetchall()
    return [dict(r) for r in rows]


def restore_model_run_ids(run_id: str, config: dict) -> dict:
    """À la REPRISE (--resume) : reconstruit config['_runtime']['model_run_ids'] depuis la DB,
    en rattachant chaque model_run persisté au rôle déclaré dans la config (par model_name).
    Évite que les phases multi-modèle (et steerer.run) retombent sur un model_run legacy alors
    qu'un modèle primaire/secondaire existe déjà en DB (Règle 11)."""
    by_name = {}
    for r in load_model_runs(run_id):
        by_name.setdefault(r["model_name"], r["model_run_id"])
    mp  = config.get("model_providers", {})
    ids = {}
    prim = mp.get("primary_reproducible") or {}
    if prim.get("model_name") in by_name:
        ids["primary"] = by_name[prim["model_name"]]
    sec = mp.get("secondary_proprietary") or {}
    if sec.get("model_name") in by_name:
        ids["secondary"] = by_name[sec["model_name"]]
    repl = mp.get("optional_cross_model_replication", {})
    if repl.get("enabled"):
        ids["replication"] = [by_name[m["model_name"]]
                              for m in repl.get("models", []) if m.get("model_name") in by_name]
    config.setdefault("_runtime", {})["model_run_ids"] = ids
    return ids


def ensure_legacy_model_run(run_id: str, model_name: str = "legacy_single_model") -> str:
    """Crée (si absent) et retourne un model_run LEGACY explicite et déterministe pour ce run.
    Sert de valeur par défaut au chemin mono-modèle / aux écritures sans model_run_id explicite,
    afin que les colonnes model_run_id NOT NULL ne dépendent jamais d'un NULL (Règle 11, item 6).
    Tier C par défaut (donc jamais admissible aux claims primaires)."""
    legacy_id = f"{run_id}::legacy"
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO model_runs (
                model_run_id, run_id, provider_name, provider_tier, backend,
                model_name, model_revision, tokenizer_revision,
                weights_sha256, tokenizer_sha256, inference_env_hash,
                precision, quantization, license,
                is_primary_scientific, use_for_primary_claims,
                generation_params_json, created_at
            ) VALUES (?, ?, 'legacy', 'C_proprietary_api', NULL,
                      ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                      0, 0, '{}', ?)
        """, (legacy_id, run_id, model_name, datetime.utcnow().isoformat()))
    return legacy_id


def get_unconsumed_batch(run_id: str, phase: str,
                         agent_name: str, run_number: int,
                         model_run_id: Optional[str] = None) -> Optional[str]:
    """Retourne le batch_id d'un batch soumis mais non consommé, si existant. Filtre par
    model_run_id : avec plusieurs modèles dans le même run, la reprise ne récupère JAMAIS le
    batch d'un autre modèle (Règle 11). Comme batches.model_run_id est NOT NULL, un appel sans
    model_run_id résout le model_run legacy explicite (sinon un filtre IS NULL ne matcherait rien)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        row = conn.execute("""
            SELECT batch_id FROM batches
            WHERE run_id=? AND phase=? AND agent_name=?
              AND run_number=? AND model_run_id=? AND status='submitted'
            ORDER BY submitted_at DESC LIMIT 1
        """, (run_id, phase, agent_name, run_number, model_run_id)).fetchone()
    return row["batch_id"] if row else None


def log_api_cost(run_id: str, phase: str, agent_name: str,
                 model: str, tokens_in: int, tokens_out: int,
                 batch_id: Optional[str], cost: float,
                 model_run_id: Optional[str] = None) -> float:
    """Loggue le coût et met à jour le cumul, ATTRIBUÉ PAR MODÈLE (Règle 11). IDEMPOTENT PAR
    (modèle, batch) : grâce à UNIQUE(run_id, model_run_id, batch_id, phase, agent_name), un coût
    déjà loggé pour ce (run, model_run, batch, phase, agent) n'est PAS recompté à la reprise.
    model_run_id par défaut = model_run legacy explicite (colonne NOT NULL).
    NB : pour les appels non-batch (batch_id NULL), SQLite n'applique pas l'unicité — la
    déduplication ne vaut que pour les batchs (cas de la reprise après crash)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        # Non-silencieux : si un coût est DÉJÀ loggé pour ce (modèle, batch) avec un montant
        # différent, c'est une divergence à signaler (et non à ignorer).
        if batch_id is not None:
            prev = conn.execute("""
                SELECT cost_usd, tokens_input, tokens_output FROM api_usage
                WHERE run_id=? AND model_run_id=? AND batch_id=? AND phase=? AND agent_name=?
            """, (run_id, model_run_id, batch_id, phase, agent_name)).fetchone()
            if prev is not None and (
                abs(prev["cost_usd"] - cost) > 1e-9
                or prev["tokens_input"] != tokens_in
                or prev["tokens_output"] != tokens_out
            ):
                raise RuntimeError(
                    f"Divergence de coût pour batch {batch_id} (run={run_id}, model_run={model_run_id}, "
                    f"{phase}/{agent_name}) : déjà loggé {prev['cost_usd']:.4f}$ "
                    f"({prev['tokens_input']}/{prev['tokens_output']} tk), "
                    f"recalculé {cost:.4f}$ ({tokens_in}/{tokens_out} tk). Run bloqué."
                )
        cur = conn.execute("""
            INSERT OR IGNORE INTO api_usage (
                call_id, run_id, model_run_id, phase, agent_name, model,
                tokens_input, tokens_output, batch_id, cost_usd,
                cumulative_cost, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """, (
            str(uuid4()), run_id, model_run_id, phase, agent_name, model,
            tokens_in, tokens_out, batch_id, cost,
            datetime.utcnow().isoformat()
        ))
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        current = row["total_cost_usd"] if row else 0.0
        if cur.rowcount == 0:
            # Coût déjà loggé pour ce (modèle, batch) (reprise, montant identique) → ne pas recompter.
            logger.info(f"Coût déjà loggé pour batch {batch_id} (model_run {model_run_id}) — non recompté.")
            return current
        cumulative = current + cost
        conn.execute(
            "UPDATE runs SET total_cost_usd=? WHERE run_id=?",
            (cumulative, run_id)
        )
        conn.execute(
            "UPDATE api_usage SET cumulative_cost=? "
            "WHERE run_id=? AND model_run_id=? AND phase=? AND agent_name=? "
            "AND (batch_id = ? OR (batch_id IS NULL AND ? IS NULL)) "
            "AND cumulative_cost IS NULL",
            (cumulative, run_id, model_run_id, phase, agent_name, batch_id, batch_id)
        )
    return cumulative


def check_budget(run_id: str, max_cost: float) -> tuple[float, bool]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    cost = row["total_cost_usd"] if row else 0.0
    return cost, cost >= max_cost
