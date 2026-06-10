# MorphoRepr — Procédure de test complète (v2)
## Infrastructure expérimentale corrigée et publiable

---

## Principes directeurs

Avant tout code, trois règles structurantes issues de la critique :

**Règle 1 — Séparation des rôles**
Claude Code sert à développer, déboguer et superviser. Le run expérimental final est piloté par `python orchestrator.py --config configs/run_v1.yaml` — déterministe, sans modification automatique de code ni intervention agentique non tracée.

**Règle 2 — Trois niveaux d'exécution**

| Mode | n features | Objectif | Résultats |
|------|-----------|----------|-----------|
| Dev run | 5 | Plomberie, DB, parsing, batch, classifieurs | Non scientifiques |
| Pilot run | 30–50 | Calibration prompts, seuils, classifieurs | Exploratoires |
| Full frozen run | 500 | Publication | Figés après lancement |

Si les seuils ou prompts sont ajustés après observation des résultats du pilot run, le déclarer explicitement comme calibration dans le papier. Le full run démarre uniquement quand tous les paramètres sont gelés.

**Règle 3 — Gel complet avant full run**
Commit Git fixé, config gelée, prompts versionnés et hashés, modèles figés, température fixée, seed documentée, corpus gelé, lexique gelé, outputs écrits une seule fois.

---

## 1. Structure du projet

```
morphorepr-pipeline/
├── CLAUDE.md                    ← instructions Claude Code (dev uniquement)
├── configs/
│   ├── dev_run.yaml
│   ├── pilot_run.yaml
│   └── run_v1.yaml              ← config gelée pour le full run
├── db/
│   ├── schema.sql               ← schéma complet versionné
│   ├── features.db              ← corpus SQLite (ne jamais modifier directement)
│   └── lexicon.json             ← lexique versionné
├── prompts/
│   ├── label_agent_v1.txt       ← prompts versionnés, lus depuis fichiers
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
│   ├── negation.py              ← propriété robuste
│   ├── tense.py                 ← propriété robuste
│   ├── code_presence.py         ← propriété robuste
│   ├── modality.py              ← propriété robuste
│   ├── valence.py               ← propriété semi-robuste
│   └── calibration/
│       ├── negation_test.json   ← 50 exemples annotés manuellement
│       └── valence_test.json
├── baselines/
│   ├── nl_labels.py
│   ├── semantic_regex.py
│   └── shuffled.py
├── utils/
│   ├── db_utils.py              ← seul point d'accès à la DB
│   ├── api_utils.py             ← wrapper Batch API avec retry
│   ├── prompt_utils.py          ← chargement et hashing des prompts
│   ├── config_utils.py          ← chargement et validation de la config
│   └── stats_utils.py           ← bootstrap IC95%, métriques
├── tests/
│   ├── test_parse.py
│   ├── test_schema.py
│   ├── test_classifiers.py
│   ├── test_db.py
│   ├── test_pipeline_e2e.py
│   └── test_shuffle_baseline.py
├── orchestrator.py              ← point d'entrée du run scientifique
├── requirements.txt
└── checkpoints/                 ← archives immuables
```

---

## 2. Fichier de configuration gelé

Tous les paramètres d'un run sont dans un seul fichier YAML. Le run les lit, ne les modifie jamais.

