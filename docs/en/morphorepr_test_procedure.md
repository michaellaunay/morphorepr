# MorphoRepr — Complete Test Procedure (v5)
## Robust experimental infrastructure for reproducible evaluation

*Version 5 — June 2026. Consistent with article v0.27. Changes relative to v4 are listed in Section 13 (changelog).*

---

## Guiding principles

**Rule 1 — Separation of roles; frozen and auditable run**
Claude Code is used only for development, debugging, and supervision. The final experimental run is driven exclusively by `python orchestrator.py --config configs/run_v1.yaml`. The run is **frozen and auditable** rather than strictly deterministic: code, configuration, prompts, corpus, and lexicon are pinned and verified by hashes, and all raw agent outputs are archived. However, LLM calls are **stochastic** (necessarily so for the two independent annotation-consistency runs); the run is therefore *re-analyzable* from archived outputs, but not *regenerable* bit-for-bit. No code modification and no untracked agentic intervention are allowed during execution.

**Rule 2 — Three execution levels**

| Mode | n features | Objective | Results |
|------|-----------:|-----------|---------|
| Dev run | 5 | Plumbing, DB, parsing, batch calls, classifiers | Non-scientific |
| Pilot run | 30–50 | Prompt calibration, thresholds, classifiers | Exploratory |
| Full frozen run | 500 | Publication | Frozen before launch |

If thresholds or prompts are adjusted after observing pilot-run results, this must be explicitly declared as calibration in the paper.

**Rule 3 — Full freeze before full run**
The Git commit is fixed and verified; the config is hashed; prompts are hashed with full SHA256; the corpus is hashed; the lexicon is hashed; the sampling policy is documented. In case of `--resume`, all these values are re-verified before resumption.

**Rule 4 — No resumption after code changes**
If code is modified after a phase failure, create a new `run_id` with a new Git commit. Never resume a run with a commit different from the one recorded at initialization.

**Rule 5 — Validation model: open-weight proxy by default**
Because complete experimental access to the activations of a production model (controlled steering with before/after generation) is not guaranteed through public interfaces, causal validation runs **by default on an open-weight proxy model with public SAEs** (e.g. GPT-2, Pythia, or Mistral through `sae_lens`). In that case: (a) the whole pipeline (Phases 1–5) runs on the proxy SAEs; (b) all causal conclusions are limited to the proxy model; (c) Claude 3 Sonnet / Neuronpedia examples remain illustrative only; (d) this must be explicitly stated in the Methods section of the paper. If direct activation access to a production model is obtained, set `proxy_model.enabled=false` and provide the corresponding access paths.

**Rule 6 — Feature-normalized steering, at the feature’s own layer**
The primary steering magnitude is **normalized per feature** (a multiple of the 99th percentile of the feature activation, column `activation_p99`), making it comparable across features and layers; the historical absolute magnitude (+5) is retained as a secondary condition. Steering targets the **feature’s own layer** (column `layer`), not a global layer. Out-of-distribution instances (`ood_flag=1`) are **excluded from the primary metric** and reported separately.

**Rule 7 — Comparison on a shared feature set**
The causal-validity head-to-head comparison (MorphoRepr vs NL labels vs Semantic Regexes) is computed **on the same feature set**: the intersection of features covered by MorphoRepr (confidence ≥ 0.5). This avoids giving MorphoRepr an advantage by evaluating it only on its clearest features. Baselines are also reported on the full set for transparency. The primary causal-validity score is **macro-F1** over the directions `{increase, decrease, no_change}`, and the go/no-go criterion is a **paired difference** whose 95% bootstrap CI excludes 0.

---

## 1. Project structure

```text
morphorepr-pipeline/
├── CLAUDE.md                        ← Claude Code instructions (development/supervision only)
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
│   ├── morphorepr_parser.py         ← single parser for all morphemic metrics
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
│   └── probe_sentences.txt          ← 20 neutral probe sentences in English
├── logs/
└── checkpoints/
```

---

## 2. Frozen configuration file

