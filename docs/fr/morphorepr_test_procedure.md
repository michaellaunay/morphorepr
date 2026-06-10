# MorphoRepr — Procédure de test complète (v4)
## Infrastructure expérimentale robuste pour une évaluation reproductible

---

## Principes directeurs

**Règle 1 — Séparation des rôles**
Claude Code sert au développement, au débogage et à la supervision uniquement. Le run expérimental final est piloté exclusivement par `python orchestrator.py --config configs/run_v1.yaml` — déterministe, sans modification de code, sans intervention agentique non tracée pendant l'exécution.

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

**Règle 5 — Repli sur modèle proxy**
Si l'accès direct aux activations de Claude 3 Sonnet n'est pas disponible, la phase de validation causale doit être exécutée sur un modèle proxy open-weight disposant de SAEs publics (ex. GPT-2, Pythia-6.9B ou Mistral-7B via `sae_lens`). Dans ce cas : (a) toutes les conclusions causales sont limitées au modèle proxy ; (b) les exemples Claude 3 Sonnet / Neuronpedia restent illustratifs uniquement ; (c) cela doit être déclaré explicitement dans la section Méthodes du papier.

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
│   └── probe_sentences.txt          ← 20 phrases-sondes neutres en anglais
├── logs/
└── checkpoints/
```

---

## 2. Fichier de configuration gelé

```yaml
# configs/run_v1.yaml

run_id_prefix: "morphorepr_v1"
description: "Full frozen run MorphoRepr v0.26 — 500 features"

# Reproductibilité
git_commit: "FILL_BEFORE_LAUNCH"    # vérifié contre le HEAD Git réel à l'init
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

# Splits du corpus
splits:
  easy:   {n: 200, min_interp_score: 0.7}
  random: {n: 200, filter: "uniform"}
  hard:   {n: 100, max_interp_score: 0.5}
primary_split: "random"              # tous les seuils go/no-go évalués ici

# Steering SAE
steering:
  magnitudes: [0, 2, 5, 10]
  primary_magnitude: 5
  n_probe_sentences: 20
  # Sous-échantillon pour la courbe dose-réponse (random.sample avec seed)
  n_subsample_for_curve: 50
  target_layer: "middle"             # "early"|"middle"|"late" — confirmer après pilot
  intervention_space: "residual"     # "residual"|"sae_latent"
  token_position: "all"              # "all"|"last"|"content_only"
  # OOD basé sur activation_p99 de la table features (PAS la norme W_dec)
  ood_threshold: 3.0

# Repli sur modèle proxy (si activations Claude 3 Sonnet indisponibles)
proxy_model:
  enabled: false                     # mettre true si Sonnet inaccessible
  name: "EleutherAI/pythia-6.9b"
  sae_release: "pythia-6.9b-res-jb"

# Baselines
baselines:
  - nl_labels
  - semantic_regex
  - keyword_tags
  - morphorepr_shuffled

# Contrôle mélangé
shuffle_control:
  n_repeats: 10
  within_split: true
  max_term_diff: 1
  preserve_coefficients: true
  # Shuffles évalués par classifieurs uniquement (pas le juge LLM) pour borner le coût
  use_llm_judge: false
  # Évalués sur le random split uniquement ; 10 répétitions agrégées avant IC
  evaluation_split: "random"

# Budget
budget:
  max_cost_usd: 150.0                # mettre à jour après estimation pilot run
  alert_at_usd: 75.0
  abort_on_exceed: true

# Seuils go/no-go (random split uniquement)
thresholds:
  coverage_easy_min: 0.65
  coverage_random_min: 0.45
  coverage_hard_min: 0.20
  fidelity_auc_min: 0.60
  causal_validity_floor: 0.50
  root_jaccard_min: 0.60
  human_audit_jaccard_min: 0.60
  free_root_rate_max: 5.0

