# agents/causal_scorer.py
"""
Score causal DÉTERMINISTE (métrique primaire). Aucun juge LLM ici (Règle 8).

Entrée logique : une liste de couples {feature_uid, property, predicted, observed}
restreinte aux propriétés ROBUSTES, où predicted/observed ∈ {INCREASE, DECREASE, NO_CHANGE}.
 - predicted : direction prédite par l'agent de prédiction (agent_outputs 'predictor').
 - observed  : direction mesurée par le classifieur de la propriété (déterministe).
Le macro-F1 est calculé GLOBALEMENT sur l'ensemble des couples (pas par feature).
"""
import json
import logging
import random
from uuid import uuid4
from datetime import datetime
from utils.db_utils import get_conn

logger = logging.getLogger(__name__)

DIRECTIONS = ["INCREASE", "DECREASE", "NO_CHANGE"]
ROBUST_PROPERTIES = ["negation_presence", "tense", "code_presence", "conditional_modality"]


def compute_global_macro_f1(pairs: list[dict]) -> dict:
    """Macro-F1 GLOBAL sur tous les couples (feature, propriété). `pairs` : liste de
    {'predicted': dir, 'observed': dir}. Le macro-F1 moyenne le F1 des classes PRÉSENTES
    dans les directions observées (vérité terrain)."""
    confusion = {a: {b: 0 for b in DIRECTIONS} for a in DIRECTIONS}
    for p in pairs:
        confusion[p["observed"]][p["predicted"]] += 1
    f1s, per_class = [], {}
    for d in DIRECTIONS:
        tp = confusion[d][d]
        fp = sum(confusion[o][d] for o in DIRECTIONS if o != d)
        fn = sum(confusion[d][o] for o in DIRECTIONS if o != d)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[d] = {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}
        if (tp + fn) > 0:                     # classe présente dans la vérité terrain
            f1s.append(f1)
    n = len(pairs) or 1
    accuracy = sum(confusion[d][d] for d in DIRECTIONS) / n
    return {
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "accuracy": round(accuracy, 4),
        "n_pairs": len(pairs),
        "per_class": per_class,
    }


def feature_clustered_bootstrap(pairs: list[dict], n_resamples: int = 10000,
                                seed: int = 42, alpha: float = 0.05) -> dict:
    """IC bootstrap du macro-F1 global, CLUSTERISÉ par feature_uid : on rééchantillonne
    des FEATURES (avec remise), pas des couples individuels (la dépendance intra-feature
    est ainsi respectée)."""
    by_feat: dict[str, list[dict]] = {}
    for p in pairs:
        by_feat.setdefault(p["feature_uid"], []).append(p)
    uids = list(by_feat)
    rng  = random.Random(seed)
    stats = []
    for _ in range(n_resamples):
        sample_uids = [rng.choice(uids) for _ in uids]      # clusters avec remise
        resampled = [pair for u in sample_uids for pair in by_feat[u]]
        stats.append(compute_global_macro_f1(resampled)["macro_f1"])
    stats.sort()
    lo = stats[int((alpha / 2) * n_resamples)]
    hi = stats[int((1 - alpha / 2) * n_resamples) - 1]
    return {"ci_low": round(lo, 4), "ci_high": round(hi, 4), "n_features": len(uids)}


def paired_diff_bootstrap(pairs_a: list[dict], pairs_b: list[dict],
                          n_resamples: int = 10000, seed: int = 42,
                          alpha: float = 0.05) -> dict:
    """Différence APPARIÉE de macro-F1 (méthode A − méthode B) avec rééchantillonnage
    des MÊMES features pour les deux méthodes (comparaison appariée, clusterisée)."""
    a = {p["feature_uid"]: [] for p in pairs_a}
    b = {p["feature_uid"]: [] for p in pairs_b}
    for p in pairs_a: a[p["feature_uid"]].append(p)
    for p in pairs_b: b[p["feature_uid"]].append(p)
    uids = sorted(set(a) & set(b))            # ensemble de features PARTAGÉ
    rng  = random.Random(seed)
    diffs = []
    for _ in range(n_resamples):
        s = [rng.choice(uids) for _ in uids]
        fa = compute_global_macro_f1([x for u in s for x in a[u]])["macro_f1"]
        fb = compute_global_macro_f1([x for u in s for x in b[u]])["macro_f1"]
        diffs.append(fa - fb)
    diffs.sort()
    lo = diffs[int((alpha / 2) * n_resamples)]
    hi = diffs[int((1 - alpha / 2) * n_resamples) - 1]
    point = compute_global_macro_f1(pairs_a)["macro_f1"] - compute_global_macro_f1(pairs_b)["macro_f1"]
    return {"diff": round(point, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4),
            "n_shared_features": len(uids)}


