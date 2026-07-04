# ─────────────────────────────────────────────
# tests/test_model_providers.py  (v6.5 — reproductibilité par modèles ouverts, Règle 11)
# ─────────────────────────────────────────────

import sqlite3
import pytest
from utils.model_provider import (ModelProvider, AnthropicProvider, VLLMProvider,
                                  TransformersProvider, LlamaCppProvider, build_provider)
from utils.model_policy import (validate_model_providers, assert_primary_claim_allowed,
                                classify_cross_model_effect)
from utils.db_utils import register_model_run, save_agent_output, load_model_runs


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


_PRIMARY = {"tier": "B_open_weight", "provider": "local", "backend": "vllm",
            "model_name": "Qwen/Qwen3-8B-Instruct", "model_revision": "abc123",
            "tokenizer_revision": "abc123", "weights_sha256": "deadbeef",
            "tokenizer_sha256": "cafef00d", "inference_container_hash": "img@sha256:1",
            "inference_env_hash": "env@sha256:1",
            "deterministic_generation": {"temperature": 0.0, "seed": 42}}
_SECONDARY = {"tier": "C_proprietary_api", "provider": "anthropic",
              "model_name": "claude-sonnet-4-6", "use_for_primary_claims": False}


def test_model_provider_interface():
    """Tous les providers exposent generate() avec la même interface ; build_provider rejette
    un backend inconnu. (Pas d'instanciation : imports lourds paresseux.)"""
    for cls in (AnthropicProvider, VLLMProvider, TransformersProvider, LlamaCppProvider):
        assert issubclass(cls, ModelProvider)
        assert callable(getattr(cls, "generate"))
    with pytest.raises(NotImplementedError):
        ModelProvider().generate([], "", 10, {})
    with pytest.raises(ValueError):
        build_provider({"backend": "unknown_backend", "model_name": "x"})


def test_model_run_id_isolation(test_db):
    """Deux modèles produisent des sorties pour le MÊME feature_uid sans collision."""
    conn = sqlite3.connect(test_db); _run(conn); _feat(conn, 6); conn.commit(); conn.close()
    mr_a = register_model_run("r1", _PRIMARY, is_primary_scientific=True)
    mr_b = register_model_run("r1", _SECONDARY, is_primary_scientific=False)
    save_agent_output("r1", 1, "encoder", 1, {"expr": "A"}, "rawA", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6), model_run_id=mr_a)
    save_agent_output("r1", 1, "encoder", 1, {"expr": "B"}, "rawB", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6), model_run_id=mr_b)
    conn = sqlite3.connect(test_db)
    n = conn.execute("SELECT COUNT(*) FROM agent_outputs WHERE feature_uid=?", (_uid(6),)).fetchone()[0]
    conn.close()
    assert n == 2                                  # une sortie par modèle, pas d'écrasement


def test_primary_claim_requires_open_model():
    """assert_primary_claim_allowed refuse un modèle Tier C et accepte un Tier A/B éligible."""
    with pytest.raises(ValueError):
        assert_primary_claim_allowed({"model_name": "claude", "provider_tier": "C_proprietary_api",
                                      "use_for_primary_claims": 0})
    assert_primary_claim_allowed({"model_name": "Qwen", "provider_tier": "B_open_weight",
                                  "use_for_primary_claims": 1})   # ne lève pas


def test_model_artifact_hashes_required():
    """Un full run échoue si le modèle primaire ouvert n'a pas révisions/hashes/env."""
    incomplete = dict(_PRIMARY); incomplete["weights_sha256"] = "FILL_BEFORE_FULL_RUN"
    cfg = {"model_providers": {"primary_reproducible": incomplete}}
    with pytest.raises(ValueError):
        validate_model_providers(cfg, "full")
    # complet → passe
    validate_model_providers({"model_providers": {"primary_reproducible": _PRIMARY}}, "full")


def test_anthropic_is_secondary_by_default(test_db):
    """provider_tier=C_proprietary_api ⇒ use_for_primary_claims=0 par défaut en DB."""
    conn = sqlite3.connect(test_db); _run(conn); conn.commit(); conn.close()
    mr = register_model_run("r1", _SECONDARY, is_primary_scientific=False)  # pas d'override explicite
    rows = {r["model_run_id"]: r for r in load_model_runs("r1")}
    assert rows[mr]["provider_tier"] == "C_proprietary_api"
    assert rows[mr]["use_for_primary_claims"] == 0


def test_cross_model_report():
    """Le rapport sépare les métriques par modèle/tier ; classify_cross_model_effect étiquette."""
    per_model = {
        "mr_open":  {"tier": "B_open_weight",     "significant": True},
        "mr_prop":  {"tier": "C_proprietary_api", "significant": True},
    }
    assert classify_cross_model_effect(per_model) == "model-invariant"
    assert classify_cross_model_effect({"mr_open": {"tier": "B_open_weight", "significant": True},
                                        "mr_prop": {"tier": "C_proprietary_api", "significant": False}}) == "open-model-only"
    assert classify_cross_model_effect({"mr_open": {"tier": "A_fully_open", "significant": False},
                                        "mr_prop": {"tier": "C_proprietary_api", "significant": True}}) == "proprietary-only"
    assert classify_cross_model_effect({"mr_open": {"tier": "B_open_weight", "significant": False}}) == "unstable"
    # séparation par tier : aucune fusion d'un score Tier C dans le bucket "ouvert"
    open_tiers = ("A_fully_open", "B_open_weight")
    buckets = {"open": [], "proprietary": []}
    for mid, m in per_model.items():
        key = "open" if m["tier"] in open_tiers else "proprietary"
        buckets[key].append(mid)
    assert buckets["open"] == ["mr_open"] and buckets["proprietary"] == ["mr_prop"]
