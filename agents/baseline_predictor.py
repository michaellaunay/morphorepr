# agents/baseline_predictor.py
"""
Prédicteur de directions pour les BASELINES (Option B, v6.8.0).

Produit, pour chaque baseline et chaque feature, un agent_output de prédiction au MÊME format
canonique que MorphoRepr (accepté par causal_scorer._extract_predicted_directions), avec
l'agent_name attendu par causal_scorer.ACCEPTED_PREDICTOR_AGENTS. Principes :
 - on NE FABRIQUE PAS de prédictions : on dépend du ModelProvider primaire (Règle 11) ;
 - on lit les annotations baselines dans la table `baselines` (annotation_run1 pour le primaire ;
   annotation_run2 = stabilité secondaire, JAMAIS mélangée) ;
 - on n'inscrit que des directions ROBUSTES valides (INCREASE/DECREASE/NO_CHANGE) ; une réponse
   non parsable ou sans direction robuste valide → status='error' (pas de NO_CHANGE silencieux) ;
 - on NE traduit PAS une baseline en MorphoRepr (prompts séparés, terminologie propre) ;
 - on NE refait PAS le steering : seul le chemin de PRÉDICTION diffère entre méthodes.
Seules nl_labels et semantic_regex sont branchées en v6.8.0 ; keyword_tags et morphorepr_shuffled
restent non branchées (NotImplementedError explicite).
"""
import json
import logging

from utils.db_utils import get_conn, save_agent_output, ensure_legacy_model_run
from utils.prompt_utils import load_prompt

logger = logging.getLogger(__name__)

ROBUST_PROPERTIES = ["negation_presence", "tense", "code_presence", "conditional_modality"]
DIRECTIONS = {"INCREASE", "DECREASE", "NO_CHANGE"}

# baseline → (agent_name attendu par causal_scorer, chemin de prompt par défaut)
BASELINE_AGENTS = {
    "nl_labels":      ("predictor_nl_labels",      "prompts/predictor_nl_labels_v1.txt"),
    "semantic_regex": ("predictor_semantic_regex", "prompts/predictor_semantic_regex_v1.txt"),
}
# Non branchées en v6.8.0 (contrôle nul / format non stabilisé) — erreur/skip documentés.
_UNSUPPORTED = {"keyword_tags", "morphorepr_shuffled"}

_DIRECTION_ALIASES = {
    "increase": "INCREASE", "up": "INCREASE", "more": "INCREASE", "INCREASE": "INCREASE",
    "decrease": "DECREASE", "down": "DECREASE", "less": "DECREASE", "DECREASE": "DECREASE",
    "no_change": "NO_CHANGE", "unchanged": "NO_CHANGE", "none": "NO_CHANGE", "NO_CHANGE": "NO_CHANGE",
}


def _normalize_direction(value):
    """INCREASE/DECREASE/NO_CHANGE ou None (ambigu) — jamais NO_CHANGE par défaut silencieux."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    return (_DIRECTION_ALIASES.get(v) or _DIRECTION_ALIASES.get(v.lower())) if v else None


def _prompt_path(method, config):
    key = {"nl_labels": "predictor_nl_labels", "semantic_regex": "predictor_semantic_regex"}[method]
    return config.get("prompts", {}).get(key, BASELINE_AGENTS[method][1])


def _load_baseline_annotations(run_id, model_run_id, method, split, which="annotation_run1"):
    """Annotations baselines pour une méthode, model-aware + split-aware (jointure features).
    `which` ∈ {annotation_run1 (primaire), annotation_run2 (stabilité secondaire)} — pas de mélange."""
    if which not in ("annotation_run1", "annotation_run2"):
        raise ValueError(f"_load_baseline_annotations : champ inattendu {which!r}.")
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT b.feature_uid, b.feature_index, b.{which} AS annotation,
                   f.nl_description, f.top_examples
            FROM baselines b JOIN features f ON f.feature_uid = b.feature_uid
            WHERE b.run_id=? AND b.model_run_id=? AND b.baseline_name=? AND f.split=?
        """, (run_id, model_run_id, method, split)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["top_examples"] = json.loads(d["top_examples"]) if d["top_examples"] else []
        except (TypeError, json.JSONDecodeError):
            d["top_examples"] = []
        out.append(d)
    return out


def _build_user_content(method, annot):
    """Contenu utilisateur SPÉCIFIQUE à la baseline (aucune terminologie MorphoRepr)."""
    examples = annot.get("top_examples") or []
    ex_block = "\n".join(f"- {str(e)[:200]}" for e in examples[:5]) or "(none provided)"
    if method == "nl_labels":
        return ("Natural-language label describing the feature:\n"
                f"{annot['annotation']}\n\n"
                f"Top-activating examples:\n{ex_block}\n\n"
                "Predict the expected behavioural effects under steering of THIS feature.")
    if method == "semantic_regex":
        desc = annot.get("nl_description") or "(no description)"
        return ("Semantic Regex annotation of the feature:\n"
                f"{annot['annotation']}\n\n"
                f"Optional description:\n{desc}\n\n"
                "Use only the regex structure to predict observable property effects under steering.")
    raise NotImplementedError(f"_build_user_content : méthode non branchée {method!r}.")


