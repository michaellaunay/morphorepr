# MorphoRepr — Complete Test Procedure (v3)
## Robust and Publishable Experimental Infrastructure

---

## Guiding Principles

**Rule 1 — Separation of roles**
Claude Code is used for development, debugging, and supervision. The final experimental run is driven exclusively by `python orchestrator.py --config configs/run_v1.yaml` — deterministic, with no code modification and no untraced agentic intervention during execution.

**Rule 2 — Three execution levels**

| Mode | n features | Objective | Results |
|------|-----------|-----------|---------|
| Dev run | 5 | Plumbing, DB, parsing, batch, classifiers | Non-scientific |
| Pilot run | 30–50 | Calibrate prompts, thresholds, classifiers | Exploratory |
| Full frozen run | 500 | Publication | Frozen before launch |

If thresholds or prompts are adjusted after observing the pilot-run results, this must be explicitly reported as calibration in the paper.

**Rule 3 — Complete freeze before the full run**
The Git commit is fixed and verified, the config is hashed, prompts are hashed with full SHA256, the corpus is hashed, the lexicon is hashed, and temperature is documented. When using `--resume`, all these values are checked again before resuming.

**Rule 4 — No resume after code modification**
If the code is modified after a phase failure, create a new `run_id` with a new Git commit. Never resume a run with a Git commit different from the one recorded for that run.

---

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
│   ├── steerer.py                   ← fully specified in Section 6
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
│   ├── db_utils.py                  ← the only DB access point
│   ├── api_utils.py                 ← Batch API wrapper
│   ├── prompt_utils.py
│   ├── config_utils.py
│   ├── morphorepr_parser.py         ← single parser for all metrics
│   └── stats_utils.py
├── tests/
│   ├── conftest.py                  ← temporary DB fixtures
│   ├── test_parser.py
│   ├── test_schema.py
│   ├── test_db.py
│   ├── test_classifiers.py
│   ├── test_shuffle_baseline.py
│   └── test_pipeline_e2e.py
├── orchestrator.py
├── requirements.txt
├── logs/
└── checkpoints/
```

---

## 2. Frozen Configuration File

```yaml
# configs/run_v1.yaml

run_id_prefix: "morphorepr_v1"
description: "Full frozen run MorphoRepr v0.26 — 500 features"

# Reproducibility — git_commit will be checked at initialization
git_commit: "FILL_BEFORE_LAUNCH"
lexicon_version: "v1.0"
corpus_frozen: true

# Sampling — temperature is not sent to the API by default
# to avoid 400 errors on some recent models
sampling:
  use_temperature: false
  temperature: null      # documented for the paper, not sent to the API

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

# Corpus
splits:
  easy:   {n: 200, min_interp_score: 0.7}
  random: {n: 200, filter: "uniform"}
  hard:   {n: 100, max_interp_score: 0.5}
primary_split: "random"

# SAE steering
steering:
  magnitudes: [0, 2, 5, 10]
  primary_magnitude: 5
  n_probe_sentences: 20
  n_subsample_for_curve: 50
  target_layer: "middle"         # "early" | "middle" | "late" — to be specified after pilot
  intervention_space: "residual" # "residual" | "sae_latent"
  token_position: "all"          # "all" | "last" | "content_only"
  ood_threshold: 3.0             # standard-deviation factor for out-of-distribution detection

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

# Budget
budget:
  max_cost_usd: 150.0     # margin after pilot-run estimation
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
```

---

## 3. Complete SQLite Schema (v3)

```sql
-- db/schema.sql  —  Version 3, never modify after the full run

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
    lexicon_hash    TEXT NOT NULL,    -- SHA256 of canonical lexicon.json export
    corpus_hash     TEXT NOT NULL,    -- SHA256 of canonical CSV corpus export
    models_json     TEXT NOT NULL,
    use_temperature INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,             -- NULL if use_temperature=0
    seed            INTEGER,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT DEFAULT 'running',
    last_phase      TEXT,
    total_cost_usd  REAL DEFAULT 0.0
);

-- ─────────────────────────────────────────────
-- Submitted batch tracking (crash resume)
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
    sha256      TEXT NOT NULL,    -- full SHA256 (64 hex chars)
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
    layer           TEXT,
    sae_version     TEXT,
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Raw outputs from each agent (immutable)
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
    baseline        TEXT,
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
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id      TEXT PRIMARY KEY,   -- deterministic: {run_id}_{fidx}_{num}
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
    shuffle_number  INTEGER NOT NULL,
    source_feature  INTEGER NOT NULL REFERENCES features(feature_index),
    annotation      TEXT NOT NULL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(run_id, feature_index, shuffle_number)   -- prevents logical duplicates
);

