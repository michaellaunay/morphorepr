# MorphoRepr — Complete Test Procedure (v4)
## Robust Experimental Infrastructure for Reproducible Evaluation

---

## Guiding Principles

**Rule 1 — Role separation**
Claude Code is used for development, debugging, and supervision only. The final experimental run is driven exclusively by `python orchestrator.py --config configs/run_v1.yaml` — deterministic, no code modification, no untraced agentic intervention during execution.

**Rule 2 — Three execution levels**

| Mode | n features | Objective | Results |
|------|-----------|-----------|---------|
| Dev run | 5 | Plumbing, DB, parsing, batch, classifiers | Not scientific |
| Pilot run | 30–50 | Prompt, threshold, classifier calibration | Exploratory |
| Full frozen run | 500 | Publication | Frozen before launch |

If thresholds or prompts are adjusted after observing pilot run results, this must be explicitly declared as calibration in the paper.

**Rule 3 — Complete freeze before full run**
Git commit fixed and verified, config hashed, prompts hashed (full SHA256), corpus hashed, lexicon hashed, sampling policy documented. On `--resume`, all these values are re-verified before execution resumes.

**Rule 4 — No resume after code modification**
If code is modified after a phase failure, create a new run_id with a new Git commit. Never resume a run with a different commit from the one recorded at initialization.

**Rule 5 — Proxy model fallback**
If direct activation access to Claude 3 Sonnet is unavailable, the causal validation phase must be run on a proxy open-weight model with public SAEs (e.g. GPT-2, Pythia-6.9B, or Mistral-7B via `sae_lens`). In that case: (a) all causal conclusions are restricted to the proxy model; (b) Claude 3 Sonnet / Neuronpedia examples remain illustrative only; (c) this must be declared explicitly in the Methods section of the paper.

---

## 1. Project Structure

```
morphorepr-pipeline/
├── CLAUDE.md                        ← Claude Code instructions (dev/supervision only)
├── configs/
│   ├── dev_run.yaml
│   ├── pilot_run.yaml
│   └── run_v1.yaml                  ← frozen full run config
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
│   └── probe_sentences.txt          ← 20 neutral English probe sentences
├── logs/
└── checkpoints/
```

---

## 2. Frozen Configuration File

```yaml
# configs/run_v1.yaml

run_id_prefix: "morphorepr_v1"
description: "Full frozen run MorphoRepr v0.26 — 500 features"

# Reproducibility
git_commit: "FILL_BEFORE_LAUNCH"    # verified against actual Git HEAD at init
lexicon_version: "v1.0"
corpus_frozen: true

# Sampling policy
# temperature is NOT sent to the API by default to avoid HTTP 400
# on recent models that reject non-default sampling parameters.
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

# Corpus splits
splits:
  easy:   {n: 200, min_interp_score: 0.7}
  random: {n: 200, filter: "uniform"}
  hard:   {n: 100, max_interp_score: 0.5}
primary_split: "random"              # all go/no-go thresholds evaluated here

# Steering SAE
steering:
  # Primary magnitude for all features; curve on subsample only
  magnitudes: [0, 2, 5, 10]
  primary_magnitude: 5
  n_probe_sentences: 20
  # Subsample for dose-response curve (random.sample with seed)
  n_subsample_for_curve: 50
  target_layer: "middle"             # "early"|"middle"|"late" — confirm after pilot
  intervention_space: "residual"     # "residual"|"sae_latent"
  token_position: "all"              # "all"|"last"|"content_only"
  # OOD: based on activation_p99 stored in features table (NOT W_dec norm)
  ood_threshold: 3.0

# Proxy model fallback (used if Claude 3 Sonnet activations unavailable)
proxy_model:
  enabled: false                     # set true if Sonnet activations unavailable
  name: "EleutherAI/pythia-6.9b"
  sae_release: "pythia-6.9b-res-jb"

# Baselines
baselines:
  - nl_labels
  - semantic_regex
  - keyword_tags
  - morphorepr_shuffled

# Shuffled control
shuffle_control:
  n_repeats: 10
  within_split: true
  max_term_diff: 1
  preserve_coefficients: true
  # Shuffles evaluated by classifiers only (not LLM judge) to bound cost
  use_llm_judge: false
  # Evaluated on random split only; 10 repeats aggregated before CI
  evaluation_split: "random"

# Budget
budget:
  max_cost_usd: 150.0                # update after pilot run estimation
  alert_at_usd: 75.0
  abort_on_exceed: true

# Go/no-go thresholds (random split only)
thresholds:
  coverage_easy_min: 0.65
  coverage_random_min: 0.45
  coverage_hard_min: 0.20
  fidelity_auc_min: 0.60
  causal_validity_floor: 0.50
  root_jaccard_min: 0.60
  human_audit_jaccard_min: 0.60
  free_root_rate_max: 5.0

# Reproducibility seed (for subsample selection and shuffle control)
seed: 42
```

---

## 3. Complete SQLite Schema (v4)

