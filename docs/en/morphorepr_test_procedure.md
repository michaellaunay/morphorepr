# MorphoRepr — Complete Test Procedure (v6.8.0)
## Robust Experimental Infrastructure for Reproducible Evaluation

*Version 6.8.0 — June 2026. Consistent with paper (≥ v0.29). **Baseline predictions (Option B)** for `nl_labels` and `semantic_regex`: the new `agents/baseline_predictor.py` module produces canonical direction-prediction `agent_outputs` (agent names `predictor_nl_labels` / `predictor_semantic_regex`) from annotations stored in the `baselines` table, through the primary provider (Rule 11) and **separate prompts** that avoid MorphoRepr terminology. Steering is **not** re-run: only the prediction path differs, which makes the **primary paired comparisons** executable in a controlled dev run — superiority vs NL labels and non-inferiority vs Semantic Regexes. `causal_scorer.run()` now computes, when `run_baseline_comparisons=true`, each baseline's own score, the paired difference, the verdict and **coverage**, guarded by `assert_baseline_predictions_ready` (strict → `RuntimeError`; otherwise explicit skip **without a verdict**; never a false `pass`/`fail`). `keyword_tags` and `morphorepr_shuffled` remain **not wired**. No LLM judge is used in the primary metric. No schema change relative to v6.5.3 (`metrics.model_run_id` is populated for every model-specific metric). MorphoRepr `_load_pairs()` (v6.7.0), the multi-model layer and `steer_feature()` remain intact; `run_intervention_controls()` remains a contract; `causal_scoring.run_in_pipeline` and `baseline_predictions.enabled` remain `false` and are not automatically enabled. **No full scientific result is claimed.** See Section 27.*
---

## Guiding Principles

**Rule 1 — Separation of roles; frozen and auditable run**
Claude Code is used for development, debugging, and supervision only. The final experimental run is driven exclusively by `python orchestrator.py --config configs/run_v1.yaml`. The run is **frozen and auditable** rather than strictly deterministic : the code, configuration, prompts, corpus, and lexicon are frozen and verified by hash, and all raw agent outputs are archived. However, the outputs of LLM calls are **stochastic** (and necessarily so for the two annotation-consistency runs) ; the run is therefore *re-analyzable* from archived outputs, without being *regenerable* identically. No code modification or untracked agentic intervention during execution.

**Rule 2 — Three execution levels**

| Mode | n features | Objective | Results |
|------|-----------|-----------|---------|
| Dev run | 5 | Plumbing, DB, parsing, batch, classifiers | Non-scientific |
| Pilot run | 30–50 | Prompt, threshold, and classifier calibration | Exploratory |
| Full frozen run | 500 | Publication | Frozen before launch |

If thresholds or prompts are adjusted after observing pilot-run results, explicitly declare this as calibration in the paper.

**Rule 3 — Full freeze before the full run**
Fixed and verified Git commit, hashed configuration, hashed prompts (full SHA256), hashed corpus, hashed lexicon, documented sampling policy. On `--resume`, all these values are rechecked before resuming.

**Rule 4 — No resume after code modification**
If code is modified after a phase failure, create a new run_id with a new Git commit. Never resume a run with a commit different from the one recorded at initialization.

**Rule 5 — Validation model: open-weight proxy by default**
Full experimental access to the activations of a production model (controlled steering with before/after generation) is not guaranteed by public interfaces, so causal validation runs **by default on an open-weight proxy model with public SAEs** (e.g., GPT-2, Pythia, or Mistral via `sae_lens`). In this case: (a) the whole pipeline (Phases 1–5) operates on the proxy SAEs; (b) all causal conclusions are limited to the proxy model; (c) Claude 3 Sonnet / Neuronpedia examples remain illustrative only; and (d) this must be explicitly stated in the Methods section of the paper. If direct access to the activations of a production model is obtained, set `proxy_model.enabled=false` and provide the corresponding access paths.

**Rule 6 — Feature-normalized steering at the feature layer**
The primary steering magnitude is **feature-normalized** (a multiple of the feature activation 99th percentile, column `activation_p99`), which makes it comparable across features and layers ; the historical absolute magnitude (+5) is kept as a secondary condition. Steering targets the **feature's own layer** (column `layer`), not a global layer. Instances pushed out of distribution (`ood_flag=1`) are **excluded from the primary metric** and reported separately.

**Rule 7 — Comparison on a shared set AND global utility**
The head-to-head causal-validity comparison (MorphoRepr vs NL labels vs Semantic Regexes) is computed **on the same feature set** — the intersection of features covered by MorphoRepr (confidence ≥ 0.5): this is **conditional performance**. Since this says nothing about utility when coverage differs strongly, we also **systematically** report **global (end-to-end) utility** on the full random set (`coverage × mean causal score`, or an integrated score with UNCOVERED = abstention/zero score, pre-registered rule). The primary causal-validity score is a **macro-F1 computed globally over all (feature, robust property) pairs**; the criterion is **superiority** vs NL (CI of the paired difference excluding 0) and **non-inferiority** vs Semantic Regexes (CI lower bound > −δ, pre-registered `nim_delta` margin).

**Rule 8 — Deterministic primary metric (without an LLM judge)**
The prediction/observation comparison for the primary metric is **deterministic** : the direction predicted by the prediction agent is compared by **code** to the direction measured by the **pre-registered classifiers**. No LLM judge intervenes in the primary metric. An LLM judge (`qualitative_judge`) is reserved for qualitative analyses, ambiguous cases, and assisted audit (secondary metrics). The bootstrap is **clustered by feature** (the resampling unit is the feature, not the feature-property pair).

**Rule 9 — Phase 4 is an implementation contract, not an implementation**
`steer_feature()` contains placeholders and raises `NotImplementedError`. The pilot run **can only be launched** when, on a dev run with ≥ 5 features, `steer_feature()` actually produces : `text_before`, `text_after`, `activation_before`, `activation_after`, the achieved activation `delta`, and a verifiable `ood_flag` (Section 7, guard `assert_steering_ready`).

**Rule 10 — Robust feature identity**
A `feature_index` alone is not sufficient: the same index may exist in several layers, SAE releases, or models. The canonical identity is `feature_uid = {model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}`, with a uniqueness constraint. Within a single run (one model, one release, one set of layers), `feature_index` remains a convenient identifier for joins; `feature_uid` guarantees cross-layer/cross-SAE uniqueness and is propagated to downstream tables.

---


## Model openness and reproducibility policy

**Why a proprietary model alone is not enough.** A model accessible only through an API may be updated, deprecated, or removed without notice, without access to its weights, tokenizer, data, or internal parameters. A scientific conclusion that exists only behind such an API is not independently verifiable or replayable over time; it depends on a non-archivable artifact. Reproducibility therefore requires at least one condition to rely on a model whose exact artifact can be frozen and redistributed.

**Why primary results must come from an open model.** For another laboratory to replay the experiment and obtain the same numbers, up to hardware variations, the model revision, tokenizer, backend and inference parameters must be known and archived. MorphoRepr's **primary claims** are therefore computed on a **Tier A fully open** or **Tier B open-weight** model; proprietary results serve as an **external comparison**.

**Distinguishing open-source, open-weight and proprietary API.**
- *Open-source / fully open (Tier A)*: weights + tokenizer + inference code + config + hyperparameters + license +, ideally, data information. This is the strongest reproducibility level.
- *Open-weight (Tier B)*: public weights and tokenizer, but partly closed training data or pretraining details. This is **computationally reproducible** (same weights → same outputs with fixed backend/seed), but not necessarily fully transparent about origin.
- *Proprietary API (Tier C)*: no weights and no tokenizer; behavior may change over time. Comparison/secondary use only.

**Reporting Tier A/B and Tier C separately.** Metrics are reported **by model and by tier**. The main table explicitly compares the open primary model with the proprietary secondary model, with the difference and interpretation. A Tier C score is never merged into a “primary” score.

**Avoiding open-washing.** A model that publishes only its weights, without sufficient data, code, or configuration, is **not** called “open source”; it is called *open-weight* (Tier B). The tier stored in `model_runs.provider_tier` must reflect what is actually available, not the provider's marketing.

**Artifacts to archive for reproduction.** For every `model_run`: exact model and tokenizer revisions, `weights_sha256`, `tokenizer_sha256`, Docker/Conda image (`inference_env_hash`), CUDA version, backend version, `precision`/`quantization`, inference parameters (`generation_params_json`: temperature, top_p, seed, max_new_tokens), hashed prompts, and **raw outputs**. Without these artifacts, a run cannot claim reproducibility and cannot support a primary claim.

**README section to update.** The README should now point to paper **v0.29** and test procedure **v6.8.0**, and remove obsolete references to the v0.26 paper and to the old “non-overlapping CIs” go/no-go criterion.

```markdown
## MorphoRepr — repository status
- Paper: v0.29 (open-model policy; primary claims on an open model).
- Test procedure: v6.8.0 (`steer_feature()`, `causal_scorer._load_pairs()`, and baseline predictions for `nl_labels` / `semantic_regex` wired for controlled dev runs; Phase 4 disabled by default).
- Causal-validity criterion: superiority over natural-language labels (feature-clustered paired-difference CI excluding 0) AND non-inferiority to Semantic Regexes (pre-registered δ margin). The old “non-overlapping CIs” criterion is OBSOLETE.

## Reproducibility and open-weight models
- MorphoRepr may use proprietary models (e.g. Anthropic) for development and secondary comparison.
- Primary scientific claims are designed to be reproducible with open-weight or fully open models.
- The protocol archives exact model revisions, hashes, inference backends, prompts, configurations, and raw outputs.
- Inference goes through `ModelProvider` for the open primary model; `api_utils` is a LEGACY Anthropic Batch wrapper for the Tier C secondary condition only.
- Anthropic results are reported as a secondary reference condition unless explicitly reproduced by an open-weight model.
- Primary claims are restricted to Tier A/B models.
```

## 1. Project Structure

```
morphorepr-pipeline/
├── CLAUDE.md                        ← Claude Code instructions (dev/supervision only)
├── configs/
│   ├── dev_run.yaml
│   ├── pilot_run.yaml
│   └── run_v1.yaml                  ← frozen full-run config
├── db/
│   ├── schema.sql
│   ├── features.db
│   └── lexicon.json
├── prompts/
│   ├── label_agent_v1.txt
│   ├── encoder_agent_v1.txt
│   ├── predictor_agent_v1.txt
│   ├── predictor_nl_labels_v1.txt
│   ├── predictor_semantic_regex_v1.txt
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
│   ├── steerer.py                   ← fully specified in Section 7
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
│   ├── morphorepr_parser.py         ← single parser for all metrics
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
│   └── probes/                      ← one probe family/category per file
│       ├── probes_neutral.txt       ← neutral probes (≥50 for primary, 20 for pilot)
│       ├── probes_code.txt          ← compatible probes "code"
│       ├── probes_social.txt        ← compatible probes "social"
│       ├── probes_temporal.txt      ← compatible probes "temporal"
│       ├── probes_spatial.txt       ← compatible probes "spatial"
│       ├── probes_affect.txt        ← compatible probes "affect"
│       └── probes_data.txt          ← compatible probes "data"
├── logs/
└── checkpoints/
```

---

## 2. Frozen Configuration File

```yaml
# configs/run_v1.yaml

run_id_prefix: "morphorepr_v1"
description: "Full frozen run MorphoRepr v0.28 — 500 features"

# Reproducibility
git_commit: "FILL_BEFORE_LAUNCH"    # verified against the HEAD Git real to initialization
allow_unpinned_commit: false        # frozen run: the commit MUST be pinned (cf. orchestrator)
lexicon_version: "v1.0"
corpus_frozen: true

# Sampling policy
# temperature is NOT sent to the API by default to avoid the HTTP 400
# on the recent models that reject non-default sampling parameters.
# Documented here for the paper; not transmitted unless use_temperature: true.
sampling:
  use_temperature: false
  temperature: null

# Models (identifiants exacts API Anthropic)
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

# Corpus splits (DISJOINTS). ORDRE SAMPLING : random EN PREMIER, uniformly
# over the whole feature set, then removed from the pool; easy/hard are then sampled from the remainder.
# Thus the random split remains representative (et non a "middle set").
splits:
  sampling_order: ["random", "easy", "hard"]   # random sampled AVANT easy/hard
  random: {n: 200, filter: "uniform"}           # uniforme on TOUT the corpus, en premier
  easy:   {n: 200, min_interp_score: 0.7}       # in the pool restant
  hard:   {n: 100, max_interp_score: 0.5}       # in the pool restant
primary_split: "random"              # all go/no-go thresholds evaluated here

# Clustering (Phase 2) — seeds fixed for the reproducibility of lexicon induction of the lexicon
clustering:
  k: 20
  kmeans_random_state: 42
  umap_random_state: 42

# Steering SAE
steering:
  # La Phase 4 (steering) is a CONTRAT not implemented (Section 7). Disabled by default
  # for permettre a dev run "plumbing hors steering" without crash ; passer to true UNIQUEMENT
  # once steer_feature() actually implemented (and assert_steering_ready passing).
  run_in_pipeline: false
  # Magnitude PRIMAIRE normalized by feature : multiple of the 99e percentile (activation_p99).
  # The absolute historical +5 magnitude (Anthropic, 2024) is kept as a SECONDARY/historical condition.
  magnitude_mode: "p99_relative"     # "p99_relative" (primary) | "absolute" (secondary)
  primary_magnitude_rel: 1.0         # 1.0 × activation_p99 of the feature (TARGET magnitude)
  dose_response_rel: [0.0, 0.5, 1.0, 2.0]   # courbe dose-response (multiples de p99)
  legacy_absolute_magnitude: 5       # condition historical secondary
  # Intervention space : adding to the residual a multiple of the decoder DOES NOT GUARANTEE
  # a hausse of activation latente of the same facteur. On reports therefore the DELTA OBTENU
  # (achieved_delta), not only the target magnitude, and two modes are supported :
  intervention_space: "residual_add_decoder"  # "residual_add_decoder" | "sae_latent_clamp"
  n_probe_sentences: 50              # PRIMARY metric (n_probe_sentences_pilot en dev/pilot)
  n_probe_sentences_pilot: 20        # used if run_mode ∈ {dev, pilot} (cf. run_mode global)
  n_domain_probes_per_category: 20   # compatible probes by category de domain
  # PRIMAIRE deterministic : 1 generation + greedy decoding (temperature=0). Pour amortir the
  # stochasticity, use stochastic_decoding (analyse SECONDAIRE) rather than multiplying
  # greedy generations (which would be identical).
  generations_per_probe: 1
  decoding:
    temperature: 0.0                 # greedy deterministic ; reported in the paper
    max_new_tokens: 64
    archive_generation_params: true  # parameters exacts archived with the outputs
  # Controlled volume (Section 6) : domain probes are a SECONDARY analysis by
  # default (broken down by category), NOT in the primary score.
  primary_probe_family: "neutral"
  use_domain_probes_in_primary: false
  domain_probes_as_secondary: true
  # Two families de probes (pre-registered ; compatible probes MUST NOT give the answer)
  probe_families: ["neutral", "domain_compatible"]
  domain_probe_categories: ["code", "social", "temporal", "spatial", "affect", "data"]
  n_subsample_for_curve: 50          # seeded subsample for the dose-response
  layer_mode: "per_feature"          # cible the layer propre of the feature (column `layer`)
  token_position: "all"              # "all"|"last"|"content_only"
  # OOD : criterion MIXTE pre-registered (robust to low p99 / distributions asymmetric).
  # OOD if activation_after > max(p99·tau, mean + k·std, epsilon)  OU
  #        |activation_after - activation_before| > delta_max · p99
  ood_tau: 3.0
  ood_k: 4.0
  ood_epsilon: 1.0e-3
  ood_delta_max: 5.0
  exclude_ood_from_primary: true     # instances ood_flag=1 exclues de the metric primary

# Stochastic decoding — analyse SECONDAIRE only (amortir the stochasticity).
# Le PRIMAIRE remains greedy deterministic (steering.decoding.temperature=0, 1 generation).
stochastic_decoding:
  enabled: false
  temperature: 0.7
  generations_per_probe: 3

# Execution mode : ajuste the volume of the probes (dev/pilot → n_probe_sentences_pilot).
run_mode: "full"                     # "dev" | "pilot" | "full"

# Causal scoring (Phase 4) — deterministic primary metric. Disabled by default as long as
# causal_scorer._load_pairs() (reading predictions/observations) is not implemented ; handles
# p4_predict, p4_score ET p4_qualitative (without steering, these phases have no material).
causal_scoring:
  run_in_pipeline: false

# Validation model — proxy open-weight BY DEFAULT (Rule 5).
# Mettre enabled=false only if access direct to the activations of a model
# of a production model is obtained (then provide the access paths in agents/steerer.py).
proxy_model:
  enabled: true
  name: "EleutherAI/pythia-6.9b"
  sae_release: "pythia-6.9b-res-jb"

# ANNOTATION baselines (compared on the shared feature set — Rule 7)
baselines:
  - nl_labels
  - semantic_regex        # implementation OFFICIELLE de Boggust and al. (apple/ml-semantic-regex)
  - keyword_tags
  - morphorepr_shuffled

# INTERVENTION controls (Phase 4) — beyond of the shuffled annotation control
intervention_controls:
  # Disabled by default : the phase p4_controls is a CONTRAT not implemented (Section 7).
  # Passer to true UNIQUEMENT once run_intervention_controls() actually implemented.
  run_in_pipeline: false
  random_feature_same_layer: true    # feature SAE random de same layer
  random_direction_same_norm: true   # direction random de same norme
  matched_activation_freq: true      # feature with comparable activation frequency
  negative_steering: true            # -magnitude when semantically relevant
  prompt_only: true                  # label in the prompt, without steering
  diffmean_reft: true                # baselines supervised DiffMean / ReFT (cf. AxBench)

# Shuffled control
shuffle_control:
  n_repeats: 10
  within_split: true
  max_term_diff: 1
  preserve_coeffhereents: true
  # Most shuffles are scored by classifiers (not by the LLM judge) to bound the cost ;
  # but a FRACTION passe by the SAME path predictor+juge that the traitement, afin de
  # calibrate comparability (otherwise the "null" is not comparable to the metric primary).
  # The primary metric is DETERMINISTIC (predictor + classifiers, Rule 8) ; the control
  # shuffled control is scored by THE SAME deterministic path (scored_by='deterministic'). A FRACTION
  # is also passed to the qualitative LLM judge (scored_by='llm_qualitative') for audit only.
  use_llm_judge: false
  llm_qualitative_audit_fraction: 0.2
  # Generated and evaluated on evaluation_split UNIQUEMENT ; repetitions aggregated before CI
  evaluation_split: "random"

# Budget
budget:
  max_cost_usd: 150.0                # update after estimate pilot run
  alert_at_usd: 75.0
  abort_on_exceed: true
  estimate_before_submit: true       # estimer the cost of a batch AVANT submission (Section 5.2)

# Go/no-go thresholds (random split only)
thresholds:
  coverage_easy_min: 0.65
  coverage_random_min: 0.45
  coverage_hard_min: 0.20
  fidelity_auc_min: 0.60
  causal_validity_floor: 0.50        # macro-F1 floor global. Main criteria :
                                     #  - vs NL : SUPERIORITY (CI of the paired difference excluding 0)
                                     #  - vs Semantic Regexes : NON-INFERIORITY (lower bound > -nim_delta)
  nim_delta: 0.05                    # non-inferiority margin pre-registered (macro-F1)
  root_jaccard_min: 0.60
  human_audit_jaccard_min: 0.60
  free_root_rate_max: 5.0

# Statistical methodology
stats:
  causal_score: "macro_f1_global_pairs"   # macro-F1 GLOBAL on all the couples (feature, prop. robust)
                                          # — NOT by feature and then averaged (unstable, too few de classes/feature)
  per_feature_macro_f1: "secondary"       # the score by feature remains reported en metric secondary
  comparison: "paired"                    # paired difference (same features)
  bootstrap_resamples: 10000
  bootstrap_cluster_unit: "feature"       # resampling CLUSTERED by feature
  stratify_by_split: true
  superiority_vs: ["nl_labels"]           # targets evaluated en superiority
  non_inferiority_vs: ["semantic_regex"]  # targets evaluated en non-inferiority (marge nim_delta)
  end_to_end_utility: true                # report coverage × score causal (+ integrated score)
  uncovered_policy: "abstention_or_zero"  # pre-registered rule for end-to-end utility
  multiple_comparison_primary: "holm"            # Holm-Bonferroni (comparisons principales)
  multiple_comparison_exploratory: "benjamini_hochberg"  # FDR (analyses exploratoires)
  prediction_failure_policy: "zero_for_property"  # prediction failure => zero score for the property

# Batch API (Anthropic) — the plupart of the batchs finissent < 1h, accessibles to the fin
# or after 24h ; ils expire to 24h. 2h was trop court (failure artifhereel possible).
batch:
  poll_interval_seconds: 60
  max_wait_seconds: 86400

# Reproducibility seed (selection of the sous-sample, control shuffled, clustering)
seed: 42
```

