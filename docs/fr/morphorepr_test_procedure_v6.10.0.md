# Procédure de test MorphoRepr — note v6.10.0 (étape 2 : orchestrateur Phase 4)

> **Statut.** La référence méthodologique figée reste **`morphorepr_test_procedure.md`
> (v6.9.0)** : protocole scientifique, règles (1–11), seuils, schéma. La présente note ne la
> remplace pas ; elle consigne ce que la version **v6.10.0 du dépôt** ajoute côté
> implémentation (docs-as-code : le code canonique vit dans le dépôt, pas dans le Markdown).
> Décisions détaillées : **`adr/ADR-001-phase4-orchestrator.md`**.

## Ce que l'étape 2 câble

- **Ordre Phase 4 corrigé et figé par test** :
  `p4_steer → p4_predict → p4_predict_baselines → p4_score → p4_controls → p4_qualitative
  → p4_dev_summary → p5_report` (les prédictions et le steering primaire précèdent le score
  et les contrôles — exigence des gardes d'readiness).
- **`agents/predictor.py`** : prédicteur MorphoRepr réel (miroir de `baseline_predictor`,
  expression seule en entrée, `status='error'` si réponse invalide).
- **Classifieurs robustes v1** : `classifiers/tense.py`, `classifiers/code_presence.py`,
  `classifiers/modality.py` — déterministes, pure-python, **à calibrer avant pilot**.
- **`agents/dev_summary.py`** (`p4_dev_summary`, `run_mode=dev` uniquement) : récapitulatif
  JSON avec `no_scientific_claim: true` — un dev run ne produit **aucun** chiffre citable.
- **Garde propre du juge LLM** : `qualitative_judge.enabled` (défaut `false`), découplée du
  score primaire déterministe (Règle 8).
- **Sondes neutres pré-enregistrées** : `data/probes/probes_neutral.txt` (20 phrases,
  zéro signal sur les 4 propriétés robustes — porte de qualité testée).
- **Prompt prédicteur matérialisé** : `prompts/predictor_agent_v1.txt` (4 propriétés
  canoniques, format JSON identique aux baselines — Annexe B.3 du papier v0.30).

## Lancer le dev run Phase 4

```bash
# Séquence complète (fakes non requis : gardes réelles, volumétrie dev)
python3 orchestrator.py --config configs/dev_phase4.yaml

# Variante smoke (contrôles réduits, comparaisons baselines off)
python3 orchestrator.py --config configs/dev_phase4_minimal.yaml
```

`configs/dev_phase4.yaml` est la **seule** configuration activant la Phase 4 ;
**`configs/run_v1.yaml` est inchangé** (Phase 4 off, aucune auto-activation). Un run gelé
exige toujours le commit épinglé ; `allow_unpinned_commit: true` est réservé au dev.

## Tests

```bash
python3 -m pytest -q                                   # 132 passed, 2 skipped (opt-in)
python3 -m pytest tests/test_pipeline_phase4_e2e.py -q # orchestration end-to-end (fakes)
MORPHOREPR_RUN_DEV_PHASE4=1 python3 -m pytest tests/test_pipeline_phase4_e2e.py -k real
```

Le test e2e exécute le **vrai** `run_pipeline` (hash config/prompts/lexique, model_runs,
gardes, reprise idempotente, échec contrôlé `strict_baselines`) ; seuls les agents p1–p3
(stubs), le modèle/SAE et le provider sont remplacés par des fakes déterministes.

## Invariants réaffirmés

Métrique primaire **déterministe sans juge LLM** ; `diffmean_reft` non implémenté
(`NotImplementedError`) ; strictement `model_run_id`/split/`intervention_space`-aware ;
politique OOD respectée ; claims du papier (v0.30) inchangés ; **aucune validation causale
complète n'est revendiquée** — les chiffres d'un dev run ne sont jamais cités.
