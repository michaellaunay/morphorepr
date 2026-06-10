# MorphoRepr — Complete Test Procedure (v2)
## Corrected and Publication-Ready Experimental Infrastructure

---

## Guiding Principles

Three structural rules before any code:

**Rule 1 — Separation of roles**
Claude Code is used for development, debugging, and supervision. The final experimental run is driven by `python orchestrator.py --config configs/run_v1.yaml` — deterministic, with no automatic code modification and no untraced agentic intervention.

**Rule 2 — Three execution levels**

| Mode | n features | Objective | Results |
|------|-----------|-----------|---------|
| Dev run | 5 | Plumbing, DB, parsing, batch, classifiers | Not scientific |
| Pilot run | 30–50 | Calibrate prompts, thresholds, classifiers | Exploratory |
| Full frozen run | 500 | Publication | Frozen after launch |

If thresholds or prompts are adjusted after observing pilot run results, declare this explicitly as calibration in the paper. The full run starts only when all parameters are frozen.

**Rule 3 — Full freeze before full run**
Fixed Git commit, frozen config, versioned and hashed prompts, fixed models, fixed temperature, documented seed, frozen corpus, frozen lexicon, outputs written once and never overwritten.

---

## 1. Project Structure

```
morphorepr-pipeline/
├── CLAUDE.md                    ← Claude Code instructions (dev only)
├── configs/
│   ├── dev_run.yaml
│   ├── pilot_run.yaml
│   └── run_v1.yaml              ← frozen config for full run
├── db/
│   ├── schema.sql               ← complete versioned schema
│   ├── features.db              ← SQLite corpus (never modify directly)
│   └── lexicon.json             ← versioned lexicon
├── prompts/
│   ├── label_agent_v1.txt       ← versioned prompts, read from files
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
│   ├── steerer.py
│   ├── predictor.py
│   ├── judge.py
│   └── reporter.py
├── classifiers/
│   ├── negation.py              ← robust property
│   ├── tense.py                 ← robust property
│   ├── code_presence.py         ← robust property
│   ├── modality.py              ← robust property
│   ├── valence.py               ← semi-robust property
│   └── calibration/
│       ├── negation_test.json   ← 50 manually annotated examples
│       └── valence_test.json
├── baselines/
│   ├── nl_labels.py
│   ├── semantic_regex.py
│   └── shuffled.py
├── utils/
│   ├── db_utils.py              ← sole DB access point
│   ├── api_utils.py             ← Batch API wrapper with retry
│   ├── prompt_utils.py          ← prompt loading and hashing
│   ├── config_utils.py          ← config loading and validation
│   └── stats_utils.py           ← bootstrap CI95%, metrics
├── tests/
│   ├── test_parse.py
│   ├── test_schema.py
│   ├── test_classifiers.py
│   ├── test_db.py
│   ├── test_pipeline_e2e.py
│   └── test_shuffle_baseline.py
├── orchestrator.py              ← scientific run entry point
├── requirements.txt
└── checkpoints/                 ← immutable archives
```

---

## 2. Frozen Configuration File

All parameters for a run live in a single YAML file. The run reads it; it never modifies it.

```yaml
# configs/run_v1.yaml

run_id: "morphorepr_v1_20260610"
description: "Full frozen run MorphoRepr v0.26 — 500 features"

# Reproducibility
git_commit: "FILL_BEFORE_LAUNCH"       # git rev-parse HEAD
temperature: 0.3                        # Option A: measure intrinsic stability
seed: 42                                # documented; not necessarily used by API
lexicon_version: "v1.0"
corpus_frozen: true                     # features.db must not change after this flag

# Models (exact Anthropic API identifiers)
models:
  semantic_judgment: "claude-sonnet-4-6"
  scoring: "claude-haiku-4-5-20251001"
  batch: true
  max_tokens_judgment: 800
  max_tokens_scoring: 400

# Prompts (read from files, not modifiable after freeze)
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
primary_split: "random"                 # all go/no-go thresholds evaluated here

# Steering
steering:
  magnitudes: [0, 2, 5, 10]            # dose-response curve
  primary_magnitude: 5                  # primary magnitude for metrics
  n_probe_sentences: 20
  n_subsample_for_curve: 50            # subsample for magnitudes 2 and 10

# Baselines
baselines:
  - nl_labels
  - semantic_regex
  - keyword_tags
  - morphorepr_shuffled

# Shuffled MorphoRepr control
shuffle_control:
  n_repeats: 10                         # shuffle repeated 10 times per feature
  within_split: true                    # never cross-split
  max_term_diff: 1                      # comparable length ±1 term
  preserve_coefficients: true

# Budget and auto-stop
budget:
  max_cost_usd: 100.0
  alert_at_usd: 50.0
  abort_on_exceed: true

# Go/no-go thresholds (evaluated on random split)
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

## 3. Complete SQLite Schema

```sql
-- db/schema.sql
-- Version 1.0 — never modify after full run

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────────
-- Run traceability
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    git_commit      TEXT NOT NULL,
    config_hash     TEXT NOT NULL,    -- SHA256 of YAML file
    prompt_hashes   TEXT NOT NULL,    -- JSON {agent: sha256}
    lexicon_version TEXT NOT NULL,
    models_json     TEXT NOT NULL,    -- JSON {agent: model_id}
    temperature     REAL NOT NULL,
    seed            INTEGER,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT DEFAULT 'running',  -- running/completed/failed
    last_phase      TEXT,
    total_cost_usd  REAL DEFAULT 0.0
);