# Seed de reproductibilité (sélection du sous-échantillon et contrôle mélangé)
seed: 42
```

---

## 3. Schéma SQLite complet (v4)

```sql
-- db/schema.sql  —  Version 4, ne jamais modifier après le full run

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
    corpus_hash     TEXT NOT NULL,    -- SHA256 de l'export CSV canonique trié
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
    feature_index   INTEGER PRIMARY KEY,
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
    layer           TEXT,
    sae_version     TEXT,
    neuronpedia_url TEXT,
    loaded_at       TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- Outputs bruts des agents (immuables)
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
-- Contrôle mélangé
-- shuffle_id est déterministe : {run_id}_{feature_index}_{shuffle_number}
-- La contrainte UNIQUE empêche les doublons en cas d'appels répétés
-- Les shuffles sont évalués par classifieurs uniquement (pas le juge LLM)
-- sur le random split uniquement ; 10 répétitions agrégées avant calcul des IC
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
-- Résultats de steering — texte et activations avant/après
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
    -- ood_flag : 1 si abs(activation_after) > activation_p99 * ood_threshold
    -- activation_p99 provient de la table features, PAS de la norme W_dec
    ood_flag            INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL
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
-- Résultats de l'étude utilisateur (hors pipeline ; stockés ici pour traçabilité)
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
    cognitive_load_score REAL,            -- score composite NASA-TLX
    preference_rank     INTEGER,
    created_at          TEXT NOT NULL
);

-- Index
CREATE INDEX IF NOT EXISTS idx_ao_feature  ON agent_outputs(feature_index, agent_name, run_number);
CREATE INDEX IF NOT EXISTS idx_metrics     ON metrics(run_id, split, metric_name);
CREATE INDEX IF NOT EXISTS idx_api_phase   ON api_usage(run_id, phase);
CREATE INDEX IF NOT EXISTS idx_steering    ON steering_results(run_id, feature_index, magnitude);
CREATE INDEX IF NOT EXISTS idx_batches_run ON batches(run_id, phase, agent_name, run_number);
```

---

## 4. Parseur MorphoRepr unique

```python
# utils/morphorepr_parser.py
"""
Parseur MorphoRepr déterministe.
Source unique de vérité pour TOUTES les métriques morphémiques.

Algorithme positionnel en 5 étapes pour chaque mot :
  1. Retirer le coefficient (avant '·')
  2. Lire les préfixes uniquement en tête du mot
  3. Lire le suffixe uniquement en queue du mot
  4. Détecter les infixes entre tirets dans le corps restant
  5. Extraire la racine comme partie restante

Aucun str.replace() global — parsing strictement positionnel partout.
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
    "mal", "ne", "pli", "plej", "duon",           # tokens de préfixe
    "ad", "int", "it", "ist", "ant", "at", "ig",  # tokens d'infixe
    "o", "a", "e", "i", "as", "is", "os", "us", "u"  # tokens de suffixe
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
    """Parse positionnel déterministe d'un seul mot MorphoRepr."""
    term = ParsedTerm(coefficient=0.0, raw_word=word)
    remaining = word.strip()

    # Étape 2 : lire les préfixes en tête (positionnel)
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
                term.parse_error = f"Préfixe terminal sans racine : {word}"
                return term
        else:
            break

    # Étape 3 : lire le suffixe en queue (correspondance la plus longue en premier)
    matched_suffix = None
    for s in sorted(ALL_SUFFIXES, key=len, reverse=True):
        if remaining.endswith(s):
            matched_suffix = s
            remaining = remaining[:-len(s)]
            break

    if not matched_suffix:
        term.parse_error = f"Aucun suffixe reconnu : {word}"
        return term

    term.suffix = matched_suffix
    term.suffix_type = ("tense" if matched_suffix in TENSE_SUFFIXES
                        else "syntactic")

    # Étape 4 : détecter les infixes dans le corps restant
    for ix in INFIXES:
        if ix in remaining:
            parts = remaining.split(ix, 1)
            before_infix = parts[0]
            after_infix  = parts[1] if len(parts) > 1 else ""
            if before_infix:
                term.infixes.append(ix.strip("-"))
                remaining = before_infix + ("-" + after_infix if after_infix else "")

    # Retirer les tirets résiduels du découpage d'infixes
    remaining = remaining.strip("-").strip()

    # Étape 5 : la racine est ce qui reste
    if not remaining:
        term.parse_error = f"Aucune racine extraite : {word}"
        return term

    term.root = remaining
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


