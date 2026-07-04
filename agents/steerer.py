# agents/steerer.py
"""
Phase 4 — Steering d'activation SAE.

steer_feature() est IMPLÉMENTÉ pour le CHEMIN PROXY OPEN-WEIGHT (TransformerLens + SAE Lens,
espace 'residual_add_decoder'). Les chemins nnsight / modèle de production NE SONT PAS
implémentés (NotImplementedError explicite), de même que l'espace 'sae_latent_clamp'.
run_intervention_controls() est IMPLÉMENTÉ (v6.9.0) pour 5 contrôles (random_feature_same_layer,
matched_activation_freq, random_direction_same_norm, negative_steering, prompt_only) ; diffmean_reft
reste NON implémenté. Les résultats vont dans la table DÉDIÉE intervention_control_results et sont
scorés comme métriques SECONDAIRES (jamais le primaire). causal_scorer._load_pairs() est IMPLÉMENTÉ
(assemblage déterministe prédiction/observation, métrique primaire — voir le scoreur causal §8 bis
et le changelog v6.7.0).
Phase 4 reste DÉSACTIVÉE par défaut (steering.run_in_pipeline=false) ; assert_steering_ready()
doit passer sur un dev run avant tout pilot/full run avec steering activé (Règle 9). L'objectif
de la série v6.6.x est un dev run de Phase 4 testable, PAS une validation scientifique de la Phase 4.

Spécification de l'intervention (v6) :
  - Espace :          'residual_add_decoder' (ajout d'un multiple de W_dec au résiduel) — IMPLÉMENTÉ.
                      'sae_latent_clamp' (clamp de l'activation latente) — NON implémenté (erreur
                      explicite). ATTENTION : ajouter k×W_dec au résiduel ne garantit PAS une
                      hausse de k×p99 de l'activation latente mesurée (norme du décodeur, encodage,
                      interférences, non-linéarités). On RAPPORTE le delta OBTENU (achieved_delta).
  - Couche :          la COUCHE PROPRE DU FEATURE (layer_index) ; SAE chargé/caché par couche (Règle 6)
  - Position token :  configurable ("all" | "last" | "content_only")
  - Amplitude :       PRIMAIRE = primary_magnitude_rel × activation_p99 (mode "p99_relative") ;
                      +5 absolu en condition SECONDAIRE (mode "absolute")
  - Sondes :          n_probe_sentences (50 primaire / 20 pilot), generations_per_probe générations,
                      deux familles : 'neutral' et 'domain_compatible'
  - Détection OOD :   critère MIXTE (Règle/Section 7) :
                      OOD si activation_after > max(p99·tau, mean + k·std, epsilon)
                          OU |activation_after - activation_before| > delta_max·p99
                      (robuste aux p99 faibles / distributions asymétriques). Stats issues
                      de la table features, PAS de la norme W_dec. ood_flag=1 exclu du primaire.

Chemins d'accès au modèle :
  A. TransformerLens — modèles proxy open-weight de style GPT — IMPLÉMENTÉ (proxy_model.enabled=true)
  B. nnsight         — accès à un modèle de production — NON implémenté
  C. Poids locaux    — modèle open-weight compatible SAE — via le chemin A


Modèle de validation (proxy par défaut, Règle 5) :
  proxy_model.enabled=true par défaut. Le pipeline entier opère alors sur les SAEs
  du proxy ; les exemples Claude 3 Sonnet restent illustratifs uniquement. À déclarer
  explicitement dans la section Méthodes.
"""
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Cache des SAE par couche (le corpus peut couvrir plusieurs couches).
_SAE_CACHE: dict = {}

REQUIRED_STEER_FIELDS = (
    "text_before", "text_after", "activation_before", "activation_after",
    "achieved_delta", "ood_flag",
)


def normalize_layer(layer) -> str:
    """Normalise une couche hétérogène (int, '6', 'blocks.6.hook_resid_post', 'middle'…)
    vers un sae_id 'blocks.{i}.hook_resid_post'. Lève ValueError si non interprétable
    (ex. 'middle' n'est PAS résolu ici : la couche doit être numérique au moment du steering)."""
    if isinstance(layer, str) and layer.startswith("blocks."):
        return layer
    if isinstance(layer, int):
        return f"blocks.{layer}.hook_resid_post"
    if isinstance(layer, str) and layer.isdigit():
        return f"blocks.{int(layer)}.hook_resid_post"
    raise ValueError(
        f"Couche non interprétable comme indice numérique : {layer!r}. "
        f"Fournir layer_index (entier) dans la table features."
    )


def _get_sae(config: dict, layer):
    """
    Charge (et cache) le SAE pour une COUCHE donnée — celle du feature.
    `layer` doit être numérique (layer_index) ou un sae_id déjà formé.
    Implémenter l'un des trois chemins avant le pilot run.
    """
    sae_id = normalize_layer(layer)
    if sae_id in _SAE_CACHE:
        return _SAE_CACHE[sae_id]
    proxy = config.get("proxy_model", {})
    if proxy.get("enabled"):
        from sae_lens import SAE
        sae, _, _ = SAE.from_pretrained(
            release=proxy["sae_release"],
            sae_id=sae_id
        )
        _SAE_CACHE[sae_id] = sae
        return sae
    raise NotImplementedError(
        "_get_sae() non implémenté.\n"
        "Pour débloquer :\n"
        "  A. Mettre proxy_model.enabled=true et utiliser un SAE public, OU\n"
        "  B. Implémenter l'accès au SAE d'un modèle de production via sae_lens/nnsight.\n"
        "Valider en dev run avant le pilot run."
    )


def assert_steering_ready(config: dict, n_probe: int = 5):
    """Garde pré-pilot (Règle 9) : vérifie que steer_feature() produit RÉELLEMENT
    tous les champs requis sur un mini dev run, en utilisant une VRAIE feature de la DB
    (couche, index, stats réels) plutôt que des valeurs artificielles. Lève RuntimeError
    sinon. À appeler avant tout pilot/full run impliquant la Phase 4."""
    from utils.db_utils import get_conn
    with get_conn() as conn:
        feat = conn.execute("""
            SELECT feature_uid, feature_index, layer_index,
                   activation_p99, activation_mean, activation_std
            FROM features
            WHERE split='random'
            ORDER BY feature_uid
            LIMIT 1
        """).fetchone()
    if feat is None:
        raise RuntimeError(
            "assert_steering_ready : aucune feature 'random' en DB. "
            "Exécuter au moins les Phases 1–2 avant de valider la Phase 4."
        )
    model = _get_model(config)
    sae   = _get_sae(config, feat["layer_index"])      # couche RÉELLE de la feature
    probes = load_probe_sentences(n_probe)
    stats = {
        "activation_p99":  feat["activation_p99"],
        "activation_mean": feat["activation_mean"],
        "activation_std":  feat["activation_std"],
    }
    results = steer_feature(model, sae, feature_index=feat["feature_index"], magnitude=2.0,
                            probe_sentences=probes, feature_stats=stats, config=config)
    if not results:
        raise RuntimeError("assert_steering_ready : steer_feature n'a produit aucun résultat.")
    missing = [f for f in REQUIRED_STEER_FIELDS if any(f not in r for r in results)]
    if missing:
        raise RuntimeError(
            f"assert_steering_ready : champs manquants {missing}. "
            f"Implémenter steer_feature() (contrat v6) avant le pilot run."
        )
    if any(r.get("text_after") in (None, r.get("text_before")) for r in results):
        raise RuntimeError("assert_steering_ready : text_after non produit (placeholder non remplacé).")


