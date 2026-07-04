# ─────────────────────────────────────────────
# tests/test_steer_feature.py  (v6.6.1 — durcissement du chemin proxy open-weight)
# Mocks légers de l'API TransformerLens/SAE Lens : aucun modèle réel n'est chargé (sauf le
# test slow, opt-in). On vérifie l'absence de placeholder, le delta, l'OOD, le mode non
# implémenté, la sélection de positions, le hook, assert_steering_ready, ET (v6.6.1) :
# _generate_text adaptatif (signatures variables), hook réellement actif pendant la génération,
# validations de shapes/bornes, dtype préservé.
# ─────────────────────────────────────────────

import os
import types
import contextlib
import pytest
import torch

import agents.steerer as steerer
from agents.steerer import (
    steer_feature, assert_steering_ready, _is_ood, REQUIRED_STEER_FIELDS,
    _position_indices, _selected_token_positions, _make_residual_add_decoder_hook,
    _supported_generate_kwargs, _generate_text, _measure_feature_activation,
    _aggregate_feature_activation, _validate_feature_and_shapes,
)

D_MODEL, D_SAE = 4, 3


class _FakeSAE:
    """W_dec[0] = e_0 ; encode = projection identité sur les d_sae premières dims du résiduel.
    Donc activation du feature 0 = composante 0 du résiduel."""
    def __init__(self):
        self.W_dec = torch.zeros(D_SAE, D_MODEL)
        self.W_dec[0, 0] = 1.0
        self.cfg = types.SimpleNamespace(hook_name="blocks.0.hook_resid_post", hook_layer=0)

    def encode(self, resid):
        return resid[..., :D_SAE]


class _FakeModel:
    """Mock minimal de HookedTransformer : to_tokens / run_with_hooks / hooks / generate.
    Le résiduel de base est un tenseur de 1.0 ; generate marque l'état (steering on/off)."""
    def __init__(self):
        self.cfg = types.SimpleNamespace(d_model=D_MODEL)
        self.tokenizer = types.SimpleNamespace(pad_token_id=None)
        self._steering = False

    def to_tokens(self, sentence, prepend_bos=True):
        n = max(1, len(str(sentence).split()))
        return torch.arange(0, n + 1).unsqueeze(0)        # [1, n+1] (index 0 = BOS)

    def run_with_hooks(self, tokens, fwd_hooks=None, return_type=None):
        seq = tokens.shape[1]
        resid = torch.ones(1, seq, D_MODEL)               # résiduel de base
        hook = types.SimpleNamespace(name="blocks.0.hook_resid_post")
        for _name, fn in (fwd_hooks or []):
            resid = fn(resid, hook)                       # intervention puis capture
        return None

    @contextlib.contextmanager
    def hooks(self, fwd_hooks=None):
        self._steering = True
        try:
            yield self
        finally:
            self._steering = False

    def generate(self, prompt, **kw):
        return prompt + (" STEERED" if self._steering else " CONT")


def _config(intervention_space="residual_add_decoder", token_position="all"):
    return {
        "proxy_model": {"enabled": True, "name": "fake", "sae_release": "fake"},
        "steering": {
            "intervention_space": intervention_space,
            "token_position": token_position,
            "activation_aggregation": "max",
            "decoding": {"temperature": 0.0, "max_new_tokens": 8},
            "ood_tau": 3.0, "ood_k": 4.0, "ood_epsilon": 1e-3, "ood_delta_max": 5.0,
        },
    }


_STATS = {"activation_p99": 10.0, "activation_mean": 1.0, "activation_std": 1.0}


# 1. Pas de placeholder : champs requis présents, text_after non None et ≠ text_before
def test_steer_feature_no_placeholder():
    res = steer_feature(_FakeModel(), _FakeSAE(), feature_index=0, magnitude=1.5,
                        probe_sentences=["the cat sat on the mat"],
                        feature_stats=_STATS, config=_config())
    assert len(res) == 1
    r = res[0]
    for f in REQUIRED_STEER_FIELDS:
        assert f in r
    assert r["text_after"] is not None
    assert r["text_after"] != r["text_before"]            # le steering change la sortie générée
    assert isinstance(r["text_before"], str) and r["text_before"] != "the cat sat on the mat"