---

## 3. Complete SQLite Schema (v6.4.1)

```sql
-- db/schema.sql  —  Version 6.4.1, never modify after the full run

PRAGMA log_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────────
-- Run traceability
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    git_commit      TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    prompt_hashes   TEXT NOT NULL,    -- JSON {agent: sha256_full}
    lexicon_version TEXT NOT NULL,
    lexicon_hash    TEXT NOT NULL,    -- SHA256 de l'export JSON canonique sorted
    -- corpus_hash covers only the features table (input data),
    -- NOT results added during the run. La DB grows legitimately.
    corpus_hash     TEXT,             -- SHA256 de l'export CSV canonique sorted ; NULL as long as
                                      -- non frozen (frozen par p1_freeze_corpus after p1_load/p1_rank)
    models_json     TEXT NOT NULL,
    use_temperature INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,             -- NULL si use_temperature=0
    seed            INTEGER,
    proxy_model     TEXT,             -- NULL si model main used
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT DEFAULT 'running',
    last_phase      TEXT,
    total_cost_usd  REAL DEFAULT 0.0
);

-- ─────────────────────────────────────────────
-- Batch tracking (resume after crash)
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

-- custom_id → feature_uid mapping PERSISTED with the batch (crash-safe resume).
-- On resume, the batch may contain custom_id values for already persisted features (therefore
-- absent from load_features_not_processed); the map reconstructed in memory would then be
-- incomplete. This table guarantees that feature_uid can always be retrieved for each custom_id.
CREATE TABLE IF NOT EXISTS batch_items (
    batch_id        TEXT NOT NULL REFERENCES batches(batch_id),
    custom_id       TEXT NOT NULL,
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),
    feature_index   INTEGER NOT NULL,
    PRIMARY KEY(batch_id, custom_id)
);

-- ─────────────────────────────────────────────
-- Versioned prompts
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id   TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    version     TEXT NOT NULL,
    content     TEXT NOT NULL,
    sha256      TEXT NOT NULL,        -- SHA256 full, 64 characters hex
    created_at  TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Feature corpus
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS features (
    -- ROBUST identity: a feature_index alone is ambiguous (same index possible across
    -- plusieurs layers / releases SAE / models). feature_uid is the canonical identity :
    --   feature_uid = '{model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}'
    feature_uid     TEXT PRIMARY KEY,
    model_name      TEXT NOT NULL,
    sae_release     TEXT NOT NULL,
    layer_index     INTEGER NOT NULL,   -- numeric layer (pour construire l'id SAE)
    hook_name       TEXT NOT NULL,      -- ex. 'hook_resid_post'
    feature_index   INTEGER NOT NULL,   -- local index in the SAE; informative, never a logical key alone
    split           TEXT NOT NULL,
    nl_description  TEXT NOT NULL,
    top_examples    TEXT NOT NULL,    -- JSON array serialized
    score_interp    REAL,
    activation_freq REAL,
    -- Activation statistics from Neuronpedia (used for OOD detection)
    -- These columns replace W_dec norm, which is a different quantity
    activation_p99  REAL,
    activation_mean REAL,
    activation_std  REAL,
    layer           TEXT,             -- display label d'affichage (peut differ de layer_index)
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL,
    -- Un same (model, release, layer, hook, index) not peut appear deux fois.
    UNIQUE(model_name, sae_release, layer_index, hook_name, feature_index)
);

-- ─────────────────────────────────────────────
-- Raw agent outputs (immutable)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITY LOGIQUE (Rule 10)
    feature_index   INTEGER NOT NULL,                       -- informative (index in the SAE)
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
    coeffhereent_type TEXT DEFAULT 'confidence',
    created_at      TEXT NOT NULL,
    -- Uniqueness sur feature_uid (PAS feature_index, ambiguous across layers/SAEs — Rule 10).
    -- Combined with divergence checking in save_agent_output(), this makes persistence idempotent.
    UNIQUE(run_id, feature_uid, agent_name, run_number)
);

-- ─────────────────────────────────────────────
-- Computed metrics
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
    baseline        TEXT,             -- NULL = MorphoRepr ; otherwise baseline name
    computed_at     TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Baselines
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS baselines (
    baseline_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_uid     TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITY LOGIQUE
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
-- Shuffled control
-- shuffle_id is deterministic : {run_id}_{sha1(feature_uid)[:12]}_{shuffle_number}
-- (based on feature_uid, NOT feature_index, to avoid inter-layer collisions)
-- La constraint UNIQUE(run_id, feature_uid, shuffle_number) prevents the doublons
-- Scored by the same deterministic path as the primary metric ; fraction 'llm_qualitative' for audit
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id          TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    feature_uid         TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITY LOGIQUE
    feature_index       INTEGER NOT NULL,                                -- informatif
    shuffle_number      INTEGER NOT NULL,
    source_feature_uid  TEXT NOT NULL REFERENCES features(feature_uid),  -- source (uid)
    source_feature_index INTEGER,                                        -- informatif
    annotation          TEXT NOT NULL,
    causal_score        REAL,
    causal_outcome      TEXT,
    -- 'deterministic' (predictor+classifiers path, like the primary metric — default)
    -- | 'llm_qualitative' (fraction d'audit, Section 8 / shuffle_control)
    scored_by           TEXT DEFAULT 'deterministic',
    created_at          TEXT NOT NULL,
    UNIQUE(run_id, feature_uid, shuffle_number)
);

-- ─────────────────────────────────────────────
-- Steering results — text and activations before/after
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS steering_results (
    result_id           TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    feature_uid         TEXT NOT NULL REFERENCES features(feature_uid),  -- IDENTITY LOGIQUE
    feature_index       INTEGER NOT NULL,                                -- informatif
    intervention_space  TEXT,            -- 'residual_add_decoder' | 'sae_latent_clamp'
    magnitude           REAL NOT NULL,   -- magnitude absolue TARGETED effectivement applied (informatif)
    magnitude_rel       REAL,            -- multiple de p99 targeted (NULL en mode "absolute") (informatif)
    -- magnitude_key: stable TEXT key for magnitude, valid in BOTH modes :
    --   'rel:{rel}' en mode p99_relative, 'abs:{legacy}' en mode absolute.
    -- Avoids a nullable float in the uniqueness constraint (idempotence aussi en absolu).
    magnitude_key       TEXT NOT NULL,
    probe_id            INTEGER NOT NULL,
    probe_family        TEXT,            -- 'neutral' | 'domain_compatible'
    probe_category      TEXT,            -- 'code'|'social'|'temporal'|… (NULL si 'neutral')
    generation_index    INTEGER DEFAULT 0,  -- index de generation (generations multiples/probe)
    text_before         TEXT NOT NULL,
    text_after          TEXT,
    layer               TEXT,
    token_position      TEXT,
    activation_before   REAL,            -- activation latente cible AVANT
    activation_after    REAL,            -- activation latente cible AFTER
    achieved_delta      REAL,            -- delta OBTENU (after - before) ; peut ≠ magnitude targeted
    -- ood_flag : criterion MIXTE (Section 7) based on activation_p99/mean/std from the features table,
    -- NOT on W_dec norm.
    ood_flag            INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL,
    -- Idempotence en resume (LES DEUX modes via magnitude_key ; probe_category avoids the
    -- collisions between categories that reset probe_id). Steering stochasticity
    -- is compatible with "frozen and auditable" archiving : on resume, we keep the
    -- 1st output and any divergence is logged (table steering_duplicate_attempts).
    UNIQUE(run_id, feature_uid, intervention_space, magnitude_key,
           probe_family, probe_category, probe_id, generation_index)
);

-- Steering divergence log : we keep the 1st output (UNIQUE above), but
-- any DIFFERENT rewrite attempt for the same cell is tracked here (audit), instead
-- to be ignored silencieusement.
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
    -- Attempted DIVERGENT output (the 1st is kept in steering_results) : we keep enough information to
    -- diagnostiquer, not only the text.
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
    cumulativeative_cost REAL,
    timestamp       TEXT NOT NULL,
    -- Cost idempotence per batch : on resume, a cost already logged for this
    -- (run, batch, phase, agent) is NOT counted again (log_api_cost en INSERT OR IGNORE).
    -- NB : SQLite autorise plusieurs NULL ; non-batch calls (batch_id NULL) are not deduplicated here.
    UNIQUE(run_id, batch_id, phase, agent_name)
);

-- ─────────────────────────────────────────────
-- Lexicon versions
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
-- Calibration of property classifiers (archived for audit/repro)
-- Written par classifiers/calibration/run_calibration.py (Section 6)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS classifier_calibrations (
    calibration_id        TEXT PRIMARY KEY,
    run_id                TEXT,                 -- run associated (NULL si calibration hors run)
    property              TEXT NOT NULL,
    classifier_name       TEXT NOT NULL,
    classifier_version    TEXT,
    dataset_hash          TEXT,                 -- hash du dataset de calibration
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
-- User-study results (outside the pipeline; stored here for traceability)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_study_results (
    result_id           TEXT PRIMARY KEY,
    partherepant_id      TEXT NOT NULL,
    condition           TEXT NOT NULL,    -- 'morphorepr'|'semantic_regex'|'nl'
    feature_uid         TEXT REFERENCES features(feature_uid),  -- logical identity (multi-layers)
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

## 4. Single MorphoRepr Parser

```python
# utils/morphorepr_parser.py
"""
MorphoRepr parser.
Single source of truth for ALL morphemic metrics.

Algorithm based on SEGMENTATION on '-' (fixes v4 bugs : non-detection
of infixes, and failure on mal-o / ne-a). For each word :
  1. Remove the coeffhereent (before '·'), done in parse_expression().
  2. Split the word on '-' en segments.
  3. The last segment is the suffix (must be a known suffix token).
  4. Read leading prefixes, WITHOUT ever consuming the last segment
     disponible (which becomes the root). => mal-o gives root 'mal' ;
     mal-emo-a gives prefix 'mal' + root 'emo'.
  5. The first non-prefix segment is the root ; the segments restants
     are the infixes.

Note : a strictly positional substring parser (v4) failed car,
after removing the suffix '-o', the body 'soc-ant' no longer contains the pattern
'-ant-' (the final hyphen has gone with the suffix). Segmentation avoids this.
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

# RESERVED_TOKENS : may NOT be used as newly induced free roots.
# Note : "mal" and "ne" apparaissent in PREDEFINED_ROOTS ET RESERVED_TOKENS.
# This is intentional :
#   - "mal" and "ne" are valid as PREDEFINED roots (ex. "mal-o", "ne-a")
#   - Ils may NOT be re-registered as new FREE roots by the pipeline
RESERVED_TOKENS = frozenset({
    "mal", "ne", "pli", "plej", "duon",                 # tokens de prefix
    "ad", "int", "it", "ist", "ant", "at", "ig", "iĝ",  # tokens of infix (iĝ inclus)
    "o", "a", "e", "i", "as", "is", "os", "us", "u"      # tokens de suffix
})

# Token sets WITHOUT hyphens, used by segmentation (parse_word).
PREFIX_TOKENS      = frozenset(p.strip("-") for p in PREFIXES)
INFIX_TOKENS       = frozenset(ix.strip("-") for ix in INFIXES)
TENSE_SUFFIX_TOK   = frozenset(s.strip("-") for s in TENSE_SUFFIXES)
SYNT_SUFFIX_TOK    = frozenset(s.strip("-") for s in SYNTACTIC_SUFFIXES)
SUFFIX_TOKENS      = TENSE_SUFFIX_TOK | SYNT_SUFFIX_TOK


@dataclass
class ParsedTerm:
    coeffhereent: float
    coeffhereent_type: str = "confidence"   # "confidence" | "activation"
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
    def coeffhereents(self) -> list[float]:
        return [t.coeffhereent for t in self.terms]


def parse_word(word: str, known_free_roots: Optional[set] = None) -> ParsedTerm:
    """Parse a single MorphoRepr word by SEGMENTATION on '-'.

    `known_free_roots` (optionnel) : registered free roots. Une root non
    predefined et non registered remains SYNTAXIQUEMENT valid (rule 6) ; parse_word
    does not invalidate it (eligibility for registration is checked separately by
    can_register_new_free_root)."""
    known_free_roots = known_free_roots or set()
    term = ParsedTerm(coeffhereent=0.0, coeffhereent_type="confidence", raw_word=word)

    segs = [s for s in word.strip().split("-") if s]
    if not segs:
        term.parse_error = f"Empty word : {word}"
        return term

    # Step 3 : suffix = last segment
    if segs[-1] not in SUFFIX_TOKENS:
        term.parse_error = f"No recognized suffix : {word}"
        return term
    term.suffix = "-" + segs[-1]
    term.suffix_type = "tense" if segs[-1] in TENSE_SUFFIX_TOK else "syntactic"

    body = segs[:-1]
    if not body:
        term.parse_error = f"No root extracted : {word}"
        return term

    # Step 4 : leading prefixes, WITHOUT ever consuming the last segment (la root).
    # => mal-o : root 'mal' ; mal-emo-a : prefix 'mal' + root 'emo' ; mal-ne-o :
    #    prefix 'mal' + root 'ne'.
    i = 0
    while i < len(body) - 1 and body[i] in PREFIX_TOKENS:
        term.prefixes.append(body[i])
        i += 1

    # Step 5a : root = premier segment non-prefix restant
    root = body[i]
    i += 1
    if root in PREDEFINED_ROOTS:
        pass                                   # predefined root (includes mal, ne)
    elif root in RESERVED_TOKENS:
        term.parse_error = f"Reserved token '{root}' used as root : {word}"
        return term
    elif root in known_free_roots:
        pass                                   # registered free root
    elif re.match(r'^[a-z]{2,5}$', root):
        pass                                   # well-formed free root (registration checked elsewhere)
    else:
        term.parse_error = f"Malformed root '{root}' : {word}"
        return term
    term.root = root

    # Step 5b : remaining segments = infixes
    for seg in body[i:]:
        if seg not in INFIX_TOKENS:
            term.parse_error = f"Unexpected segment '{seg}' (unknown/misplaced infix) : {word}"
            return term
        term.infixes.append(seg)

    return term


def parse_expression(expr: str,
                     coeffhereent_type: str = "confidence") -> ParsedExpression:
    """Parse a full MorphoRepr expression."""
    result = ParsedExpression(raw=expr)
    if not expr or not expr.strip():
        result.parse_error = "Empty expression"
        return result

    term_strings = [t.strip() for t in expr.split("+") if t.strip()]
    if not term_strings:
        result.parse_error = "No term found"
        return result

    for ts in term_strings:
        if "·" not in ts:
            result.parse_error = f"Term without separator '·' : {ts}"
            return result
        coeff_str, word = ts.split("·", 1)
        try:
            coeff = float(coeff_str.strip())
        except ValueError:
            result.parse_error = f"Invalid coeffhereent : {coeff_str}"
            return result
        if not (0.01 <= coeff <= 1.00):
            result.parse_error = f"Coeffhereent out of range [0.01,1.00] : {coeff}"
            return result
        parsed_term = parse_word(word.strip())
        parsed_term.coeffhereent = coeff
        parsed_term.coeffhereent_type = coeffhereent_type
        result.terms.append(parsed_term)

    # Check decreasing coeffhereent order
    coeffs = [t.coeffhereent for t in result.terms]
    if coeffs != sorted(coeffs, reverse=True):
        result.parse_error = "Terms not ordered by decreasing coeffhereent"
        return result

    return result


def is_valid_root(root: str, known_free_roots: Optional[set] = None) -> bool:
    """True if `root` is a currently VALID root : predefined root, or root
    libre bien formed ([a-z]{2,5}) non reserved (registered ou non). Used for parsing."""
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
    """Validate the eligibility of a candidate root to be REGISTERED as NEW
    root libre. Returns None if eligible, otherwise an error message.

    Distinct from is_valid_root : 'mal' et 'ne' are VALID roots (predefined)
    but may NOT be re-registered comme nouvelles roots libres ; de same
    an already registered root cannot be registered twice."""
    known_free_roots = known_free_roots or set()
    if root in PREDEFINED_ROOTS:
        return f"'{root}' is already a predefined root (no re-registration)"
    if root in RESERVED_TOKENS:
        return f"'{root}' is a reserved token (prefix/infix/suffix)"
    if root in known_free_roots:
        return f"'{root}' is already registered as a free root"
    if not re.match(r'^[a-z]{2,5}$', root):
        return f"'{root}' does not match [a-z]{{2,5}}"
    return None
```

---

## 5. Main Utilities

### 5.1 db_utils.py

```python
# utils/db_utils.py
"""
Only access point to features.db.
Any direct DB operation outside this module is forbidden.
DB_PATH configurable via MORPHOREPR_DB_PATH for test isolation.
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
    # Re-read the environment on EVERY call : guarantees test isolation same if ce module
    # a been imported before that the fixture not sets MORPHOREPR_DB_PATH (otherwise DB_PATH,
    # frozen at import time, pointerait on the DB de production).
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
    """Return features without output for this agent/run_number. Idempotent.
    Logical key : feature_uid (Rule 10), not feature_index."""
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
                      coeffhereent_type: str = "confidence",
                      feature_uid: Optional[str] = None):
    """Idempotent persistence BUT NON-SILENT in case of divergence.
    Logical key : feature_uid (Rule 10), REQUIRED.

    - If no output exists for (run_id, feature_uid, agent_name, run_number) → INSERT.
    - If an IDENTICAL output exists (same output_json, raw_output, status) → ignore (resume).
    - If a DIFFERENT output exists → RuntimeError (do not mask a divergence).
    Avoids the trap du INSERT OR IGNORE which silently swallows a different output."""
    if feature_uid is None:
        raise ValueError("save_agent_output : feature_uid is required (logical identity, Rule 10).")
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
                return                       # resume idempotent
            raise RuntimeError(
                f"Output divergence for (run={run_id}, feature_uid={feature_uid}, "
                f"agent={agent_name}, run_number={run_number}) : a DIFFERENT output "
                f"is already persisted. Run blocked (do not silently overwrite)."
            )
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, feature_uid, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coeffhereent_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, feature_uid, feature_index, agent_name, run_number,
            new_json, raw_output, status, error_msg,
            tokens_input, tokens_output, batch_id, cost_usd,
            coeffhereent_type,
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
    """Register the batch AND its mapping custom_id → feature_uid in A SINGLE transaction
    (crash-safe : no window where the batch exists without its map). items : [{custom_id,
    feature_uid, feature_index}, …]. Idempotent on items (INSERT OR IGNORE)."""
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
    """Persist the mapping custom_id → feature_uid of a batch (table batch_items),
    for crash-safe resume. items : [{custom_id, feature_uid, feature_index}, …].
    Idempotent (INSERT OR IGNORE) : un re-submission/re-poll not duplique pas."""
    with get_conn() as conn:
        for it in items:
            conn.execute("""
                INSERT OR IGNORE INTO batch_items (batch_id, custom_id, feature_uid, feature_index)
                VALUES (?, ?, ?, ?)
            """, (batch_id, it["custom_id"], it["feature_uid"], it["feature_index"]))