def _get_model(config: dict):
    """
    Charge le modèle de langage pour le steering.
    Implémenter l'un des trois chemins avant le pilot run.
    """
    proxy = config.get("proxy_model", {})
    if proxy.get("enabled"):
        import transformer_lens
        model = transformer_lens.HookedTransformer.from_pretrained(proxy["name"])
        return model
    raise NotImplementedError(
        "_get_model() non implémenté.\n"
        "Pour débloquer :\n"
        "  A. Mettre proxy_model.enabled=true et implémenter le chemin TransformerLens, OU\n"
        "  B. Implémenter le chemin nnsight pour l'accès à Claude, OU\n"
        "  C. Charger un modèle open-weight local.\n"
        "Valider en dev run avant le pilot run."
    )


def load_probe_sentences(n: int = 20, family: str = "neutral") -> list[str]:
    """
    Charge les phrases-sondes depuis data/probes/, un fichier par famille.
      - family='neutral'          → data/probes/probes_neutral.txt
      - family='code'/'social'/…  → data/probes/probes_{family}.txt
    Exigences (neutral) : 10–30 tokens, sans contenu émotionnel/technique fort, sans
    entités nommées, sans négation. Les familles domain_compatible sont pré-enregistrées
    par catégorie et ne doivent PAS donner la réponse à l'avance (Section 7).
    """
    path = Path(f"data/probes/probes_{family}.txt")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} introuvable.\n"
            f"Créer data/probes/ avec un fichier par famille/catégorie "
            f"(probes_neutral.txt, probes_code.txt, …) avant le dev run."
        )
    sentences = [l.strip() for l in path.read_text().splitlines()
                 if l.strip()][:n]
    if len(sentences) < n:
        raise ValueError(
            f"Seulement {len(sentences)} phrases-sondes '{family}' disponibles, {n} requises."
        )
    return sentences


def load_domain_probes(n_per_category: int, config: dict) -> dict[str, list[str]]:
    """Charge les sondes compatibles par domaine (une liste par catégorie pré-enregistrée)."""
    cats = config["steering"].get("domain_probe_categories", [])
    return {c: load_probe_sentences(n_per_category, family=c) for c in cats}


def _is_ood(activation_after, activation_before, feature_stats: dict, config: dict) -> int:
    """Critère OOD MIXTE pré-enregistré (Section 7). Robuste aux p99 faibles /
    distributions asymétriques. Renvoie 1 si hors-distribution, 0 sinon."""
    if activation_after is None:
        return 0
    st   = config["steering"]
    p99  = feature_stats.get("activation_p99")
    mean = feature_stats.get("activation_mean")
    std  = feature_stats.get("activation_std")
    tau, k = st.get("ood_tau", 3.0), st.get("ood_k", 4.0)
    eps    = st.get("ood_epsilon", 1e-3)
    dmax   = st.get("ood_delta_max", 5.0)
    thresholds = [eps]
    if p99 is not None:
        thresholds.append(p99 * tau)
    if mean is not None and std is not None:
        thresholds.append(mean + k * std)
    level = max(thresholds)
    if abs(activation_after) > level:
        return 1
    if (p99 is not None and activation_before is not None
            and abs(activation_after - activation_before) > dmax * p99):
        return 1
    return 0


def _get_hook_name_from_sae(sae, config) -> str:
    """Résout le hook_name de l'intervention. Priorité à sae.cfg.hook_name (SAE Lens) ;
    sinon sae.cfg.hook_layer → normalize_layer(int). Erreur explicite si indéterminable.
    On NE hardcode PAS une couche globale (la couche est celle du SAE/feature)."""
    cfg = getattr(sae, "cfg", None)
    name = getattr(cfg, "hook_name", None)
    if name:
        return name
    hook_layer = getattr(cfg, "hook_layer", None)
    if hook_layer is not None:
        return normalize_layer(int(hook_layer))
    raise ValueError(
        "hook_name introuvable : ni sae.cfg.hook_name ni sae.cfg.hook_layer disponibles. "
        "Vérifier la version de sae_lens / l'objet SAE."
    )


def _tokens_from_prompt(model, sentence: str):
    """Tokenise une phrase-sonde via l'API TransformerLens (model.to_tokens)."""
    return model.to_tokens(sentence)


def _position_indices(seq_len: int, token_position: str) -> list[int]:
    """Indices de positions (entiers) selon token_position — logique PURE (sans torch),
    utilisée à la fois pour la mesure et pour le hook d'intervention.
      - 'last'         : dernier token
      - 'content_only' : exclut le BOS (index 0)
      - 'all'          : toutes les positions
    Repli sur [seq_len-1] si la sélection est vide."""
    if token_position == "last":
        return [seq_len - 1]
    idx = list(range(seq_len))
    if token_position == "content_only":
        idx = [i for i in idx if i != 0]      # exclure BOS
    return idx if idx else [seq_len - 1]


def _selected_token_positions(tokens, token_position: str, pad_token_id=None) -> list[int]:
    """Positions utiles pour une phrase. `tokens` : tenseur [1, seq] / [seq] ou un entier
    seq_len. En 'content_only', exclut aussi les positions de padding si pad_token_id fourni."""
    if isinstance(tokens, int):
        return _position_indices(tokens, token_position)
    row = tokens[0] if hasattr(tokens, "dim") and tokens.dim() == 2 else tokens
    seq_len = int(len(row))
    idx = _position_indices(seq_len, token_position)
    if token_position == "content_only" and pad_token_id is not None:
        rl = row.tolist() if hasattr(row, "tolist") else list(row)
        idx = [i for i in idx if rl[i] != pad_token_id]
    return idx if idx else [seq_len - 1]


def _aggregate_feature_activation(feature_acts, token_positions, feature_index: int,
                                  aggregation: str = "max") -> float:
    """Agrège l'activation latente du feature cible sur les positions sélectionnées.
    feature_acts : tenseur [seq, d_sae] ou [1, seq, d_sae]. Agrégation 'max' par défaut
    (on cherche l'activation MAXIMALE du feature sur la phrase) ; 'mean'/'last' supportées."""
    fa = feature_acts
    if fa.dim() == 3:
        fa = fa[0]                              # [seq, d_sae]
    col = fa[:, feature_index]                  # [seq]
    sel = col[token_positions] if len(token_positions) else col
    if aggregation == "last":
        val = sel[-1]
    elif aggregation == "mean":
        val = sel.mean()
    else:
        val = sel.max()
    return float(val.detach().cpu().item())


def _make_residual_add_decoder_hook(sae, feature_index: int, magnitude: float,
                                    token_position: str, config: dict):
    """Hook TransformerLens : ajoute magnitude · sae.W_dec[feature_index] au résiduel, AUX
    POSITIONS sélectionnées par token_position (les autres positions sont inchangées).
    NB : ajouter k·W_dec NE GARANTIT PAS une hausse de k de l'activation latente — d'où la
    mesure de achieved_delta. W_dec[feature_index] (PAS sa norme)."""
    direction = sae.W_dec[feature_index]        # [d_model]

    def hook(resid, hook):                      # resid : [batch, seq, d_model]
        seq = resid.shape[1]
        positions = _position_indices(seq, token_position)
        d = direction.to(device=resid.device, dtype=resid.dtype)
        resid[:, positions, :] = resid[:, positions, :] + float(magnitude) * d
        return resid

    return hook