```sql
-- db/schema.sql  —  Version 4, never modify after full run

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────────
-- Run traceability
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    git_commit      TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    prompt_hashes   TEXT NOT NULL,    -- JSON {agent: full_sha256}
    lexicon_version TEXT NOT NULL,
    lexicon_hash    TEXT NOT NULL,    -- SHA256 of canonical sorted lexicon.json
    -- corpus_hash covers only the features table (input data),
    -- NOT results added during the run. The DB will grow legitimately.
    corpus_hash     TEXT NOT NULL,    -- SHA256 of canonical sorted CSV export
    models_json     TEXT NOT NULL,
    use_temperature INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,             -- NULL when use_temperature=0
    seed            INTEGER,
    proxy_model     TEXT,             -- NULL if using primary model
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT DEFAULT 'running',
    last_phase      TEXT,
    total_cost_usd  REAL DEFAULT 0.0
);

-- ─────────────────────────────────────────────
-- Batch tracking (crash recovery)
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

-- ─────────────────────────────────────────────
-- Versioned prompts
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id   TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    version     TEXT NOT NULL,
    content     TEXT NOT NULL,
    sha256      TEXT NOT NULL,        -- full 64-char hex SHA256
    created_at  TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Feature corpus
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS features (
    feature_index   INTEGER PRIMARY KEY,
    split           TEXT NOT NULL,
    nl_description  TEXT NOT NULL,
    top_examples    TEXT NOT NULL,    -- serialized JSON array
    score_interp    REAL,
    activation_freq REAL,
    -- Activation statistics from Neuronpedia (used for OOD detection)
    -- These replace W_dec norm which is a different quantity
    activation_p99  REAL,
    activation_mean REAL,
    activation_std  REAL,
    layer           TEXT,
    sae_version     TEXT,
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Immutable agent outputs
-- ─────────────────────────────────────────────

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
    created_at      TEXT NOT NULL
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
    baseline        TEXT,             -- NULL = MorphoRepr; else baseline name
    computed_at     TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Baselines
-- ─────────────────────────────────────────────

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

-- ─────────────────────────────────────────────
-- Shuffled control
-- shuffle_id is deterministic: {run_id}_{feature_index}_{shuffle_number}
-- UNIQUE constraint prevents duplicates on repeated calls
-- Shuffles are evaluated by classifiers only (not LLM judge)
-- on random split only; 10 repeats aggregated before CI computation
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
    shuffle_number  INTEGER NOT NULL,
    source_feature  INTEGER NOT NULL REFERENCES features(feature_index),
    annotation      TEXT NOT NULL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(run_id, feature_index, shuffle_number)
);

-- ─────────────────────────────────────────────
-- Steering results — before/after text and activation values
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS steering_results (
    result_id           TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    feature_index       INTEGER NOT NULL,
    magnitude           REAL NOT NULL,
    probe_id            INTEGER NOT NULL,
    text_before         TEXT NOT NULL,
    text_after          TEXT,
    layer               TEXT,
    token_position      TEXT,
    activation_before   REAL,
    activation_after    REAL,
    -- OOD flag: 1 if abs(activation_after) > activation_p99 * ood_threshold
    -- activation_p99 from features table, NOT from W_dec norm
    ood_flag            INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- API cost tracking
-- ─────────────────────────────────────────────

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
-- User study results (out-of-pipeline; stored here for traceability)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_study_results (
    result_id           TEXT PRIMARY KEY,
    participant_id      TEXT NOT NULL,
    condition           TEXT NOT NULL,    -- 'morphorepr'|'semantic_regex'|'nl'
    feature_index       INTEGER,
    task_id             TEXT NOT NULL,
    response            TEXT,
    accuracy            REAL,
    response_time_ms    INTEGER,
    cognitive_load_score REAL,            -- NASA-TLX composite
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

## 4. Unique MorphoRepr Parser

```python
# utils/morphorepr_parser.py
"""
Deterministic MorphoRepr parser.
Single source of truth for ALL morphemic metrics.

5-step positional algorithm for each word:
  1. Remove coefficient (before '·')
  2. Read prefixes at the start of the word only
  3. Read suffix at the end of the word only
  4. Detect infixes between hyphens in the remaining body
  5. Extract root as the remaining part

No global str.replace() — strictly positional parsing throughout.
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

# RESERVED_TOKENS: these may NOT be used as newly induced free roots.
# Note: "mal" and "ne" appear in both PREDEFINED_ROOTS and RESERVED_TOKENS.
# This is intentional:
#   - "mal" and "ne" are valid as PREDEFINED roots (e.g. "mal-o", "ne-a")
#   - They may NOT be re-registered as NEW free roots by the pipeline
RESERVED_TOKENS = frozenset({
    "mal", "ne", "pli", "plej", "duon",           # prefix tokens
    "ad", "int", "it", "ist", "ant", "at", "ig",  # infix tokens
    "o", "a", "e", "i", "as", "is", "os", "us", "u"  # suffix tokens
})


@dataclass
class ParsedTerm:
    coefficient: float
    coefficient_type: str   # "confidence" | "activation"
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


def parse_word(word: str) -> ParsedTerm:
    """Deterministic positional parse of a single MorphoRepr word."""
    term = ParsedTerm(coefficient=0.0, raw_word=word)
    remaining = word.strip()

    # Step 2: read prefixes at the start (positional)
    while True:
        matched_prefix = None
        for p in PREFIXES:
            if remaining.startswith(p):
                matched_prefix = p
                break
        if matched_prefix:
            after = remaining[len(matched_prefix):]
            if after:
                term.prefixes.append(matched_prefix.rstrip("-"))
                remaining = after
            else:
                term.parse_error = f"Terminal prefix with no root: {word}"
                return term
        else:
            break

    # Step 3: read suffix at the end (longest match first)
    matched_suffix = None
    for s in sorted(ALL_SUFFIXES, key=len, reverse=True):
        if remaining.endswith(s):
            matched_suffix = s
            remaining = remaining[:-len(s)]
            break

    if not matched_suffix:
        term.parse_error = f"No recognized suffix: {word}"
        return term

    term.suffix = matched_suffix
    term.suffix_type = ("tense" if matched_suffix in TENSE_SUFFIXES
                        else "syntactic")

    # Step 4: detect infixes in the remaining body
    for ix in INFIXES:
        if ix in remaining:
            parts = remaining.split(ix, 1)
            before_infix = parts[0]
            after_infix  = parts[1] if len(parts) > 1 else ""
            if before_infix:
                term.infixes.append(ix.strip("-"))
                remaining = before_infix + ("-" + after_infix if after_infix else "")

    # Strip residual hyphens from infix splitting
    remaining = remaining.strip("-").strip()

    # Step 5: root is what remains
    if not remaining:
        term.parse_error = f"No root extracted: {word}"
        return term

    term.root = remaining
    return term


def parse_expression(expr: str,
                     coefficient_type: str = "confidence") -> ParsedExpression:
    """Parse a complete MorphoRepr expression."""
    result = ParsedExpression(raw=expr)
    if not expr or not expr.strip():
        result.parse_error = "Empty expression"
        return result

    term_strings = [t.strip() for t in expr.split("+") if t.strip()]
    if not term_strings:
        result.parse_error = "No terms found"
        return result

    for ts in term_strings:
        if "·" not in ts:
            result.parse_error = f"Term missing '·' separator: {ts}"
            return result
        coeff_str, word = ts.split("·", 1)
        try:
            coeff = float(coeff_str.strip())
        except ValueError:
            result.parse_error = f"Invalid coefficient: {coeff_str}"
            return result
        if not (0.01 <= coeff <= 1.00):
            result.parse_error = f"Coefficient out of range [0.01,1.00]: {coeff}"
            return result
        parsed_term = parse_word(word.strip())
        parsed_term.coefficient = coeff
        parsed_term.coefficient_type = coefficient_type
        result.terms.append(parsed_term)

    # Verify descending coefficient order
    coeffs = [t.coefficient for t in result.terms]
    if coeffs != sorted(coeffs, reverse=True):
        result.parse_error = "Terms not ordered by descending coefficient"
        return result

    return result


def validate_free_root(root: str) -> Optional[str]:
    """
    Validates a free root candidate.
    Returns None if valid, error message otherwise.

    Note on mal and ne:
      - Both are in PREDEFINED_ROOTS: valid as predefined roots (e.g. "mal-o")
      - Both are in RESERVED_TOKENS: may NOT be re-registered as new free roots
      This dual membership is intentional — see comment on RESERVED_TOKENS above.
    """
    if root in PREDEFINED_ROOTS:
        return None  # predefined roots are always valid
    if root in RESERVED_TOKENS:
        return f"Root '{root}' is a reserved token"
    if not re.match(r'^[a-z]{2,5}$', root):
        return f"Root '{root}' does not match [a-z]{{2,5}}"
    return None
```

---

## 5. Core Utilities

### 5.1 db_utils.py

```python
# utils/db_utils.py
"""
Single access point to features.db.
All database operations must go through this module.
DB_PATH is configurable via MORPHOREPR_DB_PATH env var for test isolation.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