def load_batch_item_map(batch_id: str) -> dict[str, dict]:
    """Reload the map custom_id → {feature_uid, feature_index} persisted for ce batch."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT custom_id, feature_uid, feature_index FROM batch_items WHERE batch_id=?
        """, (batch_id,)).fetchall()
    return {r["custom_id"]: {"feature_uid": r["feature_uid"],
                             "feature_index": r["feature_index"]} for r in rows}


def get_unconsumed_batch(run_id: str, phase: str,
                         agent_name: str, run_number: int) -> Optional[str]:
    """Return the batch_id of a submitted but unconsumed batch, if any."""
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
    """Log the cost and update the cumulativeative total. IDEMPOTENT PER BATCH : thanks to the constraint
    UNIQUE(run_id, batch_id, phase, agent_name) on api_usage, a cost already logged for this
    (run, batch, phase, agent) is NOT counted again on resume (anti double-counting of the budget).
    NB: for non-batch calls (batch_id NULL), SQLite does not apply uniqueness — the
    deduplication applies only to batches (resume-after-crash case)."""
    with get_conn() as conn:
        # Non-silent : if a cost is ALREADY logged for ce batch with a montant
        # different, this is a divergence to report (et non to ignore).
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
                    f"Cost divergence for batch {batch_id} (run={run_id}, {phase}/{agent_name}) : "
                    f"already logged {prev['cost_usd']:.4f}$ "
                    f"({prev['tokens_input']}/{prev['tokens_output']} tk), "
                    f"recomputed {cost:.4f}$ ({tokens_in}/{tokens_out} tk). Run blocked."
                )
        cur = conn.execute("""
            INSERT OR IGNORE INTO api_usage (
                call_id, run_id, phase, agent_name, model,
                tokens_input, tokens_output, batch_id, cost_usd,
                cumulativeative_cost, timestamp
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
            # Cost already logged for ce batch (resume, montant identique) → not recompter.
            logger.info(f"Cost already logged for batch {batch_id} — not counted again.")
            return current
        cumulativeative = current + cost
        conn.execute(
            "UPDATE runs SET total_cost_usd=? WHERE run_id=?",
            (cumulativeative, run_id)
        )
        conn.execute(
            "UPDATE api_usage SET cumulativeative_cost=? "
            "WHERE run_id=? AND phase=? AND agent_name=? "
            "AND (batch_id = ? OR (batch_id IS NULL AND ? IS NULL)) "
            "AND cumulativeative_cost IS NULL",
            (cumulativeative, run_id, phase, agent_name, batch_id, batch_id)
        )
    return cumulativeative


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
Batch API wrapper with resume after crash.
The config is always passed explicitly — no call load_config() here.
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

# Lazy initialization : do not instantiate the client (nor require ANTHROPIC_API_KEY) at import time,
# so that unit tests without a key can import this module.
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
    """ROUGH estimate of a batch cost BEFORE submission (heuristique chars/4 for
    l'input, max_tokens for output). Used for the pre-submission budget guardrail, pas
    for real accounting (done after reception via compute_cost on actual usage)."""
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
    """custom_id Batch API based on feature_uid (PAS feature_index seul, ambigu between
    layers/SAEs — Rule 10). Readable format : 'feature_{index}_{sha1(uid)[:12]}'.
    Le hash garantit uniqueness ; the index is only there for debugging."""
    h = hashlib.sha1(f["feature_uid"].encode()).hexdigest()[:12]
    return f"feature_{f['feature_index']}_{h}"


def build_custom_id_map(features: list[dict]) -> dict[str, str]:
    """Mapping table custom_id → feature_uid, to attach batch outputs
    to leur logical identity au retour (save_agent_output requires feature_uid)."""
    return {feature_custom_id(f): f["feature_uid"] for f in features}


def build_batch_item_rows(features: list[dict]) -> list[dict]:
    """Rows for batch_items (crash-safe persistence of the mapping)."""
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
    Config passed explicitly. Temperature added only if use_temperature=True.
    Avoids HTTP 400 on models that reject non-default sampling parameters.
    custom_id values are based on feature_uid (cf. feature_custom_id) : deux features de
    different layers but the same feature_index can no longer collide in a batch.
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
    Submit a batch (or retrieve an existing unconsumed batch) and return the results.
    Config passed explicitly partout. Each result is enriched de `feature_uid` to partir
    from the PERSISTED map (batch_items), robust on resume.

    requires_feature_mapping (default True) : for a FEATURE-LEVEL batch, batch_items is
    MANDATORY (save_agent_output requires feature_uid). Raise ValueError if missing, and on
    resume we BLOCK if the persisted map is empty (instead of a simple warning).

    Anti double-billing (crash-safety) : if `persist_fn` is provided, it is called
    with the results BEFORE logging the cost and marking the batch consumed. Ainsi,
    en case de crash after reception but before persistence, the batch remains 'submitted' ;
    on resume, get_unconsumed_batch retrieves it and we RE-POLL the same batch (no
    nouvelle submission, therefore no double spending) then we re-persist (idempotent).
    Batch + mapping registration is ATOMIC (register_batch_with_items) : not de
    window where the batch exists without its map.
    """
    if requires_feature_mapping and not batch_items:
        raise ValueError(
            "batch_items is required for a feature-level batch "
            "(passer build_batch_item_rows(features)). "
            "Set requires_feature_mapping=False for a non-feature batch."
        )
    # Pre-check BEFORE any submission (therefore before any billing) : the custom_id
    # from requests must match those of batch_items EXACTLY. Sinon, a mauvais
    # mapping (omission, feature/request mismatch) would be detected too late, after billing.
    if requires_feature_mapping:
        request_ids = {r["custom_id"] for r in requests}
        item_ids    = {it["custom_id"] for it in batch_items}
        if request_ids != item_ids:
            missing = request_ids - item_ids     # requests without a mapping entry
            extra   = item_ids - request_ids     # mappings without a corresponding request
            raise ValueError(
                f"batch_items does not match requests "
                f"(custom_id). missing={sorted(missing)}, extra={sorted(extra)}"
            )
    batch_cfg        = config.get("batch", {})
    poll_interval    = poll_interval    or batch_cfg.get("poll_interval_seconds", 60)
    max_wait_seconds = max_wait_seconds or batch_cfg.get("max_wait_seconds", 86400)
    existing = get_unconsumed_batch(run_id, phase, agent_name, run_number)
    if existing:
        logger.info(f"Resuming unconsumed batch {existing}")
        batch_id = existing
    else:
        # Budget guardrail BEFORE submission (avoids submitting a batch which
        # would mechanically exceed the budget, which would otherwise be noticed only afterward).
        if config.get("budget", {}).get("estimate_before_submit"):
            is = estimate_batch_cost(requests, model)
            max_cost = config["budget"]["max_cost_usd"]
            current, _ = check_budget(run_id, max_cost)
            if current + is > max_cost:
                raise RuntimeError(
                    f"Estimated budget exceeded BEFORE submission : "
                    f"cumulative {current:.2f}$ + estimate {est:.2f}$ > {max_cost}$"
                )
            logger.info(f"Pre-submission estimate : {est:.2f}$ (cumulative {current:.2f}$)")
        batch = _get_client().messages.batches.create(requests=requests)
        batch_id = batch.id
        # Enregistrement ATOMIQUE batch + mapping (no window batch-sans-map).
        register_batch_with_items(batch_id, run_id, phase, agent_name,
                                  run_number, len(requests), batch_items or [])
        logger.info(f"Batch submitted : {batch_id} ({len(requests)} requests)")

    elapsed = 0
    while elapsed < max_wait_seconds:
        status_obj = _get_client().messages.batches.retrieve(batch_id)
        if status_obj.processing_status == "ended":
            break
        elif status_obj.processing_status == "errored":
            raise RuntimeError(f"Batch {batch_id} server error")
        counts = status_obj.request_counts
        logger.info(f"Batch {batch_id} : {counts.processing} processing, "
                    f"{counts.succeeded} succeeded, {counts.errored} errors")
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(f"Batch {batch_id} timeout after {max_wait_seconds}s")

    results = []
    total_in, total_out = 0, 0
    for result in _get_client().messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            msg  = result.result.message
            # Concatenate all blocks of type 'text' (defensive : a premier bloc
            # non-textuel — p. ex. reasoning/tool block — does not break parsing).
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

    # Enrich each result with feature_uid from the PERSISTED map (robust to the resume :
    # the batch peut contenir of the custom_id de features already persisted, absentes of a map
    # reconstruite en memory). save_agent_output requires feature_uid.
    id_map = load_batch_item_map(batch_id)
    if requires_feature_mapping and not id_map:
        # Map persisted empty then qu'on attend a mapping feature-level : case of a batch
        # registered by of the code pre-v6.4 or of a crash between register and items (n'arrive more
        # with register_batch_with_items). On BLOQUE rather than de risquer a mauvais rattachement.
        raise RuntimeError(
            f"batch {batch_id} : batch_items mapping empty while feature_uid is required. "
            f"Reprise blocked (impossible de rattacher the outputs to leur feature_uid)."
        )
    for r in results:
        item = id_map.get(r["custom_id"])
        if item is not None:
            r["feature_uid"]   = item["feature_uid"]
            r["feature_index"] = item["feature_index"]
        elif requires_feature_mapping:
            raise RuntimeError(
                f"custom_id {r['custom_id']} absent de batch_items (batch {batch_id}) — "
                f"feature_uid introuvable. Reprise blocked."
            )

    # Persistence BEFORE consumption/billing : guarantees that a crash between reception
    # and persistance leaves the batch recoverable without resubmission or double spending.
    if persist_fn is not None:
        persist_fn(results)

    cost       = compute_cost(model, total_in, total_out, is_batch=True)
    cumulativeative = log_api_cost(run_id, phase, agent_name, model,
                              total_in, total_out, batch_id, cost)
    mark_batch_consumed(batch_id)
    logger.info(f"Batch {batch_id} consumed — cost : {cost:.3f}$ | "
                f"Cumulative : {cumulativeative:.2f}$")

    budget = config.get("budget", {})
    if budget.get("abort_on_exceed") and \
       cumulativeative >= budget.get("max_cost_usd", float("inf")):
        raise RuntimeError(
            f"Budget exceeded : {cumulativeative:.2f}$ >= "
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
            logger.warning(f"{custom_id} : JSON without field 'status'")
            return parsed, "invalid_json"
        if parsed["status"] == "uncovered":
            return parsed, "uncovered"
        return parsed, "ok"
    except json.JSONDecodeError:
        logger.warning(f"{custom_id} : non-JSON output : {raw[:120]}")
        return None, "invalid_json"
```

### 5.3 prompt_utils.py

```python
# utils/prompt_utils.py
"""
Loading, hashing, and registering prompts.
SHA256 full (64 characters hex) — no truncation.
Canonical hash for the corpus (sorted CSV export) and the lexicon (sorted JSON keys).
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
    """SHA256 full — 64 characters hex, without troncature."""
    return hashlib.sha256(content.encode()).hexdigest()


def hash_lexicon_canonical(lexicon_path: str) -> str:
    """Canonical hash of the lexicon : sorted JSON keys, independent of encoding."""
    data      = json.loads(Path(lexicon_path).read_text())
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_corpus_canonical(db_path: str) -> str:
    """
    Canonical corpus hash: sorted CSV export of the features table only.
    Covers only input data — NOT results added during the run.
    The database legitimately grows during execution ; seules the rows
    from the features table are part of the frozen corpus definition.
    """
    conn = sqlite3.connect(db_path)
    cur  = conn.execute(
        "SELECT * FROM features ORDER BY feature_uid"
    )
    col_names = [d[0] for d in cur.description]   # header: detects a schema/order change
    rows = cur.fetchall()
    conn.close()
    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(col_names)                    # header line included in the hash
    for row in rows:
        writer.writerow(row)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def register_prompts(prompt_paths: dict) -> dict:
    """Register all prompts in DB. Return {agent_name: sha256_full}."""
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
    """Raise RuntimeError if a prompt changed since registration."""
    for agent_name, path in prompt_paths.items():
        current  = hash_prompt(load_prompt(path))
        expected = registered_hashes.get(agent_name, "")
        if current != expected:
            raise RuntimeError(
                f"Modified prompt : {agent_name}\n"
                f"  expected : {expected[:16]}...\n"
                f"  current  : {current[:16]}..."
            )
```

---

## 6. Output Property Classifiers

### 6.1 Negation (robust)

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
# Morphological prefixes: WEAK and noisy signal (display, mission, discussion, union…).
# v6 : they NO LONGER contribute to the ROBUST negation score. They are measured separately
# as "weak_morphological" (outside the primary metric), for analysis only.
# (v4 incluait aussi "a"/"in"/"im"/"il"/"ir" — massive false positives, removed en v5.)

def count_negation_signals(text: str) -> float:
    """ROBUST negation signal : syntactic dependency 'neg' + lexicon explherete UNIQUEMENT.
    Morphological prefixes are excluded (voir count_weak_morph_neg)."""
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
    """WEAK morphological signal (prefixes) — REPORTED OUTSIDE the robust metric."""
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
    # Weak morphological signal : reported separately, does NOT affect the robust direction.
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

### 6.2 Emotional valence (semi-robust)

```python
# classifiers/valence.py
"""
Uses cardiffnlp/twitter-roberta-base-sentiment-latest rather than SST-2.
SST-2 is trained on movie reviews and performs poorly on text
technical or narrative text. The Cardiff model is more robust across varied domains.
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
            top_k=None          # returns the full label distribution (not only the top label)
        )
    return _pipe

def _neg_score(text: str) -> float:
    # With top_k=None, the pipeline returns the list of all labels with their scores.
    # Read DIRECTLY the score of the label 'negative' (instead of approximating 1 - top_score,
    # which overestimated negativity when the top label was 'neutral').
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
        "reliability_note": ("Semi-robust : interpret with caution sur du texte "
                             "technical, ironic ou to forte density de code.")
    }
```

### 6.3 Classifier Calibration

```python
# classifiers/calibration/run_calibration.py
"""
Must pass before the pilot run. All robust properties require calibration.
v6.1 : reports n, class balance, confusion matrix, accuracy ET macro-F1, et
precision/recall by direction ; BLOCKS on macro-F1 (not only accuracy) ; archive
each report (with dataset_hash) in the classifier_calibrations table.
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
        # include in the average only classes present in ground truth
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
          f"(n={n}, balance={class_balance})")
    Path("calibration/reports").mkdir(parents=True, exist_ok=True)
    Path(f"calibration/reports/{property_name}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    if persist_db:
        _persist_calibration(report)
    return report


def _persist_calibration(report: dict, run_id: str | None = None):
    """Archive a rapport de calibration in the table classifier_calibrations."""
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
            "Calibration failed (macro-F1 ou accuracy insuffisant) — "
            "fix the classifiers before the pilot run."
        )
    print("\nAll classifiers calibrated (macro-F1 OK) — ready for the pilot run.")
```

---

## 7. Steering Agent — Open-Weight Proxy Implementation and Remaining Contracts

```python
# agents/steerer.py
"""
Phase 4 — Steering d'activation SAE (CONTRAT IMPLEMENTATION v6).

Cette section is un CONTRAT : steer_feature() is implemented for the open-weight proxy path (TransformerLens + SAE Lens, residual_add_decoder). The nnsight / production-model path and the sae_latent_clamp intervention space still raise explicit NotImplementedError. The pilot run remains blocked until assert_steering_ready() passes
(Rule 9).

Intervention specification (v6) :
  - Espace :          'residual_add_decoder' (ajout d'un multiple de W_dec au residual) OU
                      'sae_latent_clamp' (clamp de activation latente). ATTENTION : ajouter
                      k×W_dec to the residual does NOT guarantee a k×p99 increase in activation
                      latente measured (decoder norm, encodage, interferences, nonlinearities).
                      Therefore, the ACHIEVED delta is REPORTED (achieved_delta), not only the target magnitude.
  - Layer :          the FEATURE'S OWN LAYER (layer_index) ; SAE loaded/cached by layer (Rule 6)
  - Position token :  configurable ("all" | "last" | "content_only")
  - Amplitude :       PRIMAIRE = primary_magnitude_rel × activation_p99 (mode "p99_relative") ;
                      +5 absolu en condition SECONDAIRE (mode "absolute")
  - Sondes :          n_probe_sentences (50 primary / 20 pilot), generations_per_probe generations,
                      deux familys : 'neutral' et 'domain_compatible'
  - Detection OOD :   criterion MIXTE (Rule/Section 7) :
                      OOD si activation_after > max(p99·tau, mean + k·std, epsilon)
                          OU |activation_after - activation_before| > delta_max·p99
                      (robust to low p99 / distributions asymmetric). Stats issues
                      from the features table, NOT from W_dec norm. ood_flag=1 excluded from primary.

Model access paths (implement one of them before the pilot run) :
  A. TransformerLens — for GPT-style open-weight proxy models
  B. nnsight         — si access direct to one model de production disponible
  C. Poids locaux    — si model open-weight compatible SAE disponible

Model de validation (proxy by default, Rule 5) :
  proxy_model.enabled=true by default. Le pipeline entier operates alors sur the SAEs
  of the proxy; Claude 3 Sonnet examples remain illustrative only. This must be
  explicitly declared in the Methods section.
"""
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# SAE cache by layer (the corpus may cover several layers).
_SAE_CACHE: dict = {}

REQUIRED_STEER_FIELDS = (
    "text_before", "text_after", "activation_before", "activation_after",
    "achieved_delta", "ood_flag",
)


def normalize_layer(layer) -> str:
    """Normalise a layer heterogeneous (int, '6', 'blocks.6.hook_resid_post', 'middle'…)
    vers un sae_id 'blocks.{i}.hook_resid_post'. Raises ValueError si non interpretable
    (ex. 'middle' is NOT resolved here : the layer must be numeric at steering time)."""
    if isinstance(layer, str) and layer.startswith("blocks."):
        return layer
    if isinstance(layer, int):
        return f"blocks.{layer}.hook_resid_post"
    if isinstance(layer, str) and layer.isdigit():
        return f"blocks.{int(layer)}.hook_resid_post"
    raise ValueError(
        f"Layer non interpretable comme indice numeric : {layer!r}. "
        f"Provide layer_index (integer) in the features table."
    )


def _get_sae(config: dict, layer):
    """
    Load (and cache) the SAE for a given LAYER — the feature layer.
    `layer` must be numeric (layer_index) or an already formed sae_id.
    Implement one of the three paths before the pilot run.
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
        "_get_sae() not implemented.\n"
        "Pour unlock :\n"
        "  A. Mettre proxy_model.enabled=true et utiliser un SAE public, OU\n"
        "  B. Implement l'access au SAE d'one model de production via sae_lens/nnsight.\n"
        "Validate in a dev run before the pilot run."
    )


def assert_steering_ready(config: dict, n_probe: int = 5):
    """Pre-pilot guard (Rule 9) : verifies that steer_feature() ACTUALLY produces
    all required fields on a mini dev run, using a REAL feature from the DB
    (layer, index, stats real) rather than artificial values. Raises RuntimeError
    otherwise. Call before any pilot/full run involving Phase 4."""
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
            "assert_steering_ready : noe feature 'random' en DB. "
            "Run at least Phases 1–2 before validating Phase 4."
        )
    model = _get_model(config)
    sae   = _get_sae(config, feat["layer_index"])      # layer REAL de the feature
    probes = load_probe_sentences(n_probe)
    stats = {
        "activation_p99":  feat["activation_p99"],
        "activation_mean": feat["activation_mean"],
        "activation_std":  feat["activation_std"],
    }
    results = steer_feature(model, sae, feature_index=feat["feature_index"], magnitude=2.0,
                            probe_sentences=probes, feature_stats=stats, config=config)
    if not results:
        raise RuntimeError("assert_steering_ready : steer_feature n'a produit no result.")
    missing = [f for f in REQUIRED_STEER_FIELDS if any(f not in r for r in results)]
    if missing:
        raise RuntimeError(
            f"assert_steering_ready : fields manquants {missing}. "
            f"Implement steer_feature() (contract v6) before the pilot run."
        )
    if any(r.get("text_after") in (None, r.get("text_before")) for r in results):
        raise RuntimeError("assert_steering_ready : text_after non produit (placeholder non replaced).")


