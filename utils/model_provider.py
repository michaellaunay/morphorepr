# utils/model_provider.py
"""
Abstraction d'inférence multi-fournisseurs (Règle 11). Une seule interface generate() ;
les imports lourds (anthropic, vllm, transformers, llama_cpp) sont PARESSEUX pour que ce
module s'importe sans toutes les dépendances installées. AnthropicProvider est CONSERVÉ.
"""
from typing import Optional


class ModelProvider:
    """Interface commune. Toute implémentation expose generate() avec la MÊME signature."""
    tier: str = "unknown"          # A_fully_open | B_open_weight | C_proprietary_api

    def generate(self, messages: list[dict], system_prompt: str,
                 max_tokens: int, generation_params: dict) -> str:
        raise NotImplementedError


class AnthropicProvider(ModelProvider):
    """Tier C — API propriétaire (conditionnée SECONDAIRE par défaut, Règle 11)."""
    tier = "C_proprietary_api"

    def __init__(self, model_name: str, api_version: Optional[str] = None):
        import anthropic                       # import paresseux
        self._client = anthropic.Anthropic()
        self.model_name = model_name
        self.api_version = api_version

    def generate(self, messages, system_prompt, max_tokens, generation_params):
        params = {"model": self.model_name, "max_tokens": max_tokens,
                  "system": system_prompt, "messages": messages}
        if generation_params.get("temperature") is not None:
            params["temperature"] = generation_params["temperature"]
        resp = self._client.messages.create(**params)
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


class VLLMProvider(ModelProvider):
    """Tier A/B — modèle local servi par vLLM (révision épinglée)."""
    tier = "B_open_weight"

    def __init__(self, model_name: str, model_revision: Optional[str] = None,
                 precision: str = "bfloat16", quantization: Optional[str] = None):
        from vllm import LLM                    # import paresseux
        self.model_name = model_name
        self.model_revision = model_revision
        kw = {"model": model_name, "dtype": precision}
        if model_revision:
            kw["revision"] = model_revision
        if quantization:
            kw["quantization"] = quantization
        self._llm = LLM(**kw)

    def generate(self, messages, system_prompt, max_tokens, generation_params):
        from vllm import SamplingParams
        prompt = self._apply_chat_template(system_prompt, messages)
        sp = SamplingParams(
            temperature=generation_params.get("temperature", 0.0),
            top_p=generation_params.get("top_p", 1.0),
            seed=generation_params.get("seed", 42),
            max_tokens=max_tokens,
        )
        out = self._llm.generate([prompt], sp)
        return out[0].outputs[0].text

    def _apply_chat_template(self, system_prompt, messages):
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(self.model_name, revision=self.model_revision)
        full = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
        return tok.apply_chat_template(full, tokenize=False, add_generation_prompt=True)


class TransformersProvider(ModelProvider):
    """Tier A/B — HuggingFace Transformers (petits modèles, tests, ou backend par défaut)."""
    tier = "B_open_weight"

    def __init__(self, model_name: str, model_revision: Optional[str] = None,
                 precision: str = "bfloat16"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.model_name = model_name
        self.model_revision = model_revision
        self._tok = AutoTokenizer.from_pretrained(model_name, revision=model_revision)
        dtype = getattr(torch, precision, torch.float32)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name, revision=model_revision, torch_dtype=dtype)

    def generate(self, messages, system_prompt, max_tokens, generation_params):
        full = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
        inputs = self._tok.apply_chat_template(full, return_tensors="pt",
                                               add_generation_prompt=True)
        gen = self._model.generate(
            inputs, max_new_tokens=max_tokens,
            do_sample=generation_params.get("temperature", 0.0) > 0,
            temperature=generation_params.get("temperature", 0.0) or None,
            top_p=generation_params.get("top_p", 1.0),
        )
        return self._tok.decode(gen[0][inputs.shape[1]:], skip_special_tokens=True)


class LlamaCppProvider(ModelProvider):
    """Tier A/B — modèles GGUF quantifiés via llama.cpp (optionnel)."""
    tier = "B_open_weight"

    def __init__(self, model_path: str, n_ctx: int = 8192):
        from llama_cpp import Llama             # import paresseux
        self._llm = Llama(model_path=model_path, n_ctx=n_ctx, logits_all=False)

    def generate(self, messages, system_prompt, max_tokens, generation_params):
        full = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
        out = self._llm.create_chat_completion(
            messages=full, max_tokens=max_tokens,
            temperature=generation_params.get("temperature", 0.0),
            top_p=generation_params.get("top_p", 1.0),
            seed=generation_params.get("seed", 42),
        )
        return out["choices"][0]["message"]["content"]


_BACKENDS = {
    "anthropic":    lambda c: AnthropicProvider(c["model_name"], c.get("api_version")),
    "vllm":         lambda c: VLLMProvider(c["model_name"], c.get("model_revision"),
                                           c.get("precision", "bfloat16"), c.get("quantization")),
    "transformers": lambda c: TransformersProvider(c["model_name"], c.get("model_revision"),
                                                   c.get("precision", "bfloat16")),
    "llama_cpp":    lambda c: LlamaCppProvider(c["model_name"], c.get("n_ctx", 8192)),
}


def build_provider(provider_cfg: dict) -> ModelProvider:
    """Fabrique un ModelProvider depuis une entrée de config model_providers.
    backend 'anthropic' OU provider 'anthropic' → AnthropicProvider ; sinon backend local."""
    backend = provider_cfg.get("backend")
    if provider_cfg.get("provider") == "anthropic" and not backend:
        backend = "anthropic"
    if backend not in _BACKENDS:
        raise ValueError(f"Backend inconnu : {backend!r} (attendus : {sorted(_BACKENDS)}).")
    return _BACKENDS[backend](provider_cfg)
