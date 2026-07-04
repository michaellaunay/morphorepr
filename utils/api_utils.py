# utils/api_utils.py
"""
LEGACY Anthropic Batch API wrapper.

Ce module est le SEUL endroit autorisé à instancier le client Anthropic (`anthropic.Anthropic()`),
et UNIQUEMENT pour la **condition propriétaire secondaire** (Tier C, Règle 11). Les agents ne
l'utilisent pas directement pour produire des claims primaires : pour l'inférence scientifique
(modèle ouvert primaire), ils passent par `utils.model_provider.ModelProvider` (Section 5 bis).
Tout batch est rattaché à un `model_run_id` (par défaut un model_run legacy explicite).
La config est toujours passée explicitement — aucun appel load_config() ici.
"""
import anthropic
import hashlib
import json
import logging
import time
from typing import Optional, Callable
from utils.db_utils import (register_batch, register_batch_with_items,
                             mark_batch_consumed, ensure_legacy_model_run,
                             get_unconsumed_batch, log_api_cost, check_budget,
                             save_batch_items, load_batch_item_map)

logger = logging.getLogger(__name__)

# Init paresseuse : ne pas instancier le client (ni exiger ANTHROPIC_API_KEY) à l'import,
# afin que les tests unitaires sans clé puissent importer ce module.
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client

COST_PER_MTK = {
    "claude-sonnet-4-6":         {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0,  "output": 5.0},
}
BATCH_DISCOUNT = 0.50


def compute_cost(model: str, tokens_in: int, tokens_out: int,
                 is_batch: bool = True) -> float:
    rates = COST_PER_MTK.get(model, {"input": 3.0, "output": 15.0})
    cost  = ((tokens_in  / 1_000_000) * rates["input"] +
             (tokens_out / 1_000_000) * rates["output"])
    return cost * (BATCH_DISCOUNT if is_batch else 1.0)