def _get_model(config: dict):
    """
    Load the language model for steering.
    Implement one of the three paths before the pilot run.
    """
    proxy = config.get("proxy_model", {})
    if proxy.get("enabled"):
        import transformer_lens
        model = transformer_lens.HookedTransformer.from_pretrained(proxy["name"])
        return model
    raise NotImplementedError(
        "_get_model() not implemented.\n"
        "Pour unlock :\n"
        "  A. Set proxy_model.enabled=true and implement the TransformerLens path, OR\n"
        "  B. Implement the nnsight path for Claude access, OR\n"
        "  C. Charger one model open-weight local.\n"
        "Validate in a dev run before the pilot run."
    )


def load_probe_sentences(n: int = 20, family: str = "neutral") -> list[str]:
    """
    Charge the phrases-probes depuis data/probes/, un file par family.
      - family='neutral'          → data/probes/probes_neutral.txt
      - family='code'/'social'/…  → data/probes/probes_{family}.txt
    Requirements (neutral) : 10–30 tokens, without strong emotional/technical content, without
    named entities, without negation. domain_compatible families are pre-registered
    by category and must NOT give the answer in advance (Section 7).
    """
    path = Path(f"data/probes/probes_{family}.txt")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} introuvable.\n"
            f"Create data/probes/ with one file per family/category "
            f"(probes_neutral.txt, probes_code.txt, …) before the dev run."
        )
    sentences = [l.strip() for l in path.read_text().splitlines()
                 if l.strip()][:n]
    if len(sentences) < n:
        raise ValueError(
            f"Seulement {len(sentences)} phrases-probes '{family}' disponibles, {n} requises."
        )
    return sentences


def load_domain_probes(n_per_category: int, config: dict) -> dict[str, list[str]]:
    """Charge the compatible probes by domain (une liste by category pre-registered)."""
    cats = config["steering"].get("domain_probe_categories", [])
    return {c: load_probe_sentences(n_per_category, family=c) for c in cats}


def _is_ood(activation_after, activation_before, feature_stats: dict, config: dict) -> int:
    """MIXED OOD criterion pre-registered (Section 7). Robuste to the p99 faibles /
    distributions asymmetric. Renvoie 1 si hors-distribution, 0 otherwise."""
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
    Apply steering and return before/after pairs + the ACHIEVED delta.

    La detection OOD utilise activation_p99/mean/std depuis feature_stats (table features),
    NOT sae.W_dec[feature_index].norm() (grandeur different). Le delta latent achieved
    (achieved_delta) is measured and reported : adding magnitude·W_dec to the residual does not guarantee
    not an equal increase de activation latente (Section 7).

    Steps d'implementation :
    1. Tokenize the probe sentence
    2. Forward pass, enregistrer activation latente cible AVANT (activation_before)
    3. Intervenir selon intervention_space :
       - 'residual_add_decoder' : ajouter magnitude · sae.W_dec[feature_index] au residual
       - 'sae_latent_clamp'     : clamp the target latent activation to the target value
    4. Re-execute the forward pass with the intervention
    5. Measure the target latent activation AFTER (activation_after); decode text_before/after
    6. achieved_delta = activation_after - activation_before ; calculer ood_flag (criterion mixte)
    """
    results = []

    for probe_id, sentence in enumerate(probe_sentences, 1):
        try:
            # ── PLACEHOLDER — implement the steering specific to the model ──
            text_before       = sentence
            text_after        = None          # DOIT be replaced by l'implementation
            activation_before = None
            activation_after  = None
            # ─────────────────────────────────────────────────────────────────

            # Guard: fail loudly if placeholders have not been replaced
            if text_after is None or text_after == sentence:
                raise NotImplementedError(
                    f"Placeholder steer_feature() not replaced for "
                    f"feature {feature_index}, magnitude {magnitude}.\n"
                    f"Implement model-specific steering before the pilot run."
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
            raise   # propager — not avaler the errors of implementation
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
    """Phase 4 — Steering. Magnitude normalized by feature (× p99) ; dose-response seeded."""
    from utils.db_utils import get_conn

    logger.info("Phase 4 : Steering SAE")

    try:
        model = _get_model(config)        # the model is unique; SAEs are loaded by layer
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

    # Volume of the PRIMAIRE (Sections 6–7) : probes NEUTRES by default, generations_per_probe
    # (1 recommended with a decoding greedy temperature=0). n_probe_sentences_pilot is used
    # en mode dev/pilot. Domain probes are a SECONDARY analysis by default
    # (use_domain_probes_in_primary=false) ; when enabled, elles remainsnt broken down PAR
    # CATEGORY (probe_category kept, not merged).
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

    # Seeded subsample — NOT [:n] which would depend of order de the DB
    rng       = random.Random(seed)
    subsample = rng.sample(random_features,
                           min(n_subsample, len(random_features)))
    subsample_uids = {f["feature_uid"] for f in subsample}

    # Sous-sample : courbe dose-response complete (multiples de p99, control 0 inclus)
    _run_steering_batch(run_id, model, subsample, dose_rel,
                        probe_sets, gens, config, mode, legacy_abs)

    # Features restants : control (0) + magnitude primary only
    remaining = [f for f in random_features
                 if f["feature_uid"] not in subsample_uids]
    _run_steering_batch(run_id, model, remaining, [0.0, primary_rel],
                        probe_sets, gens, config, mode, legacy_abs)

    logger.info("Phase 4 steering completed")


def _insert_steering_result(conn, run_id, feat, space, mag_abs, mag_rel, magnitude_key,
                            family, category, g, r, config):
    """Insertion NON SILENCIEUSE : conserve the 1ʳᵉ output of a cellule, but logs
    toute tentative de rewrite DIFFERENT (table steering_duplicate_attempts) instead de
    ignore it silently (consistent with save_agent_output)."""
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
            logger.warning(f"Divergence steering ignored (1st output kept) for "
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
            # SAE de the COUCHE PROPRE of the feature : on utilise layer_index (numeric).
            sae = _get_sae(config, feat.get("layer_index", feat.get("layer")))
            feature_stats = {
                "activation_p99":  p99,
                "activation_mean": feat.get("activation_mean"),
                "activation_std":  feat.get("activation_std"),
            }
            for rel in rel_magnitudes:
                # magnitude_key : key TEXTE stable (idempotence in LES DEUX modes).
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
                            f"activation_p99 missing for feature "
                            f"{feat['feature_index']} — magnitude relative {rel} ignored"
                        )
                        continue
                # (family, category) × generations multiples ; columns probe_* populated
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
    """Phase 4 — CONTRÔLES D'INTERVENTION (contract v6). Lit config['intervention_controls'].

    Disabled by default (`run_in_pipeline: false`) → no-op with warning, so the
    dev/pilot run not soit not blocked as long as the controls are not implemented. Mettre
    `run_in_pipeline: true` once implemented ; as long as this is not done and it is
    enabled, raises NotImplementedError (comme steer_feature)."""
    ic = config.get("intervention_controls", {})
    if not ic.get("run_in_pipeline", False):
        logger.warning("p4_controls disabled (intervention_controls.run_in_pipeline=false) — ignored.")
        return
    enabled = [name for name, on in ic.items() if on and name != "run_in_pipeline"]
    raise NotImplementedError(
        "run_intervention_controls() not implemented. Controls declared to implement : "
        + ", ".join(enabled) + ". "
        "Chaque control (random_feature_same_layer, random_direction_same_norm, "
        "matched_activation_freq, negative_steering, prompt_only, diffmean_reft) doit "
        "produce results scored by the SAME deterministic path as the treatment. "
        "As long as it is not implemented, garder run_in_pipeline=false."
    )
```

---

## 8. Shuffled MorphoRepr Baseline

```python
# baselines/shuffled.py
"""
Shuffled MorphoRepr control.
- Intra-split only (no contamination cross)
- Longueur d'expression paired ±1 term
- shuffle_id deterministic : {run_id}_{sha1(feature_uid)[:12]}_{shuffle_number}
  (based on feature_uid, NOT feature_index — avoids the collisions inter-layers, Rule 10)