def validate_free_root(root: str) -> Optional[str]:
    """
    Valide une racine libre candidate.
    Retourne None si valide, message d'erreur sinon.

    Note sur mal et ne :
      - Les deux sont dans PREDEFINED_ROOTS : valides comme racines prédéfinies
        (ex. "mal-o", "ne-a")
      - Les deux sont dans RESERVED_TOKENS : ne peuvent PAS être ré-enregistrés
        comme nouvelles racines libres par le pipeline
      Cette double appartenance est intentionnelle — voir commentaire sur
      RESERVED_TOKENS ci-dessus.
    """
    if root in PREDEFINED_ROOTS:
        return None  # les racines prédéfinies sont toujours valides
    if root in RESERVED_TOKENS:
        return f"La racine '{root}' est un token réservé"
    if not re.match(r'^[a-z]{2,5}$', root):
        return f"La racine '{root}' ne correspond pas à [a-z]{{2,5}}"
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
    """Retourne les features sans output pour cet agent/run_number. Idempotent."""
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
    """INSERT nommé — résistant aux évolutions de schéma."""
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
Wrapper Batch API avec reprise après crash.
La config est toujours passée explicitement — aucun appel load_config() ici.
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
    cost  = ((tokens_in  / 1_000_000) * rates["input"] +
             (tokens_out / 1_000_000) * rates["output"])
    return cost * (BATCH_DISCOUNT if is_batch else 1.0)


def build_batch_requests(features: list[dict],
                         system_prompt: str,
                         user_prompt_fn: Callable,
                         model: str,
                         max_tokens: int,
                         config: dict) -> list[dict]:
    """
    Config passée explicitement. Température ajoutée uniquement si use_temperature=True.
    Évite les HTTP 400 sur les modèles qui rejettent les paramètres de sampling non par défaut.
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
    Soumet un batch (ou récupère un batch non consommé existant) et retourne les résultats.
    Config passée explicitement partout.
    """
    existing = get_unconsumed_batch(run_id, phase, agent_name, run_number)
    if existing:
        logger.info(f"Reprise du batch non consommé {existing}")
        batch_id = existing
    else:
        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        register_batch(batch_id, run_id, phase, agent_name,
                       run_number, len(requests))
        logger.info(f"Batch soumis : {batch_id} ({len(requests)} requêtes)")

    elapsed = 0
    while elapsed < max_wait_seconds:
        status_obj = client.messages.batches.retrieve(batch_id)
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
    rows = conn.execute(
        "SELECT * FROM features ORDER BY feature_index"
    ).fetchall()
    conn.close()
    buf    = io.StringIO()
    writer = csv.writer(buf)
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
        "reliability_note": ("Semi-robuste : interpréter avec prudence sur du texte "
                             "technique, ironique ou à forte densité de code.")
    }
```

### 6.3 Calibration des classifieurs

```python
# classifiers/calibration/run_calibration.py
"""
Doit passer avant le pilot run. Toutes les propriétés robustes requièrent une calibration.
"""
import json
from pathlib import Path

def calibrate(measure_fn, test_file: str,
              property_name: str,
              min_accuracy: float = 0.85) -> bool:
    data    = json.loads(Path(test_file).read_text())
    correct = sum(
        1 for ex in data
        if measure_fn([ex["text_before"]], [ex["text_after"]])["direction"]
           == ex["expected_direction"]
    )
    accuracy = correct / len(data)
    status   = "✅ PASS" if accuracy >= min_accuracy else "❌ FAIL"
    print(f"{status} {property_name}: {accuracy:.1%} "
          f"({correct}/{len(data)}) — seuil : {min_accuracy:.0%}")
    return accuracy >= min_accuracy

