# agents/predictor.py
"""
Prédicteur causal MorphoRepr (Phase 4, p4_predict) — v6.10.0, étape 2.

Produit, pour chaque feature ENCODÉE (sortie de l'agent 'encoder'), un agent_output de
prédiction de directions au format canonique accepté par
causal_scorer._extract_predicted_directions, sous l'agent_name 'predictor'
(ACCEPTED_PREDICTOR_AGENTS['morphorepr']). Principes — symétrie STRICTE avec
agents/baseline_predictor (Option B) :
 - on NE FABRIQUE PAS de prédictions : ModelProvider primaire (Règle 11), jamais
   anthropic.Anthropic() directement ;
 - l'entrée du prompt est l'EXPRESSION MorphoRepr SEULE ($.expression de l'encoder) —
   JAMAIS la description NL du feature, sinon la comparaison MorphoRepr vs baselines
   est contaminée (Règle 7, « same information budget ») ;
 - une réponse non parsable / sans direction robuste valide → status='error'
   (jamais de NO_CHANGE silencieux) ;
 - strictement model-aware (model_run_id primaire) et split-aware (primary_split).
"""
import logging

from utils.db_utils import get_conn, save_agent_output, ensure_legacy_model_run
from utils.prompt_utils import load_prompt
# Source UNIQUE de vérité pour le parsing des réponses de prédiction (formats acceptés,
# propriétés robustes, directions valides) — partagée avec les baselines :
from agents.baseline_predictor import _parse_prediction_response

logger = logging.getLogger(__name__)

PREDICTOR_AGENT_NAME = "predictor"          # ACCEPTED_PREDICTOR_AGENTS["morphorepr"]
DEFAULT_PROMPT_PATH  = "prompts/predictor_agent_v1.txt"


def _build_primary_provider(config):
    """Seam monkeypatchable : construit le ModelProvider PRIMAIRE (Tier A/B, Règle 11)."""
    from utils.model_provider import build_provider
    return build_provider(config["model_providers"]["primary_reproducible"])


def _load_encoded_features(run_id, model_run_id, split, encoder_run_number=1):
    """Expressions MorphoRepr encodées PAR LE MODÈLE `model_run_id` (model-aware) sur le
    split demandé (split-aware). Même logique de sélection que
    steerer._load_encoded_random_features (agent 'encoder', run 1, status='ok'),
    généralisée au split passé en argument."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_uid, f.feature_index,
                   json_extract(ao.output_json, '$.expression') AS expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id = ? AND ao.model_run_id = ? AND ao.agent_name = 'encoder'
              AND ao.run_number = ? AND ao.status = 'ok' AND f.split = ?
        """, (run_id, model_run_id, encoder_run_number, split)).fetchall()
    return [dict(r) for r in rows]


def _build_user_content(expression: str) -> str:
    """Contenu utilisateur : l'expression MorphoRepr SEULE (aucune description NL)."""
    return ("MorphoRepr expression annotating the feature:\n"
            f"{expression}\n\n"
            "Predict the expected behavioural effects under steering of THIS feature.")


def run(run_id: str, config: dict):
    """Produit les agent_outputs de prédiction MorphoRepr. NE FABRIQUE rien : une réponse
    invalide est persistée status='error' (jamais convertie en NO_CHANGE). NE refait PAS
    le steering : seule la PRÉDICTION est produite ici (le chemin d'observation est
    identique pour toutes les méthodes, Règle 7)."""
    pr = config.get("predictions", {})
    run_number = pr.get("run_number", 1)
    max_tokens = pr.get("max_tokens", 512)
    split = config.get("primary_split", "random")
    model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                    or ensure_legacy_model_run(run_id))

    system_prompt = load_prompt(config.get("prompts", {}).get("predictor", DEFAULT_PROMPT_PATH))
    feats = _load_encoded_features(run_id, model_run_id, split,
                                   encoder_run_number=pr.get("encoder_run_number", 1))
    if not feats:
        raise RuntimeError(
            f"predictor : aucune expression encodée (agent 'encoder', status='ok') pour "
            f"run_id={run_id}, model_run_id={model_run_id}, split={split}. "
            f"Exécuter p3_encode d'abord.")

    provider = _build_primary_provider(config)
    mp = config.get("model_providers", {}).get("primary_reproducible", {})
    gp = mp.get("generation_params", mp.get("deterministic_generation", {}))

    n_ok = n_err = n_skip = 0
    for f in feats:
        expr = f.get("expression")
        if not expr or not str(expr).strip():
            n_skip += 1
            logger.warning(f"predictor : expression vide pour feature_uid={f['feature_uid']} "
                           f"— ignorée (pas de prédiction fabriquée).")
            continue
        raw = provider.generate([{"role": "user", "content": _build_user_content(str(expr))}],
                                system_prompt, max_tokens, gp)
        output_json = _parse_prediction_response(raw, "morphorepr")
        status = "ok" if (output_json and output_json.get("predictions")) else "error"
        save_agent_output(
            run_id, f["feature_index"], PREDICTOR_AGENT_NAME, run_number,
            output_json if status == "ok" else None, raw if isinstance(raw, str) else "",
            status, None if status == "ok" else "no valid robust direction parsed",
            0, 0, None, 0.0, feature_uid=f["feature_uid"], model_run_id=model_run_id)
        n_ok += status == "ok"; n_err += status == "error"

    summary = {"encoded_features": len(feats), "ok": n_ok, "error": n_err, "skipped_empty": n_skip}
    logger.info(f"predictor[morphorepr] : {n_ok} ok, {n_err} error, {n_skip} skip "
                f"(agent_name={PREDICTOR_AGENT_NAME}, model_run_id={model_run_id}, split={split}).")
    return summary