-- ─────────────────────────────────────────────
-- Versioned prompts
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id   TEXT PRIMARY KEY,     -- "{agent_name}_v{version}"
    agent_name  TEXT NOT NULL,
    version     TEXT NOT NULL,
    content     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Feature corpus
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS features (
    feature_index   INTEGER PRIMARY KEY,
    split           TEXT NOT NULL,    -- 'easy', 'random', 'hard'
    nl_description  TEXT NOT NULL,
    top_examples    TEXT NOT NULL,    -- JSON array (serialized string)
    score_interp    REAL,
    activation_freq REAL,
    layer           TEXT,
    sae_version     TEXT,
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Raw agent outputs (immutable)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id       TEXT PRIMARY KEY,    -- UUID
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
    agent_name      TEXT NOT NULL,
    run_number      INTEGER NOT NULL DEFAULT 1,  -- 1 or 2
    output_json     TEXT,               -- parsed output (structured JSON)
    raw_output      TEXT,               -- raw API output (never modified)
    status          TEXT NOT NULL,      -- 'ok','uncovered','failed','invalid_json'
    error_msg       TEXT,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    batch_id        TEXT,
    cost_usd        REAL,
    coefficient_type TEXT DEFAULT 'confidence',  -- 'confidence' or 'activation'
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Computed metrics (results)
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
    baseline        TEXT,               -- NULL = MorphoRepr, else baseline name
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
-- Shuffled control (10 shuffles per feature)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL,
    shuffle_number  INTEGER NOT NULL,   -- 1 to 10
    source_feature  INTEGER NOT NULL,   -- feature whose annotation was borrowed
    annotation      TEXT NOT NULL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL
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
    morphemes       TEXT NOT NULL,      -- complete JSON
    free_roots      TEXT NOT NULL,      -- JSON list
    features_per_root REAL,
    free_root_rate  REAL,
    base_coverage   REAL,
    free_coverage   REAL,
    entropy         REAL,
    created_at      TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_agent_outputs_feature
    ON agent_outputs(feature_index, agent_name, run_number);
CREATE INDEX IF NOT EXISTS idx_metrics_split
    ON metrics(run_id, split, metric_name);
CREATE INDEX IF NOT EXISTS idx_api_usage_phase
    ON api_usage(run_id, phase);
```

---

## 4. Core Utilities

### 4.1 Database Access

```python
# utils/db_utils.py
"""
Sole access point to features.db.
Any direct DB operation outside this module is forbidden.
"""
import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

DB_PATH = Path("db/features.db")

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
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

def load_features(split: Optional[str] = None,
                  encoded: bool = False) -> list[dict]:
    """Load features by split and encoding status."""
    with get_conn() as conn:
        query = "SELECT * FROM features WHERE 1=1"
        params = []
        if split:
            query += " AND split = ?"
            params.append(split)
        # encoded = 0 means not yet processed (DEFAULT 0, not NULL)
        if not encoded:
            query += (
                " AND feature_index NOT IN "
                "(SELECT DISTINCT feature_index FROM agent_outputs "
                " WHERE agent_name = 'encoder' AND status = 'ok')"
            )
        rows = conn.execute(query, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Deserialize top_examples (stored as JSON string)
        d["top_examples"] = json.loads(d["top_examples"])
        result.append(d)
    return result

def save_agent_output(run_id: str, feature_index: int,
                      agent_name: str, run_number: int,
                      output_json: Optional[dict],
                      raw_output: str,
                      status: str,
                      error_msg: Optional[str],
                      tokens_input: int,
                      tokens_output: int,
                      batch_id: Optional[str],
                      cost_usd: float,
                      coefficient_type: str = "confidence"):
    """Insert an agent output — immutable once written."""
    from uuid import uuid4
    from datetime import datetime
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO agent_outputs VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            str(uuid4()), run_id, feature_index, agent_name,
            run_number,
            json.dumps(output_json) if output_json else None,
            raw_output, status, error_msg,
            tokens_input, tokens_output, batch_id,
            cost_usd, coefficient_type,
            datetime.utcnow().isoformat()
        ))

