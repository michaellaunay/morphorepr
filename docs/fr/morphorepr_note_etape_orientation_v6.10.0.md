# MorphoRepr — Note d'étape : orientation v6.9.0 → v6.10.0

**Statut : orientation actée (décision d'architecture).** Cette note n'est pas une version livrée : elle fige *la décision* et *le plan* du prochain chantier. Le code, les configs et les tests décrits ici restent à produire en v6.10.0.

**Portée.** Décider de la *source de vérité du code* et préparer l'**orchestrateur Phase 4 end-to-end** (dev run reproductible, sans full run). Aucun claim scientifique du papier (v0.29) n'est touché ; la procédure v6.9.0 reste figée comme référence.

Document complémentaire à `morphorepr_test_procedure_v6.9.0.md`. Issu de la synthèse de trois relectures croisées (deux externes + une interne) qui ont toutes convergé.

---

## 1. Décision

À partir de la **v6.10.0**, le **dépôt Python devient la source de vérité du code** (option **B**). Le Markdown reste, mais cesse d'être l'artefact unique : il porte la **spécification scientifique, les règles méthodologiques, les ADR et le changelog**. Le code exécutable, les tests, les configs, les prompts et le SQL vivent désormais dans de vrais fichiers versionnés.

```text
Markdown  = protocole scientifique, règles, décisions (ADR), changelog, claims autorisés/interdits
Dépôt     = code canonique (.py), tests pytest, configs YAML, prompts, db/schema.sql, data/probes/
```

On **n'adopte pas** DOCX/PDF : ce serait pire pour la reproductibilité, les diffs Git, les tests et l'audit. Le bon format pour un protocole scientifique reproductible reste **Markdown + fichiers de code/config versionnés**.

L'option **C** (MD canonique + extracteur committé `make build && make test`) a été envisagée comme pont temporaire. Elle est écartée comme forme durable : elle maintient l'édition de code *dans la prose* (donc le risque de corruption) et ajoute une couche d'outillage à entretenir.

---

## 2. Pourquoi changer maintenant

Le déclencheur n'est pas esthétique : le chantier suivant est **exécution-centré**. Son critère d'acceptation n'est plus « c'est bien spécifié » mais « ça s'enchaîne réellement ». Trois signaux concrets :

1. **Le test ne peut pas importer du code resté en prose.** Un `tests/test_pipeline_phase4_e2e.py` fait `from agents import steerer`, `import orchestrator`. Tant que ces modules n'existent que sous forme de texte dans le MD v6.9.0, `pytest` ne peut rien importer. La forme cible *docs-as-code* présuppose donc la matérialisation du code embarqué — c'est le point de non-retour.
2. **Deux corruptions de fences en une seule session** (en-tête `CREATE TABLE api_usage` avalé ; fence de clôture de `causal_scorer` avalée, emportant le titre `## 8 bis`). Symptôme typique d'éditer du code *à l'intérieur* d'un document de ~7 700 lignes via remplacement de chaînes. Sur des `.py` réels, ces deux bugs n'existent pas.
3. **La taxe d'extraction** est devenue une infrastructure à part entière, non versionnée, qui grossit à chaque session : extraire les blocs par marqueur, stubber `anthropic`/`transformer_lens`/`sae_lens`, charger les modules via `exec`, rejouer les tests avec un faux `monkeypatch`/`conftest`. En dépôt réel, les **69 tests existants tournent en `pytest` natif** sans harnais maison.

---

## 3. Ordre de migration (impératif)

La structure cible (ADR + `dev_phase4.yaml` + tests + orchestrateur) ne peut pas être posée avant que les modules existent réellement. L'ordre propre est donc :

```text
1. Matérialiser le dépôt canonique depuis v6.9.0 (extraction mécanique par marqueur)
2. Ajouter conftest.py + fixtures test_db / monkeypatch → faire passer les 69 tests en pytest natif
3. Corriger l'ordre des phases de l'orchestrateur (voir §4)
4. Ajouter ADR-001 + configs/dev_phase4.yaml (+ variante minimale)
5. Implémenter l'orchestrateur Phase 4 end-to-end + tests (fakes + opt-in réel)
```

Construire l'orchestrateur **avant** l'étape 1 reviendrait à continuer sur du code encastré dans un MD — exactement ce qu'on veut abandonner.

### Arborescence cible (déjà décrite par le README)

```text
agents/            steerer.py, causal_scorer.py, baseline_predictor.py, encoder.py, …
utils/             db_utils.py, prompt_utils.py, model_provider.py, model_policy.py, api_utils.py
baselines/         shuffled.py
db/                schema.sql
configs/           run_v1.yaml, dev_phase4.yaml, dev_phase4_minimal.yaml
prompts/           …
data/probes/       probes_neutral.txt, probes_code.txt, …
tests/             test_steer_feature.py, test_causal_scorer.py, test_baseline_predictions.py,
                   test_intervention_controls.py, test_pipeline_phase4_e2e.py, conftest.py
docs/              morphorepr_test_procedure_v6.9.0.md (référence figée),
                   morphorepr_test_procedure_v6.10.0.md (section orchestrateur courte),
                   adr/ADR-001-phase4-orchestrator.md
orchestrator.py
```

---

## 4. Séquence Phase 4 corrigée (correction la plus importante)

L'orchestrateur v6.9.0 liste actuellement les phases dans cet ordre :

```text
p4_steer → p4_controls → p4_predict → p4_predict_baselines → p4_score → p4_qualitative → p5_report
```

C'est **inoffensif tant que tout est désactivé** (chaque phase s'auto-garde et fait no-op), mais **faux pour un dev run où tous les flags sont activés** : `p4_controls` est placé **avant** `p4_predict` et `p4_score`. Or :

