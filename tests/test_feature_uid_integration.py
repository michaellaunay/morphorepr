# tests/test_feature_uid_integration.py  (v6.1)
# Robustesse de l'identité feature_uid : DEUX couches partageant le même feature_index.
# ─────────────────────────────────────────────

import sqlite3
import hashlib
import pytest
from utils.db_utils import save_agent_output, load_features_not_processed
from baselines.shuffled import generate_shuffles
from utils.prompt_utils import hash_corpus_canonical

_CFG = {"shuffle_control": {"n_repeats": 3, "max_term_diff": 1,
                            "llm_qualitative_audit_fraction": 0.0,
                            "evaluation_split": "random"},
        "seed": 42}


def _uid(layer, idx):
    return f"gpt2:res-jb:{layer}:hook_resid_post:{idx}"


def _run(conn):
    conn.execute("""INSERT INTO runs (run_id, git_commit, config_hash, prompt_hashes,
        lexicon_version, lexicon_hash, corpus_hash, models_json, use_temperature,
        temperature, seed, proxy_model, started_at, completed_at, status, last_phase,
        total_cost_usd) VALUES ('r1','c','h','{}','v1','lh','ch','{}',0,NULL,42,NULL,
        '2026-01-01',NULL,'running',NULL,0.0)""")
    # model_run legacy explicite (model_run_id NOT NULL sur agent_outputs/api_usage/…, v6.5.1)
    conn.execute("""INSERT OR IGNORE INTO model_runs (model_run_id, run_id, provider_name,
        provider_tier, backend, model_name, generation_params_json, created_at)
        VALUES ('r1::legacy','r1','legacy','C_proprietary_api',NULL,'legacy','{}','2026-01-01')""")


def _feat(conn, layer, idx, split="random"):
    conn.execute("""INSERT INTO features (feature_uid, model_name, sae_release, layer_index,
        hook_name, feature_index, split, nl_description, top_examples, score_interp,
        activation_freq, activation_p99, activation_mean, activation_std, layer,
        neuronpedia_url, loaded_at) VALUES (?, 'gpt2','res-jb',?, 'hook_resid_post',
        ?, ?, 'd','[]',0.8,0.5,2.0,0.8,0.4,?, 'http://x','2026-01-01')""",
        (_uid(layer, idx), layer, idx, split, str(layer)))


def test_meme_feature_index_deux_couches_pas_de_collision(test_db):
    """feature_index=123 sur les couches 6 ET 9 : deux features distinctes, deux outputs
    encodeur distincts, AUCUNE collision (la clé logique est feature_uid)."""
    conn = sqlite3.connect(test_db); _run(conn)
    _feat(conn, 6, 123); _feat(conn, 9, 123)     # même index, couches différentes
    conn.commit(); conn.close()

    save_agent_output("r1", 123, "encoder", 1, {"status": "encoded", "expression": "0.80·ag-is"},
                      "raw6", "ok", None, 10, 5, None, 0.0, feature_uid=_uid(6, 123))
    save_agent_output("r1", 123, "encoder", 1, {"status": "encoded", "expression": "0.70·sci-o"},
                      "raw9", "ok", None, 10, 5, None, 0.0, feature_uid=_uid(9, 123))

    conn = sqlite3.connect(test_db)
    n = conn.execute("SELECT COUNT(*) FROM agent_outputs WHERE run_id='r1'").fetchone()[0]
    conn.close()
    assert n == 2                                 # deux lignes, pas d'écrasement


def test_divergence_meme_uid_bloque(test_db):
    """Même feature_uid + sortie DIFFÉRENTE → Runtimeable (non silencieux)."""
    conn = sqlite3.connect(test_db); _run(conn); _feat(conn, 6, 123); conn.commit(); conn.close()
    save_agent_output("r1", 123, "encoder", 1, {"v": 1}, "raw", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6, 123))
    with pytest.raises(RuntimeError):
        save_agent_output("r1", 123, "encoder", 1, {"v": 2}, "raw", "ok", None, 1, 1, None, 0.0,
                          feature_uid=_uid(6, 123))


def test_hash_corpus_stable_plusieurs_couches(test_db):
    """hash_corpus_canonical est stable et indépendant de l'ordre d'insertion (ORDER BY
    feature_uid), même avec plusieurs couches partageant des feature_index."""
    conn = sqlite3.connect(test_db); _run(conn)
    for layer, idx in [(6, 1), (9, 1), (6, 2), (9, 2)]:
        _feat(conn, layer, idx)
    conn.commit(); conn.close()
    h1 = hash_corpus_canonical(test_db)

    conn = sqlite3.connect(test_db)
    conn.execute("DELETE FROM features")
    for layer, idx in [(9, 2), (6, 1), (9, 1), (6, 2)]:        # ordre d'insertion différent
        _feat(conn, layer, idx)
    conn.commit(); conn.close()
    h2 = hash_corpus_canonical(test_db)
    assert h1 == h2