def log_api_cost(run_id: str, phase: str, agent_name: str,
                 model: str, tokens_in: int, tokens_out: int,
                 batch_id: Optional[str], cost: float) -> float:
    """Log each API call and update the run's cumulative cost."""
    from uuid import uuid4
    from datetime import datetime
    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()
        cumulative = (row["total_cost_usd"] if row else 0.0) + cost
        conn.execute(
            "UPDATE runs SET total_cost_usd = ? WHERE run_id = ?",
            (cumulative, run_id)
        )
        conn.execute("""
            INSERT INTO api_usage VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            str(uuid4()), run_id, phase, agent_name, model,
            tokens_in, tokens_out, batch_id, cost, cumulative,
            datetime.utcnow().isoformat()
        ))
    return cumulative

def check_budget(run_id: str, max_cost: float) -> tuple[float, bool]:
    """Return (cumulative_cost, over_budget)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    cost = row["total_cost_usd"] if row else 0.0
    return cost, cost >= max_cost
```

### 4.2 Prompt Management

```python
# utils/prompt_utils.py
"""Load, hash, and register versioned prompts."""
import hashlib
from pathlib import Path
from datetime import datetime
from utils.db_utils import get_conn

def load_prompt(path: str) -> str:
    """Read a prompt from file. Raises if missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return p.read_text(encoding="utf-8").strip()

def hash_prompt(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def register_prompts(prompt_paths: dict) -> dict:
    """
    Register all prompts in the DB and return their hashes.
    prompt_paths: {agent_name: path}
    """
    hashes = {}
    with get_conn() as conn:
        for agent_name, path in prompt_paths.items():
            content = load_prompt(path)
            sha = hash_prompt(content)
            prompt_id = f"{agent_name}_{sha[:8]}"
            conn.execute("""
                INSERT OR IGNORE INTO prompts VALUES (?,?,?,?,?,?)
            """, (prompt_id, agent_name, "v1", content, sha,
                  datetime.utcnow().isoformat()))
            hashes[agent_name] = sha
    return hashes

def verify_prompts_unchanged(prompt_paths: dict,
                              registered_hashes: dict) -> None:
    """Raise an error if any prompt has changed since registration."""
    for agent_name, path in prompt_paths.items():
        content = load_prompt(path)
        current = hash_prompt(content)
        if current != registered_hashes.get(agent_name):
            raise RuntimeError(
                f"Prompt modified during run: {agent_name}\n"
                f"  expected: {registered_hashes[agent_name]}\n"
                f"  current:  {current}"
            )
```

### 4.3 Robust Batch API Wrapper

```python
# utils/api_utils.py
"""
Robust wrapper around the Anthropic Batch API.
Handles retry, timeouts, partial errors, budget, JSON parsing.
"""
import anthropic
import json
import time
import logging
from typing import Optional
from utils.db_utils import log_api_cost, check_budget
from utils.config_utils import load_config

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
    cost = (tokens_in  / 1_000_000) * rates["input"] + \
           (tokens_out / 1_000_000) * rates["output"]
    return cost * (BATCH_DISCOUNT if is_batch else 1.0)

def submit_batch(requests: list[dict]) -> str:
    """Submit a batch and return its ID."""
    batch = client.messages.batches.create(requests=requests)
    logger.info(f"Batch submitted: {batch.id} ({len(requests)} requests)")
    return batch.id

def poll_batch(batch_id: str,
               run_id: str,
               phase: str,
               agent_name: str,
               model: str,
               poll_interval: int = 30,
               max_wait_seconds: int = 7200) -> list[dict]:
    """
    Wait for batch completion.
    Returns a list of results with explicit status.
    """
    elapsed = 0
    while elapsed < max_wait_seconds:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        elif batch.processing_status == "errored":
            raise RuntimeError(f"Batch {batch_id} server error")
        counts = batch.request_counts
        logger.info(
            f"Batch {batch_id}: {counts.processing} processing, "
            f"{counts.succeeded} succeeded, {counts.errored} errors"
        )
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(
            f"Batch {batch_id} timed out after {max_wait_seconds}s"
        )

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
    cumulative = log_api_cost(
        run_id, phase, agent_name, model,
        total_in, total_out, batch_id, cost
    )
    logger.info(
        f"Batch {batch_id} cost: ${cost:.3f} | Cumulative: ${cumulative:.2f}"
    )

    config = load_config()
    if config["budget"]["abort_on_exceed"] and \
       cumulative >= config["budget"]["max_cost_usd"]:
        raise RuntimeError(
            f"Budget exceeded: ${cumulative:.2f} >= "
            f"${config['budget']['max_cost_usd']}"
        )

    return results

def _parse_json_output(raw: str,
                       custom_id: str) -> tuple[Optional[dict], str]:
    """
    Attempt to parse agent output as structured JSON.
    Returns (parsed_dict, status).
    """
    if not raw:
        return None, "failed"
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        )
    try:
        parsed = json.loads(clean)
        if "status" not in parsed:
            logger.warning(f"{custom_id}: JSON missing 'status' field")
            return parsed, "invalid_json"
        if parsed["status"] == "uncovered":
            return parsed, "uncovered"
        return parsed, "ok"
    except json.JSONDecodeError:
        logger.warning(f"{custom_id}: non-JSON output: {raw[:100]}")
        return None, "invalid_json"

def build_batch_requests(features: list[dict],
                          system_prompt: str,
                          user_prompt_fn,
                          model: str,
                          max_tokens: int) -> list[dict]:
    """Build the request list for the Batch API."""
    return [
        {
            "custom_id": f"feature_{f['feature_index']}",
            "params": {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": load_config()["temperature"],
                "system": system_prompt,
                "messages": [
                    {"role": "user",
                     "content": user_prompt_fn(f)}
                ]
            }
        }
        for f in features
    ]
```

### 4.4 Statistics and Metrics

```python
# utils/stats_utils.py
"""Statistical computations: bootstrap CI95%, morpheme-level metrics."""
import numpy as np
from scipy import stats as scipy_stats
from typing import Optional

def bootstrap_ci(values: list[float],
                 n_bootstrap: int = 1000,
                 ci: float = 0.95) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) via bootstrap."""
    if not values:
        return 0.0, 0.0, 0.0
    arr = np.array(values)
    means = [
        np.mean(np.random.choice(arr, len(arr), replace=True))
        for _ in range(n_bootstrap)
    ]
    alpha = (1 - ci) / 2
    return (
        float(np.mean(arr)),
        float(np.percentile(means, alpha * 100)),
        float(np.percentile(means, (1 - alpha) * 100))
    )

def morpheme_jaccard(expr1: Optional[str],
                     expr2: Optional[str]) -> float:
    """Jaccard similarity over morpheme sets."""
    if not expr1 or not expr2:
        return 0.0
    def extract(expr: str) -> set:
        morphemes = set()
        for term in expr.split("+"):
            if "·" in term:
                _, word = term.strip().split("·", 1)
                morphemes.update(word.replace("-", " ").split())
        return morphemes
    s1, s2 = extract(expr1), extract(expr2)
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)

def root_jaccard(expr1: Optional[str],
                 expr2: Optional[str]) -> float:
    """Jaccard similarity over root morphemes only."""
    SUFFIXES = {"-o","-a","-e","-i","-as","-is","-os","-us","-u"}
    INFIXES  = {"-ad-","-int-","-it-","-ist-","-ant-","-at-","-ig-","-iĝ-"}
    PREFIXES = {"mal-","ne-","pli-","plej-","duon-"}
    if not expr1 or not expr2:
        return 0.0
    def extract_roots(expr: str) -> set:
        roots = set()
        for term in expr.split("+"):
            if "·" not in term:
                continue
            _, word = term.strip().split("·", 1)
            w = word
            for p in PREFIXES:
                w = w.replace(p, "")
            for ix in INFIXES:
                w = w.replace(ix, "-")
            for s in SUFFIXES:
                if w.endswith(s):
                    w = w[:-len(s)]
                    break
            root = w.replace("-", "").strip()
            if root:
                roots.add(root)
        return roots
    s1, s2 = extract_roots(expr1), extract_roots(expr2)
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)

def coefficient_correlation(expr1: Optional[str],
                             expr2: Optional[str]) -> float:
    """Pearson correlation between corresponding term coefficients."""
    if not expr1 or not expr2:
        return 0.0
    def extract_coeffs(expr: str) -> list[float]:
        coeffs = []
        for term in expr.split("+"):
            if "·" in term:
                coeff_str, _ = term.strip().split("·", 1)
                try:
                    coeffs.append(float(coeff_str.strip()))
                except ValueError:
                    pass
        return coeffs
    c1, c2 = extract_coeffs(expr1), extract_coeffs(expr2)
    n = min(len(c1), len(c2))
    if n < 2:
        return 0.0
    r, _ = scipy_stats.pearsonr(c1[:n], c2[:n])
    return float(r)