```yaml
# configs/run_v1.yaml

run_id_prefix: "morphorepr_v1"
description: "Full frozen run MorphoRepr v0.27 — 500 features"

# Reproducibility
git_commit: "FILL_BEFORE_LAUNCH"    # checked against the actual Git HEAD at init
allow_unpinned_commit: false        # frozen run: the commit MUST be pinned (see orchestrator)
lexicon_version: "v1.0"
corpus_frozen: true

# Sampling policy
# temperature is NOT sent to the API by default to avoid HTTP 400 errors
# on recent models rejecting non-default sampling parameters.
# Documented here for the paper; not transmitted unless use_temperature: true.
sampling:
  use_temperature: false
  temperature: null

# Models (exact Anthropic API identifiers)
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

# Corpus splits (DISJOINT: random sampled from the complement of easy ∪ hard)
splits:
  easy:   {n: 200, min_interp_score: 0.7}
  random: {n: 200, filter: "uniform", disjoint_from_others: true}
  hard:   {n: 100, max_interp_score: 0.5}
primary_split: "random"              # all go/no-go thresholds are evaluated here

# Clustering (Phase 2) — fixed seeds for reproducible lexicon induction
clustering:
  k: 20
  kmeans_random_state: 42
  umap_random_state: 42

# SAE steering
steering:
  # PRIMARY magnitude normalized per feature: multiple of the 99th percentile (activation_p99).
  # The absolute +5 magnitude (Anthropic, 2024) is retained as a SECONDARY/historical condition.
  magnitude_mode: "p99_relative"     # "p99_relative" (primary) | "absolute" (secondary)
  primary_magnitude_rel: 1.0         # 1.0 × feature activation_p99
  dose_response_rel: [0.0, 0.5, 1.0, 2.0]   # dose-response curve (multiples of p99)
  legacy_absolute_magnitude: 5       # secondary historical condition
  n_probe_sentences: 20
  n_subsample_for_curve: 50          # seeded subsample for the dose-response curve
  layer_mode: "per_feature"          # target the feature’s own layer (column `layer`)
  intervention_space: "residual"     # "residual"|"sae_latent"
  token_position: "all"              # "all"|"last"|"content_only"
  # OOD based on activation_p99 from the features table (NOT W_dec norm)
  ood_threshold: 3.0
  exclude_ood_from_primary: true     # instances with ood_flag=1 are excluded from the primary metric

# Validation model — open-weight proxy BY DEFAULT (Rule 5).
# Set enabled=false only if direct activation access to a production model is obtained
# and provide access paths in agents/steerer.py.
proxy_model:
  enabled: true
  name: "EleutherAI/pythia-6.9b"
  sae_release: "pythia-6.9b-res-jb"

# ANNOTATION baselines (compared on a shared feature set — Rule 7)
baselines:
  - nl_labels
  - semantic_regex        # OFFICIAL implementation of Boggust et al. (apple/ml-semantic-regex)
  - keyword_tags
  - morphorepr_shuffled

# INTERVENTION controls (Phase 4) — beyond the shuffled-annotation control
intervention_controls:
  random_feature_same_layer: true    # random SAE feature from the same layer
  random_direction_same_norm: true   # random direction with the same norm
  matched_activation_freq: true      # feature with comparable activation frequency
  negative_steering: true            # -magnitude when semantically relevant
  prompt_only: true                  # label in prompt, without steering
  diffmean_reft: true                # supervised baselines DiffMean / ReFT (see AxBench)

# Shuffled control
shuffle_control:
  n_repeats: 10
  within_split: true
  max_term_diff: 1
  preserve_coefficients: true
  # Most shuffles are scored by classifiers (not the LLM judge) to bound cost;
  # but a FRACTION goes through the SAME predictor+judge path as the treatment to
  # calibrate comparability (otherwise the null is not comparable to the main metric).
  use_llm_judge: false
  llm_judge_calibration_fraction: 0.2
  # Evaluated on the random split only; 10 repeats are aggregated before CI computation.
  evaluation_split: "random"

# Budget
budget:
  max_cost_usd: 150.0                # update after pilot-run estimate
  alert_at_usd: 75.0
  abort_on_exceed: true

# Go/no-go thresholds (random split only)
thresholds:
  coverage_easy_min: 0.65
  coverage_random_min: 0.45
  coverage_hard_min: 0.20
  fidelity_auc_min: 0.60
  causal_validity_floor: 0.50        # macro-F1 floor; the main criterion is a
                                     # PAIRED DIFFERENCE vs baselines whose 95% CI excludes 0
  root_jaccard_min: 0.60
  human_audit_jaccard_min: 0.60
  free_root_rate_max: 5.0

# Statistical methodology
stats:
  causal_score: "macro_f1"           # macro-F1 over {increase,decrease,no_change}, robust props,
                                     # computed per feature then averaged
  comparison: "paired"               # paired difference per feature (same features)
  bootstrap_resamples: 10000
  stratify_by_split: true
  multiple_comparison_primary: "holm"            # Holm-Bonferroni (primary comparisons)
  multiple_comparison_exploratory: "benjamini_hochberg"  # FDR (exploratory analyses)
  prediction_failure_policy: "zero_for_property"  # prediction failure => zero score for the property

# Anthropic Batch API — most batches finish <1h, available at completion
# or after 24h; they expire at 24h. 2h was too short (possible artificial failure).
batch:
  poll_interval_seconds: 60
  max_wait_seconds: 86400

# Reproducibility seed (subsample selection, shuffled control, clustering)
seed: 42
```

