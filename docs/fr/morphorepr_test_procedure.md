# MorphoRepr — Procédure de test complète (v6.8.0)
## Infrastructure expérimentale robuste pour une évaluation reproductible

*Version 6.8.0 — Juin 2026. Cohérente avec l'article (≥ v0.29). **Prédictions baselines (Option B)** pour `nl_labels` et `semantic_regex` : nouveau module `agents/baseline_predictor.py` qui produit des `agent_outputs` de prédiction de directions au format canonique (agent_name `predictor_nl_labels` / `predictor_semantic_regex`) à partir des annotations de la table `baselines`, via le provider primaire (Règle 11) et des **prompts séparés** (aucune terminologie MorphoRepr). Le steering n'est **pas** refait : seul le chemin de prédiction diffère, ce qui rend les **comparaisons appariées primaires** exécutables en dev run contrôlé — supériorité vs NL, non-infériorité vs Semantic Regexes. `causal_scorer.run()` calcule désormais, sous `run_baseline_comparisons=true`, le score propre de chaque baseline, la différence appariée, le verdict et la **couverture**, avec une garde `assert_baseline_predictions_ready` (strict → `RuntimeError` ; sinon skip **sans verdict** ; jamais de faux `pass`/`fail`). `keyword_tags` et `morphorepr_shuffled` restent **non branchées**. Aucun juge LLM dans le primaire. Aucun changement de schéma vs v6.5.3 (`metrics.model_run_id` renseigné pour toute métrique model-specific). `_load_pairs()` MorphoRepr (v6.7.0), couche multi-modèle et `steer_feature()` intacts ; `run_intervention_controls()` reste un contrat ; `causal_scoring.run_in_pipeline` et `baseline_predictions.enabled` restent `false` (non auto-activés). **Aucun full scientific result revendiqué.** Voir Section 27.*

---

## Principes directeurs