DB_PATH = Path(os.environ.get("MORPHOREPR_DB_PATH", "db/features.db"))


@contextmanager
def get_conn(db_path: Optional[Path] = None):
    path = db_path or DB_PATH
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
    """Returns features without output for this agent/run_number. Idempotent."""
    with get_conn() as conn:
        done = {
            r["feature_index"]
            for r in conn.execute("""
                SELECT feature_index FROM agent_outputs
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
        if r["feature_index"] not in done:
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
                      coefficient_type: str = "confidence"):
    """Named INSERT — schema-change resistant."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, feature_index, agent_name, run_number,
            json.dumps(output_json) if output_json else None,
            raw_output, status, error_msg,
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


def mark_batch_consumed(batch_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE batches SET status='consumed', consumed_at=?
            WHERE batch_id=?
        """, (datetime.utcnow().isoformat(), batch_id))


def get_unconsumed_batch(run_id: str, phase: str,
                         agent_name: str, run_number: int) -> Optional[str]:
    """Returns batch_id of a submitted-but-not-consumed batch, if any."""
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
    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        cumulative = (row["total_cost_usd"] if row else 0.0) + cost
        conn.execute(
            "UPDATE runs SET total_cost_usd=? WHERE run_id=?",
            (cumulative, run_id)
        )
        conn.execute("""
            INSERT INTO api_usage (
                call_id, run_id, phase, agent_name, model,
                tokens_input, tokens_output, batch_id, cost_usd,
                cumulative_cost, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), run_id, phase, agent_name, model,
            tokens_in, tokens_out, batch_id, cost, cumulative,
            datetime.utcnow().isoformat()
        ))
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
Batch API wrapper with crash recovery.
Config is always passed explicitly — no load_config() calls here.
"""
import anthropic
import json
import logging
import time
from typing import Optional, Callable
from utils.db_utils import (register_batch, mark_batch_consumed,
                             get_unconsumed_batch, log_api_cost, check_budget)

logger = logging.getLogger(__name__)
client = anthropic.Anthropic()

COST_PER_MTK = {
    "claude-sonnet-4-6":         {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0,  "output": 5.0},
}
BATCH_DISCOUNT = 0.50


def compute_cost(model: str, tokens_in: int, tokens_out: int,
                 is_batch: bool = True) -> float:
    rates = COST_PER_MTK.get(model, {"input": 3.0, "output": 15.0})
    cost = ((tokens_in  / 1_000_000) * rates["input"] +
            (tokens_out / 1_000_000) * rates["output"])
    return cost * (BATCH_DISCOUNT if is_batch else 1.0)


def build_batch_requests(features: list[dict],
                         system_prompt: str,
                         user_prompt_fn: Callable,
                         model: str,
                         max_tokens: int,
                         config: dict) -> list[dict]:
    """
    Config passed explicitly. Temperature added only if use_temperature=True.
    Prevents HTTP 400 on models that reject non-default sampling parameters.
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
            "custom_id": f"feature_{f['feature_index']}",
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
                          poll_interval: int = 30,
                          max_wait_seconds: int = 7200) -> list[dict]:
    """
    Submits a batch (or recovers an existing unconsumed one) and returns results.
    Config passed explicitly throughout.
    """
    existing = get_unconsumed_batch(run_id, phase, agent_name, run_number)
    if existing:
        logger.info(f"Recovering unconsumed batch {existing}")
        batch_id = existing
    else:
        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        register_batch(batch_id, run_id, phase, agent_name,
                       run_number, len(requests))
        logger.info(f"Batch submitted: {batch_id} ({len(requests)} requests)")

    elapsed = 0
    while elapsed < max_wait_seconds:
        status_obj = client.messages.batches.retrieve(batch_id)
        if status_obj.processing_status == "ended":
            break
        elif status_obj.processing_status == "errored":
            raise RuntimeError(f"Batch {batch_id} server error")
        counts = status_obj.request_counts
        logger.info(f"Batch {batch_id}: {counts.processing} processing, "
                    f"{counts.succeeded} succeeded, {counts.errored} errored")
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(f"Batch {batch_id} timeout after {max_wait_seconds}s")

    results = []
    total_in, total_out = 0, 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            msg  = result.result.message
            raw  = msg.content[0].text if msg.content else ""
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

    cost = compute_cost(model, total_in, total_out, is_batch=True)
    cumulative = log_api_cost(run_id, phase, agent_name, model,
                              total_in, total_out, batch_id, cost)
    mark_batch_consumed(batch_id)
    logger.info(f"Batch {batch_id} consumed — cost: {cost:.3f}$ | "
                f"Cumulative: {cumulative:.2f}$")

    budget = config.get("budget", {})
    if budget.get("abort_on_exceed") and \
       cumulative >= budget.get("max_cost_usd", float("inf")):
        raise RuntimeError(
            f"Budget exceeded: {cumulative:.2f}$ >= "
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
        end = -1 if lines[-1].strip() == "```" else len(lines)
        clean = "\n".join(lines[1:end])
    try:
        parsed = json.loads(clean)
        if "status" not in parsed:
            logger.warning(f"{custom_id}: JSON missing 'status' field")
            return parsed, "invalid_json"
        if parsed["status"] == "uncovered":
            return parsed, "uncovered"
        return parsed, "ok"
    except json.JSONDecodeError:
        logger.warning(f"{custom_id}: non-JSON output: {raw[:120]}")
        return None, "invalid_json"
```

### 5.3 prompt_utils.py

```python
# utils/prompt_utils.py
"""
Prompt loading, hashing, and registration.
Full SHA256 (64 hex chars) — no truncation.
Canonical hashing for corpus (CSV sorted export) and lexicon (sorted JSON keys).
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
        raise FileNotFoundError(f"Prompt not found: {path}")
    return p.read_text(encoding="utf-8").strip()


def hash_prompt(content: str) -> str:
    """Full SHA256 — 64 hex characters, no truncation."""
    return hashlib.sha256(content.encode()).hexdigest()


def hash_lexicon_canonical(lexicon_path: str) -> str:
    """
    Canonical lexicon hash: sorted JSON keys, encoding-independent.
    """
    data = json.loads(Path(lexicon_path).read_text())
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_corpus_canonical(db_path: str) -> str:
    """
    Canonical corpus hash: sorted CSV export of the features table only.
    covers only input data — NOT results added during the run.
    The database will grow legitimately during execution; only the
    features table rows are part of the frozen corpus definition.
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM features ORDER BY feature_index"
    ).fetchall()
    conn.close()
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def register_prompts(prompt_paths: dict) -> dict:
    """Registers all prompts in DB. Returns {agent_name: full_sha256}."""
    hashes = {}
    with get_conn() as conn:
        for agent_name, path in prompt_paths.items():
            content = load_prompt(path)
            sha     = hash_prompt(content)
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
    """Raises RuntimeError if any prompt changed since registration."""
    for agent_name, path in prompt_paths.items():
        current  = hash_prompt(load_prompt(path))
        expected = registered_hashes.get(agent_name, "")
        if current != expected:
            raise RuntimeError(
                f"Prompt modified: {agent_name}\n"
                f"  expected: {expected[:16]}...\n"
                f"  current:  {current[:16]}..."
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
NEG_PREFIXES = ("un", "im", "in", "dis", "non", "ir", "il", "a")

def count_negation_signals(text: str) -> float:
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
        elif any(t.lower_.startswith(p) for p in NEG_PREFIXES) and len(t.text) > 4:
            score += 0.3
    return score / len(tokens)

def measure(texts_before: list[str], texts_after: list[str]) -> dict:
    before    = sum(count_negation_signals(t) for t in texts_before) / len(texts_before)
    after     = sum(count_negation_signals(t) for t in texts_after)  / len(texts_after)
    delta     = after - before
    THRESHOLD = 0.02
    return {
        "property":  "negation_presence",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": ("INCREASE" if delta >  THRESHOLD else
                      "DECREASE" if delta < -THRESHOLD else
                      "NO_CHANGE")
    }