# ── v6.7.0 : assemblage RÉEL des couples prédiction/observation (métrique primaire) ──

# agent_names acceptés par méthode (inspecter predictor.py / prompts ; ne pas inventer en silence)
ACCEPTED_PREDICTOR_AGENTS = {
    "morphorepr":          ["predictor", "predictor_morphorepr"],
    "nl_labels":           ["predictor_nl_labels"],
    "semantic_regex":      ["predictor_semantic_regex"],
    "keyword_tags":        ["predictor_keyword_tags"],
    "morphorepr_shuffled": ["predictor_morphorepr_shuffled"],
}

# Map propriété robuste → classifieur déterministe. Rempli paresseusement (les classifieurs ne
# sont pas importés au chargement du module) ou monkeypatché en test. negative_valence est EXCLU
# du primaire (valence semi-robuste).
CLASSIFIER_BY_PROPERTY = None

_DIRECTION_ALIASES = {
    "increase": "INCREASE", "up": "INCREASE", "more": "INCREASE", "INCREASE": "INCREASE",
    "decrease": "DECREASE", "down": "DECREASE", "less": "DECREASE", "DECREASE": "DECREASE",
    "no_change": "NO_CHANGE", "unchanged": "NO_CHANGE", "none": "NO_CHANGE", "NO_CHANGE": "NO_CHANGE",
}


def _default_classifier_map() -> dict:
    """Import paresseux des classifieurs robustes (négation, temps, code, modalité conditionnelle).
    negative_valence (semi-robuste) n'est PAS inclus dans la métrique primaire."""
    import classifiers.negation, classifiers.tense, classifiers.code_presence, classifiers.modality
    return {
        "negation_presence":    classifiers.negation.measure,
        "tense":                classifiers.tense.measure,
        "code_presence":        classifiers.code_presence.measure,
        "conditional_modality": classifiers.modality.measure,
    }


def _normalize_direction(value) -> str | None:
    """Normalise une direction (aliases) vers INCREASE/DECREASE/NO_CHANGE. Renvoie None pour
    une direction ambiguë (UNKNOWN, null, chaîne vide, valeur non reconnue) — JAMAIS NO_CHANGE
    par défaut silencieux."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    return _DIRECTION_ALIASES.get(v) or _DIRECTION_ALIASES.get(v.lower())


def _extract_predicted_directions(output_json) -> dict[str, str]:
    """Convertit la sortie du prédicteur en {property: DIRECTION}. Accepte 3 formats :
      1) {"predictions": [{"property","direction","confidence"?}, ...]}
      2) {"properties": {"prop": "DIR"}}
      3) {"properties": {"prop": {"direction": "DIR", ...}}}
    Les directions ambiguës / propriétés non reconnues sont écartées (non incluses)."""
    if isinstance(output_json, str):
        output_json = json.loads(output_json)
    out: dict[str, str] = {}
    if not isinstance(output_json, dict):
        return out
    preds = output_json.get("predictions")
    if isinstance(preds, list):
        for item in preds:
            if not isinstance(item, dict):
                continue
            prop = item.get("property")
            d = _normalize_direction(item.get("direction"))
            if prop and d:
                out[prop] = d
    props = output_json.get("properties")
    if isinstance(props, dict):
        for prop, val in props.items():
            d = _normalize_direction(val.get("direction")) if isinstance(val, dict) else _normalize_direction(val)
            if prop and d:
                out[prop] = d
    return out


def _primary_magnitude_key(config: dict) -> str:
    """Clé TEXTE de la magnitude PRIMAIRE (cohérente avec steerer._run_steering_batch) :
    'rel:{primary_magnitude_rel}' en mode p99_relative, 'abs:{legacy_absolute_magnitude}' en
    mode absolute. Le contrôle 'rel:0.0' n'est PAS la magnitude primaire (analyses secondaires)."""
    st = config.get("steering", {})
    if st.get("magnitude_mode", "p99_relative") == "absolute":
        return f"abs:{st.get('legacy_absolute_magnitude', 5)}"
    return f"rel:{st.get('primary_magnitude_rel', 1.0)}"