- `causal_scorer._load_pairs()` (primaire) a besoin des sorties du **prédicteur MorphoRepr** (`p4_predict`) ;
- `run_intervention_controls()` / `assert_intervention_controls_ready()` dépendent à la fois des **prédictions MorphoRepr** et du **steering primaire**, et le scoring des contrôles se compare au score primaire.

Sans `p4_predict` en amont, le score primaire **et** les contrôles échouent. (Une première proposition de séquence omettait carrément `p4_predict` ; c'est l'erreur qui a été corrigée en synthèse.)

**Séquence dev correcte (cible v6.10.0) :**

```text
p4_steer
→ p4_predict            (prédiction MorphoRepr — INDISPENSABLE avant score et contrôles)
→ p4_predict_baselines  (nl_labels, semantic_regex — Option B)
→ p4_score              (macro-F1 primaire + comparaisons appariées baselines)
→ p4_controls           (contrôles d'intervention + score_intervention_controls, en DERNIER)
→ p4_dev_summary        (récapitulatif dev — NOUVELLE phase ; ne produit AUCUN claim full/pilot)
```

Le travail v6.10.0 inclut donc un **fix d'ordonnancement** de la liste `PHASES` (déplacer `p4_controls` après `p4_score`) et l'ajout d'un `p4_dev_summary`. `p4_qualitative` (juge LLM, secondaire) et `p5_report` restent inchangés.

---

## 5. `configs/dev_phase4.yaml` — exigences

Le dev run Phase 4 end-to-end est piloté par un **config dédié** (le seul supporté pour ce test), dérivé de `run_v1.yaml` avec les gardes explicitement activées. Au-delà de l'ossature, deux compléments sont nécessaires (relevés en relecture) :