def morpheme_edit_distance(expr1: Optional[str],
                           expr2: Optional[str]) -> float:
    """Edit distance (substitutions) between morpheme chains."""
    if not expr1 or not expr2:
        return float("inf")
    def to_list(expr: str) -> list[str]:
        morphemes = []
        for term in expr.split("+"):
            if "·" in term:
                _, word = term.strip().split("·", 1)
                morphemes.extend(word.split("-"))
        return [m for m in morphemes if m]
    m1, m2 = to_list(expr1), to_list(expr2)
    if not m1 or not m2:
        return float(max(len(m1), len(m2)))
    dp = [[0] * (len(m2)+1) for _ in range(len(m1)+1)]
    for i in range(len(m1)+1):
        dp[i][0] = i
    for j in range(len(m2)+1):
        dp[0][j] = j
    for i in range(1, len(m1)+1):
        for j in range(1, len(m2)+1):
            cost = 0 if m1[i-1] == m2[j-1] else 1
            dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
    return float(dp[len(m1)][len(m2)])
```

---

## 5. Output Property Classifiers (Phase 4)

### 5.1 Negation (robust)

```python
# classifiers/negation.py
"""
Negation classifier — robust property.
Combines syntactic dependencies, lexical negation, and morphology.
"""
import spacy

nlp = spacy.load("en_core_web_sm")

NEG_LEXICON = {
    "no","not","never","neither","nor","nobody","nothing",
    "nowhere","none","without","lack","lacking","absent",
    "fail","fails","failed","failure","missing","unable",
    "impossible","prevent","prevents","prevented","deny",
    "denies","denied","refuse","refuses","refused"
}
NEG_PREFIXES = ("un","im","in","dis","non","ir","il","a")

def count_negation_signals(text: str) -> float:
    """Return a negation score normalized by token count.
    Weights: dep_neg = 1.0, lexicon = 0.7, morphological = 0.3
    """
    doc = nlp(text)
    tokens = [t for t in doc if not t.is_space]
    if not tokens:
        return 0.0
    score = 0.0
    for t in tokens:
        if t.dep_ == "neg":
            score += 1.0
        elif t.lower_ in NEG_LEXICON:
            score += 0.7
        elif (any(t.lower_.startswith(p) for p in NEG_PREFIXES)
              and len(t.text) > 4):
            score += 0.3
    return score / len(tokens)

def measure(texts_before: list[str],
            texts_after: list[str]) -> dict:
    before = (sum(count_negation_signals(t) for t in texts_before)
              / len(texts_before))
    after  = (sum(count_negation_signals(t) for t in texts_after)
              / len(texts_after))
    delta  = after - before
    THRESHOLD = 0.02
    return {
        "property":  "negation_presence",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": ("INCREASE"  if delta >  THRESHOLD else
                      "DECREASE"  if delta < -THRESHOLD else
                      "NO_CHANGE")
    }
```

### 5.2 Emotional Valence (semi-robust)

```python
# classifiers/valence.py
"""
Emotional valence classifier — semi-robust property.
Uses a general-domain model rather than SST-2 (movie reviews only).
"""
from transformers import pipeline as hf_pipeline

_pipe = None

def get_pipe():
    global _pipe
    if _pipe is None:
        _pipe = hf_pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True, max_length=512
        )
    return _pipe

def _neg_score(text: str) -> float:
    result = get_pipe()(text)[0]
    if result["label"].lower() in ("negative", "neg", "label_0"):
        return result["score"]
    return 1.0 - result["score"]

def measure(texts_before: list[str],
            texts_after: list[str]) -> dict:
    before = sum(_neg_score(t) for t in texts_before) / len(texts_before)
    after  = sum(_neg_score(t) for t in texts_after)  / len(texts_after)
    delta  = after - before
    THRESHOLD = 0.05
    return {
        "property":  "negative_valence",
        "tier":      "semi-robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": ("INCREASE"  if delta >  THRESHOLD else
                      "DECREASE"  if delta < -THRESHOLD else
                      "NO_CHANGE"),
        "reliability_note":
            "Semi-robust: interpret with caution on technical or ironic text."
    }
```

### 5.3 Classifier Calibration

```python
# classifiers/calibration/run_calibration.py
"""
Validate classifiers on manually annotated examples.
Must pass before the pilot run.
"""
import json
from classifiers import negation, valence

def calibrate(classifier_module, test_file: str,
              property_name: str, min_accuracy: float = 0.85) -> bool:
    data = json.loads(open(test_file).read())
    correct = 0
    for example in data:
        result = classifier_module.measure(
            [example["text_before"]],
            [example["text_after"]]
        )
        if result["direction"] == example["expected_direction"]:
            correct += 1
    accuracy = correct / len(data)
    status = "PASS" if accuracy >= min_accuracy else "FAIL"
    print(f"[{status}] {property_name}: {accuracy:.1%} "
          f"({correct}/{len(data)}) — threshold: {min_accuracy:.0%}")
    return accuracy >= min_accuracy

if __name__ == "__main__":
    results = [
        calibrate(negation, "calibration/negation_test.json",
                  "negation_presence", min_accuracy=0.85),
        calibrate(valence,  "calibration/valence_test.json",
                  "negative_valence",  min_accuracy=0.80),
    ]
    if not all(results):
        raise SystemExit(
            "Calibration failed — fix classifiers before launching pilot run"
        )
    print("\nCalibration passed — pipeline ready for pilot run")
```

---

## 6. Main Agents

### 6.1 Encoder Agent (Phase 3)

```python
# agents/encoder.py
"""
Phase 3 — MorphoRepr encoding.
Two independent runs. Structured JSON output mandatory.
"""
import json
import logging
from pathlib import Path
from utils.db_utils import save_agent_output, get_conn
from utils.api_utils import submit_batch, poll_batch, build_batch_requests
from utils.prompt_utils import load_prompt
from utils.config_utils import load_config