def _observe_property_direction(rows: list[dict], property_name: str, classifier_fn) -> dict | None:
    """Applique le classifieur déterministe d'une propriété aux paires (text_before, text_after)
    non nulles. Renvoie {property, direction, n_observations, details} ou None si aucune paire
    valide. Lève ValueError si le classifieur renvoie une direction invalide (jamais converti
    silencieusement en NO_CHANGE)."""
    before = [r["text_before"] for r in rows if r.get("text_before") and r.get("text_after")]
    after  = [r["text_after"]  for r in rows if r.get("text_before") and r.get("text_after")]
    if not before:
        return None
    out = classifier_fn(before, after)
    direction = out.get("direction") if isinstance(out, dict) else None
    if direction not in DIRECTIONS:
        raise ValueError(
            f"Classifieur de '{property_name}' a renvoyé une direction invalide : {direction!r} "
            f"(attendu ∈ {DIRECTIONS})."
        )
    return {"property": property_name, "direction": direction,
            "n_observations": len(before), "details": out}


def _load_pairs(run_id: str,
                method: str,
                config: dict | None = None,
                model_run_id: str | None = None,
                split: str = "random") -> list[dict]:
    """Assemble les couples {feature_uid, model_run_id, property, predicted, observed, method,
    n_observations, metadata} pour la métrique primaire DÉTERMINISTE, STRICTEMENT model-aware et
    split-aware. predicted ← agent_outputs (agent prédicteur de la méthode) ; observed ←
    classifieurs déterministes appliqués aux text_before/text_after de steering_results à la
    MAGNITUDE PRIMAIRE. Restreint aux ROBUST_PROPERTIES. Aucun juge LLM. Aucune pseudo-observation.

    Sélection du modèle (Règle 11) : model_run_id explicite, sinon config['_runtime']['model_run_ids']
    ['primary'], sinon ensure_legacy_model_run(run_id). Jamais de mélange entre modèles."""
    config = config or {}
    from utils.db_utils import ensure_legacy_model_run
    if model_run_id is None:
        model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                        or ensure_legacy_model_run(run_id))
    if method not in ACCEPTED_PREDICTOR_AGENTS:
        raise NotImplementedError(
            f"_load_pairs : méthode inconnue {method!r} (aucun agent prédicteur déclaré dans "
            f"ACCEPTED_PREDICTOR_AGENTS)."
        )
    accepted = ACCEPTED_PREDICTOR_AGENTS[method]
    st = config.get("steering", {})
    exclude_ood  = bool(st.get("exclude_ood_from_primary", True))
    probe_family = st.get("primary_probe_family", "neutral")
    space        = st.get("intervention_space", "residual_add_decoder")
    mag_key      = _primary_magnitude_key(config)

    # A. PRÉDICTIONS (agent_outputs, model-aware, split-aware)
    ph = ",".join("?" for _ in accepted)
    with get_conn() as conn:
        pred_rows = conn.execute(f"""
            SELECT ao.feature_uid, ao.output_json
            FROM agent_outputs ao JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id = ? AND ao.model_run_id = ? AND ao.status = 'ok'
              AND ao.agent_name IN ({ph}) AND f.split = ?
        """, (run_id, model_run_id, *accepted, split)).fetchall()
    if not pred_rows:
        raise RuntimeError(
            f"No predictor outputs found for method={method}, run_id={run_id}, "
            f"model_run_id={model_run_id} (agent_name ∈ {accepted}, split={split})."
        )
    predicted: dict[str, dict[str, str]] = {}
    for r in pred_rows:
        dirs = _extract_predicted_directions(r["output_json"])
        for prop in list(dirs):
            if prop not in ROBUST_PROPERTIES:
                logger.debug(f"_load_pairs: propriété non robuste ignorée hors primaire : {prop!r}")
        predicted.setdefault(r["feature_uid"], {}).update(
            {p: d for p, d in dirs.items() if p in ROBUST_PROPERTIES}
        )

    # B. OBSERVATIONS (steering_results à la magnitude primaire, neutres, model/split-aware)
    with get_conn() as conn:
        q = """
            SELECT sr.feature_uid, sr.text_before, sr.text_after, sr.generation_index, sr.ood_flag
            FROM steering_results sr JOIN features f ON f.feature_uid = sr.feature_uid
            WHERE sr.run_id = ? AND sr.model_run_id = ? AND sr.magnitude_key = ?
              AND sr.intervention_space = ? AND sr.probe_family = ? AND sr.probe_category IS NULL
              AND sr.text_after IS NOT NULL AND f.split = ?
        """
        if exclude_ood:
            q += " AND sr.ood_flag = 0"
        obs_rows = conn.execute(q, (run_id, model_run_id, mag_key, space, probe_family, split)).fetchall()
    if not obs_rows:
        raise RuntimeError(
            f"No steering observations found for method={method}, run_id={run_id}, "
            f"model_run_id={model_run_id}, magnitude_key={mag_key}, probe_family={probe_family}, "
            f"split={split}. Did you run p4_steer first?"
        )
    obs_by_feat: dict[str, list[dict]] = {}
    for r in obs_rows:
        obs_by_feat.setdefault(r["feature_uid"], []).append(dict(r))

    cmap = CLASSIFIER_BY_PROPERTY or _default_classifier_map()

    # C. ASSEMBLAGE — un couple seulement si prédiction ET observation existent pour une propriété ROBUSTE
    pairs = []
    for uid, props in predicted.items():
        if uid not in obs_by_feat:
            logger.info(f"_load_pairs: feature {uid} a des prédictions mais aucune observation "
                        f"steering (magnitude primaire) — ignorée (pas de score artificiel).")
            continue
        rows = obs_by_feat[uid]
        for prop in ROBUST_PROPERTIES:
            pred_dir = props.get(prop)
            if pred_dir is None:
                continue
            classifier_fn = cmap.get(prop)
            if classifier_fn is None:
                raise KeyError(f"Aucun classifieur enregistré pour la propriété robuste {prop!r}.")
            obs = _observe_property_direction(rows, prop, classifier_fn)
            if obs is None:
                logger.info(f"_load_pairs: feature {uid} / {prop} sans paire before/after valide — ignorée.")
                continue
            pairs.append({
                "feature_uid":    uid,
                "model_run_id":   model_run_id,
                "property":       prop,
                "predicted":      pred_dir,
                "observed":       obs["direction"],
                "method":         method,
                "n_observations": obs["n_observations"],
                "metadata": {"magnitude_key": mag_key, "probe_family": probe_family, "split": split},
            })
    if not pairs:
        raise RuntimeError(
            f"No causal pairs assembled for method={method}, run_id={run_id}, "
            f"model_run_id={model_run_id} : des prédictions et des observations existent, mais "
            f"aucune propriété ROBUSTE n'est commune aux deux."
        )
    return pairs