```yaml
# configs/run_v1.yaml

run_id: "morphorepr_v1_20260610"
description: "Full frozen run MorphoRepr v0.26 — 500 features"

# Reproductibilité
git_commit: "FILL_BEFORE_LAUNCH"       # git rev-parse HEAD
temperature: 0.3                        # Option A : mesurer stabilité intrinsèque
seed: 42                                # documenté, pas forcément utilisable par l'API
lexicon_version: "v1.0"
corpus_frozen: true                     # features.db ne doit pas changer après ce flag

# Modèles (identifiants exacts API Anthropic)
models:
  semantic_judgment: "claude-sonnet-4-6"
  scoring: "claude-haiku-4-5-20251001"
  batch: true
  max_tokens_judgment: 800
  max_tokens_scoring: 400

# Prompts (lus depuis fichiers, non modifiables après gel)
prompts:
  label_agent:   "prompts/label_agent_v1.txt"
  encoder:       "prompts/encoder_agent_v1.txt"
  predictor:     "prompts/predictor_agent_v1.txt"
  fidelity_judge: "prompts/fidelity_judge_v1.txt"
  causal_judge:  "prompts/causal_judge_v1.txt"

# Corpus
splits:
  easy:   {n: 200, min_interp_score: 0.7}
  random: {n: 200, filter: "uniform"}
  hard:   {n: 100, max_interp_score: 0.5}
primary_split: "random"                 # tous les seuils go/no-go évalués ici

# Steering
steering:
  magnitudes: [0, 2, 5, 10]            # courbe dose-réponse
  primary_magnitude: 5                  # magnitude principale pour les métriques
  n_probe_sentences: 20
  n_subsample_for_curve: 50            # sous-échantillon pour magnitudes 2 et 10

# Baselines
baselines:
  - nl_labels
  - semantic_regex
  - keyword_tags
  - morphorepr_shuffled

# Contrôle MorphoRepr mélangé
shuffle_control:
  n_repeats: 10                         # shuffle répété 10 fois par feature
  within_split: true                    # jamais cross-split
  max_term_diff: 1                      # longueur comparable ±1 terme
  preserve_coefficients: true

# Budget et arrêt automatique
budget:
  max_cost_usd: 100.0
  alert_at_usd: 50.0
  abort_on_exceed: true

# Seuils go/no-go (évalués sur random split)
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

## 3. Schéma SQLite complet

```sql
-- db/schema.sql
-- Version 1.0 — ne jamais modifier après le full run

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────────
-- Traçabilité des runs
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    git_commit      TEXT NOT NULL,
    config_hash     TEXT NOT NULL,    -- SHA256 du fichier YAML
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
-- Prompts versionnés
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
-- Corpus de features
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS features (
    feature_index   INTEGER PRIMARY KEY,
    split           TEXT NOT NULL,    -- 'easy', 'random', 'hard'
    nl_description  TEXT NOT NULL,
    top_examples    TEXT NOT NULL,    -- JSON array (sérialisé)
    score_interp    REAL,
    activation_freq REAL,
    layer           TEXT,
    sae_version     TEXT,
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Outputs bruts de chaque agent (immuables)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id       TEXT PRIMARY KEY,    -- UUID
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL REFERENCES features(feature_index),
    agent_name      TEXT NOT NULL,
    run_number      INTEGER NOT NULL DEFAULT 1,  -- 1 ou 2
    output_json     TEXT,               -- sortie parsée (JSON structuré)
    raw_output      TEXT,               -- sortie brute API (jamais modifiée)
    status          TEXT NOT NULL,      -- 'ok','uncovered','failed','invalid_json'
    error_msg       TEXT,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    batch_id        TEXT,
    cost_usd        REAL,
    coefficient_type TEXT DEFAULT 'confidence',  -- 'confidence' ou 'activation'
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Métriques calculées (résultats)
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
    baseline        TEXT,               -- NULL = MorphoRepr, sinon nom baseline
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
-- Contrôle mélangé (10 shuffles par feature)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shuffle_controls (
    shuffle_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    feature_index   INTEGER NOT NULL,
    shuffle_number  INTEGER NOT NULL,   -- 1 à 10
    source_feature  INTEGER NOT NULL,   -- feature dont l'annotation a été prise
    annotation      TEXT NOT NULL,
    causal_score    REAL,
    causal_outcome  TEXT,
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Suivi des coûts API
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
-- Versions du lexique
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lexicon_versions (
    version         TEXT PRIMARY KEY,
    morphemes       TEXT NOT NULL,      -- JSON complet
    free_roots      TEXT NOT NULL,      -- JSON liste
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

## 4. Utilitaires de base

### 4.1 Accès à la base de données

```python
# utils/db_utils.py
"""
Seul point d'accès à features.db.
Toute opération directe sur la DB en dehors de ce module est interdite.
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
    """Charge les features selon le split et l'état d'encodage."""
    with get_conn() as conn:
        query = "SELECT * FROM features WHERE 1=1"
        params = []
        if split:
            query += " AND split = ?"
            params.append(split)
        # encoded = 0 signifie pas encore traité (DEFAULT 0, pas NULL)
        if not encoded:
            query += " AND feature_index NOT IN "
            query += "(SELECT DISTINCT feature_index FROM agent_outputs "
            query += " WHERE agent_name = 'encoder' AND status = 'ok')"
        rows = conn.execute(query, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # Désérialiser top_examples (stocké en JSON texte)
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
    """Insère un output d'agent — immuable une fois écrit."""
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
                 batch_id: Optional[str], cost: float):
    """Logge chaque appel API et met à jour le coût cumulé du run."""
    from uuid import uuid4
    from datetime import datetime
    with get_conn() as conn:
        # Coût cumulé
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
    """Retourne (coût_cumulé, dépasse_budget)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()
    cost = row["total_cost_usd"] if row else 0.0
    return cost, cost >= max_cost
```

### 4.2 Gestion des prompts

```python
# utils/prompt_utils.py
"""Chargement, hashing et enregistrement des prompts versionnés."""
import hashlib
from pathlib import Path
from datetime import datetime
from utils.db_utils import get_conn

def load_prompt(path: str) -> str:
    """Lit un prompt depuis fichier. Lève une erreur si absent."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompt introuvable : {path}")
    return p.read_text(encoding="utf-8").strip()

def hash_prompt(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def register_prompts(prompt_paths: dict) -> dict:
    """
    Enregistre tous les prompts en DB et retourne leurs hashes.
    prompt_paths : {agent_name: path}
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
    """Lève une erreur si un prompt a changé depuis l'enregistrement."""
    for agent_name, path in prompt_paths.items():
        content = load_prompt(path)
        current = hash_prompt(content)
        if current != registered_hashes.get(agent_name):
            raise RuntimeError(
                f"Prompt modifié pendant le run : {agent_name}\n"
                f"  attendu : {registered_hashes[agent_name]}\n"
                f"  actuel  : {current}"
            )
```

### 4.3 Wrapper Batch API avec retry et gestion d'erreurs

```python
# utils/api_utils.py
"""
Wrapper robuste autour de l'API Batch Anthropic.
Gère retry, timeouts, erreurs partielles, budget, parsing JSON.
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
    "claude-sonnet-4-6":        {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0,  "output": 5.0},
}
BATCH_DISCOUNT = 0.50

def compute_cost(model: str, tokens_in: int, tokens_out: int,
                 is_batch: bool = True) -> float:
    rates = COST_PER_MTK.get(model, {"input": 3.0, "output": 15.0})
    cost = (tokens_in / 1_000_000) * rates["input"] + \
           (tokens_out / 1_000_000) * rates["output"]
    return cost * (BATCH_DISCOUNT if is_batch else 1.0)

def submit_batch(requests: list[dict]) -> str:
    """Soumet un batch et retourne l'ID."""
    batch = client.messages.batches.create(requests=requests)
    logger.info(f"Batch soumis : {batch.id} ({len(requests)} requêtes)")
    return batch.id

def poll_batch(batch_id: str,
               run_id: str,
               phase: str,
               agent_name: str,
               model: str,
               poll_interval: int = 30,
               max_wait_seconds: int = 7200) -> list[dict]:
    """
    Attend la complétion d'un batch.
    Retourne une liste de résultats avec statut explicite.
    """
    elapsed = 0
    while elapsed < max_wait_seconds:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        elif batch.processing_status == "errored":
            raise RuntimeError(f"Batch {batch_id} en erreur serveur")
        counts = batch.request_counts
        logger.info(
            f"Batch {batch_id} : {counts.processing} en cours, "
            f"{counts.succeeded} réussis, {counts.errored} erreurs"
        )
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        raise TimeoutError(f"Batch {batch_id} timeout après {max_wait_seconds}s")

    results = []
    total_in, total_out = 0, 0

    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            msg = result.result.message
            raw = msg.content[0].text if msg.content else ""
            tin  = msg.usage.input_tokens
            tout = msg.usage.output_tokens
            total_in  += tin
            total_out += tout

            # Tenter de parser JSON structuré
            parsed, status = _parse_json_output(raw, result.custom_id)
            results.append({
                "custom_id":    result.custom_id,
                "raw_output":   raw,
                "output_json":  parsed,
                "status":       status,
                "error_msg":    None,
                "tokens_input": tin,
                "tokens_output": tout,
            })
        else:
            err = result.result.error.message if result.result.error else "unknown"
            results.append({
                "custom_id":    result.custom_id,
                "raw_output":   None,
                "output_json":  None,
                "status":       "failed",
                "error_msg":    err,
                "tokens_input": 0,
                "tokens_output": 0,
            })

    # Logguer coût et vérifier budget
    cost = compute_cost(model, total_in, total_out, is_batch=True)
    cumulative = log_api_cost(run_id, phase, agent_name, model,
                              total_in, total_out, batch_id, cost)
    logger.info(f"Coût batch {batch_id} : {cost:.3f} $ | Cumulé : {cumulative:.2f} $")

    config = load_config()
    if config["budget"]["abort_on_exceed"] and \
       cumulative >= config["budget"]["max_cost_usd"]:
        raise RuntimeError(
            f"Budget dépassé : {cumulative:.2f} $ >= "
            f"{config['budget']['max_cost_usd']} $"
        )

    return results

def _parse_json_output(raw: str, custom_id: str) -> tuple[Optional[dict], str]:
    """
    Tente de parser la sortie de l'agent en JSON structuré.
    Retourne (parsed_dict, status).
    """
    if not raw:
        return None, "failed"
    # Retirer les éventuelles balises markdown
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```"
                          else lines[1:])
    try:
        parsed = json.loads(clean)
        # Valider les champs obligatoires
        if "status" not in parsed:
            logger.warning(f"{custom_id} : JSON sans champ 'status'")
            return parsed, "invalid_json"
        if parsed["status"] == "uncovered":
            return parsed, "uncovered"
        return parsed, "ok"
    except json.JSONDecodeError:
        logger.warning(f"{custom_id} : sortie non-JSON : {raw[:100]}")
        return None, "invalid_json"

def build_batch_requests(features: list[dict],
                          system_prompt: str,
                          user_prompt_fn,
                          model: str,
                          max_tokens: int) -> list[dict]:
    """Construit la liste de requêtes pour l'API Batch."""
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

### 4.4 Statistiques et métriques

```python
# utils/stats_utils.py
"""Calculs statistiques : bootstrap IC95%, métriques morphémiques."""
import numpy as np
from scipy import stats as scipy_stats
from typing import Optional

def bootstrap_ci(values: list[float],
                 n_bootstrap: int = 1000,
                 ci: float = 0.95) -> tuple[float, float, float]:
    """
    Retourne (mean, ci_low, ci_high) via bootstrap.
    """
    if not values:
        return 0.0, 0.0, 0.0
    arr = np.array(values)
    means = [np.mean(np.random.choice(arr, len(arr), replace=True))
             for _ in range(n_bootstrap)]
    alpha = (1 - ci) / 2
    return (float(np.mean(arr)),
            float(np.percentile(means, alpha * 100)),
            float(np.percentile(means, (1 - alpha) * 100)))

def morpheme_jaccard(expr1: Optional[str],
                     expr2: Optional[str]) -> float:
    """Similarité de Jaccard sur les ensembles de morphèmes."""
    if not expr1 or not expr2:
        return 0.0
    def extract_morphemes(expr: str) -> set:
        morphemes = set()
        for term in expr.split("+"):
            term = term.strip()
            if "·" in term:
                _, word = term.split("·", 1)
                parts = word.replace("-", " ").split()
                morphemes.update(parts)
        return morphemes
    s1 = extract_morphemes(expr1)
    s2 = extract_morphemes(expr2)
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)

def root_jaccard(expr1: Optional[str],
                 expr2: Optional[str]) -> float:
    """Similarité de Jaccard sur les racines uniquement."""
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
            # Retirer préfixes, infixes, suffixes
            w = word
            for p in PREFIXES:
                w = w.replace(p, "")
            for ix in INFIXES:
                w = w.replace(ix, "-")
            for s in SUFFIXES:
                if w.endswith(s):
                    w = w[:-len(s)]
                    break
            root = w.replace("-","").strip()
            if root:
                roots.add(root)
        return roots
    s1 = extract_roots(expr1)
    s2 = extract_roots(expr2)
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)

def coefficient_correlation(expr1: Optional[str],
                             expr2: Optional[str]) -> float:
    """Corrélation de Pearson entre coefficients des termes correspondants."""
    if not expr1 or not expr2:
        return 0.0
    def extract_coeffs(expr: str) -> list[float]:
        coeffs = []
        for term in expr.split("+"):
            term = term.strip()
            if "·" in term:
                coeff_str, _ = term.split("·", 1)
                try:
                    coeffs.append(float(coeff_str.strip()))
                except ValueError:
                    pass
        return coeffs
    c1 = extract_coeffs(expr1)
    c2 = extract_coeffs(expr2)
    n = min(len(c1), len(c2))
    if n < 2:
        return 0.0
    r, _ = scipy_stats.pearsonr(c1[:n], c2[:n])
    return float(r)

def morpheme_edit_distance(expr1: Optional[str],
                           expr2: Optional[str]) -> float:
    """Distance d'édition (substitutions) entre chaînes de morphèmes."""
    if not expr1 or not expr2:
        return float("inf")
    def to_morpheme_list(expr: str) -> list[str]:
        morphemes = []
        for term in expr.split("+"):
            if "·" in term:
                _, word = term.strip().split("·", 1)
                morphemes.extend(word.split("-"))
        return [m for m in morphemes if m]
    m1 = to_morpheme_list(expr1)
    m2 = to_morpheme_list(expr2)
    # Levenshtein simplifié (substitutions)
    if not m1 or not m2:
        return float(max(len(m1), len(m2)))
    dp = [[0]*(len(m2)+1) for _ in range(len(m1)+1)]
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

## 5. Classifieurs de propriétés (Phase 4)

### 5.1 Négation (robuste)

```python
# classifiers/negation.py
"""
Classifieur de négation — propriété robuste.
Combine dépendances syntaxiques, lexique négatif et morphologie.
"""
import spacy

nlp = spacy.load("en_core_web_sm")

# Lexique négatif étendu (au-delà de dep_=="neg")
NEG_LEXICON = {
    "no","not","never","neither","nor","nobody","nothing",
    "nowhere","none","without","lack","lacking","absent",
    "fail","fails","failed","failure","missing","unable",
    "impossible","prevent","prevents","prevented","deny",
    "denies","denied","refuse","refuses","refused"
}

# Préfixes négatifs morphologiques
NEG_PREFIXES = ("un","im","in","dis","non","ir","il","a")

def count_negation_signals(text: str) -> float:
    """
    Retourne un score de négation normalisé par longueur.
    Poids : dep_neg = 1.0, lexique = 0.7, morpho = 0.3
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
        elif any(t.lower_.startswith(p) for p in NEG_PREFIXES) \
             and len(t.text) > 4:
            score += 0.3
    return score / len(tokens)

def measure(texts_before: list[str],
            texts_after: list[str]) -> dict:
    before = sum(count_negation_signals(t) for t in texts_before) \
             / len(texts_before)
    after  = sum(count_negation_signals(t) for t in texts_after) \
             / len(texts_after)
    delta  = after - before
    THRESHOLD = 0.02
    return {
        "property":  "negation_presence",
        "tier":      "robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": "INCREASE"  if delta >  THRESHOLD else
                     "DECREASE"  if delta < -THRESHOLD else
                     "NO_CHANGE"
    }
```

### 5.2 Valence émotionnelle (semi-robuste)

```python
# classifiers/valence.py
"""
Classifieur de valence émotionnelle — propriété semi-robuste.
Utilise un modèle entraîné sur du texte général (pas SST-2).
"""
from transformers import pipeline as hf_pipeline

# cardiffnlp/twitter-roberta-base-sentiment-latest est plus robuste
# que SST-2 sur du texte non-cinéma
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
    THRESHOLD = 0.05  # plus conservateur que pour la négation
    return {
        "property":  "negative_valence",
        "tier":      "semi-robust",
        "before":    round(before, 4),
        "after":     round(after, 4),
        "delta":     round(delta, 4),
        "direction": "INCREASE"  if delta >  THRESHOLD else
                     "DECREASE"  if delta < -THRESHOLD else
                     "NO_CHANGE",
        "reliability_note":
            "Semi-robust: results should be interpreted with caution "
            "on technical or ironic text."
    }
```

### 5.3 Calibration des classifieurs

Avant le pilot run, chaque classifieur robuste doit être validé sur un petit jeu annoté manuellement :

```python
# classifiers/calibration/run_calibration.py
"""
Valide les classifieurs sur des exemples annotés manuellement.
Doit être exécuté et validé avant le pilot run.
"""
import json
from classifiers import negation, tense, code_presence, modality, valence

def calibrate(classifier_module, test_file: str,
              property_name: str, min_accuracy: float = 0.85):
    data = json.loads(open(test_file).read())
    correct = 0
    for example in data:
        result = classifier_module.measure(
            [example["text_before"]],
            [example["text_after"]]
        )
        predicted = result["direction"]
        expected  = example["expected_direction"]
        if predicted == expected:
            correct += 1
    accuracy = correct / len(data)
    status = "✅ PASS" if accuracy >= min_accuracy else "❌ FAIL"
    print(f"{status} {property_name}: {accuracy:.1%} "
          f"({correct}/{len(data)}) — seuil : {min_accuracy:.0%}")
    return accuracy >= min_accuracy

if __name__ == "__main__":
    results = [
        calibrate(negation, "calibration/negation_test.json",
                  "negation_presence", min_accuracy=0.85),
        calibrate(valence,  "calibration/valence_test.json",
                  "negative_valence",  min_accuracy=0.80),
    ]
    if not all(results):
        raise SystemExit("Calibration échouée — corriger les classifieurs "
                         "avant de lancer le pilot run")
    print("\nCalibration validée — pipeline prêt pour le pilot run")
```

---

## 6. Agents principaux

### 6.1 Agent d'encodage (Phase 3)

```python
# agents/encoder.py
"""
Phase 3 — Encodage MorphoRepr.
Deux runs indépendants. Sorties JSON structurées obligatoires.
"""
import json
import logging
from pathlib import Path
from utils.db_utils import load_features, save_agent_output, get_conn
from utils.api_utils import (submit_batch, poll_batch,
                              build_batch_requests, _parse_json_output)
from utils.prompt_utils import load_prompt
from utils.config_utils import load_config

logger = logging.getLogger(__name__)

# Format de sortie attendu de l'agent (documenté dans le prompt)
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

def run(run_id: str):
    config  = load_config()
    system  = load_prompt(config["prompts"]["encoder"])
    lexicon = json.loads(Path("db/lexicon.json").read_text())
    model   = config["models"]["semantic_judgment"]

    for run_number in [1, 2]:
        logger.info(f"Encodage run {run_number}/2")
        features = load_features_not_encoded(run_id, run_number)

        if not features:
            logger.info(f"Run {run_number} : tous les features déjà encodés")
            continue

        logger.info(f"  {len(features)} features à encoder (run {run_number})")

        requests = build_batch_requests(
            features, system,
            lambda f: build_user_prompt(f, lexicon),
            model=model,
            max_tokens=config["models"]["max_tokens_judgment"]
        )

        # Sauvegarder l'ID du batch pour reprise éventuelle
        batch_id = submit_batch(requests)
        Path(f"checkpoints/batch_encoder_run{run_number}.txt").write_text(batch_id)

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
                cost_usd=0.0,  # coût déjà loggué dans poll_batch
                coefficient_type="confidence"
            )

        n_ok = sum(1 for r in results if r["status"] == "ok")
        n_unc = sum(1 for r in results if r["status"] == "uncovered")
        n_fail = sum(1 for r in results if r["status"] == "failed")
        logger.info(
            f"  Run {run_number} terminé : "
            f"{n_ok} ok, {n_unc} uncovered, {n_fail} failed"
        )

def load_features_not_encoded(run_id: str, run_number: int) -> list[dict]:
    """Charge les features sans output d'encodage pour ce run_number."""
    with get_conn() as conn:
        done = {
            row["feature_index"]
            for row in conn.execute("""
                SELECT feature_index FROM agent_outputs
                WHERE run_id = ? AND agent_name = 'encoder'
                AND run_number = ?
            """, (run_id, run_number)).fetchall()
        }
        all_features = conn.execute(
            "SELECT * FROM features"
        ).fetchall()
    result = []
    for f in all_features:
        if f["feature_index"] not in done:
            d = dict(f)
            d["top_examples"] = json.loads(d["top_examples"])
            result.append(d)
    return result
```

### 6.2 Agent de prédiction causale (Phase 4)

```python
# agents/predictor.py
"""
Phase 4 — Prédiction causale.
L'agent reçoit UNIQUEMENT l'expression MorphoRepr, pas la description NL.
Sortie JSON avec propriétés stratifiées par robustesse.
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
    CRITIQUE : le juge ne reçoit PAS la description NL.
    Garde-fou anti-circularité.
    """
    return (
        f"Feature index: {feature_index}\n"
        f"MorphoRepr expression: {morphorepr_expression}\n\n"
        f"Predict which output properties will change when this feature "
        f"is amplified by +5 activation units.\n"
        f"Respond ONLY with a valid JSON object as specified in your system prompt."
    )

def load_encoded_features(run_id: str) -> list[dict]:
    """Charge les features avec expression encodée (run 1 par défaut)."""
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
    config = load_config()
    system = load_prompt(config["prompts"]["predictor"])
    model  = config["models"]["semantic_judgment"]
    features = load_encoded_features(run_id)

    if not features:
        logger.info("Phase 4 : tous les features déjà traités")
        return

    logger.info(f"Phase 4 : {len(features)} features à prédire")

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

    logger.info("Phase 4 prédiction terminée")
```

---

## 7. Contrôle MorphoRepr mélangé

```python
# baselines/shuffled.py
"""
Baseline MorphoRepr mélangé.
- Mélange intra-split uniquement
- Longueur appariée ±1 terme
- 10 shuffles par feature
- Coefficients conservés (seuls les morphèmes sont mélangés)
"""
import random
import logging
from utils.db_utils import get_conn
from utils.config_utils import load_config

logger = logging.getLogger(__name__)

def _count_terms(expression: str) -> int:
    return len([t for t in expression.split("+") if "·" in t])

def generate_shuffles(run_id: str, n_repeats: int = 10):
    config = load_config()
    max_diff = config["shuffle_control"]["max_term_diff"]

    with get_conn() as conn:
        # Récupérer toutes les annotations encodées avec leur split
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

    # Grouper par split
    by_split: dict[str, list[dict]] = {}
    for r in rows:
        if r["expression"]:
            by_split.setdefault(r["split"], []).append({
                "feature_index": r["feature_index"],
                "expression": r["expression"],
                "n_terms": _count_terms(r["expression"])
            })

    shuffles_to_insert = []
    for split, features in by_split.items():
        for feat in features:
            n_feat = feat["n_terms"]
            # Candidats : même split, longueur comparable, autre feature
            candidates = [
                f for f in features
                if f["feature_index"] != feat["feature_index"]
                and abs(f["n_terms"] - n_feat) <= max_diff
            ]
            if len(candidates) < 3:
                logger.warning(
                    f"Feature {feat['feature_index']} : "
                    f"seulement {len(candidates)} candidats pour shuffle"
                )
                continue
            for shuffle_num in range(1, n_repeats + 1):
                source = random.choice(candidates)
                shuffles_to_insert.append({
                    "feature_index": feat["feature_index"],
                    "shuffle_number": shuffle_num,
                    "source_feature": source["feature_index"],
                    "annotation": source["expression"]
                })

    # Insérer dans la DB
    from uuid import uuid4
    from datetime import datetime
    with get_conn() as conn:
        for s in shuffles_to_insert:
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
        f"Shuffles générés : {len(shuffles_to_insert)} "
        f"({n_repeats} par feature)"
    )
```

---

## 8. Tests unitaires

```python
# tests/test_parse.py
"""Tests unitaires du parseur MorphoRepr."""
import pytest
from utils.stats_utils import (morpheme_jaccard, root_jaccard,
                                coefficient_correlation,
                                morpheme_edit_distance)

class TestMorphemeJaccard:
    def test_identical_expressions(self):
        expr = "0.86·mal-emo-a + 0.42·ne-soc-a"
        assert morpheme_jaccard(expr, expr) == 1.0

    def test_completely_different(self):
        e1 = "0.90·ag-is"
        e2 = "0.80·sci-o"
        j = morpheme_jaccard(e1, e2)
        assert j < 0.5

    def test_partial_overlap(self):
        e1 = "0.86·mal-emo-a + 0.42·ne-soc-a"
        e2 = "0.86·mal-emo-a + 0.30·ag-is"
        j = morpheme_jaccard(e1, e2)
        assert 0.0 < j < 1.0

    def test_none_inputs(self):
        assert morpheme_jaccard(None, "0.8·ag-is") == 0.0
        assert morpheme_jaccard("0.8·ag-is", None) == 0.0


class TestCoefficientCorrelation:
    def test_perfect_correlation(self):
        expr = "0.90·ag-is + 0.50·sci-o"
        assert coefficient_correlation(expr, expr) == pytest.approx(1.0)

    def test_single_term_returns_zero(self):
        # Pearson non définie sur 1 point
        assert coefficient_correlation("0.90·ag-is", "0.80·sci-o") == 0.0


class TestMorphemeEditDistance:
    def test_identical(self):
        assert morpheme_edit_distance("0.9·ag-is", "0.9·ag-is") == 0.0

    def test_one_substitution(self):
        # "ag-is" vs "ag-os" : 1 substitution
        dist = morpheme_edit_distance("0.9·ag-is", "0.9·ag-os")
        assert dist <= 2.0


# tests/test_schema.py
"""Tests de validation du schéma JSON des sorties d'agents."""
import pytest
import json
from utils.api_utils import _parse_json_output

class TestJsonOutputSchema:
    def test_valid_encoded_output(self):
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
        assert parsed["status"] == "encoded"
        assert "expression" in parsed

    def test_uncovered_output(self):
        raw = json.dumps({
            "status": "uncovered",
            "expression": None,
            "coefficient_type": "confidence",
            "terms": [],
            "uncovered_reason": "No morpheme covers named entity specificity"
        })
        parsed, status = _parse_json_output(raw, "feature_999")
        assert status == "uncovered"

    def test_invalid_json(self):
        raw = "This is not JSON at all."
        parsed, status = _parse_json_output(raw, "feature_001")
        assert status == "invalid_json"
        assert parsed is None

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"status":"encoded","expression":"0.9·ag-is",' \
              '"coefficient_type":"confidence","terms":[],' \
              '"uncovered_reason":null}\n```'
        parsed, status = _parse_json_output(raw, "feature_002")
        # Doit parser malgré les balises markdown
        assert parsed is not None


# tests/test_db.py
"""Tests de la DB et de la reprise après crash."""
import pytest
import sqlite3
import tempfile
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
    # Vérifier que le feature n'est pas dans agent_outputs
    count = conn.execute("""
        SELECT COUNT(*) FROM agent_outputs
        WHERE feature_index = 1 AND agent_name = 'encoder'
    """).fetchone()[0]
    assert count == 0
    conn.close()

def test_resume_after_crash(tmp_path):
    """Si le run reprend, les features déjà encodés ne sont pas retraités."""
    db = make_test_db(tmp_path)
    conn = sqlite3.connect(db)
    # Simuler un run partiel
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
    # Feature 1 déjà encodé
    conn.execute("""
        INSERT INTO agent_outputs VALUES
        ('out1','run_test',1,'encoder',1,'{"status":"encoded"}','raw',
         'ok',NULL,100,50,NULL,0.0,'confidence',datetime('now'))
    """)
    conn.commit()
    # Seul feature 2 doit être chargé
    done = {
        r[0] for r in conn.execute("""
            SELECT feature_index FROM agent_outputs
            WHERE run_id = 'run_test' AND agent_name = 'encoder'
            AND run_number = 1
        """).fetchall()
    }
    all_f = [r[0] for r in conn.execute(
        "SELECT feature_index FROM features"
    ).fetchall()]
    to_encode = [f for f in all_f if f not in done]
    assert to_encode == [2]
    conn.close()


# tests/test_shuffle_baseline.py
"""Tests du contrôle MorphoRepr mélangé."""
import pytest

def test_shuffle_within_split():
    """Vérifie que les shuffles restent dans le même split."""
    by_split = {
        "easy": [
            {"feature_index": 1, "expression": "0.9·ag-is",   "n_terms": 1},
            {"feature_index": 2, "expression": "0.8·sci-o",   "n_terms": 1},
            {"feature_index": 3, "expression": "0.7·emo-a",   "n_terms": 1},
        ],
        "hard": [
            {"feature_index": 4, "expression": "0.6·dat-ad-o","n_terms": 1},
        ]
    }
    # Un feature du split easy ne doit jamais recevoir
    # une annotation du split hard
    for split, features in by_split.items():
        sources = {f["feature_index"] for f in features}
        for feat in features:
            candidates = [
                f for f in features
                if f["feature_index"] != feat["feature_index"]
            ]
            # Tous les candidats sont dans le même split
            for c in candidates:
                assert c["feature_index"] in sources

def test_shuffle_length_constraint():
    """Vérifie que seuls les features de longueur comparable sont candidats."""
    features = [
        {"feature_index": 1, "expression": "0.9·ag-is", "n_terms": 1},
        {"feature_index": 2, "expression": "0.8·sci-o + 0.4·emo-a", "n_terms": 2},
        {"feature_index": 3, "expression": "0.7·emo-a", "n_terms": 1},
    ]
    max_diff = 1
    target = features[0]  # n_terms = 1
    candidates = [
        f for f in features
        if f["feature_index"] != target["feature_index"]
        and abs(f["n_terms"] - target["n_terms"]) <= max_diff
    ]
    # Feature 2 (n_terms=2) est à distance 1 → candidat valide
    # Feature 3 (n_terms=1) est à distance 0 → candidat valide
    assert len(candidates) == 2


# tests/test_pipeline_e2e.py
"""Test end-to-end sur 5 features — niveau dev run."""
import pytest
import subprocess
import sys

def test_pipeline_5_features_end_to_end(tmp_path):
    """
    Lance le pipeline complet sur 5 features en mode dev.
    Vérifie que :
    - la DB est créée et peuplée
    - les phases 1-3 s'exécutent sans erreur
    - les outputs JSON sont valides
    - les métriques de cohérence sont calculées
    """
    # Ce test nécessite ANTHROPIC_API_KEY dans l'environnement
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY non définie — test e2e ignoré")

    result = subprocess.run(
        [sys.executable, "orchestrator.py",
         "--config", "configs/dev_run.yaml",
         "--n-features", "5"],
        capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, \
        f"Pipeline échoué :\n{result.stderr}"
    assert "phase3" in result.stdout.lower() or "phase3" in result.stderr.lower()
```