# 2. Calcul du delta : base=1.0 (résiduel de 1), magnitude=1.5 → after=2.5, delta=1.5
def test_steer_feature_delta():
    res = steer_feature(_FakeModel(), _FakeSAE(), feature_index=0, magnitude=1.5,
                        probe_sentences=["alpha beta gamma"],
                        feature_stats=_STATS, config=_config())
    r = res[0]
    assert abs(r["activation_before"] - 1.0) < 1e-6
    assert abs(r["activation_after"] - 2.5) < 1e-6
    assert abs(r["achieved_delta"] - 1.5) < 1e-6


# 3. OOD : un delta excessif déclenche ood_flag=1 (stats contrôlées)
def test_is_ood_flag():
    cfg = _config()
    stats = {"activation_p99": 1.0, "activation_mean": 0.5, "activation_std": 0.2}
    assert _is_ood(activation_after=100.0, activation_before=1.0,
                   feature_stats=stats, config=cfg) == 1
    assert _is_ood(activation_after=0.6, activation_before=0.5,
                   feature_stats=stats, config=cfg) == 0


# 4. Mode non implémenté : sae_latent_clamp lève NotImplementedError explicitement
def test_sae_latent_clamp_not_implemented():
    with pytest.raises(NotImplementedError):
        steer_feature(_FakeModel(), _FakeSAE(), feature_index=0, magnitude=1.0,
                      probe_sentences=["x y z"], feature_stats=_STATS,
                      config=_config(intervention_space="sae_latent_clamp"))


# 4b. Chemin non-proxy : NotImplementedError explicite (nnsight / production non implémenté)
def test_non_proxy_not_implemented():
    cfg = _config(); cfg["proxy_model"]["enabled"] = False
    with pytest.raises(NotImplementedError):
        steer_feature(_FakeModel(), _FakeSAE(), feature_index=0, magnitude=1.0,
                      probe_sentences=["x y z"], feature_stats=_STATS, config=cfg)


# 5. Sélection de positions : all / last / content_only
def test_token_position_selection():
    assert _position_indices(5, "all") == [0, 1, 2, 3, 4]
    assert _position_indices(5, "last") == [4]
    assert _position_indices(5, "content_only") == [1, 2, 3, 4]      # exclut le BOS
    toks = torch.arange(0, 5).unsqueeze(0)                            # [1,5]
    assert _selected_token_positions(toks, "last") == [4]
    assert _selected_token_positions(toks, "content_only") == [1, 2, 3, 4]


# 6. Hook : ajoute magnitude·W_dec[feature_index] aux positions sélectionnées seulement
def test_residual_add_decoder_hook_last_position_only():
    sae = _FakeSAE()
    hook = _make_residual_add_decoder_hook(sae, feature_index=0, magnitude=2.0,
                                           token_position="last", config=_config())
    resid = torch.zeros(1, 4, D_MODEL)
    hook_obj = types.SimpleNamespace(name="blocks.0.hook_resid_post")
    out = hook(resid, hook_obj)
    # dernière position modifiée de 2.0·e_0, les autres inchangées
    assert torch.allclose(out[0, -1], torch.tensor([2.0, 0.0, 0.0, 0.0]))
    assert torch.allclose(out[0, :-1], torch.zeros(3, D_MODEL))


# 7. assert_steering_ready : passe avec mocks ; échoue si text_after == placeholder
def test_assert_steering_ready_passes_and_fails(test_db, monkeypatch):
    import sqlite3
    conn = sqlite3.connect(test_db)
    conn.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,
        lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,started_at,
        completed_at,status,last_phase,total_cost_usd) VALUES ('r1','c','h','{}','v1','lh',NULL,'{}',
        0,NULL,42,NULL,'t',NULL,'loading',NULL,0.0)""")
    conn.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,
        feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,
        activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES
        ('gpt2:res-jb:0:hook_resid_post:0','gpt2','res-jb',0,'hook_resid_post',0,'random','d','[]',
        0.8,0.5,10.0,1.0,1.0,'0','x','t')""")
    conn.commit(); conn.close()

    monkeypatch.setattr(steerer, "_get_model", lambda config: _FakeModel())
    monkeypatch.setattr(steerer, "_get_sae", lambda config, layer: _FakeSAE())
    monkeypatch.setattr(steerer, "load_probe_sentences",
                        lambda n=5, family="neutral": [f"probe number {i} here" for i in range(n)])

    # passe : steer_feature réel produit text_after ('… STEERED') ≠ text_before ('… CONT')
    assert_steering_ready(_config(), n_probe=3)

    # échoue : steer_feature renvoie un text_after == text_before (placeholder simulé)
    def _placeholder_steer(model, sae, feature_index, magnitude, probe_sentences, feature_stats, config):
        return [{"probe_id": 1, "text_before": "same", "text_after": "same",
                 "activation_before": 1.0, "activation_after": 1.0,
                 "achieved_delta": 0.0, "ood_flag": 0}]
    monkeypatch.setattr(steerer, "steer_feature", _placeholder_steer)
    with pytest.raises(RuntimeError):
        assert_steering_ready(_config(), n_probe=3)


