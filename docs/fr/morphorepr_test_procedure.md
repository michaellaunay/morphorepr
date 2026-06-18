# MorphoRepr — Procédure de test complète (v6.4.1)
## Infrastructure expérimentale robuste pour une évaluation reproductible

*Version 6.4.1 — Juin 2026. Cohérente avec l'article v0.28. Micro-patch : pré-vérification avant soumission que les `custom_id` des requêtes correspondent EXACTEMENT aux `batch_items`, et clarification de `assert_steering_ready` comme garde PRÉ-PILOT Phase 4 (non bloquante pour un dev run de plomberie hors steering) — voir Section 19. La v6.4.1 reste une SPÉCIFICATION : `steer_feature()`, `run_intervention_controls()` et `causal_scorer._load_pairs()` sont des contrats non implémentés (gardes `run_in_pipeline`). Elle est jugée solide pour un dev run de plomberie hors Phase 4.*

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

**Règle 9 — La Phase 4 est un contrat d'implémentation, pas une implémentation**
`steer_feature()` contient des placeholders et lève `NotImplementedError`. Le pilot run **ne peut être lancé** que lorsque, sur un dev run de ≥ 5 features, `steer_feature()` produit réellement : `text_before`, `text_after`, `activation_before`, `activation_after`, le `delta` d'activation obtenu, et un `ood_flag` vérifiable (Section 7, garde `assert_steering_ready`).

**Règle 10 — Identité de feature robuste**
Un `feature_index` seul ne suffit pas : le même index peut exister dans plusieurs couches, releases SAE ou modèles. L'identité canonique est `feature_uid = {model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}`, avec contrainte d'unicité. Au sein d'un run unique (un modèle, une release, un ensemble de couches), `feature_index` reste un identifiant pratique pour les jointures ; `feature_uid` garantit l'unicité cross-couche/cross-SAE et est propagé aux tables aval.

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
│   ├── api_utils.py
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
description: "Full frozen run MorphoRepr v0.28 — 500 features"

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

# Modèles (identifiants exacts API Anthropic)
models:
  semantic_judgment: "claude-sonnet-4-6"
  scoring: "claude-haiku-4-5-20251001"
  batch: true
  max_tokens_judgment: 800
  max_tokens_scoring: 400

# Prompts
prompts:
  label_agent:    "prompts/label_agent_v1.txt"
  encoder:        "prompts/encoder_agent_v1.txt"
  predictor:      "prompts/predictor_agent_v1.txt"
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
  # La Phase 4 (steering) est un CONTRAT non implémenté (Section 7). Désactivée par défaut
  # pour permettre un dev run "plomberie hors steering" sans crash ; passer à true UNIQUEMENT
  # une fois steer_feature() réellement implémenté (et assert_steering_ready passant).
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

# Scoring causal (Phase 4) — métrique primaire déterministe. Désactivé par défaut tant que
# causal_scorer._load_pairs() (lecture prédictions/observations) n'est pas implémenté ; gère
# p4_predict, p4_score ET p4_qualitative (sans steering, ces phases n'ont pas de matière).
causal_scoring:
  run_in_pipeline: false

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

## 3. Schéma SQLite complet (v6.4.1)