def _parse_prediction_response(raw, method):
    """Parse la réponse du modèle en output_json canonique ou None. N'inclut que des propriétés
    ROBUSTES avec direction valide. Aucune conversion silencieuse d'une direction ambiguë."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        i, j = text.find("{"), text.rfind("}")
        if i == -1 or j == -1 or j <= i:
            return None
        try:
            obj = json.loads(text[i:j + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    raw_preds = obj.get("predictions")
    items = raw_preds if isinstance(raw_preds, list) else []
    if not items and isinstance(obj.get("properties"), dict):     # tolérance format dict
        items = [{"property": k, "direction": (v.get("direction") if isinstance(v, dict) else v)}
                 for k, v in obj["properties"].items()]
    preds = []
    for it in items:
        if not isinstance(it, dict):
            continue
        prop = it.get("property")
        direction = _normalize_direction(it.get("direction"))
        if prop in ROBUST_PROPERTIES and direction in DIRECTIONS:
            entry = {"property": prop, "direction": direction}
            if isinstance(it.get("confidence"), (int, float)):
                entry["confidence"] = it["confidence"]
            if it.get("rationale"):
                entry["rationale"] = str(it["rationale"])[:280]
            preds.append(entry)
    if not preds:
        return None
    return {"status": "ok", "method": method, "predictions": preds}


def _build_primary_provider(config):
    """Seam monkeypatchable : construit le ModelProvider PRIMAIRE (Tier A/B, Règle 11)."""
    from utils.model_provider import build_provider
    return build_provider(config["model_providers"]["primary_reproducible"])


def _predict_directions(provider, system_prompt, annot, method, config):
    """Appelle le provider primaire et parse la réponse. Renvoie (output_json|None, raw)."""
    gp = (config.get("model_providers", {}).get("primary_reproducible", {})
          .get("generation_params", {}))
    max_tokens = config.get("baseline_predictions", {}).get("max_tokens", 512)
    raw = provider.generate([{"role": "user", "content": _build_user_content(method, annot)}],
                            system_prompt, max_tokens, gp)
    return _parse_prediction_response(raw, method), raw


def run(run_id: str, config: dict):
    """Produit les agent_outputs de prédiction baselines (Option B). NE FABRIQUE rien : une
    réponse invalide est persistée status='error' (jamais convertie en NO_CHANGE). NE refait PAS
    le steering. Strictement model-aware et split-aware."""
    bp = config.get("baseline_predictions", {})
    run_number    = bp.get("run_number", 1)
    require_annot = bp.get("require_existing_baseline_annotations", True)
    skip_missing  = bp.get("skip_missing_annotations", False)
    split = config.get("primary_split", "random")
    model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                    or ensure_legacy_model_run(run_id))

    provider = _build_primary_provider(config)
    summary = {}
    for method in bp.get("methods", []):
        if method in _UNSUPPORTED:
            raise NotImplementedError(
                f"baseline_predictor : '{method}' n'est pas branché en v6.8.0 (contrôle nul / "
                f"format non stabilisé). Retirer de baseline_predictions.methods ou l'implémenter.")
        if method not in BASELINE_AGENTS:
            raise NotImplementedError(f"baseline_predictor : méthode inconnue {method!r}.")
        agent_name, _default_prompt = BASELINE_AGENTS[method]
        system_prompt = load_prompt(_prompt_path(method, config))
        annots = _load_baseline_annotations(run_id, model_run_id, method, split, "annotation_run1")
        if not annots:
            msg = (f"No baseline annotations found for method={method}, run_id={run_id}, "
                   f"model_run_id={model_run_id}, split={split}.")
            if require_annot:
                raise RuntimeError(msg + " (require_existing_baseline_annotations=true)")
            logger.warning(msg + " — méthode ignorée."); continue

        n_ok = n_err = n_skip = 0
        for a in annots:
            if not a.get("annotation"):
                if skip_missing:
                    n_skip += 1; continue
                if require_annot:
                    raise RuntimeError(
                        f"Annotation baseline vide pour feature_uid={a['feature_uid']} "
                        f"(method={method}). (require_existing_baseline_annotations=true)")
            output_json, raw = _predict_directions(provider, system_prompt, a, method, config)
            status = "ok" if (output_json and output_json.get("predictions")) else "error"
            save_agent_output(
                run_id, a["feature_index"], agent_name, run_number,
                output_json if status == "ok" else None, raw if isinstance(raw, str) else "",
                status, None if status == "ok" else "no valid robust direction parsed",
                0, 0, None, 0.0, feature_uid=a["feature_uid"], model_run_id=model_run_id)
            n_ok += status == "ok"; n_err += status == "error"
        summary[method] = {"annotations": len(annots), "ok": n_ok, "error": n_err, "skipped": n_skip}
        logger.info(f"baseline_predictor[{method}] : {n_ok} ok, {n_err} error, {n_skip} skip "
                    f"(agent_name={agent_name}, model_run_id={model_run_id}, split={split}).")
    return summary