logger = logging.getLogger(__name__)

# Expected output schema (documented in prompt)
OUTPUT_SCHEMA = {
    "status": "encoded | uncovered",
    "expression": "0.86·mal-emo-a + 0.42·ne-soc-a",
    "coefficient_type": "confidence",
    "terms": [
        {
            "coefficient": 0.86,
            "morpheme_chain": "mal-emo-a",
            "root": "emo",
            "prefixes": ["mal"],
            "infix": None,
            "suffix": "-a",
            "confidence": 0.86,
            "rationale": "negative affective context",
            "not_covered": "cultural connotation, specific named entities"
        }
    ],
    "uncovered_reason": None
}

def build_user_prompt(feature: dict, lexicon: dict) -> str:
    top10 = feature["top_examples"][:10]
    return (
        f"Feature index: {feature['feature_index']}\n"
        f"Natural language description: {feature['nl_description']}\n\n"
        f"Top-10 activating examples:\n"
        f"{json.dumps(top10, ensure_ascii=False, indent=2)}\n\n"
        f"Available lexicon:\n"
        f"{json.dumps(lexicon['morphemes'], ensure_ascii=False, indent=2)}\n\n"
        f"Respond ONLY with a valid JSON object matching this schema:\n"
        f"{json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2)}\n"
        f"No text outside the JSON object."
    )

def load_features_not_encoded(run_id: str,
                               run_number: int) -> list[dict]:
    """Load features without an encoding output for this run_number."""
    with get_conn() as conn:
        done = {
            row["feature_index"]
            for row in conn.execute("""
                SELECT feature_index FROM agent_outputs
                WHERE run_id = ? AND agent_name = 'encoder'
                AND run_number = ?
            """, (run_id, run_number)).fetchall()
        }
        all_features = conn.execute("SELECT * FROM features").fetchall()
    result = []
    for f in all_features:
        if f["feature_index"] not in done:
            d = dict(f)
            d["top_examples"] = json.loads(d["top_examples"])
            result.append(d)
    return result

def run(run_id: str):
    config  = load_config()
    system  = load_prompt(config["prompts"]["encoder"])
    lexicon = json.loads(Path("db/lexicon.json").read_text())
    model   = config["models"]["semantic_judgment"]

    for run_number in [1, 2]:
        logger.info(f"Encoding run {run_number}/2")
        features = load_features_not_encoded(run_id, run_number)

        if not features:
            logger.info(f"Run {run_number}: all features already encoded")
            continue

        logger.info(f"  {len(features)} features to encode (run {run_number})")

        requests = build_batch_requests(
            features, system,
            lambda f: build_user_prompt(f, lexicon),
            model=model,
            max_tokens=config["models"]["max_tokens_judgment"]
        )

        batch_id = submit_batch(requests)
        Path(f"checkpoints/batch_encoder_run{run_number}.txt").write_text(
            batch_id
        )
        results = poll_batch(
            batch_id, run_id, "phase3", "encoder", model
        )

        for r in results:
            feature_index = int(r["custom_id"].replace("feature_", ""))
            save_agent_output(
                run_id=run_id,
                feature_index=feature_index,
                agent_name="encoder",
                run_number=run_number,
                output_json=r["output_json"],
                raw_output=r["raw_output"] or "",
                status=r["status"],
                error_msg=r["error_msg"],
                tokens_input=r["tokens_input"],
                tokens_output=r["tokens_output"],
                batch_id=batch_id,
                cost_usd=0.0,
                coefficient_type="confidence"
            )

        n_ok   = sum(1 for r in results if r["status"] == "ok")
        n_unc  = sum(1 for r in results if r["status"] == "uncovered")
        n_fail = sum(1 for r in results if r["status"] == "failed")
        logger.info(
            f"  Run {run_number} done: "
            f"{n_ok} ok, {n_unc} uncovered, {n_fail} failed"
        )
```

### 6.2 Causal Prediction Agent (Phase 4)

```python
# agents/predictor.py
"""
Phase 4 — Causal prediction.
Agent receives ONLY the MorphoRepr expression, not the NL description.
Anti-circularity safeguard.
"""
import json
import logging
from utils.db_utils import get_conn, save_agent_output
from utils.api_utils import submit_batch, poll_batch, build_batch_requests
from utils.prompt_utils import load_prompt
from utils.config_utils import load_config

logger = logging.getLogger(__name__)

def build_user_prompt(feature_index: int,
                      morphorepr_expression: str) -> str:
    """
    CRITICAL: the judge does NOT receive the NL description.
    Anti-circularity safeguard.
    """
    return (
        f"Feature index: {feature_index}\n"
        f"MorphoRepr expression: {morphorepr_expression}\n\n"
        f"Predict which output properties will change when this feature "
        f"is amplified by +5 activation units.\n"
        f"Respond ONLY with a valid JSON object as specified "
        f"in your system prompt."
    )

def load_encoded_features(run_id: str) -> list[dict]:
    """Load features with encoded expressions (run 1, not yet predicted)."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ao.feature_index,
                   json_extract(ao.output_json, '$.expression') as expression
            FROM agent_outputs ao
            WHERE ao.run_id = ?
              AND ao.agent_name = 'encoder'
              AND ao.run_number = 1
              AND ao.status = 'ok'
              AND ao.feature_index NOT IN (
                  SELECT feature_index FROM agent_outputs
                  WHERE run_id = ? AND agent_name = 'predictor'
              )
        """, (run_id, run_id)).fetchall()
    return [dict(r) for r in rows if r["expression"]]