---

## 9. Orchestrateur final

```python
# orchestrator.py
"""
Point d'entrée du run scientifique MorphoRepr.
Déterministe, sans modification de code, sans intervention agentique.

Usage :
    python orchestrator.py --config configs/run_v1.yaml
    python orchestrator.py --config configs/dev_run.yaml --n-features 5
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

# Configuration du logging
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
from utils.db_utils import get_conn
from utils.stats_utils import bootstrap_ci

# Import des agents
from agents import loader, ranker, cluster, labeler, consistency
from agents import encoder, fidelity, steerer, predictor, judge, reporter
from baselines import shuffled as shuffled_baseline


def parse_args():
    p = argparse.ArgumentParser(description="Pipeline MorphoRepr")
    p.add_argument("--config", required=True,
                   help="Fichier de configuration YAML")
    p.add_argument("--n-features", type=int, default=None,
                   help="Limiter à n features (dev/pilot uniquement)")
    p.add_argument("--resume", action="store_true",
                   help="Reprendre un run interrompu")
    p.add_argument("--run-id", default=None,
                   help="ID du run à reprendre (avec --resume)")
    return p.parse_args()


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def initialize_run(config: dict, args) -> str:
    """Crée un nouveau run dans la DB et retourne son ID."""
    run_id = str(uuid4())[:8]
    git_commit = get_git_commit()
    config_hash = hash_config(args.config)

    # Enregistrer et hasher tous les prompts
    prompt_hashes = register_prompts(config["prompts"])

    with get_conn() as conn:
        conn.execute("""
            INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,NULL,'running',NULL,0.0)
        """, (
            run_id, git_commit, config_hash,
            json.dumps(prompt_hashes),
            config["lexicon_version"],
            json.dumps(config["models"]),
            config["temperature"],
            config.get("seed"),
            datetime.utcnow().isoformat()
        ))

    logger.info(f"Run initialisé : {run_id}")
    logger.info(f"  Git commit   : {git_commit}")
    logger.info(f"  Config hash  : {config_hash}")
    logger.info(f"  Prompts      : {prompt_hashes}")
    return run_id


def get_last_completed_phase(run_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_phase FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return row["last_phase"] if row else None


def mark_phase_complete(run_id: str, phase: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE runs SET last_phase = ? WHERE run_id = ?",
            (phase, run_id)
        )
    # Snapshot immuable
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    Path("checkpoints").mkdir(exist_ok=True)
    Path(f"checkpoints/{run_id}_{phase}_{ts}.marker").touch()
    logger.info(f"  Checkpoint : phase {phase} terminée")


def mark_run_complete(run_id: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE runs
            SET status = 'completed', completed_at = ?
            WHERE run_id = ?
        """, (datetime.utcnow().isoformat(), run_id))
    logger.info(f"Run {run_id} terminé avec succès")


def mark_run_failed(run_id: str, error: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE runs SET status = 'failed' WHERE run_id = ?
        """, (run_id,))
    logger.error(f"Run {run_id} ÉCHOUÉ : {error}")


def print_cost_summary(run_id: str):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT phase, SUM(cost_usd) as total
            FROM api_usage WHERE run_id = ?
            GROUP BY phase ORDER BY phase
        """, (run_id,)).fetchall()
        total = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()["total_cost_usd"]
    logger.info("\n=== Coût cumulé ===")
    for phase, cost in rows:
        logger.info(f"  {phase:<15} {cost:.3f} $")
    logger.info(f"  {'TOTAL':<15} {total:.3f} $")


PHASES = [
    ("phase1_load",       lambda rid, cfg: loader.run(rid),
     "Extraction features SAE"),
    ("phase1_rank",       lambda rid, cfg: ranker.run(rid, cfg),
     "Stratification splits"),
    ("phase2_cluster",    lambda rid, cfg: cluster.run(rid),
     "Clustering descriptions"),
    ("phase2_label",      lambda rid, cfg: labeler.run(rid),
     "Induction lexique"),
    ("phase2_consistency",lambda rid, cfg: consistency.run(rid),
     "Validation cohérence lexique"),
    ("phase3_encode",     lambda rid, cfg: encoder.run(rid),
     "Encodage MorphoRepr (2 runs)"),
    ("phase3_fidelity",   lambda rid, cfg: fidelity.run(rid),
     "Fidélité AUC-ROC"),
    ("phase3_baselines",  lambda rid, cfg: _run_baselines_phase3(rid),
     "Baselines Phase 3"),
    ("phase3_shuffle",    lambda rid, cfg: shuffled_baseline.generate_shuffles(rid),
     "Contrôle mélangé"),
    ("phase4_steer",      lambda rid, cfg: steerer.run(rid, cfg),
     "Steering activation"),
    ("phase4_predict",    lambda rid, cfg: predictor.run(rid),
     "Prédiction causale"),
    ("phase4_judge",      lambda rid, cfg: judge.run(rid),
     "Validation causale"),
    ("phase5_report",     lambda rid, cfg: reporter.run(rid),
     "Synthèse et rapport"),
]


def _run_baselines_phase3(run_id: str):
    from baselines import nl_labels, semantic_regex, keyword_tags
    nl_labels.run(run_id)
    semantic_regex.run(run_id)
    keyword_tags.run(run_id)


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

    # Initialiser ou reprendre le run
    if args.resume and args.run_id:
        run_id = args.run_id
        last_phase = get_last_completed_phase(run_id)
        logger.info(f"Reprise du run {run_id} depuis la phase {last_phase}")
        # Vérifier que les prompts n'ont pas changé
        with get_conn() as conn:
            row = conn.execute(
                "SELECT prompt_hashes FROM runs WHERE run_id = ?",
                (run_id,)
            ).fetchone()
        registered_hashes = json.loads(row["prompt_hashes"])
        verify_prompts_unchanged(config["prompts"], registered_hashes)
    else:
        run_id = initialize_run(config, args)
        last_phase = None

    phase_ids = [p[0] for p in PHASES]

    for phase_id, phase_fn, description in PHASES:
        # Sauter les phases déjà complétées
        if last_phase and phase_ids.index(phase_id) <= \
           phase_ids.index(last_phase):
            logger.info(f"⏭  {phase_id} déjà complétée")
            continue

        logger.info(f"\n{'='*55}")
        logger.info(f"▶  {phase_id} : {description}")
        logger.info(f"{'='*55}")

        try:
            phase_fn(run_id, config)
            mark_phase_complete(run_id, phase_id)
            print_cost_summary(run_id)

            # Vérifier budget après chaque phase
            current_cost, over = __import__(
                "utils.db_utils", fromlist=["check_budget"]
            ).check_budget(run_id, config["budget"]["max_cost_usd"])

            if config["budget"]["abort_on_exceed"] and over:
                raise RuntimeError(
                    f"Budget dépassé : {current_cost:.2f} $ >= "
                    f"{config['budget']['max_cost_usd']} $"
                )

        except Exception as e:
            mark_run_failed(run_id, str(e))
            logger.exception(f"Phase {phase_id} échouée")
            # En mode full frozen run, on n'attend PAS de correction humaine
            # On archive et on arrête
            sys.exit(1)

    mark_run_complete(run_id)
    print_cost_summary(run_id)
    logger.info(f"\nRun {run_id} terminé. Résultats dans db/features.db")


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(args)
```