def assert_baseline_predictions_ready(run_id: str, model_run_id: str,
                                      methods: list[str], split: str,
                                      min_features: int = 1) -> None:
    """Garde pré-comparaison (v6.8.0) : pour chaque baseline demandée, vérifie qu'il existe des
    annotations dans `baselines` ET des prédictions `agent_outputs` (agent_name attendu) pour CE
    model_run_id et CE split (jointure `features`). Lève RuntimeError sinon — on ne produit JAMAIS
    de verdict sur une baseline absente."""
    with get_conn() as conn:
        for method in methods:
            agents = ACCEPTED_PREDICTOR_AGENTS.get(method)
            if not agents:
                raise NotImplementedError(
                    f"assert_baseline_predictions_ready : méthode inconnue {method!r}.")
            ph = ",".join("?" for _ in agents)
            n_annot = conn.execute("""
                SELECT COUNT(DISTINCT b.feature_uid) FROM baselines b
                JOIN features f ON f.feature_uid = b.feature_uid
                WHERE b.run_id=? AND b.model_run_id=? AND b.baseline_name=? AND f.split=?
            """, (run_id, model_run_id, method, split)).fetchone()[0]
            n_pred = conn.execute(f"""
                SELECT COUNT(DISTINCT ao.feature_uid) FROM agent_outputs ao
                JOIN features f ON f.feature_uid = ao.feature_uid
                WHERE ao.run_id=? AND ao.model_run_id=? AND ao.status='ok'
                  AND ao.agent_name IN ({ph}) AND f.split=?
            """, (run_id, model_run_id, *agents, split)).fetchone()[0]
            if n_pred < min_features:
                raise RuntimeError(
                    f"Baseline '{method}' non prête : {n_pred} prédiction(s) trouvée(s) "
                    f"(agent_name ∈ {agents}, run_id={run_id}, model_run_id={model_run_id}, "
                    f"split={split} ; annotations baselines présentes={n_annot}). Lancer "
                    f"baseline_predictor.run (baseline_predictions.enabled=true) d'abord."
                )