if __name__ == "__main__":
    from classifiers import negation, tense, code_presence, modality, valence

    results = [
        calibrate(negation.measure,
                  "calibration/negation_test.json",
                  "negation_presence",   0.85),
        calibrate(tense.measure,
                  "calibration/tense_test.json",
                  "tense",               0.85),
        calibrate(code_presence.measure,
                  "calibration/code_presence_test.json",
                  "code_presence",       0.90),
        calibrate(modality.measure,
                  "calibration/modality_test.json",
                  "conditional_modality", 0.85),
        calibrate(valence.measure,
                  "calibration/valence_test.json",
                  "negative_valence",    0.80),
    ]
    if not all(results):
        raise SystemExit(
            "Calibration échouée — corriger les classifieurs avant le pilot run."
        )
    print("\nTous les classifieurs calibrés — prêt pour le pilot run.")
```

---

## 7. Agent de steering — spécification complète (v4)

```python
# agents/steerer.py
"""
Phase 4 — Steering d'activation SAE.

Spécification de l'intervention :
  - Espace :          résiduel (residual stream), après reconstruction SAE
  - Couche :          configurée dans run_v1.yaml (steering.target_layer)
  - Position token :  configurable ("all" | "last" | "content_only")
  - Amplitude :       normalisée (stockée en unités d'activation absolues dans la config)
  - Contrôle :        magnitude=0 toujours exécuté comme ligne de base
  - Dose-réponse :    [0, 2, 5, 10] sur sous-échantillon de 50 features (random split, seedé)
  - Tous les features : magnitude primaire (5) + contrôle (0) uniquement
  - Détection OOD :   abs(activation_after) > activation_p99 * ood_threshold
                      où activation_p99 provient de la table features,
                      PAS de la norme sae.W_dec[feature_index]

Chemins d'accès au modèle (implémenter l'un d'eux avant le pilot run) :
  A. TransformerLens — pour les modèles proxy open-weight de style GPT
  B. nnsight         — si accès direct à Claude disponible
  C. Poids locaux    — si modèle open-weight compatible SAE disponible

Repli sur modèle proxy :
  Si les activations de Claude 3 Sonnet sont indisponibles, mettre
  proxy_model.enabled=true dans run_v1.yaml. Toutes les conclusions causales
  seront alors limitées au modèle proxy. Les exemples Claude 3 Sonnet restent
  illustratifs uniquement. À déclarer explicitement dans la section Méthodes.
"""
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


def _get_sae(config: dict):
    """
    Charge le SAE pour le modèle et la couche cibles.
    Implémenter l'un des trois chemins avant le pilot run.
    """
    proxy = config.get("proxy_model", {})
    if proxy.get("enabled"):
        from sae_lens import SAE
        sae, _, _ = SAE.from_pretrained(
            release=proxy["sae_release"],
            sae_id=f"blocks.{config['steering']['target_layer']}.hook_resid_post"
        )
        return sae
    raise NotImplementedError(
        "_get_sae() non implémenté.\n"
        "Pour débloquer :\n"
        "  A. Mettre proxy_model.enabled=true et utiliser un SAE public, OU\n"
        "  B. Implémenter l'accès au SAE Claude 3 Sonnet via sae_lens/nnsight.\n"
        "Valider en dev run avant le pilot run."
    )


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


