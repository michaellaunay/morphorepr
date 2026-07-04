# tests/test_db.py
# ─────────────────────────────────────────────

import sqlite3
import pytest
from utils.db_utils import (
    load_features_not_processed, save_agent_output,
    register_batch, mark_batch_consumed, get_unconsumed_batch
)


def _inserer_run(conn, run_id="r1"):
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            proxy_model, started_at, completed_at, status,
            last_phase, total_cost_usd
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,'running',NULL,0.0)
    """, ("r1","abc","cfg","{}","v1","lh","ch",
          "{}",0,None,42,None,"2026-01-01T00:00:00"))


def _inserer_feature(conn, index=1, split="random"):
    conn.execute("""
        INSERT INTO features (
            feature_uid, model_name, sae_release, layer_index, hook_name,
            feature_index, split, nl_description, top_examples,
            score_interp, activation_freq,
            activation_p99, activation_mean, activation_std,
            layer, neuronpedia_url, loaded_at
        ) VALUES (?, 'gpt2', 'res-jb', 6, 'hook_resid_post',
                  ?, ?, 'desc','[]',0.8,0.5,2.1,0.8,0.4,'6','http://x',
                  '2026-01-01T00:00:00')
    """, (f"gpt2:res-jb:6:hook_resid_post:{index}", index, split))


def test_tous_features_en_attente_initialement(test_db):
    conn = sqlite3.connect(test_db)
    _inserer_run(conn)
    _inserer_feature(conn, 1)
    _inserer_feature(conn, 2)
    conn.commit(); conn.close()

    pending = load_features_not_processed("r1", "encoder", 1)
    assert len(pending) == 2


def test_encodage_partiel_laisse_reste(test_db):
    conn = sqlite3.connect(test_db)
    _inserer_run(conn)
    _inserer_feature(conn, 1)
    _inserer_feature(conn, 2)
    conn.commit(); conn.close()

    save_agent_output(
        "r1", 1, "encoder", 1, {"status": "encoded"},
        "raw", "ok", None, 100, 50, None, 0.001,
        feature_uid="gpt2:res-jb:6:hook_resid_post:1"
    )
    pending = load_features_not_processed("r1", "encoder", 1)
    assert [f["feature_index"] for f in pending] == [2]


def test_reprise_batch_apres_crash(test_db):
    conn = sqlite3.connect(test_db)
    _inserer_run(conn)
    conn.commit(); conn.close()

    register_batch("b1", "r1", "phase3", "encoder", 1, 100)   # → model_run_id legacy 'r1::legacy'
    assert get_unconsumed_batch("r1", "phase3", "encoder", 1, "r1::legacy") == "b1"

    mark_batch_consumed("b1")
    assert get_unconsumed_batch("r1", "phase3", "encoder", 1, "r1::legacy") is None


# ─────────────────────────────────────────────