**Règle 1 — Séparation des rôles ; run gelé et auditable**
Claude Code sert au développement, au débogage et à la supervision uniquement. Le run expérimental final est piloté exclusivement par `python orchestrator.py --config configs/run_v1.yaml`. Le run est **gelé et auditable** plutôt que strictement déterministe : le code, la configuration, les prompts, le corpus et le lexique sont figés et vérifiés par empreinte (hash), et toutes les sorties brutes des agents sont archivées. En revanche les sorties des appels LLM sont **stochastiques** (et le sont nécessairement pour les deux runs de cohérence d'annotation) ; le run est donc *ré-analysable* à partir des sorties archivées, sans être *régénérable* à l'identique. Aucune modification de code ni intervention agentique non tracée pendant l'exécution.

**Règle 2 — Trois niveaux d'exécution**

| Mode | n features | Objectif | Résultats |
|------|-----------|-----------|---------|
| Dev run | 5 | Plomberie, DB, parsing, batch, classifieurs | Non scientifiques |
| Pilot run | 30–50 | Calibration prompts, seuils, classifieurs | Exploratoires |
| Full frozen run | 500 | Publication | Gelés avant lancement |

Si les seuils ou prompts sont ajustés après observation des résultats du pilot run, le déclarer explicitement comme calibration dans le papier.

**Règle 3 — Gel complet avant full run**
Commit Git fixé et vérifié, config hashée, prompts hashés (SHA256 complet), corpus hashé, lexique hashé, politique de sampling documentée. En cas de `--resume`, toutes ces valeurs sont revérifiées avant reprise.

**Règle 4 — Pas de reprise après modification de code**
Si le code est modifié après un échec de phase, créer un nouveau run_id avec un nouveau commit Git. Ne jamais reprendre un run avec un commit différent de celui enregistré à l'initialisation.

**Règle 5 — Modèle de validation : proxy open-weight par défaut**
L'accès expérimental complet aux activations d'un modèle de production (steering contrôlé avec génération avant/après) n'étant pas garanti par les interfaces publiques, la validation causale s'exécute **par défaut sur un modèle proxy open-weight disposant de SAEs publics** (ex. GPT-2, Pythia ou Mistral via `sae_lens`). Dans ce cas : (a) le pipeline entier (Phases 1–5) opère sur les SAEs du proxy ; (b) toutes les conclusions causales sont limitées au modèle proxy ; (c) les exemples Claude 3 Sonnet / Neuronpedia restent illustratifs uniquement ; (d) cela doit être déclaré explicitement dans la section Méthodes du papier. Si un accès direct aux activations d'un modèle de production est obtenu, mettre `proxy_model.enabled=false` et fournir les chemins d'accès correspondants.

**Règle 6 — Steering normalisé par feature, à la couche du feature**
La magnitude de steering primaire est **normalisée par feature** (un multiple du 99e percentile d'activation du feature, colonne `activation_p99`), ce qui la rend comparable entre features et couches ; la magnitude absolue historique (+5) est conservée comme condition secondaire. Le steering cible la **couche propre du feature** (colonne `layer`), non une couche globale. Les instances poussées hors-distribution (`ood_flag=1`) sont **exclues de la métrique primaire** et rapportées séparément.

**Règle 7 — Comparaison sur ensemble partagé ET utilité globale**
Le tête-à-tête de validité causale (MorphoRepr vs étiquettes NL vs Semantic Regexes) est calculé **sur le même ensemble de features** — l'intersection des features couverts par MorphoRepr (confiance ≥ 0,5) : c'est la **performance conditionnelle**. Comme cela ne dit rien de l'utilité si la couverture diffère fortement, on rapporte **systématiquement** aussi l'**utilité globale (end-to-end)** sur le random set complet (`couverture × score causal moyen`, ou score intégré avec UNCOVERED = abstention/score nul, règle pré-enregistrée). Le score de validité causale primaire est un **macro-F1 calculé globalement sur l'ensemble des couples (feature, propriété robuste)** ; le critère est la **supériorité** vs NL (IC de la différence appariée excluant 0) et la **non-infériorité** vs Semantic Regexes (borne basse de l'IC > −δ, marge `nim_delta` pré-enregistrée).

**Règle 8 — Métrique primaire déterministe (sans juge LLM)**
La comparaison prédiction/observation de la métrique primaire est **déterministe** : la direction prédite par l'agent de prédiction est comparée par **code** à la direction mesurée par les **classifieurs pré-enregistrés**. Aucun juge LLM n'intervient dans la métrique primaire. Un juge LLM (`qualitative_judge`) est réservé aux analyses qualitatives, cas ambigus et audit assisté (métriques secondaires). Le bootstrap est **clusterisé par feature** (l'unité de rééchantillonnage est la feature, pas le couple feature-propriété).

**Règle 9 — La Phase 4 reste gardée tant qu'un dev run ne l'a pas validée**
`steer_feature()` est **implémenté pour le chemin proxy open-weight** (TransformerLens + SAE Lens, `residual_add_decoder`) ; les chemins nnsight / modèle de production et l'espace `sae_latent_clamp` lèvent `NotImplementedError`. Le pilot run **ne peut être lancé** que lorsque, sur un dev run de ≥ 5 features (`proxy_model.enabled=true`), `steer_feature()` produit réellement : `text_before`, `text_after`, `activation_before`, `activation_after`, le `delta` d'activation obtenu, et un `ood_flag` vérifiable (Section 7, garde `assert_steering_ready`). `causal_scorer._load_pairs()` est **implémenté** (assemblage déterministe prédiction/observation, métrique primaire, model/split/OOD-aware — Sections 8 et 27) ; `run_intervention_controls()` reste un contrat. La Phase 4 n'est pas scientifiquement validée (comparaisons baselines désactivées par défaut, `causal_scoring.run_in_pipeline=false`).

**Règle 10 — Identité de feature robuste**
Un `feature_index` seul ne suffit pas : le même index peut exister dans plusieurs couches, releases SAE ou modèles. L'identité canonique est `feature_uid = {model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}`, avec contrainte d'unicité. Au sein d'un run unique (un modèle, une release, un ensemble de couches), `feature_index` reste un identifiant pratique pour les jointures ; `feature_uid` garantit l'unicité cross-couche/cross-SAE et est propagé aux tables aval.

**Règle 11 — Reproductibilité par modèles ouverts**
Les conclusions scientifiques principales ne doivent pas dépendre uniquement d'un modèle propriétaire accessible par API. Le protocole distingue trois tiers de fournisseurs :

1. **Tier A — Fully open / reproducible model.** Poids, tokenizer, code d'inférence, configuration, hyperparamètres, licence et (autant que possible) informations sur les données d'entraînement sont documentés et archivables.
2. **Tier B — Open-weight model.** Poids et tokenizer publiquement disponibles, mais données ou certains détails de pré-entraînement non entièrement ouverts. Acceptable pour la **reproductibilité computationnelle** si les révisions exactes, hashes et paramètres d'inférence sont archivés.
3. **Tier C — Proprietary API model.** Accessible uniquement par API propriétaire. Utilisable pour **comparaison, développement, annotation assistée ou analyse secondaire**, mais **jamais comme seule base des conclusions principales**.

**Règle** : toute conclusion principale du papier doit être rapportée **au minimum sur un modèle Tier A ou Tier B**. Les résultats Anthropic (ou tout autre fournisseur propriétaire) sont présentés comme résultats **secondaires, de robustesse ou de comparaison externe**. Une affirmation forte (ex. « MorphoRepr outperforms natural language labels ») n'est admissible que si elle est vraie sur le **modèle primaire open-weight** ; si elle ne vaut que sur un modèle propriétaire, elle doit être reformulée en « in the proprietary reference condition ». Les agents ne doivent **jamais** instancier `anthropic.Anthropic()` directement : ils dépendent de l'abstraction `ModelProvider` (Section 5 bis) afin que le même protocole tourne avec Anthropic **ou** un modèle local.

**Règle 11 bis — Liste de modèles gelée par run.** Les noms de modèles donnés en exemple dans `model_providers` ne sont qu'illustratifs. Le **full frozen run** doit figer une liste **exacte** de modèles réellement disponibles, compatibles avec la licence de recherche et exécutables par le laboratoire. Toute substitution de modèle après le gel exige un **nouveau `run_id`**.

---

## Politique d'ouverture des modèles et reproductibilité (Model openness and reproducibility policy)

**Pourquoi un modèle propriétaire seul ne suffit pas.** Un modèle accessible uniquement par API peut être mis à jour, déprécié ou retiré sans préavis, sans accès aux poids, au tokenizer, aux données ni aux paramètres internes. Une conclusion scientifique qui n'existe que derrière une telle API n'est pas vérifiable indépendamment ni rejouable dans le temps : elle dépend d'un artefact non archivable. La reproductibilité exige donc qu'au moins une condition repose sur un modèle dont l'artefact exact peut être figé et redistribué.

**Pourquoi les résultats primaires doivent venir d'un modèle ouvert.** Pour qu'un autre laboratoire puisse rejouer l'expérience et obtenir (aux variations matérielles près) les mêmes nombres, il faut un modèle dont la révision, le tokenizer, le backend et les paramètres d'inférence sont connus et archivés. Les **claims primaires** de MorphoRepr sont donc calculés sur un modèle **Tier A (fully open)** ou **Tier B (open-weight)** ; les résultats propriétaires servent de **comparaison externe**.

**Distinguer open-source, open-weight et proprietary API.**
- *Open-source / fully open (Tier A)* : poids + tokenizer + code d'inférence + config + hyperparamètres + licence + (idéalement) infos données. Reproductible au sens le plus fort.
- *Open-weight (Tier B)* : poids + tokenizer publics, mais données/pré-entraînement partiellement fermés. Reproductible **computationnellement** (mêmes poids → mêmes sorties à backend/seed fixés), pas nécessairement scientifiquement transparent sur l'origine.
- *Proprietary API (Tier C)* : ni poids ni tokenizer ; comportement potentiellement variable. Comparaison/secondaire uniquement.

**Reporter séparément Tier A/B et Tier C.** Les métriques sont rapportées **par modèle et par tier** (Section de reporting). Le tableau principal oppose explicitement le modèle ouvert primaire au modèle propriétaire secondaire, avec la différence et son interprétation. On ne fusionne jamais un score Tier C dans un score « primaire ».

**Éviter l'open-washing.** On n'appelle **pas** « open source » un modèle qui ne fournit que les poids sans données, code ou configuration suffisants : un tel modèle est *open-weight* (Tier B), et désigné comme tel. Le tier déclaré dans `model_runs.provider_tier` doit refléter ce qui est réellement disponible, pas le marketing du fournisseur.

**Artefacts à archiver pour la reproduction.** Pour chaque `model_run` : révision exacte du modèle et du tokenizer, `weights_sha256`, `tokenizer_sha256`, image Docker/Conda (`inference_env_hash`), version CUDA, version du backend, `precision`/`quantization`, paramètres d'inférence (`generation_params_json` : température, top_p, seed, max_new_tokens), prompts (hashés, Règle 3) et **sorties brutes**. Sans ces artefacts, un run ne peut pas prétendre à la reproductibilité et ne peut pas porter de claim primaire (garde `validate_model_providers`, Section 5 bis).

**README — section à mettre à jour.** Le README doit désormais pointer le papier **v0.29** et la procédure **v6.8.0**, et **supprimer** les références obsolètes (papier v0.26 / `paper_v0.26.pdf`, ancien critère go/no-go par « IC non chevauchants » — remplacé dès la v0.27 par supériorité vs NL via IC de la différence appariée excluant 0 et non-infériorité vs Semantic Regexes). Section à inclure :

```markdown
## MorphoRepr — état du dépôt
- Article : v0.29 (politique de modèles ouverts ; claims primaires sur modèle ouvert).
- Procédure de test : v6.8.0 (prédictions baselines Option B nl_labels/semantic_regex câblées pour dev run ; Phase 4 désactivée par défaut).
- Critère de validité causale : supériorité vs étiquettes NL (IC de la différence appariée,
  clusterisé par feature, excluant 0) ET non-infériorité vs Semantic Regexes (marge δ
  pré-enregistrée). NB : l'ancien critère « IC non chevauchants » est OBSOLÈTE.

## Reproducibility and open-weight models
- MorphoRepr may use proprietary models (e.g. Anthropic) for development and secondary comparison.
- Primary scientific claims are designed to be reproducible with open-weight or fully open models.
- The protocol archives exact model revisions, hashes, inference backends, prompts, configurations,
  and raw outputs (table `model_runs` + `model_run_id` propagated to batches/outputs/baselines/
  api_usage/steering_results; aggregated metrics may be cross-model).
- Inference goes through `ModelProvider` (open primary model); `api_utils` is a LEGACY Anthropic
  Batch wrapper for the Tier C secondary condition only.
- Anthropic results are reported as a secondary reference condition unless explicitly reproduced
  by an open-weight model. Strong claims ("MorphoRepr outperforms NL labels") require the open
  primary model; otherwise they are phrased "in the proprietary reference condition".
- Primary claims are restricted to Tier A/B models (guard `assert_primary_claim_allowed`).
```

---

## 1. Structure du projet

```
morphorepr-pipeline/
├── CLAUDE.md                        ← instructions Claude Code (dev/supervision uniquement)
├── configs/
│   ├── dev_run.yaml
│   ├── pilot_run.yaml
│   └── run_v1.yaml                  ← config gelée full run
├── db/
│   ├── schema.sql
│   ├── features.db
│   └── lexicon.json
├── prompts/
│   ├── label_agent_v1.txt
│   ├── encoder_agent_v1.txt
│   ├── predictor_agent_v1.txt
│   ├── predictor_nl_labels_v1.txt      ← prédicteur baseline NL (Option B, v6.8.0)
│   ├── predictor_semantic_regex_v1.txt ← prédicteur baseline Semantic Regex (Option B, v6.8.0)
│   ├── fidelity_judge_v1.txt
│   └── causal_judge_v1.txt
├── agents/
│   ├── loader.py
│   ├── ranker.py
│   ├── cluster.py
│   ├── labeler.py
│   ├── consistency.py
│   ├── encoder.py
│   ├── fidelity.py
│   ├── steerer.py                   ← spécifié complètement en Section 7
│   ├── predictor.py
│   ├── baseline_predictor.py        ← prédictions baselines NL / Semantic Regex (Option B, §8 bis)
│   ├── causal_scorer.py             ← score causal déterministe + _load_pairs (§8)
│   ├── judge.py
│   └── reporter.py
├── classifiers/
│   ├── negation.py
│   ├── tense.py
│   ├── code_presence.py
│   ├── modality.py
│   ├── valence.py
│   └── calibration/
│       ├── negation_test.json
│       ├── tense_test.json
│       ├── code_presence_test.json
│       ├── modality_test.json
│       ├── valence_test.json
│       └── run_calibration.py
├── baselines/
│   ├── nl_labels.py
│   ├── semantic_regex.py
│   ├── keyword_tags.py
│   └── shuffled.py
├── utils/
│   ├── db_utils.py
│   ├── api_utils.py                 ← LEGACY wrapper Batch API Anthropic (Tier C secondaire)
│   ├── model_provider.py            ← abstraction ModelProvider (primaire ouvert + Anthropic)
│   ├── model_policy.py              ← gardes Règle 11 (tiers, claim primaire, cross-modèle)
│   ├── prompt_utils.py
│   ├── config_utils.py
│   ├── morphorepr_parser.py         ← parseur unique pour toutes les métriques
│   └── stats_utils.py
├── tests/
│   ├── conftest.py
│   ├── test_parser.py
│   ├── test_schema.py
│   ├── test_db.py
│   ├── test_classifiers.py
│   ├── test_shuffle_baseline.py
│   ├── test_batch_custom_id.py
│   ├── test_model_providers.py      ← Règle 11 (tiers, gardes, cross-modèle)
│   ├── test_model_run_propagation.py ← propagation effective de model_run_id (+ Phase 4 model-aware)
│   ├── test_steer_feature.py        ← steer_feature (chemin proxy open-weight, durci v6.6.1)
│   ├── test_causal_scorer.py        ← scoring causal + _load_pairs (assemblage prédiction/observation, v6.7.0)
│   ├── test_baseline_predictions.py ← prédictions baselines Option B (nl_labels, semantic_regex, v6.8.0)
│   └── test_pipeline_e2e.py
├── orchestrator.py
├── requirements.txt
├── data/
│   └── probes/                      ← une famille/catégorie de sondes par fichier
│       ├── probes_neutral.txt       ← sondes neutres (≥50 pour le primaire, 20 pilot)
│       ├── probes_code.txt          ← sondes compatibles "code"
│       ├── probes_social.txt        ← sondes compatibles "social"
│       ├── probes_temporal.txt      ← sondes compatibles "temporal"
│       ├── probes_spatial.txt       ← sondes compatibles "spatial"
│       ├── probes_affect.txt        ← sondes compatibles "affect"
│       └── probes_data.txt          ← sondes compatibles "data"
├── logs/
└── checkpoints/
```

---

## 2. Fichier de configuration gelé

```yaml
# configs/run_v1.yaml

run_id_prefix: "morphorepr_v1"
description: "Full frozen run MorphoRepr v0.29 / procedure v6.8.0 — 500 features"

# Reproductibilité
git_commit: "FILL_BEFORE_LAUNCH"    # vérifié contre le HEAD Git réel à l'init
allow_unpinned_commit: false        # run gelé : le commit DOIT être épinglé (cf. orchestrator)
lexicon_version: "v1.0"
corpus_frozen: true

# Politique de sampling
# temperature n'est PAS envoyée à l'API par défaut pour éviter les HTTP 400
# sur les modèles récents qui rejettent les paramètres de sampling non par défaut.
# Documenté ici pour le papier ; non transmis sauf si use_temperature: true.
sampling:
  use_temperature: false
  temperature: null

# Modèles (identifiants exacts API Anthropic) — conservés pour la condition propriétaire
# SECONDAIRE et les outils d'assistance. NE PAS utiliser comme seule base des claims primaires.
models:
  semantic_judgment: "claude-sonnet-4-6"
  scoring: "claude-haiku-4-5-20251001"
  batch: true
  max_tokens_judgment: 800
  max_tokens_scoring: 400

# ─────────────────────────────────────────────
# Reproductibilité par modèles ouverts (Règle 11). Les agents passent par ModelProvider
# (Section 5 bis), jamais par anthropic.Anthropic() directement. Les claims PRIMAIRES sont
# calculés sur primary_reproducible (Tier A/B) ; Anthropic est SECONDAIRE.
# NB : les model_name ci-dessous sont des EXEMPLES (Règle 11 bis) ; le full frozen run doit
# figer une liste exacte de modèles réellement disponibles et licenciés pour la recherche.
# ─────────────────────────────────────────────
model_providers:
  primary_reproducible:
    tier: "B_open_weight"
    provider: "local"
    backend: "vllm"                 # "vllm" | "transformers" | "llama_cpp"
    model_name: "Qwen/Qwen3-8B-Instruct"
    model_revision: "FILL_EXACT_HF_REVISION"
    tokenizer_revision: "FILL_EXACT_HF_REVISION"
    weights_sha256: "FILL_BEFORE_FULL_RUN"
    tokenizer_sha256: "FILL_BEFORE_FULL_RUN"
    license: "FILL"
    precision: "bfloat16"
    quantization: null
    inference_container_hash: "FILL_BEFORE_FULL_RUN"
    deterministic_generation:
      temperature: 0.0
      top_p: 1.0
      seed: 42
      max_new_tokens: 512

  secondary_proprietary:
    tier: "C_proprietary_api"
    provider: "anthropic"
    model_name: "claude-sonnet-4-6"
    api_version: "FILL"
    role: "secondary_reference"
    use_for_primary_claims: false

  optional_cross_model_replication:
    enabled: true
    models:
      - provider: "local"
        tier: "B_open_weight"
        backend: "vllm"
        model_name: "mistralai/Mistral-7B-Instruct-v0.3"
        model_revision: "FILL"
        role: "replication"
      - provider: "local"
        tier: "B_open_weight"
        backend: "vllm"
        model_name: "meta-llama/Llama-3.1-8B-Instruct"
        model_revision: "FILL"
        role: "replication"
      - provider: "local"
        tier: "A_or_B_open"
        backend: "transformers"
        model_name: "allenai/OLMo-2-1124-7B-Instruct"
        model_revision: "FILL"
        role: "replication"

# Prompts
prompts:
  label_agent:    "prompts/label_agent_v1.txt"
  encoder:        "prompts/encoder_agent_v1.txt"
  predictor:      "prompts/predictor_agent_v1.txt"
  predictor_nl_labels:      "prompts/predictor_nl_labels_v1.txt"       # baseline NL (Option B, v6.8.0)
  predictor_semantic_regex: "prompts/predictor_semantic_regex_v1.txt"  # baseline Semantic Regex (Option B)
  fidelity_judge: "prompts/fidelity_judge_v1.txt"
  causal_judge:   "prompts/causal_judge_v1.txt"

# Splits du corpus (DISJOINTS). ORDRE D'ÉCHANTILLONNAGE : random EN PREMIER, uniformément
# sur l'ensemble des features, puis retiré du pool ; easy/hard ensuite dans le reste.
# Ainsi le random reste représentatif (et non un "middle set").
splits:
  sampling_order: ["random", "easy", "hard"]   # random échantillonné AVANT easy/hard
  random: {n: 200, filter: "uniform"}           # uniforme sur TOUT le corpus, en premier
  easy:   {n: 200, min_interp_score: 0.7}       # dans le pool restant
  hard:   {n: 100, max_interp_score: 0.5}       # dans le pool restant
primary_split: "random"              # tous les seuils go/no-go évalués ici

# Clustering (Phase 2) — graines fixées pour la reproductibilité de l'induction du lexique
clustering:
  k: 20
  kmeans_random_state: 42
  umap_random_state: 42

# Steering SAE
steering:
  # `steer_feature()` est IMPLÉMENTÉ pour le chemin proxy open-weight (TransformerLens + SAE
  # Lens, Section 7), et `causal_scorer._load_pairs()` + les prédictions baselines Option B
  # (nl_labels, semantic_regex) sont câblés. Phase 4 reste néanmoins DÉSACTIVÉE par défaut tant
  # que (a) `assert_steering_ready()` n'a pas été validé sur un dev run (proxy_model.enabled=true)
  # ET (b) les comparaisons baselines / contrôles d'intervention n'ont pas été exécutés dans un
  # dev run contrôlé (baseline_predictions.enabled + run_baseline_comparisons ; run_intervention_controls
  # reste un contrat). Passer à true UNIQUEMENT après (a).
  run_in_pipeline: false
  # Magnitude PRIMAIRE normalisée par feature : multiple du 99e percentile (activation_p99).
  # La magnitude absolue +5 (Anthropic, 2024) est conservée comme condition SECONDAIRE/historique.
  magnitude_mode: "p99_relative"     # "p99_relative" (primaire) | "absolute" (secondaire)
  primary_magnitude_rel: 1.0         # 1.0 × activation_p99 du feature (magnitude VISÉE)
  dose_response_rel: [0.0, 0.5, 1.0, 2.0]   # courbe dose-réponse (multiples de p99)
  legacy_absolute_magnitude: 5       # condition secondaire historique
  # Espace d'intervention : ajouter au résiduel un multiple du décodeur NE GARANTIT PAS
  # une hausse de l'activation latente du même facteur. On rapporte donc le DELTA OBTENU
  # (achieved_delta), pas seulement la magnitude visée, et on supporte deux modes :
  intervention_space: "residual_add_decoder"  # "residual_add_decoder" | "sae_latent_clamp"
  n_probe_sentences: 50              # métrique PRIMAIRE (n_probe_sentences_pilot en dev/pilot)
  n_probe_sentences_pilot: 20        # utilisé si run_mode ∈ {dev, pilot} (cf. run_mode global)
  n_domain_probes_per_category: 20   # sondes compatibles par catégorie de domaine
  # PRIMAIRE déterministe : 1 génération + décodage greedy (temperature=0). Pour amortir la
  # stochasticité, utiliser stochastic_decoding (analyse SECONDAIRE) plutôt que de multiplier
  # les générations en greedy (qui seraient identiques).
  generations_per_probe: 1
  decoding:
    temperature: 0.0                 # greedy déterministe ; rapporté dans le papier
    max_new_tokens: 64
    archive_generation_params: true  # paramètres exacts archivés avec les sorties
  # Volumétrie maîtrisée (Section 6) : les sondes domaine sont une analyse SECONDAIRE par
  # défaut (ventilées par catégorie), PAS dans le score primaire.
  primary_probe_family: "neutral"
  use_domain_probes_in_primary: false
  domain_probes_as_secondary: true
  # Deux familles de sondes (pré-enregistrées ; les compatibles NE doivent PAS donner la réponse)
  probe_families: ["neutral", "domain_compatible"]
  domain_probe_categories: ["code", "social", "temporal", "spatial", "affect", "data"]
  n_subsample_for_curve: 50          # sous-échantillon seedé pour la dose-réponse
  layer_mode: "per_feature"          # cible la couche propre du feature (colonne `layer`)
  token_position: "all"              # "all"|"last"|"content_only"
  # OOD : critère MIXTE pré-enregistré (robuste aux p99 faibles / distributions asymétriques).
  # OOD si activation_after > max(p99·tau, mean + k·std, epsilon)  OU
  #        |activation_after - activation_before| > delta_max · p99
  ood_tau: 3.0
  ood_k: 4.0
  ood_epsilon: 1.0e-3
  ood_delta_max: 5.0
  exclude_ood_from_primary: true     # instances ood_flag=1 exclues de la métrique primaire

# Décodage stochastique — analyse SECONDAIRE uniquement (amortir la stochasticité).
# Le PRIMAIRE reste greedy déterministe (steering.decoding.temperature=0, 1 génération).
stochastic_decoding:
  enabled: false
  temperature: 0.7
  generations_per_probe: 3

# Mode d'exécution : ajuste la volumétrie des sondes (dev/pilot → n_probe_sentences_pilot).
run_mode: "full"                     # "dev" | "pilot" | "full"

# Scoring causal (Phase 4) — métrique primaire déterministe. `causal_scorer._load_pairs()` est
# IMPLÉMENTÉ (assemblage prédiction/observation, model-aware, split-aware, OOD-aware). Le scoring
# reste DÉSACTIVÉ par défaut (`run_in_pipeline=false`) ; il gère p4_predict, p4_score ET
# p4_qualitative (sans prédictions ni steering, ces phases n'ont pas de matière). Les prédictions
# baselines (Option B, v6.8.0) sont câblées pour nl_labels et semantic_regex (module
# baseline_predictor) ; les comparaisons appariées restent gardées par run_baseline_comparisons.
causal_scoring:
  run_in_pipeline: false
  run_baseline_comparisons: false    # true uniquement si les prédictions baselines existent (Option B)
  strict_baselines: true             # true → une baseline demandée mais absente lève RuntimeError ;
                                     # false → skip explicite SANS verdict (jamais de faux pass/fail)

# Prédictions BASELINES (Option B, v6.8.0). Produit des agent_outputs de prédiction de directions
# pour les baselines, au MÊME format que MorphoRepr (agent_name predictor_<méthode>), à partir des
# annotations de la table `baselines`. Désactivé par défaut ; en full run, ne pas activer sans gel
# des prompts/hashes. Seules nl_labels et semantic_regex sont branchées en v6.8.0.
baseline_predictions:
  enabled: false
  methods:
    - nl_labels
    - semantic_regex
  run_number: 1
  require_existing_baseline_annotations: true   # pas d'annotation baseline → erreur (jamais fabriquée)
  skip_missing_annotations: false               # true → features sans annotation ignorées (log), sans erreur

# Modèle de validation — proxy open-weight PAR DÉFAUT (Règle 5).
# Mettre enabled=false uniquement si un accès direct aux activations d'un modèle
# de production est obtenu (fournir alors les chemins d'accès dans agents/steerer.py).
proxy_model:
  enabled: true
  name: "EleutherAI/pythia-6.9b"
  sae_release: "pythia-6.9b-res-jb"

# Baselines d'ANNOTATION (comparées sur ensemble de features partagé — Règle 7)
baselines:
  - nl_labels
  - semantic_regex        # implémentation OFFICIELLE de Boggust et al. (apple/ml-semantic-regex)
  - keyword_tags
  - morphorepr_shuffled

# Contrôles d'INTERVENTION (Phase 4) — au-delà du contrôle d'annotation mélangé
intervention_controls:
  # Désactivé par défaut : la phase p4_controls est un CONTRAT non implémenté (Section 7).
  # Passer à true UNIQUEMENT une fois run_intervention_controls() réellement implémenté.
  run_in_pipeline: false
  random_feature_same_layer: true    # feature SAE aléatoire de même couche
  random_direction_same_norm: true   # direction aléatoire de même norme
  matched_activation_freq: true      # feature à fréquence d'activation comparable
  negative_steering: true            # -magnitude lorsque sémantiquement pertinent
  prompt_only: true                  # étiquette dans le prompt, sans steering
  diffmean_reft: true                # baselines supervisées DiffMean / ReFT (cf. AxBench)

# Contrôle mélangé
shuffle_control:
  n_repeats: 10
  within_split: true
  max_term_diff: 1
  preserve_coefficients: true
  # Le gros des shuffles est scoré par classifieurs (pas le juge LLM) pour borner le coût ;
  # mais une FRACTION passe par le MÊME chemin predictor+juge que le traitement, afin de
  # calibrer la comparabilité (sinon le "null" n'est pas comparable à la métrique principale).
  # La métrique primaire est DÉTERMINISTE (prédicteur + classifieurs, Règle 8) ; le contrôle
  # mélangé est scoré par CE MÊME chemin déterministe (scored_by='deterministic'). Une FRACTION
  # est en outre passée au juge LLM qualitatif (scored_by='llm_qualitative') pour audit seulement.
  use_llm_judge: false
  llm_qualitative_audit_fraction: 0.2
  # Généré et évalué sur evaluation_split UNIQUEMENT ; répétitions agrégées avant IC
  evaluation_split: "random"

# Budget
budget:
  max_cost_usd: 150.0                # mettre à jour après estimation pilot run
  alert_at_usd: 75.0
  abort_on_exceed: true
  estimate_before_submit: true       # estimer le coût d'un batch AVANT soumission (Section 5.2)

# Seuils go/no-go (random split uniquement)
thresholds:
  coverage_easy_min: 0.65
  coverage_random_min: 0.45
  coverage_hard_min: 0.20
  fidelity_auc_min: 0.60
  causal_validity_floor: 0.50        # plancher de macro-F1 global. Critères principaux :
                                     #  - vs NL : SUPÉRIORITÉ (IC de la diff appariée excluant 0)
                                     #  - vs Semantic Regexes : NON-INFÉRIORITÉ (borne basse > -nim_delta)
  nim_delta: 0.05                    # marge de non-infériorité pré-enregistrée (macro-F1)
  root_jaccard_min: 0.60
  human_audit_jaccard_min: 0.60
  free_root_rate_max: 5.0

# Méthodologie statistique
stats:
  causal_score: "macro_f1_global_pairs"   # macro-F1 GLOBAL sur tous les couples (feature, prop. robuste)
                                          # — PAS par feature puis moyenné (instable, trop peu de classes/feature)
  per_feature_macro_f1: "secondary"       # le score par feature reste rapporté en métrique secondaire
  comparison: "paired"                    # différence appariée (mêmes features)
  bootstrap_resamples: 10000
  bootstrap_cluster_unit: "feature"       # rééchantillonnage CLUSTERISÉ par feature
  stratify_by_split: true
  superiority_vs: ["nl_labels"]           # cibles évaluées en supériorité
  non_inferiority_vs: ["semantic_regex"]  # cibles évaluées en non-infériorité (marge nim_delta)
  end_to_end_utility: true                # rapporter couverture × score causal (+ score intégré)
  uncovered_policy: "abstention_or_zero"  # règle pré-enregistrée pour l'utilité end-to-end
  multiple_comparison_primary: "holm"            # Holm-Bonferroni (comparaisons principales)
  multiple_comparison_exploratory: "benjamini_hochberg"  # FDR (analyses exploratoires)
  prediction_failure_policy: "zero_for_property"  # échec de prédiction => score nul pour la propriété

# Batch API (Anthropic) — la plupart des batchs finissent < 1h, accessibles à la fin
# ou après 24h ; ils expirent à 24h. 2h était trop court (échec artificiel possible).
batch:
  poll_interval_seconds: 60
  max_wait_seconds: 86400

# Seed de reproductibilité (sélection du sous-échantillon, contrôle mélangé, clustering)
seed: 42
```

---

## 3. Schéma SQLite complet (v6.8.0)

```sql
-- db/schema.sql  —  Version 6.8.0 (aucun changement de schéma vs 6.5.3), ne jamais modifier après le full run

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────────
-- Traçabilité des runs
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    git_commit      TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    prompt_hashes   TEXT NOT NULL,    -- JSON {agent: sha256_complet}
    lexicon_version TEXT NOT NULL,
    lexicon_hash    TEXT NOT NULL,    -- SHA256 de l'export JSON canonique trié
    -- corpus_hash couvre uniquement la table features (données d'entrée),
    -- PAS les résultats ajoutés pendant le run. La DB croît légitimement.
    corpus_hash     TEXT,             -- SHA256 de l'export CSV canonique trié ; NULL tant que
                                      -- non gelé (gelé par p1_freeze_corpus après p1_load/p1_rank)
    models_json     TEXT NOT NULL,
    use_temperature INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,             -- NULL si use_temperature=0
    seed            INTEGER,
    proxy_model     TEXT,             -- NULL si modèle principal utilisé
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT DEFAULT 'running',
    last_phase      TEXT,
    total_cost_usd  REAL DEFAULT 0.0
);

-- ─────────────────────────────────────────────
-- Exécutions de modèles (Règle 11) : un model_run = un fournisseur/modèle/révision/env donné,
-- rattaché à un run. Permet d'exécuter et comparer plusieurs modèles sur les mêmes features et
-- d'archiver tous les artefacts de reproduction. is_primary_scientific=1 marque le modèle
-- ouvert primaire ; use_for_primary_claims contrôle l'admissibilité aux claims principaux.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id           TEXT PRIMARY KEY,
    run_id                 TEXT NOT NULL REFERENCES runs(run_id),
    provider_name          TEXT NOT NULL,
    provider_tier          TEXT NOT NULL,  -- A_fully_open | B_open_weight | C_proprietary_api
    backend                TEXT,           -- vllm | transformers | llama_cpp | anthropic_api | other
    model_name             TEXT NOT NULL,
    model_revision         TEXT,
    tokenizer_revision     TEXT,
    weights_sha256         TEXT,
    tokenizer_sha256       TEXT,
    inference_env_hash     TEXT,
    precision              TEXT,
    quantization           TEXT,
    license                TEXT,
    is_primary_scientific  INTEGER NOT NULL DEFAULT 0,
    use_for_primary_claims INTEGER NOT NULL DEFAULT 0,
    generation_params_json TEXT NOT NULL,
    created_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id        TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id    TEXT NOT NULL REFERENCES model_runs(model_run_id),  -- modèle du batch (Règle 11)
    phase           TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    run_number      INTEGER NOT NULL DEFAULT 1,
    n_requests      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'submitted',  -- submitted/consumed/failed
    submitted_at    TEXT NOT NULL,
    consumed_at     TEXT
);

-- Correspondance custom_id → feature_uid PERSISTÉE avec le batch (reprise crash-safe).
-- À la reprise, le batch peut contenir des custom_id de features déjà persistées (donc
-- absentes de load_features_not_processed) ; la map reconstruite en mémoire serait alors
-- incomplète. Cette table garantit qu'on retrouve toujours feature_uid pour chaque custom_id.
CREATE TABLE IF NOT EXISTS batch_items (
    batch_id        TEXT NOT NULL REFERENCES batches(batch_id),
    custom_id       TEXT NOT NULL,
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),
    feature_index   INTEGER NOT NULL,
    model_run_id    TEXT NOT NULL REFERENCES model_runs(model_run_id),  -- batch propre à un modèle (Règle 11)
    PRIMARY KEY(batch_id, custom_id)
);

-- ─────────────────────────────────────────────
-- Prompts versionnés
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id   TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    version     TEXT NOT NULL,
    content     TEXT NOT NULL,
    sha256      TEXT NOT NULL,        -- SHA256 complet, 64 caractères hex
    created_at  TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Corpus de features
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS features (
    -- Identité ROBUSTE : un feature_index seul est ambigu (même index possible sur
    -- plusieurs couches / releases SAE / modèles). feature_uid est l'identité canonique :
    --   feature_uid = '{model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}'
    feature_uid     TEXT PRIMARY KEY,
    model_name      TEXT NOT NULL,
    sae_release     TEXT NOT NULL,
    layer_index     INTEGER NOT NULL,   -- couche numérique (pour construire l'id SAE)
    hook_name       TEXT NOT NULL,      -- ex. 'hook_resid_post'
    feature_index   INTEGER NOT NULL,   -- index local dans le SAE ; informatif, jamais clé logique seule
    split           TEXT NOT NULL,
    nl_description  TEXT NOT NULL,
    top_examples    TEXT NOT NULL,    -- JSON array sérialisé
    score_interp    REAL,
    activation_freq REAL,
    -- Statistiques d'activation depuis Neuronpedia (utilisées pour la détection OOD)
    -- Ces colonnes remplacent la norme W_dec qui est une grandeur différente
    activation_p99  REAL,
    activation_mean REAL,
    activation_std  REAL,
    layer           TEXT,             -- libellé d'affichage (peut différer de layer_index)
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL,
    -- Un même (modèle, release, couche, hook, index) ne peut apparaître deux fois.
    UNIQUE(model_name, sae_release, layer_index, hook_name, feature_index)
);

-- ─────────────────────────────────────────────
-- Outputs bruts des agents (immuables)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id    TEXT NOT NULL REFERENCES model_runs(model_run_id),  -- modèle ayant produit la sortie (Règle 11)
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITÉ LOGIQUE (Règle 10)
    feature_index   INTEGER NOT NULL,                       -- informatif (index dans le SAE)
    agent_name      TEXT NOT NULL,
    run_number      INTEGER NOT NULL DEFAULT 1,
    output_json     TEXT,
    raw_output      TEXT,
    status          TEXT NOT NULL,
    error_msg       TEXT,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    batch_id        TEXT REFERENCES batches(batch_id),
    cost_usd        REAL,
    coefficient_type TEXT DEFAULT 'confidence',
    created_at      TEXT NOT NULL,
    -- Unicité sur (model_run_id, feature_uid) : plusieurs modèles peuvent annoter le même
    -- feature sans s'écraser (Règle 11). feature_uid (PAS feature_index) reste l'identité
    -- logique (Règle 10). La vérification de divergence dans save_agent_output() (qui inclut
    -- model_run_id via IS) rend la persistance idempotente même quand model_run_id est NULL.
    UNIQUE(run_id, model_run_id, feature_uid, agent_name, run_number)
);

-- ─────────────────────────────────────────────
-- Métriques calculées
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS metrics (
    metric_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id    TEXT REFERENCES model_runs(model_run_id),  -- modèle de la métrique ; NULL = métrique
                                      -- AGRÉGÉE / cross-modèle (stabilité inter-modèles, etc.)
    phase           TEXT NOT NULL,
    split           TEXT NOT NULL,
    metric_name     TEXT NOT NULL,
    value           REAL,
    ci_low          REAL,
    ci_high         REAL,
    n_samples       INTEGER,
    baseline        TEXT,             -- NULL = MorphoRepr ; sinon nom de la baseline
    computed_at     TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Baselines
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id    TEXT NOT NULL REFERENCES model_runs(model_run_id),  -- modèle de la baseline (Règle 11)
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITÉ LOGIQUE
    feature_index   INTEGER NOT NULL,                       -- informatif
    baseline_name   TEXT NOT NULL,
    annotation_run1 TEXT,
    annotation_run2 TEXT,
    fidelity_auc    REAL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(run_id, model_run_id, feature_uid, baseline_name)
);

-- ─────────────────────────────────────────────
-- Contrôle mélangé
-- shuffle_id est déterministe : {run_id}_{sha1(feature_uid)[:12]}_{shuffle_number}
-- (fondé sur feature_uid, PAS feature_index, pour éviter les collisions inter-couches)
-- La contrainte UNIQUE(run_id, feature_uid, shuffle_number) empêche les doublons
-- Scoré par le même chemin déterministe que le primaire ; fraction 'llm_qualitative' pour audit
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id          TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    feature_uid         TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITÉ LOGIQUE
    feature_index       INTEGER NOT NULL,                                -- informatif
    shuffle_number      INTEGER NOT NULL,
    source_feature_uid  TEXT NOT NULL REFERENCES features(feature_uid),  -- source (uid)
    source_feature_index INTEGER,                                        -- informatif
    annotation          TEXT NOT NULL,
    causal_score        REAL,
    causal_outcome      TEXT,
    -- 'deterministic' (chemin prédicteur+classifieurs, comme la métrique primaire — défaut)
    -- | 'llm_qualitative' (fraction d'audit, Section 8 / shuffle_control)
    scored_by           TEXT DEFAULT 'deterministic',
    created_at          TEXT NOT NULL,
    UNIQUE(run_id, feature_uid, shuffle_number)
);

-- ─────────────────────────────────────────────
-- Résultats de steering — texte et activations avant/après
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS steering_results (
    result_id           TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id        TEXT NOT NULL REFERENCES model_runs(model_run_id),  -- modèle du steering (Règle 11)
    feature_uid         TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITÉ LOGIQUE
    feature_index       INTEGER NOT NULL,                                -- informatif
    intervention_space  TEXT,            -- 'residual_add_decoder' | 'sae_latent_clamp'
    magnitude           REAL NOT NULL,   -- magnitude absolue VISÉE effectivement appliquée (informatif)
    magnitude_rel       REAL,            -- multiple de p99 visé (NULL en mode "absolute") (informatif)
    -- magnitude_key : clé TEXTE stable de la magnitude, valable dans LES DEUX modes :
    --   'rel:{rel}' en mode p99_relative, 'abs:{legacy}' en mode absolute.
    -- Évite un flottant nullable dans la contrainte d'unicité (idempotence aussi en absolu).
    magnitude_key       TEXT NOT NULL,
    probe_id            INTEGER NOT NULL,
    probe_family        TEXT,            -- 'neutral' | 'domain_compatible'
    probe_category      TEXT,            -- 'code'|'social'|'temporal'|… (NULL si 'neutral')
    generation_index    INTEGER DEFAULT 0,  -- index de génération (générations multiples/sonde)
    text_before         TEXT NOT NULL,
    text_after          TEXT,
    layer               TEXT,
    token_position      TEXT,
    activation_before   REAL,            -- activation latente cible AVANT
    activation_after    REAL,            -- activation latente cible APRÈS
    achieved_delta      REAL,            -- delta OBTENU (after - before) ; peut ≠ magnitude visée
    -- ood_flag : critère MIXTE (Section 7) basé sur activation_p99/mean/std de la table features,
    -- PAS sur la norme W_dec.
    ood_flag            INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL,
    -- Idempotence en reprise (LES DEUX modes via magnitude_key ; probe_category évite les
    -- collisions entre catégories qui réinitialisent probe_id). La stochasticité du steering
    -- est compatible avec l'archivage "gelé et auditable" : à la reprise, on conserve la
    -- 1ʳᵉ sortie et toute divergence est journalisée (table steering_duplicate_attempts).
    UNIQUE(run_id, model_run_id, feature_uid, intervention_space, magnitude_key,
           probe_family, probe_category, probe_id, generation_index)
);

-- Journal des divergences de steering : on conserve la 1ʳᵉ sortie (UNIQUE ci-dessus), mais
-- toute tentative de réécriture DIFFÉRENTE de la même cellule est tracée ici (audit), au lieu
-- d'être ignorée silencieusement.
CREATE TABLE IF NOT EXISTS steering_duplicate_attempts (
    attempt_id                  TEXT PRIMARY KEY,
    run_id                      TEXT NOT NULL,
    feature_uid                 TEXT NOT NULL,
    intervention_space          TEXT,
    magnitude_key               TEXT,
    probe_family                TEXT,
    probe_category              TEXT,
    probe_id                    INTEGER,
    generation_index            INTEGER,
    previous_result_id          TEXT,
    -- Sortie DIVERGENTE tentée (la 1ʳᵉ est conservée dans steering_results) : on garde de quoi
    -- diagnostiquer, pas seulement le texte.
    attempted_text_before       TEXT,
    attempted_text_after        TEXT,
    attempted_activation_before REAL,
    attempted_activation_after  REAL,
    attempted_achieved_delta    REAL,
    attempted_ood_flag          INTEGER,
    created_at                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_usage (
    call_id         TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id    TEXT NOT NULL REFERENCES model_runs(model_run_id),  -- coût/compute attribué à un modèle
    phase           TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    model           TEXT NOT NULL,
    tokens_input    INTEGER NOT NULL,
    tokens_output   INTEGER NOT NULL,
    batch_id        TEXT,
    cost_usd        REAL NOT NULL,
    cumulative_cost REAL,
    timestamp       TEXT NOT NULL,
    -- Idempotence du coût par (modèle, batch) : à la reprise, un coût déjà loggé pour ce
    -- (run, model_run, batch, phase, agent) n'est PAS recompté (log_api_cost en INSERT OR IGNORE).
    -- L'inclusion de model_run_id attribue correctement les coûts par modèle (objectif v6.5).
    UNIQUE(run_id, model_run_id, batch_id, phase, agent_name)
);

-- ─────────────────────────────────────────────
-- Versions du lexique
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lexicon_versions (
    version         TEXT PRIMARY KEY,
    morphemes       TEXT NOT NULL,
    free_roots      TEXT NOT NULL,
    features_per_root REAL,
    free_root_rate  REAL,
    base_coverage   REAL,
    free_coverage   REAL,
    entropy         REAL,
    sha256          TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Calibration des classifieurs de propriétés (archivée pour audit/repro)
-- Écrite par classifiers/calibration/run_calibration.py (Section 6)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS classifier_calibrations (
    calibration_id        TEXT PRIMARY KEY,
    run_id                TEXT,                 -- run associé (NULL si calibration hors run)
    property              TEXT NOT NULL,
    classifier_name       TEXT NOT NULL,
    classifier_version    TEXT,
    dataset_hash          TEXT,                 -- hash du jeu de calibration
    n                     INTEGER,
    class_balance_json    TEXT,
    threshold_json        TEXT,
    confusion_matrix_json TEXT,
    macro_f1              REAL,
    accuracy              REAL,
    passed                INTEGER DEFAULT 0,
    created_at            TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Résultats de l'étude utilisateur (hors pipeline ; stockés ici pour traçabilité)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_study_results (
    result_id           TEXT PRIMARY KEY,
    participant_id      TEXT NOT NULL,
    condition           TEXT NOT NULL,    -- 'morphorepr'|'semantic_regex'|'nl'
    feature_uid         TEXT REFERENCES features(feature_uid),  -- identité logique (multi-couches)
    feature_index       INTEGER,                                -- informatif
    task_id             TEXT NOT NULL,
    response            TEXT,
    accuracy            REAL,
    response_time_ms    INTEGER,
    cognitive_load_score REAL,            -- score composite NASA-TLX
    preference_rank     INTEGER,
    created_at          TEXT NOT NULL
);

-- Index
CREATE INDEX IF NOT EXISTS idx_ao_feature  ON agent_outputs(feature_uid, agent_name, run_number);
CREATE INDEX IF NOT EXISTS idx_metrics     ON metrics(run_id, split, metric_name);
CREATE INDEX IF NOT EXISTS idx_api_phase   ON api_usage(run_id, phase);
CREATE INDEX IF NOT EXISTS idx_steering    ON steering_results(run_id, feature_uid, magnitude);
CREATE INDEX IF NOT EXISTS idx_batches_run ON batches(run_id, phase, agent_name, run_number);
```

---

## 4. Parseur MorphoRepr unique

```python
# utils/morphorepr_parser.py
"""
Parseur MorphoRepr.
Source unique de vérité pour TOUTES les métriques morphémiques.

Algorithme par SEGMENTATION sur '-' (corrige les bugs de la v4 : non-détection
des infixes, et échec sur mal-o / ne-a). Pour chaque mot :
  1. Retirer le coefficient (avant '·'), fait dans parse_expression().
  2. Découper le mot sur '-' en segments.
  3. Le dernier segment est le suffixe (doit être un token de suffixe connu).
  4. Lire les préfixes en tête, SANS jamais consommer le dernier segment
     disponible (qui devient la racine). => mal-o donne racine 'mal' ;
     mal-emo-a donne préfixe 'mal' + racine 'emo'.
  5. Le premier segment non-préfixe est la racine ; les segments restants
     sont les infixes.

Note : un parseur strictement positionnel par sous-chaînes (v4) échouait car,
après retrait du suffixe '-o', le corps 'soc-ant' ne contient plus le motif
'-ant-' (le tiret final est parti avec le suffixe). La segmentation évite cela.
"""
from dataclasses import dataclass, field
from typing import Optional
import re

PREFIXES  = ("mal-", "ne-", "pli-", "plej-", "duon-")
INFIXES   = ("-ad-", "-int-", "-it-", "-ist-", "-ant-", "-at-", "-ig-", "-iĝ-")
TENSE_SUFFIXES     = ("-as", "-is", "-os", "-us", "-u")
SYNTACTIC_SUFFIXES = ("-o", "-a", "-e", "-i")
ALL_SUFFIXES = TENSE_SUFFIXES + SYNTACTIC_SUFFIXES

PREDEFINED_ROOTS = frozenset(
    {"sci", "emo", "ag", "dir", "soc", "dat", "tem", "lok", "mal", "ne"}
)

# RESERVED_TOKENS : ne peuvent PAS être utilisés comme nouvelles racines libres induites.
# Note : "mal" et "ne" apparaissent dans PREDEFINED_ROOTS ET RESERVED_TOKENS.
# C'est intentionnel :
#   - "mal" et "ne" sont valides comme racines PRÉDÉFINIES (ex. "mal-o", "ne-a")
#   - Ils ne peuvent PAS être ré-enregistrés comme nouvelles racines LIBRES par le pipeline
RESERVED_TOKENS = frozenset({
    "mal", "ne", "pli", "plej", "duon",                 # tokens de préfixe
    "ad", "int", "it", "ist", "ant", "at", "ig", "iĝ",  # tokens d'infixe (iĝ inclus)
    "o", "a", "e", "i", "as", "is", "os", "us", "u"      # tokens de suffixe
})

# Jeux de tokens SANS tiret, utilisés par la segmentation (parse_word).
PREFIX_TOKENS      = frozenset(p.strip("-") for p in PREFIXES)
INFIX_TOKENS       = frozenset(ix.strip("-") for ix in INFIXES)
TENSE_SUFFIX_TOK   = frozenset(s.strip("-") for s in TENSE_SUFFIXES)
SYNT_SUFFIX_TOK    = frozenset(s.strip("-") for s in SYNTACTIC_SUFFIXES)
SUFFIX_TOKENS      = TENSE_SUFFIX_TOK | SYNT_SUFFIX_TOK


@dataclass
class ParsedTerm:
    coefficient: float
    coefficient_type: str = "confidence"   # "confidence" | "activation"
    prefixes: list[str] = field(default_factory=list)
    root: str = ""
    infixes: list[str] = field(default_factory=list)
    suffix: str = ""
    suffix_type: str = ""   # "tense" | "syntactic"
    raw_word: str = ""
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.parse_error is None and bool(self.root) and bool(self.suffix)

    @property
    def all_morphemes(self) -> set[str]:
        m = set(self.prefixes) | {self.root} | set(self.infixes)
        if self.suffix:
            m.add(self.suffix)
        return m


@dataclass
class ParsedExpression:
    terms: list[ParsedTerm] = field(default_factory=list)
    raw: str = ""
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return (self.parse_error is None
                and bool(self.terms)
                and all(t.is_valid for t in self.terms))

    @property
    def roots(self) -> set[str]:
        return {t.root for t in self.terms if t.root}

    @property
    def all_morphemes(self) -> set[str]:
        result = set()
        for t in self.terms:
            result |= t.all_morphemes
        return result

    @property
    def coefficients(self) -> list[float]:
        return [t.coefficient for t in self.terms]


def parse_word(word: str, known_free_roots: Optional[set] = None) -> ParsedTerm:
    """Parse un seul mot MorphoRepr par SEGMENTATION sur '-'.

    `known_free_roots` (optionnel) : racines libres enregistrées. Une racine non
    prédéfinie et non enregistrée reste SYNTAXIQUEMENT valide (règle 6) ; parse_word
    ne l'invalide pas (l'éligibilité à l'enregistrement est vérifiée séparément par
    can_register_new_free_root)."""
    known_free_roots = known_free_roots or set()
    term = ParsedTerm(coefficient=0.0, coefficient_type="confidence", raw_word=word)

    segs = [s for s in word.strip().split("-") if s]
    if not segs:
        term.parse_error = f"Mot vide : {word}"
        return term

    # Étape 3 : suffixe = dernier segment
    if segs[-1] not in SUFFIX_TOKENS:
        term.parse_error = f"Aucun suffixe reconnu : {word}"
        return term
    term.suffix = "-" + segs[-1]
    term.suffix_type = "tense" if segs[-1] in TENSE_SUFFIX_TOK else "syntactic"

    body = segs[:-1]
    if not body:
        term.parse_error = f"Aucune racine extraite : {word}"
        return term

    # Étape 4 : préfixes en tête, SANS jamais consommer le dernier segment (la racine).
    # => mal-o : racine 'mal' ; mal-emo-a : préfixe 'mal' + racine 'emo' ; mal-ne-o :
    #    préfixe 'mal' + racine 'ne'.
    i = 0
    while i < len(body) - 1 and body[i] in PREFIX_TOKENS:
        term.prefixes.append(body[i])
        i += 1

    # Étape 5a : racine = premier segment non-préfixe restant
    root = body[i]
    i += 1
    if root in PREDEFINED_ROOTS:
        pass                                   # racine prédéfinie (inclut mal, ne)
    elif root in RESERVED_TOKENS:
        term.parse_error = f"Token réservé '{root}' utilisé comme racine : {word}"
        return term
    elif root in known_free_roots:
        pass                                   # racine libre enregistrée
    elif re.match(r'^[a-z]{2,5}$', root):
        pass                                   # racine libre bien formée (enreg. vérifié ailleurs)
    else:
        term.parse_error = f"Racine mal formée '{root}' : {word}"
        return term
    term.root = root

    # Étape 5b : segments restants = infixes
    for seg in body[i:]:
        if seg not in INFIX_TOKENS:
            term.parse_error = f"Segment inattendu '{seg}' (infixe inconnu/mal placé) : {word}"
            return term
        term.infixes.append(seg)

    return term


def parse_expression(expr: str,
                     coefficient_type: str = "confidence") -> ParsedExpression:
    """Parse une expression MorphoRepr complète."""
    result = ParsedExpression(raw=expr)
    if not expr or not expr.strip():
        result.parse_error = "Expression vide"
        return result

    term_strings = [t.strip() for t in expr.split("+") if t.strip()]
    if not term_strings:
        result.parse_error = "Aucun terme trouvé"
        return result

    for ts in term_strings:
        if "·" not in ts:
            result.parse_error = f"Terme sans séparateur '·' : {ts}"
            return result
        coeff_str, word = ts.split("·", 1)
        try:
            coeff = float(coeff_str.strip())
        except ValueError:
            result.parse_error = f"Coefficient invalide : {coeff_str}"
            return result
        if not (0.01 <= coeff <= 1.00):
            result.parse_error = f"Coefficient hors plage [0.01,1.00] : {coeff}"
            return result
        parsed_term = parse_word(word.strip())
        parsed_term.coefficient = coeff
        parsed_term.coefficient_type = coefficient_type
        result.terms.append(parsed_term)

    # Vérifier l'ordre décroissant des coefficients
    coeffs = [t.coefficient for t in result.terms]
    if coeffs != sorted(coeffs, reverse=True):
        result.parse_error = "Termes non ordonnés par coefficient décroissant"
        return result

    return result


def is_valid_root(root: str, known_free_roots: Optional[set] = None) -> bool:
    """Vrai si `root` est une racine VALIDE en l'état : racine prédéfinie, ou racine
    libre bien formée ([a-z]{2,5}) non réservée (enregistrée ou non). Sert au parsing."""
    known_free_roots = known_free_roots or set()
    if root in PREDEFINED_ROOTS:
        return True
    if root in RESERVED_TOKENS:
        return False
    if root in known_free_roots:
        return True
    return bool(re.match(r'^[a-z]{2,5}$', root))


def can_register_new_free_root(root: str,
                               known_free_roots: Optional[set] = None) -> Optional[str]:
    """Valide l'éligibilité d'une racine candidate à être ENREGISTRÉE comme NOUVELLE
    racine libre. Retourne None si éligible, un message d'erreur sinon.

    Distinct de is_valid_root : 'mal' et 'ne' sont des racines VALIDES (prédéfinies)
    mais ne peuvent PAS être ré-enregistrées comme nouvelles racines libres ; de même
    une racine déjà enregistrée ne peut pas l'être deux fois."""
    known_free_roots = known_free_roots or set()
    if root in PREDEFINED_ROOTS:
        return f"'{root}' est déjà une racine prédéfinie (pas de ré-enregistrement)"
    if root in RESERVED_TOKENS:
        return f"'{root}' est un token réservé (préfixe/infixe/suffixe)"
    if root in known_free_roots:
        return f"'{root}' est déjà enregistrée comme racine libre"
    if not re.match(r'^[a-z]{2,5}$', root):
        return f"'{root}' ne correspond pas à [a-z]{{2,5}}"
    return None
```

---

## 5. Utilitaires principaux

### 5.1 db_utils.py

```python
# utils/db_utils.py
"""
Seul point d'accès à features.db.
Toute opération directe sur la DB en dehors de ce module est interdite.
DB_PATH configurable via MORPHOREPR_DB_PATH pour l'isolation des tests.
"""
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("MORPHOREPR_DB_PATH", "db/features.db"))


@contextmanager
def get_conn(db_path: Optional[Path] = None):
    # Relire l'env à CHAQUE appel : garantit l'isolation des tests même si ce module
    # a été importé avant que le fixture ne fixe MORPHOREPR_DB_PATH (sinon DB_PATH,
    # figé à l'import, pointerait sur la DB de production).
    path = db_path or Path(os.environ.get("MORPHOREPR_DB_PATH", DB_PATH))
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_features(split: Optional[str] = None) -> list[dict]:
    with get_conn() as conn:
        q = "SELECT * FROM features WHERE 1=1"
        p = []
        if split:
            q += " AND split = ?"
            p.append(split)
        rows = conn.execute(q, p).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["top_examples"] = json.loads(d["top_examples"])
        result.append(d)
    return result


def load_features_not_processed(run_id: str,
                                 agent_name: str,
                                 run_number: int,
                                 model_run_id: Optional[str] = None,
                                 split: Optional[str] = None) -> list[dict]:
    """Retourne les features sans output pour cet agent/run_number ET CE MODÈLE. Idempotent.
    Clés logiques : feature_uid (Règle 10) + model_run_id (Règle 11). SANS le filtre modèle,
    un 2ᵉ modèle (réplication/secondaire) croirait toutes les features déjà traitées par le
    1ᵉʳ. model_run_id par défaut = model_run legacy explicite (chemin mono-modèle)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        done = {
            r["feature_uid"]
            for r in conn.execute("""
                SELECT feature_uid FROM agent_outputs
                WHERE run_id = ? AND model_run_id = ? AND agent_name = ? AND run_number = ?
            """, (run_id, model_run_id, agent_name, run_number)).fetchall()
        }
        q = "SELECT * FROM features WHERE 1=1"
        p = []
        if split:
            q += " AND split = ?"
            p.append(split)
        rows = conn.execute(q, p).fetchall()

    result = []
    for r in rows:
        if r["feature_uid"] not in done:
            d = dict(r)
            d["top_examples"] = json.loads(d["top_examples"])
            result.append(d)
    return result


def save_agent_output(run_id: str,
                      feature_index: int,
                      agent_name: str,
                      run_number: int,
                      output_json: Optional[dict],
                      raw_output: str,
                      status: str,
                      error_msg: Optional[str],
                      tokens_input: int,
                      tokens_output: int,
                      batch_id: Optional[str],
                      cost_usd: float,
                      coefficient_type: str = "confidence",
                      feature_uid: Optional[str] = None,
                      model_run_id: Optional[str] = None):
    """Persistance idempotente MAIS NON SILENCIEUSE en cas de divergence.
    Clés logiques : feature_uid (Règle 10, REQUIS) + model_run_id (Règle 11, modèle producteur).

    - Si aucune sortie n'existe pour (run_id, model_run_id, feature_uid, agent_name, run_number) → INSERT.
    - Si une sortie IDENTIQUE existe (même output_json, raw_output, status) → ignorer (reprise).
    - Si une sortie DIFFÉRENTE existe → RuntimeError (ne pas masquer une divergence).
    Évite le piège du INSERT OR IGNORE qui avale silencieusement une sortie différente.
    NB : model_run_id peut être NULL (chemin legacy mono-modèle) ; la comparaison utilise IS."""
    if feature_uid is None:
        raise ValueError("save_agent_output : feature_uid est requis (identité logique, Règle 10).")
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)   # colonne NOT NULL : jamais de NULL (Règle 11)
    new_json = json.dumps(output_json) if output_json is not None else None
    with get_conn() as conn:
        existing = conn.execute("""
            SELECT output_json, raw_output, status FROM agent_outputs
            WHERE run_id=? AND model_run_id=? AND feature_uid=? AND agent_name=? AND run_number=?
        """, (run_id, model_run_id, feature_uid, agent_name, run_number)).fetchone()
        if existing is not None:
            same = (existing["output_json"] == new_json
                    and existing["raw_output"] == raw_output
                    and existing["status"] == status)
            if same:
                return                       # reprise idempotente
            raise RuntimeError(
                f"Divergence de sortie pour (run={run_id}, model_run={model_run_id}, "
                f"feature_uid={feature_uid}, agent={agent_name}, run_number={run_number}) : "
                f"une sortie DIFFÉRENTE est déjà persistée. Run bloqué (ne pas écraser silencieusement)."
            )
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, model_run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, model_run_id, feature_uid, feature_index, agent_name, run_number,
            new_json, raw_output, status, error_msg,
            tokens_input, tokens_output, batch_id, cost_usd,
            coefficient_type,
            datetime.utcnow().isoformat()
        ))


def register_batch(batch_id: str, run_id: str, phase: str,
                   agent_name: str, run_number: int, n_requests: int,
                   model_run_id: Optional[str] = None):
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO batches (
                batch_id, run_id, model_run_id, phase, agent_name, run_number,
                n_requests, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
        """, (batch_id, run_id, model_run_id, phase, agent_name, run_number,
              n_requests, datetime.utcnow().isoformat()))


def register_batch_with_items(batch_id: str, run_id: str, phase: str,
                              agent_name: str, run_number: int, n_requests: int,
                              items: list[dict], model_run_id: Optional[str] = None):
    """Enregistre le batch ET son mapping custom_id → feature_uid dans UNE SEULE transaction
    (crash-safe : pas de fenêtre où le batch existe sans sa map). items : [{custom_id,
    feature_uid, feature_index, model_run_id?}, …]. model_run_id (paramètre) est la valeur
    par défaut des items qui n'en portent pas. Idempotent côté items (INSERT OR IGNORE)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO batches (
                batch_id, run_id, model_run_id, phase, agent_name, run_number,
                n_requests, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?)
        """, (batch_id, run_id, model_run_id, phase, agent_name, run_number,
              n_requests, datetime.utcnow().isoformat()))
        for it in items:
            # Fallback CORRECT : it.get(k, default) renvoie None si la clé existe AVEC None
            # (cas de build_batch_item_rows(features) sans model_run_id). On utilise `or` pour
            # retomber sur le model_run_id du batch, sinon batch_items (NOT NULL) insérerait NULL.
            item_model_run_id = it.get("model_run_id") or model_run_id
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid,
                                                   feature_index, model_run_id)
                VALUES (?, ?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"],
                  item_model_run_id))


def mark_batch_consumed(batch_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE batches SET status='consumed', consumed_at=?
            WHERE batch_id=?
        """, (datetime.utcnow().isoformat(), batch_id))


def save_batch_items(batch_id: str, items: list[dict], model_run_id: Optional[str] = None):
    """Persiste la correspondance custom_id → feature_uid d'un batch (table batch_items).
    items : [{custom_id, feature_uid, feature_index, model_run_id?}, …]. model_run_id (param)
    est la valeur par défaut. Idempotent (INSERT OR IGNORE)."""
    with get_conn() as conn:
        for it in items:
            # `or` (et non get(k, default)) : la clé peut exister avec None (build_batch_item_rows
            # sans model_run_id) ; on retombe alors sur le model_run_id du batch.
            mr = it.get("model_run_id") or model_run_id
            if mr is None:
                raise ValueError("save_batch_items : model_run_id requis (batch_items NOT NULL, Règle 11).")
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid,
                                                   feature_index, model_run_id)
                VALUES (?, ?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"], mr))


def load_batch_item_map(batch_id: str) -> dict[str, dict]:
    """Recharge la map custom_id → {feature_uid, feature_index, model_run_id} pour ce batch."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT custom_id, feature_uid, feature_index, model_run_id
            FROM batch_items WHERE batch_id=?
        """, (batch_id,)).fetchall()
    return {r["custom_id"]: {"feature_uid": r["feature_uid"],
                             "feature_index": r["feature_index"],
                             "model_run_id": r["model_run_id"]} for r in rows}


# Mapping tier déclaré (config) → valeur stockée en DB (provider_tier).
_TIER_DB = {
    "A_fully_open":      "A_fully_open",
    "A_or_B_open":       "A_fully_open",      # à préciser au gel ; rétrogradé vers B si poids seuls
    "B_open_weight":     "B_open_weight",
    "C_proprietary_api": "C_proprietary_api",
}


def register_model_run(run_id: str, provider_cfg: dict,
                       is_primary_scientific: bool = False,
                       use_for_primary_claims: Optional[bool] = None) -> str:
    """Enregistre un model_run (Règle 11) et retourne son model_run_id. Archive révisions,
    hashes, env d'inférence et paramètres de génération. Pour un fournisseur Tier C
    (propriétaire), use_for_primary_claims est forcé à False par défaut."""
    tier_decl = provider_cfg.get("tier", "C_proprietary_api")
    tier_db   = _TIER_DB.get(tier_decl, tier_decl)
    is_proprietary = tier_db == "C_proprietary_api"
    if use_for_primary_claims is None:
        # Par défaut : un Tier C n'est jamais admissible aux claims primaires (Règle 11).
        use_for_primary_claims = (not is_proprietary) and is_primary_scientific
    if is_proprietary and use_for_primary_claims:
        raise ValueError("Un fournisseur Tier C (propriétaire) ne peut pas porter de claim primaire (Règle 11).")
    gen = provider_cfg.get("deterministic_generation",
                           provider_cfg.get("generation_params", {}))
    model_run_id = str(uuid4())
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO model_runs (
                model_run_id, run_id, provider_name, provider_tier, backend,
                model_name, model_revision, tokenizer_revision,
                weights_sha256, tokenizer_sha256, inference_env_hash,
                precision, quantization, license,
                is_primary_scientific, use_for_primary_claims,
                generation_params_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_run_id, run_id, provider_cfg.get("provider", "unknown"), tier_db,
            provider_cfg.get("backend"), provider_cfg.get("model_name", "unknown"),
            provider_cfg.get("model_revision"), provider_cfg.get("tokenizer_revision"),
            provider_cfg.get("weights_sha256"), provider_cfg.get("tokenizer_sha256"),
            provider_cfg.get("inference_container_hash", provider_cfg.get("inference_env_hash")),
            provider_cfg.get("precision"), provider_cfg.get("quantization"),
            provider_cfg.get("license"),
            int(is_primary_scientific), int(use_for_primary_claims),
            json.dumps(gen), datetime.utcnow().isoformat()
        ))
    return model_run_id


def load_model_runs(run_id: str) -> list[dict]:
    """Tous les model_runs d'un run (pour le reporting par modèle/tier)."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM model_runs WHERE run_id=?", (run_id,)).fetchall()
    return [dict(r) for r in rows]


def restore_model_run_ids(run_id: str, config: dict) -> dict:
    """À la REPRISE (--resume) : reconstruit config['_runtime']['model_run_ids'] depuis la DB,
    en rattachant chaque model_run persisté au rôle déclaré dans la config (par model_name).
    Évite que les phases multi-modèle (et steerer.run) retombent sur un model_run legacy alors
    qu'un modèle primaire/secondaire existe déjà en DB (Règle 11)."""
    by_name = {}
    for r in load_model_runs(run_id):
        by_name.setdefault(r["model_name"], r["model_run_id"])
    mp  = config.get("model_providers", {})
    ids = {}
    prim = mp.get("primary_reproducible") or {}
    if prim.get("model_name") in by_name:
        ids["primary"] = by_name[prim["model_name"]]
    sec = mp.get("secondary_proprietary") or {}
    if sec.get("model_name") in by_name:
        ids["secondary"] = by_name[sec["model_name"]]
    repl = mp.get("optional_cross_model_replication", {})
    if repl.get("enabled"):
        ids["replication"] = [by_name[m["model_name"]]
                              for m in repl.get("models", []) if m.get("model_name") in by_name]
    config.setdefault("_runtime", {})["model_run_ids"] = ids
    return ids


def ensure_legacy_model_run(run_id: str, model_name: str = "legacy_single_model") -> str:
    """Crée (si absent) et retourne un model_run LEGACY explicite et déterministe pour ce run.
    Sert de valeur par défaut au chemin mono-modèle / aux écritures sans model_run_id explicite,
    afin que les colonnes model_run_id NOT NULL ne dépendent jamais d'un NULL (Règle 11, item 6).
    Tier C par défaut (donc jamais admissible aux claims primaires)."""
    legacy_id = f"{run_id}::legacy"
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO model_runs (
                model_run_id, run_id, provider_name, provider_tier, backend,
                model_name, model_revision, tokenizer_revision,
                weights_sha256, tokenizer_sha256, inference_env_hash,
                precision, quantization, license,
                is_primary_scientific, use_for_primary_claims,
                generation_params_json, created_at
            ) VALUES (?, ?, 'legacy', 'C_proprietary_api', NULL,
                      ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                      0, 0, '{}', ?)
        """, (legacy_id, run_id, model_name, datetime.utcnow().isoformat()))
    return legacy_id


def get_unconsumed_batch(run_id: str, phase: str,
                         agent_name: str, run_number: int,
                         model_run_id: Optional[str] = None) -> Optional[str]:
    """Retourne le batch_id d'un batch soumis mais non consommé, si existant. Filtre par
    model_run_id : avec plusieurs modèles dans le même run, la reprise ne récupère JAMAIS le
    batch d'un autre modèle (Règle 11). Comme batches.model_run_id est NOT NULL, un appel sans
    model_run_id résout le model_run legacy explicite (sinon un filtre IS NULL ne matcherait rien)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        row = conn.execute("""
            SELECT batch_id FROM batches
            WHERE run_id=? AND phase=? AND agent_name=?
              AND run_number=? AND model_run_id=? AND status='submitted'
            ORDER BY submitted_at DESC LIMIT 1
        """, (run_id, phase, agent_name, run_number, model_run_id)).fetchone()
    return row["batch_id"] if row else None


def log_api_cost(run_id: str, phase: str, agent_name: str,
                 model: str, tokens_in: int, tokens_out: int,
                 batch_id: Optional[str], cost: float,
                 model_run_id: Optional[str] = None) -> float:
    """Loggue le coût et met à jour le cumul, ATTRIBUÉ PAR MODÈLE (Règle 11). IDEMPOTENT PAR
    (modèle, batch) : grâce à UNIQUE(run_id, model_run_id, batch_id, phase, agent_name), un coût
    déjà loggé pour ce (run, model_run, batch, phase, agent) n'est PAS recompté à la reprise.
    model_run_id par défaut = model_run legacy explicite (colonne NOT NULL).
    NB : pour les appels non-batch (batch_id NULL), SQLite n'applique pas l'unicité — la
    déduplication ne vaut que pour les batchs (cas de la reprise après crash)."""
    if model_run_id is None:
        model_run_id = ensure_legacy_model_run(run_id)
    with get_conn() as conn:
        # Non-silencieux : si un coût est DÉJÀ loggé pour ce (modèle, batch) avec un montant
        # différent, c'est une divergence à signaler (et non à ignorer).
        if batch_id is not None:
            prev = conn.execute("""
                SELECT cost_usd, tokens_input, tokens_output FROM api_usage
                WHERE run_id=? AND model_run_id=? AND batch_id=? AND phase=? AND agent_name=?
            """, (run_id, model_run_id, batch_id, phase, agent_name)).fetchone()
            if prev is not None and (
                abs(prev["cost_usd"] - cost) > 1e-9
                or prev["tokens_input"] != tokens_in
                or prev["tokens_output"] != tokens_out
            ):
                raise RuntimeError(
                    f"Divergence de coût pour batch {batch_id} (run={run_id}, model_run={model_run_id}, "
                    f"{phase}/{agent_name}) : déjà loggé {prev['cost_usd']:.4f}$ "
                    f"({prev['tokens_input']}/{prev['tokens_output']} tk), "
                    f"recalculé {cost:.4f}$ ({tokens_in}/{tokens_out} tk). Run bloqué."
                )
        cur = conn.execute("""
            INSERT OR IGNORE INTO api_usage (
                call_id, run_id, model_run_id, phase, agent_name, model,
                tokens_input, tokens_output, batch_id, cost_usd,
                cumulative_cost, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """, (
            str(uuid4()), run_id, model_run_id, phase, agent_name, model,
            tokens_in, tokens_out, batch_id, cost,
            datetime.utcnow().isoformat()
        ))
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        current = row["total_cost_usd"] if row else 0.0
        if cur.rowcount == 0:
            # Coût déjà loggé pour ce (modèle, batch) (reprise, montant identique) → ne pas recompter.
            logger.info(f"Coût déjà loggé pour batch {batch_id} (model_run {model_run_id}) — non recompté.")
            return current
        cumulative = current + cost
        conn.execute(
            "UPDATE runs SET total_cost_usd=? WHERE run_id=?",
            (cumulative, run_id)
        )
        conn.execute(
            "UPDATE api_usage SET cumulative_cost=? "
            "WHERE run_id=? AND model_run_id=? AND phase=? AND agent_name=? "
            "AND (batch_id = ? OR (batch_id IS NULL AND ? IS NULL)) "
            "AND cumulative_cost IS NULL",
            (cumulative, run_id, model_run_id, phase, agent_name, batch_id, batch_id)
        )
    return cumulative


def check_budget(run_id: str, max_cost: float) -> tuple[float, bool]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    cost = row["total_cost_usd"] if row else 0.0
    return cost, cost >= max_cost
```

### 5.2 api_utils.py

```python
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
```

### 5.3 prompt_utils.py

```python
# utils/prompt_utils.py
"""
Chargement, hashing et enregistrement des prompts.
SHA256 complet (64 caractères hex) — pas de troncature.
Hash canonique pour le corpus (export CSV trié) et le lexique (clés JSON triées).
"""
import csv
import hashlib
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from utils.db_utils import get_conn


def load_prompt(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompt introuvable : {path}")
    return p.read_text(encoding="utf-8").strip()


def hash_prompt(content: str) -> str:
    """SHA256 complet — 64 caractères hex, sans troncature."""
    return hashlib.sha256(content.encode()).hexdigest()


def hash_lexicon_canonical(lexicon_path: str) -> str:
    """Hash canonique du lexique : clés JSON triées, indépendant de l'encodage."""
    data      = json.loads(Path(lexicon_path).read_text())
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_corpus_canonical(db_path: str) -> str:
    """
    Hash canonique du corpus : export CSV trié de la table features uniquement.
    Couvre uniquement les données d'entrée — PAS les résultats ajoutés pendant le run.
    La base de données croît légitimement pendant l'exécution ; seules les lignes
    de la table features font partie de la définition du corpus gelé.
    """
    conn = sqlite3.connect(db_path)
    cur  = conn.execute(
        "SELECT * FROM features ORDER BY feature_uid"
    )
    col_names = [d[0] for d in cur.description]   # en-tête : détecte un changement de schéma/ordre
    rows = cur.fetchall()
    conn.close()
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(col_names)                    # ligne d'en-tête incluse dans le hash
    for row in rows:
        writer.writerow(row)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def register_prompts(prompt_paths: dict) -> dict:
    """Enregistre tous les prompts en DB. Retourne {agent_name: sha256_complet}."""
    hashes = {}
    with get_conn() as conn:
        for agent_name, path in prompt_paths.items():
            content   = load_prompt(path)
            sha       = hash_prompt(content)
            prompt_id = f"{agent_name}_{sha[:12]}"
            conn.execute("""
                INSERT OR IGNORE INTO prompts (
                    prompt_id, agent_name, version,
                    content, sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (prompt_id, agent_name, "v1", content, sha,
                  datetime.utcnow().isoformat()))
            hashes[agent_name] = sha
    return hashes


def verify_prompts_unchanged(prompt_paths: dict,
                              registered_hashes: dict) -> None:
    """Lève une RuntimeError si un prompt a changé depuis l'enregistrement."""
    for agent_name, path in prompt_paths.items():
        current  = hash_prompt(load_prompt(path))
        expected = registered_hashes.get(agent_name, "")
        if current != expected:
            raise RuntimeError(
                f"Prompt modifié : {agent_name}\n"
                f"  attendu : {expected[:16]}...\n"
                f"  actuel  : {current[:16]}..."
            )
```

---

## 5 bis. Abstraction d'inférence (`ModelProvider`) et politique de modèles

Les agents ne doivent **jamais** instancier `anthropic.Anthropic()` directement (Règle 11). Ils dépendent d'une interface commune `ModelProvider`, ce qui permet d'exécuter le **même** protocole avec Anthropic (Tier C, secondaire) ou un modèle local (Tier A/B, primaire).

```python
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
```

### Politique de modèles (gardes) — `utils/model_policy.py`

```python
# utils/model_policy.py
"""Gardes de la Règle 11 : exécutabilité par tier, admissibilité des claims primaires,
exigence d'artefacts pour un full run, et reporting/robustesse cross-modèle."""

TIER_OPEN = {"A_fully_open", "B_open_weight"}
_REQUIRED_FULL_RUN_ARTIFACTS = ("model_revision", "tokenizer_revision",
                                "weights_sha256", "tokenizer_sha256", "inference_env_hash")


def normalize_tier(tier: str) -> str:
    return {"A_or_B_open": "A_fully_open"}.get(tier, tier)


def validate_model_providers(config: dict, run_mode: str):
    """Vérifie la politique de tiers selon le run_mode.
      - dev   : aucun modèle ouvert requis (résultats non scientifiques).
      - pilot : au moins un modèle ouvert (Tier A/B) doit être déclaré.
      - full  : un primary_reproducible Tier A/B est OBLIGATOIRE, avec TOUS les artefacts
                d'archivage renseignés (révisions, hashes, env). Tier C ⇒ jamais primaire.
    Lève ValueError en cas de violation."""
    mp = config.get("model_providers", {})
    primary = mp.get("primary_reproducible")
    secondary = mp.get("secondary_proprietary")

    if secondary and normalize_tier(secondary.get("tier", "")) == "C_proprietary_api":
        if secondary.get("use_for_primary_claims", False):
            raise ValueError("secondary_proprietary (Tier C) ne peut pas avoir use_for_primary_claims=true (Règle 11).")

    if run_mode == "dev":
        return
    # pilot/full : il faut au moins un modèle ouvert
    open_models = []
    if primary and normalize_tier(primary.get("tier", "")) in TIER_OPEN:
        open_models.append(primary)
    for m in mp.get("optional_cross_model_replication", {}).get("models", []):
        if normalize_tier(m.get("tier", "")) in TIER_OPEN:
            open_models.append(m)
    if not open_models:
        raise ValueError(f"run_mode={run_mode} exige au moins un modèle ouvert (Tier A/B).")

    if run_mode == "full":
        if not primary or normalize_tier(primary.get("tier", "")) not in TIER_OPEN:
            raise ValueError("full run : primary_reproducible (Tier A/B) obligatoire.")
        missing = [k for k in _REQUIRED_FULL_RUN_ARTIFACTS
                   if not primary.get(k) or str(primary.get(k)).startswith("FILL")]
        if missing:
            raise ValueError(
                f"full run : artefacts d'archivage manquants pour le modèle primaire ouvert : {missing}. "
                f"Renseigner révisions/hashes/env avant le gel (Règle 11)."
            )


def assert_primary_claim_allowed(model_run: dict):
    """Garde du reporter : refuse de marquer une métrique comme claim PRIMAIRE si elle ne
    provient pas d'un modèle admissible (Tier A/B avec use_for_primary_claims=1)."""
    tier = normalize_tier(model_run.get("provider_tier", ""))
    if tier not in TIER_OPEN or not model_run.get("use_for_primary_claims"):
        raise ValueError(
            f"Claim primaire refusé : modèle {model_run.get('model_name')} "
            f"(tier={tier}, use_for_primary_claims={model_run.get('use_for_primary_claims')}). "
            f"Les claims primaires sont restreints aux modèles Tier A/B (Règle 11)."
        )


def classify_cross_model_effect(per_model: dict, threshold: float = 0.0) -> str:
    """Classe un effet à partir d'un dict {model_run_id: {'tier':…, 'significant':bool}}.
      - model-invariant : significatif sur ≥ 2 modèles (dont ≥ 1 ouvert)
      - open-model-only : significatif uniquement sur des modèles ouverts
      - proprietary-only: significatif uniquement sur des modèles propriétaires
      - unstable        : aucun des cas ci-dessus (effet non robuste)."""
    sig_open  = [m for m in per_model.values() if m["significant"] and normalize_tier(m["tier"]) in TIER_OPEN]
    sig_prop  = [m for m in per_model.values() if m["significant"] and normalize_tier(m["tier"]) == "C_proprietary_api"]
    n_sig = len(sig_open) + len(sig_prop)
    if n_sig >= 2 and sig_open:
        return "model-invariant"
    if sig_open and not sig_prop:
        return "open-model-only"
    if sig_prop and not sig_open:
        return "proprietary-only"
    return "unstable"
```

### Reporting par modèle et par tier

Le rapport final sépare **toujours** les métriques par modèle et par tier (jamais de fusion d'un score Tier C dans un score primaire). Tableau principal :

| Metric | Open-weight primary | Proprietary secondary | Difference | Interpretation |
| ------ | ------------------: | --------------------: | ---------: | -------------- |

Sont rapportés, par modèle : *causal validity primary score* (modèle ouvert), *causal validity secondary score* (Anthropic), couverture, utilité end-to-end, fidelity AUC, consistance, coût, runtime, et **reproducibility tier**. Une affirmation forte (« MorphoRepr outperforms NL labels ») n'est admissible que si elle est vraie sur le **modèle primaire ouvert** ; sinon elle est reformulée « in the proprietary reference condition » (Règle 11).

### Robustesse cross-modèle

Lorsque `optional_cross_model_replication.enabled=true`, le protocole calcule : stabilité des annotations entre modèles, stabilité des propriétés causales, variation du macro-F1 par modèle, corrélation des scores de validité causale, et différence open-weight primaire vs propriétaire secondaire. Chaque effet est ensuite classé par `classify_cross_model_effect` en **model-invariant**, **open-model-only**, **proprietary-only** ou **unstable**.

### Politique d'exécution par phase

- **Dev run** : Anthropic OU un petit modèle local ; résultats non scientifiques.
- **Pilot run** : doit inclure **au moins un modèle open-weight** ; Anthropic possible pour comparaison.
- **Full frozen run** : déclare un `primary_reproducible` (Tier A/B) ; les métriques **principales** sont calculées sur ce modèle ; Anthropic est **secondaire** ; si les conclusions diffèrent entre modèle ouvert et propriétaire, le papier doit le **rapporter explicitement**.

---

## 6. Classifieurs de propriétés de sortie

### 6.1 Négation (robuste)

```python
# classifiers/negation.py
import spacy

nlp = spacy.load("en_core_web_sm")

NEG_LEXICON = {
    "no","not","never","neither","nor","nobody","nothing",
    "nowhere","none","without","lack","lacking","absent",
    "fail","fails","failed","failure","missing","unable",
    "impossible","prevent","prevents","prevented","deny",
    "denies","denied","refuse","refuses","refused"
}
NEG_PREFIXES = ("un", "non", "dis", "mis")
# Préfixes morphologiques : signal FAIBLE et bruité (display, mission, discussion, union…).
# v6 : ils ne contribuent PLUS au score ROBUSTE de négation. Ils sont mesurés séparément
# comme "weak_morphological" (hors métrique primaire), pour analyse seulement.
# (v4 incluait aussi "a"/"in"/"im"/"il"/"ir" — faux positifs massifs, supprimés en v5.)

def count_negation_signals(text: str) -> float:
    """Signal ROBUSTE de négation : dépendance syntaxique 'neg' + lexique explicite UNIQUEMENT.
    Les préfixes morphologiques sont exclus (voir count_weak_morph_neg)."""
    doc    = nlp(text)
    tokens = [t for t in doc if not t.is_space]
    if not tokens:
        return 0.0
    score = 0.0
    for t in tokens:
        if t.dep_ == "neg":
            score += 1.0
        elif t.lower_ in NEG_LEXICON:
            score += 0.7
    return score / len(tokens)

def count_weak_morph_neg(text: str) -> float:
    """Signal FAIBLE morphologique (préfixes) — RAPPORTÉ HORS métrique robuste."""
    doc    = nlp(text)
    tokens = [t for t in doc if not t.is_space]
    if not tokens:
        return 0.0
    score = sum(
        0.3 for t in tokens
        if any(t.lower_.startswith(p) for p in NEG_PREFIXES) and len(t.text) > 4
    )
    return score / len(tokens)

def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before    = sum(count_negation_signals(t) for t in texts_before) / len(texts_before)
    after     = sum(count_negation_signals(t) for t in texts_after)  / len(texts_after)
    delta     = after - before
    # Signal faible morphologique : rapporté séparément, n'affecte PAS la direction robuste.
    weak_before = sum(count_weak_morph_neg(t) for t in texts_before) / len(texts_before)
    weak_after  = sum(count_weak_morph_neg(t) for t in texts_after)  / len(texts_after)
    THRESHOLD = 0.02
    return {
        "property":  "negation_presence",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "weak_morphological_delta": round(weak_after - weak_before, 4),
        "direction": ("INCREASE" if delta >  THRESHOLD else
                      "DECREASE" if delta < -THRESHOLD else
                      "NO_CHANGE")
    }
```

### 6.2 Valence émotionnelle (semi-robuste)

```python
# classifiers/valence.py
"""
Utilise cardiffnlp/twitter-roberta-base-sentiment-latest plutôt que SST-2.
SST-2 est entraîné sur des critiques de films et peu performant sur du texte
technique ou narratif. Le modèle Cardiff est plus robuste sur des domaines variés.
"""
from transformers import pipeline as hf_pipeline

_pipe = None

def get_pipe():
    global _pipe
    if _pipe is None:
        _pipe = hf_pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True,
            max_length=512,
            top_k=None          # renvoie la distribution complète des labels (pas le seul top)
        )
    return _pipe

def _neg_score(text: str) -> float:
    # Avec top_k=None, la pipeline renvoie la liste de tous les labels avec leur score.
    # On lit DIRECTEMENT le score du label 'negative' (au lieu d'approximer 1 - top_score,
    # qui surévaluait la négativité quand le top label était 'neutral').
    scores = get_pipe()(text)[0]
    for s in scores:
        if s["label"].lower() in ("negative", "neg", "label_0"):
            return float(s["score"])
    return 0.0

def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before    = sum(_neg_score(t) for t in texts_before) / len(texts_before)
    after     = sum(_neg_score(t) for t in texts_after)  / len(texts_after)
    delta     = after - before
    THRESHOLD = 0.05
    return {
        "property":         "negative_valence",
        "tier":             "semi-robust",
        "before":           round(before, 4),
        "after":            round(after, 4),
        "delta":            round(delta, 4),
        "direction":        ("INCREASE" if delta >  THRESHOLD else
                             "DECREASE" if delta < -THRESHOLD else
                             "NO_CHANGE"),
        "reliability_note": ("Semi-robuste : interpréter avec prudence sur du texte "
                             "technique, ironique ou à forte densité de code.")
    }
```

### 6.3 Calibration des classifieurs

```python
# classifiers/calibration/run_calibration.py
"""
Doit passer avant le pilot run. Toutes les propriétés robustes requièrent une calibration.
v6.1 : rapporte n, équilibre des classes, matrice de confusion, accuracy ET macro-F1, et
précision/rappel par direction ; BLOQUE sur le macro-F1 (pas seulement l'accuracy) ; archive
chaque rapport (avec dataset_hash) dans la table classifier_calibrations.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import uuid4

DIRECTIONS = ["INCREASE", "DECREASE", "NO_CHANGE"]


def _macro_f1(confusion: dict) -> tuple[float, dict]:
    per_dir = {}
    f1s = []
    for d in DIRECTIONS:
        tp = confusion[d][d]
        fp = sum(confusion[o][d] for o in DIRECTIONS if o != d)
        fn = sum(confusion[d][o] for o in DIRECTIONS if o != d)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_dir[d] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)}
        # n'inclure dans la moyenne que les classes présentes dans la vérité terrain
        if (tp + fn) > 0:
            f1s.append(f1)
    macro = sum(f1s) / len(f1s) if f1s else 0.0
    return macro, per_dir


def calibrate(measure_fn, test_file: str, property_name: str,
              model_version: str = "unknown",
              min_macro_f1: float = 0.80,
              min_accuracy: float = 0.85,
              persist_db: bool = True) -> dict:
    raw = Path(test_file).read_bytes()
    dataset_hash = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    n = len(data)
    class_balance = dict(Counter(ex["expected_direction"] for ex in data))
    confusion = {a: {b: 0 for b in DIRECTIONS} for a in DIRECTIONS}
    correct = 0
    for ex in data:
        pred = measure_fn([ex["text_before"]], [ex["text_after"]])["direction"]
        true = ex["expected_direction"]
        confusion[true][pred] += 1
        correct += int(pred == true)
    accuracy = correct / n if n else 0.0
    macro_f1, per_dir = _macro_f1(confusion)
    passed = (macro_f1 >= min_macro_f1) and (accuracy >= min_accuracy)
    report = {
        "property": property_name,
        "model_version": model_version,
        "dataset_hash": dataset_hash,
        "n": n,
        "class_balance": class_balance,
        "accuracy": round(accuracy, 3),
        "macro_f1": round(macro_f1, 3),
        "per_direction": per_dir,
        "confusion_matrix": confusion,
        "thresholds": {"min_macro_f1": min_macro_f1, "min_accuracy": min_accuracy},
        "passed": passed,
    }
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} {property_name}: acc={accuracy:.1%} macro-F1={macro_f1:.3f} "
          f"(n={n}, équilibre={class_balance})")
    Path("calibration/reports").mkdir(parents=True, exist_ok=True)
    Path(f"calibration/reports/{property_name}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    if persist_db:
        _persist_calibration(report)
    return report


def _persist_calibration(report: dict, run_id: str | None = None):
    """Archive un rapport de calibration dans la table classifier_calibrations."""
    from utils.db_utils import get_conn
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO classifier_calibrations (
                calibration_id, run_id, property, classifier_name, classifier_version,
                dataset_hash, n, class_balance_json, threshold_json,
                confusion_matrix_json, macro_f1, accuracy, passed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, report["property"], report["property"],
            report["model_version"], report["dataset_hash"], report["n"],
            json.dumps(report["class_balance"]), json.dumps(report["thresholds"]),
            json.dumps(report["confusion_matrix"]), report["macro_f1"],
            report["accuracy"], int(report["passed"]),
            datetime.utcnow().isoformat()
        ))


if __name__ == "__main__":
    from classifiers import negation, tense, code_presence, modality, valence

    reports = [
        calibrate(negation.measure,      "calibration/negation_test.json",
                  "negation_presence",    min_macro_f1=0.80, min_accuracy=0.85),
        calibrate(tense.measure,          "calibration/tense_test.json",
                  "tense",                min_macro_f1=0.80, min_accuracy=0.85),
        calibrate(code_presence.measure,  "calibration/code_presence_test.json",
                  "code_presence",        min_macro_f1=0.85, min_accuracy=0.90),
        calibrate(modality.measure,       "calibration/modality_test.json",
                  "conditional_modality", min_macro_f1=0.80, min_accuracy=0.85),
        calibrate(valence.measure,        "calibration/valence_test.json",
                  "negative_valence",     min_macro_f1=0.75, min_accuracy=0.80),
    ]
    if not all(r["passed"] for r in reports):
        raise SystemExit(
            "Calibration échouée (macro-F1 ou accuracy insuffisant) — "
            "corriger les classifieurs avant le pilot run."
        )
    print("\nTous les classifieurs calibrés (macro-F1 OK) — prêt pour le pilot run.")
```

---

## 7. Agent de steering — implémentation proxy open-weight et contrats restants

```python
# agents/steerer.py
"""
Phase 4 — Steering d'activation SAE.

steer_feature() est IMPLÉMENTÉ pour le CHEMIN PROXY OPEN-WEIGHT (TransformerLens + SAE Lens,
espace 'residual_add_decoder'). Les chemins nnsight / modèle de production NE SONT PAS
implémentés (NotImplementedError explicite), de même que l'espace 'sae_latent_clamp'.
run_intervention_controls() reste un CONTRAT. causal_scorer._load_pairs() est IMPLÉMENTÉ
(assemblage déterministe prédiction/observation, métrique primaire — Sections 8 et 27).
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


def run_intervention_controls(run_id: str, config: dict):
    """Phase 4 — CONTRÔLES D'INTERVENTION (contrat v6). Lit config['intervention_controls'].

    Désactivé par défaut (`run_in_pipeline: false`) → no-op avec avertissement, pour que le
    dev/pilot run ne soit pas bloqué tant que les contrôles ne sont pas implémentés. Mettre
    `run_in_pipeline: true` une fois implémentés ; tant que ce n'est pas fait et que c'est
    activé, lève NotImplementedError (comme steer_feature)."""
    ic = config.get("intervention_controls", {})
    if not ic.get("run_in_pipeline", False):
        logger.warning("p4_controls désactivé (intervention_controls.run_in_pipeline=false) — ignoré.")
        return
    enabled = [name for name, on in ic.items() if on and name != "run_in_pipeline"]
    raise NotImplementedError(
        "run_intervention_controls() non implémenté. Contrôles déclarés à implémenter : "
        + ", ".join(enabled) + ". "
        "Chaque contrôle (random_feature_same_layer, random_direction_same_norm, "
        "matched_activation_freq, negative_steering, prompt_only, diffmean_reft) doit "
        "produire des résultats scorés par le MÊME chemin déterministe que le traitement. "
        "Tant que non implémenté, garder run_in_pipeline=false."
    )
```

---

## 8. Baseline MorphoRepr mélangé

```python
# baselines/shuffled.py
"""
Contrôle MorphoRepr mélangé.
- Intra-split uniquement (pas de contamination croisée)
- Longueur d'expression appariée ±1 terme
- shuffle_id déterministe : {run_id}_{sha1(feature_uid)[:12]}_{shuffle_number}
  (fondé sur feature_uid, PAS feature_index — évite les collisions inter-couches, Règle 10)
- UNIQUE(run_id, feature_uid, shuffle_number) empêche les doublons
- Généré et évalué pour evaluation_split UNIQUEMENT
- Scoré par le MÊME chemin déterministe que le primaire (scored_by='deterministic') ;
  une fraction (llm_qualitative_audit_fraction) est marquée 'llm_qualitative' pour audit
- Répétitions agrégées avant calcul des IC
"""
import hashlib
import logging
import random
from datetime import datetime
from typing import Optional
from utils.db_utils import get_conn

logger = logging.getLogger(__name__)


def _count_terms(expression: str) -> int:
    return len([t for t in expression.split("+") if "·" in t])


def generate_shuffles(run_id: str, config: dict, n_repeats: Optional[int] = None):
    """Génère les annotations mélangées intra-split. Config passée explicitement.

    v6 : (a) ne génère QUE pour evaluation_split (pas tous les splits) ; (b) assigne
    scored_by ('deterministic' par défaut, 'llm_qualitative' pour une fraction d'audit
    = llm_qualitative_audit_fraction) ; (c) insère scored_by et feature_uid."""
    sc        = config["shuffle_control"]
    n_repeats = n_repeats if n_repeats is not None else sc["n_repeats"]
    max_diff  = sc["max_term_diff"]
    eval_split = sc.get("evaluation_split", "random")
    audit_frac = sc.get("llm_qualitative_audit_fraction", 0.0)
    seed      = config.get("seed", 42)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_uid,
                   f.feature_index,
                   f.split,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id = ?
              AND ao.agent_name = 'encoder'
              AND ao.run_number = 1
              AND ao.status = 'ok'
              AND f.split = ?
        """, (run_id, eval_split)).fetchall()

    features = []
    for r in rows:
        if r["expression"]:
            features.append({
                "feature_index": r["feature_index"],
                "feature_uid":   r["feature_uid"],
                "expression":    r["expression"],
                "n_terms":       _count_terms(r["expression"]),
            })

    rng     = random.Random(seed)
    inserts = []
    for feat in features:        # un seul split (eval_split) — pas de contamination croisée
        n_feat     = feat["n_terms"]
        candidates = [
            f for f in features
            if f["feature_uid"] != feat["feature_uid"]
            and abs(f["n_terms"] - n_feat) <= max_diff
        ]
        if len(candidates) < 3:
            logger.warning(
                f"Feature {feat['feature_uid']} : "
                f"seulement {len(candidates)} candidats pour shuffle"
            )
            continue
        uid_short = hashlib.sha1(feat["feature_uid"].encode()).hexdigest()[:12]
        for shuffle_num in range(1, n_repeats + 1):
            source     = rng.choice(candidates)
            shuffle_id = f"{run_id}_{uid_short}_{shuffle_num}"
            scored_by  = "llm_qualitative" if rng.random() < audit_frac else "deterministic"
            inserts.append({
                "shuffle_id":           shuffle_id,
                "feature_uid":          feat["feature_uid"],
                "feature_index":        feat["feature_index"],
                "shuffle_number":       shuffle_num,
                "source_feature_uid":   source["feature_uid"],
                "source_feature_index": source["feature_index"],
                "annotation":           source["expression"],
                "scored_by":            scored_by,
            })

    with get_conn() as conn:
        for s in inserts:
            conn.execute("""
                INSERT OR IGNORE INTO shuffle_controls (
                    shuffle_id, run_id, feature_uid, feature_index, shuffle_number,
                    source_feature_uid, source_feature_index, annotation,
                    causal_score, causal_outcome, scored_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """, (
                s["shuffle_id"], run_id,
                s["feature_uid"], s["feature_index"], s["shuffle_number"],
                s["source_feature_uid"], s["source_feature_index"],
                s["annotation"], s["scored_by"],
                datetime.utcnow().isoformat()
            ))

    logger.info(f"Shuffles générés : {len(inserts)} ({n_repeats}/feature, split={eval_split})")
```

---

## 8 bis. Scoreur causal déterministe (métrique primaire)

Implémente la métrique PRIMAIRE (Règle 8) : comparaison **déterministe** de la direction
prédite (par l'agent de prédiction, à partir de la seule expression) à la direction
**observée** (mesurée par les classifieurs pré-enregistrés), agrégée en **macro-F1 GLOBAL sur
tous les couples `(feature_uid, propriété robuste)`** — et NON par feature puis moyenné. Le
bootstrap est **clusterisé par feature** (l'unité de rééchantillonnage est `feature_uid`).

```python
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
```

---

## 8 bis. Prédicteurs de baselines (Option B) — `agents/baseline_predictor.py`

Pour rendre les comparaisons primaires exécutables (supériorité vs `nl_labels`, non-infériorité vs `semantic_regex`), il faut des **prédictions baselines** au même format que MorphoRepr, lues par `causal_scorer._load_pairs(run_id, base, …)` via les `agent_name` de `ACCEPTED_PREDICTOR_AGENTS`. Ce module produit ces `agent_outputs` à partir des **annotations baselines** déjà stockées dans la table `baselines`, en passant par le **provider primaire** (Règle 11) et des **prompts séparés** (aucune terminologie MorphoRepr). Le steering n'est **pas** refait : seul le chemin de *prédiction* diffère entre méthodes — c'est ce qui autorise la comparaison appariée.

```python
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
```

### Prompts séparés (terminologie propre à chaque baseline)

`prompts/predictor_nl_labels_v1.txt` — entrée = label naturel (+ exemples), sortie = directions robustes, **sans** demander d'annotation MorphoRepr :

```text
You are predicting the behavioural effect of steering (amplifying) a single sparse-autoencoder
feature inside a language model. You are given ONLY a natural-language label for that feature and,
optionally, a few top-activating text examples.

Your task: predict, for each of the four ROBUST behavioural properties below, the direction in
which the property will change in the model's output when this feature is steered UP (positive
magnitude) on neutral prompts, relative to the unsteered output.

Robust properties (predict ALL four):
- negation_presence: presence/quantity of explicit negation (no, not, never, ...).
- tense: shift toward past vs non-past tense.
- code_presence: presence of source-code / programming syntax.
- conditional_modality: presence of conditional/hypothetical modality (if, would, could, ...).

Allowed directions (exactly one per property):
- INCREASE  - the property becomes more present / stronger.
- DECREASE  - the property becomes less present / weaker.
- NO_CHANGE - no reliable change expected.

Rules:
- Base your prediction ONLY on the natural-language label (and examples if given). Do NOT invent a
  MorphoRepr expression and do NOT use any controlled-language formalism.
- If a property is genuinely unrelated to the label, predict NO_CHANGE - but never output UNKNOWN
  and never leave a property out.
- Output STRICT JSON only, no prose around it, in exactly this schema:

{
  "status": "ok",
  "method": "nl_labels",
  "predictions": [
    {"property": "negation_presence", "direction": "INCREASE", "confidence": 0.0, "rationale": "..."},
    {"property": "tense", "direction": "NO_CHANGE", "confidence": 0.0},
    {"property": "code_presence", "direction": "NO_CHANGE", "confidence": 0.0},
    {"property": "conditional_modality", "direction": "NO_CHANGE", "confidence": 0.0}
  ]
}

confidence is a number in [0,1]; rationale is optional and short.
```

`prompts/predictor_semantic_regex_v1.txt` — entrée = Semantic Regex (+ description), sortie = directions robustes, **sans** traduction en MorphoRepr :

```text
You are predicting the behavioural effect of steering (amplifying) a single sparse-autoencoder
feature inside a language model. You are given ONLY a Semantic Regex annotation of that feature
(in the Boggust et al. formalism) and, optionally, a short natural-language description.

Your task: predict, for each of the four ROBUST behavioural properties below, the direction in
which the property will change in the model's output when this feature is steered UP (positive
magnitude) on neutral prompts, relative to the unsteered output.

Robust properties (predict ALL four):
- negation_presence: presence/quantity of explicit negation (no, not, never, ...).
- tense: shift toward past vs non-past tense.
- code_presence: presence of source-code / programming syntax.
- conditional_modality: presence of conditional/hypothetical modality (if, would, could, ...).

Allowed directions (exactly one per property): INCREASE / DECREASE / NO_CHANGE.

Rules:
- Use ONLY the structure and tokens of the Semantic Regex to infer which observable properties the
  feature governs. Do NOT translate the regex into MorphoRepr or any other controlled language.
- If the regex says nothing about a property, predict NO_CHANGE - never output UNKNOWN and never
  omit a property.
- Output STRICT JSON only, no prose around it, in exactly this schema:

{
  "status": "ok",
  "method": "semantic_regex",
  "predictions": [
    {"property": "negation_presence", "direction": "INCREASE", "confidence": 0.0, "rationale": "..."},
    {"property": "tense", "direction": "NO_CHANGE", "confidence": 0.0},
    {"property": "code_presence", "direction": "NO_CHANGE", "confidence": 0.0},
    {"property": "conditional_modality", "direction": "NO_CHANGE", "confidence": 0.0}
  ]
}

confidence is a number in [0,1]; rationale is optional and short.
```

---

## 9. Tests unitaires

```python
# tests/conftest.py
import os
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """DB temporaire isolée injectée via env var. Aucune DB de production touchée."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MORPHOREPR_DB_PATH", str(db_path))
    schema = Path("db/schema.sql").read_text()
    conn   = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    return db_path


# ─────────────────────────────────────────────
# tests/test_parser.py
# ─────────────────────────────────────────────

import pytest
from utils.morphorepr_parser import (
    parse_expression, parse_word,
    is_valid_root, can_register_new_free_root
)


# Tous les exemples d'encodage du papier doivent parser correctement (cas mal/ne et infixes).
@pytest.mark.parametrize("word,root,prefixes,infixes,suffix", [
    ("ag-is",          "ag",   [],      [],      "-is"),
    ("mal-o",          "mal",  [],      [],      "-o"),   # mal comme RACINE
    ("ne-a",           "ne",   [],      [],      "-a"),   # ne comme RACINE
    ("mal-emo-a",      "emo",  ["mal"], [],      "-a"),   # mal comme PRÉFIXE
    ("ne-soc-a",       "soc",  ["ne"],  [],      "-a"),
    ("soc-ant-o",      "soc",  [],      ["ant"], "-o"),
    ("dat-ad-o",       "dat",  [],      ["ad"],  "-o"),
    ("ag-int-a",       "ag",   [],      ["int"], "-a"),
    ("pens-ad-is",     "pens", [],      ["ad"],  "-is"),
    ("mal-far-int-e",  "far",  ["mal"], ["int"], "-e"),
    ("mal-ne-o",       "ne",   ["mal"], [],      "-o"),   # préfixe mal + racine ne
])
def test_examples_from_paper(word, root, prefixes, infixes, suffix):
    t = parse_word(word, known_free_roots={"far", "pens"})
    assert t.is_valid, f"{word} devrait être valide : {t.parse_error}"
    assert t.root == root
    assert t.prefixes == prefixes
    assert t.infixes == infixes
    assert t.suffix == suffix


class TestParseWord:
    def test_verbal_simple(self):
        t = parse_word("ag-is")
        assert t.root == "ag" and t.suffix == "-is"
        assert t.suffix_type == "tense" and t.is_valid

    def test_prefix_root_suffix(self):
        t = parse_word("mal-emo-a")
        assert "mal" in t.prefixes
        assert t.root == "emo" and t.suffix == "-a"
        assert t.suffix_type == "syntactic" and t.is_valid

    def test_root_infix_suffix(self):
        t = parse_word("soc-ant-o")
        assert t.root == "soc" and "ant" in t.infixes and t.suffix == "-o"
        assert t.is_valid

    def test_sans_suffixe_invalide(self):
        t = parse_word("ag")
        assert not t.is_valid and t.parse_error is not None

    def test_racine_libre(self):
        t = parse_word("pens-is")
        assert t.root == "pens" and t.suffix == "-is" and t.is_valid


class TestParseExpression:
    def test_deux_termes_valides(self):
        e = parse_expression("0.86·mal-emo-a + 0.42·ne-soc-a")
        assert e.is_valid and len(e.terms) == 2
        assert e.roots == {"emo", "soc"}

    def test_ordre_decroissant_obligatoire(self):
        e = parse_expression("0.40·ag-is + 0.90·sci-o")
        assert not e.is_valid and "décroissant" in e.parse_error.lower()

    def test_coefficient_hors_plage(self):
        e = parse_expression("9.99·ag-is")
        assert not e.is_valid

    def test_expression_vide(self):
        assert not parse_expression("").is_valid


class TestRootValidation:
    def test_racine_libre_bien_formee_valide(self):
        assert is_valid_root("pens") and is_valid_root("far")

    def test_token_reserve_invalide_comme_racine(self):
        assert not is_valid_root("is")
        assert not is_valid_root("ad")
        assert not is_valid_root("pli")   # préfixe réservé, pas une racine

    def test_mal_ne_valides_comme_racines_predefinies(self):
        # mal et ne SONT des racines valides (prédéfinies)...
        assert is_valid_root("mal") and is_valid_root("ne")

    def test_mal_ne_non_enregistrables_comme_libres(self):
        # ...mais ne peuvent PAS être ré-enregistrées comme NOUVELLES racines libres.
        assert can_register_new_free_root("mal") is not None
        assert can_register_new_free_root("ne")  is not None

    def test_enregistrement_racine_libre_valide(self):
        assert can_register_new_free_root("pens") is None

    def test_enregistrement_token_reserve_rejete(self):
        assert can_register_new_free_root("ad") is not None

    def test_enregistrement_deja_enregistree_rejete(self):
        assert can_register_new_free_root("far", known_free_roots={"far"}) is not None

    def test_trop_long_rejete(self):
        assert not is_valid_root("toolong")
        assert can_register_new_free_root("toolong") is not None

    def test_majuscule_rejetee(self):
        assert not is_valid_root("Pens")
        assert can_register_new_free_root("Pens") is not None


# ─────────────────────────────────────────────
# tests/test_db.py
# ─────────────────────────────────────────────

import sqlite3
import pytest
from utils.db_utils import (
    load_features_not_processed, save_agent_output,
    register_batch, mark_batch_consumed, get_unconsumed_batch
)


def _inserer_run(conn, run_id="r1"):
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            proxy_model, started_at, completed_at, status,
            last_phase, total_cost_usd
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,'running',NULL,0.0)
    """, ("r1","abc","cfg","{}","v1","lh","ch",
          "{}",0,None,42,None,"2026-01-01T00:00:00"))


def _inserer_feature(conn, index=1, split="random"):
    conn.execute("""
        INSERT INTO features (
            feature_uid, model_name, sae_release, layer_index, hook_name,
            feature_index, split, nl_description, top_examples,
            score_interp, activation_freq,
            activation_p99, activation_mean, activation_std,
            layer, neuronpedia_url, loaded_at
        ) VALUES (?, 'gpt2', 'res-jb', 6, 'hook_resid_post',
                  ?, ?, 'desc','[]',0.8,0.5,2.1,0.8,0.4,'6','http://x',
                  '2026-01-01T00:00:00')
    """, (f"gpt2:res-jb:6:hook_resid_post:{index}", index, split))


def test_tous_features_en_attente_initialement(test_db):
    conn = sqlite3.connect(test_db)
    _inserer_run(conn)
    _inserer_feature(conn, 1)
    _inserer_feature(conn, 2)
    conn.commit(); conn.close()

    pending = load_features_not_processed("r1", "encoder", 1)
    assert len(pending) == 2


def test_encodage_partiel_laisse_reste(test_db):
    conn = sqlite3.connect(test_db)
    _inserer_run(conn)
    _inserer_feature(conn, 1)
    _inserer_feature(conn, 2)
    conn.commit(); conn.close()

    save_agent_output(
        "r1", 1, "encoder", 1, {"status": "encoded"},
        "raw", "ok", None, 100, 50, None, 0.001,
        feature_uid="gpt2:res-jb:6:hook_resid_post:1"
    )
    pending = load_features_not_processed("r1", "encoder", 1)
    assert [f["feature_index"] for f in pending] == [2]


def test_reprise_batch_apres_crash(test_db):
    conn = sqlite3.connect(test_db)
    _inserer_run(conn)
    conn.commit(); conn.close()

    register_batch("b1", "r1", "phase3", "encoder", 1, 100)   # → model_run_id legacy 'r1::legacy'
    assert get_unconsumed_batch("r1", "phase3", "encoder", 1, "r1::legacy") == "b1"

    mark_batch_consumed("b1")
    assert get_unconsumed_batch("r1", "phase3", "encoder", 1, "r1::legacy") is None


# ─────────────────────────────────────────────
# tests/test_shuffle_baseline.py
# ─────────────────────────────────────────────

import sqlite3
import pytest
from baselines.shuffled import generate_shuffles

# Config minimale pour les tests (generate_shuffles prend désormais la config en argument)
_CFG = {"shuffle_control": {"n_repeats": 10, "max_term_diff": 1,
                            "llm_qualitative_audit_fraction": 0.2,
                            "evaluation_split": "random"},
        "seed": 42}


def _setup_features_encodees(test_db, n=5, split="random"):
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            proxy_model, started_at, completed_at, status,
            last_phase, total_cost_usd
        ) VALUES ('r1','c','h','{}','v1','lh','ch','{}',0,NULL,42,NULL,
                  '2026-01-01',NULL,'running',NULL,0.0)
    """)
    # model_run legacy explicite (model_run_id NOT NULL sur agent_outputs, v6.5.1)
    conn.execute("""
        INSERT INTO model_runs (model_run_id, run_id, provider_name, provider_tier, backend,
            model_name, generation_params_json, created_at)
        VALUES ('r1::legacy','r1','legacy','C_proprietary_api',NULL,'legacy','{}','2026-01-01')
    """)
    for i in range(1, n + 1):
        conn.execute("""
            INSERT INTO features (
                feature_uid, model_name, sae_release, layer_index, hook_name,
                feature_index, split, nl_description, top_examples,
                score_interp, activation_freq,
                activation_p99, activation_mean, activation_std,
                layer, neuronpedia_url, loaded_at
            ) VALUES (?, 'gpt2', 'res-jb', 6, 'hook_resid_post',
                      ?, ?, 'd','[]',0.8,0.5,2.0,0.8,0.4,'6','http://x','2026-01-01')
        """, (f"gpt2:res-jb:6:hook_resid_post:{i}", i, split))
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, model_run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?,?,'r1::legacy',?,?,'encoder',1,?,?,?,NULL,100,50,NULL,0.0,
                      'confidence','2026-01-01')
        """, (
            f"o{i}", "r1", f"gpt2:res-jb:6:hook_resid_post:{i}", i,
            f'{{"status":"encoded","expression":"0.{i+5}0·ag-is"}}',
            "raw", "ok"
        ))
    conn.commit()
    conn.close()


def test_shuffle_pas_auto_assigne(test_db):
    """Un feature ne doit jamais recevoir sa propre annotation (comparaison sur feature_uid)."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", _CFG, n_repeats=3)
    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT feature_uid, source_feature_uid FROM shuffle_controls"
    ).fetchall()
    conn.close()
    assert all(r[0] != r[1] for r in rows)


def test_shuffle_contrainte_unicite(test_db):
    """La contrainte UNIQUE empêche les doublons logiques."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", _CFG, n_repeats=3)
    generate_shuffles("r1", _CFG, n_repeats=3)  # deuxième appel — pas de doublons
    conn = sqlite3.connect(test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM shuffle_controls WHERE run_id='r1'"
    ).fetchone()[0]
    conn.close()
    assert count <= 5 * 3   # max 15 entrées pour 5 features × 3 répétitions
```

```python
# ─────────────────────────────────────────────
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
# tests/test_causal_scorer.py  (v6.1)
# Prouve que le macro-F1 est GLOBAL sur couples, et que le bootstrap est clusterisé.
# ─────────────────────────────────────────────

from agents.causal_scorer import (compute_global_macro_f1,
                                   feature_clustered_bootstrap, paired_diff_bootstrap)


def test_macro_f1_global_pas_par_feature():
    """Le score est calculé sur l'ENSEMBLE des couples. Une feature avec une seule classe
    observée ne rend pas le score instable (contrairement à un macro-F1 par feature)."""
    pairs = [
        {"feature_uid": "u1", "property": "tense",            "predicted": "INCREASE",  "observed": "INCREASE"},
        {"feature_uid": "u1", "property": "negation_presence","predicted": "DECREASE",  "observed": "DECREASE"},
        {"feature_uid": "u2", "property": "tense",            "predicted": "NO_CHANGE", "observed": "NO_CHANGE"},
        {"feature_uid": "u2", "property": "code_presence",    "predicted": "INCREASE",  "observed": "INCREASE"},
    ]
    r = compute_global_macro_f1(pairs)
    assert r["n_pairs"] == 4
    assert r["macro_f1"] == 1.0 and r["accuracy"] == 1.0   # toutes les directions correctes


def test_macro_f1_penalise_erreurs():
    pairs = [
        {"feature_uid": "u1", "property": "tense",            "predicted": "INCREASE",  "observed": "INCREASE"},
        {"feature_uid": "u1", "property": "negation_presence","predicted": "INCREASE",  "observed": "DECREASE"},
        {"feature_uid": "u2", "property": "tense",            "predicted": "NO_CHANGE", "observed": "NO_CHANGE"},
    ]
    r = compute_global_macro_f1(pairs)
    assert 0.0 < r["macro_f1"] < 1.0


def test_bootstrap_clusterise_par_feature():
    pairs = [{"feature_uid": f"u{i}", "property": "tense",
              "predicted": "INCREASE", "observed": "INCREASE"} for i in range(20)]
    ci = feature_clustered_bootstrap(pairs, n_resamples=200, seed=1)
    assert ci["n_features"] == 20 and ci["ci_low"] <= ci["ci_high"]


def test_paired_diff_sur_features_partagees():
    a = [{"feature_uid": f"u{i}", "property": "tense", "predicted": "INCREASE",
          "observed": "INCREASE"} for i in range(10)]
    b = [{"feature_uid": f"u{i}", "property": "tense",
          "predicted": ("INCREASE" if i < 5 else "DECREASE"), "observed": "INCREASE"}
         for i in range(10)]
    d = paired_diff_bootstrap(a, b, n_resamples=200, seed=1)
    assert d["n_shared_features"] == 10 and d["diff"] > 0   # A (parfait) > B


# ─────────────────────────────────────────────
# v6.7.0 : _load_pairs() — assemblage réel prédiction/observation (métrique primaire)
# ─────────────────────────────────────────────
import json as _json
import sqlite3 as _sqlite3
import pytest as _pytest
import agents.causal_scorer as cs
from agents.causal_scorer import (
    _load_pairs, _extract_predicted_directions, _normalize_direction,
    _primary_magnitude_key, _observe_property_direction, run as causal_run,
)

_CFG_CAUSAL = {
    "primary_split": "random",
    "steering": {"magnitude_mode": "p99_relative", "primary_magnitude_rel": 1.0,
                 "legacy_absolute_magnitude": 5, "primary_probe_family": "neutral",
                 "exclude_ood_from_primary": True},
    "stats": {"bootstrap_resamples": 50, "superiority_vs": ["nl_labels"],
              "non_inferiority_vs": ["semantic_regex"]},
    "thresholds": {"nim_delta": 0.05},
    "causal_scoring": {"run_baseline_comparisons": False},
    "seed": 42,
}


def _mk_run(conn, run_id="r1"):
    conn.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,
        lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,started_at,
        completed_at,status,last_phase,total_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, 'c', 'h', '{}', 'v1', 'lh', 'ch', '{}', 0, None, 42, None,
         '2026-01-01', None, 'running', None, 0.0))


def _mk_model_run(conn, run_id, mrid, name="primary", tier="B_open_weight"):
    conn.execute("""INSERT INTO model_runs (model_run_id, run_id, provider_name, provider_tier,
        backend, model_name, generation_params_json, created_at)
        VALUES (?,?,?,?,?,?,'{}','2026-01-01')""", (mrid, run_id, "p", tier, "vllm", name))


def _mk_feature(conn, idx, split="random"):
    uid = f"gpt2:res-jb:6:hook_resid_post:{idx}"
    conn.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,
        feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,
        activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES
        (?, 'gpt2','res-jb',6,'hook_resid_post',?,?,'d','[]',0.8,0.5,2.0,0.8,0.4,'6','x','2026-01-01')""",
        (uid, idx, split))
    return uid


def _mk_prediction(conn, run_id, mrid, uid, idx, props, agent="predictor"):
    conn.execute("""INSERT INTO agent_outputs (output_id,run_id,model_run_id,feature_uid,feature_index,
        agent_name,run_number,output_json,raw_output,status,error_msg,tokens_input,tokens_output,
        batch_id,cost_usd,coefficient_type,created_at) VALUES
        (?,?,?,?,?,?,1,?,?,'ok',NULL,1,1,NULL,0.0,'confidence','2026-01-01')""",
        (f"p-{mrid}-{idx}-{agent}", run_id, mrid, uid, idx, agent,
         _json.dumps({"status": "ok", "properties": props}), "raw"))


def _mk_steer(conn, run_id, mrid, uid, idx, before, after, mag_key="rel:1.0",
              ood=0, gen=0, family="neutral", cat=None):
    conn.execute("""INSERT INTO steering_results (result_id,run_id,model_run_id,feature_uid,
        feature_index,intervention_space,magnitude,magnitude_rel,magnitude_key,probe_id,probe_family,
        probe_category,generation_index,text_before,text_after,layer,token_position,activation_before,
        activation_after,achieved_delta,ood_flag,created_at) VALUES
        (?,?,?,?,?, 'residual_add_decoder', 2.0, 1.0, ?, ?, ?, ?, ?, ?, ?, '6','all',1.0,2.0,1.0,?,'2026-01-01')""",
        (f"s-{mrid}-{idx}-{gen}-{family}-{cat}", run_id, mrid, uid, idx, mag_key, idx, family, cat,
         gen, before, after, ood))


# 1-3. Extraction / normalisation des directions prédites
def test_extract_predictions_canonical():
    out = _extract_predicted_directions({"status": "ok", "predictions": [
        {"property": "negation_presence", "direction": "increase", "confidence": 0.8},
        {"property": "tense", "direction": "NO_CHANGE"}]})
    assert out == {"negation_presence": "INCREASE", "tense": "NO_CHANGE"}


def test_extract_predictions_dict_and_objects():
    assert _extract_predicted_directions(
        {"properties": {"negation_presence": "increase", "tense": "down"}}
    ) == {"negation_presence": "INCREASE", "tense": "DECREASE"}
    assert _extract_predicted_directions(
        {"properties": {"negation_presence": {"direction": "INCREASE", "confidence": 0.8}}}
    ) == {"negation_presence": "INCREASE"}


def test_extract_rejects_invalid_directions():
    out = _extract_predicted_directions({"properties": {
        "negation_presence": "UNKNOWN", "tense": None, "code_presence": "",
        "conditional_modality": "increase"}})
    assert out == {"conditional_modality": "INCREASE"}     # seules les directions valides retenues
    assert _normalize_direction("UNKNOWN") is None
    assert _normalize_direction(None) is None and _normalize_direction("") is None


# 4. Observation via classifieur déterministe
def test_observe_property_direction():
    rows = [{"text_before": "a", "text_after": "b"}, {"text_before": "c", "text_after": "d"},
            {"text_before": None, "text_after": "x"}]
    obs = _observe_property_direction(rows, "tense", lambda tb, ta: {"direction": "INCREASE"})
    assert obs["direction"] == "INCREASE" and obs["n_observations"] == 2   # paire None ignorée


def test_observe_invalid_direction_raises():
    with _pytest.raises(ValueError):
        _observe_property_direction([{"text_before": "a", "text_after": "b"}], "tense",
                                    lambda tb, ta: {"direction": "WUT"})


# 5. Clé de magnitude primaire
def test_primary_magnitude_key():
    assert _primary_magnitude_key({"steering": {"magnitude_mode": "p99_relative",
                                                 "primary_magnitude_rel": 1.0}}) == "rel:1.0"
    assert _primary_magnitude_key({"steering": {"magnitude_mode": "absolute",
                                                 "legacy_absolute_magnitude": 5}}) == "abs:5"


# 6. OOD exclu/inclus selon la config
def test_load_pairs_ood_filter(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", uid, 1, {"negation_presence": "INCREASE"})
    _mk_steer(conn, "r1", "mrP", uid, 1, "x", "y", ood=0, gen=0)
    _mk_steer(conn, "r1", "mrP", uid, 1, "x2", "y2", ood=1, gen=1)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    p1 = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert len(p1) == 1 and p1[0]["n_observations"] == 1           # OOD exclu
    cfg2 = _json.loads(_json.dumps(_CFG_CAUSAL)); cfg2["steering"]["exclude_ood_from_primary"] = False
    p2 = _load_pairs("r1", "morphorepr", config=cfg2, model_run_id="mrP", split="random")
    assert p2[0]["n_observations"] == 2                            # OOD inclus


# 7. Strictement model-aware
def test_load_pairs_model_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn)
    _mk_model_run(conn, "r1", "mrP", "primary"); _mk_model_run(conn, "r1", "mrS", "secondary", "C_proprietary_api")
    uid = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", uid, 1, {"negation_presence": "INCREASE"})
    _mk_prediction(conn, "r1", "mrS", uid, 1, {"negation_presence": "DECREASE"})
    _mk_steer(conn, "r1", "mrP", uid, 1, "a", "b")
    _mk_steer(conn, "r1", "mrS", uid, 1, "c", "d")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert len(pairs) == 1 and pairs[0]["model_run_id"] == "mrP" and pairs[0]["predicted"] == "INCREASE"
    # le primaire ne charge jamais la prédiction DECREASE du secondaire


# 8. Strictement split-aware
def test_load_pairs_split_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    ur = _mk_feature(conn, 1, "random"); ue = _mk_feature(conn, 2, "easy")
    _mk_prediction(conn, "r1", "mrP", ur, 1, {"tense": "INCREASE"})
    _mk_prediction(conn, "r1", "mrP", ue, 2, {"tense": "INCREASE"})
    _mk_steer(conn, "r1", "mrP", ur, 1, "a", "b"); _mk_steer(conn, "r1", "mrP", ue, 2, "c", "d")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"tense": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert {p["feature_uid"] for p in pairs} == {ur}               # easy exclu


# 9-10. Absences explicites
def test_load_pairs_no_steering_raises(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random"); _mk_prediction(conn, "r1", "mrP", uid, 1, {"tense": "INCREASE"})
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"tense": lambda tb, ta: {"direction": "INCREASE"}})
    with _pytest.raises(RuntimeError, match="p4_steer"):
        _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")


def test_load_pairs_no_predictor_raises(test_db):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random"); _mk_steer(conn, "r1", "mrP", uid, 1, "a", "b")
    conn.commit(); conn.close()
    with _pytest.raises(RuntimeError, match="No predictor outputs"):
        _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")


def test_load_pairs_unknown_method_raises():
    with _pytest.raises(NotImplementedError):
        _load_pairs("r1", "does_not_exist", config=_CFG_CAUSAL, model_run_id="mrP")


# 11. Couple final assemblé
def test_load_pairs_assembles_pair(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    uid = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", uid, 1, {"negation_presence": "INCREASE"})
    _mk_steer(conn, "r1", "mrP", uid, 1, "no problems", "not a problem, no issues")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {
        "negation_presence": lambda tb, ta: {"property": "negation_presence", "direction": "INCREASE"}})
    pairs = _load_pairs("r1", "morphorepr", config=_CFG_CAUSAL, model_run_id="mrP", split="random")
    assert len(pairs) == 1
    p = pairs[0]
    assert (p["predicted"] == "INCREASE" and p["observed"] == "INCREASE"
            and p["property"] == "negation_presence" and p["method"] == "morphorepr")


# 12-13. run() minimal : métrique écrite avec model_run_id ; baselines non comparées (run_baseline_comparisons=false)
def test_run_minimal_writes_metric_and_skips_baselines(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):
        uid = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", uid, i, {"negation_presence": "INCREASE"})
        _mk_steer(conn, "r1", "mrP", uid, i, "a", "b")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY",
                        {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    cfg = _json.loads(_json.dumps(_CFG_CAUSAL))
    cfg["_runtime"] = {"model_run_ids": {"primary": "mrP"}}        # run() lit le primaire
    res = causal_run("r1", cfg)
    assert res["morphorepr"]["macro_f1"] == 1.0                    # toutes prédictions == observations
    assert res["comparisons"] == {}                                # run_baseline_comparisons=false : aucune comparaison
    conn = _sqlite3.connect(test_db)
    row = conn.execute("""SELECT model_run_id, split FROM metrics
                          WHERE metric_name='causal_macro_f1_global'""").fetchone()
    n_diff = conn.execute("""SELECT COUNT(*) FROM metrics
                             WHERE metric_name='causal_macro_f1_paired_diff'""").fetchone()[0]
    conn.close()
    assert row[0] == "mrP" and row[1] == "random"                  # metrics.model_run_id renseigné
    assert n_diff == 0                                             # aucun verdict baseline (pas de faux pass/fail)
```

```python
# ─────────────────────────────────────────────
# tests/test_baseline_predictions.py  (v6.8.0 — prédictions baselines Option B)
# nl_labels (supériorité) et semantic_regex (non-infériorité). Tout est déterministe : le provider
# primaire et/ou la prédiction sont monkeypatchés, et les classifieurs via cs.CLASSIFIER_BY_PROPERTY.
# ─────────────────────────────────────────────
import json as _json
import sqlite3 as _sqlite3
import pytest as _pytest
import agents.baseline_predictor as bp
import agents.causal_scorer as cs
from agents.baseline_predictor import (run as bp_run, _parse_prediction_response,
                                       _load_baseline_annotations)
from agents.causal_scorer import (_load_pairs, run as causal_run,
                                  assert_baseline_predictions_ready, _extract_predicted_directions)

_CFG_BP = {
    "primary_split": "random",
    "prompts": {"predictor_nl_labels": "prompts/predictor_nl_labels_v1.txt",
                "predictor_semantic_regex": "prompts/predictor_semantic_regex_v1.txt"},
    "model_providers": {"primary_reproducible": {"backend": "vllm", "model_name": "m",
                                                 "generation_params": {"temperature": 0.0}}},
    "baseline_predictions": {"enabled": True, "methods": ["nl_labels", "semantic_regex"],
                             "run_number": 1, "require_existing_baseline_annotations": True,
                             "skip_missing_annotations": False},
    "steering": {"magnitude_mode": "p99_relative", "primary_magnitude_rel": 1.0,
                 "primary_probe_family": "neutral", "exclude_ood_from_primary": True,
                 "intervention_space": "residual_add_decoder"},
    "stats": {"bootstrap_resamples": 50, "superiority_vs": ["nl_labels"],
              "non_inferiority_vs": ["semantic_regex"]},
    "thresholds": {"nim_delta": 0.05},
    "causal_scoring": {"run_baseline_comparisons": True, "strict_baselines": True},
    "seed": 42,
    "_runtime": {"model_run_ids": {"primary": "mrP"}},
}


class _FakeProvider:
    """Provider déterministe : renvoie un JSON canonique (négation INCREASE, reste NO_CHANGE)."""
    def __init__(self, direction="INCREASE"): self.direction = direction
    def generate(self, messages, system_prompt, max_tokens, generation_params):
        return _json.dumps({"status": "ok", "method": "x", "predictions": [
            {"property": "negation_presence", "direction": self.direction, "confidence": 0.8},
            {"property": "tense", "direction": "NO_CHANGE", "confidence": 0.5},
            {"property": "code_presence", "direction": "NO_CHANGE", "confidence": 0.5},
            {"property": "conditional_modality", "direction": "NO_CHANGE", "confidence": 0.5}]})


def _mk_run(conn, run_id="r1"):
    conn.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,
        lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,started_at,
        completed_at,status,last_phase,total_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, 'c', 'h', '{}', 'v1', 'lh', 'ch', '{}', 0, None, 42, None, '2026-01-01', None,
         'running', None, 0.0))


def _mk_model_run(conn, run_id, mrid, name="primary", tier="B_open_weight"):
    conn.execute("""INSERT INTO model_runs (model_run_id, run_id, provider_name, provider_tier,
        backend, model_name, generation_params_json, created_at)
        VALUES (?,?,?,?,?,?,'{}','2026-01-01')""", (mrid, run_id, "p", tier, "vllm", name))


def _mk_feature(conn, idx, split="random"):
    uid = f"gpt2:res-jb:6:hook_resid_post:{idx}"
    conn.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,
        feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,
        activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES
        (?, 'gpt2','res-jb',6,'hook_resid_post',?,?,'a feature about negation','[]',0.8,0.5,2.0,0.8,0.4,'6','x','2026-01-01')""",
        (uid, idx, split))
    return uid


def _mk_baseline(conn, run_id, mrid, uid, idx, name, annot="negation label"):
    conn.execute("""INSERT INTO baselines (baseline_id,run_id,model_run_id,feature_uid,feature_index,
        baseline_name,annotation_run1,created_at) VALUES (?,?,?,?,?,?,?,'2026-01-01')""",
        (f"b-{mrid}-{idx}-{name}", run_id, mrid, uid, idx, name, annot))


def _mk_prediction(conn, run_id, mrid, uid, idx, props, agent):
    conn.execute("""INSERT INTO agent_outputs (output_id,run_id,model_run_id,feature_uid,feature_index,
        agent_name,run_number,output_json,raw_output,status,error_msg,tokens_input,tokens_output,
        batch_id,cost_usd,coefficient_type,created_at) VALUES
        (?,?,?,?,?,?,1,?,?,'ok',NULL,1,1,NULL,0.0,'confidence','2026-01-01')""",
        (f"p-{mrid}-{idx}-{agent}", run_id, mrid, uid, idx, agent,
         _json.dumps({"status": "ok", "method": agent, "predictions":
                      [{"property": k, "direction": v} for k, v in props.items()]}), "raw"))


def _mk_steer(conn, run_id, mrid, uid, idx, before="a", after="b"):
    conn.execute("""INSERT INTO steering_results (result_id,run_id,model_run_id,feature_uid,
        feature_index,intervention_space,magnitude,magnitude_rel,magnitude_key,probe_id,probe_family,
        probe_category,generation_index,text_before,text_after,layer,token_position,activation_before,
        activation_after,achieved_delta,ood_flag,created_at) VALUES
        (?,?,?,?,?, 'residual_add_decoder', 2.0, 1.0, 'rel:1.0', ?, 'neutral', NULL, 0, ?, ?,
         '6','all',1.0,2.0,1.0,0,'2026-01-01')""",
        (f"s-{mrid}-{idx}", run_id, mrid, uid, idx, idx, before, after))


# 1. Chargement des annotations baselines (model/split-aware)
def test_load_baseline_annotations(test_db):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random")
    _mk_baseline(conn, "r1", "mrP", u, 1, "nl_labels", "a negation label")
    _mk_baseline(conn, "r1", "mrP", u, 1, "semantic_regex", "/(no|not)/")
    conn.commit(); conn.close()
    nl = _load_baseline_annotations("r1", "mrP", "nl_labels", "random")
    sr = _load_baseline_annotations("r1", "mrP", "semantic_regex", "random")
    assert len(nl) == 1 and nl[0]["annotation"] == "a negation label"
    assert len(sr) == 1 and sr[0]["annotation"] == "/(no|not)/"


# 2-3. Sauvegarde prédiction nl_labels + format accepté par _extract_predicted_directions
def test_bp_saves_nl_prediction_canonical(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random"); _mk_baseline(conn, "r1", "mrP", u, 1, "nl_labels")
    conn.commit(); conn.close()
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider("INCREASE"))
    monkeypatch.setattr(bp, "load_prompt", lambda p: "SYS")          # pas de fichier en test
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["baseline_predictions"]["methods"] = ["nl_labels"]
    summary = bp_run("r1", cfg)
    assert summary["nl_labels"]["ok"] == 1 and summary["nl_labels"]["error"] == 0
    conn = _sqlite3.connect(test_db); conn.row_factory = _sqlite3.Row
    row = conn.execute("""SELECT agent_name, model_run_id, feature_uid, status, output_json
                          FROM agent_outputs WHERE agent_name='predictor_nl_labels'""").fetchone()
    conn.close()
    assert row["agent_name"] == "predictor_nl_labels" and row["model_run_id"] == "mrP"
    assert row["feature_uid"] == u and row["status"] == "ok"
    dirs = _extract_predicted_directions(row["output_json"])        # format canonique accepté
    assert dirs["negation_presence"] == "INCREASE"


# 4. Sauvegarde prédiction semantic_regex
def test_bp_saves_semantic_regex_prediction(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random"); _mk_baseline(conn, "r1", "mrP", u, 1, "semantic_regex", "/(no|not)/")
    conn.commit(); conn.close()
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider("INCREASE"))
    monkeypatch.setattr(bp, "load_prompt", lambda p: "SYS")
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["baseline_predictions"]["methods"] = ["semantic_regex"]
    bp_run("r1", cfg)
    conn = _sqlite3.connect(test_db)
    n = conn.execute("""SELECT COUNT(*) FROM agent_outputs
                        WHERE agent_name='predictor_semantic_regex' AND status='ok'""").fetchone()[0]
    conn.close()
    assert n == 1


# 5. Absence d'annotation + require_existing_baseline_annotations=true → RuntimeError (pas de prédiction factice)
def test_bp_missing_annotations_raises(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    _mk_feature(conn, 1, "random"); conn.commit(); conn.close()      # AUCUNE ligne baselines
    monkeypatch.setattr(bp, "_build_primary_provider", lambda cfg: _FakeProvider())
    monkeypatch.setattr(bp, "load_prompt", lambda p: "SYS")
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["baseline_predictions"]["methods"] = ["nl_labels"]
    with _pytest.raises(RuntimeError, match="No baseline annotations"):
        bp_run("r1", cfg)
    conn = _sqlite3.connect(test_db)
    assert conn.execute("SELECT COUNT(*) FROM agent_outputs").fetchone()[0] == 0   # rien de fabriqué
    conn.close()


# 6. assert_baseline_predictions_ready : passe si prédictions présentes, échoue sinon
def test_assert_baseline_predictions_ready(test_db):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random"); _mk_baseline(conn, "r1", "mrP", u, 1, "nl_labels")
    conn.commit()
    with _pytest.raises(RuntimeError, match="non prête"):            # pas encore de prédiction
        assert_baseline_predictions_ready("r1", "mrP", ["nl_labels"], "random")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    conn.commit(); conn.close()
    assert_baseline_predictions_ready("r1", "mrP", ["nl_labels"], "random")   # passe désormais


# 7-8. _load_pairs sur les baselines
def test_load_pairs_nl_and_semantic(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    u = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_semantic_regex")
    _mk_steer(conn, "r1", "mrP", u, 1); conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    for method in ("nl_labels", "semantic_regex"):
        pairs = _load_pairs("r1", method, config=_CFG_BP, model_run_id="mrP", split="random")
        assert len(pairs) == 1 and pairs[0]["predicted"] == "INCREASE" and pairs[0]["method"] == method


# 9. run() avec comparaisons activées : scores + paired diff + verdicts
def test_run_with_baseline_comparisons(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):
        u = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor")               # MorphoRepr
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "DECREASE"}, "predictor_nl_labels")     # NL (faux)
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_semantic_regex")# SemReg (vrai)
        _mk_steer(conn, "r1", "mrP", u, i)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    res = causal_run("r1", _json.loads(_json.dumps(_CFG_BP)))
    assert res["morphorepr"]["macro_f1"] == 1.0
    assert res["baseline_scores"]["nl_labels"]["macro_f1"] == 0.0          # NL tout faux
    assert res["baseline_scores"]["semantic_regex"]["macro_f1"] == 1.0     # SemReg tout vrai
    assert res["comparisons"]["nl_labels"]["mode"] == "superiority" and res["comparisons"]["nl_labels"]["verdict"] == "pass"
    assert res["comparisons"]["semantic_regex"]["mode"] == "non_inferiority" and res["comparisons"]["semantic_regex"]["verdict"] == "pass"
    assert res["comparisons"]["nl_labels"]["coverage"]["n_shared_features"] == 3
    conn = _sqlite3.connect(test_db)
    n_global = conn.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='causal_macro_f1_global'").fetchone()[0]
    n_diff = conn.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='causal_macro_f1_paired_diff'").fetchone()[0]
    null_mrid = conn.execute("SELECT COUNT(*) FROM metrics WHERE model_run_id IS NULL").fetchone()[0]
    conn.close()
    assert n_global == 3 and n_diff == 2 and null_mrid == 0   # MorphoRepr + 2 baselines ; 2 paired diff ; jamais NULL


# 10. Baseline absente + comparaisons activées : strict raise / non-strict skip SANS verdict
def test_run_missing_baseline_no_false_verdict(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):
        u = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_semantic_regex")
        _mk_steer(conn, "r1", "mrP", u, i)                       # NL ABSENT
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    strict = _json.loads(_json.dumps(_CFG_BP))                  # strict_baselines=true
    with _pytest.raises(RuntimeError, match="non prête"):
        causal_run("r1", strict)
    lax = _json.loads(_json.dumps(_CFG_BP)); lax["causal_scoring"]["strict_baselines"] = False
    res = causal_run("r1", lax)
    assert "nl_labels" not in res["comparisons"]                # skip sans verdict
    assert res["comparisons"]["semantic_regex"]["verdict"] in ("pass", "fail")


# 11. model-aware : le primaire ne charge pas les prédictions baselines du secondaire
def test_baseline_load_pairs_model_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn)
    _mk_model_run(conn, "r1", "mrP", "primary"); _mk_model_run(conn, "r1", "mrS", "sec", "C_proprietary_api")
    u = _mk_feature(conn, 1, "random")
    _mk_prediction(conn, "r1", "mrP", u, 1, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    _mk_prediction(conn, "r1", "mrS", u, 1, {"negation_presence": "DECREASE"}, "predictor_nl_labels")
    _mk_steer(conn, "r1", "mrP", u, 1); _mk_steer(conn, "r1", "mrS", u, 1)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "nl_labels", config=_CFG_BP, model_run_id="mrP", split="random")
    assert len(pairs) == 1 and pairs[0]["predicted"] == "INCREASE"   # jamais la prédiction DECREASE du secondaire


# 12. split-aware : split=random ne charge que random
def test_baseline_load_pairs_split_aware(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    ur = _mk_feature(conn, 1, "random"); ue = _mk_feature(conn, 2, "easy")
    for u, i in ((ur, 1), (ue, 2)):
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
        _mk_steer(conn, "r1", "mrP", u, i)
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    pairs = _load_pairs("r1", "nl_labels", config=_CFG_BP, model_run_id="mrP", split="random")
    assert {p["feature_uid"] for p in pairs} == {ur}


# 13. couverture : comparaison appariée sur features partagées uniquement
def test_baseline_coverage_shared_features(test_db, monkeypatch):
    conn = _sqlite3.connect(test_db); _mk_run(conn); _mk_model_run(conn, "r1", "mrP")
    for i in (1, 2, 3):                                          # MorphoRepr sur 3 features
        u = _mk_feature(conn, i, "random")
        _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor")
        _mk_steer(conn, "r1", "mrP", u, i)
        if i < 3:                                                # NL seulement sur 2 features
            _mk_prediction(conn, "r1", "mrP", u, i, {"negation_presence": "INCREASE"}, "predictor_nl_labels")
    conn.commit(); conn.close()
    monkeypatch.setattr(cs, "CLASSIFIER_BY_PROPERTY", {"negation_presence": lambda tb, ta: {"direction": "INCREASE"}})
    cfg = _json.loads(_json.dumps(_CFG_BP)); cfg["stats"]["non_inferiority_vs"] = []   # NL seul
    res = causal_run("r1", cfg)
    cov = res["comparisons"]["nl_labels"]["coverage"]
    assert cov["morphorepr_pairs"] == 3 and cov["baseline_pairs"] == 2 and cov["n_shared_features"] == 2
```

```python
# ─────────────────────────────────────────────
# tests/test_batch_custom_id.py  (v6.2)
# Les custom_id Batch API doivent être uniques même si feature_index est répété entre couches.
# ─────────────────────────────────────────────

from utils.api_utils import feature_custom_id, build_custom_id_map, build_batch_item_rows


def test_batch_custom_id_unique_with_same_feature_index():
    features = [
        {"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
        {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123},
    ]
    ids = [feature_custom_id(f) for f in features]
    assert len(ids) == len(set(ids))            # pas de collision


def test_custom_id_map_recupere_feature_uid():
    features = [
        {"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
        {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123},
    ]
    m = build_custom_id_map(features)
    assert m[feature_custom_id(features[0])] == "gpt2:res-jb:6:hook_resid_post:123"
    assert m[feature_custom_id(features[1])] == "gpt2:res-jb:9:hook_resid_post:123"


def test_submit_rejette_batch_items_incoherents():
    """Pré-vérification AVANT soumission : si les custom_id des requests ≠ batch_items,
    submit_and_poll_batch lève ValueError (avant tout appel réseau, donc avant facturation)."""
    import pytest
    from utils.api_utils import submit_and_poll_batch
    feats = [{"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
             {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123}]
    requests = [{"custom_id": feature_custom_id(f), "params": {}} for f in feats]
    items    = build_batch_item_rows(feats[:1])   # incomplet : il manque la 2ᵉ feature
    with pytest.raises(ValueError):
        submit_and_poll_batch(requests, "r1", "p3", "encoder", 1, "m", {}, batch_items=items)
```

```python
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
```

```python
# ─────────────────────────────────────────────
# tests/test_model_run_propagation.py  (v6.5.1 — propagation effective de model_run_id)
# ─────────────────────────────────────────────

import sqlite3
import pytest
from utils.db_utils import (register_model_run, register_batch_with_items, get_unconsumed_batch,
                            save_agent_output, log_api_cost, load_batch_item_map)
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
```

```python
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
```

---

## 10. Orchestrateur

```python
# orchestrator.py
"""
Orchestrateur MorphoRepr v6.8.0 — run gelé et auditable.

Usage :
    python orchestrator.py --config configs/run_v1.yaml
    python orchestrator.py --config configs/dev_run.yaml --n-features 5
    python orchestrator.py --config configs/run_v1.yaml --resume --run-id abc12345
"""
import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Créer logs/ AVANT basicConfig : sinon FileHandler("logs/pipeline.log") échoue à l'import
# (avant même d'entrer dans run_pipeline qui créait le dossier trop tard).
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("orchestrator")

from utils.config_utils import load_config, hash_config
from utils.prompt_utils import (register_prompts, verify_prompts_unchanged,
                                 hash_lexicon_canonical, hash_corpus_canonical)
from utils.db_utils import get_conn, check_budget, register_model_run, restore_model_run_ids

from agents import loader, ranker, cluster, labeler, consistency
from agents import encoder, fidelity, steerer, predictor, causal_scorer, reporter
from agents import baseline_predictor          # prédictions baselines Option B (v6.8.0)
from agents import qualitative_judge          # juge LLM — analyses SECONDAIRES uniquement
from baselines import shuffled as shuffled_baseline


def parse_args():
    p = argparse.ArgumentParser(description="Pipeline MorphoRepr")
    p.add_argument("--config",     required=True)
    p.add_argument("--n-features", type=int, default=None)
    p.add_argument("--resume",     action="store_true")
    p.add_argument("--run-id",     default=None)
    return p.parse_args()


def get_git_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def initialize_run(config: dict, args) -> str:
    git_commit  = get_git_commit()
    config_hash = hash_config(args.config)

    config_commit = config.get("git_commit", "FILL_BEFORE_LAUNCH")
    if config_commit == "FILL_BEFORE_LAUNCH":
        # Le run gelé (run_v1) DOIT épingler le commit. Seuls les dev runs peuvent
        # lever cette exigence via allow_unpinned_commit: true.
        if not config.get("allow_unpinned_commit", False):
            raise RuntimeError(
                "git_commit vaut encore 'FILL_BEFORE_LAUNCH'. Épingler le commit "
                "(git_commit: <HEAD>) dans la config avant le run gelé, ou mettre "
                "allow_unpinned_commit: true pour un dev run."
            )
        logger.warning("git_commit non épinglé (dev run) — provenance non gelée.")
    elif config_commit != git_commit:
        raise RuntimeError(
            f"git_commit dans la config ({config_commit[:8]}) ne correspond pas "
            f"au HEAD courant ({git_commit[:8]}). "
            f"Mettre à jour configs/run_v1.yaml avant le lancement."
        )

    prompt_hashes = register_prompts(config["prompts"])
    lexicon_hash  = hash_lexicon_canonical("db/lexicon.json")
    # Le hash du corpus est GELÉ APRÈS p1_load/p1_rank (qui peuplent et stratifient la table
    # features) — sinon il ne refléterait pas le corpus réellement utilisé. NULL = en attente ;
    # freeze_corpus_hash() le renseigne (phase p1_freeze_corpus).
    corpus_hash   = None

    run_id   = f"{config.get('run_id_prefix','run')}_{uuid4().hex[:8]}"
    sampling = config.get("sampling", {})
    proxy    = config.get("proxy_model", {})

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO runs (
                run_id, git_commit, config_hash, prompt_hashes,
                lexicon_version, lexicon_hash, corpus_hash,
                models_json, use_temperature, temperature, seed,
                proxy_model, started_at, completed_at, status,
                last_phase, total_cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'loading', NULL, 0.0)
        """, (
            run_id, git_commit, config_hash,
            json.dumps(prompt_hashes),
            config["lexicon_version"], lexicon_hash, corpus_hash,
            json.dumps(config["models"]),
            int(sampling.get("use_temperature", False)),
            sampling.get("temperature"),
            config.get("seed"),
            proxy.get("name") if proxy.get("enabled") else None,
            datetime.utcnow().isoformat()
        ))

    # Enregistrer les model_runs (Règle 11) et mémoriser leurs ids pour les agents.
    # Le modèle primaire ouvert porte is_primary_scientific=1 ; Anthropic reste secondaire.
    _register_model_runs(run_id, config)

    logger.info(f"Run initialisé : {run_id}")
    logger.info(f"  Git commit    : {git_commit[:16]}")
    logger.info(f"  Config hash   : {config_hash[:16]}")
    logger.info(f"  Corpus hash   : (gelé après p1_load/p1_rank)")
    logger.info(f"  Lexique hash  : {lexicon_hash[:16]}")
    if proxy.get("enabled"):
        logger.info(f"  Modèle proxy  : {proxy.get('name')} (Sonnet inaccessible)")
    return run_id


def _register_model_runs(run_id: str, config: dict):
    """Crée un model_run par fournisseur déclaré et stocke les ids dans config['_runtime'].
    primary_reproducible → is_primary_scientific=1 ; secondary_proprietary (Tier C) → secondaire."""
    mp = config.get("model_providers", {})
    runtime = config.setdefault("_runtime", {})
    ids = {}
    if mp.get("primary_reproducible"):
        ids["primary"] = register_model_run(run_id, mp["primary_reproducible"],
                                             is_primary_scientific=True)
    if mp.get("secondary_proprietary"):
        ids["secondary"] = register_model_run(run_id, mp["secondary_proprietary"],
                                              is_primary_scientific=False,
                                              use_for_primary_claims=False)
    repl = mp.get("optional_cross_model_replication", {})
    if repl.get("enabled"):
        ids["replication"] = [register_model_run(run_id, m, is_primary_scientific=False)
                              for m in repl.get("models", [])]
    runtime["model_run_ids"] = ids
    logger.info(f"  model_runs    : primary={'oui' if 'primary' in ids else 'non'}, "
                f"secondary={'oui' if 'secondary' in ids else 'non'}, "
                f"replication={len(ids.get('replication', []))}")


def freeze_corpus_hash(run_id: str):
    """Gèle le hash du corpus APRÈS chargement/stratification des features (phase
    p1_freeze_corpus). Idempotent : ne réécrit pas un hash déjà gelé (sinon la reprise
    le détecterait comme une 'modification')."""
    with get_conn() as conn:
        row = conn.execute("SELECT corpus_hash FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row and row["corpus_hash"]:
            logger.info("Corpus déjà gelé — pas de réécriture.")
            return
        h = hash_corpus_canonical("db/features.db")
        conn.execute("UPDATE runs SET corpus_hash=?, status='running_frozen' WHERE run_id=?",
                     (h, run_id))
    logger.info(f"  Corpus hash gelé : {h[:16]}")


def verify_resume_integrity(run_id: str, config: dict, args):
    """Tous les hashes re-vérifiés à la reprise. Tout changement = erreur bloquante."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    if not row:
        raise RuntimeError(f"run_id {run_id} introuvable en DB")

    current_git     = get_git_commit()
    current_config  = hash_config(args.config)
    current_lexicon = hash_lexicon_canonical("db/lexicon.json")

    errors = []
    if row["git_commit"] != current_git:
        errors.append(
            f"Commit Git modifié : {row['git_commit'][:8]} → {current_git[:8]}"
        )
    if row["config_hash"] != current_config:
        errors.append("Config modifiée depuis le run original")
    # Le corpus n'est comparé que s'il a été GELÉ (après p1_load/p1_rank). Si NULL (crash
    # avant le gel), on ne compare pas — il sera gelé au prochain passage de p1_freeze_corpus.
    if row["corpus_hash"]:
        current_corpus = hash_corpus_canonical("db/features.db")
        if row["corpus_hash"] != current_corpus:
            errors.append("Corpus modifié depuis le run original")
    if row["lexicon_hash"] != current_lexicon:
        errors.append("Lexique modifié depuis le run original")

    registered_hashes = json.loads(row["prompt_hashes"])
    try:
        verify_prompts_unchanged(config["prompts"], registered_hashes)
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        msg = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(
            f"Reprise bloquée — modifications détectées :\n{msg}\n\n"
            f"Pour continuer avec ces modifications, créer un nouveau run."
        )
    logger.info(f"Intégrité vérifiée pour le run {run_id} — reprise autorisée")


def get_last_phase(run_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_phase FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return row["last_phase"] if row else None


def mark_phase_complete(run_id: str, phase: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET last_phase=? WHERE run_id=?", (phase, run_id)
        )
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    Path("checkpoints").mkdir(exist_ok=True)
    Path(f"checkpoints/{run_id}_{phase}_{ts}.ok").touch()
    logger.info(f"  ✓ Phase {phase} complète")


def print_cost_summary(run_id: str):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT phase, SUM(cost_usd) as total
            FROM api_usage WHERE run_id=?
            GROUP BY phase ORDER BY phase
        """, (run_id,)).fetchall()
        total = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()["total_cost_usd"]
    logger.info("=== Coût cumulé ===")
    for phase, cost in rows:
        logger.info(f"  {phase:<20} {cost:6.3f} $")
    logger.info(f"  {'TOTAL':<20} {total:6.3f} $")


def _run_baselines(run_id: str):
    from baselines import nl_labels, semantic_regex, keyword_tags
    nl_labels.run(run_id)
    semantic_regex.run(run_id)
    keyword_tags.run(run_id)


PHASES = [
    ("p1_load",        lambda rid, cfg: loader.run(rid, cfg),        "Extraction SAE"),
    ("p1_rank",        lambda rid, cfg: ranker.run(rid, cfg),        "Stratification splits"),
    # Gel du hash du corpus APRÈS chargement+stratification (le corpus est alors figé).
    ("p1_freeze_corpus", lambda rid, cfg: freeze_corpus_hash(rid),   "Gel du hash corpus"),
    ("p2_cluster",     lambda rid, cfg: cluster.run(rid),            "Clustering"),
    ("p2_label",       lambda rid, cfg: labeler.run(rid),            "Induction lexique"),
    ("p2_consistency", lambda rid, cfg: consistency.run(rid),        "Validation lexique"),
    ("p3_encode",      lambda rid, cfg: encoder.run(rid),            "Encodage (2 runs)"),
    ("p3_fidelity",    lambda rid, cfg: fidelity.run(rid),           "Fidélité AUC-ROC"),
    ("p3_baselines",   lambda rid, cfg: _run_baselines(rid),         "Baselines d'annotation"),
    ("p3_shuffle",     lambda rid, cfg: shuffled_baseline.generate_shuffles(rid, cfg),
                                                                     "Contrôle mélangé"),
    ("p4_steer",       lambda rid, cfg: (steerer.run(rid, cfg)
                          if cfg["steering"].get("run_in_pipeline", True)
                          else logger.warning("p4_steer désactivé (steering.run_in_pipeline=false) — steering non implémenté")),
                                                                     "Steering (traitement)"),
    ("p4_controls",    lambda rid, cfg: steerer.run_intervention_controls(rid, cfg),
                                                                     "Contrôles d'intervention"),
    # Phases de scoring causal : gardées par causal_scoring.run_in_pipeline (sans prédictions ni
    # steering, elles n'ont pas de matière). _load_pairs() est implémenté (v6.7.0) ; les
    # comparaisons baselines restent gardées par causal_scoring.run_baseline_comparisons.
    ("p4_predict",     lambda rid, cfg: (predictor.run(rid)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_predict désactivé (causal_scoring.run_in_pipeline=false)")),
                                                                     "Prédiction causale"),
    # Prédictions BASELINES (Option B, v6.8.0) : gardées par baseline_predictions.enabled (défaut
    # false, NON auto-activé). Produit predictor_nl_labels / predictor_semantic_regex pour permettre
    # les comparaisons appariées dans p4_score (run_baseline_comparisons).
    ("p4_predict_baselines", lambda rid, cfg: (baseline_predictor.run(rid, cfg)
                          if cfg.get("baseline_predictions", {}).get("enabled", False)
                          else logger.warning("p4_predict_baselines désactivé (baseline_predictions.enabled=false)")),
                                                                     "Prédiction baselines (Option B)"),
    # Métrique PRIMAIRE = score déterministe (prédiction vs classifieurs), SANS juge LLM (Règle 8)
    ("p4_score",       lambda rid, cfg: (causal_scorer.run(rid, cfg)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_score désactivé (causal_scoring.run_in_pipeline=false)")),
                                                                     "Score causal DÉTERMINISTE (primaire)"),
    # Juge LLM qualitatif : analyses SECONDAIRES uniquement (cas ambigus, audit)
    ("p4_qualitative", lambda rid, cfg: (qualitative_judge.run(rid, cfg)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_qualitative désactivé (causal_scoring.run_in_pipeline=false)")),
                                                                     "Juge LLM qualitatif (secondaire)"),
    ("p5_report",      lambda rid, cfg: reporter.run(rid),           "Synthèse"),
]


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

    # Garde Règle 11 : valider la politique de tiers de modèles AVANT toute exécution.
    # full → primary_reproducible Tier A/B obligatoire avec artefacts ; Tier C jamais primaire.
    from utils.model_policy import validate_model_providers
    validate_model_providers(config, config.get("run_mode", "full"))

    # Propager --n-features (dev run) : loader/ranker lisent config["_runtime"]["n_features_override"].
    config.setdefault("_runtime", {})["n_features_override"] = args.n_features
    if args.n_features:
        logger.info(f"Dev run : corpus limité à {args.n_features} features (override).")
        if config.get("run_mode") == "full":
            logger.warning("--n-features utilisé avec run_mode=full ; considérer run_mode=dev "
                           "(sinon n_probe_sentences reste à la valeur 'full').")

    if args.resume and args.run_id:
        run_id = args.run_id
        verify_resume_integrity(run_id, config, args)
        # Reconstruire les model_run_ids depuis la DB (Règle 11) : sinon les phases multi-modèle
        # et steerer.run retomberaient sur un model_run legacy au lieu du primaire déjà enregistré.
        ids = restore_model_run_ids(run_id, config)
        logger.info(f"model_runs restaurés : primary={'oui' if 'primary' in ids else 'non'}, "
                    f"secondary={'oui' if 'secondary' in ids else 'non'}, "
                    f"replication={len(ids.get('replication', []))}")
        last_phase = get_last_phase(run_id)
        logger.info(f"Reprise du run {run_id} depuis : {last_phase}")
    else:
        run_id     = initialize_run(config, args)
        last_phase = None

    phase_ids = [p[0] for p in PHASES]

    for phase_id, phase_fn, description in PHASES:
        if last_phase and phase_ids.index(phase_id) <= \
           phase_ids.index(last_phase):
            logger.info(f"⏭  {phase_id} déjà complétée")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"▶  {phase_id} : {description}")
        logger.info(f"{'='*60}")

        try:
            phase_fn(run_id, config)
            mark_phase_complete(run_id, phase_id)
            print_cost_summary(run_id)

            cost, over = check_budget(run_id, config["budget"]["max_cost_usd"])
            if config["budget"]["abort_on_exceed"] and over:
                raise RuntimeError(
                    f"Budget dépassé : {cost:.2f}$ >= "
                    f"{config['budget']['max_cost_usd']}$"
                )

        except Exception as e:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE runs SET status='failed' WHERE run_id=?",
                    (run_id,)
                )
            logger.exception(f"Phase {phase_id} échouée — run {run_id} archivé")
            # Full frozen run : pas de correction automatique, pas d'intervention agentique.
            # Archiver, analyser, puis créer un nouveau run avec un nouveau commit.
            sys.exit(1)

    with get_conn() as conn:
        conn.execute("""
            UPDATE runs SET status='completed', completed_at=?
            WHERE run_id=?
        """, (datetime.utcnow().isoformat(), run_id))
    print_cost_summary(run_id)
    logger.info(f"\n✅ Run {run_id} terminé — résultats dans db/features.db")


if __name__ == "__main__":
    run_pipeline(parse_args())
```

---

## 11. Ordre de mise en place et d'exécution

```bash
# ── 1. Environnement ────────────────────────────────────────
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sqlite3 db/features.db < db/schema.sql

# ── 2. Tests unitaires (sans clé API) ───────────────────────
pytest tests/test_parser.py tests/test_schema.py \
       tests/test_db.py tests/test_shuffle_baseline.py -v
# Tous doivent passer avant de continuer

# ── 3. Calibration des classifieurs ─────────────────────────
python classifiers/calibration/run_calibration.py
# Doit afficher ✅ PASS pour les 5 propriétés

# ── 4. Validation de l'accès au modèle (BLOQUANT) ───────────
python -c "
from agents.steerer import _get_model, _get_sae
from utils.config_utils import load_config
cfg = load_config('configs/dev_run.yaml')
_get_model(cfg)
# _get_sae prend désormais une COUCHE (le SAE est chargé par couche, Règle 6).
# Tester sur une couche représentative du proxy (ex. 6 pour pythia).
layer = cfg.get('proxy_model', {}).get('validation_layer', 6)
_get_sae(cfg, layer)
print('Accès modèle OK')
"
# Si NotImplementedError : implémenter _get_model() / _get_sae() d'abord.
# proxy_model.enabled est true PAR DÉFAUT (Règle 5) ; pour un modèle de production,
# mettre enabled=false et fournir les chemins d'accès dans agents/steerer.py.
# Rappel : la reproductibilité du clustering (Phase 2) dépend de
# clustering.kmeans_random_state / umap_random_state (graines fixées dans la config).

# ── 4 bis. Garde PRÉ-PILOT Phase 4 (à exécuter UNIQUEMENT avant un pilot/full run AVEC
#          steering activé). N'est PAS une étape du dev run de plomberie hors Phase 4 :
#          tant que steer_feature() est un placeholder, cette garde ÉCHOUE — c'est attendu,
#          et cela NE doit PAS empêcher le dev run de plomberie (étape 5) de tourner.
python -c "
from agents.steerer import assert_steering_ready
from utils.config_utils import load_config
assert_steering_ready(load_config('configs/dev_run.yaml'), n_probe=5)
print('steer_feature() produit bien text/activation/delta/ood — Phase 4 prête')
"
# À ne lancer (et faire passer) qu'AVANT d'activer le steering (steering.run_in_pipeline=true)
# pour un pilot/full run. La Phase 4 reste un CONTRAT (§7) ; le dev run de plomberie (étape 5)
# s'exécute indépendamment, sans cette garde.

# ── 5. Dev run (5 features — plomberie) ─────────────────────
# Plomberie HORS steering/scoring (tant que steer_feature() et causal_scorer._load_pairs()
# ne sont pas implémentés) : dans dev_run.yaml, mettre steering.run_in_pipeline=false ET
# causal_scoring.run_in_pipeline=false → p4_steer, p4_controls, p4_predict, p4_score et
# p4_qualitative sont sautés (avertissements) ; le pipeline va jusqu'à p5_report sans crash.
# Mettre ces flags à true APRÈS avoir implémenté le steering/scoring (et fait passer
# assert_steering_ready, étape 4 bis).
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Vérifier : DB peuplée, JSON parsés, coût < 1$, hash corpus gelé après p1_rank
# (status passe de 'loading' à 'running_frozen').
# En dev run hors steering, p4_predict, p4_score et p4_qualitative sont SAUTÉS par défaut
# (causal_scoring.run_in_pipeline=false). steer_feature() (v6.6.x) et causal_scorer._load_pairs()
# (v6.7.0) sont implémentés : un dev run causal MINIMAL (MorphoRepr seul) est possible en
# activant causal_scoring.run_in_pipeline=true sur un run contrôlé ayant des prédictions et du
# steering. Les comparaisons baselines restent désactivées (causal_scoring.run_baseline_comparisons=false).

# ── 6. Pilot run (40 features — calibration) ────────────────
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Analyser : coût réel, couverture, précision classifieurs, validité JSON
# Ajuster seuils ou prompts si nécessaire
# DÉCLARER tout ajustement comme calibration dans le papier

# ── 7. Estimation du budget full run ────────────────────────
python -c "
import sqlite3
conn = sqlite3.connect('db/features.db')
cost = conn.execute(
    'SELECT total_cost_usd FROM runs ORDER BY started_at DESC LIMIT 1'
).fetchone()[0]
n_pilot = 40; n_full = 500; factor = 3.0
estimate = cost * (n_full / n_pilot) * factor
print(f'Coût pilot : {cost:.2f}\$')
print(f'Estimation full run : {estimate:.1f}\$')
"
# Mettre à jour budget.max_cost_usd dans run_v1.yaml en conséquence

# ── 8. Gel de la configuration ───────────────────────────────
git add -A && git commit -m "Gel de tous les paramètres pour le full run v1"
python -c "
import subprocess
commit = subprocess.check_output(
    ['git','rev-parse','HEAD'], text=True
).strip()
print(f'Ajouter dans run_v1.yaml : git_commit: {commit}')
"
# Mettre à jour run_v1.yaml avec le commit exact

# ── 9. Full frozen run ───────────────────────────────────────
# Checklist Règle 11 (vérifiée par validate_model_providers, échoue sinon) :
#   [ ] model revision pinned          (primary_reproducible.model_revision)
#   [ ] tokenizer revision pinned      (primary_reproducible.tokenizer_revision)
#   [ ] weights hash archived          (weights_sha256)
#   [ ] tokenizer hash archived        (tokenizer_sha256)
#   [ ] inference container hash archived (inference_container_hash / inference_env_hash)
#   [ ] backend version archived       (dans inference_env_hash / env)
#   [ ] dtype and quantization archived (precision, quantization)
#   [ ] generation parameters archived (deterministic_generation → generation_params_json)
#   [ ] model tier declared            (provider_tier)
#   [ ] primary claims restricted to Tier A/B (use_for_primary_claims=1 seulement pour A/B)
python orchestrator.py --config configs/run_v1.yaml
# Aucune intervention pendant l'exécution

# ── 10. Reprise après crash (si nécessaire) ──────────────────
# UNIQUEMENT si le code, les prompts et la config n'ont PAS changé
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"
python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <run_id_interrompu>
# Si la vérification d'intégrité échoue → créer un nouveau run avec un nouveau commit
```

---

## 12. Rôle de Claude Code

Claude Code intervient **uniquement en dehors du full frozen run** :

**Autorisé en permanence :**
- Écrire et déboguer les agents, classifieurs et utilitaires
- Générer les fichiers de calibration des classifieurs
- Analyser les résultats intermédiaires du pilot run
- Produire des rapports lisibles depuis la base SQLite
- Suggérer des corrections si une phase du dev run ou pilot run échoue
- Implémenter `steerer.py` une fois l'accès au modèle validé

**Interdit pendant le full frozen run :**
- Modifier le moindre fichier de code, prompt ou config
- Intervenir dans l'orchestrateur en cours d'exécution
- Interpréter des erreurs et proposer des correctifs automatiques
- Relancer une phase échouée sans validation humaine explicite

---

## 13. Changelog v4 → v5

Cette version aligne le protocole sur l'article v0.27 et corrige plusieurs bugs vérifiés par exécution.

**Parseur (§4) — corrections critiques (vérifiées : 30/30 tests passent, dont les 11 exemples du papier).**
- Réécriture de `parse_word` par **segmentation sur tirets** (au lieu du parsing positionnel par sous-chaînes). La v4 (a) ne détectait **jamais** les infixes dans la forme `racine-infixe-suffixe` (ex. `soc-ant-o` → racine `soc-ant`, infixes `[]`), car après retrait du suffixe `-o` le corps `soc-ant` ne contient plus le motif `-ant-` ; (b) échouait sur `mal-o` et `ne-a` (« Aucun suffixe reconnu ») à cause de la boucle de préfixes gloutonne ; (c) plantait dès l'instanciation de `ParsedTerm`, le champ `coefficient_type` n'ayant pas de valeur par défaut. Les trois sont corrigés (segmentation + désambiguïsation positionnelle de `mal`/`ne` + défaut `coefficient_type="confidence"`).
- `RESERVED_TOKENS` complété avec `iĝ` ; ajout des jeux de tokens sans tiret (`PREFIX_TOKENS`, `INFIX_TOKENS`, `SUFFIX_TOKENS`) utilisés par la segmentation.
- `validate_free_root` scindé en `is_valid_root` (racine valide en l'état) et `can_register_new_free_root` (éligibilité à l'enregistrement comme nouvelle racine libre). `mal`/`ne` sont des racines valides mais non ré-enregistrables.
- Tests (§9) : import mis à jour ; ajout de `test_examples_from_paper` (11 cas paramétrés) ; `TestValidateFreeRoot` → `TestRootValidation`.

**Validation causale et steering (§7, config) — alignement sur la méthodologie v0.27.**
- Magnitude de steering **primaire normalisée par feature** (`magnitude_mode: p99_relative`, multiple de `activation_p99`) ; +5 absolu conservé en condition secondaire (`legacy_absolute_magnitude`). Courbe dose-réponse en multiples de p99 (`dose_response_rel`).
- Steering à la **couche propre du feature** (`layer_mode: per_feature`) ; `_get_sae(config, layer)` charge et **cache le SAE par couche** (le corpus peut couvrir plusieurs couches).
- **Exclusion des instances OOD** de la métrique primaire (`exclude_ood_from_primary`).
- `run()` et `_run_steering_batch` réécrits en conséquence ; colonne `magnitude_rel` ajoutée à `steering_results` ; insertion de la couche réelle du feature.

**Modèle de validation — proxy par défaut (Règle 5).**
- `proxy_model.enabled: true` par défaut. Validation principale sur modèle proxy open-weight ; exemples Claude 3 Sonnet purement illustratifs.

**Comparaison et statistiques (config, §4/§7).**
- Comparaison de validité causale **sur ensemble de features partagé** (Règle 7) ; score primaire **macro-F1** sur {increase, decrease, no_change} ; critère go/no-go en **différence appariée** dont l'IC bootstrap à 95 % exclut 0.
- Nouvelle section `stats` (bootstrap 10 000 stratifié, Holm-Bonferroni primaire, Benjamini-Hochberg exploratoire, politique d'échec de prédiction).
- Nouvelle section `intervention_controls` (feature aléatoire même couche, direction même norme, fréquence comparable, steering négatif, prompt-only, DiffMean/ReFT).
- Contrôle mélangé : fraction calibrée par le même chemin predictor+juge que le traitement (`llm_judge_calibration_fraction`, colonne `scored_by`).

**Reproductibilité et splits (config).**
- Splits **disjoints** (random échantillonné dans le complément de easy ∪ hard).
- Section `clustering` avec graines fixées (`kmeans_random_state`, `umap_random_state`).
- Section `batch` : `poll_interval_seconds: 60`, `max_wait_seconds: 86400` (2 h était trop court — risque de timeout artificiel avant l'expiration à 24 h des batchs).
- `git_commit` placeholder : l'orchestrateur **bloque** le run gelé tant que le commit n'est pas épinglé (sauf `allow_unpinned_commit: true` pour un dev run).
- Run requalifié « **gelé et auditable** » (et non « déterministe ») : sorties LLM stochastiques, mais code/config/prompts/corpus/lexique figés et vérifiés par empreinte, sorties archivées.

**Robustesse logicielle (§5, §6).**
- `db_utils.save_agent_output` : bug `if output_json` → `is not None` (un JSON `{}` ou `[]` n'est plus écrasé en NULL) ; **`INSERT OR IGNORE`** + contrainte `UNIQUE(run_id, feature_index, agent_name, run_number)` pour une persistance idempotente.
- `api_utils` : client Anthropic **paresseux** (`_get_client()`, import sans clé) ; concaténation **de tous les blocs `text`** (au lieu de `content[0].text`) ; timeouts lus depuis la config ; **persistance avant consommation/facturation** (`persist_fn`) pour éliminer le risque de double-dépense à la reprise.
- `prompt_utils.hash_corpus_canonical` : l'en-tête des colonnes est inclus dans le hash (détecte un changement de schéma/ordre).
- `classifiers/negation.py` : préfixes de négation élagués (retrait de `"a"`, `"in"`, `"im"`, `"il"`, `"ir"` — faux positifs massifs).
- `classifiers/valence.py` : pipeline en `top_k=None` ; `_neg_score` lit **directement** le score du label `negative` (au lieu d'approximer `1 - top_score`).
- `baselines/shuffled.generate_shuffles(run_id, config, …)` : la config est **passée explicitement** (la v4 appelait `load_config()` sans argument, ce qui échouait) ; appel orchestrateur et tests mis à jour.

**Divers.**
- En-têtes de version v4 → v5 (titre, §3, §7, docstring orchestrateur).

---

## 14. Changelog v5 → v6

Cette version répond à une seconde relecture critique et aligne le protocole sur l'article v0.28.

**Méthodologie causale (P0).**
- **Score causal primaire** : macro-F1 **global sur les couples (feature, propriété robuste)** au lieu de « par feature puis moyenné » (instable, trop peu de classes par feature) ; bootstrap **clusterisé par feature** ; score par feature conservé en secondaire (`stats`).
- **Métrique primaire DÉTERMINISTE** (Règle 8) : la phase `p4_judge` (juge LLM) est scindée en `p4_score` (`causal_scorer`, comparaison déterministe prédiction/classifieurs — primaire) et `p4_qualitative` (`qualitative_judge` — LLM, secondaire).
- **Random split représentatif** : `sampling_order: [random, easy, hard]` — random échantillonné **en premier, uniformément** sur tout le corpus, puis easy/hard dans le reste (plus de « middle set »).
- **Utilité globale (end-to-end)** : en plus de la performance conditionnelle (ensemble partagé), on rapporte `couverture × score causal` et un score intégré (UNCOVERED = abstention/0). Règle 7 et `stats.end_to_end_utility`.
- **Critère vs Semantic Regexes en non-infériorité** (`stats.non_inferiority_vs`, marge `thresholds.nim_delta`) ; supériorité vs NL.

**Identité de feature robuste (P0, Règle 10).**
- Table `features` : `feature_uid TEXT PRIMARY KEY` + `model_name`, `sae_release`, `layer_index`, `hook_name`, `feature_index` + `UNIQUE(model_name, sae_release, layer_index, hook_name, feature_index)`. `feature_uid` propagé (provenance) à `agent_outputs`, `steering_results`, `shuffle_controls`. Les FK `REFERENCES features(feature_index)` (devenues invalides) sont retirées ; les jointures intra-run restent sur `feature_index`.

**Phase 4 = contrat d'implémentation (P0, Règle 9).**
- §7 renommée « contrat d'implémentation v6 ». Ajout de `assert_steering_ready()` (garde **bloquante** pré-pilot : `steer_feature()` doit produire `text_before/after`, `activation_before/after`, `achieved_delta`, `ood_flag` sur un dev run). Étape §11.4 bis ajoutée.
- `normalize_layer()` : la couche (TEXT en base, ex. `'6'`/`'middle'`) est normalisée en `blocks.{i}.hook_resid_post` ; `_get_sae` utilise `layer_index` (numérique).
- Steering : `intervention_space` ∈ {`residual_add_decoder`, `sae_latent_clamp`} ; on **mesure et stocke `achieved_delta`** (le delta latent obtenu ≠ magnitude visée) ; OOD **mixte** (`max(p99·τ, mean+k·std, ε)` OU `|Δ| > delta_max·p99`).
- Sondes : `n_probe_sentences: 50` (20 pilot), `generations_per_probe`, paramètres de décodage gelés/archivés, deux familles (`neutral` + `domain_compatible`).
- `run_intervention_controls()` (contrat) ajouté + phase `p4_controls` ; les contrôles déclarés (prompt-only, DiffMean/ReFT, random même couche/norme, fréquence, steering négatif) sont désormais branchés (ou bloquent explicitement tant que non implémentés).

**Contrôle mélangé conforme (P0).**
- `generate_shuffles` ne génère QUE pour `evaluation_split`, assigne `scored_by` ('deterministic' par défaut, 'llm_qualitative' selon `llm_qualitative_audit_fraction`) et insère `scored_by` + `feature_uid`.

**Robustesse logicielle (P1).**
- `save_agent_output` : **non silencieux** — lève une `RuntimeError` si une sortie DIFFÉRENTE existe déjà (au lieu d'`INSERT OR IGNORE` qui avalait la divergence) ; reprise idempotente si identique ; accepte `feature_uid`.
- `log_api_cost` : **idempotent par batch** via `UNIQUE(run_id, batch_id, phase, agent_name)` sur `api_usage` ; le cumul n'est mis à jour que si la ligne est nouvellement insérée (anti double-comptage à la reprise).
- `api_utils` : `estimate_batch_cost()` + **garde budgétaire AVANT soumission** (`budget.estimate_before_submit`).
- Orchestrateur : `Path("logs").mkdir()` **avant** `logging.basicConfig` (le `FileHandler` ne peut plus échouer à l'import) ; `--n-features` **propagé** via `config["_runtime"]["n_features_override"]` ; `loader.run(rid, cfg)`.

**Classifieurs (P1/P2).**
- Négation : les préfixes morphologiques (`un/non/dis/mis`) sortent du **score robuste** et deviennent un **signal faible** rapporté à part (`weak_morphological_delta`).
- Calibration : rapport enrichi par propriété (n, équilibre des classes, **matrice de confusion**, accuracy ET **macro-F1**, précision/rappel par direction, version de modèle, seuils) ; **blocage sur le macro-F1**, pas seulement l'accuracy.

**Divers.**
- En-têtes de version v5 → v6 (titre, §3, §7) ; config `description` v0.27 → cohérente v0.28 ; `ood_threshold` unique remplacé par les paramètres du critère mixte.

---

## 15. Changelog v6 → v6.1

Patch ciblé répondant à la troisième relecture : **application complète de `feature_uid`** comme identité logique, plus corrections DB/tests. Aucune nouvelle fonctionnalité méthodologique ; la v6.1 reste une spécification (steering et contrôles d'intervention non implémentés).

**P0 — `feature_uid` partout (identité logique, Règle 10).**
- `agent_outputs` : `UNIQUE(run_id, feature_uid, agent_name, run_number)` (au lieu de `feature_index`) ; `feature_uid NOT NULL`. Index `idx_ao_feature` sur `feature_uid`.
- `baselines` : `feature_uid NOT NULL` + `UNIQUE(run_id, feature_uid, baseline_name)`.
- `shuffle_controls` : `feature_uid NOT NULL` ; `UNIQUE(run_id, feature_uid, shuffle_number)` ; `source_feature` remplacé par `source_feature_uid` (+ `source_feature_index` informatif).
- `steering_results` : `feature_uid NOT NULL` ; index sur `feature_uid`.
- Jointures `JOIN features f ON f.feature_uid = ao.feature_uid` dans `steerer.run` et `generate_shuffles` ; sous-échantillonnage et candidats de shuffle dédoublonnés sur `feature_uid`.
- `load_features_not_processed` et `save_agent_output` : reprise/idempotence clés sur `feature_uid` (et `save_agent_output` exige désormais `feature_uid`).
- `shuffle_id = {run_id}_{sha1(feature_uid)[:12]}_{n}` (plus de collision si même `feature_index` sur deux couches).
- Nouveau module `agents/causal_scorer.py` : `compute_global_macro_f1` calcule explicitement le macro-F1 **global sur les couples** `(feature_uid, propriété robuste)`, avec **bootstrap clusterisé par `feature_uid`** et différences appariées (supériorité vs NL / non-infériorité vs Semantic Regexes).

**P0 — autres corrections DB.**
- `hash_corpus_canonical` : `ORDER BY feature_uid` (hash réellement canonique avec plusieurs couches).
- `db_utils.py` : ajout de `import logging` + `logger = logging.getLogger(__name__)` (corrige un `NameError` potentiel dans `log_api_cost`).
- Versions : titre §3 « Schéma SQLite complet (v6.1) », commentaire `-- db/schema.sql — Version 6.1 », en-tête et docstring orchestrateur en v6.1.
- `assert_steering_ready` : tire désormais une **vraie feature** de la DB (`feature_uid`, `feature_index`, `layer_index`, stats `p99/mean/std`, `split='random'`) au lieu de `layer=6`/`feature_index=0` artificiels.

**P1.**
- `p4_controls` rendu **non bloquant par défaut** : `intervention_controls.run_in_pipeline=false` → `run_intervention_controls()` no-op avec avertissement (le dev/pilot run n'est plus stoppé) ; lève `NotImplementedError` seulement si activé sans implémentation.
- Arborescence `data/probes/` avec un fichier par famille/catégorie ; `load_probe_sentences(n, family=…)` lit `data/probes/probes_{family}.txt` et `load_domain_probes` charge les catégories `domain_compatible`.
- Table `classifier_calibrations` ajoutée au schéma ; `run_calibration.calibrate()` hashe le jeu de calibration et **archive** chaque rapport (n, équilibre, matrice de confusion, macro-F1, accuracy, seuils, version) en DB.
- `log_api_cost` : **non silencieux** en cas de divergence de coût pour un même `(run, batch, phase, agent)` (lève `RuntimeError` si coût/tokens diffèrent) ; `UPDATE` du cumul réécrit en `(batch_id=? OR (batch_id IS NULL AND ? IS NULL))` (plus portable que `batch_id IS ?`) et restreint à `cumulative_cost IS NULL`.
- `get_conn` relit `MORPHOREPR_DB_PATH` à chaque appel → isolation des tests effective quel que soit l'ordre d'import.

**P2 — tests ajoutés.**
- `test_feature_uid_integration.py` : (a) même `feature_index` sur deux couches → deux outputs sans collision ; (b) sortie divergente pour le même `feature_uid` → `RuntimeError` ; (c) hash corpus stable avec plusieurs couches et ordres d'insertion différents ; (d) shuffle sans collision de `shuffle_id` avec `feature_index` répété entre couches ; (e) reprise batch où coût recalculé ≠ coût loggé → `RuntimeError`.
- `test_causal_scorer.py` : macro-F1 **global** (et non par feature), pénalisation des erreurs, bootstrap clusterisé par feature, différence appariée sur features partagées.

**Réserves inchangées.** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`) ; la garde `assert_steering_ready` bloque tout pilot run tant que le steering n'est pas réellement implémenté. Les fonctions de scoring causal (`compute_global_macro_f1`, bootstraps) sont, elles, complètes et testées.

---

## 16. Changelog v6.1 → v6.2

Patch ciblé répondant à la quatrième relecture : suppression du dernier endroit où deux features de couches différentes pouvaient se confondre (`custom_id` Batch API), plus renforcements d'idempotence et de câblage. Aucune nouvelle fonctionnalité méthodologique.

**P0 — `custom_id` Batch API fondés sur `feature_uid`.**
- `utils/api_utils.py` : ajout de `feature_custom_id(f)` (= `feature_{feature_index}_{sha1(feature_uid)[:12]}`) et `build_custom_id_map(features)` (custom_id → feature_uid, pour rattacher les sorties batch à leur identité logique au retour). `build_batch_requests` utilise désormais `feature_custom_id(f)` au lieu de `feature_{feature_index}` : deux features de couches différentes mais de même `feature_index` ne peuvent plus collisionner dans un batch.
- Test `test_batch_custom_id.py` : unicité des `custom_id` avec `feature_index` répété ; récupération du `feature_uid` via la map.

**P1 — idempotence et câblage.**
- `steering_results` : ajout d'une contrainte `UNIQUE(run_id, feature_uid, intervention_space, magnitude_rel, probe_family, probe_id, generation_index)` (idempotence en reprise) ; `magnitude` reste informative (on évite la magnitude absolue flottante dans la clé). Les INSERT passent en `INSERT OR IGNORE` (à la reprise, la 1ʳᵉ sortie archivée est conservée — cohérent avec le run "gelé et auditable").
- `steerer.run` : charge désormais les **familles de sondes** (`neutral` + `domain_compatible` via `load_domain_probes`) et applique **generations_per_probe** ; `_run_steering_batch` itère sur (famille × génération) et **alimente les colonnes `probe_family` et `generation_index`** (jusque-là inutilisées). `steer_feature()` reste un contrat (placeholder), mais toute la structure d'orchestration est branchée.
- `p4_steer` rendu **non bloquant** via `steering.run_in_pipeline` (défaut `false`) : l'orchestrateur saute la phase avec un avertissement tant que le steering n'est pas implémenté → un dev run "plomberie hors steering" ne crashe plus. Config + garde dans `PHASES` + note §11.
- `user_study_results` : ajout de `feature_uid TEXT REFERENCES features(feature_uid)` (l'étude utilisateur peut référencer des features de plusieurs couches) ; `feature_index` informatif.

**Wording.**
- Commentaire de `features.feature_index` clarifié : « index local dans le SAE ; informatif, jamais clé logique seule ».

**Réserves inchangées (assumées).** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`). La partie identité des features / reproductibilité DB est désormais saine de bout en bout (DB, shuffles, hash, batch). Le prochain chantier n'est plus `feature_uid` mais l'implémentation effective de `steer_feature()`, de `_load_pairs()` et l'exécution réelle des sondes/générations multiples maintenant câblées.

---

## 17. Changelog v6.2 → v6.3

Patch ciblé répondant à la cinquième relecture : exécutabilité du pipeline hors steering, persistance du mapping `custom_id → feature_uid`, idempotence du steering en mode absolu, ventilation des sondes par catégorie, volumétrie resserrée, gel du hash corpus après chargement. Aucune nouvelle fonctionnalité méthodologique ; la v6.3 reste une spécification.

**Exécutabilité hors steering/scoring (P0 de la relecture).**
- Nouveau flag `causal_scoring.run_in_pipeline` (défaut `false`) gardant `p4_predict`, `p4_score` ET `p4_qualitative` dans l'orchestrateur : sans steering ni observations classifieurs (et avec `_load_pairs()` non implémenté), ces phases sont sautées avec un avertissement. Combiné à `steering.run_in_pipeline=false`, un dev run « plomberie » va désormais jusqu'à `p5_report` sans crash (note §11 mise à jour).

**Reprise Batch robuste — mapping persisté.**
- Table `batch_items(batch_id, custom_id, feature_uid, feature_index)` ; `save_batch_items`/`load_batch_item_map` dans `db_utils` ; `build_batch_item_rows(features)` dans `api_utils`. `submit_and_poll_batch` reçoit `batch_items`, **persiste le mapping à la soumission** et **enrichit chaque résultat de `feature_uid`** depuis la map persistée (robuste à la reprise : un batch peut contenir des `custom_id` de features déjà persistées, absentes d'une map reconstruite en mémoire).
- Test `test_batch_items_mapping_persiste_pour_reprise`.

**Idempotence `steering_results` en mode absolu + audit des divergences.**
- Ajout de `magnitude_key` (clé TEXTE stable : `rel:{rel}` ou `abs:{legacy}`) ; la contrainte d'unicité passe de `magnitude_rel` (flottant nullable) à `magnitude_key` → idempotence aussi en mode absolu.
- `INSERT OR IGNORE` remplacé par une insertion **non silencieuse** : la 1ʳᵉ sortie d'une cellule est conservée, mais toute tentative de réécriture DIFFÉRENTE est journalisée dans la nouvelle table `steering_duplicate_attempts` (au lieu d'être ignorée en silence).

**Sondes : catégorie conservée + volumétrie resserrée.**
- `steering_results.probe_category` ajoutée ; `steerer.run` ne fusionne plus les catégories de domaine sous une seule famille — il conserve `(probe_family, probe_category)` (permet « la feature X ne réagit que sur les sondes code/data »). La contrainte d'unicité inclut `probe_category` (évite les collisions entre catégories réinitialisant `probe_id`).
- Volumétrie du primaire réduite : `generations_per_probe: 1` (cohérent avec un décodage greedy `temperature=0`), sondes domaine **hors primaire par défaut** (`use_domain_probes_in_primary: false`, `domain_probes_as_secondary: true`). Bloc `stochastic_decoding` (secondaire) ajouté pour amortir la stochasticité si besoin.
- `run_mode` (`dev`/`pilot`/`full`) câblé : en dev/pilot, `n_probe_sentences_pilot` est effectivement utilisé (le champ ne dormait plus).

**Gel du hash corpus après chargement (point structurel).**
- `initialize_run` ne calcule plus le hash corpus au départ (NULL = en attente) ; nouvelle phase `p1_freeze_corpus` (après `p1_rank`) appelle `freeze_corpus_hash(run_id)` (idempotent). `verify_resume_integrity` ne compare le corpus que s'il a été gelé. Le hash reflète désormais le corpus réellement chargé et stratifié, pas l'état d'avant `p1_load`.

**Versions.**
- Marqueurs corrigés en v6.3 : en-tête, titre §3, commentaire `-- db/schema.sql — Version 6.3`, docstring orchestrateur.

**Réserves inchangées (assumées).** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`), désormais tous gardés par des flags `run_in_pipeline` pour permettre un pipeline exécutable de bout en bout hors steering/scoring. L'identité des features / reproductibilité DB est saine (DB, shuffles, hash, batch + mapping persisté). Le prochain chantier est l'implémentation effective de `steer_feature()`, `_load_pairs()` et l'exécution réelle des sondes/générations.

---

## 18. Changelog v6.3 → v6.4

Patch de finition répondant à la sixième relecture (qualifiée de mineure). Aucune nouvelle fonctionnalité ; durcissement de la reprise Batch et de l'auditabilité. La v6.4 est jugée solide pour un dev run de plomberie hors Phase 4.

**Enregistrement batch + mapping ATOMIQUE.**
- Nouvelle fonction `register_batch_with_items(batch_id, run_id, phase, agent_name, run_number, n_requests, items)` : INSERT du batch + INSERT des `batch_items` dans UNE SEULE transaction → suppression de la fenêtre de crash entre `register_batch()` et `save_batch_items()`. `submit_and_poll_batch` l'utilise. (`register_batch`/`save_batch_items` conservés pour usages séparés et tests.)
- À la reprise, si la map persistée (`load_batch_item_map`) est vide alors qu'un mapping feature-level est attendu → **RuntimeError** (au lieu d'un warning) ; idem si un `custom_id` reçu n'a pas d'entrée. On ne risque plus un mauvais rattachement silencieux.
- Test `test_register_batch_with_items_atomique`.

**`batch_items` obligatoire pour les batchs feature-level.**
- `submit_and_poll_batch(..., requires_feature_mapping=True)` : `ValueError` si `batch_items` manquant (un agent qui oublie `build_batch_item_rows(features)` est arrêté tôt). `requires_feature_mapping=False` permet les rares batchs non-feature.

**`steering_duplicate_attempts` enrichie (audit).**
- Colonnes ajoutées : `attempted_text_before`, `attempted_activation_before`, `attempted_activation_after`, `attempted_achieved_delta`, `attempted_ood_flag`. `_insert_steering_result` les renseigne → en cas de divergence, on conserve la 1ʳᵉ sortie mais on garde aussi de quoi diagnostiquer (activations, delta, OOD), pas seulement le texte.

**Wording dev run corrigé.**
- La note §11 ne prétend plus que `p4_score` s'exécute : elle indique que `p4_predict`, `p4_score` et `p4_qualitative` sont sautés par défaut (`causal_scoring.run_in_pipeline=false`) et que la métrique causale primaire ne sera testée qu'après implémentation du steering/scoring.

**Statut de run explicite pour l'audit.**
- `initialize_run` pose `status='loading'` ; `freeze_corpus_hash` passe à `status='running_frozen'` (en plus de geler `corpus_hash`). On distingue clairement un run pas encore gelé scientifiquement d'un run gelé. (Les transitions `failed`/`completed` ne dépendent pas de l'ancienne valeur ; `get_unconsumed_batch` dépend de `batches.status`, pas de `runs.status`.)

**Garde `--n-features` / `run_mode`.**
- `run_pipeline` émet un avertissement si `--n-features` est utilisé avec `run_mode=full` (rappel de passer en `run_mode=dev`, sinon `n_probe_sentences` reste à la valeur « full »).

**Versions.** Marqueurs en v6.4 (en-tête, titre §3, `-- Version 6.4`, docstring orchestrateur).

**Réserves inchangées (assumées).** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`), gardés par des flags `run_in_pipeline`. Comme l'a conclu la relecture, le prochain vrai chantier n'est plus le protocole mais l'implémentation effective de `steer_feature()` et de `causal_scorer._load_pairs()`.

---

## 19. Changelog v6.4 → v6.4.1

Micro-patch répondant à la septième relecture (deux retouches). Aucune modification de schéma, aucune nouvelle fonctionnalité.

**Pré-vérification `requests` ↔ `batch_items` AVANT soumission.**
- `submit_and_poll_batch` compare désormais, en plus du contrôle de présence, l'ensemble des `custom_id` des `requests` à celui des `batch_items` AVANT toute soumission (donc avant toute facturation). En cas d'écart → `ValueError` détaillant `missing`/`extra`. Ferme la dernière faiblesse logique du mapping batch : un décalage features/requests était sinon détecté seulement au retour des résultats, après facturation.
- Test `test_submit_rejette_batch_items_incoherents`.

**`assert_steering_ready` clarifiée comme garde PRÉ-PILOT Phase 4.**
- L'étape §11.4 bis est reformulée : c'est une garde à exécuter UNIQUEMENT avant un pilot/full run AVEC steering activé. Elle ÉCHOUE tant que `steer_feature()` est un placeholder — c'est attendu — et ne doit PAS empêcher le dev run de plomberie hors Phase 4 (étape 5), qui s'exécute indépendamment. Le wording « bloquant » absolu, qui pouvait laisser croire que le dev run était gelé tant que le steering n'était pas implémenté, est levé.

**Versions.** Marqueurs en v6.4.1 (en-tête, titre §3, `-- Version 6.4.1`, docstring orchestrateur).

**Réserves inchangées (assumées).** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`), gardés par des flags `run_in_pipeline`. Le protocole est jugé suffisamment stable ; le prochain vrai chantier est l'implémentation effective de `steer_feature()` et de `causal_scorer._load_pairs()`.

---

## 20. Changelog v6.4.1 → v6.5

Ajout d'une **couche de reproductibilité par modèles ouverts** (Règle 11). Touche le schéma SQLite → version mineure v6.5. **Compatibilité v6.4.1 préservée** : `batch_items` intact, `AnthropicProvider` conservé, Phase 4 toujours désactivée par défaut, `steer_feature()`/`run_intervention_controls()`/`causal_scorer._load_pairs()` restent des contrats.

**Règles.**
- **Règle 11 (Reproductibilité par modèles ouverts)** : trois tiers de fournisseurs (A fully open / B open-weight / C proprietary API). Toute conclusion principale doit être rapportée sur un modèle Tier A/B ; les résultats propriétaires sont secondaires. Une affirmation forte n'est admissible que sur le modèle primaire ouvert. Les agents passent par `ModelProvider`, jamais par `anthropic.Anthropic()` directement.
- **Règle 11 bis** : le full frozen run fige une liste exacte de modèles ; toute substitution après gel exige un nouveau `run_id`.

**Schéma (v6.5).**
- Nouvelle table `model_runs` (fournisseur, tier, backend, révisions, hashes poids/tokenizer, env d'inférence, precision/quantization, licence, `is_primary_scientific`, `use_for_primary_claims`, `generation_params_json`).
- `model_run_id` ajouté à `agent_outputs` (UNIQUE devient `(run_id, model_run_id, feature_uid, agent_name, run_number)` → plusieurs modèles annotent le même feature sans collision), `baselines` (+ dans son UNIQUE), `metrics`, `api_usage`, `batch_items`.
- `save_agent_output` accepte `model_run_id` (clé d'existence via `IS`, NULL-safe pour le chemin legacy mono-modèle).
- NB : le reporting est basé fichier (pas de table `reports`) ; `model_run_id` est porté par les `metrics` agrégées.

**Configuration.**
- Section `model_providers` (`primary_reproducible` Tier B exemple Qwen3-8B, `secondary_proprietary` Anthropic `use_for_primary_claims=false`, `optional_cross_model_replication` Mistral/Llama/OLMo). Champs à figer (révisions, hashes, env) marqués `FILL*`. La section `models` Anthropic est conservée pour la condition secondaire et les outils d'assistance.

**Code.**
- `utils/model_provider.py` : interface `ModelProvider.generate()` + `AnthropicProvider` (Tier C), `VLLMProvider`, `TransformersProvider`, `LlamaCppProvider` (imports lourds paresseux) + fabrique `build_provider`.
- `utils/model_policy.py` : `validate_model_providers(config, run_mode)` (pilot exige ≥ 1 modèle ouvert ; full exige un primaire Tier A/B avec révisions+hashes+env ; Tier C jamais primaire), `assert_primary_claim_allowed(model_run)` (garde reporter), `classify_cross_model_effect(...)` (model-invariant / open-model-only / proprietary-only / unstable).
- `db_utils` : `register_model_run(...)` (Tier C ⇒ `use_for_primary_claims=0` par défaut), `load_model_runs(...)`.
- Orchestrateur : `run_pipeline` appelle `validate_model_providers` avant toute phase ; `initialize_run` enregistre les `model_runs` (primaire/secondaire/réplication) et mémorise leurs ids dans `config['_runtime']`.

**Politique, reporting, robustesse cross-modèle.**
- Section « Model openness and reproducibility policy » (pourquoi un propriétaire seul ne suffit pas, distinction open-source/open-weight/proprietary, reporting séparé Tier A/B vs C, anti open-washing, liste d'artefacts à archiver) + extrait README.
- Politique d'exécution dev/pilot/full ; tableau de reporting par modèle/tier ; section robustesse cross-modèle ; règle de conclusion scientifique (« in the proprietary reference condition » si non reproduit sur modèle ouvert).
- Checklist full frozen run (révisions/hashes/env/dtype/quantization/params/tier/claims restreints A/B).

**Tests (6).**
- `test_model_provider_interface` (interface commune + backend inconnu rejeté), `test_model_run_id_isolation` (deux modèles, même feature_uid, pas de collision), `test_primary_claim_requires_open_model` (reporter refuse un claim primaire Tier C), `test_model_artifact_hashes_required` (full run échoue sans révisions/hashes/env), `test_anthropic_is_secondary_by_default` (Tier C ⇒ `use_for_primary_claims=0`), `test_cross_model_report` (séparation par modèle/tier + classification d'effet).

**À faire côté papier (v0.29, hors procédure).** Ajouter à la méthode la politique de tiers et la justification de reproductibilité (claims primaires sur modèle ouvert, propriétaire en comparaison externe) ; aux menaces à la validité : open-weight ≠ toujours fully open, dépendance au modèle, modèles propriétaires changeants sans accès complet, variations backend/dtype/quantization/matériel ; à la checklist de gel : révisions/hashes/env/tier/claims restreints A/B.

---

## 21. Changelog v6.5 → v6.5.1

Correctif : la politique de modèles ouverts (v6.5) était bonne, mais `model_run_id` était ajouté au schéma **sans être propagé** dans plusieurs fonctions. La v6.5.1 complète la propagation et durcit les contraintes. Réponse point par point à la 8ᵉ relecture.

**1. Marqueurs du papier (v0.29).** En-tête `*Version 0.29 — Juin 2026*`, `Remplace la version 0.28`, footer en v0.29, note de version « par rapport aux versions antérieures ». 0 marqueur v0.28 résiduel.

**2. `model_run_id` propagé dans les batchs.** `batches` reçoit la colonne `model_run_id` (NOT NULL). `register_batch`, `register_batch_with_items`, `save_batch_items`, `build_batch_item_rows(features, model_run_id)` et `load_batch_item_map` (qui renvoie désormais `model_run_id`) le propagent. La colonne `batch_items.model_run_id` est réellement renseignée.

**3. Reprise batch multi-modèle sûre.** `get_unconsumed_batch(..., model_run_id=None)` filtre `model_run_id IS ?`. `submit_and_poll_batch(..., model_run_id=None)` résout le modèle (legacy explicite par défaut) **après** la validation d'entrée, puis le passe à `get_unconsumed_batch` ET `register_batch_with_items` (même id) : deux modèles d'un même run ne peuvent plus reprendre le batch l'un de l'autre.

**4. Comptabilité par modèle.** `log_api_cost(..., model_run_id=None)` insère `model_run_id` ; `api_usage` passe à `UNIQUE(run_id, model_run_id, batch_id, phase, agent_name)` ; coûts attribués par modèle.

**5. Statut de `api_utils.py` (Option A).** Marqué explicitement **LEGACY Anthropic Batch API wrapper** : seul endroit autorisé à instancier `anthropic.Anthropic()`, et UNIQUEMENT pour la condition propriétaire **secondaire** (Tier C). L'inférence scientifique passe par `ModelProvider`. Plus de contradiction avec la Règle 11.

**6. `model_run_id` NOT NULL là où le multi-modèle est central.** `agent_outputs`, `baselines`, `batch_items`, `batches`, `api_usage`, `steering_results` : `model_run_id TEXT NOT NULL`. Un `model_run` **legacy explicite** déterministe (`{run_id}::legacy`, Tier C) est créé via `ensure_legacy_model_run` et sert de valeur par défaut au chemin mono-modèle — plus aucune dépendance à l'unicité SQLite avec NULL. **Déviation assumée** : `metrics.model_run_id` reste NULLABLE, car certaines métriques sont **agrégées / cross-modèle** (stabilité inter-modèles) et n'appartiennent à aucun modèle unique.

**7. `steering_results.model_run_id`.** Colonne NOT NULL ajoutée ; incluse dans la contrainte d'unicité. `_insert_steering_result`, `_run_steering_batch` et `steerer.run` (qui résout le modèle ouvert primaire depuis `config['_runtime']`, sinon legacy) le persistent. Le steering devient rapportable par modèle/tier.

**8. README.** Pointeurs mis à jour (papier v0.29, procédure v6.5.1, `model_runs`, `ModelProvider`, modèle ouvert primaire, Anthropic secondaire, claims Tier A/B) et **suppression** des références obsolètes (papier v0.26, critère « IC non chevauchants »).

**9. Tests.** Nouveau bloc `test_model_run_propagation.py` : deux modèles ne reprennent jamais le même batch ; `batch_items.model_run_id` renseigné (0 NULL) ; `api_usage` sépare deux modèles ; `agent_outputs` refuse la collision intra-modèle mais autorise deux modèles. Tests batch existants adaptés (passage du `model_run_id` legacy à `get_unconsumed_batch`/`build_batch_item_rows`/`register_batch*`). Fixtures directes (`_setup_features_encodees`, helper `_run`, test de collision shuffle) insèrent un `model_runs` legacy et `model_run_id`.

**Réserves inchangées.** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`), gardés par des flags `run_in_pipeline`. La v6.5.1 complète la propagation de `model_run_id` (le verrouillage de la couche « modèles ouverts » sera finalisé en v6.5.3, Phase 4 incluse) ; le prochain vrai chantier reste l'implémentation effective de `steer_feature()` et de `causal_scorer._load_pairs()`.

---

## 22. Changelog v6.5.1 → v6.5.2

Correctif **final** de propagation multi-modèle. `model_run_id` était présent dans le schéma (v6.5.1) mais la **logique de sélection des features** n'était pas encore *model-aware*, et deux pièges de fallback/filtre subsistaient. Aucune modification de schéma.

**1. `load_features_not_processed` rendu *model-aware*.** Ajout d'un paramètre `model_run_id` ; le filtre des sorties déjà produites passe à `(run_id, model_run_id, agent_name, run_number)`. Sans cela, un 2ᵉ modèle (réplication/secondaire) voyait toutes les features comme déjà traitées par le 1ᵉʳ — bloquant pour la réplication. `model_run_id` par défaut = model_run legacy explicite (chemin mono-modèle). Les agents (modules non montrés) passent le `model_run_id` correspondant : **contrat documenté**. Test `test_load_features_not_processed_model_aware`.

**2. Fallback `batch_items.model_run_id` ne produisant plus de NULL.** `dict.get(clé, défaut)` renvoie `None` quand la clé existe **avec** la valeur `None` (cas de `build_batch_item_rows(features)` sans `model_run_id`). Dans `register_batch_with_items` et `save_batch_items`, remplacement par `it.get("model_run_id") or model_run_id`. La colonne `batch_items.model_run_id` (NOT NULL) ne peut plus recevoir de NULL même quand les items portent une clé `model_run_id=None`. Test `test_build_batch_item_rows_none_ne_produit_pas_null`.

**3. `get_unconsumed_batch(model_run_id=None)` résout le legacy.** Comme `batches.model_run_id` est NOT NULL, un filtre `IS NULL` ne pouvait plus rien matcher. La fonction résout désormais `ensure_legacy_model_run(run_id)` quand `model_run_id is None` (et filtre par égalité). Un batch legacy enregistré via `register_batch(..., model_run_id=None)` est de nouveau retrouvable. Test `test_get_unconsumed_batch_legacy_retrouvable`.

**4. Description YAML.** `description: "Full frozen run MorphoRepr v0.29 / procedure v6.8.0 — 500 features"` (résidu v0.28 supprimé).

**5. Reprise : restauration des `model_run_ids`.** Nouvelle fonction `restore_model_run_ids(run_id, config)` qui reconstruit `config['_runtime']['model_run_ids']` depuis la DB (rattachement par `model_name` au rôle déclaré : primary/secondary/replication). Appelée dans la branche `--resume` de l'orchestrateur. `steerer.run` ne retombe donc plus sur un model_run legacy quand un modèle primaire existe déjà en DB. Test `test_resume_restaure_model_run_ids`.

**Réserves inchangées.** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`), gardés par des flags `run_in_pipeline`. La couche « modèles ouverts / reproductibilité » est désormais cohérente de bout en bout (schéma + logique de sélection + reprise). Le prochain vrai chantier reste l'implémentation effective de `steer_feature()` et de `causal_scorer._load_pairs()`.

---

## 23. Changelog v6.5.2 → v6.5.3

Correctif d'une **dernière fuite multi-modèle en Phase 4**. Aucune modification de schéma.

**`steerer.run()` rendu strictement model-aware.** La fonction résolvait déjà le `model_run_id` du modèle primaire, mais la requête qui charge les sorties `encoder` depuis `agent_outputs` ne filtrait pas dessus : un même `feature_uid` annoté par plusieurs modèles aurait pu faire steerer une annotation secondaire/legacy sous le `model_run_id` primaire. Le chargement est désormais extrait dans `_load_encoded_random_features(run_id, model_run_id)`, dont la requête ajoute `AND ao.model_run_id = ?` (paramètres `(run_id, model_run_id)`) ; `run()` l'appelle. Le steering primaire n'utilise donc que les annotations du modèle primaire.

**Test.** `test_steering_charge_uniquement_le_modele_primaire` : deux `model_run_id` dans le même run, deux sorties `encoder` pour le même `feature_uid` (expressions différentes) ; le chargement du steering ne récupère que l'annotation du modèle primaire, et symétriquement le secondaire ne voit que la sienne — aucune sortie secondaire/legacy n'est steerable sous le `model_run_id` primaire.

**Résidus documentaires.** README intégré : « Procédure de test : v6.5.3 ». Changelog v6.5.1 reformulé en historique (verrouillage finalisé en v6.5.3). Papier v0.29 : « Voir la procédure de test v6.5.x (≥ v6.5.3) ».

**Phase 4 toujours contractuelle.** `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`) gardés par des flags `run_in_pipeline` : le correctif rend le *chargement* du steering model-aware, mais la Phase 4 n'est pas exécutable tant que `steer_feature()` n'est pas implémenté. La couche « modèles ouverts / reproductibilité » est désormais cohérente de bout en bout (schéma, sélection des features, reprise **et** Phase 4). Le prochain vrai chantier reste l'implémentation effective de `steer_feature()` et de `causal_scorer._load_pairs()`.

---

## 24. Changelog v6.5.3 → v6.6.0

Extension fonctionnelle : **implémentation réelle de `steer_feature()` pour le chemin proxy open-weight**. Aucun changement de schéma SQLite. La couche multi-modèle v6.5.3 (`model_run_id`, `_load_encoded_random_features`, propagation) est **inchangée**.

**`steer_feature()` implémenté (TransformerLens + SAE Lens, `residual_add_decoder`).** Pour chaque phrase-sonde : (1) génération `text_before` SANS intervention via `model.generate` (paramètres gelés de `config["steering"]["decoding"]`, greedy si `temperature=0`) ; (2) mesure `activation_before` par forward pass → résiduel au hook du SAE → `sae.encode` → agrégation (`max` par défaut) selon `token_position` ; (3-4) intervention `magnitude · sae.W_dec[feature_index]` ajoutée au résiduel aux positions sélectionnées, puis génération `text_after` AVEC le hook actif (même prompt, mêmes paramètres) ; (5) mesure `activation_after` ; (6) `achieved_delta = activation_after − activation_before` et `ood_flag = _is_ood(...)`. Plus aucun placeholder ; `text_after` n'est jamais `None` dans le chemin nominal.

**Erreurs explicites (pas de simulation).** `proxy_model.enabled=false` → `NotImplementedError` (chemins nnsight / modèle de production non implémentés ; aucune interface publique ne garantit le steering interne d'un modèle propriétaire). `intervention_space='sae_latent_clamp'` → `NotImplementedError` (seul `residual_add_decoder` est implémenté). `NotImplementedError` est toujours propagée (échec bruyant) ; une erreur technique sur une probe est consignée (`error`, `text_after=None`) sans interrompre le batch — et fait, à dessein, échouer `assert_steering_ready`.

**Fonctions ajoutées** (toutes dans `agents/steerer.py`) : `_get_hook_name_from_sae` (priorité `sae.cfg.hook_name`, repli `sae.cfg.hook_layer`), `_tokens_from_prompt`, `_position_indices` (logique pure), `_selected_token_positions`, `_aggregate_feature_activation`, `_make_residual_add_decoder_hook`, `_measure_feature_activation`, `_generate_text`. Robustesse aux variations d'API (capture du résiduel post-intervention via un hook de capture ajouté après le hook d'intervention ; `sae.encode` tolérant aux retours tuple ; gestion device/dtype).

**`steerer.run()` inchangé** : reste strictement model-aware (`_load_encoded_random_features` non modifié), passe `mag_abs` à `steer_feature` comme avant. `model_run_id` non touché.

**Tests ajoutés** (`tests/test_steer_feature.py`, mocks légers de l'API TransformerLens/SAE Lens) : non-placeholder + champs requis ; calcul du delta (1.0 → 2.5 ⇒ 1.5) ; OOD ; `sae_latent_clamp` et chemin non-proxy lèvent `NotImplementedError` ; sélection `all`/`last`/`content_only` ; hook ajoutant `magnitude·W_dec` aux seules positions sélectionnées ; `assert_steering_ready` (passe avec mocks, échoue si `text_after` == placeholder) ; test d'intégration **slow** opt-in (`MORPHOREPR_RUN_SLOW_STEERING=1`).

**Phase 4 non validée scientifiquement.** `steering.run_in_pipeline` reste `false` par défaut (non activé automatiquement). `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`). La v6.6.0 rend la Phase 4 **exécutable pour le chemin proxy open-weight** et **testable** (`assert_steering_ready` peut passer sur un dev run contrôlé), mais ne produit aucun résultat causal : le scoring causal n'est pas opérationnel tant que `causal_scorer._load_pairs()` n'est pas implémenté. Les claims scientifiques du papier (v0.29) sont inchangés.

**Limites restantes.** `sae_latent_clamp`, chemin nnsight / modèle de production, `run_intervention_controls()`, `causal_scorer._load_pairs()` ; pas d'exécution réelle en CI standard (test d'intégration opt-in) ; dépendance aux versions exactes de TransformerLens / SAE Lens (erreurs explicites si l'API attendue diffère).

---

## 25. Changelog v6.6.0 → v6.6.1

Durcissement de l'implémentation v6.6.0 de `steer_feature()` (chemin proxy open-weight). **Aucun changement de schéma.** Philosophie v6.6.0 inchangée ; `model_run_id` et `_load_encoded_random_features` intacts ; Phase 4 toujours désactivée par défaut.

**Compatibilité TransformerLens / SAE Lens — `_generate_text()` adaptatif.** Nouveau helper `_supported_generate_kwargs(model, desired)` : introspection de la signature de `model.generate` (`inspect.signature`) ; ne passe que les kwargs réellement supportés ; conserve tout si `**kwargs` (VAR_KEYWORD) ; lève `AttributeError` explicite si `model.generate` est absent. Mapping greedy propre (`temperature=0.0` et/ou `do_sample=False` selon le support ; `top_p`/`verbose` seulement s'ils sont acceptés). Les kwargs effectivement passés sont journalisés (`logger.debug`).

**Sémantique `activation_before/after` clarifiée (Option A).** Documenté explicitement dans `_measure_feature_activation` et `steer_feature` : ce sont des `probe_activation_before/after`, mesurées sur le CONTEXTE de la phrase-sonde au hook du SAE, PAS sur la continuation générée. L'Option B (mesure sur le texte généré complet) mélangerait l'effet du changement de texte avec l'effet direct de l'intervention ; non retenue. Aucun changement de schéma.

**Validations de shapes / bornes (erreurs explicites).** Nouveau helper `_validate_feature_and_shapes(sae, feature_index, resid)` : `feature_index ∈ [0, sae.W_dec.shape[0])` (sinon `IndexError`) ; `d_model` du décodeur == `d_model` du résiduel (sinon `ValueError` avec les formes observées). Appelé dans `_measure_feature_activation`. Contrôle de borne `feature_index` AUSSI dès l'entrée de `steer_feature` (avant toute génération). Forme de `sae.encode(resid)` validée (`[batch, seq, d_sae]` ou `[seq, d_sae]`) ; retour tuple toléré (`acts[0]`) et documenté.

**Tests renforcés** (`tests/test_steer_feature.py`) : `_generate_text` filtre les kwargs non supportés (fake `generate` sans `do_sample`) et conserve tout si `**kwargs` ; `AttributeError` si `generate` absent ; **hook réellement exécuté pendant `model.generate`** (fake model qui exécute les hooks enregistrés ; `text_after` dépend de la modification effective du résiduel ; `hook_name` présent dans `hooks_entered`/`hook_calls`) ; `feature_index` hors borne → `IndexError` ; `d_model` incompatible → `ValueError` ; `sae.encode` tuple toléré ; agrégation 2D et 3D ; **dtype préservé** par le hook (W_dec float32, résiduel float16/bfloat16). Test slow opt-in (`MORPHOREPR_RUN_SLOW_STEERING=1`) renforcé : **skip propre** avec message si modèle/SAE indisponible, et vérifications `text_before/after` non vides, `activation_before/after`/`achieved_delta` numériques, `ood_flag ∈ {0,1}`.

**Résidus documentaires.** Procédure : « Le README doit désormais pointer le papier v0.29 et la procédure v6.6.1 » ; commentaire YAML `steering.run_in_pipeline` reformulé (steer_feature implémenté pour le chemin proxy open-weight, Phase 4 désactivée tant que `assert_steering_ready` non validé en dev run **et** que le scoring causal reste contractuel) ; structure projet complétée (`utils/model_provider.py`, `utils/model_policy.py`, `tests/test_model_providers.py`, `tests/test_model_run_propagation.py`, `tests/test_steer_feature.py`, `api_utils.py` annoté legacy).

**Réserves inchangées.** Phase 4 non activée automatiquement (`steering.run_in_pipeline=false`) et non validée scientifiquement. `run_intervention_controls()` et `causal_scorer._load_pairs()` restent des **contrats** (`NotImplementedError`) : aucun résultat causal n'est produit. `sae_latent_clamp` et le chemin nnsight / modèle de production restent non implémentés (erreurs explicites). Les claims scientifiques du papier (v0.29) sont inchangés. Limites restantes : pas d'exécution réelle en CI standard (test d'intégration opt-in) ; dépendance aux versions exactes de TransformerLens / SAE Lens (désormais atténuée par l'introspection, avec erreurs explicites si l'API attendue diffère).

---

## 26. Changelog v6.6.1 → v6.7.0

Extension fonctionnelle du scoring causal : **implémentation réelle de `causal_scorer._load_pairs()`**. **Aucun changement de schéma** (la colonne `metrics.model_run_id` existante est désormais renseignée). Couche multi-modèle et `steer_feature()` v6.6.1 inchangées. Le papier v0.29 et ses claims ne sont pas modifiés.

**`_load_pairs()` implémenté (métrique primaire déterministe).** Signature étendue : `_load_pairs(run_id, method, config=None, model_run_id=None, split="random")`. Pour chaque `feature_uid` et chaque propriété ROBUSTE, assemble un couple `{feature_uid, model_run_id, property, predicted, observed, method, n_observations, metadata}` :
- **predicted** ← `agent_outputs` (agent prédicteur de la méthode), via `_extract_predicted_directions` qui accepte trois formats (`predictions:[…]`, `properties:{prop:"DIR"}`, `properties:{prop:{"direction":…}}`), normalise les alias (`increase/up/more`→INCREASE, etc.) et **rejette** les directions ambiguës (`UNKNOWN`, `null`, vide, non reconnue) sans les convertir en `NO_CHANGE` ;
- **observed** ← classifieurs déterministes appliqués aux paires `text_before/text_after` de `steering_results` à la **magnitude primaire** (`_primary_magnitude_key`), via `_observe_property_direction` (aucune pseudo-observation ; direction invalide du classifieur → erreur, jamais `NO_CHANGE` silencieux) ;
- **aucun juge LLM** dans le primaire ; `negative_valence` (semi-robuste) est exclu (`CLASSIFIER_BY_PROPERTY` ne contient que négation, temps, code, modalité conditionnelle).

**Strictement model-aware / split-aware / OOD-aware.** Sélection du modèle : `model_run_id` explicite → `config["_runtime"]["model_run_ids"]["primary"]` → `ensure_legacy_model_run(run_id)`. Toutes les requêtes (`agent_outputs`, `steering_results`) filtrent sur ce `model_run_id` et joignent `features` pour filtrer `split`. Les `steering_results` à `ood_flag=1` sont exclus si `exclude_ood_from_primary=true`. Seules les sondes neutres du primaire sont retenues (`probe_family='neutral'`, `probe_category IS NULL`).

**Erreurs explicites (jamais de liste vide silencieuse).** Aucune prédiction → `RuntimeError("No predictor outputs found …")` ; aucune observation → `RuntimeError("No steering observations found … Did you run p4_steer first?")` ; features prédites sans observation → ignorées avec log d'audit (pas de score artificiel) ; aucun couple assemblé → `RuntimeError("No causal pairs assembled …")` ; méthode inconnue → `NotImplementedError`.

**`run()` mis à jour.** Résout le `model_run_id` primaire et le `split` primaire, calcule `compute_global_macro_f1` + `feature_clustered_bootstrap` sur les couples MorphoRepr, et **persiste `metrics.model_run_id`** (le modèle primaire ; `NULL` réservé aux agrégats cross-modèles). Les fonctions de scoring (`compute_global_macro_f1`, `feature_clustered_bootstrap`, `paired_diff_bootstrap`) sont **inchangées**.

**Baselines — Option A (par défaut).** Les comparaisons baselines (supériorité vs NL, non-infériorité vs Semantic Regexes) ne sont exécutées que si `causal_scoring.run_baseline_comparisons=true` (les prédictions baselines ne sont pas encore branchées dans le pipeline). Par défaut : **score MorphoRepr seul**, log explicite, **aucun verdict** de supériorité/non-infériorité (pas de faux `pass`/`fail`). Si activé sans prédictions baselines, `_load_pairs(base)` lève une `RuntimeError` explicite (Option B propre). Aucune prédiction baseline fabriquée.

**Tests ajoutés** (`tests/test_causal_scorer.py`) : extraction des trois formats de prédiction + rejet des directions invalides ; `_observe_property_direction` (paires nulles ignorées, direction invalide → `ValueError`) ; `_primary_magnitude_key` (`rel:1.0` / `abs:5`) ; OOD exclu/inclus ; **model-aware** (le primaire ne charge jamais prédiction/observation du secondaire) ; **split-aware** ; absences explicites (no steering / no predictor / méthode inconnue) ; couple final assemblé ; `run()` minimal (macro-F1=1.0, `metrics.model_run_id` renseigné, baselines skippées sans verdict).

**Statut.** `causal_scorer._load_pairs()` est implémenté pour MorphoRepr (**dev run causal minimal** possible). `run_intervention_controls()` reste un **contrat**. `causal_scoring.run_in_pipeline` reste `false` (non activé automatiquement) ; un dev run causal exige un run contrôlé disposant de prédictions et de steering. **Aucun full result scientifique n'est revendiqué** : pas de comparaison baseline par défaut, et la validation causale complète reste à établir. Limites restantes : prédictions baselines non branchées (Option A), `run_intervention_controls()` contractuel, pas d'exécution réelle en CI standard (dev causal opt-in), dépendance au chemin steer_feature proxy open-weight pour produire les observations.

---

## 27. Changelog v6.7.0 → v6.8.0

Prédictions **baselines (Option B)** pour `nl_labels` et `semantic_regex` : les comparaisons primaires prévues par le protocole (supériorité vs NL, non-infériorité vs Semantic Regexes) deviennent **exécutables en dev run contrôlé**. **Aucun changement de schéma.** `_load_pairs()` MorphoRepr (v6.7.0), la couche multi-modèle et `steer_feature()` sont inchangés. Le papier v0.29 et ses claims ne sont pas modifiés. **Aucun full scientific result n'est revendiqué.**

**Nouveau module `agents/baseline_predictor.py`.** `run(run_id, config)` produit, pour chaque baseline activée et chaque feature, un `agent_output` de prédiction de directions au **format canonique** accepté par `causal_scorer._extract_predicted_directions`, avec l'`agent_name` attendu (`predictor_nl_labels`, `predictor_semantic_regex`). Il lit les annotations dans la table `baselines` (`annotation_run1` pour le primaire ; `annotation_run2` réservé à une analyse de stabilité secondaire, **jamais mélangée**), construit le **provider primaire** (`_build_primary_provider`, seam monkeypatchable, Règle 11), appelle `provider.generate(...)` avec un **prompt séparé** par baseline, puis parse la réponse (`_parse_prediction_response`) en ne gardant que les **propriétés robustes** avec direction valide. Une réponse non parsable ou sans direction robuste valide est persistée `status='error'` (jamais convertie en `NO_CHANGE`). Le steering n'est **pas** refait : seul le chemin de prédiction diffère, ce qui garantit une comparaison appariée correcte (mêmes `steering_results`, classifieurs, split, `model_run_id`, `magnitude_key`, filtrage OOD, bootstrap clusterisé).

**Prompts séparés** (aucune terminologie MorphoRepr) : `prompts/predictor_nl_labels_v1.txt` (entrée = label naturel + exemples top-activating ; sortie = directions robustes ; ne demande pas d'annotation MorphoRepr) et `prompts/predictor_semantic_regex_v1.txt` (entrée = Semantic Regex + description ; exploite la structure regex ; ne traduit pas en MorphoRepr). Même schéma JSON strict pour les deux.

**Baselines branchées** : `nl_labels` (supériorité) et `semantic_regex` (non-infériorité). **Non branchées** : `keyword_tags` et `morphorepr_shuffled` (`_UNSUPPORTED` → `NotImplementedError` explicite si demandées ; `morphorepr_shuffled` est un contrôle nul d'annotation, hors priorité des comparaisons principales).

**Config.** Nouvelle section `baseline_predictions` (`enabled:false`, `methods:[nl_labels, semantic_regex]`, `run_number:1`, `require_existing_baseline_annotations:true`, `skip_missing_annotations:false`) et nouveau flag `causal_scoring.strict_baselines` (`true` → baseline demandée mais absente lève `RuntimeError` ; `false` → skip explicite **sans verdict**). Prompts ajoutés à `prompts:`.

**Garde `causal_scorer.assert_baseline_predictions_ready(run_id, model_run_id, methods, split, min_features=1)`** : vérifie la présence d'annotations dans `baselines` ET de prédictions `agent_outputs` (agent_name attendu) pour le **même** `model_run_id` et le **même** split (jointure `features`). Lève `RuntimeError` sinon — **aucun verdict sur une baseline absente**.

**`causal_scorer.run()` (Option B).** Si `run_baseline_comparisons=true` : pour chaque baseline de `superiority_vs + non_inferiority_vs`, readiness d'abord (strict → `RuntimeError` ; sinon skip + log, **jamais** de faux `pass`/`fail`), puis `_load_pairs(base)`, son **propre** `causal_macro_f1_global` (avec `baseline=<nom>`), `paired_diff_bootstrap` apparié, verdict (`superiority` pour NL : IC de la différence > 0 ; `non_inferiority` pour Semantic Regexes : borne basse > −`nim_delta`), et **couverture** (paires MorphoRepr, paires baseline, features partagées). `metrics.model_run_id` est renseigné pour **toutes** ces métriques (jamais `NULL` pour une métrique model-specific). La perte de couverture n'est pas masquée (comparaison appariée sur l'ensemble partagé, couverture rapportée).

**Orchestrateur.** Nouvelle phase `p4_predict_baselines` (avant `p4_score`), gardée par `baseline_predictions.enabled` (défaut `false`, **non auto-activée**) ; `baseline_predictor` importé. `causal_scoring.run_in_pipeline` reste `false`.

**Tests ajoutés** (`tests/test_baseline_predictions.py`, déterministes — provider et/ou prédiction monkeypatchés, classifieurs via `cs.CLASSIFIER_BY_PROPERTY`) : chargement des annotations baselines ; sauvegarde des prédictions `predictor_nl_labels`/`predictor_semantic_regex` (model_run_id, feature_uid, status) ; format JSON accepté par `_extract_predicted_directions` ; absence d'annotation + `require_existing_baseline_annotations=true` → `RuntimeError` (rien de fabriqué) ; `assert_baseline_predictions_ready` (passe/échoue) ; `_load_pairs("nl_labels")` et `_load_pairs("semantic_regex")` ; `run()` avec comparaisons (scores MorphoRepr+NL+SemReg, paired diff, verdicts supériorité/non-infériorité, model_run_id jamais NULL) ; baseline absente → strict raise / non-strict skip sans verdict ; model-aware ; split-aware ; couverture (features partagées uniquement).

**Statut.** `run_baseline_comparisons=true` est désormais possible **en dev run contrôlé** si les prédictions baselines existent. `run_intervention_controls()` reste un **contrat** (non implémenté ici). Aucun juge LLM dans la métrique primaire. Limites restantes : `keyword_tags`/`morphorepr_shuffled` non branchées ; `run_intervention_controls()` contractuel ; pas d'exécution réelle en CI standard (dev opt-in, provider réel requis) ; qualité des prédictions baselines dépendante du modèle primaire et des prompts (à geler avant tout full run) ; **aucune validation causale complète revendiquée**.