def _validate_feature_and_shapes(sae, feature_index: int, resid) -> None:
    """Validations de bornes/shapes avec erreurs EXPLICITES (formes observées) :
      - feature_index ∈ [0, sae.W_dec.shape[0]) ;
      - d_model du décodeur (W_dec.shape[1]) == d_model du résiduel (resid.shape[-1])."""
    n_features = sae.W_dec.shape[0]
    if not (0 <= int(feature_index) < int(n_features)):
        raise IndexError(
            f"feature_index={feature_index} hors borne [0, {n_features}) "
            f"(sae.W_dec.shape[0]={n_features})."
        )
    d_dec = sae.W_dec.shape[1]
    d_resid = resid.shape[-1]
    if int(d_dec) != int(d_resid):
        raise ValueError(
            f"Dimension incompatible SAE/résiduel : W_dec d_model={d_dec} ≠ résiduel "
            f"d_model={d_resid} (W_dec.shape={tuple(sae.W_dec.shape)}, "
            f"resid.shape={tuple(resid.shape)})."
        )


def _measure_feature_activation(model, sae, tokens, feature_index: int, config: dict,
                                hook_fn=None, hook_name: str = None) -> float:
    """Forward pass → résiduel au hook du SAE → encode SAE → activation du feature cible,
    agrégée selon token_position. Si hook_fn est fourni, il est appliqué AVANT la capture
    (le résiduel mesuré est donc post-intervention). On capture via un hook de capture ajouté
    APRÈS le hook d'intervention (ordre des fwd_hooks garanti) pour éviter toute ambiguïté.

    SÉMANTIQUE (Option A, v6.6.1) : la mesure porte sur le CONTEXTE de la phrase-sonde
    (`tokens`), PAS sur la continuation générée. activation_before/after sont donc des
    `probe_activation_before/after` : elles quantifient l'effet de l'intervention sur le
    résiduel de la sonde au hook du SAE. (Option B — mesurer sur le texte généré complet —
    mélangerait l'effet du changement de texte avec l'effet direct de l'intervention ; non
    retenue en v6.6.1. Aucun changement de schéma.)"""
    hook_name = hook_name or _get_hook_name_from_sae(sae, config)
    captured = {}

    def _capture(resid, hook):
        captured["resid"] = resid
        return resid

    fwd = []
    if hook_fn is not None:
        fwd.append((hook_name, hook_fn))        # intervention d'abord
    fwd.append((hook_name, _capture))           # capture ensuite (post-intervention)
    model.run_with_hooks(tokens, fwd_hooks=fwd, return_type=None)

    if "resid" not in captured:
        raise RuntimeError(
            f"Le hook {hook_name} n'a pas été déclenché : impossible de mesurer l'activation. "
            f"Vérifier que le SAE et le modèle partagent bien ce point d'accroche."
        )
    resid = captured["resid"]
    if hasattr(resid, "dim") and resid.dim() == 2:
        resid = resid.unsqueeze(0)
    _validate_feature_and_shapes(sae, feature_index, resid)   # bornes + d_model (formes observées)
    dev = getattr(getattr(sae, "W_dec", None), "device", None)
    if dev is not None:
        resid = resid.to(dev)
    acts = sae.encode(resid)
    if isinstance(acts, tuple):                 # certaines versions renvoient (acts, …) — toléré, documenté
        acts = acts[0]
    if hasattr(acts, "dim") and acts.dim() not in (2, 3):
        raise ValueError(
            f"sae.encode a renvoyé une forme inattendue {tuple(acts.shape)} ; "
            f"attendu [batch, seq, d_sae] ou [seq, d_sae]."
        )
    st = config["steering"]
    pad_id = getattr(getattr(model, "tokenizer", None), "pad_token_id", None)
    positions = _selected_token_positions(tokens, st.get("token_position", "all"), pad_token_id=pad_id)
    return _aggregate_feature_activation(acts, positions, feature_index,
                                         aggregation=st.get("activation_aggregation", "max"))


def _supported_generate_kwargs(model, desired: dict) -> dict:
    """Filtre `desired` selon la signature RÉELLE de model.generate (compat TransformerLens
    multi-versions). Si generate accepte **kwargs (VAR_KEYWORD), tout est conservé. Lève
    AttributeError explicite si model.generate est absent / non appelable."""
    import inspect
    gen = getattr(model, "generate", None)
    if gen is None or not callable(gen):
        raise AttributeError(
            "model.generate introuvable ou non appelable : modèle incompatible avec le chemin "
            "de génération (TransformerLens HookedTransformer attendu)."
        )
    try:
        params = list(inspect.signature(gen).parameters.values())
    except (TypeError, ValueError):
        return dict(desired)                 # signature introuvable : tenter tel quel
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
        return dict(desired)                 # **kwargs → tout est accepté
    allowed = {p.name for p in params}
    return {k: v for k, v in desired.items() if k in allowed}


def _generate_text(model, prompt: str, config: dict, hook_fn=None) -> str:
    """Génère une continuation via model.generate, avec les paramètres GELÉS dans
    config['steering']['decoding'] (greedy si temperature=0). ROBUSTE aux signatures variables
    de TransformerLens : seuls les kwargs réellement supportés sont passés (introspection via
    _supported_generate_kwargs). Mapping greedy : temperature=0.0 et/ou do_sample=False selon
    le support ; top_p/verbose seulement s'ils sont acceptés. Si hook_fn=(hook_name, fn), la
    génération se fait AVEC le hook actif (steering). Le prompt est inchangé entre before/after.
    Retourne la sortie GÉNÉRÉE (≠ simple phrase-sonde)."""
    dec = config["steering"].get("decoding", {})
    temperature = dec.get("temperature", 0.0)
    greedy = not (temperature and float(temperature) > 0.0)
    desired = {"max_new_tokens": dec.get("max_new_tokens", 64), "verbose": False}
    if greedy:
        desired["do_sample"] = False         # greedy déterministe
        desired["temperature"] = 0.0
    else:
        desired["do_sample"] = True
        desired["temperature"] = float(temperature)
        if "top_p" in dec:
            desired["top_p"] = dec["top_p"]
    kw = _supported_generate_kwargs(model, desired)
    logger.debug(
        f"_generate_text → model.generate kwargs={sorted(kw)} "
        f"(greedy={greedy}, hook={'oui' if hook_fn else 'non'})"
    )
    if hook_fn is not None:
        hook_name, fn = hook_fn
        with model.hooks(fwd_hooks=[(hook_name, fn)]):
            return model.generate(prompt, **kw)
    return model.generate(prompt, **kw)