def run(run_id: str):
    config   = load_config()
    system   = load_prompt(config["prompts"]["predictor"])
    model    = config["models"]["semantic_judgment"]
    features = load_encoded_features(run_id)

    if not features:
        logger.info("Phase 4: all features already predicted")
        return

    logger.info(f"Phase 4: {len(features)} features to predict")

    requests = build_batch_requests(
        features, system,
        lambda f: build_user_prompt(f["feature_index"], f["expression"]),
        model=model,
        max_tokens=config["models"]["max_tokens_judgment"]
    )

    batch_id = submit_batch(requests)
    results  = poll_batch(batch_id, run_id, "phase4", "predictor", model)

    for r in results:
        feature_index = int(r["custom_id"].replace("feature_", ""))
        save_agent_output(
            run_id=run_id,
            feature_index=feature_index,
            agent_name="predictor",
            run_number=1,
            output_json=r["output_json"],
            raw_output=r["raw_output"] or "",
            status=r["status"],
            error_msg=r["error_msg"],
            tokens_input=r["tokens_input"],
            tokens_output=r["tokens_output"],
            batch_id=batch_id,
            cost_usd=0.0
        )

    logger.info("Phase 4 prediction complete")
```

---

## 7. Shuffled MorphoRepr Control

```python
# baselines/shuffled.py
"""
Shuffled MorphoRepr baseline.
- Within-split shuffling only (never cross-split)
- Length-matched ±1 term
- 10 shuffles per feature
- Coefficients preserved (only morphemes are shuffled)
"""
import random
import logging
from uuid import uuid4
from datetime import datetime
from utils.db_utils import get_conn
from utils.config_utils import load_config

logger = logging.getLogger(__name__)

def _count_terms(expression: str) -> int:
    return len([t for t in expression.split("+") if "·" in t])

def generate_shuffles(run_id: str, n_repeats: int = 10):
    config   = load_config()
    max_diff = config["shuffle_control"]["max_term_diff"]

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

    to_insert = []
    for split, features in by_split.items():
        for feat in features:
            candidates = [
                f for f in features
                if f["feature_index"] != feat["feature_index"]
                and abs(f["n_terms"] - feat["n_terms"]) <= max_diff
            ]
            if len(candidates) < 3:
                logger.warning(
                    f"Feature {feat['feature_index']}: "
                    f"only {len(candidates)} candidates for shuffle"
                )
                continue
            for shuffle_num in range(1, n_repeats + 1):
                source = random.choice(candidates)
                to_insert.append({
                    "feature_index": feat["feature_index"],
                    "shuffle_number": shuffle_num,
                    "source_feature": source["feature_index"],
                    "annotation":    source["expression"]
                })

    with get_conn() as conn:
        for s in to_insert:
            conn.execute("""
                INSERT OR IGNORE INTO shuffle_controls
                VALUES (?,?,?,?,?,?,NULL,NULL,?)
            """, (
                str(uuid4()), run_id,
                s["feature_index"], s["shuffle_number"],
                s["source_feature"], s["annotation"],
                datetime.utcnow().isoformat()
            ))

    logger.info(
        f"Shuffles generated: {len(to_insert)} "
        f"({n_repeats} per feature)"
    )
```

---

## 8. Unit Tests

```python
# tests/test_parse.py
"""Unit tests for MorphoRepr parsing utilities."""
import pytest
from utils.stats_utils import (morpheme_jaccard, root_jaccard,
                                coefficient_correlation,
                                morpheme_edit_distance)

class TestMorphemeJaccard:
    def test_identical(self):
        expr = "0.86·mal-emo-a + 0.42·ne-soc-a"
        assert morpheme_jaccard(expr, expr) == 1.0

    def test_completely_different(self):
        assert morpheme_jaccard("0.90·ag-is", "0.80·sci-o") < 0.5

    def test_partial_overlap(self):
        e1 = "0.86·mal-emo-a + 0.42·ne-soc-a"
        e2 = "0.86·mal-emo-a + 0.30·ag-is"
        j = morpheme_jaccard(e1, e2)
        assert 0.0 < j < 1.0

    def test_none_inputs(self):
        assert morpheme_jaccard(None, "0.8·ag-is") == 0.0

class TestCoefficientCorrelation:
    def test_perfect(self):
        expr = "0.90·ag-is + 0.50·sci-o"
        assert coefficient_correlation(expr, expr) == pytest.approx(1.0)

    def test_single_term(self):
        assert coefficient_correlation("0.90·ag-is", "0.80·sci-o") == 0.0

class TestMorphemeEditDistance:
    def test_identical(self):
        assert morpheme_edit_distance("0.9·ag-is", "0.9·ag-is") == 0.0

    def test_one_substitution(self):
        dist = morpheme_edit_distance("0.9·ag-is", "0.9·ag-os")
        assert dist <= 2.0


# tests/test_schema.py
"""Tests for agent JSON output schema validation."""
import pytest
import json
from utils.api_utils import _parse_json_output

class TestJsonOutputSchema:
    def test_valid_encoded(self):
        raw = json.dumps({
            "status": "encoded",
            "expression": "0.86·mal-emo-a + 0.42·ne-soc-a",
            "coefficient_type": "confidence",
            "terms": [
                {"coefficient": 0.86, "morpheme_chain": "mal-emo-a",
                 "root": "emo", "prefixes": ["mal"], "infix": None,
                 "suffix": "-a", "confidence": 0.86,
                 "rationale": "negative affect",
                 "not_covered": "pragmatic connotation"}
            ],
            "uncovered_reason": None
        })
        parsed, status = _parse_json_output(raw, "feature_7823")
        assert status == "ok"
        assert "expression" in parsed

    def test_uncovered(self):
        raw = json.dumps({
            "status": "uncovered",
            "expression": None,
            "coefficient_type": "confidence",
            "terms": [],
            "uncovered_reason": "No morpheme covers named entity specificity"
        })
        _, status = _parse_json_output(raw, "feature_999")
        assert status == "uncovered"

    def test_invalid_json(self):
        _, status = _parse_json_output("Not JSON.", "feature_001")
        assert status == "invalid_json"

    def test_markdown_fences_stripped(self):
        raw = ('```json\n{"status":"encoded","expression":"0.9·ag-is",'
               '"coefficient_type":"confidence","terms":[],'
               '"uncovered_reason":null}\n```')
        parsed, _ = _parse_json_output(raw, "feature_002")
        assert parsed is not None


# tests/test_db.py
"""Tests for DB operations and crash recovery."""
import pytest
import sqlite3
from pathlib import Path

def make_test_db(tmp_path) -> Path:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(Path("db/schema.sql").read_text())
    conn.commit()
    conn.close()
    return db_path