- UNIQUE(run_id, feature_uid, shuffle_number) prevents the doublons
- Generated and evaluated for evaluation_split ONLY
- Scored by the SAME deterministic path as the primary metric (scored_by='deterministic') ;
  a fraction (llm_qualitative_audit_fraction) is marked 'llm_qualitative' for audit
- Repetitions are aggregated before CI computation
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
    """Generate the annotations shuffled intra-split. Config passed explicitly.

    v6 : (a) generates ONLY for evaluation_split (not all splits) ; (b) assigne
    scored_by ('deterministic' by default, 'llm_qualitative' for an audit fraction
    = llm_qualitative_audit_fraction) ; (c) inserts scored_by et feature_uid."""
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
    for feat in features:        # alone split (eval_split) — not de contamination cross
        n_feat     = feat["n_terms"]
        candidates = [
            f for f in features
            if f["feature_uid"] != feat["feature_uid"]
            and abs(f["n_terms"] - n_feat) <= max_diff
        ]
        if len(candidates) < 3:
            logger.warning(
                f"Feature {feat['feature_uid']} : "
                f"only {len(candidates)} shuffle candidates"
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

    logger.info(f"Shuffles generated : {len(inserts)} ({n_repeats}/feature, split={eval_split})")
```

---

## 8 bis. Deterministic Causal Scorer (Primary Metric)

This section implements the **primary deterministic causal metric** (Rule 8): the direction predicted by the prediction agent, based on the annotation alone, is compared in code with the direction observed by pre-registered deterministic classifiers. The score is a **global macro-F1 over all `(feature_uid, robust property)` pairs**, not a per-feature score averaged afterward. Bootstrap confidence intervals are **feature-clustered**, with `feature_uid` as the resampling unit.

In v6.8.0, `_load_pairs()` remains implemented for `method="morphorepr"`, and baseline prediction Option B is now wired for `nl_labels` and `semantic_regex`. The scorer reads prediction outputs from `agent_outputs`, reads steering observations from `steering_results`, applies the deterministic robust-property classifiers to `text_before` / `text_after`, and assembles strict model/split/intervention-space/OOD-aware pairs. Baselines are not fabricated: paired comparisons only run when the corresponding baseline prediction outputs exist and pass `assert_baseline_predictions_ready`.

```python
# agents/causal_scorer.py
"""
Deterministic causal scorer (primary metric). No LLM judge is used here (Rule 8).

Logical input: a list of pairs {feature_uid, property, predicted, observed}
restricted to ROBUST_PROPERTIES, where predicted/observed ∈ {INCREASE, DECREASE, NO_CHANGE}.
 - predicted: direction predicted by the prediction agent.
 - observed: direction measured by the deterministic property classifier.
The macro-F1 is computed globally over all pairs, not per feature.
"""
import json
import logging
import random
from uuid import uuid4
from datetime import datetime
from utils.db_utils import get_conn, ensure_legacy_model_run

logger = logging.getLogger(__name__)

DIRECTIONS = ["INCREASE", "DECREASE", "NO_CHANGE"]
ROBUST_PROPERTIES = ["negation_presence", "tense", "code_presence", "conditional_modality"]


ACCEPTED_PREDICTOR_AGENTS = {
    "morphorepr":          ["predictor", "predictor_morphorepr"],
    "nl_labels":           ["predictor_nl_labels"],
    "semantic_regex":      ["predictor_semantic_regex"],
    "keyword_tags":        ["predictor_keyword_tags"],
    "morphorepr_shuffled": ["predictor_morphorepr_shuffled"],
}

CLASSIFIER_BY_PROPERTY = None

_DIRECTION_ALIASES = {
    "increase": "INCREASE", "up": "INCREASE", "more": "INCREASE", "INCREASE": "INCREASE",
    "decrease": "DECREASE", "down": "DECREASE", "less": "DECREASE", "DECREASE": "DECREASE",
    "no_change": "NO_CHANGE", "unchanged": "NO_CHANGE", "none": "NO_CHANGE", "NO_CHANGE": "NO_CHANGE",
}


def compute_global_macro_f1(pairs: list[dict]) -> dict:
    """Global macro-F1 over all (feature, property) pairs."""
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
        if (tp + fn) > 0:
            f1s.append(f1)
    n = len(pairs) or 1
    accuracy = sum(confusion[d][d] for d in DIRECTIONS) / n
    return {"macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
            "accuracy": round(accuracy, 4), "n_pairs": len(pairs), "per_class": per_class}


def feature_clustered_bootstrap(pairs: list[dict], n_resamples: int = 10000,
                                seed: int = 42, alpha: float = 0.05) -> dict:
    """Bootstrap CI for global macro-F1, clustered by feature_uid."""
    by_feat: dict[str, list[dict]] = {}
    for p in pairs:
        by_feat.setdefault(p["feature_uid"], []).append(p)
    uids = list(by_feat)
    rng  = random.Random(seed)
    stats = []
    for _ in range(n_resamples):
        sample_uids = [rng.choice(uids) for _ in uids]
        resampled = [pair for u in sample_uids for pair in by_feat[u]]
        stats.append(compute_global_macro_f1(resampled)["macro_f1"])
    stats.sort()
    lo = stats[int((alpha / 2) * n_resamples)]
    hi = stats[int((1 - alpha / 2) * n_resamples) - 1]
    return {"ci_low": round(lo, 4), "ci_high": round(hi, 4), "n_features": len(uids)}


def paired_diff_bootstrap(pairs_a: list[dict], pairs_b: list[dict],
                          n_resamples: int = 10000, seed: int = 42,
                          alpha: float = 0.05) -> dict:
    """Paired macro-F1 difference (A − B), clustered by shared features."""
    a = {p["feature_uid"]: [] for p in pairs_a}
    b = {p["feature_uid"]: [] for p in pairs_b}
    for p in pairs_a: a[p["feature_uid"]].append(p)
    for p in pairs_b: b[p["feature_uid"]].append(p)
    uids = sorted(set(a) & set(b))
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


def _default_classifier_map() -> dict:
    """Lazy import of robust-property classifiers. negative_valence is excluded from the primary metric."""
    import classifiers.negation, classifiers.tense, classifiers.code_presence, classifiers.modality
    return {
        "negation_presence":    classifiers.negation.measure,
        "tense":                classifiers.tense.measure,
        "code_presence":        classifiers.code_presence.measure,
        "conditional_modality": classifiers.modality.measure,
    }


def _normalize_direction(value) -> str | None:
    """Normalize a direction alias. Ambiguous values are rejected, never silently mapped to NO_CHANGE."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    return _DIRECTION_ALIASES.get(v) or _DIRECTION_ALIASES.get(v.lower())


def _extract_predicted_directions(output_json) -> dict[str, str]:
    """Extract {property: DIRECTION} from the three accepted predictor-output formats."""
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
            if prop in ROBUST_PROPERTIES and d:
                out[prop] = d

    props = output_json.get("properties")
    if isinstance(props, dict):
        for prop, val in props.items():
            d = _normalize_direction(val.get("direction")) if isinstance(val, dict) else _normalize_direction(val)
            if prop in ROBUST_PROPERTIES and d:
                out[prop] = d
    return out


def _primary_magnitude_key(config: dict) -> str:
    """Text key for the primary steering magnitude, aligned with steerer._run_steering_batch."""
    st = config.get("steering", {})
    if st.get("magnitude_mode", "p99_relative") == "absolute":
        return f"abs:{st.get('legacy_absolute_magnitude', 5)}"
    return f"rel:{st.get('primary_magnitude_rel', 1.0)}"


def _observe_property_direction(rows: list[dict], property_name: str, classifier_fn) -> dict | None:
    """Apply a deterministic classifier to valid before/after text pairs."""
    before = [r["text_before"] for r in rows if r.get("text_before") and r.get("text_after")]
    after  = [r["text_after"]  for r in rows if r.get("text_before") and r.get("text_after")]
    if not before:
        return None
    measured = classifier_fn(before, after)
    d = _normalize_direction(measured.get("direction"))
    if not d:
        raise ValueError(f"Classifier for {property_name} returned an invalid direction: {measured!r}")
    return {"property": property_name, "direction": d,
            "n_observations": len(before), "details": measured}


def _resolve_model_run_id(run_id: str, config: dict | None, model_run_id: str | None) -> str:
    if model_run_id:
        return model_run_id
    if config:
        primary = config.get("_runtime", {}).get("model_run_ids", {}).get("primary")
        if primary:
            return primary
    return ensure_legacy_model_run(run_id)


def _load_pairs(run_id: str,
                method: str,
                config: dict | None = None,
                model_run_id: str | None = None,
                split: str = "random") -> list[dict]:
    """Assemble deterministic prediction/observation pairs for one method.

    For v6.7.0, `method="morphorepr"` is implemented. Baseline methods are intentionally
    not fabricated: if baseline prediction outputs are not present, a clear RuntimeError is
    raised when comparisons are explicitly enabled.
    """
    config = config or {}
    if method not in ACCEPTED_PREDICTOR_AGENTS:
        raise NotImplementedError(f"Unknown or unsupported causal-scoring method: {method!r}")

    mrid = _resolve_model_run_id(run_id, config, model_run_id)
    magnitude_key = _primary_magnitude_key(config)
    st = config.get("steering", {})
    probe_family = st.get("primary_probe_family", "neutral")
    exclude_ood = st.get("exclude_ood_from_primary", True)
    intervention_space = st.get("intervention_space", "residual_add_decoder")

    agent_names = ACCEPTED_PREDICTOR_AGENTS[method]
    placeholders = ",".join("?" for _ in agent_names)

    with get_conn() as conn:
        pred_rows = conn.execute(f"""
            SELECT ao.feature_uid, ao.feature_index, ao.output_json
            FROM agent_outputs ao
            JOIN features f ON f.feature_uid = ao.feature_uid
            WHERE ao.run_id = ?
              AND ao.model_run_id = ?
              AND ao.agent_name IN ({placeholders})
              AND ao.status = 'ok'
              AND f.split = ?
        """, (run_id, mrid, *agent_names, split)).fetchall()

        if not pred_rows:
            raise RuntimeError(
                f"No predictor outputs found for method={method}, run_id={run_id}, "
                f"model_run_id={mrid}, split={split}."
            )

        q = """
            SELECT sr.*
            FROM steering_results sr
            JOIN features f ON f.feature_uid = sr.feature_uid
            WHERE sr.run_id = ?
              AND sr.model_run_id = ?
              AND sr.intervention_space = ?
              AND sr.magnitude_key = ?
              AND sr.probe_family = ?
              AND sr.probe_category IS NULL
              AND sr.text_after IS NOT NULL
              AND f.split = ?
        """
        params = [run_id, mrid, intervention_space, magnitude_key, probe_family, split]
        if exclude_ood:
            q += " AND COALESCE(sr.ood_flag, 0) = 0"
        obs_rows = conn.execute(q, params).fetchall()

    if not obs_rows:
        raise RuntimeError(
            f"No steering observations found for run_id={run_id}, model_run_id={mrid}, "
            f"split={split}, magnitude_key={magnitude_key}, intervention_space={intervention_space}. "
            f"Did you run p4_steer first?"
        )

    predictions: dict[str, dict[str, str]] = {}
    for r in pred_rows:
        dirs = _extract_predicted_directions(r["output_json"])
        robust = {p: d for p, d in dirs.items() if p in ROBUST_PROPERTIES}
        if robust:
            predictions[r["feature_uid"]] = robust

    by_feature: dict[str, list[dict]] = {}
    for r in obs_rows:
        by_feature.setdefault(r["feature_uid"], []).append(dict(r))

    classifier_map = CLASSIFIER_BY_PROPERTY or _default_classifier_map()
    pairs: list[dict] = []
    for feature_uid, pred_by_prop in predictions.items():
        rows = by_feature.get(feature_uid)
        if not rows:
            logger.info("Skipping %s: predictions exist but no steering observations", feature_uid)
            continue
        for prop, predicted in pred_by_prop.items():
            if prop not in ROBUST_PROPERTIES:
                continue
            classifier_fn = classifier_map.get(prop)
            if classifier_fn is None:
                raise RuntimeError(f"No deterministic classifier registered for robust property {prop!r}")
            observed = _observe_property_direction(rows, prop, classifier_fn)
            if observed is None:
                continue
            pairs.append({
                "feature_uid": feature_uid,
                "model_run_id": mrid,
                "property": prop,
                "predicted": predicted,
                "observed": observed["direction"],
                "method": method,
                "n_observations": observed["n_observations"],
                "metadata": {
                    "split": split,
                    "magnitude_key": magnitude_key,
                    "intervention_space": intervention_space,
                    "exclude_ood_from_primary": exclude_ood,
                    "classifier_details": observed.get("details", {}),
                },
            })

    if not pairs:
        raise RuntimeError(
            f"No causal pairs assembled for method={method}, run_id={run_id}, "
            f"model_run_id={mrid}, split={split}."
        )
    return pairs


def run(run_id: str, config: dict):
    """Primary deterministic causal score: MorphoRepr macro-F1 + feature-clustered bootstrap.

    Baseline comparisons are gated by causal_scoring.run_baseline_comparisons. Option A is the
    default: if baselines are not wired, the MorphoRepr score is written without any superiority
    or non-inferiority verdict.
    """
    split = config.get("primary_split", "random")
    model_run_id = _resolve_model_run_id(run_id, config, None)
    n_boot = config["stats"].get("bootstrap_resamples", 10000)

    mr = _load_pairs(run_id, "morphorepr", config=config, model_run_id=model_run_id, split=split)
    point = compute_global_macro_f1(mr)
    ci = feature_clustered_bootstrap(mr, n_boot, config.get("seed", 42))
    results = {"morphorepr": {**point, **ci}, "comparisons": {}}

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO metrics (metric_id, run_id, model_run_id, phase, split, metric_name,
                                 value, ci_low, ci_high, n_samples, baseline, computed_at)
            VALUES (?, ?, ?, 'p4_score', ?, 'causal_macro_f1_global', ?, ?, ?, ?, NULL, ?)
        """, (str(uuid4()), run_id, model_run_id, split, point["macro_f1"],
              ci["ci_low"], ci["ci_high"], point["n_pairs"], datetime.utcnow().isoformat()))

    if config.get("causal_scoring", {}).get("run_baseline_comparisons", False):
        nim = config["thresholds"].get("nim_delta", 0.05)
        for base in config["stats"].get("superiority_vs", []) + config["stats"].get("non_inferiority_vs", []):
            base_pairs = _load_pairs(run_id, base, config=config, model_run_id=model_run_id, split=split)
            d = paired_diff_bootstrap(mr, base_pairs, n_boot, config.get("seed", 42))
            mode = "non_inferiority" if base in config["stats"].get("non_inferiority_vs", []) else "superiority"
            d["verdict"] = (("pass" if d["ci_low"] > -nim else "fail") if mode == "non_inferiority"
                            else ("pass" if d["ci_low"] > 0 else "fail"))
            results["comparisons"][base] = {"mode": mode, **d}
            with get_conn() as conn:
                conn.execute("""
                    INSERT INTO metrics (metric_id, run_id, model_run_id, phase, split, metric_name,
                                         value, ci_low, ci_high, n_samples, baseline, computed_at)
                    VALUES (?, ?, ?, 'p4_score', ?, 'causal_macro_f1_paired_diff', ?, ?, ?, ?, ?, ?)
                """, (str(uuid4()), run_id, model_run_id, split, d["diff"], d["ci_low"],
                      d["ci_high"], d["n_shared_features"], base, datetime.utcnow().isoformat()))
    else:
        logger.warning("Baseline comparisons disabled (causal_scoring.run_baseline_comparisons=false; Option B is available but off by default). "
                       "Writing MorphoRepr score only, without superiority/non-inferiority verdict.")

    logger.info("Global causal score: macro-F1=%s CI95=%s", point["macro_f1"], ci)
    return results
```

---

## 9. Unit Tests

```python
# tests/conftest.py
import os
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """DB temporary isolated injected via env var. Aucune DB de production touched."""
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