def steer_feature(model,
                  sae,
                  feature_index: int,
                  magnitude: float,
                  probe_sentences: list[str],
                  feature_stats: dict,
                  config: dict) -> list[dict]:
    """
    Applique le steering et retourne, par phrase-sonde, la paire avant/après + le delta OBTENU.

    IMPLÉMENTÉ pour le CHEMIN PROXY OPEN-WEIGHT (TransformerLens + SAE Lens), espace
    `residual_add_decoder`. PAS de simulation, PAS de placeholder : text_before/after sont des
    générations réelles, les activations sont mesurées par forward pass + encode SAE.

    Chemins NON implémentés (erreur explicite) :
      - proxy_model.enabled=false (chemin nnsight / modèle de production) → NotImplementedError ;
      - intervention_space='sae_latent_clamp' → NotImplementedError (v6.6.0 ne fait que
        'residual_add_decoder', le chemin primaire le plus simple à valider).

    La détection OOD utilise activation_p99/mean/std (feature_stats), PAS la norme de W_dec.
    Ajouter magnitude·W_dec au résiduel ne garantit pas une hausse égale de l'activation
    latente : on mesure et rapporte achieved_delta (Section 7).

    SÉMANTIQUE (Option A, v6.6.1) : activation_before/after sont des `probe_activation_before/after`
    — mesurées sur le CONTEXTE de la phrase-sonde au hook du SAE, PAS sur la continuation
    générée (voir _measure_feature_activation). text_before/after sont, eux, des générations
    réelles. Aucun changement de schéma.
    """
    proxy = config.get("proxy_model", {})
    if not proxy.get("enabled"):
        raise NotImplementedError(
            "steer_feature() : seul le chemin PROXY OPEN-WEIGHT est implémenté "
            "(mettre proxy_model.enabled=true). Les chemins nnsight / modèle de production "
            "ne sont PAS implémentés (aucune interface publique ne garantit le steering interne "
            "d'un modèle propriétaire)."
        )

    space = config["steering"].get("intervention_space", "residual_add_decoder")
    if space == "sae_latent_clamp":
        raise NotImplementedError(
            "intervention_space='sae_latent_clamp' n'est PAS implémenté en v6.6.x "
            "(seul 'residual_add_decoder' l'est). Approche prévue (à implémenter proprement, "
            "sans pseudo-code) : encoder le résiduel, cloner les activations SAE, fixer "
            "l'activation cible vers activation_before+magnitude, puis appliquer au résiduel "
            "le delta de reconstruction decode(clamped)-decode(original). Tant que ce n'est "
            "pas fait, ce mode échoue bruyamment plutôt que de produire un faux résultat."
        )
    if space != "residual_add_decoder":
        raise ValueError(f"intervention_space inconnu : {space!r}")

    # Borne feature_index dès l'entrée (erreur explicite avant toute génération coûteuse)
    n_features = sae.W_dec.shape[0]
    if not (0 <= int(feature_index) < int(n_features)):
        raise IndexError(
            f"feature_index={feature_index} hors borne [0, {n_features}) "
            f"(sae.W_dec.shape[0]={n_features})."
        )

    token_position = config["steering"].get("token_position", "all")
    hook_name = _get_hook_name_from_sae(sae, config)
    results = []

    for probe_id, sentence in enumerate(probe_sentences, 1):
        try:
            # 1. Continuation SANS intervention (sortie générée, pas la simple phrase-sonde)
            text_before = _generate_text(model, sentence, config, hook_fn=None)

            # 2. Activation latente AVANT (forward pass + encode SAE + agrégation)
            tokens = _tokens_from_prompt(model, sentence)
            activation_before = _measure_feature_activation(
                model, sae, tokens, feature_index, config, hook_fn=None, hook_name=hook_name)

            # 3-4. Intervention residual_add_decoder + continuation AVEC hook actif (même prompt,
            #      mêmes paramètres de génération)
            steer_hook = _make_residual_add_decoder_hook(
                sae, feature_index, magnitude, token_position, config)
            text_after = _generate_text(model, sentence, config, hook_fn=(hook_name, steer_hook))

            # 5. Activation latente APRÈS (même hook actif, même agrégation)
            activation_after = _measure_feature_activation(
                model, sae, tokens, feature_index, config, hook_fn=steer_hook, hook_name=hook_name)

            # 6. Delta obtenu + OOD
            achieved_delta = activation_after - activation_before
            ood = _is_ood(activation_after, activation_before, feature_stats, config)

            results.append({
                "probe_id":          probe_id,
                "text_before":       text_before,
                "text_after":        text_after,
                "activation_before": activation_before,
                "activation_after":  activation_after,
                "achieved_delta":    achieved_delta,
                "ood_flag":          ood,
            })
        except NotImplementedError:
            raise   # NE JAMAIS masquer une erreur d'implémentation : échouer bruyamment
        except Exception as e:
            # Erreur technique sur UNE probe : consignée (le batch n'est pas interrompu), mais
            # text_after=None + 'error' fera échouer assert_steering_ready (comportement voulu :
            # un steering cassé ne doit pas passer pour valide).
            logger.warning(
                f"Erreur steering feature {feature_index} probe {probe_id} "
                f"magnitude {magnitude}: {e}"
            )
            results.append({
                "probe_id":          probe_id,
                "text_before":       sentence,
                "text_after":        None,
                "activation_before": None,
                "activation_after":  None,
                "achieved_delta":    None,
                "ood_flag":          0,
                "error":             str(e),
            })
    return results


