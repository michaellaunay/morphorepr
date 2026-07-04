-- db/schema.sql  —  Version 6.9.0 (PREMIER changement de schéma depuis 6.5.3 : ajout de la table
-- intervention_control_results), ne jamais modifier après le full run

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

-- v6.9.0 : PREMIER changement de schéma depuis v6.5.3. Table DÉDIÉE aux contrôles d'intervention
-- (run_intervention_controls). Séparée de steering_results pour ne PAS polluer le primaire et
-- parce qu'un contrôle a parfois DEUX features : la target (dont la prédiction MorphoRepr est
-- évaluée) et la control (celle réellement steerée). control_name distingue les contrôles ;
-- target_feature_uid rattache le résultat à la feature évaluée. Métriques SECONDAIRES uniquement.
CREATE TABLE IF NOT EXISTS intervention_control_results (
    control_result_id    TEXT PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES runs(run_id),
    model_run_id         TEXT NOT NULL REFERENCES model_runs(model_run_id),
    target_feature_uid   TEXT NOT NULL REFERENCES features(feature_uid),
    target_feature_index INTEGER NOT NULL,
    control_name         TEXT NOT NULL,
    control_feature_uid  TEXT REFERENCES features(feature_uid),   -- NULL pour random_direction/prompt_only
    control_feature_index INTEGER,
    intervention_space   TEXT,
    magnitude            REAL,
    magnitude_rel        REAL,
    magnitude_key        TEXT NOT NULL,
    probe_id             INTEGER NOT NULL,
    probe_family         TEXT,
    probe_category       TEXT,
    generation_index     INTEGER DEFAULT 0,
    text_before          TEXT NOT NULL,
    text_after           TEXT,
    activation_before    REAL,
    activation_after     REAL,
    achieved_delta       REAL,
    ood_flag             INTEGER DEFAULT 0,
    metadata_json        TEXT,            -- seed/norm/distance/annotation tronquée selon le contrôle
    created_at           TEXT NOT NULL,
    UNIQUE(
        run_id, model_run_id, target_feature_uid, control_name,
        control_feature_uid, intervention_space, magnitude_key,
        probe_family, probe_category, probe_id, generation_index
    )
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
CREATE INDEX IF NOT EXISTS idx_control_results ON intervention_control_results(run_id, model_run_id, target_feature_uid, control_name);
CREATE INDEX IF NOT EXISTS idx_batches_run ON batches(run_id, phase, agent_name, run_number);