```sql
-- db/schema.sql  —  Version 6.4.1, ne jamais modifier après le full run

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
-- Suivi des batchs (reprise après crash)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS batches (
    batch_id        TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
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
    -- Unicité sur feature_uid (PAS feature_index, ambigu entre couches/SAEs — Règle 10).
    -- Combinée à la vérification de divergence dans save_agent_output(), rend la persistance idempotente.
    UNIQUE(run_id, feature_uid, agent_name, run_number)
);

-- ─────────────────────────────────────────────
-- Métriques calculées
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS metrics (
    metric_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
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
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITÉ LOGIQUE
    feature_index   INTEGER NOT NULL,                       -- informatif
    baseline_name   TEXT NOT NULL,
    annotation_run1 TEXT,
    annotation_run2 TEXT,
    fidelity_auc    REAL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(run_id, feature_uid, baseline_name)
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
    UNIQUE(run_id, feature_uid, intervention_space, magnitude_key,
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
    phase           TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    model           TEXT NOT NULL,
    tokens_input    INTEGER NOT NULL,
    tokens_output   INTEGER NOT NULL,
    batch_id        TEXT,
    cost_usd        REAL NOT NULL,
    cumulative_cost REAL,
    timestamp       TEXT NOT NULL,
    -- Idempotence du coût par batch : à la reprise, un coût déjà loggé pour ce
    -- (run, batch, phase, agent) n'est PAS recompté (log_api_cost en INSERT OR IGNORE).
    -- NB : SQLite autorise plusieurs NULL ; les appels non-batch (batch_id NULL) ne sont pas dédoublonnés ici.
    UNIQUE(run_id, batch_id, phase, agent_name)
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
                                 split: Optional[str] = None) -> list[dict]:
    """Retourne les features sans output pour cet agent/run_number. Idempotent.
    Clé logique : feature_uid (Règle 10), pas feature_index."""
    with get_conn() as conn:
        done = {
            r["feature_uid"]
            for r in conn.execute("""
                SELECT feature_uid FROM agent_outputs
                WHERE run_id = ? AND agent_name = ? AND run_number = ?
            """, (run_id, agent_name, run_number)).fetchall()
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
                      feature_uid: Optional[str] = None):
    """Persistance idempotente MAIS NON SILENCIEUSE en cas de divergence.
    Clé logique : feature_uid (Règle 10), REQUIS.

    - Si aucune sortie n'existe pour (run_id, feature_uid, agent_name, run_number) → INSERT.
    - Si une sortie IDENTIQUE existe (même output_json, raw_output, status) → ignorer (reprise).
    - Si une sortie DIFFÉRENTE existe → RuntimeError (ne pas masquer une divergence).
    Évite le piège du INSERT OR IGNORE qui avale silencieusement une sortie différente."""
    if feature_uid is None:
        raise ValueError("save_agent_output : feature_uid est requis (identité logique, Règle 10).")
    new_json = json.dumps(output_json) if output_json is not None else None
    with get_conn() as conn:
        existing = conn.execute("""
            SELECT output_json, raw_output, status FROM agent_outputs
            WHERE run_id=? AND feature_uid=? AND agent_name=? AND run_number=?
        """, (run_id, feature_uid, agent_name, run_number)).fetchone()
        if existing is not None:
            same = (existing["output_json"] == new_json
                    and existing["raw_output"] == raw_output
                    and existing["status"] == status)
            if same:
                return                       # reprise idempotente
            raise RuntimeError(
                f"Divergence de sortie pour (run={run_id}, feature_uid={feature_uid}, "
                f"agent={agent_name}, run_number={run_number}) : une sortie DIFFÉRENTE "
                f"est déjà persistée. Run bloqué (ne pas écraser silencieusement)."
            )
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, feature_uid, feature_index, agent_name, run_number,
            new_json, raw_output, status, error_msg,
            tokens_input, tokens_output, batch_id, cost_usd,
            coefficient_type,
            datetime.utcnow().isoformat()
        ))


def register_batch(batch_id: str, run_id: str, phase: str,
                   agent_name: str, run_number: int, n_requests: int):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO batches (
                batch_id, run_id, phase, agent_name, run_number,
                n_requests, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?)
        """, (batch_id, run_id, phase, agent_name, run_number,
              n_requests, datetime.utcnow().isoformat()))


def register_batch_with_items(batch_id: str, run_id: str, phase: str,
                              agent_name: str, run_number: int, n_requests: int,
                              items: list[dict]):
    """Enregistre le batch ET son mapping custom_id → feature_uid dans UNE SEULE transaction
    (crash-safe : pas de fenêtre où le batch existe sans sa map). items : [{custom_id,
    feature_uid, feature_index}, …]. Idempotent côté items (INSERT OR IGNORE)."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO batches (
                batch_id, run_id, phase, agent_name, run_number,
                n_requests, status, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?)
        """, (batch_id, run_id, phase, agent_name, run_number,
              n_requests, datetime.utcnow().isoformat()))
        for it in items:
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid, feature_index)
                VALUES (?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"]))


def mark_batch_consumed(batch_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE batches SET status='consumed', consumed_at=?
            WHERE batch_id=?
        """, (datetime.utcnow().isoformat(), batch_id))


def save_batch_items(batch_id: str, items: list[dict]):
    """Persiste la correspondance custom_id → feature_uid d'un batch (table batch_items),
    pour une reprise crash-safe. items : [{custom_id, feature_uid, feature_index}, …].
    Idempotent (INSERT OR IGNORE) : un re-soumission/re-poll ne duplique pas."""
    with get_conn() as conn:
        for it in items:
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid, feature_index)
                VALUES (?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"]))


def load_batch_item_map(batch_id: str) -> dict[str, dict]:
    """Recharge la map custom_id → {feature_uid, feature_index} persistée pour ce batch."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT custom_id, feature_uid, feature_index FROM batch_items WHERE batch_id=?
        """, (batch_id,)).fetchall()
    return {r["custom_id"]: {"feature_uid": r["feature_uid"],
                             "feature_index": r["feature_index"]} for r in rows}


def get_unconsumed_batch(run_id: str, phase: str,
                         agent_name: str, run_number: int) -> Optional[str]:
    """Retourne le batch_id d'un batch soumis mais non consommé, si existant."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT batch_id FROM batches
            WHERE run_id=? AND phase=? AND agent_name=?
              AND run_number=? AND status='submitted'
            ORDER BY submitted_at DESC LIMIT 1
        """, (run_id, phase, agent_name, run_number)).fetchone()
    return row["batch_id"] if row else None


def log_api_cost(run_id: str, phase: str, agent_name: str,
                 model: str, tokens_in: int, tokens_out: int,
                 batch_id: Optional[str], cost: float) -> float:
    """Loggue le coût et met à jour le cumul. IDEMPOTENT PAR BATCH : grâce à la contrainte
    UNIQUE(run_id, batch_id, phase, agent_name) sur api_usage, un coût déjà loggé pour ce
    (run, batch, phase, agent) n'est PAS recompté à la reprise (anti double-comptage du budget).
    NB : pour les appels non-batch (batch_id NULL), SQLite n'applique pas l'unicité — la
    déduplication ne vaut que pour les batchs (cas de la reprise après crash)."""
    with get_conn() as conn:
        # Non-silencieux : si un coût est DÉJÀ loggé pour ce batch avec un montant
        # différent, c'est une divergence à signaler (et non à ignorer).
        if batch_id is not None:
            prev = conn.execute("""
                SELECT cost_usd, tokens_input, tokens_output FROM api_usage
                WHERE run_id=? AND batch_id=? AND phase=? AND agent_name=?
            """, (run_id, batch_id, phase, agent_name)).fetchone()
            if prev is not None and (
                abs(prev["cost_usd"] - cost) > 1e-9
                or prev["tokens_input"] != tokens_in
                or prev["tokens_output"] != tokens_out
            ):
                raise RuntimeError(
                    f"Divergence de coût pour batch {batch_id} (run={run_id}, {phase}/{agent_name}) : "
                    f"déjà loggé {prev['cost_usd']:.4f}$ "
                    f"({prev['tokens_input']}/{prev['tokens_output']} tk), "
                    f"recalculé {cost:.4f}$ ({tokens_in}/{tokens_out} tk). Run bloqué."
                )
        cur = conn.execute("""
            INSERT OR IGNORE INTO api_usage (
                call_id, run_id, phase, agent_name, model,
                tokens_input, tokens_output, batch_id, cost_usd,
                cumulative_cost, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """, (
            str(uuid4()), run_id, phase, agent_name, model,
            tokens_in, tokens_out, batch_id, cost,
            datetime.utcnow().isoformat()
        ))
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        current = row["total_cost_usd"] if row else 0.0
        if cur.rowcount == 0:
            # Coût déjà loggé pour ce batch (reprise, montant identique) → ne pas recompter.
            logger.info(f"Coût déjà loggé pour batch {batch_id} — non recompté.")
            return current
        cumulative = current + cost
        conn.execute(
            "UPDATE runs SET total_cost_usd=? WHERE run_id=?",
            (cumulative, run_id)
        )
        conn.execute(
            "UPDATE api_usage SET cumulative_cost=? "
            "WHERE run_id=? AND phase=? AND agent_name=? "
            "AND (batch_id = ? OR (batch_id IS NULL AND ? IS NULL)) "
            "AND cumulative_cost IS NULL",
            (cumulative, run_id, phase, agent_name, batch_id, batch_id)
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
Wrapper Batch API avec reprise après crash.
La config est toujours passée explicitement — aucun appel load_config() ici.
"""
import anthropic
import hashlib
import json
import logging
import time
from typing import Optional, Callable
from utils.db_utils import (register_batch, register_batch_with_items,
                             mark_batch_consumed,
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


def build_batch_item_rows(features: list[dict]) -> list[dict]:
    """Lignes pour batch_items (persistance crash-safe du mapping)."""
    return [{"custom_id": feature_custom_id(f),
             "feature_uid": f["feature_uid"],
             "feature_index": f["feature_index"]} for f in features]


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
                          poll_interval: Optional[int] = None,
                          max_wait_seconds: Optional[int] = None) -> list[dict]:
    """
    Soumet un batch (ou récupère un batch non consommé existant) et retourne les résultats.
    Config passée explicitement partout. Chaque résultat est enrichi de `feature_uid` à partir
    de la map PERSISTÉE (batch_items), robuste à la reprise.

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
    if requires_feature_mapping and not batch_items:
        raise ValueError(
            "batch_items est requis pour un batch feature-level "
            "(passer build_batch_item_rows(features)). "
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
    batch_cfg        = config.get("batch", {})
    poll_interval    = poll_interval    or batch_cfg.get("poll_interval_seconds", 60)
    max_wait_seconds = max_wait_seconds or batch_cfg.get("max_wait_seconds", 86400)
    existing = get_unconsumed_batch(run_id, phase, agent_name, run_number)
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
        # Enregistrement ATOMIQUE batch + mapping (pas de fenêtre batch-sans-map).
        register_batch_with_items(batch_id, run_id, phase, agent_name,
                                  run_number, len(requests), batch_items or [])
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
                              total_in, total_out, batch_id, cost)
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

## 7. Agent de steering — contrat d'implémentation (v6)

```python
# agents/steerer.py
"""
Phase 4 — Steering d'activation SAE (CONTRAT D'IMPLÉMENTATION v6).

Cette section est un CONTRAT : steer_feature() contient des placeholders et lève
NotImplementedError. Le pilot run est bloqué tant que assert_steering_ready() échoue
(Règle 9).

Spécification de l'intervention (v6) :
  - Espace :          'residual_add_decoder' (ajout d'un multiple de W_dec au résiduel) OU
                      'sae_latent_clamp' (clamp de l'activation latente). ATTENTION : ajouter
                      k×W_dec au résiduel ne garantit PAS une hausse de k×p99 de l'activation
                      latente mesurée (norme du décodeur, encodage, interférences, non-linéarités).
                      On RAPPORTE donc le delta OBTENU (achieved_delta), pas seulement la magnitude visée.
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

Chemins d'accès au modèle (implémenter l'un d'eux avant le pilot run) :
  A. TransformerLens — pour les modèles proxy open-weight de style GPT
  B. nnsight         — si accès direct à un modèle de production disponible
  C. Poids locaux    — si modèle open-weight compatible SAE disponible

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


def steer_feature(model,
                  sae,
                  feature_index: int,
                  magnitude: float,
                  probe_sentences: list[str],
                  feature_stats: dict,
                  config: dict) -> list[dict]:
    """
    Applique le steering et retourne les paires avant/après + le delta OBTENU.

    La détection OOD utilise activation_p99/mean/std depuis feature_stats (table features),
    PAS sae.W_dec[feature_index].norm() (grandeur différente). Le delta latent obtenu
    (achieved_delta) est mesuré et rapporté : ajouter magnitude·W_dec au résiduel ne garantit
    pas une hausse égale de l'activation latente (Section 7).

    Étapes d'implémentation :
    1. Tokeniser la phrase-sonde
    2. Forward pass, enregistrer l'activation latente cible AVANT (activation_before)
    3. Intervenir selon intervention_space :
       - 'residual_add_decoder' : ajouter magnitude · sae.W_dec[feature_index] au résiduel
       - 'sae_latent_clamp'     : clamper l'activation latente cible à la valeur visée
    4. Ré-exécuter le forward pass avec l'intervention
    5. Mesurer l'activation latente cible APRÈS (activation_after) ; décoder text_before/after
    6. achieved_delta = activation_after - activation_before ; calculer ood_flag (critère mixte)
    """
    results = []

    for probe_id, sentence in enumerate(probe_sentences, 1):
        try:
            # ── PLACEHOLDER — implémenter le steering spécifique au modèle ──
            text_before       = sentence
            text_after        = None          # DOIT être remplacé par l'implémentation
            activation_before = None
            activation_after  = None
            # ─────────────────────────────────────────────────────────────────

            # Garde : échouer bruyamment si les placeholders ne sont pas remplacés
            if text_after is None or text_after == sentence:
                raise NotImplementedError(
                    f"Placeholder steer_feature() non remplacé pour "
                    f"feature {feature_index}, magnitude {magnitude}.\n"
                    f"Implémenter le steering spécifique au modèle avant le pilot run."
                )

            achieved_delta = (None if activation_after is None or activation_before is None
                              else activation_after - activation_before)
            ood = _is_ood(activation_after, activation_before, feature_stats, config)

            results.append({
                "probe_id":          probe_id,
                "text_before":       text_before,
                "text_after":        text_after,
                "activation_before": activation_before,
                "activation_after":  activation_after,
                "achieved_delta":    achieved_delta,
                "ood_flag":          ood
            })
        except NotImplementedError:
            raise   # propager — ne pas avaler les erreurs d'implémentation
        except Exception as e:
            logger.warning(
                f"Erreur steering feature {feature_index} "
                f"probe {probe_id} magnitude {magnitude}: {e}"
            )
            results.append({
                "probe_id":          probe_id,
                "text_before":       sentence,
                "text_after":        None,
                "activation_before": None,
                "activation_after":  None,
                "achieved_delta":    None,
                "ood_flag":          0,
                "error":             str(e)
            })
    return results


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
            WHERE ao.run_id = ? AND ao.agent_name = 'encoder'
              AND ao.run_number = 1 AND ao.status = 'ok'
        """, (run_id,)).fetchall()

    random_features = [dict(r) for r in rows if r["split"] == "random"]

    # Sous-échantillon seedé — PAS [:n] qui dépendrait de l'ordre de la DB
    rng       = random.Random(seed)
    subsample = rng.sample(random_features,
                           min(n_subsample, len(random_features)))
    subsample_uids = {f["feature_uid"] for f in subsample}

    # Sous-échantillon : courbe dose-réponse complète (multiples de p99, contrôle 0 inclus)
    _run_steering_batch(run_id, model, subsample, dose_rel,
                        probe_sets, gens, config, mode, legacy_abs)

    # Features restants : contrôle (0) + magnitude primaire uniquement
    remaining = [f for f in random_features
                 if f["feature_uid"] not in subsample_uids]
    _run_steering_batch(run_id, model, remaining, [0.0, primary_rel],
                        probe_sets, gens, config, mode, legacy_abs)

    logger.info("Phase 4 steering terminée")