```

### 6.2 Valence (semi-robust)

```python
# classifiers/valence.py
"""
Uses cardiffnlp/twitter-roberta-base-sentiment-latest rather than SST-2.
SST-2 is trained on movie reviews and performs poorly on technical/narrative text.
The Cardiff model is more robust across text domains.
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
            max_length=512
        )
    return _pipe

def _neg_score(text: str) -> float:
    result = get_pipe()(text)[0]
    if result["label"].lower() in ("negative", "neg", "label_0"):
        return result["score"]
    return 1.0 - result["score"]

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
        "reliability_note": ("Semi-robust: interpret with caution on "
                             "technical, ironic, or code-heavy text.")
    }
```

### 6.3 Classifier calibration

```python
# classifiers/calibration/run_calibration.py
"""
Must pass before pilot run. All primary robust properties require calibration.
"""
import json
from pathlib import Path

def calibrate(measure_fn, test_file: str,
              property_name: str,
              min_accuracy: float = 0.85) -> bool:
    data = json.loads(Path(test_file).read_text())
    correct = sum(
        1 for ex in data
        if measure_fn([ex["text_before"]], [ex["text_after"]])["direction"]
           == ex["expected_direction"]
    )
    accuracy = correct / len(data)
    status   = "✅ PASS" if accuracy >= min_accuracy else "❌ FAIL"
    print(f"{status} {property_name}: {accuracy:.1%} "
          f"({correct}/{len(data)}) — threshold: {min_accuracy:.0%}")
    return accuracy >= min_accuracy

if __name__ == "__main__":
    from classifiers import negation, tense, code_presence, modality, valence

    results = [
        calibrate(negation.measure,
                  "calibration/negation_test.json",
                  "negation_presence",  0.85),
        calibrate(tense.measure,
                  "calibration/tense_test.json",
                  "tense",              0.85),
        calibrate(code_presence.measure,
                  "calibration/code_presence_test.json",
                  "code_presence",      0.90),
        calibrate(modality.measure,
                  "calibration/modality_test.json",
                  "conditional_modality", 0.85),
        calibrate(valence.measure,
                  "calibration/valence_test.json",
                  "negative_valence",   0.80),
    ]
    if not all(results):
        raise SystemExit(
            "Calibration failed — fix classifiers before running pilot."
        )
    print("\nAll classifiers calibrated — ready for pilot run.")
```

---

## 7. Steerer — Full Specification (v4)

```python
# agents/steerer.py
"""
Phase 4 — SAE Activation Steering.

Intervention specification:
  - Space:          residual stream, after SAE reconstruction
  - Layer:          configured in run_v1.yaml (steering.target_layer)
  - Token position: configurable ("all" | "last" | "content_only")
  - Amplitude:      normalized (stored as absolute activation units in config)
  - Control:        magnitude=0 always executed as baseline
  - Dose-response:  [0, 2, 5, 10] on seeded subsample of 50 random-split features
  - All features:   primary magnitude (5) + control (0) only
  - OOD detection:  abs(activation_after) > activation_p99 * ood_threshold
                    where activation_p99 comes from features table,
                    NOT from sae.W_dec[feature_index].norm()

Model access paths (implement one before pilot run):
  A. TransformerLens  — for GPT-style proxy open-weight models
  B. nnsight          — if direct Claude access available
  C. Local weights    — if open-weight SAE-compatible model available

Proxy model fallback:
  If Claude 3 Sonnet activations are unavailable, set proxy_model.enabled=true
  in run_v1.yaml. All causal conclusions will then be restricted to the proxy
  model. Claude 3 Sonnet examples remain illustrative only. This must be
  declared explicitly in the paper Methods section.