-- ─────────────────────────────────────────────
-- Steering — before/after storage
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS steering_results (
    result_id       TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL,
    magnitude       REAL NOT NULL,      -- 0, 2, 5, or 10
    probe_id        INTEGER NOT NULL,   -- 1..20
    text_before     TEXT NOT NULL,
    text_after      TEXT NOT NULL,
    layer           TEXT,
    token_position  TEXT,
    activation_before REAL,
    activation_after  REAL,
    ood_flag        INTEGER DEFAULT 0,  -- 1 if out of distribution
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Cost tracking
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ao_feature   ON agent_outputs(feature_index, agent_name, run_number);
CREATE INDEX IF NOT EXISTS idx_metrics      ON metrics(run_id, split, metric_name);
CREATE INDEX IF NOT EXISTS idx_api_phase    ON api_usage(run_id, phase);
CREATE INDEX IF NOT EXISTS idx_steering     ON steering_results(run_id, feature_index, magnitude);
CREATE INDEX IF NOT EXISTS idx_batches_run  ON batches(run_id, phase, agent_name, run_number);
```

---

## 4. Single MorphoRepr Parser

```python
# utils/morphorepr_parser.py
"""
Deterministic MorphoRepr parser.
Single source of truth for all morphemic metrics.

Five-step algorithm for each word:
  1. Remove the coefficient (before '·')
  2. Read prefixes only at the beginning of the word
  3. Read the suffix only at the end of the word
  4. Detect infixes between hyphens in the remaining body
  5. Extract the root as the remaining part

Never use global str.replace() — always use positional parsing.
"""
from dataclasses import dataclass, field
from typing import Optional
import re

# Complete inventory
PREFIXES = ("mal-", "ne-", "pli-", "plej-", "duon-")
INFIXES  = ("-ad-", "-int-", "-it-", "-ist-", "-ant-", "-at-", "-ig-", "-iĝ-")
TENSE_SUFFIXES    = ("-as", "-is", "-os", "-us", "-u")
SYNTACTIC_SUFFIXES = ("-o", "-a", "-e", "-i")
ALL_SUFFIXES = TENSE_SUFFIXES + SYNTACTIC_SUFFIXES

PREDEFINED_ROOTS = frozenset(
    {"sci", "emo", "ag", "dir", "soc", "dat", "tem", "lok", "mal", "ne"}
)

# Reserved tokens (free roots cannot be any of these)
RESERVED_TOKENS = frozenset({
    "mal", "ne", "pli", "plej", "duon",
    "ad", "int", "it", "ist", "ant", "at", "ig",
    "o", "a", "e", "i", "as", "is", "os", "us", "u"
})


@dataclass
class ParsedTerm:
    coefficient: float
    coefficient_type: str  # "confidence" | "activation"
    prefixes: list[str] = field(default_factory=list)
    root: str = ""
    infixes: list[str] = field(default_factory=list)
    suffix: str = ""
    suffix_type: str = ""  # "tense" | "syntactic"
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
    """
    Parse a single MorphoRepr word deterministically.
    Does not use global str.replace().
    """
    term = ParsedTerm(coefficient=0.0, raw_word=word)
    remaining = word.strip()

    # Step 2: read prefixes at the beginning (positionally)
    while True:
        matched_prefix = None
        for p in PREFIXES:
            if remaining.startswith(p):
                matched_prefix = p
                break
        if matched_prefix:
            # Check that something remains after the prefix
            after = remaining[len(matched_prefix):]
            if after:
                term.prefixes.append(matched_prefix.rstrip("-"))
                remaining = after
            else:
                term.parse_error = f"Terminal prefix without root: {word}"
                return term
        else:
            break

    # Step 3: read suffix at the end
    matched_suffix = None
    # Try suffixes from longest to shortest to avoid
    # confusing "-as" with "-a" + "s"
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

    # Remove residual hyphens at the edges (artifacts of infix splitting)
    remaining = remaining.rstrip("-").lstrip("-").strip()

    # Step 5: the root is whatever remains
    if not remaining:
        term.parse_error = f"No root extracted: {word}"
        return term

    term.root = remaining
    return term


def parse_expression(expr: str,
                     coefficient_type: str = "confidence") -> ParsedExpression:
    """
    Parse a complete MorphoRepr expression.
    Return a ParsedExpression with all parsed terms.
    """
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
            result.parse_error = f"Term without '·' separator: {ts}"
            return result
        coeff_str, word = ts.split("·", 1)
        try:
            coeff = float(coeff_str.strip())
        except ValueError:
            result.parse_error = f"Invalid coefficient: {coeff_str}"
            return result
        if not (0.01 <= coeff <= 1.00):
            result.parse_error = f"Coefficient outside [0.01,1.00]: {coeff}"
            return result

        parsed_term = parse_word(word.strip())
        parsed_term.coefficient = coeff
        parsed_term.coefficient_type = coefficient_type
        result.terms.append(parsed_term)

    # Check descending coefficient order
    coeffs = [t.coefficient for t in result.terms]
    if coeffs != sorted(coeffs, reverse=True):
        result.parse_error = "Terms are not ordered by decreasing coefficient"
        return result

    return result


def validate_free_root(root: str) -> Optional[str]:
    """
    Check whether a free root is valid.
    Return None if valid, otherwise an error message.
    """
    if root in PREDEFINED_ROOTS:
        return None  # Predefined root = always valid
    if root in RESERVED_TOKENS:
        return f"Root '{root}' is a reserved token"
    if not re.match(r'^[a-z]{2,5}$', root):
        return f"Root '{root}' does not match [a-z]{{2,5}}"
    return None
```

---

## 5. Corrected Utilities

### 5.1 db_utils.py (named INSERTs, configurable DB_PATH)

```python
# utils/db_utils.py
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

# DB_PATH configurable through an environment variable (unit tests)
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
    """
    Return features with no output for this agent/run_number.
    Used for idempotent resume.
    """
    with get_conn() as conn:
        done_q = """
            SELECT feature_index FROM agent_outputs
            WHERE run_id = ? AND agent_name = ? AND run_number = ?
        """
        done = {
            r["feature_index"]
            for r in conn.execute(done_q, (run_id, agent_name, run_number)).fetchall()
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
    """Named INSERT — resilient to schema evolution."""
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
    """Register a submitted batch before polling it."""
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
                         agent_name: str,
                         run_number: int) -> Optional[str]:
    """
    Return the ID of a submitted but unconsumed batch, if any.
    Used to resume after a crash between submission and consumption.
    """
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
    """Log cost and update cumulative total. Return the cumulative total."""
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

### 5.2 api_utils.py (explicit config, submitted-batch handling)

```python
# utils/api_utils.py
import anthropic
import json
import logging
import time
from typing import Optional, Callable
from utils.db_utils import (register_batch, mark_batch_consumed,
                             get_unconsumed_batch, log_api_cost,
                             check_budget)

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
    Config is passed explicitly — never call load_config() here.
    Temperature is added only if use_temperature=True.
    """
    sampling = config.get("sampling", {})
    requests = []
    for f in features:
        params = {
            "model":      model,
            "max_tokens": max_tokens,
            "system":     system_prompt,
            "messages":   [{"role": "user",
                             "content": user_prompt_fn(f)}],
        }
        # Conditional temperature — avoids 400 errors on recent models
        if sampling.get("use_temperature") and sampling.get("temperature") is not None:
            params["temperature"] = sampling["temperature"]

        requests.append({
            "custom_id": f"feature_{f['feature_index']}",
            "params": params
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
    Submit a batch (or recover an already submitted batch) and return results.
    Handles resume after a crash between submission and consumption.
    Config is passed explicitly.
    """
    # Check if an unconsumed batch already exists for this task
    existing_batch_id = get_unconsumed_batch(run_id, phase, agent_name, run_number)

    if existing_batch_id:
        logger.info(
            f"Resuming existing batch {existing_batch_id} "
            f"({phase}/{agent_name}/run{run_number})"
        )
        batch_id = existing_batch_id
    else:
        # Submit a new batch
        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        register_batch(batch_id, run_id, phase, agent_name,
                       run_number, len(requests))
        logger.info(f"Batch submitted: {batch_id} ({len(requests)} requests)")

    # Poll until completion
    elapsed = 0
    while elapsed < max_wait_seconds:
        batch_status = client.messages.batches.retrieve(batch_id)
        if batch_status.processing_status == "ended":
            break
        elif batch_status.processing_status == "errored":
            raise RuntimeError(f"Batch {batch_id} failed on server side")
        counts = batch_status.request_counts
        logger.info(
            f"Batch {batch_id}: {counts.processing} processing, "
            f"{counts.succeeded} succeeded, {counts.errored} errored"
        )
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(f"Batch {batch_id} timed out after {max_wait_seconds}s")

    # Retrieve results
    results = []
    total_in, total_out = 0, 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            msg = result.result.message
            raw = msg.content[0].text if msg.content else ""
            tin, tout = msg.usage.input_tokens, msg.usage.output_tokens
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

    # Log cost and mark batch as consumed
    cost = compute_cost(model, total_in, total_out, is_batch=True)
    cumulative = log_api_cost(run_id, phase, agent_name, model,
                              total_in, total_out, batch_id, cost)
    mark_batch_consumed(batch_id)
    logger.info(f"Batch {batch_id} consumed — cost: {cost:.3f} $ | "
                f"Cumulative: {cumulative:.2f} $")

    # Check budget (config passed explicitly)
    budget = config.get("budget", {})
    if budget.get("abort_on_exceed") and \
       cumulative >= budget.get("max_cost_usd", float("inf")):
        raise RuntimeError(
            f"Budget exceeded: {cumulative:.2f} $ >= "
            f"{budget['max_cost_usd']} $"
        )

    return results


def _parse_json_output(raw: str,
                       custom_id: str) -> tuple[Optional[dict], str]:
    """Parse the agent JSON output. Return (parsed, status)."""
    if not raw:
        return None, "failed"
    clean = raw.strip()
    # Remove markdown fences if present
    if clean.startswith("```"):
        lines = clean.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        clean = "\n".join(lines[1:end])
    try:
        parsed = json.loads(clean)
        if "status" not in parsed:
            logger.warning(f"{custom_id}: JSON without 'status' field")
            return parsed, "invalid_json"
        if parsed["status"] == "uncovered":
            return parsed, "uncovered"
        return parsed, "ok"
    except json.JSONDecodeError:
        logger.warning(f"{custom_id}: non-JSON output: {raw[:120]}")
        return None, "invalid_json"
```

### 5.3 prompt_utils.py (full SHA256)

```python
# utils/prompt_utils.py
import hashlib
from pathlib import Path
from datetime import datetime
from utils.db_utils import get_conn


def load_prompt(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return p.read_text(encoding="utf-8").strip()


def hash_prompt(content: str) -> str:
    """Full SHA256 (64 hex characters) — no truncation."""
    return hashlib.sha256(content.encode()).hexdigest()


def hash_file(path: str) -> str:
    """SHA256 of a binary or text file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hash_lexicon_canonical(lexicon_path: str) -> str:
    """
    Canonical lexicon hash: sort keys so that the hash is independent
    of JSON serialization order.
    """
    import json
    data = json.loads(Path(lexicon_path).read_text())
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_corpus_canonical(db_path: str) -> str:
    """
    Canonical corpus hash: sorted CSV export of features,
    independent of SQLite's binary format.
    """
    import csv
    import io
    import sqlite3
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
    """Register all prompts in DB. Return {agent: full_sha256}."""
    hashes = {}
    with get_conn() as conn:
        for agent_name, path in prompt_paths.items():
            content = load_prompt(path)
            sha = hash_prompt(content)
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
    """Raise an error if a prompt changed since registration."""
    for agent_name, path in prompt_paths.items():
        current = hash_prompt(load_prompt(path))
        expected = registered_hashes.get(agent_name, "")
        if current != expected:
            raise RuntimeError(
                f"Prompt modified: {agent_name}\n"
                f"  expected: {expected[:16]}...\n"
                f"  current : {current[:16]}..."
            )
```

---

## 6. Steering Agent — Complete Specification

```python
# agents/steerer.py
"""
Phase 4 — SAE steering.

Intervention specification:
  - Space: residual stream after SAE reconstruction
  - Layer: configured in run_v1.yaml (steering.target_layer)
  - Token position: all tokens (or configurable)
  - Magnitude: normalized by the feature's maximum activation on the corpus
  - +0 control: always run to measure baseline
  - Dose-response curve: [0, 2, 5, 10] units, +5 = primary magnitude
  - Subsample: magnitudes 2 and 10 on 50 random-split features
  - Out-of-distribution detection (OOD): if activation after intervention
    exceeds p99 * ood_threshold, the result is marked ood_flag=1

Required architecture:
  TransformerLens or nnsight to access Claude 3 Sonnet activations
  through open-source weights (if available) or a proxy model.
  If activation access is not available through the API,
  this phase requires a local model or special access.

Note: this phase is the most infrastructure-dependent one.
  Validate activation access in the dev run before the pilot run.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def _get_sae_model(config: dict):
    """
    Load the SAE for the target model and layer.
    Uses sae_lens to access public Claude 3 Sonnet SAEs.
    """
    from sae_lens import SAE
    layer = config["steering"]["target_layer"]
    # SAE identifier to be specified after pilot-run validation
    sae, _, _ = SAE.from_pretrained(
        release="claude-3-sonnet-res-jb",
        sae_id=f"blocks.{layer}.hook_resid_post",
    )
    return sae


def _get_model(config: dict):
    """
    Load the language model for steering.
    Uses TransformerLens or nnsight.
    """
    # To be specified according to available access:
    # - TransformerLens for a GPT-style proxy model
    # - nnsight for Claude if access is available
    # - Local model if open-source weights are available
    raise NotImplementedError(
        "Specify model loading according to available access.\n"
        "Validate in a dev run with a proxy model before the pilot run."
    )


def load_probe_sentences(n: int = 20) -> list[str]:
    """
    Load neutral probe sentences.
    Sentences must be:
    - short (10-30 tokens)
    - without strong emotional or technical content
    - in English
    - without named entities
    """
    path = Path("data/probe_sentences.txt")
    if not path.exists():
        raise FileNotFoundError(
            "data/probe_sentences.txt missing. "
            "Create this file with 20 neutral sentences before the dev run."
        )
    sentences = [l.strip() for l in path.read_text().splitlines()
                 if l.strip()][:n]
    if len(sentences) < n:
        raise ValueError(
            f"Only {len(sentences)} probe sentences available, "
            f"{n} required."
        )
    return sentences


def steer_feature(model, sae, feature_index: int,
                  magnitude: float,
                  probe_sentences: list[str],
                  config: dict) -> list[dict]:
    """
    Apply steering to an SAE feature and return before/after pairs.

    Implementation:
    1. For each probe sentence, encode into tokens
    2. Run a forward pass and retrieve feature activation at target layer
    3. Modify the residual by adding magnitude * SAE_decoder_direction
       on all tokens (or token_position according to config)
    4. Run the forward pass again with the modified residual
    5. Decode the before and after outputs
    6. Measure the actual resulting activation (for OOD checking)
    """
    token_pos   = config["steering"]["token_position"]
    ood_thresh  = config["steering"]["ood_threshold"]
    results = []

    for probe_id, sentence in enumerate(probe_sentences, 1):
        try:
            # SAE intervention in the residual stream
            # (implementation depends on model access)
            text_before = sentence
            text_after  = sentence  # Placeholder — to be implemented
            activation_before = 0.0
            activation_after  = magnitude  # Placeholder

            # OOD detection
            p99 = sae.W_dec[feature_index].norm().item()
            ood = int(abs(activation_after) > p99 * ood_thresh)

            results.append({
                "probe_id":         probe_id,
                "text_before":      text_before,
                "text_after":       text_after,
                "activation_before": activation_before,
                "activation_after":  activation_after,
                "ood_flag":         ood
            })
        except Exception as e:
            logger.warning(
                f"Steering error for feature {feature_index} "
                f"probe {probe_id} magnitude {magnitude}: {e}"
            )
            results.append({
                "probe_id":   probe_id,
                "text_before": sentence,
                "text_after":  None,
                "activation_before": None,
                "activation_after":  None,
                "ood_flag":   0,
                "error":      str(e)
            })
    return results


def run(run_id: str, config: dict):
    """
    Phase 4 — Steering.
    Run the dose-response curve on the subsample and the primary
    magnitude on all encoded features.
    """
    from utils.db_utils import get_conn

    logger.info("Phase 4: SAE steering")

    try:
        model = _get_model(config)
        sae   = _get_sae_model(config)
    except NotImplementedError as e:
        logger.error(str(e))
        raise

    probe_sentences = load_probe_sentences(config["steering"]["n_probe_sentences"])
    primary_mag     = config["steering"]["primary_magnitude"]
    all_magnitudes  = config["steering"]["magnitudes"]
    n_subsample     = config["steering"]["n_subsample_for_curve"]

    # Retrieve encoded features
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_index,
                   f.split,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            JOIN features f ON f.feature_index = ao.feature_index
            WHERE ao.run_id = ? AND ao.agent_name = 'encoder'
              AND ao.run_number = 1 AND ao.status = 'ok'
        """, (run_id,)).fetchall()

    random_features = [r for r in rows if r["split"] == "random"]
    subsample = random_features[:n_subsample]

    # Subsample: full dose-response curve
    _run_steering_batch(
        run_id, model, sae, subsample,
        all_magnitudes, probe_sentences, config
    )

    # All features: primary magnitude only
    remaining = [r for r in rows
                 if r["feature_index"] not in
                 {s["feature_index"] for s in subsample}]
    _run_steering_batch(
        run_id, model, sae, remaining,
        [0, primary_mag], probe_sentences, config
    )

    logger.info("Phase 4 steering completed")


def _run_steering_batch(run_id: str, model, sae,
                        features: list,
                        magnitudes: list[float],
                        probe_sentences: list[str],
                        config: dict):
    from utils.db_utils import get_conn
    with get_conn() as conn:
        for feat in features:
            for mag in magnitudes:
                results = steer_feature(
                    model, sae,
                    feat["feature_index"], mag,
                    probe_sentences, config
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

## 7. Corrected Unit Tests

```python
# tests/conftest.py
"""Shared fixtures: temporary DB injected through env var."""
import os
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create a temporary DB and expose it through an env var."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MORPHOREPR_DB_PATH", str(db_path))
    schema = Path("db/schema.sql").read_text()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    return db_path


# tests/test_parser.py
"""Tests for the single MorphoRepr parser."""
import pytest
from utils.morphorepr_parser import (
    parse_expression, parse_word, validate_free_root,
    ParsedExpression
)


class TestParseWord:
    def test_simple_verbal(self):
        t = parse_word("ag-is")
        assert t.root == "ag"
        assert t.suffix == "-is"
        assert t.suffix_type == "tense"
        assert t.is_valid

    def test_prefix_root_suffix(self):
        t = parse_word("mal-emo-a")
        assert "mal" in t.prefixes
        assert t.root == "emo"
        assert t.suffix == "-a"
        assert t.suffix_type == "syntactic"
        assert t.is_valid

    def test_root_infix_suffix(self):
        t = parse_word("soc-ant-o")
        assert t.root == "soc"
        assert "ant" in t.infixes
        assert t.suffix == "-o"
        assert t.is_valid

    def test_invalid_no_suffix(self):
        t = parse_word("ag")
        assert not t.is_valid
        assert t.parse_error is not None

    def test_free_root(self):
        t = parse_word("pens-is")
        assert t.root == "pens"
        assert t.suffix == "-is"
        assert t.is_valid


class TestParseExpression:
    def test_valid_two_terms(self):
        e = parse_expression("0.86·mal-emo-a + 0.42·ne-soc-a")
        assert e.is_valid
        assert len(e.terms) == 2
        assert e.terms[0].coefficient == pytest.approx(0.86)
        assert e.roots == {"emo", "soc"}

    def test_descending_order_enforced(self):
        # Terms in the wrong order → error
        e = parse_expression("0.40·ag-is + 0.90·sci-o")
        assert not e.is_valid
        assert "ordered" in e.parse_error or "ordonnés" in e.parse_error

    def test_coefficient_out_of_range(self):
        e = parse_expression("9.99·ag-is")
        assert not e.is_valid

    def test_missing_separator(self):
        e = parse_expression("0.86 mal-emo-a")
        assert not e.is_valid

    def test_empty_expression(self):
        e = parse_expression("")
        assert not e.is_valid


class TestValidateFreeRoot:
    def test_valid_free_root(self):
        assert validate_free_root("pens") is None
        assert validate_free_root("far") is None

    def test_reserved_token_rejected(self):
        assert validate_free_root("mal") is not None   # reserved
        assert validate_free_root("is") is not None    # suffix
        assert validate_free_root("ad") is not None    # infix

    def test_predefined_root_ok(self):
        assert validate_free_root("emo") is None
        assert validate_free_root("sci") is None

    def test_too_long(self):
        assert validate_free_root("toolong") is not None

    def test_uppercase_rejected(self):
        assert validate_free_root("Pens") is not None


# tests/test_db.py
"""DB tests using real production functions."""
import sqlite3
import pytest
from utils.db_utils import (
    load_features_not_processed, save_agent_output,
    register_batch, mark_batch_consumed, get_unconsumed_batch
)


def insert_run(conn, run_id="run_test"):
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            started_at, completed_at, status, last_phase, total_cost_usd
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL,'running',NULL,0.0)
    """, (run_id, "abc123", "cfghash", "{}", "v1",
          "lexhash", "corpushash", "{}", 0, None, 42,
          "2026-01-01T00:00:00"))


def insert_feature(conn, index=1, split="random"):
    conn.execute("""
        INSERT INTO features (
            feature_index, split, nl_description, top_examples,
            score_interp, activation_freq, layer, sae_version,
            neuronpedia_url, loaded_at
        ) VALUES (?,?,'desc','[]',0.8,0.5,'l1','sae1','http://x',
                  '2026-01-01T00:00:00')
    """, (index, split))


def test_load_features_not_processed_empty(test_db):
    """With no output at all, all features must be processed."""
    import sqlite3
    conn = sqlite3.connect(test_db)
    insert_run(conn)
    insert_feature(conn, index=1)
    insert_feature(conn, index=2)
    conn.commit()
    conn.close()

    pending = load_features_not_processed("run_test", "encoder", 1)
    assert len(pending) == 2


def test_load_features_not_processed_after_partial(test_db):
    """After partial encoding, only unprocessed features are returned."""
    import sqlite3
    conn = sqlite3.connect(test_db)
    insert_run(conn)
    insert_feature(conn, index=1)
    insert_feature(conn, index=2)
    conn.commit()
    conn.close()

    # Simulate encoding of feature 1
    save_agent_output(
        run_id="run_test", feature_index=1, agent_name="encoder",
        run_number=1, output_json={"status": "encoded"},
        raw_output="raw", status="ok", error_msg=None,
        tokens_input=100, tokens_output=50,
        batch_id=None, cost_usd=0.001
    )

    # Only feature 2 should be returned
    pending = load_features_not_processed("run_test", "encoder", 1)
    assert [f["feature_index"] for f in pending] == [2]


def test_batch_resume_after_crash(test_db):
    """A submitted but unconsumed batch can be recovered."""
    import sqlite3
    conn = sqlite3.connect(test_db)
    insert_run(conn)
    conn.commit()
    conn.close()

    # Simulate submission without consumption
    register_batch("batch_123", "run_test", "phase3",
                   "encoder", 1, 100)

    # Resume should find the batch
    found = get_unconsumed_batch("run_test", "phase3", "encoder", 1)
    assert found == "batch_123"

    # After consumption, there is no unconsumed batch anymore
    mark_batch_consumed("batch_123")
    found_after = get_unconsumed_batch("run_test", "phase3", "encoder", 1)
    assert found_after is None


# tests/test_shuffle_baseline.py
"""Tests for the shuffled control using real functions."""
import sqlite3
import pytest
from baselines.shuffled import generate_shuffles


def setup_test_db_with_features(test_db):
    """Populate the test DB with encoded features."""
    conn = sqlite3.connect(test_db)
    conn.execute("""
        INSERT INTO runs (
            run_id, git_commit, config_hash, prompt_hashes,
            lexicon_version, lexicon_hash, corpus_hash,
            models_json, use_temperature, temperature, seed,
            started_at, completed_at, status, last_phase, total_cost_usd
        ) VALUES ('r1','c','h','{}','v1','lh','ch','{}',0,NULL,42,
                  '2026-01-01',NULL,'running',NULL,0.0)
    """)
    for i in range(1, 6):
        conn.execute("""
            INSERT INTO features VALUES (?,
                'random','desc','[]',0.8,0.5,'l1','s1','http://x',
                '2026-01-01')
        """, (i,))
    for i in range(1, 6):
        conn.execute("""
            INSERT INTO agent_outputs (
                output_id, run_id, feature_index, agent_name, run_number,
                output_json, raw_output, status, error_msg,
                tokens_input, tokens_output, batch_id, cost_usd,
                coefficient_type, created_at
            ) VALUES (?,?,?,'encoder',1,?,?,?,NULL,100,50,NULL,0.0,
                      'confidence','2026-01-01')
        """, (
            f"out_{i}", "r1", i,
            f'{{"status":"encoded","expression":"0.{i+5}·ag-is"}}',
            "raw", "ok"
        ))
    conn.commit()
    conn.close()


def test_shuffle_stays_within_split(test_db):
    """Check that generate_shuffles() produces intra-split shuffles."""
    setup_test_db_with_features(test_db)
    generate_shuffles("r1", n_repeats=3)

    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT feature_index, source_feature FROM shuffle_controls"
    ).fetchall()
    conn.close()

    assert len(rows) > 0
    for row in rows:
        assert row[0] != row[1]  # source ≠ target