def _load_encoded_random_features(run_id: str, model_run_id: str) -> list[dict]:
    """Charge les features du split 'random' encodées PAR LE MODÈLE `model_run_id` (Phase 4
    strictement model-aware, Règle 11). Le filtre `ao.model_run_id = ?` garantit qu'on ne
    steere QUE les annotations du modèle primaire : une sortie encoder secondaire ou legacy
    pour le même feature_uid n'est jamais récupérée sous le model_run_id primaire.
    C'est la logique de chargement utilisée par run()."""
    from utils.db_utils import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_uid,
                   f.feature_index,
                   f.split, f.layer, f.layer_index,
                   f.activation_p99,
                   f.activation_mean,
                   f.activation_std,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id = ? AND ao.model_run_id = ? AND ao.agent_name = 'encoder'
              AND ao.run_number = 1 AND ao.status = 'ok'
        """, (run_id, model_run_id)).fetchall()
    return [dict(r) for r in rows if r["split"] == "random"]


def run(run_id: str, config: dict):
    """Phase 4 — Steering. Magnitude normalisée par feature (× p99) ; dose-réponse seedée."""
    from utils.db_utils import get_conn

    logger.info("Phase 4 : Steering SAE")

    try:
        model = _get_model(config)        # le modèle est unique ; les SAE sont chargés par couche
    except NotImplementedError as e:
        logger.error(str(e))
        raise

    st              = config["steering"]
    mode            = st.get("magnitude_mode", "p99_relative")
    primary_rel     = st.get("primary_magnitude_rel", 1.0)
    dose_rel        = st.get("dose_response_rel", [0.0, 0.5, 1.0, 2.0])
    legacy_abs      = st.get("legacy_absolute_magnitude", 5)
    n_subsample     = st["n_subsample_for_curve"]
    seed            = config.get("seed", 42)
    gens            = st.get("generations_per_probe", 1)

    # Modèle du steering (Règle 11) : le modèle ouvert primaire si disponible (stash de
    # l'orchestrateur), sinon un model_run legacy explicite. steering_results.model_run_id NOT NULL.
    from utils.db_utils import ensure_legacy_model_run
    model_run_id = (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
                    or ensure_legacy_model_run(run_id))

    # Volumétrie du PRIMAIRE (Sections 6–7) : sondes NEUTRES par défaut, generations_per_probe
    # (1 recommandé avec un décodage greedy temperature=0). n_probe_sentences_pilot est utilisé
    # en mode dev/pilot. Les sondes domaine sont une analyse SECONDAIRE par défaut
    # (use_domain_probes_in_primary=false) ; quand activées, elles restent ventilées PAR
    # CATÉGORIE (probe_category conservée, non fusionnée).
    run_mode  = config.get("run_mode", "full")
    n_neutral = (st.get("n_probe_sentences_pilot", st["n_probe_sentences"])
                 if run_mode in ("dev", "pilot") else st["n_probe_sentences"])

    # probe_sets : liste de (probe_family, probe_category, sentences).
    probe_sets = [("neutral", None, load_probe_sentences(n_neutral, family="neutral"))]
    if st.get("use_domain_probes_in_primary", False) and \
       "domain_compatible" in st.get("probe_families", []):
        n_dom = st.get("n_domain_probes_per_category", n_neutral)
        for cat, sents in load_domain_probes(n_dom, config).items():
            probe_sets.append(("domain_compatible", cat, sents))

    # Chargement STRICTEMENT model-aware : uniquement les annotations encoder du modèle primaire
    # (filtre ao.model_run_id dans _load_encoded_random_features). Pas de fuite multi-modèle.
    random_features = _load_encoded_random_features(run_id, model_run_id)

    # Sous-échantillon seedé — PAS [:n] qui dépendrait de l'ordre de la DB
    rng       = random.Random(seed)
    subsample = rng.sample(random_features,
                           min(n_subsample, len(random_features)))
    subsample_uids = {f["feature_uid"] for f in subsample}

    # Sous-échantillon : courbe dose-réponse complète (multiples de p99, contrôle 0 inclus)
    _run_steering_batch(run_id, model, subsample, dose_rel,
                        probe_sets, gens, config, mode, legacy_abs, model_run_id)

    # Features restants : contrôle (0) + magnitude primaire uniquement
    remaining = [f for f in random_features
                 if f["feature_uid"] not in subsample_uids]
    _run_steering_batch(run_id, model, remaining, [0.0, primary_rel],
                        probe_sets, gens, config, mode, legacy_abs, model_run_id)

    logger.info("Phase 4 steering terminée")


def _insert_steering_result(conn, run_id, model_run_id, feat, space, mag_abs, mag_rel, magnitude_key,
                            family, category, g, r, config):
    """Insertion NON SILENCIEUSE : conserve la 1ʳᵉ sortie d'une cellule, mais journalise
    toute tentative de réécriture DIFFÉRENTE (table steering_duplicate_attempts) au lieu de
    l'ignorer en silence (cohérent avec save_agent_output). Rattaché au modèle (Règle 11)."""
    key = (run_id, model_run_id, feat.get("feature_uid"), space, magnitude_key,
           family, category, r["probe_id"], g)
    existing = conn.execute("""
        SELECT result_id, text_after FROM steering_results
        WHERE run_id=? AND model_run_id=? AND feature_uid=? AND intervention_space=? AND magnitude_key=?
          AND probe_family IS ? AND probe_category IS ? AND probe_id=? AND generation_index=?
    """, key).fetchone()
    if existing is not None:
        if existing["text_after"] != r.get("text_after"):
            conn.execute("""
                INSERT INTO steering_duplicate_attempts (
                    attempt_id, run_id, feature_uid, intervention_space, magnitude_key,
                    probe_family, probe_category, probe_id, generation_index,
                    previous_result_id, attempted_text_before, attempted_text_after,
                    attempted_activation_before, attempted_activation_after,
                    attempted_achieved_delta, attempted_ood_flag, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid4()), run_id, feat.get("feature_uid"), space, magnitude_key,
                  family, category, r["probe_id"], g,
                  existing["result_id"], r.get("text_before"), r.get("text_after"),
                  r.get("activation_before"), r.get("activation_after"),
                  r.get("achieved_delta"), r.get("ood_flag", 0),
                  datetime.utcnow().isoformat()))
            logger.warning(f"Divergence steering ignorée (1ʳᵉ sortie conservée) pour "
                           f"{feat.get('feature_uid')} {family}/{category} probe {r['probe_id']} gen {g}")
        return
    conn.execute("""
        INSERT INTO steering_results (
            result_id, run_id, model_run_id, feature_uid, feature_index,
            intervention_space, magnitude, magnitude_rel, magnitude_key,
            probe_id, probe_family, probe_category, generation_index,
            text_before, text_after, layer, token_position,
            activation_before, activation_after, achieved_delta,
            ood_flag, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uuid4()), run_id, model_run_id, feat.get("feature_uid"), feat["feature_index"], space,
        mag_abs, mag_rel, magnitude_key, r["probe_id"], family, category, g,
        r["text_before"], r.get("text_after"), feat.get("layer"),
        config["steering"].get("token_position"),
        r.get("activation_before"), r.get("activation_after"), r.get("achieved_delta"),
        r.get("ood_flag", 0), datetime.utcnow().isoformat()
    ))


def _run_steering_batch(run_id: str, model,
                        features: list[dict],
                        rel_magnitudes: list[float],
                        probe_sets: list[tuple],   # (probe_family, probe_category, sentences)
                        generations_per_probe: int,
                        config: dict,
                        mode: str,
                        legacy_abs: float,
                        model_run_id: str):
    from utils.db_utils import get_conn
    space = config["steering"].get("intervention_space", "residual_add_decoder")
    with get_conn() as conn:
        for feat in features:
            p99 = feat.get("activation_p99")
            # SAE de la COUCHE PROPRE du feature : on utilise layer_index (numérique).
            sae = _get_sae(config, feat.get("layer_index", feat.get("layer")))
            feature_stats = {
                "activation_p99":  p99,
                "activation_mean": feat.get("activation_mean"),
                "activation_std":  feat.get("activation_std"),
            }
            for rel in rel_magnitudes:
                # magnitude_key : clé TEXTE stable (idempotence dans LES DEUX modes).
                if mode == "absolute":
                    mag_abs, mag_rel = (0.0 if rel == 0.0 else float(legacy_abs)), None
                    magnitude_key = "rel:0.0" if rel == 0.0 else f"abs:{legacy_abs}"
                else:
                    mag_rel = rel
                    magnitude_key = f"rel:{rel}"
                    if rel == 0.0:
                        mag_abs = 0.0
                    elif p99 is not None:
                        mag_abs = rel * p99
                    else:
                        logger.warning(
                            f"activation_p99 manquant pour feature "
                            f"{feat['feature_index']} — magnitude relative {rel} ignorée"
                        )
                        continue
                # (famille, catégorie) × générations multiples ; colonnes probe_* alimentées
                for family, category, sentences in probe_sets:
                    for g in range(generations_per_probe):
                        results = steer_feature(
                            model, sae, feat["feature_index"],
                            mag_abs, sentences, feature_stats, config
                        )
                        for r in results:
                            _insert_steering_result(conn, run_id, model_run_id, feat, space, mag_abs,
                                                    mag_rel, magnitude_key, family, category,
                                                    g, r, config)


# ─── Contrôles d'intervention (v6.9.0) ──────────────────────────────────────────────────────
# run_intervention_controls() est IMPLÉMENTÉ pour 5 contrôles. Résultats dans la table DÉDIÉE
# intervention_control_results (JAMAIS steering_results). Métriques SECONDAIRES uniquement.
# Strictement model/split/intervention_space-aware ; politique OOD respectée. diffmean_reft reste
# NON implémenté (NotImplementedError si demandé). Désactivé par défaut (run_in_pipeline=false).

