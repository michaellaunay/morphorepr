# MorphoRepr

**A Morphologically Structured Controlled Language for SAE Feature Description in LLMs**

*A Position Paper and Evaluation Protocol*

[![arXiv](https://img.shields.io/badge/arXiv-2606.XXXXX-B31B1B.svg)](https://arxiv.org/abs/2606.XXXXX)
[![HAL](https://img.shields.io/badge/HAL-hal--05649380-blue.svg)](https://hal.science/hal-05649380)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Paper: CC BY 4.0](https://img.shields.io/badge/Paper-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: Position Paper](https://img.shields.io/badge/status-position%20paper%20%26%20evaluation%20protocol-orange.svg)]()

---

## Overview

MorphoRepr is a controlled language for annotating the sparse features produced by Sparse Autoencoders (SAEs) trained on large language models (LLMs). It is inspired by the agglutinative grammar of Esperanto and provides a notation system that is compositional, formally specified, and human-legible.

Each MorphoRepr expression encodes human hypotheses about the semantics of one or more SAE latents as a weighted sum of morpheme chains:

```
0.87·mal-ag-int-e  +  0.41·soc-ant-o
```

Read as: *"not having acted physically (strength 0.87) plus a currently acting social entity (strength 0.41)"*.

MorphoRepr does not claim to decode the internal representations of LLMs. It encodes structured human hypotheses about SAE latent semantics — hypotheses that must be validated by activation prediction and causal intervention experiments. The central open question is whether agglutinative morphological composition provides a measurable advantage over existing structured annotation approaches, in particular Semantic Regexes (Boggust et al., 2025), in terms of annotation consistency, compactness, and causal predictive power.

The formal grammar, morpheme inventory, complete evaluation protocol, and longer-term research agenda are described in the accompanying position paper (see [Paper](#paper)).

---

## Contents

- [Motivation](#motivation)
- [Key Concepts](#key-concepts)
- [Evaluation Protocol](#evaluation-protocol)
- [Repository Structure](#repository-structure)
- [Current Status](#current-status)
- [Paper](#paper)
- [Citation](#citation)
- [Contact and Collaboration](#contact-and-collaboration)
- [License](#license)

---

## Motivation

SAE-based mechanistic interpretability has produced thousands of interpretable feature directions in production LLMs. The bottleneck is now labeling: natural language descriptions of SAE features can be useful and often accurate, but they are insufficiently structured for systematic evaluation, cross-feature comparison, and causal prediction. They are vague, inconsistent across annotation runs, and resist formal manipulation.

MorphoRepr addresses this by providing a notation system that is:

- **Compositional** — expressions are built from a finite, formally specified morpheme inventory following agglutinative composition rules
- **Consistent** — the same morpheme always carries the same formally bounded meaning
- **Human-legible** — expressions are pronounceable and learnable from a one-page reference table
- **Causally evaluable** — the evaluation protocol verifies that MorphoRepr expressions predict model behavior under feature steering, not merely describe activation patterns
- **Honestly bounded** — features that cannot be encoded with confidence are reported as UNCOVERED, which is a first-class output, not a failure

---

## Key Concepts

### Morpheme categories

The MorphoRepr inventory distinguishes five morpheme roles, following the grammar `(prefix)* root (infix)* suffix`:

| Role | Examples | Function |
|------|---------|---------|
| Prefix | `mal-`, `ne-`, `pli-`, `plej-`, `duon-` | polarity and degree modification |
| Root (predefined) | `ag`, `emo`, `sci`, `soc`, `dat`, `tem`, `lok`, `dir` | semantic domain |
| Root (free) | `far`, `pens` | pipeline-induced concepts, registered in versioned lexicon |
| Infix | `-ant-`, `-int-`, `-ad-`, `-ig-`, `-iĝ-` | agentivity and aspect |
| Syntactic suffix | `-o`, `-a`, `-e`, `-i` | nominal, adjectival, adverbial, infinitival |
| Tense suffix | `-as`, `-is`, `-os`, `-us` | present, past, future, conditional |

A predefined root belongs to the fixed vocabulary. A free root is induced by the agentic pipeline when no predefined root covers a feature cluster, and must be registered in the versioned lexicon before use. A free root may not collide with any existing prefix, infix, or suffix token.

### Coefficient normalization

An expression has the form `alpha1·word1 [+ alpha2·word2 ...]` where each coefficient is the normalized activation strength of the corresponding SAE latent, clipped to [0.01, 1.00] via:

```
alpha(f, x) = clip( a(f, x) / p99(f), 0.01, 1.00 )
```

where `p99(f)` is the 99th percentile activation of feature `f` on a reference corpus. In the static annotation context (not tied to a specific activation instance), the coefficient represents the encoder's confidence in the morpheme assignment.

### Lexicon governance

Free roots are registered in a versioned JSON lexicon with formal definition, scope statement, inducing feature cluster, and version timestamp. Morphological productivity metrics (features per root, free root rate, morpheme entropy) are tracked to detect drift from compositionality toward an ad hoc dictionary.

### MDE abstraction analogy

MorphoRepr can be understood by analogy with the Model-Driven Engineering abstraction hierarchy:

| MDE level | MorphoRepr equivalent |
|-----------|----------------------|
| M0 | A token in context, with its activation vector |
| M1 | A SAE latent — a learned direction in activation space |
| M2 | A MorphoRepr expression — structured encoding of one or more latents |
| M3 | The MorphoRepr morpheme inventory — self-describing primitive set |

This analogy is illustrative. SAE latents are not models in the MDE sense; MorphoRepr does not have the formal semantics of MOF.

---

## Evaluation Protocol

The evaluation protocol is described in full in the paper (Section 4). The key design choices are:

**Stratified corpus.** 500 SAE features split into easy (n=200, interpretability score >= 0.7), random (n=200, uniform sampling), and hard (n=100, score < 0.5 or context-dependent). All go/no-go thresholds are evaluated on the random set.

**Fidelity as discrimination task.** For each encoded feature, a fidelity judge receives the MorphoRepr annotation and must classify which of 40 candidate examples (20 top-activating, 20 matched controls) belong to the positive set. The metric is AUC-ROC.

**Causal validity via stratified output property classifiers.** Output properties are stratified by classifier reliability: robust (negation, tense, code presence, conditional modality), semi-robust (emotional valence), and fragile (agent presence, social reference, spatial reference). Causal validity conclusions are drawn primarily from robust and semi-robust properties, with bootstrap 95% confidence intervals.

**Go/no-go criterion.** The primary publication criterion is relative improvement over baselines with non-overlapping 95% bootstrap confidence intervals. MorphoRepr is considered to demonstrate causal utility if its causal validity score on the random set exceeds both natural language labels and Semantic Regexes with non-overlapping confidence intervals. The value 0.65 is retained as a minimum absolute floor only.

**Four baselines.** Natural language labels (LLM-generated, unconstrained), Semantic Regexes (Boggust et al., 2025 protocol), controlled keyword tags, and MorphoRepr shuffled (real annotations from other features, randomly reassigned within the same split at comparable length, repeated 10 times per feature).

**Human audit.** 50 features from the random split are annotated by two independent human annotators with adjudication by a third. Pipeline-vs-human morpheme Jaccard >= 0.60 is a publication threshold.

**Planned user study.** 20 NLP/ML researchers, within-subject counterbalanced design, measuring learning time, interpretation time, interpretation accuracy, annotation consistency, NASA-TLX cognitive load, and preference ranking across MorphoRepr, Semantic Regexes, and natural language labels.

---

## Repository Structure

```
morphorepr/
├── core/
│   ├── grammar.bnf              # Extended BNF specification
│   └── parser.py                # AST parser for MorphoRepr expressions
├── pipeline/
│   ├── orchestrator.py          # Deterministic scientific run entry point
│   ├── configs/
│   │   ├── dev_run.yaml
│   │   ├── pilot_run.yaml
│   │   └── run_v1.yaml          # Frozen config for full run
│   ├── agents/
│   │   ├── phase1_loader.py     # SAE feature extraction via sae_lens / Neuronpedia API
│   │   ├── phase2_inducer.py    # Lexicon induction: clustering + morpheme labeling
│   │   ├── phase3_encoder.py    # Feature encoding (2 independent runs)
│   │   ├── phase4_predictor.py  # Causal prediction from MorphoRepr expression only
│   │   ├── phase4_judge.py      # Causal validation via activation steering
│   │   └── phase5_report.py     # Stratified statistics and results synthesis
│   ├── classifiers/
│   │   ├── negation.py          # Robust: syntactic + lexical + morphological
│   │   ├── tense.py             # Robust: POS tagger
│   │   ├── code_presence.py     # Robust: token-level classifier
│   │   ├── modality.py          # Robust: syntactic pattern matching
│   │   └── valence.py           # Semi-robust: transformer-based sentiment
│   └── baselines/
│       ├── nl_labels.py
│       ├── semantic_regex.py
│       └── shuffled.py          # Within-split, length-matched shuffled control
├── db/
│   ├── schema.sql               # Complete versioned SQLite schema
│   └── lexicon/                 # Versioned JSON lexicon schemas
├── docs/
│   ├── paper_v0.26.pdf          # Current preprint (mirrored from HAL/arXiv)
│   └── morpheme_table.md        # Quick-reference morpheme inventory
├── tests/
│   ├── test_parse.py
│   ├── test_schema.py
│   ├── test_db.py
│   ├── test_shuffle_baseline.py
│   └── test_pipeline_e2e.py
└── README.md
```

---

## Current Status

This repository accompanies a position paper and evaluation protocol. No experimental results are yet available; they will be reported in v1.0 upon completion of the pipeline run.

| Component | Status |
|-----------|--------|
| Formal grammar (`grammar.bnf`) | Available |
| Predefined morpheme lexicon | Available |
| Paper v0.26 (HAL, published) | https://hal.science/hal-05649380 |
| Paper v0.26 (arXiv) | Under moderation |
| SQLite schema and DB utilities | Available |
| Batch API wrapper with retry | Available |
| Prompt versioning and hash verification | Available |
| Output property classifiers | Available |
| Classifier calibration protocol | Available |
| Unit tests | Available |
| Phase 1 — Feature extraction | In progress |
| Phase 2 — Lexicon induction | In progress |
| Phase 3 — Feature encoding | Planned |
| Phase 4 — Causal validation | Planned |
| Phase 5 — Results report | Planned |
| Human audit (50 features) | Planned |
| User study (20 participants) | Planned |
| Memory consolidation (Section 5) | Future work, contingent on Phase 4 results |

---

## Paper

> Launay, M. (2026). *MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol*. Version 0.26.

- **HAL (published):** https://hal.science/hal-05649380
- **arXiv (under moderation):** https://arxiv.org/abs/2606.XXXXX
- **PDF:** `docs/paper_v0.26.pdf`

The paper covers:

- Formal specification of the MorphoRepr grammar and morpheme inventory, including coefficient normalization convention (Section 3)
- Five-phase agentic evaluation pipeline with stratified feature splits, AUC-ROC fidelity discrimination task, stratified output property classifiers, within-split shuffled control, and planned human audit and user study (Section 4)
- Go/no-go criteria based on relative improvement over baselines with bootstrap confidence intervals (Section 4.5)
- Threats to validity: residual annotation circularity, classifier reliability tiers, steering magnitude calibration, English-language bias, cognitive cost, lexicon drift (Section 7.4)
- Positioning relative to natural language labels, Semantic Regexes (Boggust et al., 2025), SAELing (Huang et al., 2025), TCAV (Kim et al., 2018), and first-order logic (Section 6)
- Research agenda toward MorphoRepr-guided model editing and biologically-inspired memory consolidation, contingent on Phase 4 results (Section 5)

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
  note         = {Also available at \url{https://hal.science/hal-05649380}},
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

- Researchers in mechanistic interpretability or NLP with access to SAE infrastructure (in particular open-weight SAEs for models other than Claude 3 Sonnet)
- Doctoral supervisors interested in co-supervising a CIFRE thesis on this topic (target industrial partners: Mistral AI, LightOn, Hugging Face, or equivalent)
- Researchers who have worked on structured feature labeling, model editing (ROME/MEMIT), or biologically-inspired LLM memory architectures
- Annotators willing to participate in the planned human audit or user study

If you are interested in collaborating, co-authoring a follow-up paper, or supervising related doctoral work, please reach out by email or open a GitHub Discussion.

---

## License

The code in this repository is released under the [GNU Lesser General Public License v3.0 (LGPL v3)](LICENSE).

The accompanying paper is available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
