# ─────────────────────────────────────────────
# tests/test_model_run_propagation.py  (v6.5.1 — propagation effective de model_run_id)
# ─────────────────────────────────────────────

import sqlite3
import pytest
from utils.db_utils import (register_model_run, register_batch_with_items, get_unconsumed_batch,
                            save_agent_output, log_api_cost, load_batch_item_map,
                            ensure_legacy_model_run)
from utils.api_utils import build_batch_item_rows, feature_custom_id


def _uid(L, idx=1): return f"gpt2:res-jb:{L}:hook_resid_post:{idx}"


def _run(conn):
    conn.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,
        lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,
        started_at,completed_at,status,last_phase,total_cost_usd) VALUES ('r1','c','h','{}','v1',
        'lh',NULL,'{}',0,NULL,42,NULL,'t',NULL,'loading',NULL,0.0)""")


def _feat(conn, L, idx=1):
    conn.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,
        feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,
        activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES (?,?,?,?,?,?,?,?,?,?,
        ?,?,?,?,?,?,?)""", (_uid(L, idx),"gpt2","res-jb",L,"hook_resid_post",idx,"random","d","[]",
        0.8,0.5,2.0,0.8,0.4,str(L),"x","t"))


_A = {"tier": "B_open_weight", "provider": "local", "backend": "vllm", "model_name": "Qwen"}
_B = {"tier": "C_proprietary_api", "provider": "anthropic", "model_name": "claude"}


def _two_models(test_db):
    conn = sqlite3.connect(test_db); _run(conn); _feat(conn, 6, 1); conn.commit(); conn.close()
    mr_a = register_model_run("r1", _A, is_primary_scientific=True)
    mr_b = register_model_run("r1", _B, is_primary_scientific=False)
    return mr_a, mr_b


def test_two_models_never_resume_same_batch(test_db):
    """Deux modèles, même (run, phase, agent, run_number) : la reprise filtrée par model_run_id
    ne retourne JAMAIS le batch de l'autre modèle (get_unconsumed_batch + batches.model_run_id)."""
    mr_a, mr_b = _two_models(test_db)
    feats = [{"feature_uid": _uid(6, 1), "feature_index": 1}]
    register_batch_with_items("bA", "r1", "p3", "encoder", 1, 1,
                              build_batch_item_rows(feats, mr_a), model_run_id=mr_a)
    register_batch_with_items("bB", "r1", "p3", "encoder", 1, 1,
                              build_batch_item_rows(feats, mr_b), model_run_id=mr_b)
    assert get_unconsumed_batch("r1", "p3", "encoder", 1, mr_a) == "bA"   # chacun son batch
    assert get_unconsumed_batch("r1", "p3", "encoder", 1, mr_b) == "bB"
    assert get_unconsumed_batch("r1", "p3", "encoder", 1, mr_a) != "bB"


def test_batch_items_model_run_id_renseigne(test_db):
    """batch_items.model_run_id est bien renseigné (NOT NULL) et retrouvé par load_batch_item_map."""
    mr_a, _ = _two_models(test_db)
    feats = [{"feature_uid": _uid(6, 1), "feature_index": 1}]
    register_batch_with_items("bA", "r1", "p3", "encoder", 1, 1,
                              build_batch_item_rows(feats, mr_a), model_run_id=mr_a)
    m = load_batch_item_map("bA")
    assert m[feature_custom_id(feats[0])]["model_run_id"] == mr_a
    conn = sqlite3.connect(test_db)
    n_null = conn.execute("SELECT COUNT(*) FROM batch_items WHERE model_run_id IS NULL").fetchone()[0]
    conn.close()
    assert n_null == 0


def test_api_usage_separe_deux_modeles(test_db):
    """log_api_cost attribue les coûts PAR modèle : deux model_run_id → deux lignes api_usage."""
    mr_a, mr_b = _two_models(test_db)
    log_api_cost("r1", "p3", "encoder", "Qwen",  100, 50, "bA", 0.10, model_run_id=mr_a)
    log_api_cost("r1", "p3", "encoder", "claude",100, 50, "bB", 0.40, model_run_id=mr_b)
    conn = sqlite3.connect(test_db); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT model_run_id, cost_usd FROM api_usage ORDER BY cost_usd").fetchall()
    conn.close()
    assert len(rows) == 2                                  # pas d'écrasement entre modèles
    by_mr = {r["model_run_id"]: r["cost_usd"] for r in rows}
    assert abs(by_mr[mr_a] - 0.10) < 1e-9 and abs(by_mr[mr_b] - 0.40) < 1e-9


def test_agent_outputs_refuse_collision_par_modele(test_db):
    """Même modèle + même feature_uid + sortie différente → RuntimeError (anti-collision intra-modèle) ;
    deux modèles différents → deux lignes (pas d'écrasement inter-modèle)."""
    mr_a, mr_b = _two_models(test_db)
    save_agent_output("r1", 1, "encoder", 1, {"e": "A"}, "rawA", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6, 1), model_run_id=mr_a)
    # collision intra-modèle (même mr_a, sortie différente) → bloquée
    with pytest.raises(RuntimeError):
        save_agent_output("r1", 1, "encoder", 1, {"e": "A2"}, "rawA2", "ok", None, 1, 1, None, 0.0,
                          feature_uid=_uid(6, 1), model_run_id=mr_a)
    # autre modèle → autorisé (pas d'écrasement)
    save_agent_output("r1", 1, "encoder", 1, {"e": "B"}, "rawB", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6, 1), model_run_id=mr_b)
    conn = sqlite3.connect(test_db)
    n = conn.execute("SELECT COUNT(*) FROM agent_outputs WHERE feature_uid=?", (_uid(6, 1),)).fetchone()[0]
    conn.close()
    assert n == 2