def run(run_id: str, config: dict):
    """Métrique primaire : macro-F1 global sur couples + bootstrap clusterisé par feature.
    STRICTEMENT model-aware (modèle primaire) et split-aware. Persiste dans metrics AVEC
    model_run_id (NULL réservé aux agrégats cross-modèles).

    Comparaisons baselines (Option B, v6.8.0) exécutées seulement si
    causal_scoring.run_baseline_comparisons=true. Pour chaque baseline demandée : garde de
    readiness (strict → RuntimeError ; sinon skip explicite SANS verdict), score propre de la
    baseline (causal_macro_f1_global, baseline=<nom>), différence appariée (supériorité vs NL ;
    non-infériorité vs Semantic Regexes), et couverture (paires MorphoRepr/baseline, features
    partagées). Aucun verdict sur une baseline absente."""
    from utils.db_utils import ensure_legacy_model_run
    nim    = config["thresholds"].get("nim_delta", 0.05)
    split  = config.get("primary_split", "random")
    n_boot = config["stats"].get("bootstrap_resamples", 10000)
    seed   = config.get("seed", 42)
    model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                    or ensure_legacy_model_run(run_id))

    mr    = _load_pairs(run_id, "morphorepr", config=config, model_run_id=model_run_id, split=split)
    point = compute_global_macro_f1(mr)
    ci    = feature_clustered_bootstrap(mr, n_boot, seed)
    results = {"morphorepr": {**point, **ci}, "comparisons": {}, "baseline_scores": {}}

    # (metric_name, value, ci_low, ci_high, n_samples, baseline) — model_run_id renseigné partout
    metric_rows = [("causal_macro_f1_global", point["macro_f1"], ci["ci_low"], ci["ci_high"],
                    point["n_pairs"], None)]

    cs_cfg = config.get("causal_scoring", {})
    if cs_cfg.get("run_baseline_comparisons", False):
        strict  = cs_cfg.get("strict_baselines", True)
        targets = config["stats"].get("superiority_vs", []) + config["stats"].get("non_inferiority_vs", [])
        for base in targets:
            try:
                assert_baseline_predictions_ready(run_id, model_run_id, [base], split)
            except (RuntimeError, NotImplementedError) as e:
                if strict:
                    raise
                logger.warning(f"Baseline '{base}' IGNORÉE (non prête) : {e} — AUCUN verdict produit.")
                continue
            base_pairs = _load_pairs(run_id, base, config=config, model_run_id=model_run_id, split=split)
            base_point = compute_global_macro_f1(base_pairs)
            results["baseline_scores"][base] = base_point
            metric_rows.append(("causal_macro_f1_global", base_point["macro_f1"], None, None,
                                base_point["n_pairs"], base))
            d = paired_diff_bootstrap(mr, base_pairs, n_boot, seed)
            mode = ("non_inferiority" if base in config["stats"].get("non_inferiority_vs", [])
                    else "superiority")
            d["verdict"] = (("pass" if d["ci_low"] > -nim else "fail") if mode == "non_inferiority"
                            else ("pass" if d["ci_low"] > 0 else "fail"))
            d["coverage"] = {"morphorepr_pairs": point["n_pairs"], "baseline_pairs": base_point["n_pairs"],
                             "n_shared_features": d["n_shared_features"]}
            results["comparisons"][base] = {"mode": mode, **d}
            metric_rows.append(("causal_macro_f1_paired_diff", d["diff"], d["ci_low"], d["ci_high"],
                                d["n_shared_features"], base))
            logger.info(f"Comparaison vs {base} ({mode}) : diff={d['diff']} "
                        f"IC95=[{d['ci_low']},{d['ci_high']}] verdict={d['verdict']} "
                        f"(features partagées={d['n_shared_features']})")
    else:
        logger.warning(
            "Comparaisons baselines IGNORÉES (causal_scoring.run_baseline_comparisons=false). "
            "AUCUN verdict de supériorité/non-infériorité ; seul causal_macro_f1_global "
            "(MorphoRepr) est écrit."
        )

    with get_conn() as conn:
        for name, value, lo, hi, n, base in metric_rows:
            conn.execute("""INSERT INTO metrics (metric_id, run_id, model_run_id, phase, split,
                            metric_name, value, ci_low, ci_high, n_samples, baseline, computed_at)
                            VALUES (?, ?, ?, 'p4_score', ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (str(uuid4()), run_id, model_run_id, split, name, value, lo, hi, n, base,
                          datetime.utcnow().isoformat()))
    logger.info(f"Score causal global (split={split}, model_run_id={model_run_id}) : "
                f"macro-F1={point['macro_f1']} IC95={ci}")
    return results


def load_intervention_control_pairs(run_id: str,
                                    control_name: str,
                                    method: str = "morphorepr",
                                    config: dict | None = None,
                                    model_run_id: str | None = None,
                                    split: str = "random") -> list[dict]:
    """Couples prédiction/observation pour UN contrôle d'intervention (table dédiée
    intervention_control_results). À NE PAS confondre avec _load_pairs() primaire : les
    observations proviennent des contrôles, PAS de steering_results. predicted ← prédictions
    MorphoRepr (agent_outputs) de la TARGET ; observed ← MÊMES classifieurs déterministes appliqués
    aux text_before/text_after du contrôle. Restreint aux ROBUST_PROPERTIES. model/split/space-aware,
    politique OOD respectée. Aucun juge LLM, aucune pseudo-observation."""
    config = config or {}
    if method != "morphorepr":
        raise NotImplementedError(
            "load_intervention_control_pairs : les contrôles sont scorés contre les prédictions "
            "MorphoRepr uniquement (method='morphorepr').")
    from utils.db_utils import ensure_legacy_model_run
    if model_run_id is None:
        model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                        or ensure_legacy_model_run(run_id))
    accepted = ACCEPTED_PREDICTOR_AGENTS["morphorepr"]
    st = config.get("steering", {})
    exclude_ood = bool(st.get("exclude_ood_from_primary", True))
    space = st.get("intervention_space", "residual_add_decoder")
    # prompt_only stocke intervention_space='prompt_only' ; les contrôles steerés gardent le space primaire.
    obs_space = "prompt_only" if control_name == "prompt_only" else space

    ph = ",".join("?" for _ in accepted)
    with get_conn() as conn:
        pred_rows = conn.execute(f"""
            SELECT ao.feature_uid, ao.output_json
            FROM agent_outputs ao JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id=? AND ao.model_run_id=? AND ao.status='ok'
              AND ao.agent_name IN ({ph}) AND f.split=?
        """, (run_id, model_run_id, *accepted, split)).fetchall()
    if not pred_rows:
        raise RuntimeError(
            f"No MorphoRepr predictor outputs for control={control_name}, run_id={run_id}, "
            f"model_run_id={model_run_id} (agent_name ∈ {accepted}, split={split}).")
    predicted: dict[str, dict[str, str]] = {}
    for r in pred_rows:
        dirs = _extract_predicted_directions(r["output_json"])
        predicted.setdefault(r["feature_uid"], {}).update(
            {p: d for p, d in dirs.items() if p in ROBUST_PROPERTIES})

    with get_conn() as conn:
        q = """
            SELECT icr.target_feature_uid AS feature_uid, icr.text_before, icr.text_after,
                   icr.generation_index, icr.ood_flag
            FROM intervention_control_results icr
            JOIN features f ON f.feature_uid = icr.target_feature_uid
            WHERE icr.run_id=? AND icr.model_run_id=? AND icr.control_name=?
              AND icr.intervention_space=? AND icr.text_after IS NOT NULL AND f.split=?
        """
        if exclude_ood:
            q += " AND icr.ood_flag = 0"
        obs_rows = conn.execute(q, (run_id, model_run_id, control_name, obs_space, split)).fetchall()
    if not obs_rows:
        raise RuntimeError(
            f"No intervention-control observations for control={control_name}, run_id={run_id}, "
            f"model_run_id={model_run_id}, space={obs_space}, split={split}. "
            f"Did you run run_intervention_controls() first?")
    obs_by_feat: dict[str, list[dict]] = {}
    for r in obs_rows:
        obs_by_feat.setdefault(r["feature_uid"], []).append(dict(r))

    cmap = CLASSIFIER_BY_PROPERTY or _default_classifier_map()
    pairs = []
    for uid, props in predicted.items():
        if uid not in obs_by_feat:
            continue
        rows = obs_by_feat[uid]
        for prop in ROBUST_PROPERTIES:
            pred_dir = props.get(prop)
            if pred_dir is None:
                continue
            classifier_fn = cmap.get(prop)
            if classifier_fn is None:
                raise KeyError(f"Aucun classifieur enregistré pour la propriété robuste {prop!r}.")
            obs = _observe_property_direction(rows, prop, classifier_fn)
            if obs is None:
                continue
            pairs.append({
                "feature_uid":    uid,
                "model_run_id":   model_run_id,
                "property":       prop,
                "predicted":      pred_dir,
                "observed":       obs["direction"],
                "method":         method,
                "control_name":   control_name,
                "n_observations": obs["n_observations"],
                "metadata": {"control_name": control_name, "split": split, "space": obs_space},
            })
    if not pairs:
        raise RuntimeError(
            f"No control pairs assembled for control={control_name}, run_id={run_id}, "
            f"model_run_id={model_run_id} : prédictions et observations existent mais aucune "
            f"propriété ROBUSTE commune.")
    return pairs


def score_intervention_controls(run_id: str, config: dict) -> dict:
    """Score SECONDAIRE des contrôles d'intervention (jamais le primaire). Pour chaque contrôle de
    controls_to_run : macro-F1 du contrôle + différence appariée primaire − contrôle (bootstrap
    clusterisé par feature) + couverture. Écrit metric_name='intervention_control_macro_f1:<nom>'
    et 'intervention_control_paired_diff:<nom>' (baseline='control:<nom>', model_run_id renseigné).
    Strict → RuntimeError si un contrôle activé est absent ; sinon skip explicite SANS verdict."""
    from utils.db_utils import ensure_legacy_model_run
    ic = config.get("intervention_controls", {})
    strict = ic.get("strict_controls", True)
    split  = config.get("primary_split", "random")
    n_boot = config["stats"].get("bootstrap_resamples", 10000)
    seed   = config.get("seed", 42)
    model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                    or ensure_legacy_model_run(run_id))

    primary = _load_pairs(run_id, "morphorepr", config=config, model_run_id=model_run_id, split=split)
    p_point = compute_global_macro_f1(primary)
    results = {"primary": p_point, "controls": {}}
    metric_rows = []

    controls = ic.get("controls_to_run") or [
        k for k, v in ic.items() if v is True and k not in {
            "run_in_pipeline", "strict_controls", "score_controls", "controls_to_run",
            "prompt_only_annotation_source", "random_direction_seed_mode",
            "matched_activation_freq_log_eps"}]
    for control_name in controls:
        try:
            c_pairs = load_intervention_control_pairs(
                run_id, control_name, method="morphorepr", config=config,
                model_run_id=model_run_id, split=split)
        except RuntimeError as e:
            if strict:
                raise
            logger.warning(f"Contrôle '{control_name}' IGNORÉ au scoring (absent/incomplet) : {e} "
                           f"— AUCUN verdict produit."); continue
        c_point = compute_global_macro_f1(c_pairs)
        d = paired_diff_bootstrap(primary, c_pairs, n_boot, seed)
        d["coverage"] = {"primary_pairs": p_point["n_pairs"], "control_pairs": c_point["n_pairs"],
                         "n_shared_features": d["n_shared_features"]}
        results["controls"][control_name] = {"macro_f1": c_point["macro_f1"], **d}
        metric_rows.append((f"intervention_control_macro_f1:{control_name}", c_point["macro_f1"],
                            None, None, c_point["n_pairs"], f"control:{control_name}"))
        metric_rows.append((f"intervention_control_paired_diff:{control_name}", d["diff"],
                            d["ci_low"], d["ci_high"], d["n_shared_features"], f"control:{control_name}"))
        logger.info(f"Contrôle {control_name} : macro-F1={c_point['macro_f1']} ; "
                    f"diff primaire−contrôle={d['diff']} IC95=[{d['ci_low']},{d['ci_high']}] "
                    f"(features partagées={d['n_shared_features']}).")

    with get_conn() as conn:
        for name, value, lo, hi, n, base in metric_rows:
            conn.execute("""INSERT INTO metrics (metric_id, run_id, model_run_id, phase, split,
                            metric_name, value, ci_low, ci_high, n_samples, baseline, computed_at)
                            VALUES (?, ?, ?, 'p4_controls', ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (str(uuid4()), run_id, model_run_id, split, name, value, lo, hi, n, base,
                          datetime.utcnow().isoformat()))
    return results