# All encoding examples from the paper must parse correctly (mal/ne and infix cases).
@pytest.mark.parametrize("word,root,prefixes,infixes,suffix", [
    ("ag-is",          "ag",   [],      [],      "-is"),
    ("mal-o",          "mal",  [],      [],      "-o"),   # mal as RACINE
    ("ne-a",           "ne",   [],      [],      "-a"),   # not as RACINE
    ("mal-emo-a",      "emo",  ["mal"], [],      "-a"),   # mal as PREFIX
    ("ne-soc-a",       "soc",  ["ne"],  [],      "-a"),
    ("soc-ant-o",      "soc",  [],      ["ant"], "-o"),
    ("dat-ad-o",       "dat",  [],      ["ad"],  "-o"),
    ("ag-int-a",       "ag",   [],      ["int"], "-a"),
    ("pens-ad-is",     "pens", [],      ["ad"],  "-is"),
    ("mal-far-int-e",  "far",  ["mal"], ["int"], "-e"),
    ("mal-ne-o",       "ne",   ["mal"], [],      "-o"),   # prefix mal + root not
])
def test_examples_from_paper(word, root, prefixes, infixes, suffix):
    t = parse_word(word, known_free_roots={"far", "pens"})
    assert t.is_valid, f"{word} devrait be valid : {t.parse_error}"
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

    def test_sans_suffix_invalide(self):
        t = parse_word("ag")
        assert not t.is_valid and t.parse_error is not None

    def test_root_libre(self):
        t = parse_word("pens-is")
        assert t.root == "pens" and t.suffix == "-is" and t.is_valid


class TestParseExpression:
    def test_deux_terms_valid(self):
        e = parse_expression("0.86·mal-emo-a + 0.42·ne-soc-a")
        assert e.is_valid and len(e.terms) == 2
        assert e.roots == {"emo", "soc"}

    def test_order_decroissant_obligatoire(self):
        e = parse_expression("0.40·ag-is + 0.90·sci-o")
        assert not e.is_valid and "decreasing" in e.parse_error.lower()

    def test_coeffhereent_hors_plage(self):
        e = parse_expression("9.99·ag-is")
        assert not e.is_valid

    def test_expression_empty(self):
        assert not parse_expression("").is_valid


class TestRootValidation:
    def test_root_libre_bien_formee_valid(self):
        assert is_valid_root("pens") and is_valid_root("far")

    def test_token_reserve_invalide_comme_root(self):
        assert not is_valid_root("is")
        assert not is_valid_root("ad")
        assert not is_valid_root("pli")   # prefix reserved, not a root

    def test_mal_ne_valid_comme_roots_predefinies(self):
        # mal and not SONT of the roots valid (predefined)...
        assert is_valid_root("mal") and is_valid_root("ne")

    def test_mal_ne_non_enregistrables_comme_libres(self):
        # ...but may NOT be re-registered as NOUVELLES roots libres.
        assert can_register_new_free_root("mal") is not None
        assert can_register_new_free_root("ne")  is not None

    def test_enregistrement_root_libre_valid(self):
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


def test_encodage_partiel_laisse_remains(test_db):
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


def test_resume_batch_apres_crash(test_db):
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

# Config minimale for the tests (generate_shuffles prend now the config en argument)
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
                coeffhereent_type, created_at
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
    """A feature must never receive its own annotation (comparison on feature_uid)."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", _CFG, n_repeats=3)
    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT feature_uid, source_feature_uid FROM shuffle_controls"
    ).fetchall()
    conn.close()
    assert all(r[0] != r[1] for r in rows)


def test_shuffle_constraint_unherete(test_db):
    """La constraint UNIQUE prevents the doublons logiques."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", _CFG, n_repeats=3)
    generate_shuffles("r1", _CFG, n_repeats=3)  # second call — no duplicates
    conn = sqlite3.connect(test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM shuffle_controls WHERE run_id='r1'"
    ).fetchone()[0]
    conn.close()
    assert count <= 5 * 3   # max 15 entries for 5 features × 3 repetitions
```

```python
# ─────────────────────────────────────────────
# tests/test_feature_uid_integration.py  (v6.1)
# Robustesse of identity feature_uid : DEUX layers partageant the same feature_index.
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


def test_meme_feature_index_deux_layers_pas_de_collision(test_db):
    """feature_index=123 on the layers 6 ET 9 : deux features distinctes, deux outputs
    encodeur distincts, NO collision (la logical key is feature_uid)."""
    conn = sqlite3.connect(test_db); _run(conn)
    _feat(conn, 6, 123); _feat(conn, 9, 123)     # same index, layers different
    conn.commit(); conn.close()

    save_agent_output("r1", 123, "encoder", 1, {"status": "encoded", "expression": "0.80·ag-is"},
                      "raw6", "ok", None, 10, 5, None, 0.0, feature_uid=_uid(6, 123))
    save_agent_output("r1", 123, "encoder", 1, {"status": "encoded", "expression": "0.70·sci-o"},
                      "raw9", "ok", None, 10, 5, None, 0.0, feature_uid=_uid(9, 123))

    conn = sqlite3.connect(test_db)
    n = conn.execute("SELECT COUNT(*) FROM agent_outputs WHERE run_id='r1'").fetchone()[0]
    conn.close()
    assert n == 2                                 # two rows, not of overwrite


def test_divergence_meme_uid_bloque(test_db):
    """Same feature_uid + DIFFERENT output → RuntimeError (non silencieux)."""
    conn = sqlite3.connect(test_db); _run(conn); _feat(conn, 6, 123); conn.commit(); conn.close()
    save_agent_output("r1", 123, "encoder", 1, {"v": 1}, "raw", "ok", None, 1, 1, None, 0.0,
                      feature_uid=_uid(6, 123))
    with pytest.raises(RuntimeError):
        save_agent_output("r1", 123, "encoder", 1, {"v": 2}, "raw", "ok", None, 1, 1, None, 0.0,
                          feature_uid=_uid(6, 123))


def test_hash_corpus_stable_plusieurs_layers(test_db):
    """hash_corpus_canonical is stable and independent of order of insertion (ORDER BY
    feature_uid), even with several layers sharing feature_index values."""
    conn = sqlite3.connect(test_db); _run(conn)
    for layer, idx in [(6, 1), (9, 1), (6, 2), (9, 2)]:
        _feat(conn, layer, idx)
    conn.commit(); conn.close()
    h1 = hash_corpus_canonical(test_db)

    conn = sqlite3.connect(test_db)
    conn.execute("DELETE FROM features")
    for layer, idx in [(9, 2), (6, 1), (9, 1), (6, 2)]:        # order of insertion different
        _feat(conn, layer, idx)
    conn.commit(); conn.close()
    h2 = hash_corpus_canonical(test_db)
    assert h1 == h2


def test_shuffle_pas_de_collision_uid(test_db):
    """Deux features de layers different but MÊME feature_index : the shuffle_id
    (based sur sha1(feature_uid)) not collisionnent pas."""
    conn = sqlite3.connect(test_db); _run(conn)
    # 4 features on 2 layers, indices {1,2} repeated → 2 pairs of identical indexes
    data = [(6, 1), (6, 2), (6, 3), (9, 1), (9, 2), (9, 3)]
    for layer, idx in data:
        _feat(conn, layer, idx)
        conn.execute("""INSERT INTO agent_outputs (output_id, run_id, feature_uid,
            feature_index, agent_name, run_number, output_json, raw_output, status,
            error_msg, tokens_input, tokens_output, batch_id, cost_usd, coeffhereent_type,
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
    assert len(ids) == len(set(ids))              # no shuffle_id duplicated
    assert n_uid == 6                             # the 6 distinct features are shuffled


def test_log_api_cost_divergence_leve(test_db):
    """Reprise of a batch where the cost recomputed DIFFERS of the cost logged → RuntimeError."""
    from utils.db_utils import log_api_cost
    conn = sqlite3.connect(test_db); _run(conn); conn.commit(); conn.close()
    log_api_cost("r1", "p3", "encoder", "m", 100, 50, "b1", 1.0)
    # same batch, cost different → divergence
    with pytest.raises(RuntimeError):
        log_api_cost("r1", "p3", "encoder", "m", 100, 50, "b1", 2.0)


def test_batch_items_mapping_persiste_pour_resume(test_db):
    """Le mapping custom_id → feature_uid is persisted (batch_items) and retrievable even if
    the feature is no longer pending (crash-safe resume case)."""
    from utils.db_utils import register_batch, save_batch_items, load_batch_item_map
    from utils.api_utils import feature_custom_id, build_batch_item_rows
    conn = sqlite3.connect(test_db); _run(conn)
    _feat(conn, 6, 123); _feat(conn, 9, 123)      # same feature_index, deux layers
    conn.commit(); conn.close()

    feats = [{"feature_uid": _uid(6, 123), "feature_index": 123},
             {"feature_uid": _uid(9, 123), "feature_index": 123}]
    register_batch("b1", "r1", "p3", "encoder", 1, len(feats))
    save_batch_items("b1", build_batch_item_rows(feats))

    m = load_batch_item_map("b1")
    assert m[feature_custom_id(feats[0])]["feature_uid"] == _uid(6, 123)
    assert m[feature_custom_id(feats[1])]["feature_uid"] == _uid(9, 123)
    # idempotent : re-persister not duplique not (PK batch_id+custom_id)
    save_batch_items("b1", build_batch_item_rows(feats))
    assert len(load_batch_item_map("b1")) == 2


def test_register_batch_with_items_atomique(test_db):
    """register_batch_with_items writes the batch ET son mapping en a single transaction
    (no window batch-sans-map)."""
    from utils.db_utils import register_batch_with_items, load_batch_item_map, get_unconsumed_batch
    from utils.api_utils import build_batch_item_rows
    conn = sqlite3.connect(test_db); _run(conn)
    _feat(conn, 6, 7); _feat(conn, 9, 7)
    conn.commit(); conn.close()

    feats = [{"feature_uid": _uid(6, 7), "feature_index": 7},
             {"feature_uid": _uid(9, 7), "feature_index": 7}]
    register_batch_with_items("bX", "r1", "p3", "encoder", 1, len(feats),
                              build_batch_item_rows(feats))
    # the batch is registered (recoverable) AND the map is present, in the same transaction
    assert get_unconsumed_batch("r1", "p3", "encoder", 1) == "bX"
    assert len(load_batch_item_map("bX")) == 2


# ─────────────────────────────────────────────
# tests/test_causal_scorer.py  (v6.1)
# Proves that macro-F1 is GLOBAL on couples, and that the bootstrap is clustered.
# ─────────────────────────────────────────────

from agents.causal_scorer import (compute_global_macro_f1,
                                   feature_clustered_bootstrap, paired_diff_bootstrap)


def test_macro_f1_global_pas_par_feature():
    """The score is computed over the FULL set of pairs. Une feature with alone classe
    observed does not make the score unstable (unlike per-feature macro-F1)."""
    pairs = [
        {"feature_uid": "u1", "property": "tense",            "predicted": "INCREASE",  "observed": "INCREASE"},
        {"feature_uid": "u1", "property": "negation_presence","predicted": "DECREASE",  "observed": "DECREASE"},
        {"feature_uid": "u2", "property": "tense",            "predicted": "NO_CHANGE", "observed": "NO_CHANGE"},
        {"feature_uid": "u2", "property": "code_presence",    "predicted": "INCREASE",  "observed": "INCREASE"},
    ]
    r = compute_global_macro_f1(pairs)
    assert r["n_pairs"] == 4
    assert r["macro_f1"] == 1.0 and r["accuracy"] == 1.0   # all the directions correctes


def test_macro_f1_penalise_errors():
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
# Batch API custom_id values must be unique even if feature_index is repeated across layers.
# ─────────────────────────────────────────────

from utils.api_utils import feature_custom_id, build_custom_id_map, build_batch_item_rows


def test_batch_custom_id_unique_with_same_feature_index():
    features = [
        {"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
        {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123},
    ]
    ids = [feature_custom_id(f) for f in features]
    assert len(ids) == len(set(ids))            # not de collision


def test_custom_id_map_recupere_feature_uid():
    features = [
        {"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
        {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123},
    ]
    m = build_custom_id_map(features)
    assert m[feature_custom_id(features[0])] == "gpt2:res-jb:6:hook_resid_post:123"
    assert m[feature_custom_id(features[1])] == "gpt2:res-jb:9:hook_resid_post:123"


def test_submit_rejette_batch_items_incoherents():
    """Pre-verification AVANT submission : if the custom_id of the requests ≠ batch_items,
    submit_and_poll_batch raises ValueError (before tout appel network, donc before billing)."""
    import pytest
    from utils.api_utils import submit_and_poll_batch
    feats = [{"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
             {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123}]
    requests = [{"custom_id": feature_custom_id(f), "params": {}} for f in feats]
    items    = build_batch_item_rows(feats[:1])   # incomplet : il manque the 2ᵉ feature
    with pytest.raises(ValueError):
        submit_and_poll_batch(requests, "r1", "p3", "encoder", 1, "m", {}, batch_items=items)
```

---

## 10. Orchestrator

```python
# orchestrator.py
"""
Orchestrateur MorphoRepr v6.4.1 — run frozen et auditable.

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

# Create logs/ BEFORE basicConfig : otherwise FileHandler("logs/pipeline.log") fails at import time
# (before even entering in run_pipeline which created the directory too late).
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
from agents import qualitative_judge          # juge LLM — analyses SECONDAIRES only
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
        # The frozen run (run_v1) DOIT pin the commit. Only dev runs may
        # lift this requirement viallow_unpinned_commit: true.
        if not config.get("allow_unpinned_commit", False):
            raise RuntimeError(
                "git_commit is still 'FILL_BEFORE_LAUNCH'. Pin the commit "
                "(git_commit: <HEAD>) in the config before the frozen run, or set "
                "allow_unpinned_commit: true for a dev run."
            )
        logger.warning("git_commit non pinned (dev run) — provenance non frozen.")
    elif config_commit != git_commit:
        raise RuntimeError(
            f"git_commit in the config ({config_commit[:8]}) does not match "
            f"au HEAD courant ({git_commit[:8]}). "
            f"Update configs/run_v1.yaml before launch."
        )

    prompt_hashes = register_prompts(config["prompts"])
    lexicon_hash  = hash_lexicon_canonical("db/lexicon.json")
    # The corpus hash is FROZEN AFTER p1_load/p1_rank (which populate and stratify the table
    # features) — otherwise il not would reflect not the corpus actually used. NULL = pending ;
    # freeze_corpus_hash() the renseigne (phase p1_freeze_corpus).
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

    logger.info(f"Run initialized : {run_id}")
    logger.info(f"  Git commit    : {git_commit[:16]}")
    logger.info(f"  Config hash   : {config_hash[:16]}")
    logger.info(f"  Corpus hash   : (frozen after p1_load/p1_rank)")
    logger.info(f"  Lexique hash  : {lexicon_hash[:16]}")
    if proxy.get("enabled"):
        logger.info(f"  Model proxy  : {proxy.get('name')} (Sonnet inaccessible)")
    return run_id


def freeze_corpus_hash(run_id: str):
    """Freeze the hash of the corpus AFTER loading/stratification of the features (phase
    p1_freeze_corpus). Idempotent : does not rewrite an already frozen hash (otherwise resume
    would detect it as a 'modification')."""
    with get_conn() as conn:
        row = conn.execute("SELECT corpus_hash FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row and row["corpus_hash"]:
            logger.info("Corpus already frozen — not de rewrite.")
            return
        h = hash_corpus_canonical("db/features.db")
        conn.execute("UPDATE runs SET corpus_hash=?, status='running_frozen' WHERE run_id=?",
                     (h, run_id))
    logger.info(f"  Corpus hash frozen : {h[:16]}")


def verify_resume_integrity(run_id: str, config: dict, args):
    """All the hashes re-verified to the resume. Tout changement = error blocking."""
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
            f"Commit Git modified : {row['git_commit'][:8]} → {current_git[:8]}"
        )
    if row["config_hash"] != current_config:
        errors.append("Config modified since the original run")
    # The corpus is compared only if it has been FROZEN (after p1_load/p1_rank). If NULL (crash
    # before the gel), on not compare not — il sera frozen to the prochain passage de p1_freeze_corpus.
    if row["corpus_hash"]:
        current_corpus = hash_corpus_canonical("db/features.db")
        if row["corpus_hash"] != current_corpus:
            errors.append("Corpus modified since the original run")
    if row["lexicon_hash"] != current_lexicon:
        errors.append("Lexicon modified since the original run")

    registered_hashes = json.loads(row["prompt_hashes"])
    try:
        verify_prompts_unchanged(config["prompts"], registered_hashes)
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        msg = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(
            f"Reprise blocked — detected modifications :\n{msg}\n\n"
            f"To continue with these modifications, create a new run."
        )
    logger.info(f"Integrity verified for run {run_id} — resume authorized")


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
    logger.info(f"  ✓ Phase {phase} complete")


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
    logger.info("=== Cumulative cost ===")
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
    # Freeze of the hash of the corpus AFTER loading+stratification (the corpus is then frozen).
    ("p1_freeze_corpus", lambda rid, cfg: freeze_corpus_hash(rid),   "Gel du hash corpus"),
    ("p2_cluster",     lambda rid, cfg: cluster.run(rid),            "Clustering"),
    ("p2_label",       lambda rid, cfg: labeler.run(rid),            "Induction lexicon"),
    ("p2_consistency", lambda rid, cfg: consistency.run(rid),        "Validation lexicon"),
    ("p3_encode",      lambda rid, cfg: encoder.run(rid),            "Encodage (2 runs)"),
    ("p3_fidelity",    lambda rid, cfg: fidelity.run(rid),           "Fidelity AUC-ROC"),
    ("p3_baselines",   lambda rid, cfg: _run_baselines(rid),         "Baselines d'annotation"),
    ("p3_shuffle",     lambda rid, cfg: shuffled_baseline.generate_shuffles(rid, cfg),
                                                                     "Shuffled control"),
    ("p4_steer",       lambda rid, cfg: (steerer.run(rid, cfg)
                          if cfg["steering"].get("run_in_pipeline", True)
                          else logger.warning("p4_steer disabled (steering.run_in_pipeline=false) — steering not implemented")),
                                                                     "Steering (traitement)"),
    ("p4_controls",    lambda rid, cfg: steerer.run_intervention_controls(rid, cfg),
                                                                     "Intervention controls"),
    # Causal scoring phases: guarded by causal_scoring.run_in_pipeline (without steering or
    # observations classifiers, elles do not have yet de material ; _load_pairs() = contract).
    ("p4_predict",     lambda rid, cfg: (predictor.run(rid)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_predict disabled (causal_scoring.run_in_pipeline=false)")),
                                                                     "Causal prediction"),
    # Metric PRIMAIRE = score deterministic (prediction vs classifiers), SANS juge LLM (Rule 8)
    ("p4_score",       lambda rid, cfg: (causal_scorer.run(rid, cfg)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_score disabled (_load_pairs not implemented)")),
                                                                     "Score causal DETERMINISTIC (primary)"),
    # Juge LLM qualitatif : analyses SECONDAIRES only (case ambigus, audit)
    ("p4_qualitative", lambda rid, cfg: (qualitative_judge.run(rid, cfg)
                          if cfg.get("causal_scoring", {}).get("run_in_pipeline", False)
                          else logger.warning("p4_qualitative disabled (causal_scoring.run_in_pipeline=false)")),
                                                                     "Juge LLM qualitatif (secondary)"),
    ("p5_report",      lambda rid, cfg: reporter.run(rid),           "Synthesis"),
]


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

    # Propager --n-features (dev run) : loader/ranker lisent config["_runtime"]["n_features_override"].
    config.setdefault("_runtime", {})["n_features_override"] = args.n_features
    if args.n_features:
        logger.info(f"Dev run: corpus limited to {args.n_features} features (override).")
        if config.get("run_mode") == "full":
            logger.warning("--n-features used with run_mode=full ; consider run_mode=dev "
                           "(otherwise n_probe_sentences remains at the value 'full').")

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
            logger.info(f"⏭  {phase_id} already completed")
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
                    f"Budget exceeded : {cost:.2f}$ >= "
                    f"{config['budget']['max_cost_usd']}$"
                )

        except Exception as e:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE runs SET status='failed' WHERE run_id=?",
                    (run_id,)
                )
            logger.exception(f"Phase {phase_id} failed — run {run_id} archived")
            # Full frozen run : not de correction automatique, not of intervention agentique.
            # Archiver, analyser, puis create a new run with a new commit.
            sys.exit(1)

    with get_conn() as conn:
        conn.execute("""
            UPDATE runs SET status='completed', completed_at=?
            WHERE run_id=?
        """, (datetime.utcnow().isoformat(), run_id))
    print_cost_summary(run_id)
    logger.info(f"\n✅ Run {run_id} completed — results in db/features.db")