---

## 3. Complete SQLite schema (v5)

```sql
-- db/schema.sql — Version 4, never modify after the full run

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Run traceability
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    git_commit      TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    prompt_hashes   TEXT NOT NULL,    -- JSON {agent: full_sha256}
    lexicon_version TEXT NOT NULL,
    lexicon_hash    TEXT NOT NULL,    -- SHA256 of sorted canonical JSON export
    -- corpus_hash covers only the features table (input data), NOT results added during the run.
    -- The DB legitimately grows during execution.
    corpus_hash     TEXT NOT NULL,    -- SHA256 of sorted canonical CSV export
    models_json     TEXT NOT NULL,
    use_temperature INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,             -- NULL if use_temperature=0
    seed            INTEGER,
    proxy_model     TEXT,             -- NULL if primary model is used
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT DEFAULT 'running',
    last_phase      TEXT,
    total_cost_usd  REAL DEFAULT 0.0
);

-- Batch tracking (crash resumption)
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

-- Versioned prompts
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id   TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    version     TEXT NOT NULL,
    content     TEXT NOT NULL,
    sha256      TEXT NOT NULL,        -- full SHA256, 64 hex characters
    created_at  TEXT NOT NULL
);

-- Feature corpus
CREATE TABLE IF NOT EXISTS features (
    feature_index   INTEGER PRIMARY KEY,
    split           TEXT NOT NULL,
    nl_description  TEXT NOT NULL,
    top_examples    TEXT NOT NULL,    -- serialized JSON array
    score_interp    REAL,
    activation_freq REAL,
    -- Activation statistics from Neuronpedia (used for OOD detection).
    -- These columns replace W_dec norm, which is a different quantity.
    activation_p99  REAL,
    activation_mean REAL,
    activation_std  REAL,
    layer           TEXT,
    sae_version     TEXT,
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL
);

-- Raw agent outputs (immutable)
CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
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
    -- Prevent duplicates during partial resumption or double execution.
    -- Combined with INSERT OR IGNORE in save_agent_output(), this makes persistence idempotent.
    UNIQUE(run_id, feature_index, agent_name, run_number)
);

-- Computed metrics
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
    baseline        TEXT,             -- NULL = MorphoRepr; otherwise baseline name
    computed_at     TEXT NOT NULL
);

-- Baselines
CREATE TABLE IF NOT EXISTS baselines (
    baseline_id     TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
    baseline_name   TEXT NOT NULL,
    annotation_run1 TEXT,
    annotation_run2 TEXT,
    fidelity_auc    REAL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL
);

-- Shuffled control
CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
    shuffle_number  INTEGER NOT NULL,
    source_feature  INTEGER NOT NULL REFERENCES features(feature_index),
    annotation      TEXT NOT NULL,
    causal_score    REAL,
    causal_outcome  TEXT,
    -- 'classifier' (most shuffles) | 'llm_judge' (calibration fraction, Rule/Section 4)
    scored_by       TEXT DEFAULT 'classifier',
    created_at      TEXT NOT NULL,
    UNIQUE(run_id, feature_index, shuffle_number)
);

-- Steering results — before/after text and activations
CREATE TABLE IF NOT EXISTS steering_results (
    result_id           TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    feature_index       INTEGER NOT NULL,
    magnitude           REAL NOT NULL,
    -- magnitude_rel: multiple of activation_p99 applied (primary "p99_relative" mode);
    -- NULL in "absolute" mode. magnitude remains the actual absolute value applied.
    magnitude_rel       REAL,
    probe_id            INTEGER NOT NULL,
    text_before         TEXT NOT NULL,
    text_after          TEXT,
    layer               TEXT,
    token_position      TEXT,
    activation_before   REAL,
    activation_after    REAL,
    -- ood_flag: 1 if abs(activation_after) > activation_p99 * ood_threshold.
    -- activation_p99 comes from the features table, NOT from W_dec norm.
    ood_flag            INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL
);

-- API cost tracking
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
    timestamp       TEXT NOT NULL
);

-- Lexicon versions
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

-- User-study results (outside the pipeline; stored here for traceability)
CREATE TABLE IF NOT EXISTS user_study_results (
    result_id           TEXT PRIMARY KEY,
    participant_id      TEXT NOT NULL,
    condition           TEXT NOT NULL,    -- 'morphorepr'|'semantic_regex'|'nl'
    feature_index       INTEGER,
    task_id             TEXT NOT NULL,
    response            TEXT,
    accuracy            REAL,
    response_time_ms    INTEGER,
    cognitive_load_score REAL,            -- NASA-TLX composite score
    preference_rank     INTEGER,
    created_at          TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ao_feature  ON agent_outputs(feature_index, agent_name, run_number);
CREATE INDEX IF NOT EXISTS idx_metrics     ON metrics(run_id, split, metric_name);
CREATE INDEX IF NOT EXISTS idx_api_phase   ON api_usage(run_id, phase);
CREATE INDEX IF NOT EXISTS idx_steering    ON steering_results(run_id, feature_index, magnitude);
CREATE INDEX IF NOT EXISTS idx_batches_run ON batches(run_id, phase, agent_name, run_number);
```