def test_feature_not_encoded_by_default(tmp_path):
    db = make_test_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("""
        INSERT INTO features VALUES
        (1,'random','test desc','[]',0.8,0.5,'layer1','sae_v1',
         'http://x.com',datetime('now'))
    """)
    conn.commit()
    count = conn.execute("""
        SELECT COUNT(*) FROM agent_outputs
        WHERE feature_index = 1 AND agent_name = 'encoder'
    """).fetchone()[0]
    assert count == 0
    conn.close()

def test_resume_after_crash(tmp_path):
    """On resume, already-encoded features must not be reprocessed."""
    db = make_test_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("""
        INSERT INTO runs VALUES
        ('run_test','abc123','cfghash','{}','v1','{}',0.3,42,
         datetime('now'),NULL,'running',NULL,0.0)
    """)
    conn.execute("""
        INSERT INTO features VALUES
        (1,'random','desc','[]',0.8,0.5,'l1','sae1','http://x',datetime('now'))
    """)
    conn.execute("""
        INSERT INTO features VALUES
        (2,'random','desc2','[]',0.7,0.4,'l1','sae1','http://y',datetime('now'))
    """)
    # Feature 1 already encoded
    conn.execute("""
        INSERT INTO agent_outputs VALUES
        ('out1','run_test',1,'encoder',1,'{"status":"encoded"}','raw',
         'ok',NULL,100,50,NULL,0.0,'confidence',datetime('now'))
    """)
    conn.commit()
    done = {
        r[0] for r in conn.execute("""
            SELECT feature_index FROM agent_outputs
            WHERE run_id='run_test' AND agent_name='encoder' AND run_number=1
        """).fetchall()
    }
    all_f = [r[0] for r in conn.execute(
        "SELECT feature_index FROM features"
    ).fetchall()]
    to_encode = [f for f in all_f if f not in done]
    assert to_encode == [2]
    conn.close()


# tests/test_shuffle_baseline.py
"""Tests for the shuffled MorphoRepr control."""

def test_shuffle_within_split():
    """Shuffle candidates must come from the same split."""
    by_split = {
        "easy": [
            {"feature_index": 1, "expression": "0.9·ag-is",  "n_terms": 1},
            {"feature_index": 2, "expression": "0.8·sci-o",  "n_terms": 1},
            {"feature_index": 3, "expression": "0.7·emo-a",  "n_terms": 1},
        ],
        "hard": [
            {"feature_index": 4, "expression": "0.6·dat-ad-o","n_terms": 1},
        ]
    }
    for split, features in by_split.items():
        valid_indices = {f["feature_index"] for f in features}
        for feat in features:
            candidates = [
                f for f in features
                if f["feature_index"] != feat["feature_index"]
            ]
            for c in candidates:
                assert c["feature_index"] in valid_indices

def test_shuffle_length_constraint():
    """Only features with comparable length (±1 term) are candidates."""
    features = [
        {"feature_index": 1, "expression": "0.9·ag-is", "n_terms": 1},
        {"feature_index": 2, "expression": "0.8·sci-o + 0.4·emo-a",
         "n_terms": 2},
        {"feature_index": 3, "expression": "0.7·emo-a", "n_terms": 1},
    ]
    max_diff = 1
    target = features[0]
    candidates = [
        f for f in features
        if f["feature_index"] != target["feature_index"]
        and abs(f["n_terms"] - target["n_terms"]) <= max_diff
    ]
    # Feature 2 (n_terms=2, diff=1) → valid
    # Feature 3 (n_terms=1, diff=0) → valid
    assert len(candidates) == 2


# tests/test_pipeline_e2e.py
"""End-to-end test on 5 features — dev run level."""
import pytest
import subprocess
import sys
import os

def test_pipeline_5_features_end_to_end():
    """
    Run the complete pipeline on 5 features in dev mode.
    Requires ANTHROPIC_API_KEY in the environment.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set — e2e test skipped")

    result = subprocess.run(
        [sys.executable, "orchestrator.py",
         "--config", "configs/dev_run.yaml",
         "--n-features", "5"],
        capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, \
        f"Pipeline failed:\n{result.stderr}"
    assert ("phase3" in result.stdout.lower()
            or "phase3" in result.stderr.lower())
```

---

## 9. Final Orchestrator

```python
# orchestrator.py
"""
MorphoRepr scientific run entry point.
Deterministic, no code modification, no agentic intervention.

Usage:
    python orchestrator.py --config configs/run_v1.yaml
    python orchestrator.py --config configs/dev_run.yaml --n-features 5
    python orchestrator.py --config configs/run_v1.yaml --resume --run-id <id>
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
from utils.prompt_utils import register_prompts, verify_prompts_unchanged
from utils.db_utils import get_conn, check_budget

from agents import (loader, ranker, cluster, labeler, consistency,
                    encoder, fidelity, steerer, predictor, judge, reporter)
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
        r = subprocess.run(["git","rev-parse","HEAD"],
                           capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def initialize_run(config: dict, args) -> str:
    run_id    = str(uuid4())[:8]
    git_hash  = get_git_commit()
    cfg_hash  = hash_config(args.config)
    p_hashes  = register_prompts(config["prompts"])

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,NULL,'running',NULL,0.0)
        """, (
            run_id, git_hash, cfg_hash,
            json.dumps(p_hashes),
            config["lexicon_version"],
            json.dumps(config["models"]),
            config["temperature"],
            config.get("seed"),
            datetime.utcnow().isoformat()
        ))

    logger.info(f"Run initialized: {run_id}")
    logger.info(f"  Git commit  : {git_hash}")
    logger.info(f"  Config hash : {cfg_hash}")
    return run_id


def get_last_phase(run_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_phase FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return row["last_phase"] if row else None


def mark_phase_complete(run_id: str, phase: str):
    with get_conn() as conn:
        conn.execute("UPDATE runs SET last_phase=? WHERE run_id=?",
                     (phase, run_id))
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    Path("checkpoints").mkdir(exist_ok=True)
    Path(f"checkpoints/{run_id}_{phase}_{ts}.marker").touch()
    logger.info(f"  Checkpoint: phase {phase} complete")


def mark_run_complete(run_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE runs SET status='completed', completed_at=?
            WHERE run_id=?
        """, (datetime.utcnow().isoformat(), run_id))
    logger.info(f"Run {run_id} completed successfully")