def test_shuffle_pas_de_collision_uid(test_db):
    """Deux features de couches différentes mais MÊME feature_index : les shuffle_id
    (fondés sur sha1(feature_uid)) ne collisionnent pas."""
    conn = sqlite3.connect(test_db); _run(conn)
    # 4 features sur 2 couches, indices {1,2} répétés → 2 paires d'index identiques
    data = [(6, 1), (6, 2), (6, 3), (9, 1), (9, 2), (9, 3)]
    for layer, idx in data:
        _feat(conn, layer, idx)
        conn.execute("""INSERT INTO agent_outputs (output_id, run_id, model_run_id, feature_uid,
            feature_index, agent_name, run_number, output_json, raw_output, status,
            error_msg, tokens_input, tokens_output, batch_id, cost_usd, coefficient_type,
            created_at) VALUES (?,?,'r1::legacy',?,?, 'encoder',1,?, 'r','ok',NULL,1,1,NULL,0.0,
            'confidence','2026-01-01')""",
            (f"o_{layer}_{idx}", "r1", _uid(layer, idx), idx,
             f'{{"status":"encoded","expression":"0.{idx+5}0·ag-is"}}'))
    conn.commit(); conn.close()

    generate_shuffles("r1", _CFG, n_repeats=3)
    conn = sqlite3.connect(test_db)
    ids = [r[0] for r in conn.execute("SELECT shuffle_id FROM shuffle_controls").fetchall()]
    n_uid = conn.execute("SELECT COUNT(DISTINCT feature_uid) FROM shuffle_controls").fetchone()[0]
    conn.close()
    assert len(ids) == len(set(ids))              # aucun shuffle_id dupliqué
    assert n_uid == 6                             # les 6 features distinctes sont mélangées


def test_log_api_cost_divergence_leve(test_db):
    """Reprise d'un batch où le coût recalculé DIFFÈRE du coût loggé → RuntimeError."""
    from utils.db_utils import log_api_cost
    conn = sqlite3.connect(test_db); _run(conn); conn.commit(); conn.close()
    log_api_cost("r1", "p3", "encoder", "m", 100, 50, "b1", 1.0)
    # même batch, coût différent → divergence
    with pytest.raises(RuntimeError):
        log_api_cost("r1", "p3", "encoder", "m", 100, 50, "b1", 2.0)


def test_batch_items_mapping_persiste_pour_reprise(test_db):
    """Le mapping custom_id → feature_uid est persisté (batch_items) et retrouvable même si
    la feature n'est plus 'pending' (cas de la reprise crash-safe)."""
    from utils.db_utils import register_batch, save_batch_items, load_batch_item_map
    from utils.api_utils import feature_custom_id, build_batch_item_rows
    conn = sqlite3.connect(test_db); _run(conn)
    _feat(conn, 6, 123); _feat(conn, 9, 123)      # même feature_index, deux couches
    conn.commit(); conn.close()

    feats = [{"feature_uid": _uid(6, 123), "feature_index": 123},
             {"feature_uid": _uid(9, 123), "feature_index": 123}]
    register_batch("b1", "r1", "p3", "encoder", 1, len(feats), model_run_id="r1::legacy")
    save_batch_items("b1", build_batch_item_rows(feats, "r1::legacy"))

    m = load_batch_item_map("b1")
    assert m[feature_custom_id(feats[0])]["feature_uid"] == _uid(6, 123)
    assert m[feature_custom_id(feats[1])]["feature_uid"] == _uid(9, 123)
    assert m[feature_custom_id(feats[0])]["model_run_id"] == "r1::legacy"   # rattaché au modèle
    # idempotent : re-persister ne duplique pas (PK batch_id+custom_id)
    save_batch_items("b1", build_batch_item_rows(feats, "r1::legacy"))
    assert len(load_batch_item_map("b1")) == 2


def test_register_batch_with_items_atomique(test_db):
    """register_batch_with_items écrit le batch ET son mapping en une seule transaction
    (pas de fenêtre batch-sans-map)."""
    from utils.db_utils import register_batch_with_items, load_batch_item_map, get_unconsumed_batch
    from utils.api_utils import build_batch_item_rows
    conn = sqlite3.connect(test_db); _run(conn)
    _feat(conn, 6, 7); _feat(conn, 9, 7)
    conn.commit(); conn.close()

    feats = [{"feature_uid": _uid(6, 7), "feature_index": 7},
             {"feature_uid": _uid(9, 7), "feature_index": 7}]
    register_batch_with_items("bX", "r1", "p3", "encoder", 1, len(feats),
                              build_batch_item_rows(feats), model_run_id="r1::legacy")
    # le batch est enregistré (récupérable) ET la map est présente, dans la même transaction
    assert get_unconsumed_batch("r1", "p3", "encoder", 1, "r1::legacy") == "bX"
    assert len(load_batch_item_map("bX")) == 2


# ─────────────────────────────────────────────