def _insert_steering_result(conn, run_id, feat, space, mag_abs, mag_rel, magnitude_key,
                            family, category, g, r, config):
    """Insertion NON SILENCIEUSE : conserve la 1ʳᵉ sortie d'une cellule, mais journalise
    toute tentative de réécriture DIFFÉRENTE (table steering_duplicate_attempts) au lieu de
    l'ignorer en silence (cohérent avec save_agent_output)."""
    key = (run_id, feat.get("feature_uid"), space, magnitude_key,
           family, category, r["probe_id"], g)
    existing = conn.execute("""
        SELECT result_id, text_after FROM steering_results
        WHERE run_id=? AND feature_uid=? AND intervention_space=? AND magnitude_key=?
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
            result_id, run_id, feature_uid, feature_index,
            intervention_space, magnitude, magnitude_rel, magnitude_key,
            probe_id, probe_family, probe_category, generation_index,
            text_before, text_after, layer, token_position,
            activation_before, activation_after, achieved_delta,
            ood_flag, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uuid4()), run_id, feat.get("feature_uid"), feat["feature_index"], space,
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
                        legacy_abs: float):
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
                            _insert_steering_result(conn, run_id, feat, space, mag_abs,
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


def _load_pairs(run_id: str, method: str) -> list[dict]:
    """Assemble les couples (feature_uid, propriété robuste) {predicted, observed} pour une
    méthode d'annotation. Contrat : predicted vient de l'agent 'predictor_{method}', observed
    des classifieurs (stockés en metrics/steering). Restreint aux ROBUST_PROPERTIES."""
    raise NotImplementedError(
        "_load_pairs() : brancher la lecture des directions prédites (agent_outputs "
        f"'predictor_{method}') et observées (classifieurs) en couples robustes. "
        "Les fonctions de scoring ci-dessus sont, elles, complètes et testées."
    )


def run(run_id: str, config: dict):
    """Métrique primaire : macro-F1 global sur couples + bootstrap clusterisé par feature,
    et différences appariées vs baselines (supériorité vs NL ; non-infériorité vs Semantic
    Regexes avec marge nim_delta). Persiste le tout dans metrics."""
    nim = config["thresholds"].get("nim_delta", 0.05)
    mr = _load_pairs(run_id, "morphorepr")          # lève NotImplementedError tant que non branché
    point = compute_global_macro_f1(mr)
    ci    = feature_clustered_bootstrap(mr, config["stats"].get("bootstrap_resamples", 10000),
                                        config.get("seed", 42))
    results = {"morphorepr": {**point, **ci}, "comparisons": {}}
    for base in config["stats"].get("superiority_vs", []) + config["stats"].get("non_inferiority_vs", []):
        d = paired_diff_bootstrap(mr, _load_pairs(run_id, base),
                                  config["stats"].get("bootstrap_resamples", 10000),
                                  config.get("seed", 42))
        mode = "non_inferiority" if base in config["stats"].get("non_inferiority_vs", []) else "superiority"
        d["verdict"] = (("pass" if d["ci_low"] > -nim else "fail") if mode == "non_inferiority"
                        else ("pass" if d["ci_low"] > 0 else "fail"))
        results["comparisons"][base] = {"mode": mode, **d}
    with get_conn() as conn:
        conn.execute("""INSERT INTO metrics (metric_id, run_id, phase, split, metric_name,
                        value, ci_low, ci_high, n_samples, baseline, computed_at)
                        VALUES (?, ?, 'p4_score', 'random', 'causal_macro_f1_global',
                                ?, ?, ?, ?, NULL, ?)""",
                     (str(uuid4()), run_id, point["macro_f1"], ci["ci_low"], ci["ci_high"],
                      point["n_pairs"], datetime.utcnow().isoformat()))
        for base, d in results["comparisons"].items():
            conn.execute("""INSERT INTO metrics (metric_id, run_id, phase, split, metric_name,
                            value, ci_low, ci_high, n_samples, baseline, computed_at)
                            VALUES (?, ?, 'p4_score', 'random', 'causal_macro_f1_paired_diff',
                                    ?, ?, ?, ?, ?, ?)""",
                         (str(uuid4()), run_id, d["diff"], d["ci_low"], d["ci_high"],
                          d["n_shared_features"], base, datetime.utcnow().isoformat()))
    logger.info(f"Score causal global : macro-F1={point['macro_f1']} IC95={ci}")
    return results
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

    register_batch("b1", "r1", "phase3", "encoder", 1, 100)
    assert get_unconsumed_batch("r1", "phase3", "encoder", 1) == "b1"

    mark_batch_consumed("b1")
    assert get_unconsumed_batch("r1", "phase3", "encoder", 1) is None


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
                output_id, run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?,?,?,?,'encoder',1,?,?,?,NULL,100,50,NULL,0.0,
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
        conn.execute("""INSERT INTO agent_outputs (output_id, run_id, feature_uid,
            feature_index, agent_name, run_number, output_json, raw_output, status,
            error_msg, tokens_input, tokens_output, batch_id, cost_usd, coefficient_type,
            created_at) VALUES (?,?,?,?, 'encoder',1,?, 'r','ok',NULL,1,1,NULL,0.0,
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
    register_batch("b1", "r1", "p3", "encoder", 1, len(feats))
    save_batch_items("b1", build_batch_item_rows(feats))

    m = load_batch_item_map("b1")
    assert m[feature_custom_id(feats[0])]["feature_uid"] == _uid(6, 123)
    assert m[feature_custom_id(feats[1])]["feature_uid"] == _uid(9, 123)
    # idempotent : re-persister ne duplique pas (PK batch_id+custom_id)
    save_batch_items("b1", build_batch_item_rows(feats))
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
                              build_batch_item_rows(feats))
    # le batch est enregistré (récupérable) ET la map est présente, dans la même transaction
    assert get_unconsumed_batch("r1", "p3", "encoder", 1) == "bX"
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

---

## 10. Orchestrateur

```python
# orchestrator.py
"""
Orchestrateur MorphoRepr v6.4.1 — run gelé et auditable.

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
from utils.db_utils import get_conn, check_budget

from agents import loader, ranker, cluster, labeler, consistency
from agents import encoder, fidelity, steerer, predictor, causal_scorer, reporter
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

    logger.info(f"Run initialisé : {run_id}")
    logger.info(f"  Git commit    : {git_commit[:16]}")
    logger.info(f"  Config hash   : {config_hash[:16]}")
    logger.info(f"  Corpus hash   : (gelé après p1_load/p1_rank)")
    logger.info(f"  Lexique hash  : {lexicon_hash[:16]}")
    if proxy.get("enabled"):
        logger.info(f"  Modèle proxy  : {proxy.get('name')} (Sonnet inaccessible)")
    return run_id


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
    # Phases de scoring causal : gardées par causal_scoring.run_in_pipeline (sans steering ni
    # observations classifieurs, elles n'ont pas encore de matière ; _load_pairs() = contrat).
    ("p4_predict",     lambda rid, cfg: (predictor.run(rid)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_predict désactivé (causal_scoring.run_in_pipeline=false)")),
                                                                     "Prédiction causale"),
    # Métrique PRIMAIRE = score déterministe (prédiction vs classifieurs), SANS juge LLM (Règle 8)
    ("p4_score",       lambda rid, cfg: (causal_scorer.run(rid, cfg)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_score désactivé (_load_pairs non implémenté)")),
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
# (causal_scoring.run_in_pipeline=false). La métrique causale primaire (déterministe,
# p4_score = causal_scorer) ne sera testée qu'APRÈS implémentation de steer_feature(), des
# classifieurs d'observation et de causal_scorer._load_pairs().

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