def estimate_batch_cost(requests: list[dict], model: str) -> float:
    """Estimation GROSSIÈRE du coût d'un batch AVANT soumission (heuristique chars/4 pour
    l'entrée, max_tokens pour la sortie). Sert au garde-fou budgétaire pré-soumission, pas
    à la comptabilité réelle (faite après réception via compute_cost sur l'usage réel)."""
    tin = tout = 0
    for r in requests:
        p = r.get("params", {})
        sys_txt = p.get("system", "") or ""
        msg_txt = "".join(
            m.get("content", "") if isinstance(m.get("content"), str) else ""
            for m in p.get("messages", [])
        )
        tin  += max(1, (len(sys_txt) + len(msg_txt)) // 4)   # ≈ 4 chars/token
        tout += p.get("max_tokens", 512)
    return compute_cost(model, tin, tout, is_batch=True)


def feature_custom_id(f: dict) -> str:
    """custom_id Batch API fondé sur feature_uid (PAS feature_index seul, ambigu entre
    couches/SAEs — Règle 10). Format lisible : 'feature_{index}_{sha1(uid)[:12]}'.
    Le hash garantit l'unicité ; l'index n'est là que pour le debug."""
    h = hashlib.sha1(f["feature_uid"].encode()).hexdigest()[:12]
    return f"feature_{f['feature_index']}_{h}"


def build_custom_id_map(features: list[dict]) -> dict[str, str]:
    """Table de correspondance custom_id → feature_uid, pour rattacher les sorties batch
    à leur identité logique au retour (save_agent_output exige feature_uid)."""
    return {feature_custom_id(f): f["feature_uid"] for f in features}


def build_batch_item_rows(features: list[dict], model_run_id: Optional[str] = None) -> list[dict]:
    """Lignes pour batch_items (persistance crash-safe du mapping). model_run_id rattache
    chaque entrée au modèle producteur (batch_items.model_run_id NOT NULL, Règle 11)."""
    return [{"custom_id": feature_custom_id(f),
             "feature_uid": f["feature_uid"],
             "feature_index": f["feature_index"],
             "model_run_id": model_run_id} for f in features]


def build_batch_requests(features: list[dict],
                         system_prompt: str,
                         user_prompt_fn: Callable,
                         model: str,
                         max_tokens: int,
                         config: dict) -> list[dict]:
    """
    Config passée explicitement. Température ajoutée uniquement si use_temperature=True.
    Évite les HTTP 400 sur les modèles qui rejettent les paramètres de sampling non par défaut.
    Les custom_id sont fondés sur feature_uid (cf. feature_custom_id) : deux features de
    couches différentes mais de même feature_index ne peuvent plus collisionner dans un batch.
    """
    sampling = config.get("sampling", {})
    requests = []
    for f in features:
        params = {
            "model":      model,
            "max_tokens": max_tokens,
            "system":     system_prompt,
            "messages":   [{"role": "user", "content": user_prompt_fn(f)}],
        }
        if sampling.get("use_temperature") and \
           sampling.get("temperature") is not None:
            params["temperature"] = sampling["temperature"]
        requests.append({
            "custom_id": feature_custom_id(f),
            "params":    params
        })
    return requests


def submit_and_poll_batch(requests: list[dict],
                          run_id: str,
                          phase: str,
                          agent_name: str,
                          run_number: int,
                          model: str,
                          config: dict,
                          persist_fn: Optional[Callable] = None,
                          batch_items: Optional[list[dict]] = None,
                          requires_feature_mapping: bool = True,
                          model_run_id: Optional[str] = None,
                          poll_interval: Optional[int] = None,
                          max_wait_seconds: Optional[int] = None) -> list[dict]:
    """
    Soumet un batch (ou récupère un batch non consommé existant) et retourne les résultats.
    Config passée explicitement partout. Chaque résultat est enrichi de `feature_uid` et
    `model_run_id` à partir de la map PERSISTÉE (batch_items), robuste à la reprise.

    model_run_id : modèle producteur (Règle 11) ; à défaut, un model_run legacy explicite.
    La reprise (get_unconsumed_batch) ET l'enregistrement filtrent/écrivent ce model_run_id,
    de sorte que deux modèles d'un même run ne peuvent JAMAIS reprendre le batch l'un de l'autre.

    requires_feature_mapping (défaut True) : pour un batch FEATURE-LEVEL, batch_items est
    OBLIGATOIRE (save_agent_output exige feature_uid). On lève ValueError si manquant, et à la
    reprise on BLOQUE si la map persistée est vide (au lieu d'un simple warning).

    Anti double-facturation (crash-safety) : si `persist_fn` est fourni, il est appelé
    avec les résultats AVANT de logger le coût et de marquer le batch consommé. Ainsi,
    en cas de crash après réception mais avant persistance, le batch reste 'submitted' ;
    à la reprise, get_unconsumed_batch le récupère et on RE-POLL le même batch (pas de
    nouvelle soumission, donc pas de double dépense) puis on re-persiste (idempotent).
    L'enregistrement batch + mapping est ATOMIQUE (register_batch_with_items) : pas de
    fenêtre où le batch existe sans sa map.
    """
    # Validation d'entrée PURE (sans DB) d'abord.
    if requires_feature_mapping and not batch_items:
        raise ValueError(
            "batch_items est requis pour un batch feature-level "
            "(passer build_batch_item_rows(features, model_run_id)). "
            "Mettre requires_feature_mapping=False pour un batch non-feature."
        )
    # Pré-vérification AVANT toute soumission (donc avant toute facturation) : les custom_id
    # des requêtes doivent correspondre EXACTEMENT à ceux de batch_items. Sinon, un mauvais
    # mapping (oubli, décalage features/requests) serait détecté trop tard, après facturation.
    if requires_feature_mapping:
        request_ids = {r["custom_id"] for r in requests}
        item_ids    = {it["custom_id"] for it in batch_items}
        if request_ids != item_ids:
            missing = request_ids - item_ids     # requêtes sans entrée de mapping
            extra   = item_ids - request_ids     # mappings sans requête correspondante
            raise ValueError(
                f"batch_items ne correspond pas aux requests "
                f"(custom_id). missing={sorted(missing)}, extra={sorted(extra)}"
            )
    # Résoudre le modèle producteur (écrit le model_run legacy si besoin) APRÈS la validation
    # d'entrée : get_unconsumed_batch et register_batch_with_items doivent utiliser le MÊME
    # model_run_id (sinon la reprise ne retrouverait pas le batch).
    model_run_id = model_run_id or ensure_legacy_model_run(run_id)
    batch_cfg        = config.get("batch", {})
    poll_interval    = poll_interval    or batch_cfg.get("poll_interval_seconds", 60)
    max_wait_seconds = max_wait_seconds or batch_cfg.get("max_wait_seconds", 86400)
    existing = get_unconsumed_batch(run_id, phase, agent_name, run_number, model_run_id)
    if existing:
        logger.info(f"Reprise du batch non consommé {existing}")
        batch_id = existing
    else:
        # Garde-fou budgétaire AVANT soumission (évite de soumettre un batch qui
        # dépasse mécaniquement le budget, constaté seulement après coup).
        if config.get("budget", {}).get("estimate_before_submit"):
            est = estimate_batch_cost(requests, model)
            max_cost = config["budget"]["max_cost_usd"]
            current, _ = check_budget(run_id, max_cost)
            if current + est > max_cost:
                raise RuntimeError(
                    f"Budget estimé dépassé AVANT soumission : "
                    f"cumul {current:.2f}$ + estimation {est:.2f}$ > {max_cost}$"
                )
            logger.info(f"Estimation pré-soumission : {est:.2f}$ (cumul {current:.2f}$)")
        batch = _get_client().messages.batches.create(requests=requests)
        batch_id = batch.id
        # Enregistrement ATOMIQUE batch + mapping (pas de fenêtre batch-sans-map), rattaché au modèle.
        register_batch_with_items(batch_id, run_id, phase, agent_name,
                                  run_number, len(requests), batch_items or [],
                                  model_run_id=model_run_id)
        logger.info(f"Batch soumis : {batch_id} ({len(requests)} requêtes)")

    elapsed = 0
    while elapsed < max_wait_seconds:
        status_obj = _get_client().messages.batches.retrieve(batch_id)
        if status_obj.processing_status == "ended":
            break
        elif status_obj.processing_status == "errored":
            raise RuntimeError(f"Batch {batch_id} erreur serveur")
        counts = status_obj.request_counts
        logger.info(f"Batch {batch_id} : {counts.processing} en cours, "
                    f"{counts.succeeded} réussis, {counts.errored} erreurs")
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(f"Batch {batch_id} timeout après {max_wait_seconds}s")

    results = []
    total_in, total_out = 0, 0
    for result in _get_client().messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            msg  = result.result.message
            # Concaténer tous les blocs de type 'text' (défensif : un premier bloc
            # non-textuel — p. ex. bloc de raisonnement/outil — ne casse pas le parsing).
            raw  = "".join(
                getattr(b, "text", "") for b in (msg.content or [])
                if getattr(b, "type", "") == "text"
            )
            tin  = msg.usage.input_tokens
            tout = msg.usage.output_tokens
            total_in  += tin
            total_out += tout
            parsed, status = _parse_json_output(raw, result.custom_id)
            results.append({
                "custom_id":     result.custom_id,
                "raw_output":    raw,
                "output_json":   parsed,
                "status":        status,
                "error_msg":     None,
                "tokens_input":  tin,
                "tokens_output": tout,
            })
        else:
            err = (result.result.error.message
                   if result.result.error else "unknown")
            results.append({
                "custom_id":     result.custom_id,
                "raw_output":    None,
                "output_json":   None,
                "status":        "failed",
                "error_msg":     err,
                "tokens_input":  0,
                "tokens_output": 0,
            })

    # Enrichir chaque résultat avec feature_uid depuis la map PERSISTÉE (robuste à la reprise :
    # le batch peut contenir des custom_id de features déjà persistées, absentes d'une map
    # reconstruite en mémoire). save_agent_output exige feature_uid.
    id_map = load_batch_item_map(batch_id)
    if requires_feature_mapping and not id_map:
        # Map persistée vide alors qu'on attend un mapping feature-level : cas d'un batch
        # enregistré par du code pré-v6.4 ou d'un crash entre register et items (n'arrive plus
        # avec register_batch_with_items). On BLOQUE plutôt que de risquer un mauvais rattachement.
        raise RuntimeError(
            f"batch {batch_id} : mapping batch_items vide alors que feature_uid est requis. "
            f"Reprise bloquée (impossible de rattacher les sorties à leur feature_uid)."
        )
    for r in results:
        item = id_map.get(r["custom_id"])
        if item is not None:
            r["feature_uid"]   = item["feature_uid"]
            r["feature_index"] = item["feature_index"]
            r["model_run_id"]  = item["model_run_id"]
        elif requires_feature_mapping:
            raise RuntimeError(
                f"custom_id {r['custom_id']} absent de batch_items (batch {batch_id}) — "
                f"feature_uid introuvable. Reprise bloquée."
            )

    # Persistance AVANT consommation/facturation : garantit qu'un crash entre réception
    # et persistance laisse le batch récupérable sans re-soumission ni double dépense.
    if persist_fn is not None:
        persist_fn(results)

    cost       = compute_cost(model, total_in, total_out, is_batch=True)
    cumulative = log_api_cost(run_id, phase, agent_name, model,
                              total_in, total_out, batch_id, cost,
                              model_run_id=model_run_id)
    mark_batch_consumed(batch_id)
    logger.info(f"Batch {batch_id} consommé — coût : {cost:.3f}$ | "
                f"Cumulé : {cumulative:.2f}$")

    budget = config.get("budget", {})
    if budget.get("abort_on_exceed") and \
       cumulative >= budget.get("max_cost_usd", float("inf")):
        raise RuntimeError(
            f"Budget dépassé : {cumulative:.2f}$ >= "
            f"{budget['max_cost_usd']}$"
        )
    return results


def _parse_json_output(raw: str,
                       custom_id: str) -> tuple[Optional[dict], str]:
    if not raw:
        return None, "failed"
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        end   = -1 if lines[-1].strip() == "```" else len(lines)
        clean = "\n".join(lines[1:end])
    try:
        parsed = json.loads(clean)
        if "status" not in parsed:
            logger.warning(f"{custom_id} : JSON sans champ 'status'")
            return parsed, "invalid_json"
        if parsed["status"] == "uncovered":
            return parsed, "uncovered"
        return parsed, "ok"
    except json.JSONDecodeError:
        logger.warning(f"{custom_id} : sortie non-JSON : {raw[:120]}")
        return None, "invalid_json"