if __name__ == "__main__":
    run_pipeline(parse_args())
```

---

## 11. Setup and Execution Order

```bash
# ── 1. Environment ────────────────────────────────────────
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sqlite3 db/features.db < db/schema.sql

# ── 2. Unit tests (without API key) ───────────────────────
pytest tests/test_parser.py tests/test_schema.py \
       tests/test_db.py tests/test_shuffle_baseline.py -v
# All must pass before continuing

# ── 3. Classifier calibration ─────────────────────────
python classifiers/calibration/run_calibration.py
# Must display ✅ PASS for the 5 properties

# ── 4. Model access validation (BLOCKING) ───────────
python -c "
from agents.steerer import _get_model, _get_sae
from utils.config_utils import load_config
cfg = load_config('configs/dev_run.yaml')
_get_model(cfg)
# _get_sae now takes a LAYER (the SAE is loaded by layer, Rule 6).
# Test on a representative proxy layer (ex. 6 for pythia).
layer = cfg.get('proxy_model', {}).get('validation_layer', 6)
_get_sae(cfg, layer)
print('Model access OK')
"
# If NotImplementedError : implement _get_model() / _get_sae() first.
# proxy_model.enabled is true BY DEFAULT (Rule 5) ; for a production model,
# set enabled=false and provide access paths in agents/steerer.py.
# Reminder : the reproducibility of the clustering (Phase 2) depends on
# clustering.kmeans_random_state / umap_random_state (seeds fixed in the config).

# ── 4 bis. PRE-PILOT Phase 4 guard (to execute UNIQUEMENT before a pilot/full run AVEC
#          steering enabled). Is NOT a step of the plumbing dev run outside Phase 4 :
#          as long as steer_feature() is a placeholder, this guard FAILS — this is expected,
#          and this must NOT prevent the plumbing dev run (step 5) from running.
python -c "
from agents.steerer import assert_steering_ready
from utils.config_utils import load_config
assert_steering_ready(load_config('configs/dev_run.yaml'), n_probe=5)
print('steer_feature() properly produces text/activation/delta/ood — Phase 4 ready')
"
# Run only (and make pass) ONLY BEFORE enabling steering (steering.run_in_pipeline=true)
# for a pilot/full run. Phase 4 remains a CONTRACT (§7) ; the plumbing dev run (step 5)
# runs independently, without this guard.

# ── 5. Dev run (5 features — plumbing) ─────────────────────
# Plumbing OUTSIDE steering/scoring (as long as steer_feature() and causal_scorer._load_pairs()
# are not implemented) : in dev_run.yaml, set steering.run_in_pipeline=false ET
# causal_scoring.run_in_pipeline=false → p4_steer, p4_controls, p4_predict, p4_score and
# p4_qualitative are skipped (warnings) ; the pipeline runs up to p5_report without crashing.
# Set these flags to true AFTER implementing the steering/scoring (et fait passer
# assert_steering_ready, step 4 bis).
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Check: DB populated, JSON parsed, cost < 1$, corpus hash frozen after p1_rank
# (status goes from 'loading' to 'running_frozen').
# In a dev run without steering, p4_predict, p4_score and p4_qualitative are SKIPPED by default
# (causal_scoring.run_in_pipeline=false). La metric causale primary (deterministic,
# p4_score = causal_scorer) will be tested only AFTER implementation de steer_feature(), of the
# observation classifiers and de causal_scorer._load_pairs().

# ── 6. Pilot run (40 features — calibration) ────────────────
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Analyze : cost real, coverage, classifier precision, JSON validity
# Adjust thresholds or prompts if needed
# DECLARE any adjustment as calibration in the paper

# ── 7. Full-run budget estimate ────────────────────────
python -c "
import sqlite3
conn = sqlite3.connect('db/features.db')
cost = conn.execute(
    'SELECT total_cost_usd FROM runs ORDER BY started_at DESC LIMIT 1'
).fetchone()[0]
n_pilot = 40; n_full = 500; factor = 3.0
estimate = cost * (n_full / n_pilot) * factor
print(f'Cost pilot : {cost:.2f}\$')
print(f'Estimation full run : {estimate:.1f}\$')
"
# Update budget.max_cost_usd in run_v1.yaml accordingly

# ── 8. Configuration freeze ───────────────────────────────
git add -A && git commit -m "Freeze all parameters for full run v1"
python -c "
import subprocess
commit = subprocess.check_output(
    ['git','rev-parse','HEAD'], text=True
).strip()
print(f'Add in run_v1.yaml : git_commit: {commit}')
"
# Update run_v1.yaml with the commit exact

# ── 9. Full frozen run ───────────────────────────────────────
python orchestrator.py --config configs/run_v1.yaml
# No intervention during execution

