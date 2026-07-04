# tests/test_shuffle_baseline.py
# ─────────────────────────────────────────────

import sqlite3
import pytest
from baselines.shuffled import generate_shuffles

# Config minimale pour les tests (generate_shuffles prend désormais la config en argument)
_CFG = {"shuffle_control": {"n_repeats": 10, "max_term_diff": 1,
                            "llm_qualitative_audit_fraction": 0.2,
                            "evaluation_split": "random"},
        "seed": 42}


def _setup_features_encodees(test_db, n=5, split="random"):
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            proxy_model, started_at, completed_at, status,
            last_phase, total_cost_usd
        ) VALUES ('r1','c','h','{}','v1','lh','ch','{}',0,NULL,42,NULL,
                  '2026-01-01',NULL,'running',NULL,0.0)
    """)
    # model_run legacy explicite (model_run_id NOT NULL sur agent_outputs, v6.5.1)
    conn.execute("""
        INSERT INTO model_runs (model_run_id, run_id, provider_name, provider_tier, backend,
            model_name, generation_params_json, created_at)
        VALUES ('r1::legacy','r1','legacy','C_proprietary_api',NULL,'legacy','{}','2026-01-01')
    """)
    for i in range(1, n + 1):
        conn.execute("""
            INSERT INTO features (
                feature_uid, model_name, sae_release, layer_index, hook_name,
                feature_index, split, nl_description, top_examples,
                score_interp, activation_freq,
                activation_p99, activation_mean, activation_std,
                layer, neuronpedia_url, loaded_at
            ) VALUES (?, 'gpt2', 'res-jb', 6, 'hook_resid_post',
                      ?, ?, 'd','[]',0.8,0.5,2.0,0.8,0.4,'6','http://x','2026-01-01')
        """, (f"gpt2:res-jb:6:hook_resid_post:{i}", i, split))
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, model_run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?,?,'r1::legacy',?,?,'encoder',1,?,?,?,NULL,100,50,NULL,0.0,
                      'confidence','2026-01-01')
        """, (
            f"o{i}", "r1", f"gpt2:res-jb:6:hook_resid_post:{i}", i,
            f'{{"status":"encoded","expression":"0.{i+5}0·ag-is"}}',
            "raw", "ok"
        ))
    conn.commit()
    conn.close()


def test_shuffle_pas_auto_assigne(test_db):
    """Un feature ne doit jamais recevoir sa propre annotation (comparaison sur feature_uid)."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", _CFG, n_repeats=3)
    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT feature_uid, source_feature_uid FROM shuffle_controls"
    ).fetchall()
    conn.close()
    assert all(r[0] != r[1] for r in rows)


def test_shuffle_contrainte_unicite(test_db):
    """La contrainte UNIQUE empêche les doublons logiques."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", _CFG, n_repeats=3)
    generate_shuffles("r1", _CFG, n_repeats=3)  # deuxième appel — pas de doublons
    conn = sqlite3.connect(test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM shuffle_controls WHERE run_id='r1'"
    ).fetchone()[0]
    conn.close()
    assert count <= 5 * 3   # max 15 entrées pour 5 features × 3 répétitions