def load_probe_sentences(n: int = 20) -> list[str]:
    """
    Charge les phrases-sondes neutres en anglais.
    Exigences : 10–30 tokens chacune, sans contenu émotionnel ou technique fort,
    sans entités nommées, sans marqueurs de négation.
    """
    path = Path("data/probe_sentences.txt")
    if not path.exists():
        raise FileNotFoundError(
            "data/probe_sentences.txt introuvable.\n"
            "Créer ce fichier avec 20 phrases neutres avant le dev run."
        )
    sentences = [l.strip() for l in path.read_text().splitlines()
                 if l.strip()][:n]
    if len(sentences) < n:
        raise ValueError(
            f"Seulement {len(sentences)} phrases-sondes disponibles, {n} requises."
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
    Applique le steering et retourne les paires avant/après.

    La détection OOD utilise activation_p99 depuis feature_stats (chargé depuis
    la table features), PAS sae.W_dec[feature_index].norm() qui est une grandeur
    différente (norme d'un vecteur direction vs percentile d'une distribution
    d'activation).

    Étapes d'implémentation :
    1. Tokeniser la phrase-sonde
    2. Forward pass, enregistrer l'activation résiduelle à la couche cible
    3. Modifier le résiduel : ajouter magnitude * sae.W_dec[feature_index]
       aux positions token configurées
    4. Ré-exécuter le forward pass avec le résiduel modifié
    5. Décoder les sorties avant et après
    6. Mesurer l'activation réelle obtenue (pour la vérification OOD)
    """
    ood_thresh     = config["steering"]["ood_threshold"]
    activation_p99 = feature_stats.get("activation_p99")

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

            # Détection OOD utilisant activation_p99 depuis la table features
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
                "ood_flag":          0,
                "error":             str(e)
            })
    return results


def run(run_id: str, config: dict):
    """Phase 4 — Steering. Courbe dose-réponse sur sous-échantillon seedé."""
    from utils.db_utils import get_conn

    logger.info("Phase 4 : Steering SAE")

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

    # Sous-échantillon seedé — PAS [:n] qui dépendrait de l'ordre de la DB
    rng       = random.Random(seed)
    subsample = rng.sample(random_features,
                           min(n_subsample, len(random_features)))
    subsample_indices = {f["feature_index"] for f in subsample}

    # Sous-échantillon : courbe dose-réponse complète
    _run_steering_batch(run_id, model, sae, subsample,
                        all_magnitudes, probe_sentences, config)

    # Features restants : magnitude primaire + contrôle uniquement
    remaining = [f for f in random_features
                 if f["feature_index"] not in subsample_indices]
    _run_steering_batch(run_id, model, sae, remaining,
                        [0, primary_mag], probe_sentences, config)

    logger.info("Phase 4 steering terminée")


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

## 8. Baseline MorphoRepr mélangé

```python
# baselines/shuffled.py
"""
Contrôle MorphoRepr mélangé.
- Intra-split uniquement (pas de contamination croisée)
- Longueur d'expression appariée ±1 terme
- 10 répétitions par feature, seedées
- shuffle_id déterministe : {run_id}_{feature_index}_{shuffle_number}
- UNIQUE(run_id, feature_index, shuffle_number) empêche les doublons
- Évalués par classifieurs uniquement (pas le juge LLM) pour borner le coût
- Évalués sur le random split uniquement ; 10 répétitions agrégées avant IC
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

    rng     = random.Random(seed)
    inserts = []
    for split, features in by_split.items():
        for feat in features:
            n_feat     = feat["n_terms"]
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
                source     = rng.choice(candidates)
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

    logger.info(f"Shuffles générés : {len(inserts)} ({n_repeats} par feature)")
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
    parse_expression, parse_word, validate_free_root
)


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


class TestValidateFreeRoot:
    def test_racine_libre_valide(self):
        assert validate_free_root("pens") is None
        assert validate_free_root("far") is None

    def test_token_reserve_rejete(self):
        assert validate_free_root("is") is not None
        assert validate_free_root("ad") is not None

    def test_mal_ne_sont_predefinies_non_libres(self):
        # mal et ne sont des racines PRÉDÉFINIES valides — validate_free_root
        # retourne None pour les racines prédéfinies
        assert validate_free_root("mal") is None
        assert validate_free_root("ne")  is None

    def test_trop_long_rejete(self):
        assert validate_free_root("toolong") is not None

    def test_majuscule_rejetee(self):
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
            feature_index, split, nl_description, top_examples,
            score_interp, activation_freq,
            activation_p99, activation_mean, activation_std,
            layer, sae_version, neuronpedia_url, loaded_at
        ) VALUES (?,?,'desc','[]',0.8,0.5,2.1,0.8,0.4,'l1','s1','http://x',
                  '2026-01-01T00:00:00')
    """, (index, split))


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
        "raw", "ok", None, 100, 50, None, 0.001
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


def test_shuffle_pas_auto_assigne(test_db):
    """Un feature ne doit jamais recevoir sa propre annotation."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", n_repeats=3)
    conn = sqlite3.connect(test_db)
    rows = conn.execute(
        "SELECT feature_index, source_feature FROM shuffle_controls"
    ).fetchall()
    conn.close()
    assert all(r[0] != r[1] for r in rows)


