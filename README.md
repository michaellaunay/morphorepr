# MorphoRepr

**A Morphologically Structured Controlled Language for SAE Feature Description in LLMs**

[![arXiv](https://img.shields.io/badge/arXiv-2606.XXXXX-B31B1B.svg)](https://arxiv.org/abs/2606.XXXXX)
[![HAL](https://img.shields.io/badge/HAL-hal--XXXXXXX-blue.svg)](https://hal.science)
[![License: LGPL v3](https://img.shields.io/badge/License-LGPL_v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: Position Paper](https://img.shields.io/badge/status-position%20paper%20%26%20protocol-orange.svg)]()

---

MorphoRepr is a morphologically structured controlled language for annotating the sparse features produced by Sparse Autoencoders (SAEs) trained on large language model activations. It is inspired by the agglutinative grammar of Esperanto and provides a notation that is compositional, formally specified, and causally testable.

Each MorphoRepr expression encodes one or more SAE latents as a weighted sum of compositional morpheme chains:

```
0.87·mal-ag-int-e  +  0.41·soc-ant-o
```

Read as: *"not having acted physically (strength 0.87) plus a currently acting social entity (strength 0.41)"*.

**Scope.** MorphoRepr does not claim to decode the internal representations of LLMs. It encodes structured human hypotheses about SAE latent semantics — hypotheses that must be validated by activation prediction and causal intervention experiments. The central open question is whether agglutinative morphological composition provides a measurable advantage over existing alternatives (in particular Semantic Regexes, Boggust et al., 2025) in annotation consistency and causal predictive power.

The formal grammar, morpheme inventory, complete evaluation protocol, and a prospective research agenda are described in the accompanying position paper (see [Paper](#paper)).

---

## Contents

- [Motivation](#motivation)
- [Key Concepts](#key-concepts)
- [Repository Structure](#repository-structure)
- [Installation](#installation)
- [Current Status](#current-status)
- [Paper](#paper)
- [Citation](#citation)
- [Contact and Collaboration](#contact-and-collaboration)
- [License](#license)

---

## Motivation

SAE-based mechanistic interpretability has produced thousands of human-interpretable feature directions in production LLMs. The bottleneck is now *labeling*: natural language descriptions of features can be useful and often accurate, but they are insufficiently structured for systematic evaluation, cross-feature comparison, and causal prediction. They are vague, inconsistent across annotation runs, and unsuitable for formal reasoning over large feature inventories.

MorphoRepr addresses this by providing a notation system that is:

- **Compositional** — expressions are built from a finite, formally specified morpheme inventory following agglutinative concatenation rules
- **Consistent** — the same morpheme always carries the same bounded, formally defined meaning
- **Human-legible** — expressions are pronounceable and interpretable from a one-page reference table
- **Causally testable** — the evaluation protocol verifies that morpheme-based predictions hold under activation steering, not merely that descriptions are plausible

---

## Key Concepts

### Morpheme categories

The MorphoRepr inventory distinguishes five morpheme roles, following the grammar `(prefix)* root (infix)* suffix`:

| Role | Examples | Function |
|------|---------|---------|
| Prefix | `mal-`, `ne-`, `pli-` | polarity and degree modification |
| Root (predefined) | `ag`, `emo`, `sci`, `soc`, `dat`, `tem`, `lok`, `dir` | semantic domain |
| Root (free) | `far`, `pens`, `ver` | pipeline-induced concepts, registered in versioned lexicon |
| Infix | `-ant-`, `-int-`, `-ad-`, `-ig-` | agentivity and aspect |
| Suffix (syntactic) | `-o`, `-a`, `-e`, `-i` | nominal, adjectival, adverbial, infinitival |
| Suffix (tense) | `-as`, `-is`, `-os`, `-us` | present, past, future, conditional |

A word ends in exactly one suffix. Syntactic suffixes and tense suffixes are mutually exclusive within a single word. A free root is induced by the agentic pipeline when no predefined root covers a feature cluster; it must be registered in the versioned lexicon and may not collide with any existing prefix, infix, or suffix token.

### Coefficient normalization

Each coefficient `α ∈ [0.01, 1.00]` is normalized as follows. Let `a(f, x)` be the activation of feature `f` on input `x`, and `p99(f)` the 99th percentile activation of `f` on the reference corpus:

```
α(f, x) = clip( a(f, x) / p99(f), 0.01, 1.00 )
```

In static annotation contexts (not tied to a specific activation instance), coefficients represent encoder confidence rather than measured activation strength. The JSON output schema includes a `coefficient_type` field (`"activation"` or `"confidence"`) to distinguish the two cases.

### Output format

Every agent output is a structured JSON object:

```json
{
  "status": "encoded",
  "expression": "0.86·mal-emo-a + 0.42·ne-soc-a",
  "coefficient_type": "confidence",
  "terms": [
    {
      "coefficient": 0.86,
      "morpheme_chain": "mal-emo-a",
      "root": "emo",
      "prefixes": ["mal"],
      "infix": null,
      "suffix": "-a",
      "confidence": 0.86,
      "rationale": "negative affective context",
      "not_covered": "cultural connotation, named entity specificity"
    }
  ],
  "uncovered_reason": null
}
```

Features that cannot be encoded with confidence >= 0.50 receive `"status": "uncovered"` with an explanation. UNCOVERED outputs are first-class results, not failures; they quantify the boundary between morpho-semantic and contextual-pragmatic content in the SAE feature space.

### MDE abstraction analogy

MorphoRepr occupies level M2 in the MOF abstraction tower applied to LLM representations. This analogy is illustrative and does not constitute a formal claim.

| MDE level | LLM equivalent |
|-----------|---------------|
| M0 | A token in context, with its activation vector |
| M1 | A SAE latent — a learned direction in activation space |
| M2 | A MorphoRepr expression — structured encoding of one or more latents |
| M3 | The MorphoRepr morpheme inventory — self-describing set of primitives |

### Prospective: model editing and memory consolidation

Section 5 of the paper sketches two longer-term research directions, explicitly contingent on the experimental results of the evaluation protocol:

- **MorphoRepr-Edit**: using validated MorphoRepr encodings as a structured address space for model editing (ROME/MEMIT-style), replacing the costly empirical localization step with a structured lookup.
- **MorphoRepr-Memory**: a biologically-inspired two-stage memory architecture combining an external episodic buffer (indexed by MorphoRepr embeddings) with selective parametric consolidation via LoRA, inspired by Complementary Learning Systems theory.

Neither direction is implemented in this repository. Both are contingent on the causal validity results of the full evaluation run.

---

## Repository Structure

```
morphorepr/
├── core/
│   ├── grammar.bnf              # Formal BNF grammar specification
│   └── parser.py                # MorphoRepr expression parser and validator
├── pipeline/
│   ├── agents/
│   │   ├── loader.py            # Phase 1: SAE feature extraction (Neuronpedia / sae_lens)
│   │   ├── ranker.py            # Phase 1: stratified split construction (easy/random/hard)
│   │   ├── cluster.py           # Phase 2: k-means clustering of NL descriptions
│   │   ├── labeler.py           # Phase 2: morpheme proposal per cluster
│   │   ├── consistency.py       # Phase 2: lexicon consistency validation
│   │   ├── encoder.py           # Phase 3: MorphoRepr encoding (2 independent runs)
│   │   ├── fidelity.py          # Phase 3: fidelity AUC-ROC (discrimination task)
│   │   ├── steerer.py           # Phase 4: activation steering (+5 units, dose-response)
│   │   ├── predictor.py         # Phase 4: causal prediction from expression only
│   │   ├── judge.py             # Phase 4: causal validation via output property classifiers
│   │   └── reporter.py          # Phase 5: stratified results synthesis
│   ├── baselines/
│   │   ├── nl_labels.py         # Natural language label baseline
│   │   ├── semantic_regex.py    # Semantic Regexes baseline (Boggust et al., 2025)
│   │   ├── keyword_tags.py      # Controlled keyword tag baseline
│   │   └── shuffled.py          # Within-split shuffled MorphoRepr control (10 repeats)
│   └── classifiers/
│       ├── negation.py          # Robust: negation presence
│       ├── tense.py             # Robust: tense shift
│       ├── code_presence.py     # Robust: code token presence
│       ├── modality.py          # Robust: conditional modality
│       ├── valence.py           # Semi-robust: emotional valence
│       └── calibration/         # Manually annotated calibration sets (50 examples each)
├── db/
│   ├── schema.sql               # Complete SQLite schema
│   └── lexicon/                 # Versioned JSON lexicon schemas
├── prompts/
│   ├── label_agent_v1.txt       # Versioned agent system prompts
│   ├── encoder_agent_v1.txt
│   ├── predictor_agent_v1.txt
│   ├── fidelity_judge_v1.txt
│   └── causal_judge_v1.txt
├── utils/
│   ├── db_utils.py              # Sole DB access point
│   ├── api_utils.py             # Batch API wrapper with retry and budget control
│   ├── prompt_utils.py          # Prompt loading, hashing, and immutability verification
│   ├── config_utils.py          # Config loading and validation
│   └── stats_utils.py           # Bootstrap CI95%, morpheme-level metrics
├── configs/
│   ├── dev_run.yaml             # 5 features — plumbing and parsing validation
│   ├── pilot_run.yaml           # 30-50 features — prompt and threshold calibration
│   └── run_v1.yaml              # Full frozen run — 500 features, publication
├── tests/
│   ├── test_parse.py            # Morpheme Jaccard, coefficient correlation, edit distance
│   ├── test_schema.py           # JSON output schema validation
│   ├── test_db.py               # DB operations and crash recovery
│   ├── test_shuffle_baseline.py # Within-split and length-matching constraints
│   └── test_pipeline_e2e.py     # End-to-end test on 5 features
├── docs/
│   ├── paper.pdf                # Preprint (mirrored from arXiv)
│   └── morpheme_table.md        # Quick-reference morpheme inventory
├── orchestrator.py              # Deterministic scientific run entry point
└── README.md
```

---

## Installation

```bash
python -m venv morphorepr-env
source morphorepr-env/bin/activate          # Linux/macOS
# morphorepr-env\Scripts\activate           # Windows

pip install -r requirements.txt
python -m spacy download en_core_web_sm

mkdir -p db logs checkpoints
sqlite3 db/features.db < db/schema.sql

export ANTHROPIC_API_KEY="sk-ant-..."
```

Verify the installation:

```bash
pytest tests/test_parse.py tests/test_schema.py tests/test_db.py -v
```

Run the classifier calibration before any pilot or full run:

```bash
python pipeline/classifiers/calibration/run_calibration.py
```

Launch sequence:

```bash
# Development run (5 features, non-scientific)
python orchestrator.py --config configs/dev_run.yaml --n-features 5

# Pilot run (30-50 features, calibration)
python orchestrator.py --config configs/pilot_run.yaml --n-features 40

# Full frozen run (500 features, publication)
# Freeze the git commit first:
git add -A && git commit -m "Freeze config for full run v1"
python orchestrator.py --config configs/run_v1.yaml

# Resume after interruption:
python orchestrator.py --config configs/run_v1.yaml --resume --run-id <run_id>
```

The orchestrator is fully deterministic. Agentic tools are used only during development and do not intervene during the scientific run. All prompts are versioned, hashed, and verified for immutability on resume.

---

## Current Status

This repository accompanies a position paper and evaluation protocol (paper v0.26). The agentic evaluation pipeline is being prepared for execution on a stratified corpus of 500 SAE features from Claude 3 Sonnet (via Neuronpedia API), split into easy (n=200), random (n=200), and hard (n=100) subsets. All go/no-go thresholds are evaluated on the random split. Experimental results will be added to the paper and this repository upon completion of the full frozen run.

| Component | Status |
|-----------|--------|
| Formal grammar (`grammar.bnf`) | Available |
| Predefined morpheme lexicon | Available |
| Paper v0.26 (arXiv / HAL) | Available |
| SQLite schema and DB utilities | Available |
| Versioned prompt system | Available |
| Batch API wrapper with retry and budget control | Available |
| Bootstrap CI95% and morpheme-level metrics | Available |
| Classifier calibration sets | Available |
| Phase 1 — Feature extraction and stratification | In progress |
| Phase 2 — Lexicon induction | In progress |
| Phase 3 — Encoding, fidelity AUC-ROC, baselines | Planned |
| Phase 4 — Causal validation (stratified classifiers) | Planned |
| Phase 5 — Results synthesis | Planned |
| Human audit (50 features, 2 annotators) | Planned |
| User study (interpretation accuracy, NASA-TLX) | Planned |
| Memory consolidation (Section 5) | Future work |

---

## Paper

> Launay, M. (2026). *MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol*. Version 0.26. arXiv:2606.XXXXX.

- **arXiv:** https://arxiv.org/abs/2606.XXXXX
- **HAL:** https://hal.science/hal-05649380
- **PDF:** [`docs/en/paper.pdf`](docs/en/paper.pdf)

The paper covers:

- Formal BNF grammar, morpheme inventory, and coefficient normalization convention (Section 3)
- Five-phase agentic evaluation pipeline: stratified feature splits, fidelity as AUC-ROC discrimination task, causal validity via stratified output property classifiers (robust / semi-robust / fragile) with 95% bootstrap confidence intervals, morphological productivity metrics, morpheme-level annotation consistency, within-split shuffled control (Section 4)
- Human audit protocol and planned user study (Section 4)
- Positioning against natural language labels, Semantic Regexes (Boggust et al., 2025), SAELing (Huang et al., 2025), TCAV (Kim et al., 2018), and first-order logic (Section 6)
- Threats to validity: residual annotation circularity, classifier reliability stratification, English-language bias, risk of ad hoc lexicon growth (Section 7)
- Prospective research agenda: MorphoRepr-Edit and MorphoRepr-Memory (Section 5)

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
  url          = {https://arxiv.org/abs/2606.XXXXX},
  note         = {Version 0.26. Position paper and evaluation protocol;
                  no experimental claims. Results forthcoming.}
}
```

---

## Contact and Collaboration

**Michaël Launay**
Logikascium EURL, Fretin, France
Enseignant vacataire — Université de Lille / ENSAM Lille / Polytech Lille
michaellaunay@logikascium.com
https://www.logikascium.com

The author is actively seeking academic collaborators, in particular:

- Researchers in mechanistic interpretability or NLP with access to SAE infrastructure (Neuronpedia, sae_lens, or equivalent)
- Researchers who have worked on structured feature labeling, activation steering, or model editing
- Doctoral supervisors interested in co-supervising a CIFRE thesis on this topic (target industrial partners: Mistral AI, LightOn, Hugging Face, or equivalent)
- Researchers interested in biologically-inspired memory architectures for LLMs

Contributions, issues, and discussions are welcome via GitHub. For collaboration inquiries, reach out by email or open a GitHub Discussion.

---

## License

This repository is released under the [GNU Lesser General Public License v3.0 (LGPL v3)](LICENSE).

The accompanying paper is available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
