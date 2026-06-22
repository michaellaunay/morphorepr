# MorphoRepr

**A Morphologically Structured Controlled Language for SAE Feature Description in LLMs**

*A Position Paper and Evaluation Protocol*

[![arXiv](https://img.shields.io/badge/arXiv-2606.XXXXX-B31B1B.svg)](https://arxiv.org/abs/2606.XXXXX)
[![HAL](https://img.shields.io/badge/HAL-hal--05649380-blue.svg)](https://hal.science/hal-05649380)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Paper: CC BY 4.0](https://img.shields.io/badge/Paper-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Paper v0.29](https://img.shields.io/badge/paper-v0.29-blue.svg)]()
[![Procedure v6.8.0](https://img.shields.io/badge/test%20procedure-v6.8.0-orange.svg)]()
[![Status: Specification](https://img.shields.io/badge/status-position%20paper%20%2B%20test%20specification-orange.svg)]()

---

## Overview

MorphoRepr is a controlled notation for describing sparse features produced by Sparse Autoencoders (SAEs) trained on large language models (LLMs). It is inspired by Esperanto-like agglutinative morphology and is designed to encode structured human hypotheses about SAE latent semantics.

A MorphoRepr expression represents one or more semantic hypotheses as a weighted sum of morpheme chains:

```text
0.87·mal-ag-int-e  +  0.41·soc-ant-o
```

Read approximately as: *“not having acted physically / action-negation in a past or completed form, with confidence or activation weight 0.87, plus a social actor / currently acting social entity with weight 0.41.”*

MorphoRepr does **not** claim to decode the internal representations of LLMs. It encodes structured, inspectable hypotheses about SAE features. These hypotheses must be evaluated through fidelity tests, activation prediction, and causal intervention experiments on a model where SAE activations are accessible.

The current paper is **v0.29**. The current test procedure is **v6.8.0**. The project is still a **position paper and experimental specification**: no full scientific run has been completed yet, and no causal validity result is claimed at this stage.

Starting with paper v0.29 and procedure v6.5.x, the protocol adopts an **open-weight reproducibility policy**: primary scientific claims are designed to be reproducible with open-weight or fully open models, and proprietary models (e.g. Anthropic) are used only as a secondary reference / comparison condition. See [Reproducibility and Open-Weight Models](#reproducibility-and-open-weight-models).

---

## Contents

- [Motivation](#motivation)
- [Key Concepts](#key-concepts)
- [Evaluation Protocol](#evaluation-protocol)
- [Reproducibility and Open-Weight Models](#reproducibility-and-open-weight-models)
- [Test Procedure v6.8.0](#test-procedure-v680)
- [Repository Structure](#repository-structure)
- [Current Status](#current-status)
- [Paper](#paper)
- [Citation](#citation)
- [Contact and Collaboration](#contact-and-collaboration)
- [License](#license)

---

## Motivation

SAE-based mechanistic interpretability has produced many sparse, often interpretable feature directions in language models. The bottleneck is no longer only feature discovery, but feature description and evaluation.

Natural-language feature labels are useful, but they are often vague, inconsistent across annotation runs, difficult to compare across features, and hard to evaluate causally. MorphoRepr addresses this by proposing a notation that is:

- **Compositional** — expressions are built from a bounded morpheme inventory and explicit word-formation rules.
- **Operationally specified** — the syntax, parsing rules, coefficient conventions, and evaluation metrics are explicit and testable.
- **Human-legible** — expressions are compact and intended to be learnable from a small reference table.
- **Causally evaluable** — the protocol tests whether annotations predict behavioral changes under feature steering.
- **Honestly bounded** — features that cannot be encoded with sufficient confidence are reported as `UNCOVERED`, rather than forced into misleading labels.

The central research question is whether agglutinative morphological composition provides a measurable advantage over natural-language labels and existing structured annotation approaches, especially Semantic Regexes, in terms of coverage, consistency, compactness, and causal predictive power. This is stated as a testable hypothesis, not a result.

---

## Key Concepts

### MorphoRepr expression

A MorphoRepr expression is a sum of weighted terms:

```text
coefficient·word [+ coefficient·word ...]
```

Each `word` follows the grammar:

```text
(prefix)* root (infix)* suffix
```

Example:

```text
0.87·mal-ag-int-e + 0.41·soc-ant-o
```

### Morpheme categories

| Role | Examples | Function |
|------|----------|----------|
| Prefix | `mal-`, `ne-`, `pli-`, `plej-`, `duon-` | polarity and degree modification |
| Predefined root | `ag`, `emo`, `sci`, `soc`, `dat`, `tem`, `lok`, `dir` | fixed semantic domain |
| Free root | `far`, `pens` | induced concept registered in the versioned lexicon |
| Infix | `-ant-`, `-int-`, `-ad-`, `-ig-`, `-iĝ-` | agentivity, aspect, causation, transformation |
| Syntactic suffix | `-o`, `-a`, `-e`, `-i` | nominal, adjectival, adverbial, infinitival role |
| Tense suffix | `-as`, `-is`, `-os`, `-us`, `-u` | present, past, future, conditional, imperative/subjunctive-like role |

Predefined roots belong to the fixed inventory. Free roots are introduced by the pipeline only when no predefined root adequately covers a feature cluster. They must be registered in the versioned lexicon and may not collide with reserved prefix, infix, or suffix tokens.

### Coefficients

The procedure distinguishes two coefficient types:

- **Confidence coefficients**: used in static annotations to express the encoder’s confidence in a morpheme assignment.
- **Activation coefficients**: used when an expression is tied to a specific feature activation instance.

For activation-bound use, coefficients may be normalized with respect to a feature’s 99th percentile activation:

```text
alpha(f, x) = clip(a(f, x) / p99(f), 0.01, 1.00)
```

The distinction between confidence and activation coefficients is explicit in the test procedure and database schema.

### Feature identity

A central correction in the v6 test procedure is the use of a robust feature identity:

```text
feature_uid = {model_name}:{sae_release}:{layer_index}:{hook_name}:{feature_index}
```

`feature_index` alone is not a stable identity: the same index can appear in multiple layers, hooks, SAE releases, or models. In the v6.8.0 procedure, `feature_uid` is the logical key used across agent outputs, baselines, shuffle controls, steering results, batch mappings, and user-study records.

### Model-run identity

Because the protocol now runs the same evaluation with several models (an open-weight primary model plus secondary / replication models), outputs are also keyed by the **model that produced them**:

```text
model_run_id  →  one (provider, model, revision, inference environment) within a run
```

`model_run_id` is recorded in the `model_runs` table and propagated (as a `NOT NULL` column) to `agent_outputs`, `baselines`, `api_usage`, `batches`, `batch_items`, and `steering_results`, so that multiple models can annotate the same `feature_uid` without collision, costs are attributed per model, and Phase 4 steering only consumes annotations from the intended model.

---

## Evaluation Protocol

The v0.29 paper and v6.8.0 procedure define an evaluation protocol centered on reproducibility, coverage, fidelity, and causal predictive validity.

### Feature splits

The planned full run uses 500 SAE features:

| Split | n | Sampling rule |
|-------|---|---------------|
| Random | 200 | sampled first, uniformly over the available feature corpus |
| Easy | 200 | sampled after random, with high interpretability score |
| Hard | 100 | sampled after random, with low interpretability score or context-dependent interpretation |

The random split is sampled first to avoid turning it into a residual “middle set.” Primary go/no-go thresholds are evaluated on the random split.

### Fidelity

Fidelity is evaluated as a discrimination task. Given an annotation, a judge or scoring mechanism must distinguish top-activating examples from matched controls. The planned metric is AUC-ROC.

### Causal validity

The primary causal score is not based on an LLM judge. It is deterministic:

1. a predictor derives expected output-property changes from an annotation;
2. steering is applied to the target SAE feature;
3. pre-registered classifiers measure observed output-property changes;
4. code compares predicted and observed directions.

The primary score is a **global macro-F1 over all `(feature, robust property)` pairs**, not a per-feature macro-F1 averaged afterward, with a feature-clustered bootstrap for confidence intervals.

### Baselines

The planned baselines are:

- natural-language labels;
- Semantic Regexes;
- controlled keyword tags;
- shuffled MorphoRepr annotations, matched within split and controlled for length.

MorphoRepr is tested for:

- **superiority** against natural-language labels, via a confidence interval on the feature-clustered paired difference that excludes 0;
- **non-inferiority** against Semantic Regexes, with a pre-registered margin;
- end-to-end utility, combining coverage and causal score.

> The earlier “non-overlapping confidence intervals” go/no-go rule is **obsolete**; it was replaced (from paper v0.27 on) by the paired-difference superiority test above plus the non-inferiority margin.

### End-to-end utility

Coverage is treated as part of the result. A method that gives strong labels for only a small subset of features is not equivalent to a method with broader coverage.

The protocol therefore reports both:

- conditional performance on the shared covered feature set;
- global utility over the full random set, using a pre-registered `UNCOVERED` / zero-score policy.

### Human audit and user study

The planned human evaluation includes:

- a human audit over 50 random-split features;
- independent annotation by two human annotators, with adjudication;
- morpheme-level agreement metrics such as Jaccard similarity;
- a planned user study with interpretation and production tasks across MorphoRepr, Semantic Regexes, and natural-language labels.

---

## Reproducibility and Open-Weight Models

Following a community call for the use of open models in research to guarantee reproducibility, the protocol no longer lets the main scientific conclusions depend on a single proprietary API model.

### Provider tiers (Rule 11)

- **Tier A — fully open / reproducible**: weights, tokenizer, inference code, configuration, hyperparameters, license, and (as far as possible) training-data information are documented and archivable.
- **Tier B — open-weight**: weights and tokenizer are public, but training data or some pre-training details are not fully open; reproducible *computationally* if exact revisions, hashes, and inference parameters are archived.
- **Tier C — proprietary API**: available only through a proprietary API; usable for comparison, development, or secondary analysis, but never as the sole basis of the main conclusions.

### Policy

- **Primary scientific claims** are computed on a Tier A/B model (the open primary model). Proprietary results (e.g. Anthropic) are reported as a **secondary reference / robustness condition**.
- A strong claim (e.g. *“MorphoRepr outperforms natural-language labels”*) is admissible only if it holds on the open primary model; otherwise it is phrased *“in the proprietary reference condition.”*
- Cross-model replication classifies each effect as **model-invariant**, **open-model-only**, **proprietary-only**, or **unstable**.
- The term “open source” is not applied to a model that only ships its weights without sufficient data/code/configuration; such a model is labeled **open-weight** (anti open-washing). The declared `provider_tier` reflects what is actually available, not vendor marketing.

### Inference abstraction

- Agents go through a common `ModelProvider` interface (`utils/model_provider.py`): `AnthropicProvider` (Tier C), `VLLMProvider`, `TransformersProvider`, `LlamaCppProvider`, with lazy heavy imports and a `build_provider` factory. Agents never instantiate `anthropic.Anthropic()` directly.
- `utils/api_utils.py` is a **legacy Anthropic Batch API wrapper**: the only place allowed to instantiate the Anthropic client, and only for the Tier C secondary condition.
- Policy guards (`utils/model_policy.py`): `validate_model_providers` (a full run requires a Tier A/B primary with pinned revisions/hashes/inference environment; Tier C is never primary), `assert_primary_claim_allowed` (the reporter refuses a primary claim from a Tier C model), and `classify_cross_model_effect`.

### Execution modes

- **Dev run**: Anthropic or a small local model; non-scientific results.
- **Pilot run**: must include at least one open-weight model; Anthropic may be used for comparison.
- **Full frozen run**: declares a `primary_reproducible` (Tier A/B) model; primary metrics are computed on it; Anthropic results are secondary; if conclusions differ between the open and proprietary models, the paper reports it explicitly.

### Archived artifacts

For each `model_run`, the protocol archives: exact model and tokenizer revisions, weight and tokenizer hashes, the inference image (Docker/Conda, CUDA version, backend version), precision and quantization, generation parameters (temperature, top-p, seed, max tokens), prompts (hashed), and raw outputs.

> Example model names in `model_providers` are illustrative. The full frozen run must pin an exact list of actually available, research-licensed models; any substitution after freezing requires a new `run_id`.

---

## Test Procedure v6.8.0

The current test procedure is **v6.8.0**. It is a robust experimental specification, not yet a completed implementation of Phase 4.

### What v6.8.0 stabilizes

The procedure includes:

- frozen and auditable runs driven by `python orchestrator.py --config configs/run_v1.yaml`;
- dev, pilot, and full execution modes;
- Git commit, config, prompt, lexicon, and corpus hashing;
- raw LLM output archival;
- crash-safe resume rules, including restoration of `model_run_ids` from the database on `--resume`;
- robust `feature_uid` identity across tables and joins;
- model-aware feature selection: `load_features_not_processed` filters by `model_run_id`, so a second model never sees a feature as already processed by the first;
- persistent `batch_items` mapping from Batch API `custom_id` to `feature_uid`, carrying `model_run_id`;
- atomic batch registration with `register_batch_with_items`;
- mandatory `batch_items` for feature-level batches;
- pre-submission validation that request `custom_id`s match `batch_items` exactly;
- model-aware batch resume: `get_unconsumed_batch` filters by `model_run_id`, so two models in the same run cannot resume each other’s batch;
- idempotent and non-silent agent output persistence;
- non-silent API cost logging with divergence detection and **per-model** cost attribution;
- budget estimation before batch submission;
- a single MorphoRepr parser based on hyphen segmentation;
- classifier calibration tables and reporting;
- `magnitude_key` for stable steering-result identity in both relative and absolute magnitude modes;
- `steering_duplicate_attempts` for audit of divergent steering reruns;
- `loading` → `running_frozen` run status transition after corpus freezing;
- a `model_runs` table and an open-weight reproducibility policy (Rule 11), with a legacy `model_run` explicitly created for the single-model path instead of relying on `NULL`;
- strictly model-aware Phase 4 loading: steering only consumes encoder annotations from the primary `model_run_id`;
- a real `steer_feature()` for the open-weight proxy path (TransformerLens + SAE Lens, `residual_add_decoder`): real before/after generations, measured latent activations, and `achieved_delta`; `sae_latent_clamp` and the production-model path raise explicit `NotImplementedError`;
- a real `causal_scorer._load_pairs()` assembling deterministic prediction/observation pairs for the primary macro-F1 (model/split/OOD-aware, no LLM judge);
- **baseline prediction (Option B)** for `nl_labels` and `semantic_regex` (new `agents/baseline_predictor.py`): baseline-specific prompts produce canonical direction predictions, making the **paired primary comparisons** (superiority vs NL, non-inferiority vs Semantic Regexes) runnable on a controlled dev run; baseline comparisons remain off by default;
- Phase 4 guards so that dev runs can execute outside steering/scoring.

### Current Phase 4 status

`steer_feature()` is **implemented for the open-weight proxy path** (TransformerLens + SAE Lens, `residual_add_decoder`): given `proxy_model.enabled=true`, it produces real `text_before`/`text_after` generations and measured `activation_before`/`activation_after`/`achieved_delta`/`ood_flag` per probe. The `sae_latent_clamp` mode and the nnsight / production-model path raise an explicit `NotImplementedError`.

`causal_scorer._load_pairs()` is **implemented** (v6.8.0): it assembles the deterministic prediction/observation pairs `(feature_uid, robust property)` for the primary macro-F1, strictly **model-aware, split-aware and OOD-aware**, reading predictions from `agent_outputs` and applying the deterministic classifiers to the steering `text_before`/`text_after`. No LLM judge is used in the primary metric. This enables a **minimal causal dev run for MorphoRepr**.

Still a contract:

- `run_intervention_controls()`.

Baseline prediction (**Option B**, v6.8.0) is **wired for `nl_labels` (superiority) and `semantic_regex` (non-inferiority)** via `agents/baseline_predictor.py`: from the annotations in the `baselines` table, baseline-specific prompts (no MorphoRepr terminology) produce canonical direction predictions stored in `agent_outputs` under `predictor_nl_labels` / `predictor_semantic_regex`. The steering is **not** re-run — only the prediction path differs — which is what makes the paired comparison valid. With `causal_scoring.run_baseline_comparisons=true` on a controlled dev run, `causal_scorer.run()` then computes each baseline's own score, the paired difference, the verdict and the coverage, guarded by `assert_baseline_predictions_ready()` (strict → `RuntimeError`; otherwise explicit skip **without a verdict** — never a false `pass`/`fail`). `keyword_tags` and `morphorepr_shuffled` remain **not wired** (explicit `NotImplementedError`). Baseline comparisons stay **off by default** (`run_baseline_comparisons=false`); no LLM judge is used in the primary metric, and **no full scientific result is claimed**.

Phase 4 is **disabled by default** (`steering.run_in_pipeline=false`, `causal_scoring.run_in_pipeline=false`) and is **not auto-enabled**; `assert_steering_ready()` must pass on a controlled dev run before any pilot/full run with steering. The v6.8.0 procedure is stable for a **dev run of the non-Phase-4 plumbing** and now also allows a **testable dev run of Phase 4 steering and a minimal MorphoRepr causal score on the open-weight proxy**, but it does **not** claim full causal validation: no published scientific result is asserted yet. The scientific claims of the paper (v0.29) are unchanged.

---

## Repository Structure

The intended repository structure is:

```text
morphorepr-pipeline/
├── CLAUDE.md
├── configs/
│   ├── dev_run.yaml
│   ├── pilot_run.yaml
│   └── run_v1.yaml
├── db/
│   ├── schema.sql            # includes the model_runs table (v6.5.x)
│   ├── features.db
│   └── lexicon.json
├── prompts/
│   ├── label_agent_v1.txt
│   ├── encoder_agent_v1.txt
│   ├── predictor_agent_v1.txt
│   ├── predictor_nl_labels_v1.txt
│   ├── predictor_semantic_regex_v1.txt
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
│   ├── baseline_predictor.py
│   ├── causal_scorer.py
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
│   ├── api_utils.py          # legacy Anthropic Batch API wrapper (Tier C secondary only)
│   ├── model_provider.py     # ModelProvider abstraction (open primary + Anthropic)
│   ├── model_policy.py       # Rule 11 guards (tiers, primary-claim, cross-model)
│   ├── prompt_utils.py
│   ├── config_utils.py
│   ├── morphorepr_parser.py
│   └── stats_utils.py
├── tests/
│   ├── conftest.py
│   ├── test_parser.py
│   ├── test_schema.py
│   ├── test_db.py
│   ├── test_classifiers.py
│   ├── test_shuffle_baseline.py
│   ├── test_batch_custom_id.py
│   ├── test_model_providers.py
│   ├── test_model_run_propagation.py
│   ├── test_steer_feature.py
│   ├── test_causal_scorer.py
│   ├── test_baseline_predictions.py
│   └── test_pipeline_e2e.py
├── data/
│   └── probes/
│       ├── probes_neutral.txt
│       ├── probes_code.txt
│       ├── probes_social.txt
│       ├── probes_temporal.txt
│       ├── probes_spatial.txt
│       ├── probes_affect.txt
│       └── probes_data.txt
├── logs/
├── checkpoints/
├── orchestrator.py
├── requirements.txt
└── README.md
```

---

## Current Status

This repository accompanies the v0.29 position paper and the v6.8.0 test procedure. No full experimental run has been completed yet.

| Component | Status |
|-----------|--------|
| Paper v0.29 | Written / current working version |
| Test procedure v6.8.0 | Stable for dev plumbing; steer_feature() implemented for the open-weight proxy path |
| Formal grammar and parser specification | Available |
| Predefined morpheme inventory | Available |
| Free-root governance | Specified |
| SQLite schema (incl. `model_runs`) | Specified (unchanged in v6.8.0) |
| `feature_uid` identity model | Specified and propagated |
| `model_run_id` multi-model identity | Specified and propagated (NOT NULL) |
| Open-weight reproducibility policy (Rule 11) | Specified |
| `ModelProvider` inference abstraction | Specified |
| Batch API crash-safety design | Specified |
| Prompt, lexicon, and corpus hashing | Specified |
| Output property classifiers | Specified |
| Classifier calibration protocol | Specified |
| Shuffle baseline | Specified |
| Human audit | Planned |
| User study | Planned |
| Phase 1 — Feature loading/ranking | Specification / implementation in progress |
| Phase 2 — Lexicon induction | Specification / implementation in progress |
| Phase 3 — Feature encoding | Specification / implementation in progress |
| Phase 4 — Steering | `steer_feature()` implemented for the open-weight proxy path; disabled by default |
| Phase 4 — Causal scoring | `causal_scorer._load_pairs()` implemented (MorphoRepr + baselines, model/split/OOD-aware); paired comparisons runnable; baseline comparisons off by default; disabled in pipeline by default |
| Phase 4 — Baseline prediction (Option B) | `nl_labels` + `semantic_regex` wired (`agents/baseline_predictor.py`); `keyword_tags` / `morphorepr_shuffled` not wired; off by default (`baseline_predictions.enabled=false`) |
| Phase 4 — Intervention controls | Contract only (`run_intervention_controls()` not implemented) |
| Phase 5 — Reporting | Planned |
| Full scientific results | Not yet available |

---

## Paper

> Launay, M. (2026). *MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol*. Version 0.29.

- **HAL:** https://hal.science/hal-05649380
- **arXiv:** https://arxiv.org/abs/2606.XXXXX
- **PDF:** `docs/paper_v0.29.pdf`
- **Test procedure:** `docs/morphorepr_test_procedure_v6.8.0.md`

The v0.29 paper covers:

- the MorphoRepr grammar and morpheme inventory;
- the distinction between confidence and activation coefficients;
- the feature identity problem and the use of robust feature identifiers;
- the five-phase evaluation pipeline;
- random-first split construction;
- deterministic causal scoring over feature/property pairs;
- coverage-aware end-to-end utility;
- comparison against natural-language labels, Semantic Regexes, keyword tags, and shuffled controls;
- the open-weight model tiers and reproducibility policy (primary claims on the open model, proprietary results as external comparison);
- threats to validity, including model-dependence and open-weight-vs-fully-open caveats;
- human audit and user-study design;
- future work on model editing and memory consolidation, contingent on causal validation results.

---

## Citation

If you use MorphoRepr in your research, please cite:

```bibtex
@misc{launay2026morphorepr,
  title        = {{MorphoRepr}: A Morphologically Structured Controlled Language
                  for {SAE} Feature Description in {LLMs} ---
                  A Position Paper and Evaluation Protocol},
  author       = {Launay, Micha\"{e}l},
  year         = {2026},
  eprint       = {2606.XXXXX},
  archivePrefix= {arXiv},
  primaryClass = {cs.CL},
  note         = {Version 0.29. Also available at \url{https://hal.science/hal-05649380}},
  url          = {https://arxiv.org/abs/2606.XXXXX}
}
```

---

## Contact and Collaboration

**Michaël Launay**  
Logikascium EURL, Fretin, France  
Enseignant vacataire — Université de Lille / ENSAM Lille / Polytech Lille  
michaellaunay@logikascium.com  
https://www.logikascium.com

This project is at an early stage. The author is actively seeking:

- researchers in mechanistic interpretability or NLP with access to SAE infrastructure;
- collaborators interested in structured feature labeling and causal evaluation;
- researchers working on Semantic Regexes, SAE feature descriptions, model editing, or memory mechanisms;
- doctoral supervisors interested in a CIFRE thesis on the topic;
- annotators willing to participate in the planned human audit or user study.

If you are interested in collaborating, co-authoring a follow-up paper, or supervising related doctoral work, please reach out by email or open a GitHub Discussion.

---

## License

The code in this repository is released under the [GNU Lesser General Public License v3.0 (LGPL v3)](LICENSE).

The accompanying paper is available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