def test_shuffle_contrainte_unicite(test_db):
    """La contrainte UNIQUE empêche les doublons logiques."""
    _setup_features_encodees(test_db)
    generate_shuffles("r1", n_repeats=3)
    generate_shuffles("r1", n_repeats=3)  # deuxième appel — pas de doublons
    conn = sqlite3.connect(test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM shuffle_controls WHERE run_id='r1'"
    ).fetchone()[0]
    conn.close()
    assert count <= 5 * 3   # max 15 entrées pour 5 features × 3 répétitions
```

---

## 10. Orchestrateur

```python
# orchestrator.py
"""
Orchestrateur MorphoRepr v4 — déterministe et auditable.

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
    if config_commit != "FILL_BEFORE_LAUNCH" and config_commit != git_commit:
        raise RuntimeError(
            f"git_commit dans la config ({config_commit[:8]}) ne correspond pas "
            f"au HEAD courant ({git_commit[:8]}). "
            f"Mettre à jour configs/run_v1.yaml avant le lancement."
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

    logger.info(f"Run initialisé : {run_id}")
    logger.info(f"  Git commit    : {git_commit[:16]}")
    logger.info(f"  Config hash   : {config_hash[:16]}")
    logger.info(f"  Corpus hash   : {corpus_hash[:16]}")
    logger.info(f"  Lexique hash  : {lexicon_hash[:16]}")
    if proxy.get("enabled"):
        logger.info(f"  Modèle proxy  : {proxy.get('name')} (Sonnet inaccessible)")
    return run_id


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
    current_corpus  = hash_corpus_canonical("db/features.db")
    current_lexicon = hash_lexicon_canonical("db/lexicon.json")

    errors = []
    if row["git_commit"] != current_git:
        errors.append(
            f"Commit Git modifié : {row['git_commit'][:8]} → {current_git[:8]}"
        )
    if row["config_hash"] != current_config:
        errors.append("Config modifiée depuis le run original")
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
    ("p1_load",        lambda rid, cfg: loader.run(rid),           "Extraction SAE"),
    ("p1_rank",        lambda rid, cfg: ranker.run(rid, cfg),       "Stratification splits"),
    ("p2_cluster",     lambda rid, cfg: cluster.run(rid),           "Clustering"),
    ("p2_label",       lambda rid, cfg: labeler.run(rid),           "Induction lexique"),
    ("p2_consistency", lambda rid, cfg: consistency.run(rid),       "Validation lexique"),
    ("p3_encode",      lambda rid, cfg: encoder.run(rid),           "Encodage (2 runs)"),
    ("p3_fidelity",    lambda rid, cfg: fidelity.run(rid),          "Fidélité AUC-ROC"),
    ("p3_baselines",   lambda rid, cfg: _run_baselines(rid),        "Baselines"),
    ("p3_shuffle",     lambda rid, cfg: shuffled_baseline.generate_shuffles(rid),
                                                                     "Contrôle mélangé"),
    ("p4_steer",       lambda rid, cfg: steerer.run(rid, cfg),      "Steering"),
    ("p4_predict",     lambda rid, cfg: predictor.run(rid),         "Prédiction causale"),
    ("p4_judge",       lambda rid, cfg: judge.run(rid),             "Validation causale"),
    ("p5_report",      lambda rid, cfg: reporter.run(rid),          "Synthèse"),
]


def run_pipeline(args):
    Path("logs").mkdir(exist_ok=True)
    config = load_config(args.config)

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
_get_sae(cfg)
print('Accès modèle OK')
"
# Si NotImplementedError : implémenter _get_model() / _get_sae() d'abord.
# Si proxy : mettre proxy_model.enabled=true dans dev_run.yaml

# ── 5. Dev run (5 features — plomberie) ─────────────────────
python orchestrator.py --config configs/dev_run.yaml --n-features 5
# Vérifier : DB peuplée, JSON parsés, coût < 1$, steering produit une sortie

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