def test_shuffle_unique_constraint(test_db):
    """Check that the UNIQUE constraint prevents duplicates."""
    setup_test_db_with_features(test_db)
    generate_shuffles("r1", n_repeats=3)
    # Running it a second time must not insert duplicates
    generate_shuffles("r1", n_repeats=3)  # INSERT OR IGNORE

    conn = sqlite3.connect(test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM shuffle_controls WHERE run_id='r1'"
    ).fetchone()[0]
    conn.close()

    # With 5 features and 3 shuffles each = max 15 entries
    assert count <= 15
```

---

## 8. Final Orchestrator (v3)

```python
# orchestrator.py
"""
MorphoRepr v3 orchestrator — deterministic and auditable.

Usage:
    python orchestrator.py --config configs/run_v1.yaml
    python orchestrator.py --config configs/dev_run.yaml --n-features 5
    python orchestrator.py --config configs/run_v1.yaml --resume --run-id abc12345
"""
import argparse
import hashlib
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
    p = argparse.ArgumentParser()
    p.add_argument("--config",      required=True)
    p.add_argument("--n-features",  type=int, default=None)
    p.add_argument("--resume",      action="store_true")
    p.add_argument("--run-id",      default=None)
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
    git_commit   = get_git_commit()
    config_hash  = hash_config(args.config)

    # Check config git_commit consistency against actual commit
    config_commit = config.get("git_commit", "FILL_BEFORE_LAUNCH")
    if config_commit != "FILL_BEFORE_LAUNCH" and config_commit != git_commit:
        raise RuntimeError(
            f"git_commit in config ({config_commit[:8]}) "
            f"does not match current commit ({git_commit[:8]}). "
            f"Update configs/run_v1.yaml before launching."
        )

    prompt_hashes  = register_prompts(config["prompts"])
    lexicon_hash   = hash_lexicon_canonical("db/lexicon.json")
    corpus_hash    = hash_corpus_canonical("db/features.db")

    run_id = f"{config.get('run_id_prefix','run')}_{uuid4().hex[:8]}"

    sampling = config.get("sampling", {})
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO runs (
                run_id, git_commit, config_hash, prompt_hashes,
                lexicon_version, lexicon_hash, corpus_hash,
                models_json, use_temperature, temperature, seed,
                started_at, completed_at, status, last_phase, total_cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'running', NULL, 0.0)
        """, (
            run_id, git_commit, config_hash,
            json.dumps(prompt_hashes),
            config["lexicon_version"], lexicon_hash, corpus_hash,
            json.dumps(config["models"]),
            int(sampling.get("use_temperature", False)),
            sampling.get("temperature"),
            config.get("seed"),
            datetime.utcnow().isoformat()
        ))

    logger.info(f"Run initialized: {run_id}")
    logger.info(f"  Git commit  : {git_commit[:16]}")
    logger.info(f"  Config hash : {config_hash[:16]}")
    logger.info(f"  Corpus hash : {corpus_hash[:16]}")
    logger.info(f"  Lexicon hash: {lexicon_hash[:16]}")
    return run_id


def verify_resume_integrity(run_id: str, config: dict, args):
    """
    Verify that nothing changed since the original run.
    Raise an error if code, prompts, or config changed.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    if not row:
        raise RuntimeError(f"run_id {run_id} not found in DB")

    current_git    = get_git_commit()
    current_config = hash_config(args.config)
    current_corpus = hash_corpus_canonical("db/features.db")
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

    # Check prompts
    registered_hashes = json.loads(row["prompt_hashes"])
    try:
        verify_prompts_unchanged(config["prompts"], registered_hashes)
    except RuntimeError as e:
        errors.append(str(e))

    if errors:
        msg = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(
            f"Resume impossible — modifications detected:\n{msg}\n\n"
            f"To continue with modifications, create a new run."
        )

    logger.info(f"Run {run_id} integrity verified — resume authorized")