"""
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# IMPLEMENTATION GUARD
# The functions below raise NotImplementedError until model
# access is fully implemented and validated in the dev run.
# ─────────────────────────────────────────────────────────

def _get_sae(config: dict):
    """
    Load the SAE for the target model and layer.
    Implement one of the three paths before pilot run.
    """
    proxy = config.get("proxy_model", {})
    if proxy.get("enabled"):
        from sae_lens import SAE
        sae, _, _ = SAE.from_pretrained(
            release=proxy["sae_release"],
            sae_id=f"blocks.{config['steering']['target_layer']}.hook_resid_post"
        )
        return sae
    # Default: Claude 3 Sonnet SAE (requires special access)
    raise NotImplementedError(
        "_get_sae() not implemented.\n"
        "To unblock:\n"
        "  A. Set proxy_model.enabled=true in config and use a public SAE, OR\n"
        "  B. Implement Claude 3 Sonnet SAE access via sae_lens/nnsight.\n"
        "Validate in dev run before pilot run."
    )


def _get_model(config: dict):
    """
    Load the language model for steering.
    Implement one of the three paths before pilot run.
    """
    proxy = config.get("proxy_model", {})
    if proxy.get("enabled"):
        # Path A: TransformerLens proxy model
        import transformer_lens
        model = transformer_lens.HookedTransformer.from_pretrained(
            proxy["name"]
        )
        return model
    # Path B/C: Claude 3 Sonnet or other — requires nnsight or local weights
    raise NotImplementedError(
        "_get_model() not implemented.\n"
        "To unblock:\n"
        "  A. Set proxy_model.enabled=true and implement TransformerLens path, OR\n"
        "  B. Implement nnsight path for Claude access, OR\n"
        "  C. Load local open-weight model.\n"
        "Validate in dev run before pilot run."
    )


def load_probe_sentences(n: int = 20) -> list[str]:
    """
    Load neutral English probe sentences.
    Requirements: 10–30 tokens each, no strong emotional or technical content,
    no named entities, no negation markers.
    """
    path = Path("data/probe_sentences.txt")
    if not path.exists():
        raise FileNotFoundError(
            "data/probe_sentences.txt not found.\n"
            "Create this file with 20 neutral sentences before the dev run."
        )
    sentences = [l.strip() for l in path.read_text().splitlines()
                 if l.strip()][:n]
    if len(sentences) < n:
        raise ValueError(
            f"Only {len(sentences)} probe sentences available, {n} required."
        )
    return sentences


def steer_feature(model,
                  sae,
                  feature_index: int,
                  magnitude: float,
                  probe_sentences: list[str],
                  feature_stats: dict,
                  config: dict) -> list[dict]:
    """
    Apply steering and return before/after pairs.

    OOD detection uses activation_p99 from feature_stats (loaded from the
    features table), NOT sae.W_dec[feature_index].norm() which is a different
    quantity (direction norm vs activation distribution percentile).

    Implementation steps:
    1. Tokenize probe sentence
    2. Forward pass, record residual activation at target layer
    3. Modify residual: add magnitude * sae.W_dec[feature_index] at token positions
    4. Re-run forward pass with modified residual
    5. Decode before and after outputs
    6. Measure actual activation achieved (for OOD check)
    """
    ood_thresh    = config["steering"]["ood_threshold"]
    # Use stored activation_p99, NOT W_dec norm
    activation_p99 = feature_stats.get("activation_p99")

    results = []

    for probe_id, sentence in enumerate(probe_sentences, 1):
        try:
            # ── PLACEHOLDER — implement model-specific steering here ──
            text_before = sentence
            text_after  = None          # MUST be replaced by implementation
            activation_before = None
            activation_after  = None
            # ────────────────────────────────────────────────────────────

            # Guard: fail loudly if placeholders not replaced
            if text_after is None or text_after == sentence:
                raise NotImplementedError(
                    f"steer_feature() placeholder not replaced for "
                    f"feature {feature_index}, magnitude {magnitude}.\n"
                    f"Implement model-specific steering before running pilot."
                )

            # OOD detection using activation_p99 from features table
            ood = 0
            if activation_p99 and activation_after is not None:
                ood = int(abs(activation_after) > activation_p99 * ood_thresh)

            results.append({
                "probe_id":          probe_id,
                "text_before":       text_before,
                "text_after":        text_after,
                "activation_before": activation_before,
                "activation_after":  activation_after,
                "ood_flag":          ood
            })
        except NotImplementedError:
            raise   # propagate — do not swallow implementation errors
        except Exception as e:
            logger.warning(
                f"Steering error feature {feature_index} "
                f"probe {probe_id} magnitude {magnitude}: {e}"
            )
            results.append({
                "probe_id":          probe_id,
                "text_before":       sentence,
                "text_after":        None,
                "activation_before": None,
                "activation_after":  None,
                "ood_flag":          0,
                "error":             str(e)
            })
    return results


def run(run_id: str, config: dict):
    """
    Phase 4 — Steering.
    Dose-response curve on seeded subsample; primary magnitude on all features.
    """
    from utils.db_utils import get_conn

    logger.info("Phase 4: SAE Steering")

    # Validate model access before loading full corpus
    try:
        model = _get_model(config)
        sae   = _get_sae(config)
    except NotImplementedError as e:
        logger.error(str(e))
        raise

    probe_sentences = load_probe_sentences(config["steering"]["n_probe_sentences"])
    primary_mag     = config["steering"]["primary_magnitude"]
    all_magnitudes  = config["steering"]["magnitudes"]
    n_subsample     = config["steering"]["n_subsample_for_curve"]
    seed            = config.get("seed", 42)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_index,
                   f.split,
                   f.activation_p99,
                   f.activation_mean,
                   f.activation_std,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_index = ao.feature_index
            WHERE ao.run_id = ? AND ao.agent_name = 'encoder'
              AND ao.run_number = 1 AND ao.status = 'ok'
        """, (run_id,)).fetchall()

    random_features = [dict(r) for r in rows if r["split"] == "random"]

    # Seeded subsample — NOT [:n] which would be order-dependent
    rng       = random.Random(seed)
    subsample = rng.sample(random_features,
                           min(n_subsample, len(random_features)))
    subsample_indices = {f["feature_index"] for f in subsample}

    # Subsample: full dose-response curve
    _run_steering_batch(run_id, model, sae, subsample,
                        all_magnitudes, probe_sentences, config)

    # Remaining features: primary magnitude + control only
    remaining = [f for f in random_features
                 if f["feature_index"] not in subsample_indices]
    _run_steering_batch(run_id, model, sae, remaining,
                        [0, primary_mag], probe_sentences, config)

    logger.info("Phase 4 steering complete")