# ── v6.6.1 : _generate_text robuste aux signatures variables de model.generate ──

class _FakeModelNoDoSample:
    """generate() N'ACCEPTE PAS do_sample/top_p : _generate_text ne doit PAS les passer."""
    def __init__(self):
        self.received = None
    @contextlib.contextmanager
    def hooks(self, fwd_hooks=None):
        yield self
    def generate(self, prompt, max_new_tokens=16, temperature=0.0, verbose=False):
        self.received = {"max_new_tokens": max_new_tokens, "temperature": temperature,
                         "verbose": verbose}
        return prompt + " OUT"


def test_generate_text_filters_unsupported_kwargs():
    m = _FakeModelNoDoSample()
    out = _generate_text(m, "hello world", _config())          # ne doit pas planter
    assert out == "hello world OUT"
    assert "do_sample" not in m.received and "top_p" not in m.received   # filtrés
    assert m.received["temperature"] == 0.0 and m.received["verbose"] is False


class _FakeModelVarKw:
    """generate(**kwargs) : tout doit être conservé (VAR_KEYWORD)."""
    def __init__(self):
        self.received = None
    @contextlib.contextmanager
    def hooks(self, fwd_hooks=None):
        yield self
    def generate(self, prompt, **kwargs):
        self.received = kwargs
        return prompt + " OUT"


def test_generate_text_var_keyword_keeps_all():
    m = _FakeModelVarKw()
    _generate_text(m, "x", _config())
    assert m.received.get("do_sample") is False and m.received.get("temperature") == 0.0
    assert "max_new_tokens" in m.received


def test_generate_text_missing_generate_raises():
    class _NoGen:
        pass
    with pytest.raises(AttributeError):
        _supported_generate_kwargs(_NoGen(), {"do_sample": False})


# ── v6.6.1 : le hook est RÉELLEMENT exécuté pendant model.generate ──

class _HookExecModel:
    """generate() exécute RÉELLEMENT les hooks enregistrés via hooks(fwd_hooks=...), comme
    TransformerLens : prouve que le hook modifie le résiduel pendant la génération (et pas un
    simple booléen _steering). Trace les hook_name vus/appelés."""
    def __init__(self):
        self.cfg = types.SimpleNamespace(d_model=D_MODEL)
        self.tokenizer = types.SimpleNamespace(pad_token_id=None)
        self._fwd = []
        self.hooks_entered = []
        self.hook_calls = []

    def to_tokens(self, s, prepend_bos=True):
        n = max(1, len(str(s).split()))
        return torch.arange(0, n + 1).unsqueeze(0)

    def run_with_hooks(self, tokens, fwd_hooks=None, return_type=None):
        seq = tokens.shape[1]
        resid = torch.ones(1, seq, D_MODEL)
        h = types.SimpleNamespace(name="blocks.0.hook_resid_post")
        for _n, fn in (fwd_hooks or []):
            resid = fn(resid, h)
        return None

    @contextlib.contextmanager
    def hooks(self, fwd_hooks=None):
        self._fwd = list(fwd_hooks or [])
        self.hooks_entered += [n for n, _ in self._fwd]
        try:
            yield self
        finally:
            self._fwd = []

    def generate(self, prompt, **kw):
        # exécute les hooks sur un résiduel (comme pendant un forward de génération)
        resid = torch.zeros(1, 3, D_MODEL)
        h = types.SimpleNamespace(name="blocks.0.hook_resid_post")
        for name, fn in self._fwd:
            resid = fn(resid, h)
            self.hook_calls.append(name)
        total = float(resid.sum().item())
        return f"{prompt} [resid_sum={total:.1f}]"   # le texte DÉPEND de la modif réelle


def test_hook_actually_runs_during_generation():
    m = _HookExecModel()
    res = steer_feature(m, _FakeSAE(), feature_index=0, magnitude=3.0,
                        probe_sentences=["alpha beta"], feature_stats=_STATS, config=_config())
    r = res[0]
    # hook enregistré avec le bon hook_name pendant la génération AFTER, et réellement appelé
    assert "blocks.0.hook_resid_post" in m.hooks_entered
    assert "blocks.0.hook_resid_post" in m.hook_calls
    # text_after dépend de la modification effective du résiduel (≠ before non steeré)
    assert r["text_after"] != r["text_before"]
    assert "resid_sum=0.0" in r["text_before"]      # before : aucun hook → résiduel inchangé
    assert "resid_sum=9.0" in r["text_after"]       # after : +3·e0 sur 3 positions → somme 9.0


