# orchestrator.py
"""
Orchestrateur MorphoRepr v6.9.0 — run gelé et auditable.

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