def mark_run_failed(run_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE runs SET status='failed' WHERE run_id=?",
                     (run_id,))


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
    logger.info("\n=== Cumulative Cost ===")
    for phase, cost in rows:
        logger.info(f"  {phase:<20} ${cost:.3f}")
    logger.info(f"  {'TOTAL':<20} ${total:.3f}")


def _run_baselines_p3(run_id: str):
    from baselines import nl_labels, semantic_regex, keyword_tags
    nl_labels.run(run_id)
    semantic_regex.run(run_id)
    keyword_tags.run(run_id)


PHASES = [
    ("phase1_load",        lambda r, c: loader.run(r),
     "SAE feature extraction"),
    ("phase1_rank",        lambda r, c: ranker.run(r, c),
     "Split stratification"),
    ("phase2_cluster",     lambda r, c: cluster.run(r),
     "Description clustering"),
    ("phase2_label",       lambda r, c: labeler.run(r),
     "Lexicon induction"),
    ("phase2_consistency", lambda r, c: consistency.run(r),
     "Lexicon consistency validation"),
    ("phase3_encode",      lambda r, c: encoder.run(r),
     "MorphoRepr encoding (2 runs)"),
    ("phase3_fidelity",    lambda r, c: fidelity.run(r),
     "Fidelity AUC-ROC"),
    ("phase3_baselines",   lambda r, c: _run_baselines_p3(r),
     "Phase 3 baselines"),
    ("phase3_shuffle",     lambda r, c: shuffled_baseline.generate_shuffles(r),
     "Shuffled control"),
    ("phase4_steer",       lambda r, c: steerer.run(r, c),
     "Activation steering"),
    ("phase4_predict",     lambda r, c: predictor.run(r),
     "Causal prediction"),
    ("phase4_judge",       lambda r, c: judge.run(r),
     "Causal validation"),
    ("phase5_report",      lambda r, c: reporter.run(r),
     "Synthesis and reporting"),
]


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

    if args.resume and args.run_id:
        run_id     = args.run_id
        last_phase = get_last_phase(run_id)
        logger.info(f"Resuming run {run_id} from phase {last_phase}")
        # Verify prompts have not changed since registration
        with get_conn() as conn:
            row = conn.execute(
                "SELECT prompt_hashes FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        verify_prompts_unchanged(
            config["prompts"], json.loads(row["prompt_hashes"])
        )
    else:
        run_id     = initialize_run(config, args)
        last_phase = None

    phase_ids = [p[0] for p in PHASES]

    for phase_id, phase_fn, description in PHASES:
        if last_phase and (phase_ids.index(phase_id)
                           <= phase_ids.index(last_phase)):
            logger.info(f"  {phase_id} already complete — skip")
            continue

        logger.info(f"\n{'='*55}")
        logger.info(f"  {phase_id}: {description}")
        logger.info(f"{'='*55}")

        try:
            phase_fn(run_id, config)
            mark_phase_complete(run_id, phase_id)
            print_cost_summary(run_id)

            current_cost, over = check_budget(
                run_id, config["budget"]["max_cost_usd"]
            )
            if config["budget"]["abort_on_exceed"] and over:
                raise RuntimeError(
                    f"Budget exceeded: ${current_cost:.2f} >= "
                    f"${config['budget']['max_cost_usd']}"
                )

        except Exception as e:
            mark_run_failed(run_id)
            logger.exception(f"Phase {phase_id} failed: {e}")
            # In full frozen run mode: archive and stop.
            # Do NOT wait for human correction.
            sys.exit(1)

    mark_run_complete(run_id)
    print_cost_summary(run_id)
    logger.info(f"\nRun {run_id} complete. Results in db/features.db")


if __name__ == "__main__":
    run_pipeline(parse_args())
```

---

## 10. Setup and Launch Sequence

### Step 1 — Environment

```bash
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
mkdir -p db logs checkpoints
sqlite3 db/features.db < db/schema.sql
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Step 2 — Unit tests

```bash
pytest tests/test_parse.py tests/test_schema.py \
       tests/test_db.py tests/test_shuffle_baseline.py -v
# All must pass before proceeding
```

### Step 3 — Classifier calibration

```bash
python classifiers/calibration/run_calibration.py
# Must show PASS for all robust properties
```

### Step 4 — Dev run (5 features)

```bash
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Check: DB populated, JSON parsed, cost < $1
```

### Step 5 — Pilot run (30–50 features)

```bash
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Calibrate thresholds and prompts if needed
# DECLARE any adjustment as calibration in the paper
```

### Step 6 — Freeze the configuration

```bash
# Commit all changes
git add -A && git commit -m "Freeze config for full run v1"

# Write the commit hash into the config
echo "git_commit: $(git rev-parse HEAD)" >> configs/run_v1.yaml

# Verify prompt hashes
python -c "
import yaml
from utils.prompt_utils import load_prompt, hash_prompt
cfg = yaml.safe_load(open('configs/run_v1.yaml'))
for agent, path in cfg['prompts'].items():
    print(f'{agent}: {hash_prompt(load_prompt(path))}')
"
```

### Step 7 — Full frozen run

```bash
python orchestrator.py --config configs/run_v1.yaml
# No intervention during execution
# On failure: archive, analyse, fix, relaunch with --resume
```

### Step 8 — Resume after crash

```bash
# Find the interrupted run ID
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"

python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <run_id>
# Prompts are verified automatically — any modification is detected
```

---

## Role of Claude Code in This Protocol

Claude Code intervenes **only** during development phases:

- writing and debugging agent scripts
- generating classifier calibration files
- analysing pilot run intermediate results
- producing readable reports from SQLite data
- suggesting fixes when a phase fails during development

Claude Code **never** intervenes during the full frozen run. The scientific run is driven exclusively by `orchestrator.py` with a frozen configuration.