def _run_steering_batch(run_id: str, model, sae,
                        features: list[dict],
                        magnitudes: list[float],
                        probe_sentences: list[str],
                        config: dict):
    from utils.db_utils import get_conn
    with get_conn() as conn:
        for feat in features:
            feature_stats = {
                "activation_p99":  feat.get("activation_p99"),
                "activation_mean": feat.get("activation_mean"),
                "activation_std":  feat.get("activation_std"),
            }
            for mag in magnitudes:
                results = steer_feature(
                    model, sae, feat["feature_index"],
                    mag, probe_sentences, feature_stats, config
                )
                for r in results:
                    conn.execute("""
                        INSERT INTO steering_results (
                            result_id, run_id, feature_index, magnitude,
                            probe_id, text_before, text_after,
                            layer, token_position,
                            activation_before, activation_after,
                            ood_flag, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid4()), run_id, feat["feature_index"],
                        mag, r["probe_id"],
                        r["text_before"], r.get("text_after"),
                        config["steering"].get("target_layer"),
                        config["steering"].get("token_position"),
                        r.get("activation_before"),
                        r.get("activation_after"),
                        r.get("ood_flag", 0),
                        datetime.utcnow().isoformat()
                    ))
```

---

## 8. Shuffled Baseline

```python
# baselines/shuffled.py
"""
MorphoRepr shuffled control.
- Within same split only (no cross-split contamination)
- Matched expression length ±1 term
- 10 repeats per feature, seeded
- shuffle_id is deterministic: {run_id}_{feature_index}_{shuffle_number}
- UNIQUE(run_id, feature_index, shuffle_number) prevents duplicates
- Evaluated by classifiers only (not LLM judge) to bound cost
- Evaluated on random split only; 10 repeats aggregated before CI
"""
import logging
import random
from datetime import datetime
from utils.db_utils import get_conn
from utils.config_utils import load_config

logger = logging.getLogger(__name__)


def _count_terms(expression: str) -> int:
    return len([t for t in expression.split("+") if "·" in t])


def generate_shuffles(run_id: str, n_repeats: int = 10):
    config   = load_config()
    max_diff = config["shuffle_control"]["max_term_diff"]
    seed     = config.get("seed", 42)

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_index,
                   f.split,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_index = ao.feature_index
            WHERE ao.run_id = ?
              AND ao.agent_name = 'encoder'
              AND ao.run_number = 1
              AND ao.status = 'ok'
        """, (run_id,)).fetchall()

    by_split: dict[str, list[dict]] = {}
    for r in rows:
        if r["expression"]:
            by_split.setdefault(r["split"], []).append({
                "feature_index": r["feature_index"],
                "expression":    r["expression"],
                "n_terms":       _count_terms(r["expression"])
            })

    rng = random.Random(seed)
    inserts = []
    for split, features in by_split.items():
        for feat in features:
            n_feat = feat["n_terms"]
            candidates = [
                f for f in features
                if f["feature_index"] != feat["feature_index"]
                and abs(f["n_terms"] - n_feat) <= max_diff
            ]
            if len(candidates) < 3:
                logger.warning(
                    f"Feature {feat['feature_index']}: "
                    f"only {len(candidates)} shuffle candidates"
                )
                continue
            for shuffle_num in range(1, n_repeats + 1):
                source = rng.choice(candidates)
                shuffle_id = (f"{run_id}_{feat['feature_index']}"
                              f"_{shuffle_num}")
                inserts.append({
                    "shuffle_id":     shuffle_id,
                    "feature_index":  feat["feature_index"],
                    "shuffle_number": shuffle_num,
                    "source_feature": source["feature_index"],
                    "annotation":     source["expression"]
                })

    with get_conn() as conn:
        for s in inserts:
            conn.execute("""
                INSERT OR IGNORE INTO shuffle_controls (
                    shuffle_id, run_id, feature_index, shuffle_number,
                    source_feature, annotation,
                    causal_score, causal_outcome, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """, (
                s["shuffle_id"], run_id,
                s["feature_index"], s["shuffle_number"],
                s["source_feature"], s["annotation"],
                datetime.utcnow().isoformat()
            ))

    logger.info(f"Generated {len(inserts)} shuffle controls "
                f"({n_repeats} per feature)")
```

---

## 9. Tests

```python
# tests/conftest.py
import os
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Isolated temp DB injected via env var. No production DB touched."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MORPHOREPR_DB_PATH", str(db_path))
    schema = Path("db/schema.sql").read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    return db_path


# ─────────────────────────────────────────────
# tests/test_parser.py
# ─────────────────────────────────────────────

import pytest
from utils.morphorepr_parser import (
    parse_expression, parse_word, validate_free_root
)


class TestParseWord:
    def test_simple_verbal(self):
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

    def test_no_suffix_invalid(self):
        t = parse_word("ag")
        assert not t.is_valid and t.parse_error is not None

    def test_free_root(self):
        t = parse_word("pens-is")
        assert t.root == "pens" and t.suffix == "-is" and t.is_valid


class TestParseExpression:
    def test_valid_two_terms(self):
        e = parse_expression("0.86·mal-emo-a + 0.42·ne-soc-a")
        assert e.is_valid and len(e.terms) == 2
        assert e.roots == {"emo", "soc"}

    def test_descending_order_enforced(self):
        e = parse_expression("0.40·ag-is + 0.90·sci-o")
        assert not e.is_valid and "descending" in e.parse_error.lower()

    def test_coefficient_out_of_range(self):
        e = parse_expression("9.99·ag-is")
        assert not e.is_valid

    def test_empty(self):
        assert not parse_expression("").is_valid


class TestValidateFreeRoot:
    def test_valid_free_root(self):
        assert validate_free_root("pens") is None
        assert validate_free_root("far") is None

    def test_reserved_token_rejected(self):
        # Reserved as prefix/infix/suffix — cannot be new free root
        assert validate_free_root("is") is not None
        assert validate_free_root("ad") is not None

    def test_mal_ne_are_predefined_not_free(self):
        # mal and ne are PREDEFINED roots (valid), not new free roots
        # validate_free_root returns None for predefined roots
        assert validate_free_root("mal") is None  # allowed as predefined
        assert validate_free_root("ne")  is None  # allowed as predefined

    def test_too_long_rejected(self):
        assert validate_free_root("toolong") is not None

    def test_uppercase_rejected(self):
        assert validate_free_root("Pens") is not None


# ─────────────────────────────────────────────
# tests/test_db.py
# ─────────────────────────────────────────────

