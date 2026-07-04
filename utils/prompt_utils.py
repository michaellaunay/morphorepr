# utils/prompt_utils.py
"""
Chargement, hashing et enregistrement des prompts.
SHA256 complet (64 caractères hex) — pas de troncature.
Hash canonique pour le corpus (export CSV trié) et le lexique (clés JSON triées).
"""
import csv
import hashlib
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from utils.db_utils import get_conn


def load_prompt(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompt introuvable : {path}")
    return p.read_text(encoding="utf-8").strip()


def hash_prompt(content: str) -> str:
    """SHA256 complet — 64 caractères hex, sans troncature."""
    return hashlib.sha256(content.encode()).hexdigest()


def hash_lexicon_canonical(lexicon_path: str) -> str:
    """Hash canonique du lexique : clés JSON triées, indépendant de l'encodage."""
    data      = json.loads(Path(lexicon_path).read_text())
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_corpus_canonical(db_path: str) -> str:
    """
    Hash canonique du corpus : export CSV trié de la table features uniquement.
    Couvre uniquement les données d'entrée — PAS les résultats ajoutés pendant le run.
    La base de données croît légitimement pendant l'exécution ; seules les lignes
    de la table features font partie de la définition du corpus gelé.
    """
    conn = sqlite3.connect(db_path)
    cur  = conn.execute(
        "SELECT * FROM features ORDER BY feature_uid"
    )
    col_names = [d[0] for d in cur.description]   # en-tête : détecte un changement de schéma/ordre
    rows = cur.fetchall()
    conn.close()
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(col_names)                    # ligne d'en-tête incluse dans le hash
    for row in rows:
        writer.writerow(row)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def register_prompts(prompt_paths: dict) -> dict:
    """Enregistre tous les prompts en DB. Retourne {agent_name: sha256_complet}."""
    hashes = {}
    with get_conn() as conn:
        for agent_name, path in prompt_paths.items():
            content   = load_prompt(path)
            sha       = hash_prompt(content)
            prompt_id = f"{agent_name}_{sha[:12]}"
            conn.execute("""
                INSERT OR IGNORE INTO prompts (
                    prompt_id, agent_name, version,
                    content, sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (prompt_id, agent_name, "v1", content, sha,
                  datetime.utcnow().isoformat()))
            hashes[agent_name] = sha
    return hashes


def verify_prompts_unchanged(prompt_paths: dict,
                              registered_hashes: dict) -> None:
    """Lève une RuntimeError si un prompt a changé depuis l'enregistrement."""
    for agent_name, path in prompt_paths.items():
        current  = hash_prompt(load_prompt(path))
        expected = registered_hashes.get(agent_name, "")
        if current != expected:
            raise RuntimeError(
                f"Prompt modifié : {agent_name}\n"
                f"  attendu : {expected[:16]}...\n"
                f"  actuel  : {current[:16]}..."
            )