---

## 4. Single MorphoRepr parser

The parser is the single source of truth for all morphemic metrics. Version 5 replaces the brittle substring-based positional parser with segmentation on hyphens, fixing the v4 failures on `mal-o`, `ne-a`, and infixed forms such as `soc-ant-o`.

Core rules:

1. `parse_expression()` removes the coefficient before `·`.
2. `parse_word()` splits the word on `-`.
3. The last segment must be a known suffix.
4. Prefixes are read at the beginning, but never consume the last available body segment, which becomes the root.
5. The first remaining non-prefix segment is the root; subsequent segments are infixes.
6. Predefined roots, registered free roots, and well-formed free roots are syntactically valid; eligibility for registering a *new* free root is checked separately.

Important edge cases:

| Word | Expected parse |
|------|----------------|
| `mal-o` | root `mal`, suffix `-o` |
| `ne-a` | root `ne`, suffix `-a` |
| `mal-emo-a` | prefix `mal`, root `emo`, suffix `-a` |
| `soc-ant-o` | root `soc`, infix `ant`, suffix `-o` |
| `dat-ad-o` | root `dat`, infix `ad`, suffix `-o` |
| `pens-ad-is` | root `pens`, infix `ad`, suffix `-is` |
| `mal-far-int-e` | prefix `mal`, root `far`, infix `int`, suffix `-e` |