import sqlite3
import pytest
from utils.db_utils import (
    load_features_not_processed, save_agent_output,
    register_batch, mark_batch_consumed, get_unconsumed_batch
)


def _insert_run(conn, run_id="r1"):
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            proxy_model, started_at, completed_at, status,
            last_phase, total_cost_usd
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,'running',NULL,0.0)
    """, (run_id, "abc", "cfg", "{}", "v1", "lh", "ch",
          "{}", 0, None, 42, None, "2026-01-01T00:00:00"))


def _insert_feature(conn, index=1, split="random"):
    conn.execute("""
        INSERT INTO features (
            feature_index, split, nl_description, top_examples,
            score_interp, activation_freq,
            activation_p99, activation_mean, activation_std,
            layer, sae_version, neuronpedia_url, loaded_at
        ) VALUES (?,?,'desc','[]',0.8,0.5,2.1,0.8,0.4,'l1','s1','http://x',
                  '2026-01-01T00:00:00')
    """, (index, split))


def test_all_features_pending_initially(test_db):
    conn = sqlite3.connect(test_db)
    _insert_run(conn)
    _insert_feature(conn, 1)
    _insert_feature(conn, 2)
    conn.commit(); conn.close()

    pending = load_features_not_processed("r1", "encoder", 1)
    assert len(pending) == 2


def test_partial_encoding_leaves_remainder(test_db):
    conn = sqlite3.connect(test_db)
    _insert_run(conn)
    _insert_feature(conn, 1)
    _insert_feature(conn, 2)
    conn.commit(); conn.close()

    save_agent_output(
        "r1", 1, "encoder", 1, {"status": "encoded"},
        "raw", "ok", None, 100, 50, None, 0.001
    )
    pending = load_features_not_processed("r1", "encoder", 1)
    assert [f["feature_index"] for f in pending] == [2]


def test_batch_crash_recovery(test_db):
    conn = sqlite3.connect(test_db)
    _insert_run(conn)
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


def _setup_encoded_features(test_db, n=5, split="random"):
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
                feature_index, split, nl_description, top_examples,
                score_interp, activation_freq,
                activation_p99, activation_mean, activation_std,
                layer, sae_version, neuronpedia_url, loaded_at
            ) VALUES (?,?,'d','[]',0.8,0.5,2.0,0.8,0.4,'l1','s1','http://x',
                      '2026-01-01')
        """, (i, split))
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?,?,?,'encoder',1,?,?,?,NULL,100,50,NULL,0.0,
                      'confidence','2026-01-01')
        """, (
            f"o{i}", "r1", i,
            f'{{"status":"encoded","expression":"0.{i+5}0·ag-is"}}',
            "raw", "ok"
        ))
    conn.commit()
    conn.close()


def test_shuffle_not_self_assigned(test_db):
    _setup_encoded_features(test_db)
    generate_shuffles("r1", n_repeats=3)
    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT feature_index, source_feature FROM shuffle_controls"
    ).fetchall()
    conn.close()
    assert all(r[0] != r[1] for r in rows), "Feature assigned its own annotation"


def test_shuffle_unique_constraint(test_db):
    _setup_encoded_features(test_db)
    generate_shuffles("r1", n_repeats=3)
    generate_shuffles("r1", n_repeats=3)  # second call — no duplicates
    conn = sqlite3.connect(test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM shuffle_controls WHERE run_id='r1'"
    ).fetchone()[0]
    conn.close()
    assert count <= 5 * 3  # max 15 entries for 5 features × 3 repeats
```

---

## 10. Orchestrator

```python
# orchestrator.py
"""
MorphoRepr Pipeline Orchestrator v4.
Deterministic, frozen-config, auditable scientific run.

Usage:
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
from agents import encoder, fidelity, steerer, predictor, judge, reporter
from baselines import shuffled as shuffled_baseline


def parse_args():
    p = argparse.ArgumentParser(description="MorphoRepr Pipeline")
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
    if config_commit != "FILL_BEFORE_LAUNCH" and config_commit != git_commit:
        raise RuntimeError(
            f"git_commit in config ({config_commit[:8]}) does not match "
            f"current HEAD ({git_commit[:8]}). "
            f"Update configs/run_v1.yaml before launching."
        )

    prompt_hashes = register_prompts(config["prompts"])
    lexicon_hash  = hash_lexicon_canonical("db/lexicon.json")
    corpus_hash   = hash_corpus_canonical("db/features.db")

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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'running', NULL, 0.0)
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

    logger.info(f"Run initialized: {run_id}")
    logger.info(f"  Git commit:    {git_commit[:16]}")
    logger.info(f"  Config hash:   {config_hash[:16]}")
    logger.info(f"  Corpus hash:   {corpus_hash[:16]}")
    logger.info(f"  Lexicon hash:  {lexicon_hash[:16]}")
    if proxy.get("enabled"):
        logger.info(f"  Proxy model:   {proxy.get('name')} (Sonnet unavailable)")
    return run_id