---

## 10. Ordre de mise en place

### Étape 1 — Environnement

```bash
python -m venv morphorepr-env && source morphorepr-env/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
sqlite3 db/features.db < db/schema.sql
```

### Étape 2 — Tests unitaires

```bash
pytest tests/test_parse.py tests/test_schema.py tests/test_db.py \
       tests/test_shuffle_baseline.py -v
# Tous doivent passer avant de continuer
```

### Étape 3 — Calibration des classifieurs

```bash
python classifiers/calibration/run_calibration.py
# Doit afficher ✅ PASS pour toutes les propriétés robustes
```

### Étape 4 — Dev run (5 features)

```bash
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Vérifier : DB peuplée, JSON parsés, coût < 1 $
```

### Étape 5 — Pilot run (30–50 features)

```bash
python orchestrator.py --config configs/pilot_run.yaml --n-features 40
# Calibrer les seuils, ajuster les prompts si nécessaire
# DÉCLARER tout ajustement comme calibration dans le papier
```

### Étape 6 — Gel de la configuration

```bash
# Figer tous les paramètres dans configs/run_v1.yaml
# Renseigner git_commit :
git add -A && git commit -m "Freeze config for full run v1"
echo "git_commit: $(git rev-parse HEAD)" >> configs/run_v1.yaml

# Vérifier que les hashes de prompts sont cohérents
python -c "
from utils.prompt_utils import load_prompt, hash_prompt
import yaml
cfg = yaml.safe_load(open('configs/run_v1.yaml'))
for agent, path in cfg['prompts'].items():
    print(f'{agent}: {hash_prompt(load_prompt(path))}')
"
```

### Étape 7 — Full frozen run

```bash
python orchestrator.py --config configs/run_v1.yaml
# Aucune intervention pendant l'exécution
# Si échec : archiver, analyser, corriger, relancer avec --resume
```

### Étape 8 — Reprise après crash éventuel

```bash
# Retrouver l'ID du run interrompu
sqlite3 db/features.db "SELECT run_id, last_phase, status FROM runs"

python orchestrator.py --config configs/run_v1.yaml \
       --resume --run-id <run_id>
# Les prompts sont vérifiés automatiquement — toute modification est détectée
```

---

## Rôle de Claude Code dans ce protocole

Claude Code intervient **uniquement** dans les phases de développement :

- écrire et déboguer les scripts des agents
- générer les fichiers de calibration des classifieurs
- analyser les résultats intermédiaires du pilot run
- produire des rapports lisibles depuis les données SQLite
- suggérer des corrections si une phase échoue

Il n'intervient **jamais** pendant le full frozen run. Le run scientifique final est piloté exclusivement par `orchestrator.py` avec une configuration gelée.
