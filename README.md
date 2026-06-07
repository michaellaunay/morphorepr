# MorphoRepr

**A Morphologically-Structured Meta-Language for Human-Readable Projection of LLM Internal Representations**

[![arXiv](https://img.shields.io/badge/arXiv-2606.XXXXX-B31B1B.svg)](https://arxiv.org/abs/2606.XXXXX)
[![HAL](https://img.shields.io/badge/HAL-hal--XXXXXXX-blue.svg)](https://hal.science)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status: Framework](https://img.shields.io/badge/status-framework%20%26%20pipeline%20in%20progress-orange.svg)]()

---

MorphoRepr is a formal meta-language designed as a **human-readable projection layer** over the sparse, disentangled features produced by Sparse Autoencoders (SAEs) trained on large language models. It is inspired by the agglutinative grammar of Esperanto and maps directly to the Model-Driven Engineering (MDE/MOF) abstraction hierarchy.

Each MorphoRepr expression encodes one or more SAE features as a weighted sum of compositional morpheme chains:

```
0.87·mal-ag-int-e  +  0.41·soc-ant-o
```

Read as: *"not having acted physically (strength 0.87) plus a currently acting social entity (strength 0.41)"*.

The formal grammar, morpheme inventory, evaluation protocol, and a prospective memory consolidation architecture are described in the accompanying position paper (see [Paper](#paper)).

---

## Contents

- [Motivation](#motivation)
- [Key Concepts](#key-concepts)
- [Repository Structure](#repository-structure)
- [Current Status](#current-status)
- [Paper](#paper)
- [Citation](#citation)
- [Contact and Collaboration](#contact-and-collaboration)
- [License](#license)

---

## Motivation

SAE-based mechanistic interpretability has produced thousands of human-interpretable feature directions in production LLMs. The bottleneck is now *labeling*: natural language descriptions of features are accurate but vague, inconsistent across runs, and unsuitable for formal reasoning. MorphoRepr addresses this by providing a notation system that is:

- **Compositional** — expressions are built from a finite, formally specified morpheme inventory
- **Consistent** — the same morpheme always carries the same bounded meaning
- **Human-legible** — expressions are pronounceable and learnable from a one-page reference table
- **Causally grounded** — the evaluation protocol verifies that morphemes predict model behavior under feature steering, not merely describe activation patterns

---

## Key Concepts

### Morpheme categories

The MorphoRepr inventory distinguishes four morpheme roles, following the grammar `(prefix)* root (infix)* suffix`:

| Role | Examples | Function |
|------|---------|---------|
| Prefix | `mal-`, `ne-`, `pli-` | polarity and degree modification |
| Root (predefined) | `ag`, `emo`, `sci`, `soc`, `dat` | semantic domain |
| Root (free) | `far`, `pens`, `ver` | pipeline-induced concepts |
| Infix | `-ant-`, `-int-`, `-ad-`, `-ig-` | agentivity and aspect |
| Suffix | `-o`, `-a`, `-is`, `-as` | syntactic role and tense |

A predefined root is part of the fixed vocabulary. A free root is induced by the agentic pipeline when no predefined root covers a feature cluster, and is registered in the versioned lexicon.

### Weighted activation encoding

An expression has the form `α₁·word₁ [+ α₂·word₂ ...]` where each coefficient `α ∈ [0.01, 1.00]` is the normalized activation strength of the corresponding SAE feature. Terms are ordered by descending coefficient.

### MDE abstraction analogy

MorphoRepr occupies level M2 in the MOF abstraction tower applied to LLM representations:

| MDE level | LLM equivalent |
|-----------|---------------|
| M0 | A token in context, with its activation vector |
| M1 | A SAE feature — a direction in activation space |
| M2 | A MorphoRepr expression — formal encoding of one or more features |
| M3 | The MorphoRepr morpheme inventory — self-describing set of primitives |

### Prospective: memory consolidation

A future research direction (contingent on feasibility results) proposes inverting the pipeline to use MorphoRepr as a semantically typed write interface for targeted model editing (ROME/MEMIT-style), combined with a biologically-inspired two-stage memory architecture (external episodic buffer + parametric consolidation via LoRA). This direction is described in Section 5 of the paper and is **not yet implemented**.

---

## Repository Structure

```
morphorepr/
├── core/
│   ├── grammar.bnf          # Extended BNF specification (available)
│   └── parser.py            # AST parser for MorphoRepr expressions (in progress)
├── pipeline/
│   ├── phase1_loader.py     # SAE feature extraction via sae_lens / Neuronpedia API
│   ├── phase2_inducer.py    # Lexicon induction: k-means clustering + morpheme labeling
│   ├── phase3_encoder.py    # Automated feature encoding
│   ├── phase4_steer.py      # Causal validation via activation steering
│   └── phase5_report.py     # Coverage statistics and results synthesis
├── data/
│   └── lexicon/             # Versioned JSON lexicon schemas (available)
├── docs/
│   ├── paper.pdf            # Preprint (mirrored from arXiv)
│   └── morpheme_table.md    # Quick-reference morpheme inventory
├── tests/
│   └── test_parser.py       # Grammar conformance tests
└── README.md
```

---

## Current Status

This repository accompanies a position paper and methodological framework. The agentic evaluation pipeline (Phases 1–5) is currently running on the top-500 most frequent and interpretable SAE features of Claude 3 Sonnet (via Neuronpedia API). Experimental results will be added to the paper and this repository upon completion.

| Component | Status |
|-----------|--------|
| Formal grammar (`grammar.bnf`) | Available |
| Predefined morpheme lexicon | Available |
| Paper (arXiv / HAL) | Available |
| Phase 1 — Feature extraction | In progress |
| Phase 2 — Lexicon induction | In progress |
| Phase 3 — Feature encoding | Planned |
| Phase 4 — Causal validation | Planned |
| Phase 5 — Results report | Planned |
| Memory consolidation (Section 5) | Future work |

---

## Paper

> Launay, M. (2026). *MorphoRepr: A Morphologically-Structured Meta-Language for Human-Readable Projection of LLM Internal Representations*. arXiv:2606.XXXXX.

- **arXiv:** https://arxiv.org/abs/2606.XXXXX
- **HAL:** https://hal.science/hal-XXXXXXX
- **PDF:** [`docs/paper.pdf`](docs/paper.pdf)

The paper covers:
- Formal specification of the MorphoRepr grammar and morpheme inventory (Section 3)
- Five-phase agentic evaluation pipeline and success criteria (Section 4)
- Prospective memory consolidation architecture inspired by Complementary Learning Systems theory (Section 5)
- Positioning relative to Semantic Regexes (Boggust et al., 2025), SAELing (Huang et al., 2025), ROME/MEMIT, and first-order logic approaches (Section 6)

---

## Citation

If you use MorphoRepr in your research, please cite:

```bibtex
@misc{launay2026morphorepr,
  title        = {{MorphoRepr}: A Morphologically-Structured Meta-Language
                  for Human-Readable Projection of {LLM} Internal Representations},
  author       = {Launay, Micha\"{e}l},
  year         = {2026},
  eprint       = {2606.XXXXX},
  archivePrefix= {arXiv},
  primaryClass = {cs.CL},
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

This project is at an early stage and the author is actively seeking academic collaborators, in particular:

- Researchers in mechanistic interpretability or NLP with access to SAE infrastructure
- Doctoral supervisors interested in co-supervising a CIFRE thesis on this topic (target partners: Mistral AI, LightOn, Hugging Face, or equivalent)
- Anyone who has worked on structured feature labeling, model editing, or biologically-inspired LLM memory architectures

If you are interested in collaborating, co-authoring a follow-up paper, or supervising related doctoral work, please reach out by email or open a GitHub Discussion.

---

## License

This repository is released under the [MIT License](LICENSE).

The accompanying paper is available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