# ── 10. Resume after crash (if necessary) ──────────────────
# ONLY if code, prompts, and config have NOT changed
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"
python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <run_id_interrompu>
# If integrity verification fails → create a new run with a new commit
```

---

## 12. Role of Claude Code

Claude Code intervient **only en dehors of the full frozen run** :

**Always allowed :**
- Write and debug agents, classifiers, and utilities
- Generate classifier calibration files
- Analyze the intermediate results of the pilot run
- Produire of the rapports lisibles depuis the base SQLite
- Suggest corrections if a phase of the dev run or pilot run fails
- Implement `steerer.py` once model access has been validated

**Interdit during the full frozen run :**
- Modifier the moindre file de code, prompt or config
- Intervenir in l'orchestrateur processing of execution
- Interpret errors and propose automatic fixes
- Relancer a phase failed without validation humaine explherete

---

## 13. Changelog v4 → v5

**Parser (§4) — critical corrections.**
- Rewrote `parse_word` using **hyphen segmentation** instead of positional substring parsing. The v4 approach did not reliably detect infixes in forms such as `root-ant-o` and failed on `mal-o` / `ne-a`.
- Completed `RESERVED_TOKENS` with `iĝ`; added hyphenless token sets (`PREFIX_TOKENS`, `INFIX_TOKENS`, `SUFFIX_TOKENS`) used by the segmentation algorithm.
- Split free-root validation into `is_valid_root` (root valid in the current parsing state) and `can_register_new_free_root` (eligibility to register a new free root). `mal` and `ne` are valid predefined roots, but cannot be re-registered as new free roots.
- Updated tests: imports updated, `test_examples_from_paper` added, and `TestValidateFreeRoot` renamed to `TestRootValidation`.

**Causal validation and steering (§7, config).**
- Default validation model changed to an **open-weight proxy model** with public SAEs. Causal claims are limited to this proxy unless direct production-model activation access is obtained.
- Primary steering magnitude is normalized per feature (`activation_p99`), while the historical absolute +5 magnitude is kept only as a secondary condition.
- Steering targets the feature's own layer, not a global layer.
- OOD detection is based on activation statistics (`activation_p99`, `activation_mean`, `activation_std`), not decoder norm.
- `steering_results` records before/after text, before/after target activations, achieved delta, OOD flag, layer, and token position.

**Statistical and methodological changes.**
- The run is described as **frozen and auditable**, not strictly deterministic: LLM outputs remain stochastic, but code/config/prompts/corpus/lexicon are frozen and verified by hashes.
- Shared-set comparison is defined for MorphoRepr vs NL vs Semantic Regexes.
- Bootstrap, confidence intervals, root Jaccard, human audit, and shuffled control are specified more explicitly.

**Batch API and reproducibility.**
- Added batch tracking for crash-safe resume.
- Added budget guardrails and cost accounting.
- Added full SHA256 prompt hashing and canonical corpus/lexicon hashing.
- Made the Anthropic client lazy so unit tests can import modules without an API key.

---

## 14. Changelog v5 → v6

This version responds to a second critical review and aligns the protocol with article v0.28.

**Causal methodology (P0).**
- The primary metric is now **deterministic**: `p4_judge` is split into `p4_score` (`causal_scorer`, deterministic comparison between predicted direction and classifier-observed direction) and `p4_qualitative` (LLM judge for qualitative analysis only).
- The primary causal score is now **global macro-F1 over all (feature, robust-property) pairs**, not per-feature macro-F1 averaged afterward.
- Bootstrap is now **clustered by feature**.
- End-to-end/global utility is reported in addition to conditional performance on the shared set.
- Semantic Regexes comparison is framed as **non-inferiority** with a pre-registered `nim_delta`; NL comparison remains superiority-based.

**Feature identity (P0).**
- Introduced robust `feature_uid` identity: `{model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}`.
- Added `model_name`, `sae_release`, `layer_index`, `hook_name`, and `feature_index` to `features`.
- `feature_index` remains informative/local; `feature_uid` is the logical identity.

**Phase 4 contract.**
- Section 7 is explicitly an implementation contract. `steer_feature()` remains a placeholder until the actual model hook is implemented.
- Added `assert_steering_ready()` as a pre-pilot guard.
- Added intervention-control declarations (`prompt_only`, `diffmean_reft`, random same-layer feature, random same-norm direction, matched activation frequency, negative steering).

**Configuration and probes.**
- Random split is sampled first, then easy/hard are sampled from the remaining pool.
- Added `probe_families`, domain-compatible probe categories, multiple generation parameters, mixed OOD criterion, and dose-response configuration.

**Classifier calibration.**
- Classifier calibration now reports `n`, class balance, confusion matrix, accuracy, macro-F1, and per-direction precision/recall.
- Calibration blocks on macro-F1, not only on accuracy.

---

## 15. Changelog v6 → v6.1

Targeted patch following the third review: complete application of `feature_uid` as the logical identity, plus DB/test corrections.

**`feature_uid` applied as logical key.**
- `agent_outputs`, `baselines`, `shuffle_controls`, and `steering_results` now use `feature_uid NOT NULL` as their logical key.
- Uniqueness constraints were moved from `feature_index` to `feature_uid` where needed.
- Joins now use `feature_uid` instead of `feature_index` where cross-layer ambiguity is possible.
- `load_features_not_processed()` and `save_agent_output()` now key resume/idempotence on `feature_uid`.
- `save_agent_output()` now requires `feature_uid` and remains non-silent on divergent duplicates.

**Hashing and DB utilities.**
- `hash_corpus_canonical()` now orders by `feature_uid`.
- Added missing `logger` in `db_utils.py`.
- `log_api_cost()` is non-silent in case of divergent cost/tokens for the same `(run, batch, phase, agent)`.

**Shuffled control.**
- `shuffle_id` is now based on `sha1(feature_uid)` rather than `feature_index`.
- `source_feature_uid` was added.
- Shuffled candidates are deduplicated by `feature_uid`.

**Tests.**
- Added integration tests proving that two layers may share the same `feature_index` without collision.
- Added tests for divergent duplicate agent outputs, corpus hash stability, shuffle uniqueness, and global causal macro-F1.

---

## 16. Changelog v6.1 → v6.2

Targeted patch following the fourth review: removal of the last place where two features from different layers could be confused, namely Batch API `custom_id`.

**Batch API `custom_id`.**
- Added `feature_custom_id(f)`: `feature_{feature_index}_{sha1(feature_uid)[:12]}`.
- `feature_index` remains present for debug readability; uniqueness comes from `feature_uid`.
- Added `build_custom_id_map(features)`.
- Added tests verifying that `custom_id`s remain unique when `feature_index` repeats across layers.

**Phase 4 guards.**
- Added `steering.run_in_pipeline: false` so a plumbing dev run can proceed without implemented steering.
- Added guards around `p4_steer` and `p4_controls`.

**Steering schema.**
- Added idempotence constraint on `steering_results` for the primary relative-magnitude mode.
- Added `feature_uid` to `user_study_results`.

**Probe wiring.**
- `steerer.run()` now wires probe families and multiple-generation parameters conceptually, while still remaining a contract until `steer_feature()` is implemented.

---

## 17. Changelog v6.2 → v6.3

Targeted patch following the fifth review: executable pipeline outside steering, persistent `custom_id → feature_uid` mapping, stronger steering idempotence, probe categories, controlled volume, and corpus hash frozen after loading.

**Pipeline executable outside steering/scoring.**
- Added `causal_scoring.run_in_pipeline: false`.
- `p4_predict`, `p4_score`, and `p4_qualitative` are now guarded and skipped by default until causal scoring is implemented.

**Persistent batch mapping.**
- Added `batch_items(batch_id, custom_id, feature_uid, feature_index)`.
- Added `save_batch_items()`, `load_batch_item_map()`, and `build_batch_item_rows(features)`.
- `submit_and_poll_batch()` enriches batch results with persisted `feature_uid` / `feature_index`.

**Steering idempotence and audit.**
- Added `magnitude_key`, stable in both relative and absolute modes (`rel:{x}` / `abs:{x}`).
- Added `steering_duplicate_attempts` to log divergent duplicate steering attempts.

**Probe design and volume.**
- Added `probe_category` to `steering_results`.
- Domain probes are secondary by default; neutral probes remain primary.
- `generations_per_probe` is set to 1 for deterministic greedy primary decoding.
- Added `stochastic_decoding` as a secondary-analysis option.
- Added `run_mode` to use smaller probe counts in dev/pilot.

**Corpus freezing.**
- `runs.corpus_hash` is initially NULL.
- Added `p1_freeze_corpus` after `p1_load` / `p1_rank`.
- `verify_resume_integrity()` only checks corpus hash once it has been frozen.

---

## 18. Changelog v6.3 → v6.4

Finishing patch following the sixth review. No new methodological functionality; this hardens Batch resume and auditability. v6.4 is considered solid for a plumbing dev run outside Phase 4.

**Atomic batch registration.**
- Added `register_batch_with_items()`, writing both `batches` and `batch_items` in one transaction.
- On resume, an empty persisted mapping for a feature-level batch now raises `RuntimeError`.
- Missing `custom_id` entries in `batch_items` also raise `RuntimeError`.

**Feature-level batch guard.**
- `submit_and_poll_batch(..., requires_feature_mapping=True)` now raises `ValueError` if `batch_items` is missing.
- Non-feature batches must explicitly pass `requires_feature_mapping=False`.

**Run status.**
- `initialize_run()` now starts with `status='loading'`.
- `freeze_corpus_hash()` switches to `status='running_frozen'` after freezing `corpus_hash`.

**Audit enrichment.**
- `steering_duplicate_attempts` now stores attempted text, activations, achieved delta, and OOD flag.

**CLI guard.**
- `run_pipeline()` warns when `--n-features` is used with `run_mode=full`.

---

## 19. Changelog v6.4 → v6.4.1

Micro-patch following the seventh review. No schema change and no new methodological functionality.

**Pre-check `requests` ↔ `batch_items` before submission.**
- `submit_and_poll_batch()` now compares the set of request `custom_id`s with the set of `batch_items` `custom_id`s before any submission, hence before any billing.
- If the sets differ, it raises `ValueError` with explicit `missing` and `extra` lists.
- Added `test_submit_rejects_inconsistent_batch_items`.

**`assert_steering_ready` clarified as a PRE-PILOT Phase 4 guard.**
- Section 11.4 bis now states that this guard is only to be run before a pilot/full run with steering enabled.
- It is expected to fail while `steer_feature()` is a placeholder.
- It must not block a plumbing dev run outside Phase 4.

**Unchanged caveats.**
- `steer_feature()`, `run_intervention_controls()`, and `causal_scorer._load_pairs()` remain implementation contracts (`NotImplementedError`), guarded by `run_in_pipeline` flags.
- The protocol is now stable enough; the next real task is implementation of `steer_feature()` and `causal_scorer._load_pairs()`.


---

## 20. Changelog v6.4.1 → v6.5

Added an **open-model reproducibility layer** (Rule 11). This touches the SQLite schema, hence the minor version bump to v6.5. Compatibility with v6.4.1 is preserved: `batch_items` remains intact, `AnthropicProvider` is preserved, Phase 4 remains disabled by default, and `steer_feature()`, `run_intervention_controls()`, and `causal_scorer._load_pairs()` remain contracts.

**Open-model policy.** Added Tier A / Tier B / Tier C provider classes; primary claims must be supported by Tier A/B models, while Anthropic and other proprietary API models are secondary comparison conditions.

**Configuration.** Added `model_providers.primary_reproducible`, `secondary_proprietary`, and `optional_cross_model_replication`, with model revision, tokenizer revision, hashes, precision, quantization and inference-container hash fields.

**Schema.** Added the `model_runs` table and propagated `model_run_id` conceptually to outputs, metrics, baselines, API usage and model-specific reporting.

**Inference abstraction.** Added the `ModelProvider` interface and provider implementations for Anthropic, vLLM, Transformers and llama.cpp backends, with lazy imports.

**Reporting.** Added per-model/per-tier reporting, cross-model robustness classification, and guards preventing a Tier C model from supporting a primary claim.

---

## 21. Changelog v6.5 → v6.5.1

Corrective patch for the open-model reproducibility layer. The policy was sound, but `model_run_id` had been added to the schema without being fully propagated in several functions.

**Full `model_run_id` propagation.** Added/required `model_run_id` in `batches`, `batch_items`, `agent_outputs`, `baselines`, `api_usage`, and `steering_results`. Introduced an explicit deterministic legacy `model_run` instead of relying on NULLs.

**Batch resume and accounting.** Batch recovery is filtered by `model_run_id`; `batch_items` persists `model_run_id`; API costs are logged per model; uniqueness constraints include model identity where needed.

**Legacy Anthropic wrapper.** `api_utils.py` is explicitly marked as a legacy Anthropic Batch API wrapper for the Tier C secondary condition only. Agents producing scientific outputs are expected to go through `ModelProvider`.

**Paper markers.** The paper was cleaned to v0.29, with residual v0.28 markers removed.

---

## 22. Changelog v6.5.1 → v6.5.2

Final propagation patch for multi-model execution. No schema change.

**`load_features_not_processed` made model-aware.** The function now filters already-produced outputs by `(run_id, model_run_id, agent_name, run_number)`. Without this filter, a second model would incorrectly see features processed by the first model as already done.

**`batch_items.model_run_id` fallback fixed.** Replaced `dict.get("model_run_id", model_run_id)` with `dict.get("model_run_id") or model_run_id`, so an item carrying `None` no longer inserts NULL into a NOT NULL column.

**Legacy batch resume fixed.** `get_unconsumed_batch(model_run_id=None)` now resolves the explicit legacy model run before filtering.

**Resume restores model-run IDs.** Added `restore_model_run_ids(run_id, config)` to rebuild `config["_runtime"]["model_run_ids"]` from the database on `--resume`, preventing later phases from falling back to the legacy model when a primary model already exists.

**YAML description.** Updated to `Full frozen run MorphoRepr v0.29 / procedure v6.5.2 — 500 features` in that patch, later bumped to v6.6.1.

---

## 23. Changelog v6.5.2 → v6.5.3

Patch for the **last multi-model leak in Phase 4**. No schema change.

**`steerer.run()` made strictly model-aware.** The function already resolved the primary model's `model_run_id`, but the query loading `encoder` outputs from `agent_outputs` did not filter on it. The same `feature_uid`, annotated by several models, could therefore have caused a secondary or legacy annotation to be steered under the primary `model_run_id`. The loading logic is now extracted into `_load_encoded_random_features(run_id, model_run_id)`, whose query adds `AND ao.model_run_id = ?` with parameters `(run_id, model_run_id)`; `run()` calls this helper. Primary steering therefore uses only the primary model's annotations.

**Test.** `test_steering_charge_uniquement_le_modele_primaire`: two `model_run_id`s in the same run, two `encoder` outputs for the same `feature_uid` with different expressions; the steering loader retrieves only the primary annotation, and symmetrically the secondary model sees only its own. No secondary or legacy output is steerable under the primary `model_run_id`.

**Documentation residues.** Integrated README: “Test procedure: v6.6.1”. The v6.5.1 changelog is framed historically, and the paper now refers to “test procedure v6.5.x / v6.6.x (≥ v6.6.1)”.

**Phase 4 remains contractual.** `steer_feature()`, `run_intervention_controls()` and `causal_scorer._load_pairs()` remain **contracts** (`NotImplementedError`) behind `run_in_pipeline` flags. This patch makes the *loading* side of steering model-aware, but Phase 4 is not executable until `steer_feature()` is implemented.


---

## 24. Changelog v6.5.3 → v6.6.0

Version 6.6.0 turns `steer_feature()` from a pure contract into a real implementation for the open-weight proxy path. This is a functional extension, not a schema change. The SQLite schema remains unchanged from v6.5.3, and the multi-model reproducibility layer (`model_runs`, `model_run_id`, model-aware batch recovery, and model-aware Phase 4 loading) is preserved.

Main changes:

- `steer_feature()` is implemented for the TransformerLens + SAE Lens proxy path when `proxy_model.enabled=true`.
- The primary intervention space is `residual_add_decoder`: the hook adds `magnitude * sae.W_dec[feature_index]` to the residual stream at the selected token positions.
- For every probe, the function now returns real `text_before`, `text_after`, `activation_before`, `activation_after`, `achieved_delta`, and `ood_flag`.
- `text_before` and `text_after` are generated continuations, not placeholders.
- `activation_before/after` are measured through a forward pass, residual capture at the SAE hook, SAE encoding, and feature-activation aggregation.
- `achieved_delta = activation_after - activation_before` is reported because adding a decoder direction does not guarantee a target latent-activation increase.
- The production/nnsight path remains explicit `NotImplementedError`.
- `sae_latent_clamp` remains explicit `NotImplementedError`, with the intended future implementation described but not simulated.
- Phase 4 remains disabled by default (`steering.run_in_pipeline=false`).
- `run_intervention_controls()` and `causal_scorer._load_pairs()` remain explicit contracts.
- No causal scientific result is claimed in this version.

New helper functions in `agents/steerer.py`:

- `_get_hook_name_from_sae()`
- `_tokens_from_prompt()`
- `_position_indices()`
- `_selected_token_positions()`
- `_aggregate_feature_activation()`
- `_make_residual_add_decoder_hook()`
- `_measure_feature_activation()`
- `_generate_text()`

Tests added in `tests/test_steer_feature.py`:

- required fields and non-placeholder outputs;
- achieved-delta computation;
- OOD flagging;
- explicit `NotImplementedError` for unsupported modes;
- token-position selection (`all`, `last`, `content_only`);
- residual hook behavior;
- `assert_steering_ready()` with mocks;
- optional slow integration test guarded by `MORPHOREPR_RUN_SLOW_STEERING=1`.

## 25. Changelog v6.6.0 → v6.6.1

Version 6.6.1 hardens the `steer_feature()` implementation without changing the schema or the scientific claims of paper v0.29. It is a robustness and documentation cleanup release for the open-weight proxy steering path.

Main changes:

- `_generate_text()` no longer assumes a single TransformerLens `model.generate` signature.
- Generation keyword arguments are filtered through `inspect.signature`; unsupported kwargs such as `do_sample`, `top_p`, or `verbose` are not passed if the installed model API does not accept them.
- Greedy decoding semantics are preserved while passing only supported kwargs.
- The semantics of `activation_before` and `activation_after` are clarified: in v6.6.1 they are measured on the probe context, not on the generated continuation.
- `feature_index`, `W_dec`, residual tensors, and SAE output shapes are validated with explicit errors.
- `sae.encode()` methods returning tuples are supported by taking the first returned element.
- The residual dtype is preserved when applying `magnitude * W_dec[feature_index]`.
- Hook tests are strengthened so the intervention is actually invoked during generation.
- Tests are added or extended for dtype preservation, unsupported generation kwargs, shape errors, tuple encode outputs, and opt-in slow integration.
- The steering section is now described as an open-weight proxy implementation with remaining contracts, rather than as a pure implementation contract.
- v6.6.0-specific wording is replaced by the broader v6.6.x objective.
- The integrated README points to paper v0.29 and test procedure v6.8.0.

Still not implemented:

- `sae_latent_clamp`;
- nnsight / production-model steering;
- `run_intervention_controls()`;
- `causal_scorer._load_pairs()`.

Acceptance criteria for v6.6.1:

- unit tests pass;
- no schema change is introduced;
- the multi-model layer remains intact;
- Phase 4 is not automatically enabled;
- no phrase claims that causal validation is complete;
- no scientific claim in paper v0.29 is changed.

Recommended test commands:

```bash
pip install -r requirements.txt
pytest tests/test_steer_feature.py -v

# Optional real integration test; may download a small model and public SAE:
MORPHOREPR_RUN_SLOW_STEERING=1 pytest tests/test_steer_feature.py -v -k slow
```

## 26. Changelog v6.6.1 → v6.7.0

Functional extension: **real implementation of `causal_scorer._load_pairs()` for the deterministic primary score**. No SQLite schema change. The multi-model layer and the v6.6.1 `steer_feature()` implementation remain unchanged.

**`_load_pairs()` implemented for `method="morphorepr"`.** The function now reads predictor outputs from `agent_outputs`, normalizes predicted directions, reads steering observations from `steering_results`, applies deterministic robust-property classifiers to `text_before` / `text_after`, and assembles `(feature_uid, robust property)` prediction/observation pairs for the primary global macro-F1. It is strictly filtered by `run_id`, `model_run_id`, `split`, primary `magnitude_key`, primary probe family, and `intervention_space`.

**No LLM judge in the primary metric.** The observed directions are produced by pre-registered deterministic classifiers (`negation_presence`, `tense`, `code_presence`, `conditional_modality`). `negative_valence` remains semi-robust and is excluded from the primary score.

**Prediction normalization.** `_extract_predicted_directions()` accepts three explicit formats: `predictions[]`, `properties: {prop: direction}`, and `properties: {prop: {direction: ...}}`. Direction aliases such as `increase`, `up`, `decrease`, `down`, `no_change`, and `unchanged` are normalized. Ambiguous directions such as `UNKNOWN`, `null`, or an empty string are rejected rather than silently mapped to `NO_CHANGE`.

**Observation assembly.** `_observe_property_direction()` collects valid `text_before` / `text_after` pairs and applies the classifier. A pair is created only if both prediction and observation exist for a robust property. Missing predictions, missing steering observations, and empty final pair sets raise explicit errors instead of returning a silent empty list.

**OOD, split, model, and intervention-space safety.** OOD rows are excluded from the primary metric when `exclude_ood_from_primary=true`. The query is split-aware and model-aware, and now also filters `sr.intervention_space = config["steering"].get("intervention_space", "residual_add_decoder")`, avoiding future contamination if additional intervention spaces are implemented later.

**`run()` updated.** `run()` resolves the primary `model_run_id`, computes MorphoRepr global macro-F1 and a feature-clustered bootstrap, and writes `metrics.model_run_id` for model-specific scores. `NULL` remains reserved for cross-model aggregate metrics.

**Baseline policy: Option A.** Baseline comparisons are disabled by default through `causal_scoring.run_baseline_comparisons=false`. The MorphoRepr score is written alone, without superiority or non-inferiority verdict. If baseline comparisons are explicitly enabled without baseline prediction outputs, `_load_pairs(base)` fails loudly; no fake baseline predictions are produced.

**Tests added/extended.** `tests/test_causal_scorer.py` covers prediction extraction, direction normalization, rejection of invalid directions, deterministic observation, `_primary_magnitude_key()`, OOD filtering, model-aware and split-aware selection, intervention-space filtering, missing predictor/steering errors, final pair assembly, and a minimal `run()` writing `causal_macro_f1_global` with `metrics.model_run_id` populated while skipping baselines.

**Remaining limits.** Baseline predictions are not wired yet; no superiority/non-inferiority verdict is produced. `run_intervention_controls()` remains a contract. `causal_scoring.run_in_pipeline=false` remains the default. A full scientific causal validation is not claimed, and paper v0.29 scientific claims remain unchanged.

Recommended test commands:

```bash
pytest tests/test_causal_scorer.py -v
pytest tests/test_steer_feature.py tests/test_causal_scorer.py -v

# Optional dev causal integration test if implemented:
MORPHOREPR_RUN_DEV_CAUSAL=1 pytest tests/test_pipeline_e2e.py -v -k causal
```

## Current v6.8.0 status summary

`steer_feature()` is implemented for the open-weight proxy path, and `causal_scorer._load_pairs()` is implemented for a minimal MorphoRepr causal dev score. The pipeline still does not claim full causal validation: baseline comparisons remain off by default, `run_intervention_controls()` is not implemented, and Phase 4 remains disabled in the default pipeline configuration. The next major tasks are wiring baseline prediction outputs (Option B) and implementing intervention controls.


---

## 27. Changelog v6.7.0 → v6.8.0

**Baseline prediction Option B.** Adds baseline prediction outputs for `nl_labels` and `semantic_regex` through `agents/baseline_predictor.py`. The module reads baseline annotations from the `baselines` table and writes canonical direction predictions to `agent_outputs` under `predictor_nl_labels` and `predictor_semantic_regex`.

**Separate baseline prompts.** Adds `prompts/predictor_nl_labels_v1.txt` and `prompts/predictor_semantic_regex_v1.txt`. These prompts do not use MorphoRepr terminology. The NL baseline is scored from natural-language labels; the Semantic Regex baseline is scored from the regex annotation itself.

**Paired comparisons are now runnable in controlled dev runs.** With `baseline_predictions.enabled=true` followed by `causal_scoring.run_baseline_comparisons=true`, the scorer can compute the MorphoRepr score, the baseline scores, paired differences, coverage, superiority vs NL labels and non-inferiority vs Semantic Regexes.

**No fake baseline predictions.** Missing annotations or missing prediction outputs trigger `RuntimeError` in strict mode. In non-strict mode, a baseline may be explicitly skipped, but no verdict is produced. There is never a false `pass` or `fail` for an absent baseline.

**Still not wired.** `keyword_tags` and `morphorepr_shuffled` remain explicitly unsupported in the baseline-prediction path. `run_intervention_controls()` remains a contract.

**Default safety.** `baseline_predictions.enabled=false`, `causal_scoring.run_baseline_comparisons=false`, and `causal_scoring.run_in_pipeline=false` remain the defaults. No full causal validation and no published scientific result are claimed in v6.8.0. Paper v0.29 scientific claims remain unchanged.