# ── v6.6.1 : validations de shapes / bornes ──

def test_feature_index_out_of_bounds():
    with pytest.raises(IndexError):
        steer_feature(_FakeModel(), _FakeSAE(), feature_index=99, magnitude=1.0,
                      probe_sentences=["x y"], feature_stats=_STATS, config=_config())


def test_validate_shapes_dmodel_mismatch():
    sae = _FakeSAE()
    with pytest.raises(ValueError):
        _validate_feature_and_shapes(sae, 0, torch.ones(1, 3, D_MODEL + 2))   # d_model incompatible
    with pytest.raises(IndexError):
        _validate_feature_and_shapes(sae, 999, torch.ones(1, 3, D_MODEL))     # feature_index OOB


class _FakeSAETuple(_FakeSAE):
    def encode(self, resid):
        return (resid[..., :D_SAE], {"aux": 1})     # certaines versions renvoient un tuple


def test_encode_returns_tuple_supported():
    m = _FakeModel()
    val = _measure_feature_activation(m, _FakeSAETuple(), m.to_tokens("alpha beta gamma"),
                                      0, _config())
    assert isinstance(val, float) and abs(val - 1.0) < 1e-6   # tuple toléré (acts[0] utilisé)


def test_aggregate_handles_2d_and_3d():
    acts3 = torch.zeros(1, 4, D_SAE); acts3[0, 2, 0] = 5.0    # [batch, seq, d_sae]
    acts2 = torch.zeros(4, D_SAE);    acts2[2, 0] = 5.0       # [seq, d_sae]
    assert abs(_aggregate_feature_activation(acts3, [0, 1, 2, 3], 0) - 5.0) < 1e-6
    assert abs(_aggregate_feature_activation(acts2, [0, 1, 2, 3], 0) - 5.0) < 1e-6


# ── v6.6.1 : device / dtype ──

def test_hook_preserves_residual_dtype():
    sae = _FakeSAE()                              # W_dec float32
    assert sae.W_dec.dtype == torch.float32
    hook = _make_residual_add_decoder_hook(sae, 0, 2.0, "all", _config())
    for dt in (torch.float16, torch.bfloat16):
        resid = torch.ones(1, 3, D_MODEL, dtype=dt)
        out = hook(resid, types.SimpleNamespace(name="x"))
        assert out.dtype == dt                    # dtype préservé malgré W_dec float32
        assert torch.allclose(out[0, 0, 0].float(), torch.tensor(3.0), atol=1e-2)  # 1 + 2·1


# 8. Intégration optionnelle (slow) — uniquement si MORPHOREPR_RUN_SLOW_STEERING=1
@pytest.mark.skipif(os.environ.get("MORPHOREPR_RUN_SLOW_STEERING") != "1",
                    reason="test slow opt-in : nécessite un petit modèle proxy + SAE public")
def test_steer_feature_integration_slow():
    # Skip PROPRE (message explicite) si le modèle/SAE proxy est indisponible — pas d'échec muet.
    try:
        import transformer_lens
        from sae_lens import SAE
        model = transformer_lens.HookedTransformer.from_pretrained("gpt2")
        sae, _, _ = SAE.from_pretrained(release="gpt2-small-res-jb",
                                        sae_id="blocks.6.hook_resid_post")
    except Exception as e:
        pytest.skip(f"modèle/SAE proxy indisponible ({type(e).__name__}: {e}) — test slow ignoré.")

    cfg = _config(); cfg["steering"]["decoding"]["max_new_tokens"] = 8
    res = steer_feature(model, sae, feature_index=0, magnitude=4.0,
                        probe_sentences=["The weather today is"],
                        feature_stats={"activation_p99": 5.0, "activation_mean": 1.0,
                                       "activation_std": 1.0},
                        config=cfg)
    assert len(res) == 1
    r = res[0]
    assert isinstance(r["text_before"], str) and len(r["text_before"]) > 0
    assert isinstance(r["text_after"], str) and len(r["text_after"]) > 0
    assert isinstance(r["activation_before"], float)
    assert isinstance(r["activation_after"], float)
    assert isinstance(r["achieved_delta"], float)
    assert r["ood_flag"] in (0, 1)
