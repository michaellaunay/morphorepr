# ADR-001 — Phase 4 Orchestrator End-to-End Dev Run

- **Statut** : Accepté
- **Date** : 2026-07-04
- **Version dépôt** : v6.10.0, étape 2
- **Décideurs** : Michaël Launay (revue), Claude (proposition)
- **Contexte procédural** : la procédure de test **v6.9.0 reste la référence méthodologique
  figée** ; cet ADR ne modifie ni le protocole scientifique ni les claims du papier (v0.30).
  Il consigne des décisions d'implémentation du dépôt (docs-as-code, cf. note d'orientation
  v6.10.0).

---

## Contexte

L'ordre `PHASES` hérité du bloc v6.9.0 plaçait `p4_controls` immédiatement après `p4_steer`,
**avant** `p4_predict` et `p4_score`. Or :

1. `steerer.run_intervention_controls()` appelle `assert_intervention_controls_ready()`, qui
   **exige en DB des prédictions MorphoRepr (agent `predictor`) ET des `steering_results` à la
   magnitude primaire** ;
2. lorsque `intervention_controls.score_controls=true`, `causal_scorer.score_intervention_controls()`
   recharge les couples primaires via `_load_pairs()` — qui exige les mêmes prédictions.

Conséquence : la séquence échouait dès l'activation réelle de la Phase 4. Le bug était
indétectable tant que toutes les gardes `run_in_pipeline` restaient à `false` (cas de
`run_v1.yaml`). Un **tripwire xfail strict** avait été posé à l'étape 1
(`tests/test_orchestrator_phases.py`) pour empêcher d'oublier la correction.

Par ailleurs : `agents/predictor.py` était un stub (aucune prédiction MorphoRepr productible),
les classifieurs `tense`/`code_presence`/`modality` étaient des stubs (aucune observation
mesurable pour 3 des 4 propriétés robustes), `p4_qualitative` (juge LLM, **secondaire**)
partageait la garde `causal_scoring.run_in_pipeline` du score **primaire déterministe**
(couplage contraire à l'esprit de la Règle 8), et aucune configuration n'exécutait la
Phase 4 de bout en bout.

## Décision

1. **Ordre corrigé** (et figé par test) :
   `p4_steer → p4_predict → p4_predict_baselines → p4_score → p4_controls → p4_qualitative
   → p4_dev_summary → p5_report`. Les prédictions et le steering primaire précèdent le score
   ET les contrôles.

2. **`agents/predictor.py` implémenté**, miroir strict de `agents/baseline_predictor.py` :
   même seam `_build_primary_provider()` (ModelProvider primaire, Règle 11), même parseur de
   réponses (`_parse_prediction_response`, source unique), même politique d'erreur (réponse
   invalide → `status='error'`, jamais de `NO_CHANGE` silencieux), strictement
   model-aware/split-aware. **Entrée du prompt : l'expression MorphoRepr seule**
   (`$.expression` de l'agent `encoder`) — jamais la description NL (« same information
   budget », Règle 7). Prompt matérialisé : `prompts/predictor_agent_v1.txt` (4 propriétés
   canoniques, format JSON identique aux baselines).

3. **Garde propre pour le juge LLM** : `p4_qualitative` est désormais gardée par
   `qualitative_judge.enabled` (défaut `false`), **découplée** du score primaire déterministe.
   Comportement net de `run_v1.yaml` inchangé (clé absente → `false`, comme avant où
   `causal_scoring.run_in_pipeline=false` la désactivait déjà).