The implementation defines:

```python
parse_word(word: str, known_free_roots: Optional[set] = None) -> ParsedTerm
parse_expression(expr: str, coefficient_type: str = "confidence") -> ParsedExpression
is_valid_root(root: str, known_free_roots: Optional[set] = None) -> bool
can_register_new_free_root(root: str, known_free_roots: Optional[set] = None) -> Optional[str]
```

`mal` and `ne` are valid predefined roots but cannot be registered again as new free roots.

---

## 5. Main utilities

### 5.1 `db_utils.py`

`db_utils.py` is the only access point to `features.db`. Direct DB operations outside this module are forbidden. `DB_PATH` is configurable via `MORPHOREPR_DB_PATH` for test isolation.

Main responsibilities:

- open SQLite connections with `PRAGMA foreign_keys=ON`;
- load features by split;
- load not-yet-processed features for a given agent/run number;
- persist agent outputs idempotently with `INSERT OR IGNORE`;
- register, recover, and consume batches;
- log API costs and update cumulative run costs;
- check budget limits.

Important v5 changes:

- `json.dumps(output_json) if output_json is not None else None` prevents `{}` or `[]` from being stored as NULL;
- `UNIQUE(run_id, feature_index, agent_name, run_number)` prevents duplicate outputs;
- `save_agent_output()` is compatible with crash resumption.

### 5.2 `api_utils.py`

`api_utils.py` wraps the Anthropic Batch API with crash-safe resumption. The config is always passed explicitly; no `load_config()` call occurs inside the wrapper.

Key design points:

- lazy Anthropic client initialization so unit tests can import the module without an API key;
- temperature is added only when `sampling.use_temperature=true`;
- existing unconsumed batches are recovered instead of re-submitted;
- all text blocks returned by the API are concatenated defensively;
- `persist_fn(results)` is called before cost logging and `mark_batch_consumed()`;
- batch polling parameters are read from the config (`poll_interval_seconds`, `max_wait_seconds`);
- budget overrun raises a runtime error.

Crash-safety logic:

> If the process crashes after receiving batch results but before persistence, the batch remains `submitted`; resumption retrieves the same batch and re-persists idempotently. This avoids a new submission and therefore avoids double external spending.

### 5.3 `prompt_utils.py`

`prompt_utils.py` handles prompt loading, hashing, and prompt registration. SHA256 hashes are full 64-character hex strings, not truncated.

Main responsibilities:

- load prompt files with UTF-8 encoding;
- compute full prompt hashes;
- hash the lexicon canonically with sorted JSON keys;
- hash the corpus canonically from the sorted `features` table only;
- include column headers in the corpus hash to detect schema/order changes;
- register prompts in SQLite;
- verify unchanged prompts during resumption.

---

## 6. Output-property classifiers

### 6.1 Negation (robust)

The negation classifier combines dependency parsing (`dep_ == "neg"`) with a carefully pruned negation lexicon. Version 4 included ambiguous prefixes such as `a`, `in`, `im`, `il`, `ir`, which produced massive false positives (`about`, `after`, `information`, `important`, etc.). Version 5 keeps only weak morphological signals such as `un`, `non`, `dis`, `mis`, with low weight.

The classifier returns a normalized before/after score and a direction:

```text
INCREASE | DECREASE | NO_CHANGE
```

with a threshold of `0.02`.

### 6.2 Emotional valence (semi-robust)

The valence classifier uses `cardiffnlp/twitter-roberta-base-sentiment-latest` instead of SST-2, because SST-2 is trained on movie reviews and is poorly suited to technical or narrative text. The pipeline is configured with `top_k=None`, so the full label distribution is returned; `_neg_score()` reads the `negative` score directly instead of approximating it as `1 - top_score`.

The classifier is explicitly marked semi-robust and should be interpreted with caution on technical, ironic, or code-heavy text.

### 6.3 Classifier calibration

Classifier calibration must pass before the pilot run. The following thresholds are used:

| Property | Minimum accuracy |
|----------|-----------------:|
| Negation presence | 0.85 |
| Tense | 0.85 |
| Code presence | 0.90 |
| Conditional modality | 0.85 |
| Negative valence | 0.80 |

If any classifier fails calibration, the pilot run must not start.

---

## 7. Steering agent — full specification (v5)

Phase 4 performs SAE activation steering.

**Intervention specification:**

- Space: residual stream, after SAE reconstruction.
- Layer: the feature’s own layer (`layer` column), not a global layer.
- Token position: configurable (`all`, `last`, `content_only`).
- Amplitude: primary magnitude normalized per feature, `primary_magnitude_rel × activation_p99`; absolute +5 retained as a secondary historical condition.
- Control: magnitude 0 always run as baseline.
- Dose-response: `dose_response_rel` multiples of `p99` on a seeded subsample.
- OOD detection: `abs(activation_after) > activation_p99 × ood_threshold`; OOD instances are excluded from the primary metric.

**Model access paths to implement before the pilot run:**

1. TransformerLens for GPT-style open-weight proxy models.
2. `nnsight` if direct production-model access is available.
3. Local weights if an SAE-compatible open-weight model is available.

The proxy model is enabled by default. When proxy mode is used, the entire pipeline runs on the proxy SAEs, and Claude 3 Sonnet examples remain illustrative only.

The steering code must:

1. tokenize the probe sentence;
2. run a forward pass and record the residual activation at the target layer;
3. modify the residual by adding `magnitude * sae.W_dec[feature_index]` at the configured token positions;
4. rerun the forward pass with the modified residual;
5. decode before/after outputs;
6. measure the achieved activation for OOD verification;
7. persist `magnitude`, `magnitude_rel`, `activation_before`, `activation_after`, `ood_flag`, and the actual layer used.

The placeholder implementation intentionally raises `NotImplementedError` if `text_after` is not produced. This prevents an accidental pilot run with a fake steering implementation.

---

## 8. Shuffled MorphoRepr baseline

The shuffled baseline reassigns real MorphoRepr annotations to other features within the same split. It tests whether the morphologic form itself carries predictive power independently of its semantic match.

Constraints:

- shuffle within the same split;
- match expression length within ±1 term;
- preserve coefficients if configured;
- repeat `n_repeats` times;
- evaluate on `shuffle_control.evaluation_split` (random split by default);
- store `scored_by` as either `classifier` or `llm_judge`;
- use a deterministic `shuffle_id = {run_id}_{feature_index}_{shuffle_number}`;
- enforce `UNIQUE(run_id, feature_index, shuffle_number)`.

Most shuffled annotations are scored by classifiers to limit cost. A calibration fraction is routed through the same predictor+judge path as the treatment, so the null comparison remains calibrated.

---

## 9. Unit tests

The test suite must pass before any pilot or full run.

Required tests include:

- parser tests, including all examples from the paper;
- root-validation tests, distinguishing valid roots from roots eligible for registration;
- schema tests, including uniqueness constraints;
- DB tests with isolated `MORPHOREPR_DB_PATH`;
- classifier tests;
- shuffled-baseline tests;
- end-to-end pipeline tests on a tiny dev run.

Parser tests must cover at least:

```python
("mal-o", "mal", [], [], "-o")
("ne-a", "ne", [], [], "-a")
("mal-emo-a", "emo", ["mal"], [], "-a")
("soc-ant-o", "soc", [], ["ant"], "-o")
("dat-ad-o", "dat", [], ["ad"], "-o")
("pens-ad-is", "pens", [], ["ad"], "-is")
("mal-far-int-e", "far", ["mal"], ["int"], "-e")
```

All 11 paper examples must pass.

---

## 10. Orchestrator

The orchestrator is the only entry point for the final run.

Primary command:

```bash
python orchestrator.py --config configs/run_v1.yaml
```

Supported modes:

```bash
python orchestrator.py --config configs/dev_run.yaml --n-features 5
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
python orchestrator.py --config configs/run_v1.yaml --resume --run-id <run_id>
```

The orchestrator must:

- create logs and checkpoints;
- initialize or resume a run;
- verify Git commit, config hash, prompt hashes, corpus hash, and lexicon hash;
- block frozen runs with `git_commit: FILL_BEFORE_LAUNCH` unless `allow_unpinned_commit=true`;
- execute phases in order;
- check budget before and after phases;
- persist `last_phase` for resumption;
- stop loudly on any phase failure;
- never auto-fix code during a full frozen run.

Phase order:

1. `p1_load` — load SAE features.
2. `p1_rank` — assign splits.
3. `p2_cluster` — cluster NL descriptions.
4. `p2_label` — propose lexicon morphemes.
5. `p2_consistency` — validate lexicon coherence.
6. `p3_encode_run1` — first annotation run.
7. `p3_encode_run2` — second independent annotation run.
8. `p3_fidelity` — AUC-ROC fidelity evaluation.
9. `p3_baselines` — NL, Semantic Regex, keyword tags.
10. `p4_steering` — activation steering.
11. `p4_predict` — causal prediction from annotations.
12. `p4_judge` — causal/qualitative judging.
13. `p5_report` — reporting and metrics.
14. `p5_gaps` — analysis of uncovered features.

---

## 11. Setup and execution order

```bash
# 1. Environment
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sqlite3 db/features.db < db/schema.sql

# 2. Unit tests (no API key required)
pytest tests/test_parser.py tests/test_schema.py \
       tests/test_db.py tests/test_shuffle_baseline.py -v
# All must pass before continuing.

# 3. Classifier calibration
python classifiers/calibration/run_calibration.py
# Must print PASS for all 5 properties.

# 4. Model-access validation (BLOCKING)
python -c "
from agents.steerer import _get_model, _get_sae
from utils.config_utils import load_config
cfg = load_config('configs/dev_run.yaml')
_get_model(cfg)
# _get_sae now takes a LAYER (the SAE is loaded by layer, Rule 6).
# Test on a representative proxy layer (e.g. 6 for Pythia).
layer = cfg.get('proxy_model', {}).get('validation_layer', 6)
_get_sae(cfg, layer)
print('Model access OK')
"
# If NotImplementedError: implement _get_model() / _get_sae() first.

# 5. Dev run (5 features — plumbing)
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Verify: DB populated, JSON parsed, cost < $1, steering produces output.

# 6. Pilot run (40 features — calibration)
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Analyze actual cost, coverage, classifier accuracy, JSON validity.
# Adjust thresholds/prompts if necessary, and declare all adjustments as calibration.

# 7. Full-run budget estimate
python -c "
import sqlite3
conn = sqlite3.connect('db/features.db')
cost = conn.execute(
    'SELECT total_cost_usd FROM runs ORDER BY started_at DESC LIMIT 1'
).fetchone()[0]
n_pilot = 40; n_full = 500; factor = 3.0
estimate = cost * (n_full / n_pilot) * factor
print(f'Pilot cost: {cost:.2f}\$')
print(f'Estimated full run: {estimate:.1f}\$')
"
# Update budget.max_cost_usd in run_v1.yaml accordingly.

# 8. Freeze configuration
git add -A && git commit -m "Freeze all parameters for full run v1"
python -c "
import subprocess
commit = subprocess.check_output(
    ['git','rev-parse','HEAD'], text=True
).strip()
print(f'Add to run_v1.yaml: git_commit: {commit}')
"
# Update run_v1.yaml with the exact commit.

# 9. Full frozen run
python orchestrator.py --config configs/run_v1.yaml
# No intervention during execution.

# 10. Crash resumption (if needed)
# ONLY if code, prompts, and config have NOT changed.
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"
python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <interrupted_run_id>
# If integrity verification fails: create a new run with a new commit.
```

---

## 12. Role of Claude Code

Claude Code is used **only outside the full frozen run**.

**Always allowed:**

- Write and debug agents, classifiers, and utilities.
- Generate classifier calibration files.
- Analyze intermediate pilot-run results.
- Produce readable reports from the SQLite database.
- Suggest fixes if a dev-run or pilot-run phase fails.
- Implement `steerer.py` once model access is validated.