# ── v6.5.2 : bugs de propagation multi-modèle restants ──

def test_load_features_not_processed_model_aware(test_db):
    """Deux modèles doivent pouvoir traiter le MÊME feature_uid (même agent/run_number) : après
    que mr_a a produit la sortie, mr_b doit TOUJOURS voir la feature comme à traiter."""
    from utils.db_utils import load_features_not_processed
    mr_a, mr_b = _two_models(test_db)
    save_agent_output("r1", 1, "encoder", 1, {"e": "A"}, "raw", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6, 1), model_run_id=mr_a)
    # mr_a : la feature est traitée → plus en attente
    assert [f["feature_uid"] for f in load_features_not_processed("r1", "encoder", 1, mr_a)] == []
    # mr_b : la même feature est ENCORE à traiter (sinon la réplication serait bloquée)
    assert [f["feature_uid"] for f in load_features_not_processed("r1", "encoder", 1, mr_b)] == [_uid(6, 1)]


def test_build_batch_item_rows_none_ne_produit_pas_null(test_db):
    """build_batch_item_rows(features) avec model_run_id=None, puis register_batch_with_items(...,
    model_run_id='r1::legacy') : l'item doit insérer 'r1::legacy', JAMAIS NULL (fallback `or`)."""
    conn = sqlite3.connect(test_db); _run(conn); _feat(conn, 6, 1); conn.commit(); conn.close()
    ensure_legacy_model_run("r1")                       # crée la ligne model_runs 'r1::legacy' (FK)
    feats = [{"feature_uid": _uid(6, 1), "feature_index": 1}]
    rows = build_batch_item_rows(feats)                 # model_run_id=None dans chaque item
    assert rows[0]["model_run_id"] is None
    register_batch_with_items("bL", "r1", "p3", "encoder", 1, 1, rows, model_run_id="r1::legacy")
    m = load_batch_item_map("bL")
    assert m[feature_custom_id(feats[0])]["model_run_id"] == "r1::legacy"
    conn = sqlite3.connect(test_db)
    n_null = conn.execute("SELECT COUNT(*) FROM batch_items WHERE model_run_id IS NULL").fetchone()[0]
    conn.close()
    assert n_null == 0


def test_get_unconsumed_batch_legacy_retrouvable(test_db):
    """Un batch legacy enregistré via register_batch(..., model_run_id=None) doit être retrouvé
    par get_unconsumed_batch(..., model_run_id=None) (les deux résolvent le même legacy)."""
    from utils.db_utils import register_batch, get_unconsumed_batch
    conn = sqlite3.connect(test_db); _run(conn); conn.commit(); conn.close()
    register_batch("bLeg", "r1", "p3", "encoder", 1, 1)          # model_run_id=None → legacy
    assert get_unconsumed_batch("r1", "p3", "encoder", 1) == "bLeg"   # None → legacy aussi


def test_resume_restaure_model_run_ids(test_db):
    """Après enregistrement d'un primaire + secondaire, restore_model_run_ids reconstruit les
    mêmes model_run_id depuis la DB (reprise --resume)."""
    from utils.db_utils import restore_model_run_ids
    conn = sqlite3.connect(test_db); _run(conn); conn.commit(); conn.close()
    cfg = {"model_providers": {
        "primary_reproducible":  {"model_name": "Qwen",  "tier": "B_open_weight"},
        "secondary_proprietary": {"model_name": "claude","tier": "C_proprietary_api"},
    }}
    mr_p = register_model_run("r1", cfg["model_providers"]["primary_reproducible"], is_primary_scientific=True)
    mr_s = register_model_run("r1", cfg["model_providers"]["secondary_proprietary"], is_primary_scientific=False)
    ids = restore_model_run_ids("r1", cfg)
    assert ids["primary"] == mr_p and ids["secondary"] == mr_s
    assert cfg["_runtime"]["model_run_ids"]["primary"] == mr_p     # bien écrit dans _runtime


# ── v6.5.3 : fuite multi-modèle en Phase 4 (chargement du steering) ──

def test_steering_charge_uniquement_le_modele_primaire(test_db):
    """Phase 4 strictement model-aware : deux sorties encoder pour le MÊME feature_uid (modèles
    A et B, expressions différentes) ; _load_encoded_random_features (la logique de chargement
    de steerer.run) ne récupère QUE l'annotation du modèle primaire, jamais celle du secondaire."""
    from agents.steerer import _load_encoded_random_features
    mr_a, mr_b = _two_models(test_db)
    save_agent_output("r1", 1, "encoder", 1, {"expression": "0.80·ag-is"}, "rawA", "ok", None,
                      1, 1, None, 0.0, feature_uid=_uid(6, 1), model_run_id=mr_a)
    save_agent_output("r1", 1, "encoder", 1, {"expression": "0.70·sci-o"}, "rawB", "ok", None,
                      1, 1, None, 0.0, feature_uid=_uid(6, 1), model_run_id=mr_b)
    feats = _load_encoded_random_features("r1", mr_a)              # steering sous le modèle PRIMAIRE
    assert len(feats) == 1 and feats[0]["feature_uid"] == _uid(6, 1)
    assert feats[0]["expression"] == "0.80·ag-is"                 # annotation du primaire (A)
    # aucune sortie secondaire/legacy n'est steerable sous le model_run_id primaire
    assert "0.70·sci-o" not in {f["expression"] for f in feats}
    # symétriquement, le secondaire ne voit que sa propre annotation
    feats_b = _load_encoded_random_features("r1", mr_b)
    assert len(feats_b) == 1 and feats_b[0]["expression"] == "0.70·sci-o"