4. **Nouvelle phase `p4_dev_summary`** (`agents/dev_summary.py`) : exécutée **uniquement** si
   `run_mode=dev` (sinon skip loggé + refus interne, double garde). Écrit
   `logs/dev_summary_<run_id>.json` (comptes + métriques p4 telles qu'en DB) avec
   `"no_scientific_claim": true` et un DISCLAIMER explicite ; une seule métrique numérique
   (`dev_run_completed=1.0`, phase `p4_dev_summary`). Aucun claim pilot/full.

5. **Classifieurs robustes v1 matérialisés** : `classifiers/tense.py`,
   `classifiers/code_presence.py`, `classifiers/modality.py` — heuristiques **déterministes
   pure-python** (interface `measure(before, after)` identique à `negation`). Le lexique code
   exclut les mots-clés ambigus en prose anglaise (`this`, `class`, `return`, …), défaut
   détecté par la porte de qualité des sondes. **À calibrer avant tout pilot**
   (`classifiers/calibration`, matrices de confusion — Section 4.2 du papier).
   `classifiers/negation.py` (spaCy) inchangé.

6. **Sondes neutres pré-enregistrées** : `data/probes/probes_neutral.txt` (20 phrases,
   10–30 tokens). Porte de qualité automatisée et testée : **zéro signal** sur les 4
   propriétés robustes pour chaque ligne (sinon les `text_before` contaminent les deltas).

7. **Configurations dev** : `configs/dev_phase4.yaml` est la **seule** configuration activant
   la séquence Phase 4 end-to-end (`steering/causal_scoring/intervention_controls
   .run_in_pipeline=true`, `baseline_predictions.enabled=true`, `run_mode=dev`,
   `allow_unpinned_commit=true`) ; `configs/dev_phase4_minimal.yaml` en variante smoke
   (différences documentées en tête). **`configs/run_v1.yaml` est inchangé** : Phase 4 off par
   défaut, aucune auto-activation.

8. **Stratégie de test** (`tests/test_pipeline_phase4_e2e.py`) :
   - test d'orchestration **sur le vrai `run_pipeline`** (initialize_run réel : hash config /
     prompts / lexique, model_runs, budget) — les agents p1–p3 non implémentés sont remplacés
     par des fakes qui sèment un corpus dev de 4 features (une par propriété robuste) ;
     modèle/SAE/provider monkeypatchés ; scoring par les **vrais** classifieurs ;
   - vérifications : séquence complète `completed`, volumétrie steering exacte, macro-F1
     MorphoRepr = 1.0 par construction et NL < 1 (annotation faussée exprès), 5 contrôles
     produits **et** scorés (métriques secondaires), récapitulatif dev sans claim ;
   - **reprise idempotente** (`--resume` : aucune ligne modifiée) ;
   - **garde `strict_baselines`** : run archivé `failed` si les prédictions baselines manquent ;
   - porte de qualité des sondes neutres ;
   - **smoke réel opt-in** (`MORPHOREPR_RUN_DEV_PHASE4=1`) : `assert_steering_ready()` sur
     gpt2 + SAE `gpt2-small-res-jb` réels (téléchargements HF).
   Le tripwire xfail est **retiré** (rôle rempli) ; l'ordre cible devient un test passant.

## Conséquences

- La Phase 4 est **exécutable de bout en bout en dev** ; les gardes existantes
  (`assert_steering_ready`, `assert_intervention_controls_ready`,
  `assert_baseline_predictions_ready`, `strict_*`) sont désormais **exercées par la suite**.
- `run_v1.yaml` et la procédure v6.9.0 sont inchangés ; les claims du papier (v0.30) sont
  inchangés ; un dev run ne produit **aucun** résultat citable (affiché par `p4_dev_summary`).
- Suite de tests : 132 passed, 2 skipped (opt-in), 0 xfail.

## Limites connues (assumées à cette étape)

- Chemins `db/features.db` et `db/lexicon.json` **codés en dur** dans les hashes corpus/lexique
  de l'orchestrateur (la DB de travail, elle, est configurable via `MORPHOREPR_DB_PATH`) :
  le e2e monkeypatche `hash_corpus_canonical` ; un vrai dev run s'exécute à la racine du dépôt.
- Agents p1–p3 (`loader`, `ranker`, `cluster`, `labeler`, `consistency`, `encoder`,
  `fidelity`, baselines d'annotation) : **toujours des stubs** — le e2e les remplace par des
  fakes de semis ; leur implémentation reste un chantier distinct.
- Classifieurs v1 : heuristiques lexicales **non calibrées** (seuil 0.02, lexiques réduits) —
  calibration obligatoire avant pilot.
- `diffmean_reft` : toujours `NotImplementedError` (inchangé, volontaire).
- `datetime.utcnow()` déprécié (motif hérité de tout le codebase — nettoyage transverse à
  planifier séparément).

## Alternatives considérées

- *Conserver la garde partagée `causal_scoring.run_in_pipeline` pour `p4_qualitative`* :
  rejeté — couple un juge LLM secondaire au chemin primaire déterministe (Règle 8).
- *Désactiver `p4_controls` par configuration au lieu de réordonner* : rejeté — l'ordre
  resterait objectivement faux et la garde d'readiness resterait invérifiable en pipeline.
- *Skips conditionnels des phases p1–p3 dans l'orchestrateur* : rejeté — logique morte en
  production ; les fakes de test et la reprise (`last_phase`) couvrent le besoin sans toucher
  le chemin réel.
- *Procédure v6.10.0 complète (fork du MD v6.9.0)* : rejeté — v6.9.0 reste la référence
  figée ; une note courte (`docs/fr/morphorepr_test_procedure_v6.10.0.md`) pointe vers le
  dépôt et cet ADR (docs-as-code).