def verify_resume_integrity(run_id: str, config: dict, args):
    """All hashes re-verified on resume. Any change = blocking error."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    if not row:
        raise RuntimeError(f"run_id {run_id} not found in DB")

    current_git     = get_git_commit()
    current_config  = hash_config(args.config)
    current_corpus  = hash_corpus_canonical("db/features.db")
    current_lexicon = hash_lexicon_canonical("db/lexicon.json")

    errors = []
    if row["git_commit"] != current_git:
        errors.append(
            f"Git commit changed: {row['git_commit'][:8]} → {current_git[:8]}"
        )
    if row["config_hash"] != current_config:
        errors.append("Config changed since original run")
    if row["corpus_hash"] != current_corpus:
        errors.append("Corpus changed since original run")
    if row["lexicon_hash"] != current_lexicon:
        errors.append("Lexicon changed since original run")

    registered_hashes = json.loads(row["prompt_hashes"])
    try:
        verify_prompts_unchanged(config["prompts"], registered_hashes)
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        msg = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(
            f"Resume blocked — modifications detected:\n{msg}\n\n"
            f"To continue with modifications, start a new run."
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
    logger.info("=== Cost summary ===")
    for phase, cost in rows:
        logger.info(f"  {phase:<20} {cost:6.3f} $")
    logger.info(f"  {'TOTAL':<20} {total:6.3f} $")


def _run_baselines(run_id: str):
    from baselines import nl_labels, semantic_regex, keyword_tags
    nl_labels.run(run_id)
    semantic_regex.run(run_id)
    keyword_tags.run(run_id)


PHASES = [
    ("p1_load",        lambda rid, cfg: loader.run(rid),           "SAE feature extraction"),
    ("p1_rank",        lambda rid, cfg: ranker.run(rid, cfg),       "Split stratification"),
    ("p2_cluster",     lambda rid, cfg: cluster.run(rid),           "Description clustering"),
    ("p2_label",       lambda rid, cfg: labeler.run(rid),           "Lexicon induction"),
    ("p2_consistency", lambda rid, cfg: consistency.run(rid),       "Lexicon validation"),
    ("p3_encode",      lambda rid, cfg: encoder.run(rid),           "MorphoRepr encoding (2 runs)"),
    ("p3_fidelity",    lambda rid, cfg: fidelity.run(rid),          "Fidelity AUC-ROC"),
    ("p3_baselines",   lambda rid, cfg: _run_baselines(rid),        "Baselines"),
    ("p3_shuffle",     lambda rid, cfg: shuffled_baseline.generate_shuffles(rid),
                                                                     "Shuffled control"),
    ("p4_steer",       lambda rid, cfg: steerer.run(rid, cfg),      "Activation steering"),
    ("p4_predict",     lambda rid, cfg: predictor.run(rid),         "Causal prediction"),
    ("p4_judge",       lambda rid, cfg: judge.run(rid),             "Causal validation"),
    ("p5_report",      lambda rid, cfg: reporter.run(rid),          "Synthesis"),
]


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

    if args.resume and args.run_id:
        run_id = args.run_id
        verify_resume_integrity(run_id, config, args)
        last_phase = get_last_phase(run_id)
        logger.info(f"Resuming run {run_id} from: {last_phase}")
    else:
        run_id     = initialize_run(config, args)
        last_phase = None

    phase_ids = [p[0] for p in PHASES]

    for phase_id, phase_fn, description in PHASES:
        if last_phase and phase_ids.index(phase_id) <= \
           phase_ids.index(last_phase):
            logger.info(f"⏭  {phase_id} already complete")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"▶  {phase_id}: {description}")
        logger.info(f"{'='*60}")

        try:
            phase_fn(run_id, config)
            mark_phase_complete(run_id, phase_id)
            print_cost_summary(run_id)

            cost, over = check_budget(run_id, config["budget"]["max_cost_usd"])
            if config["budget"]["abort_on_exceed"] and over:
                raise RuntimeError(
                    f"Budget exceeded: {cost:.2f}$ >= "
                    f"{config['budget']['max_cost_usd']}$"
                )

        except Exception as e:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE runs SET status='failed' WHERE run_id=?",
                    (run_id,)
                )
            logger.exception(f"Phase {phase_id} failed — run {run_id} archived")
            # Full frozen run: no automatic correction, no agentic intervention.
            # Archive, analyze, then start a new run with a new commit.
            sys.exit(1)

    with get_conn() as conn:
        conn.execute("""
            UPDATE runs SET status='completed', completed_at=?
            WHERE run_id=?
        """, (datetime.utcnow().isoformat(), run_id))
    print_cost_summary(run_id)
    logger.info(f"\n✅ Run {run_id} complete — results in db/features.db")


if __name__ == "__main__":
    run_pipeline(parse_args())
```

---

## 11. Setup and Execution Order

```bash
# ── 1. Environment ──────────────────────────────────────────
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sqlite3 db/features.db < db/schema.sql

# ── 2. Unit tests (no API key required) ─────────────────────
pytest tests/test_parser.py tests/test_schema.py \
       tests/test_db.py tests/test_shuffle_baseline.py -v
# All must pass before continuing

# ── 3. Classifier calibration ───────────────────────────────
python classifiers/calibration/run_calibration.py
# Must show ✅ PASS for all 5 properties

# ── 4. Validate model access (BLOCKING) ─────────────────────
python -c "
from agents.steerer import _get_model, _get_sae
from utils.config_utils import load_config
cfg = load_config('configs/dev_run.yaml')
_get_model(cfg)
_get_sae(cfg)
print('Model access OK')
"
# If NotImplementedError: implement _get_model() / _get_sae() first.
# If using proxy: set proxy_model.enabled=true in dev_run.yaml

# ── 5. Dev run (5 features — plumbing) ──────────────────────
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Verify: DB populated, JSON parsed, cost < 1$, steering produces output

# ── 6. Pilot run (40 features — calibration) ────────────────
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Analyze: actual cost, coverage, classifier accuracy, JSON validity
# Adjust thresholds or prompts if needed
# DECLARE any adjustment as calibration in the paper

# ── 7. Budget estimation for full run ───────────────────────
python -c "
import sqlite3
conn = sqlite3.connect('db/features.db')
cost = conn.execute(
    'SELECT total_cost_usd FROM runs ORDER BY started_at DESC LIMIT 1'
).fetchone()[0]
n_pilot = 40; n_full = 500; factor = 3.0
estimate = cost * (n_full / n_pilot) * factor
print(f'Pilot cost: {cost:.2f}\$')
print(f'Full run estimate: {estimate:.1f}\$')
"
# Update budget.max_cost_usd in run_v1.yaml accordingly

# ── 8. Freeze configuration ─────────────────────────────────
git add -A && git commit -m "Freeze all parameters for full run v1"
python -c "
import subprocess
commit = subprocess.check_output(
    ['git','rev-parse','HEAD'], text=True
).strip()
print(f'Add to run_v1.yaml: git_commit: {commit}')
"
# Update run_v1.yaml with exact commit hash

# ── 9. Full frozen run ───────────────────────────────────────
python orchestrator.py --config configs/run_v1.yaml
# No intervention during execution

# ── 10. Resume after crash (if needed) ──────────────────────
# ONLY if code, prompts, and config have NOT changed
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"
python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <interrupted_run_id>
# If integrity check fails → start new run with new commit
```

---

## 12. Role of Claude Code

Claude Code is involved **only outside the full frozen run**:

**Permitted at all times:**
- Writing and debugging agent scripts, classifiers, and utilities
- Generating classifier calibration files
- Analyzing pilot run intermediate results
- Producing human-readable reports from the SQLite database
- Suggesting corrections when a dev or pilot run phase fails
- Implementing `steerer.py` once model access is validated

**Prohibited during the full frozen run:**
- Modifying any code, prompt, or config file
- Intervening in the orchestrator during execution
- Interpreting errors and proposing automatic fixes
- Restarting a failed phase without explicit human validation