- `proxy_model.enabled: true` — explicite, car `steer_feature()` / `_get_sae()` dépendent du chemin proxy open-weight (c'est déjà le défaut, mais un config de dev run doit le rendre visible) ;
- les **cibles statistiques** de comparaison, qui vivent sous `stats`, **pas** sous `causal_scoring`.

```yaml
run_mode: "dev"

proxy_model:
  enabled: true            # requis par steer_feature / _get_sae (chemin proxy open-weight)

steering:
  run_in_pipeline: true

baseline_predictions:
  enabled: true
  methods: [nl_labels, semantic_regex]

causal_scoring:
  run_in_pipeline: true
  run_baseline_comparisons: true
  strict_baselines: true

stats:                      # cibles des comparaisons appariées (lues par causal_scorer.run)
  superiority_vs: [nl_labels]
  non_inferiority_vs: [semantic_regex]

intervention_controls:
  run_in_pipeline: true
  score_controls: true
  strict_controls: true
  controls_to_run:
    - random_feature_same_layer
    - matched_activation_freq
    - random_direction_same_norm
    - negative_steering
    - prompt_only
```

`configs/dev_phase4_minimal.yaml` : même chose mais volumétrie réduite (sous-échantillon minimal, `controls_to_run` restreint, `run_baseline_comparisons` possiblement off) — pour un câblage rapide en CI.

**Note de cohérence des clés** (vérifiées contre le code v6.9.0) : `steering.run_in_pipeline`, `baseline_predictions.enabled`/`methods`, `causal_scoring.run_in_pipeline`/`run_baseline_comparisons`/`strict_baselines`, `stats.superiority_vs`/`non_inferiority_vs`, `intervention_controls.*` existent tous tels quels.

---

## 6. Stratégie de test (deux niveaux)

Un seul test opt-in « réel » ne suffit pas : dans un environnement restreint (sans `transformer_lens`/`sae_lens`, réseau limité à pypi/github/npm), le run gpt2/pythia + SAE réel est **systématiquement skippé**. Il faut donc :

1. **Test d'orchestration à fakes (s'exécute partout).** Modèle, SAE et provider monkeypatchés. Prouve le **câblage** : la séquence corrigée (§4) s'enchaîne sans erreur, chaque garde s'active, l'idempotence/reprise tient. C'est ce test qui donne la valeur prouvable immédiatement.
2. **Test e2e réel, opt-in (skippé ici).** Garde explicite :

```python
pytestmark = pytest.mark.skipif(
    os.environ.get("MORPHOREPR_RUN_DEV_PHASE4") != "1",
    reason="Phase 4 e2e test is opt-in (real proxy + SAE)",
)
```

**Assertions (noms vérifiés contre v6.9.0) :**

- `steering_results` non vide (à la magnitude primaire) ;
- `agent_outputs` de prédiction présents : `predictor` (MorphoRepr) **et** `predictor_nl_labels` / `predictor_semantic_regex` ;
- `metrics` contient `causal_macro_f1_global` (primaire) ;
- `intervention_control_results` non vide ;
- `metrics` contient `intervention_control_macro_f1:*` (et `intervention_control_paired_diff:*`), `model_run_id` renseigné, `phase='p4_controls'` ;
- **aucun** claim scientifique full/pilot n'est produit.

---

## 7. Garde-fous (inchangés)

- `run_v1.yaml` garde la Phase 4 **désactivée par défaut** ; `dev_phase4.yaml` est le **seul** config qui active la séquence end-to-end. **Aucune auto-activation** du full run.
- Métrique primaire **déterministe**, **sans juge LLM** ; contrôles en **métriques secondaires** uniquement.
- `diffmean_reft` reste **non implémenté** (`NotImplementedError` si activé).
- `model_run_id`-aware, `split`-aware, `intervention_space`-aware ; politique OOD respectée.
- **Aucune validation causale complète revendiquée** ; les claims du papier (v0.29) sont inchangés.

---

## 8. Ce qui reste figé

- `morphorepr_test_procedure_v6.9.0.md` : **référence méthodologique figée** (spec + changelog jusqu'à §28). Il n'embarquera plus le code une fois la migration faite ; il *pointera* vers le dépôt.
- Les **claims scientifiques** et le schéma logique (17 tables, dont `intervention_control_results`) sont inchangés.

---

## 9. Prochaine demande à formuler

Le chantier v6.10.0 n'est donc **pas** « ajouter une section au Markdown », mais :

> **Matérialiser le dépôt canonique depuis v6.9.0 + `conftest.py` + faire passer les 69 tests en `pytest` natif ; corriger l'ordre des phases ; ajouter `ADR-001` + `configs/dev_phase4.yaml` (+ variante minimale) ; implémenter l'orchestrateur Phase 4 end-to-end avec un test d'orchestration à fakes (exécutable) et un test e2e réel opt-in (`MORPHOREPR_RUN_DEV_PHASE4=1`).**

Séquence Phase 4 de référence à implémenter :

```text
p4_steer → p4_predict → p4_predict_baselines → p4_score → p4_controls → p4_dev_summary
```