**Forbidden during the full frozen run:**

- Modify any code, prompt, or config file.
- Intervene in the orchestrator while it is running.
- Interpret errors and propose automatic fixes.
- Relaunch a failed phase without explicit human validation.

---

## 13. Changelog v4 → v5

This version aligns the protocol with article v0.27 and fixes several bugs verified by execution.

**Parser (§4) — critical fixes (verified: 30/30 tests pass, including the 11 examples from the paper).**

- `parse_word` rewritten using **hyphen segmentation** instead of substring-based positional parsing. Version v4 (a) never detected infixes in the form `root-infix-suffix` (e.g. `soc-ant-o` became root `soc-ant`, infixes `[]`), because after removing suffix `-o`, the body `soc-ant` no longer contained the pattern `-ant-`; (b) failed on `mal-o` and `ne-a` because of the greedy prefix loop; (c) crashed at `ParsedTerm` instantiation because `coefficient_type` had no default value. All three are fixed.
- `RESERVED_TOKENS` completed with `iĝ`; hyphenless token sets (`PREFIX_TOKENS`, `INFIX_TOKENS`, `SUFFIX_TOKENS`) added for segmentation.
- `validate_free_root` split into `is_valid_root` and `can_register_new_free_root`. `mal`/`ne` are valid roots but cannot be re-registered.
- Tests updated: new `test_examples_from_paper`; `TestValidateFreeRoot` renamed `TestRootValidation`.

**Causal validation and steering (§7, config) — alignment with v0.27 methodology.**

- Primary steering magnitude normalized per feature (`magnitude_mode: p99_relative`, multiple of `activation_p99`); absolute +5 retained as a secondary condition.
- Steering at the feature’s own layer (`layer_mode: per_feature`); `_get_sae(config, layer)` loads and caches one SAE per layer.
- OOD instances excluded from the primary metric.
- `run()` and `_run_steering_batch` rewritten accordingly; `magnitude_rel` added to `steering_results`; real feature layer inserted.

**Validation model — proxy by default (Rule 5).**

- `proxy_model.enabled: true` by default. Primary validation runs on an open-weight proxy model; Claude 3 Sonnet examples are illustrative only.

**Comparison and statistics.**

- Causal-validity comparison on a shared feature set; primary score macro-F1 over `{increase, decrease, no_change}`; go/no-go criterion as paired difference with 95% bootstrap CI excluding 0.
- New `stats` section: 10,000 stratified bootstrap resamples, Holm-Bonferroni for primary comparisons, Benjamini-Hochberg for exploratory analyses, prediction-failure policy.
- New `intervention_controls` section: same-layer random feature, same-norm random direction, matched activation frequency, negative steering, prompt-only, DiffMean/ReFT.
- Shuffled control: calibration fraction through the same predictor+judge path as treatment (`llm_judge_calibration_fraction`, `scored_by` column).

**Reproducibility and splits.**

- Disjoint splits; random sampled from the complement of easy ∪ hard.
- Fixed clustering seeds.
- Batch section: 60-second polling, 86,400-second max wait.
- Frozen run blocked while `git_commit` is unpinned, except dev runs with `allow_unpinned_commit: true`.
- Run requalified as **frozen and auditable**, not deterministic.

**Software robustness.**

- `db_utils.save_agent_output`: `if output_json` bug fixed; `INSERT OR IGNORE` + uniqueness constraint for idempotent persistence.
- `api_utils`: lazy Anthropic client; concatenate all text blocks; config-driven timeouts; persistence before consumption/accounting.
- `prompt_utils.hash_corpus_canonical`: column headers included in the hash.
- `classifiers/negation.py`: ambiguous negation prefixes pruned.
- `classifiers/valence.py`: full label distribution with direct `negative` score.
- `baselines/shuffled.generate_shuffles(run_id, config, ...)`: config passed explicitly; orchestrator and tests updated.

**Miscellaneous.**

- Version headers updated v4 → v5.