_IMPLEMENTED_CONTROLS = {"random_feature_same_layer", "matched_activation_freq",
                         "random_direction_same_norm", "negative_steering", "prompt_only"}
_UNIMPLEMENTED_CONTROLS = {"diffmean_reft"}
_CONTROL_META_KEYS = {"run_in_pipeline", "strict_controls", "score_controls", "controls_to_run",
                      "prompt_only_annotation_source", "random_direction_seed_mode",
                      "matched_activation_freq_log_eps"}


def _derive_int_seed(*parts) -> int:
    import hashlib
    return int(hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def _primary_model_run_id(run_id: str, config: dict) -> str:
    from utils.db_utils import ensure_legacy_model_run
    return (config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
            or ensure_legacy_model_run(run_id))


def _primary_magnitude_key(config: dict) -> str:
    """Clé TEXTE de la magnitude primaire (cohérente avec _run_steering_batch / causal_scorer)."""
    st = config["steering"]
    if st.get("magnitude_mode", "p99_relative") == "absolute":
        return f"abs:{st.get('legacy_absolute_magnitude', 5)}"
    return f"rel:{st.get('primary_magnitude_rel', 1.0)}"


def _primary_magnitude(config: dict, feature: dict):
    """(mag_abs, mag_rel, magnitude_key) à la magnitude PRIMAIRE — même logique que run()."""
    st   = config["steering"]
    mode = st.get("magnitude_mode", "p99_relative")
    rel  = st.get("primary_magnitude_rel", 1.0)
    if mode == "absolute":
        legacy = st.get("legacy_absolute_magnitude", 5)
        return float(legacy), None, f"abs:{legacy}"
    p99 = feature.get("activation_p99")
    if p99 is None:
        raise ValueError(f"activation_p99 manquant pour {feature.get('feature_uid')!r} : "
                         f"magnitude relative impossible.")
    return rel * p99, rel, f"rel:{rel}"


def _controls_to_run(config: dict) -> list[str]:
    """controls_to_run prioritaire ; sinon clés booléennes true (compat héritée)."""
    ic = config.get("intervention_controls", {})
    explicit = ic.get("controls_to_run")
    if explicit:
        return list(explicit)
    return [k for k, v in ic.items() if v is True and k not in _CONTROL_META_KEYS]


def _load_control_targets(run_id: str, model_run_id: str, split: str) -> list[dict]:
    """Targets = features du split encodées (MorphoRepr) par le modèle PRIMAIRE. model/split-aware."""
    from utils.db_utils import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT DISTINCT f.feature_uid, f.feature_index, f.layer, f.layer_index,
                   f.activation_p99, f.activation_mean, f.activation_std, f.activation_freq,
                   f.nl_description
            FROM agent_outputs ao JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id=? AND ao.model_run_id=? AND ao.agent_name='encoder'
              AND ao.run_number=1 AND ao.status='ok' AND f.split=?
        """, (run_id, model_run_id, split)).fetchall()
    return [dict(r) for r in rows]


def _load_layer_candidates(layer_index, exclude_uid: str) -> list[dict]:
    """Features de la MÊME couche (hors target). N'importe quelle feature SAE de la couche peut
    être steerée comme contrôle (indépendant de l'encodage MorphoRepr)."""
    from utils.db_utils import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT feature_uid, feature_index, layer, layer_index,
                   activation_p99, activation_mean, activation_std, activation_freq
            FROM features WHERE layer_index=? AND feature_uid<>?
        """, (layer_index, exclude_uid)).fetchall()
    return [dict(r) for r in rows]


def _select_random_feature_same_layer(target: dict, candidates: list[dict], seed: int):
    """Feature aléatoire DÉTERMINISTE de même couche, ≠ target. None si aucune candidate."""
    if not candidates:
        return None
    rng = random.Random(f"{seed}|{target['feature_uid']}|random_feature_same_layer")
    return candidates[rng.randrange(len(candidates))]


def _select_matched_activation_freq(target: dict, candidates: list[dict], log_eps: float = 1e-9):
    """Feature de même couche minimisant |log(freq_t+eps) − log(freq_c+eps)|. (control, distance)
    ou (None, None) si aucune candidate exploitable."""
    import math
    ft = target.get("activation_freq")
    pool = [c for c in candidates if c.get("activation_freq") is not None]
    if ft is None or not pool:
        return None, None
    def dist(c): return abs(math.log(ft + log_eps) - math.log(c["activation_freq"] + log_eps))
    best = min(pool, key=dist)
    return best, dist(best)


def _make_random_direction_hook(d_model: int, norm: float, magnitude: float,
                                token_position: str, seed: int):
    """Hook ajoutant magnitude·(direction aléatoire ramenée à `norm`) au résiduel, aux positions
    sélectionnées. DÉTERMINISTE (torch.Generator seedé). Renvoie (hook, used_norm)."""
    import torch
    g = torch.Generator(device="cpu"); g.manual_seed(int(seed) & 0x7FFFFFFF)
    v = torch.randn(d_model, generator=g)
    v = v / (v.norm() + 1e-12) * float(norm)        # même norme que W_dec[target]
    used_norm = float(v.norm().item())

    def hook(resid, hook):
        seq = resid.shape[1]
        positions = _position_indices(seq, token_position)
        d = v.to(device=resid.device, dtype=resid.dtype)
        resid[:, positions, :] = resid[:, positions, :] + float(magnitude) * d
        return resid

    return hook, used_norm


def _prompt_only_annotation(run_id, model_run_id, target, config) -> str:
    """Annotation injectée pour prompt_only. Source 'morphorepr' → expression encoder du target ;
    sinon nl_description. Repli sur nl_description si l'expression manque."""
    src = config.get("intervention_controls", {}).get("prompt_only_annotation_source", "morphorepr")
    if src == "morphorepr":
        from utils.db_utils import get_conn
        with get_conn() as conn:
            row = conn.execute("""
                SELECT json_extract(output_json, '$.expression') AS expr
                FROM agent_outputs WHERE run_id=? AND model_run_id=? AND feature_uid=?
                  AND agent_name='encoder' AND run_number=1 AND status='ok'
            """, (run_id, model_run_id, target["feature_uid"])).fetchone()
        expr = row["expr"] if row else None
        return expr or target.get("nl_description") or ""
    return target.get("nl_description") or ""


def _enrich_prompt(sentence: str, annotation: str) -> str:
    """Prompt enrichi pour prompt_only : injecte l'étiquette SANS aucune intervention résiduelle."""
    annotation = (annotation or "").strip()
    return f"Consider the concept: {annotation}. {sentence}" if annotation else sentence


def _control_rows_exist(conn, run_id, model_run_id, target_uid, control_name) -> bool:
    return conn.execute("""
        SELECT COUNT(*) FROM intervention_control_results
        WHERE run_id=? AND model_run_id=? AND target_feature_uid=? AND control_name=?
    """, (run_id, model_run_id, target_uid, control_name)).fetchone()[0] > 0


def _insert_intervention_control_result(conn, run_id, model_run_id, target, control_name,
                                        control_feat, space, magnitude, mag_rel, mag_key,
                                        family, category, probe_id, g, text_before, text_after,
                                        a_before, a_after, achieved, ood, metadata) -> bool:
    """Insertion idempotente NON SILENCIEUSE dans intervention_control_results (1ʳᵉ sortie
    conservée ; divergence journalisée). Renvoie True si une ligne a été insérée."""
    cuid = control_feat.get("feature_uid") if control_feat else None
    cidx = control_feat.get("feature_index") if control_feat else None
    existing = conn.execute("""
        SELECT control_result_id, text_after FROM intervention_control_results
        WHERE run_id=? AND model_run_id=? AND target_feature_uid=? AND control_name=?
          AND control_feature_uid IS ? AND intervention_space IS ? AND magnitude_key=?
          AND probe_family IS ? AND probe_category IS ? AND probe_id=? AND generation_index=?
    """, (run_id, model_run_id, target["feature_uid"], control_name, cuid, space, mag_key,
          family, category, probe_id, g)).fetchone()
    if existing is not None:
        if existing["text_after"] != text_after:
            logger.warning(f"Divergence contrôle {control_name}/{target['feature_uid']} probe "
                           f"{probe_id} gen {g} — 1ʳᵉ sortie conservée (non écrasée).")
        return False
    conn.execute("""
        INSERT INTO intervention_control_results (
            control_result_id, run_id, model_run_id, target_feature_uid, target_feature_index,
            control_name, control_feature_uid, control_feature_index, intervention_space,
            magnitude, magnitude_rel, magnitude_key, probe_id, probe_family, probe_category,
            generation_index, text_before, text_after, activation_before, activation_after,
            achieved_delta, ood_flag, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid4()), run_id, model_run_id, target["feature_uid"], target["feature_index"],
          control_name, cuid, cidx, space, magnitude, mag_rel, mag_key, probe_id, family, category,
          g, text_before, text_after, a_before, a_after, achieved, ood,
          json.dumps(metadata) if metadata else None, datetime.utcnow().isoformat()))
    return True


def _build_control_plan(run_id, model_run_id, control_name, target, config):
    """Plan d'exécution pour (control_name, target), ou None si skip (non strict). Le plan isole
    ce qui DIFFÈRE entre contrôles : feature steerée, magnitude/clé, hook (ou non), feature/SAE
    mesurés, métadonnées, mode prompt_only."""
    st = config["steering"]
    space = st.get("intervention_space", "residual_add_decoder")
    token_position = st.get("token_position", "all")
    seed = config.get("seed", 42)
    ic = config.get("intervention_controls", {})
    strict = ic.get("strict_controls", True)
    layer = target.get("layer_index", target.get("layer"))
    target_stats = {"activation_p99": target.get("activation_p99"),
                    "activation_mean": target.get("activation_mean"),
                    "activation_std": target.get("activation_std")}
    plan = {"control_feat": None, "space": space, "metadata": {}, "prompt_only": False,
            "annotation": None, "hook_factory": None, "magnitude": None, "mag_rel": None,
            "mag_key": None, "measure_sae": None, "measure_index": target["feature_index"],
            "measure_stats": target_stats}

    if control_name in ("random_feature_same_layer", "matched_activation_freq"):
        cands = _load_layer_candidates(layer, target["feature_uid"])
        if control_name == "random_feature_same_layer":
            cf = _select_random_feature_same_layer(target, cands, seed)
        else:
            cf, dmatch = _select_matched_activation_freq(
                target, cands, ic.get("matched_activation_freq_log_eps", 1e-9))
        if cf is None:
            msg = (f"Contrôle '{control_name}' : aucune feature candidate de couche {layer} pour "
                   f"target {target['feature_uid']}.")
            if strict:
                raise RuntimeError(msg)
            logger.warning(msg + " — skip (non strict)."); return None
        if control_name == "matched_activation_freq":
            plan["metadata"]["freq_log_distance"] = dmatch
        sae = _get_sae(config, cf.get("layer_index", cf.get("layer")))
        idx = cf["feature_index"]
        mag_abs, mag_rel, mag_key = _primary_magnitude(config, cf)   # magnitude primaire de la CONTROL feature
        plan.update(control_feat=cf, magnitude=mag_abs, mag_rel=mag_rel, mag_key=mag_key,
                    measure_sae=sae, measure_index=idx,
                    measure_stats={"activation_p99": cf.get("activation_p99"),
                                   "activation_mean": cf.get("activation_mean"),
                                   "activation_std": cf.get("activation_std")},
                    hook_factory=lambda s=sae, i=idx, m=mag_abs:
                        _make_residual_add_decoder_hook(s, i, m, token_position, config))

    elif control_name == "negative_steering":
        sae = _get_sae(config, layer); idx = target["feature_index"]
        mag_abs, mag_rel, _ = _primary_magnitude(config, target)
        neg_abs = -mag_abs
        neg_rel = (-mag_rel if mag_rel is not None else None)
        neg_key = (f"rel:{neg_rel}" if neg_rel is not None else f"abs:-{abs(mag_abs)}")
        plan.update(magnitude=neg_abs, mag_rel=neg_rel, mag_key=neg_key, measure_sae=sae,
                    measure_index=idx, measure_stats=target_stats,
                    hook_factory=lambda s=sae, i=idx, m=neg_abs:
                        _make_residual_add_decoder_hook(s, i, m, token_position, config))

    elif control_name == "random_direction_same_norm":
        sae = _get_sae(config, layer); idx = target["feature_index"]
        norm = float(sae.W_dec[idx].norm().item()); d_model = int(sae.W_dec.shape[1])
        mag_abs, mag_rel, mag_key = _primary_magnitude(config, target)
        dseed = _derive_int_seed(seed, target["feature_uid"], control_name)
        hook, used_norm = _make_random_direction_hook(d_model, norm, mag_abs, token_position, dseed)
        plan["metadata"].update(random_direction_seed=dseed, target_decoder_norm=norm,
                                used_norm=used_norm)
        plan.update(magnitude=mag_abs, mag_rel=mag_rel, mag_key=mag_key, measure_sae=sae,
                    measure_index=idx, measure_stats=target_stats, hook_factory=lambda h=hook: h)

    elif control_name == "prompt_only":
        annotation = _prompt_only_annotation(run_id, model_run_id, target, config)
        plan.update(prompt_only=True, space="prompt_only", annotation=annotation,
                    magnitude=None, mag_rel=None, mag_key="prompt_only")
        plan["metadata"].update(
            annotation_source=ic.get("prompt_only_annotation_source", "morphorepr"),
            annotation=(annotation or "")[:200])
        try:
            plan["measure_sae"] = _get_sae(config, layer)
        except NotImplementedError:
            plan["measure_sae"] = None

    elif control_name in _UNIMPLEMENTED_CONTROLS:
        raise NotImplementedError(f"Contrôle '{control_name}' non implémenté en v6.9.0 (DiffMean/ReFT).")
    else:
        raise NotImplementedError(f"Contrôle inconnu : {control_name!r}.")
    return plan


def _run_control_for_target(conn, model, run_id, model_run_id, control_name, target,
                            probe_sets, gens, config) -> int:
    """Produit et insère les résultats d'UN contrôle pour UNE target. Renvoie le nb de lignes.
    Pour random_feature_same_layer / matched_activation_freq : on STEERE la control feature mais
    on RATTACHE le résultat à la target (control_feature_uid conservé)."""
    plan = _build_control_plan(run_id, model_run_id, control_name, target, config)
    if plan is None:
        return 0
    n = 0
    for family, category, sentences in probe_sets:
        for probe_id, sentence in enumerate(sentences, 1):
            for g in range(gens):
                try:
                    if plan["prompt_only"]:
                        text_before = _generate_text(model, sentence, config, hook_fn=None)
                        text_after  = _generate_text(model, _enrich_prompt(sentence, plan["annotation"]),
                                                      config, hook_fn=None)   # AUCUN hook de steering
                        a_before = a_after = achieved = None; ood = 0
                        if plan["measure_sae"] is not None:
                            toks = _tokens_from_prompt(model, sentence)
                            a_before = _measure_feature_activation(model, plan["measure_sae"], toks,
                                                                   plan["measure_index"], config)
                    else:
                        sae = plan["measure_sae"]; hname = _get_hook_name_from_sae(sae, config)
                        hook = plan["hook_factory"]()
                        toks = _tokens_from_prompt(model, sentence)
                        text_before = _generate_text(model, sentence, config, hook_fn=None)
                        a_before = _measure_feature_activation(model, sae, toks, plan["measure_index"],
                                                               config, hook_fn=None, hook_name=hname)
                        text_after = _generate_text(model, sentence, config, hook_fn=(hname, hook))
                        a_after = _measure_feature_activation(model, sae, toks, plan["measure_index"],
                                                              config, hook_fn=hook, hook_name=hname)
                        achieved = a_after - a_before
                        ood = _is_ood(a_after, a_before, plan["measure_stats"], config)
                except NotImplementedError:
                    raise
                except Exception as e:
                    logger.warning(f"Erreur contrôle {control_name} target {target['feature_uid']} "
                                   f"probe {probe_id}: {e}")
                    continue
                if _insert_intervention_control_result(
                        conn, run_id, model_run_id, target, control_name, plan["control_feat"],
                        plan["space"], plan["magnitude"], plan["mag_rel"], plan["mag_key"],
                        family, category, probe_id, g, text_before, text_after,
                        a_before, a_after, achieved, ood, plan["metadata"]):
                    n += 1
    return n


def assert_intervention_controls_ready(run_id: str, config: dict) -> None:
    """Garde DB-only : prédictions MorphoRepr + steering_results PRIMAIRES présents (modèle et
    split primaires). steer_feature lui-même est vérifié séparément via assert_steering_ready
    (appelé dans run_intervention_controls). Lève RuntimeError sinon."""
    from utils.db_utils import get_conn
    model_run_id = _primary_model_run_id(run_id, config)
    split = config.get("primary_split", "random")
    st = config["steering"]; space = st.get("intervention_space", "residual_add_decoder")
    mag_key = _primary_magnitude_key(config)
    accepted = ("predictor", "predictor_morphorepr")
    ph = ",".join("?" for _ in accepted)
    with get_conn() as conn:
        n_pred = conn.execute(f"""
            SELECT COUNT(DISTINCT ao.feature_uid) FROM agent_outputs ao
            JOIN features f ON f.feature_uid=ao.feature_uid
            WHERE ao.run_id=? AND ao.model_run_id=? AND ao.status='ok'
              AND ao.agent_name IN ({ph}) AND f.split=?
        """, (run_id, model_run_id, *accepted, split)).fetchone()[0]
        if n_pred == 0:
            raise RuntimeError(
                f"Contrôles : aucune prédiction MorphoRepr (agent ∈ {accepted}) pour "
                f"model_run_id={model_run_id}, split={split}. Lancer le predictor d'abord.")
        n_steer = conn.execute("""
            SELECT COUNT(*) FROM steering_results sr JOIN features f ON f.feature_uid=sr.feature_uid
            WHERE sr.run_id=? AND sr.model_run_id=? AND sr.magnitude_key=? AND sr.intervention_space=?
              AND f.split=? AND sr.text_after IS NOT NULL
        """, (run_id, model_run_id, mag_key, space, split)).fetchone()[0]
        if n_steer == 0:
            raise RuntimeError(
                f"Contrôles : aucun steering_results primaire (magnitude_key={mag_key}, space={space}) "
                f"pour model_run_id={model_run_id}, split={split}. Lancer steerer.run() d'abord.")


def run_intervention_controls(run_id: str, config: dict):
    """Phase 4 — CONTRÔLES D'INTERVENTION (v6.9.0). IMPLÉMENTÉ pour random_feature_same_layer,
    matched_activation_freq, random_direction_same_norm, negative_steering, prompt_only. Résultats
    dans intervention_control_results (JAMAIS steering_results). Métriques SECONDAIRES uniquement
    (jamais le score primaire). Désactivé par défaut (run_in_pipeline=false) → no-op. Un contrôle
    activé mais non implémenté (diffmean_reft) lève NotImplementedError AVANT toute génération."""
    ic = config.get("intervention_controls", {})
    if not ic.get("run_in_pipeline", False):
        logger.warning("p4_controls désactivé (intervention_controls.run_in_pipeline=false) — ignoré.")
        return {"status": "disabled"}

    controls = _controls_to_run(config)
    for c in controls:                          # échouer AVANT toute génération si non implémenté/inconnu
        if c in _UNIMPLEMENTED_CONTROLS:
            raise NotImplementedError(
                f"Contrôle '{c}' activé mais NON implémenté en v6.9.0 (baseline supervisée "
                f"DiffMean/ReFT). Le retirer de controls_to_run ou l'implémenter (pas de version factice).")
        if c not in _IMPLEMENTED_CONTROLS:
            raise NotImplementedError(f"Contrôle inconnu : {c!r}.")

    from utils.db_utils import get_conn
    model = _get_model(config)
    assert_steering_ready(config)                        # steer_feature réellement opérationnel (Règle 9)
    assert_intervention_controls_ready(run_id, config)   # prédictions MorphoRepr + steering primaire présents
    model_run_id = _primary_model_run_id(run_id, config)
    split = config.get("primary_split", "random")
    gens = config["steering"].get("generations_per_probe", 1)
    run_mode = config.get("run_mode", "full")
    n_neutral = (config["steering"].get("n_probe_sentences_pilot", config["steering"]["n_probe_sentences"])
                 if run_mode in ("dev", "pilot") else config["steering"]["n_probe_sentences"])
    probe_sets = [("neutral", None, load_probe_sentences(n_neutral, family="neutral"))]
    targets = _load_control_targets(run_id, model_run_id, split)

    summary = {}
    with get_conn() as conn:
        for control_name in controls:
            rows = 0
            for target in targets:
                if _control_rows_exist(conn, run_id, model_run_id, target["feature_uid"], control_name):
                    continue                     # reprise idempotente
                rows += _run_control_for_target(conn, model, run_id, model_run_id, control_name,
                                                target, probe_sets, gens, config)
            summary[control_name] = {"targets": len(targets), "rows": rows}
            logger.info(f"Contrôle {control_name} : {rows} lignes pour {len(targets)} targets.")

    scores = None
    if ic.get("score_controls", True):
        from agents import causal_scorer
        scores = causal_scorer.score_intervention_controls(run_id, config)
    logger.info("Phase 4 contrôles d'intervention terminée.")
    return {"status": "ok", "controls": summary, "scores": scores}