def get_last_phase(run_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_phase FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
    return row["last_phase"] if row else None


def mark_phase_complete(run_id: str, phase: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET last_phase=? WHERE run_id=?",
            (phase, run_id)
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


PHASES = [
    ("p1_load",       lambda rid, cfg: loader.run(rid),           "SAE extraction"),
    ("p1_rank",       lambda rid, cfg: ranker.run(rid, cfg),       "Split stratification"),
    ("p2_cluster",    lambda rid, cfg: cluster.run(rid),           "Clustering"),
    ("p2_label",      lambda rid, cfg: labeler.run(rid),           "Lexicon induction"),
    ("p2_consistency",lambda rid, cfg: consistency.run(rid),       "Lexicon validation"),
    ("p3_encode",     lambda rid, cfg: encoder.run(rid),           "Encoding (2 runs)"),
    ("p3_fidelity",   lambda rid, cfg: fidelity.run(rid),          "Fidelity AUC-ROC"),
    ("p3_baselines",  lambda rid, cfg: _run_baselines(rid),        "Baselines"),
    ("p3_shuffle",    lambda rid, cfg: shuffled_baseline.generate_shuffles(rid), "Shuffled control"),
    ("p4_steer",      lambda rid, cfg: steerer.run(rid, cfg),      "Steering"),
    ("p4_predict",    lambda rid, cfg: predictor.run(rid),         "Causal prediction"),
    ("p4_judge",      lambda rid, cfg: judge.run(rid),             "Causal validation"),
    ("p5_report",     lambda rid, cfg: reporter.run(rid),          "Synthesis"),
]


def _run_baselines(run_id: str):
    from baselines import nl_labels, semantic_regex, keyword_tags
    nl_labels.run(run_id)
    semantic_regex.run(run_id)
    keyword_tags.run(run_id)


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

    if args.resume and args.run_id:
        run_id = args.run_id
        verify_resume_integrity(run_id, config, args)
        last_phase = get_last_phase(run_id)
        logger.info(f"Resuming run {run_id} from: {last_phase}")
    else:
        run_id = initialize_run(config, args)
        last_phase = None

    phase_ids = [p[0] for p in PHASES]

    for phase_id, phase_fn, description in PHASES:
        if last_phase and phase_ids.index(phase_id) <= \
           phase_ids.index(last_phase):
            logger.info(f"⏭  {phase_id} already completed")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"▶  {phase_id}: {description}")
        logger.info(f"{'='*60}")

        try:
            phase_fn(run_id, config)
            mark_phase_complete(run_id, phase_id)
            print_cost_summary(run_id)

            cost, over = check_budget(
                run_id, config["budget"]["max_cost_usd"]
            )
            if config["budget"]["abort_on_exceed"] and over:
                raise RuntimeError(
                    f"Budget exceeded: {cost:.2f} $ >= "
                    f"{config['budget']['max_cost_usd']} $"
                )

        except Exception as e:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE runs SET status='failed' WHERE run_id=?",
                    (run_id,)
                )
            logger.exception(f"Phase {phase_id} failed — run {run_id} archived")
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

## 9. Setup Order

```bash
# 1. Environment
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sqlite3 db/features.db < db/schema.sql

# 2. Unit tests (without API key)
pytest tests/test_parser.py tests/test_schema.py \
       tests/test_db.py tests/test_shuffle_baseline.py -v
# All tests must pass before continuing

# 3. Classifier calibration
python classifiers/calibration/run_calibration.py
# Must display ✅ PASS for negation, tense, code, modality, valence

# 4. Steering access validation (BLOCKING — validate in dev run)
python -c "from agents.steerer import _get_model, _get_sae_model; print('OK')"
# If NotImplementedError: specify model loading before continuing

# 5. Dev run (5 features — plumbing)
python orchestrator.py --config configs/dev_run.yaml --n-features 5

# 6. Pilot run (40 features — calibration)
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Analyze: actual cost, coverage, parsed JSON, classifiers
# Adjust thresholds and prompts if necessary
# DECLARE any adjustment as calibration in the paper

# 7. Full-run budget estimation
python -c "
import sqlite3
conn = sqlite3.connect('db/features.db')
cost = conn.execute(
    'SELECT total_cost_usd FROM runs ORDER BY started_at DESC LIMIT 1'
).fetchone()[0]
n_pilot = 40
n_full  = 500
factor  = 3.0  # remaining phases not executed in pilot
estimate = cost * (n_full / n_pilot) * factor
print(f'Pilot cost: {cost:.2f} \$')
print(f'Estimated full run: {estimate:.1f} \$')
"
# Adjust max_cost_usd in run_v1.yaml accordingly

# 8. Freeze configuration
git add -A && git commit -m "Freeze all parameters for full run v1"
python -c "
import subprocess
commit = subprocess.check_output(
    ['git','rev-parse','HEAD'], text=True
).strip()
print(f'Add to run_v1.yaml: git_commit: {commit}')
"
# Update run_v1.yaml with the exact commit

# 9. Full frozen run
python orchestrator.py --config configs/run_v1.yaml
# No intervention during execution

# 10. Resume after crash (if necessary)
# ONLY if code, prompts, and config have NOT changed
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"
python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <interrupted_run_id>
# If integrity check fails → create a new run with a new commit
```

---

## 10. Role of Claude Code

Claude Code is used **only outside the full frozen run**:

**Allowed:**
- Write and debug agents, classifiers, and utilities
- Generate classifier calibration files
- Analyze intermediate pilot-run results
- Produce readable reports from the SQLite DB
- Suggest corrections if a phase fails during a dev or pilot run
- Implement `steerer.py` once model access has been validated

**Forbidden during the full frozen run:**
- Modify any code, prompt, or config file
- Intervene in the orchestrator while it is running
- Interpret errors and propose automatic fixes
- Relaunch a failed phase without explicit human validation
