# MorphoRepr: A Morphologically-Structured Meta-Language for Human-Readable Projection of LLM Internal Representations

**Michaël Launay**
Logikascium (EURL), Fretin, France
Enseignant vacataire, Université de Lille / ENSAM Lille / Polytech Lille
michaellaunay@logikascium.com

---

*Preprint — submitted to arXiv cs.CL / HAL*
*Version 0.23 — June 2026*

---

## Abstract

No natural language provides sufficient expressive power to faithfully describe the internal representations of large language models (LLMs). While agglutinative and logically regular languages such as Esperanto offer structural properties — compositionality, morphological transparency, and unambiguous suffix semantics — that are theoretically better suited to this task than analytic languages, even such languages can only capture a small fraction of the information encoded in high-dimensional activation spaces. This limitation arises because each activation vector does not represent a word in isolation, but encodes its contextual interactions with the surrounding tokens and the broader discourse context — a type of relational, graded, and continuous information that no natural language, and no existing formal language designed to eliminate ambiguity, can express without becoming either lossy or unreadably verbose.

We propose **MorphoRepr**, a morphologically-structured meta-language inspired by Esperanto's agglutinative grammar, designed as a human-readable projection layer over the sparse, disentangled features produced by Sparse Autoencoders (SAEs) trained on LLM activations. Each MorphoRepr expression maps one or more SAE features to a compositional string of morphemes with formally defined semantics, weighted by their activation coefficients. This approach draws a structural analogy with the abstraction hierarchy of Model-Driven Engineering (MDE): just as the MOF meta-metamodel defines a self-describing tower of abstraction levels (M0–M3) where each level describes the one below it, MorphoRepr operates as an interpretability layer that describes activation-level representations in terms of human-legible compositional primitives — without claiming to be exhaustive at the level of raw geometry.

The goal is not to fully decode an LLM's internal state, but to provide a sufficiently precise and consistent human-readable approximation that enables auditing, steering, and causal analysis of model behavior at the feature level.

In this paper, we propose a formal framework for this approach and describe a five-phase agentic AI pipeline designed to evaluate its feasibility. We outline an evaluation protocol to measure coverage rates, morpheme utilization statistics, and causal alignment scores, and discuss which categories of features are expected to resist morphological encoding and why. Experimental results will be reported in a subsequent version upon completion of the pipeline run.

**Beyond Interpretation: Toward MorphoRepr-Guided Memory Consolidation in LLMs.** Should MorphoRepr prove viable as a structured projection layer over SAE features, a natural extension arises: inverting the pipeline to write new knowledge directly into model weights, rather than merely reading from activation spaces. We sketch a research trajectory in which MorphoRepr-encoded content — expressed in Esperanto and parsed into compositional morpheme chains — serves as a semantically addressed writing interface for targeted model editing. This would build upon existing model editing techniques such as ROME and MEMIT, which demonstrate that factual associations can be localized to specific MLP weight matrices in transformer layers and surgically modified without global degradation. We further propose a hybrid memory architecture inspired by the Complementary Learning Systems (CLS) theory of biological memory consolidation, in which an external vector store serves as a fast episodic buffer and a consolidation mechanism selectively transfers validated knowledge into model weights via low-rank adaptation (LoRA), mirroring hippocampal-to-neocortical replay observed during sleep in biological systems.

**Keywords:** mechanistic interpretability, sparse autoencoders, agglutinative morphology, Esperanto, feature projection, model editing, memory consolidation, agentic AI

---

## 1. Introduction

The internal representations of large language models (LLMs) remain largely opaque to human inspection. A transformer processing the sentence *"She had not finished the task"* encodes this meaning not as a structured linguistic object, but as a high-dimensional activation vector — or more precisely, as a superposition of thousands of weakly active directions in a space of 768 to 4096 dimensions, where each direction corresponds to a latent feature with no guaranteed human-interpretable correlate.

The field of mechanistic interpretability has made significant progress in decomposing these representations. Sparse Autoencoders (SAEs), in particular, have emerged as a scalable tool for disentangling the polysemantic superposition of model neurons into sparser, more monosemantic feature directions (Bricken et al., 2023; Cunningham et al., 2023; Templeton et al., 2024). Yet the problem of *labeling* these features — of assigning them human-readable descriptions that are precise, consistent, and compositionally structured — remains open. Current approaches rely on natural language labels generated by LLMs, which are accurate but vague, inconsistent across runs, and poorly suited to formal reasoning about feature relationships (Boggust et al., 2025).

This paper proposes a different approach, motivated by a linguistic observation: the structural properties that make Esperanto an unusually learnable natural language — its agglutinative morphology, its bijective suffix-to-meaning mapping, its compositional word formation — are precisely the properties one would want in a notation system for SAE features. A feature encoding "negation of a past action by a human agent" could be written `mal-far-int-a` rather than a free-form English phrase, with each morpheme carrying a formally defined and bounded meaning.

We do not propose to use Esperanto itself as a representation language — its lexicon is too small, its coverage of abstract computational concepts too limited, and its natural-language ambiguities too numerous. We propose instead **MorphoRepr**, a formal meta-language that borrows Esperanto's *structural logic* — its agglutinative composition rules, its finite morpheme inventory, its transparent derivational system — and extends it with a controlled vocabulary of primitives empirically derived from the SAE feature space of a production-scale LLM.

The structural analogy we draw with Model-Driven Engineering (MDE) is not merely decorative. In MDE, the Meta-Object Facility (MOF) defines a tower of abstraction levels (M0: instances, M1: models, M2: metamodels, M3: the MOF itself) where each level describes the one below it, and M3 is self-describing. MorphoRepr occupies an analogous position: it is a language that describes the language of LLM features, itself defined in terms of a finite set of formally specified primitives. This self-referential structure is precisely what gives it the potential to scale — the same morpheme inventory that describes a feature today can describe a new feature tomorrow, without requiring manual extension of a natural-language vocabulary.

### 1.1 Contributions

This paper makes the following contributions:

1. **Conceptual**: We formalize the notion of a morphologically-structured meta-language for SAE feature annotation, and establish its theoretical grounding in the Linear Representation Hypothesis and the Superposition Hypothesis.

2. **Methodological**: We describe a five-phase agentic AI pipeline for empirically inducing a MorphoRepr lexicon from SAE features and specify an evaluation protocol for coverage and causal validity.

3. **Prospective**: We sketch a research trajectory extending MorphoRepr from a read-only interpretability tool to a write-enabled model editing interface and, ultimately, a biologically-inspired memory consolidation architecture.

---

## 2. Background and Related Work

### 2.1 Sparse Autoencoders and Mechanistic Interpretability

The Linear Representation Hypothesis (LRH) posits that neural networks encode interpretable concepts as linear directions in their activation spaces (Mikolov et al., 2013; Park et al., 2023). The Superposition Hypothesis (Elhage et al., 2022) further proposes that models compress a large number of such features into a smaller number of neurons by exploiting approximate orthogonality, creating polysemantic neurons that respond to multiple unrelated concepts.

Sparse Autoencoders address superposition by projecting activations into a higher-dimensional space while enforcing sparsity, causing each input to activate only a small number of learned features. Bricken et al. (2023) demonstrate that SAE features are more monosemantic and more interpretable than individual neurons, as measured by automated interpretability scoring. Templeton et al. (2024) scale this approach to production models, finding features corresponding to specific named entities, syntactic constructions, and abstract semantic concepts.

The current bottleneck in SAE-based interpretability is *labeling*: assigning human-readable descriptions to the tens of thousands of features discovered by large SAEs. Existing approaches use LLMs to generate natural language descriptions by inspecting high-activating examples (Bills et al., 2023; Paulo et al., 2024). These descriptions are accurate but exhibit the well-known limitations of natural language as a formal notation: vagueness, inconsistency across runs, and the impossibility of compositional reasoning.

### 2.2 Structured Languages for Feature Annotation

Boggust et al. (2025) introduce *Semantic Regexes*, a structured language for automatically describing LLM features by combining primitives for exact token patterns, syntactic word forms, and semantic categories with modifiers for contextualization, composition, and quantification. Semantic Regexes match the accuracy of natural language descriptions while yielding more concise and consistent outputs. This work is the closest antecedent to MorphoRepr in the current literature.

The key difference is structural: Semantic Regexes are a pattern-matching language in the tradition of regular expressions, where primitives are combined by logical operators (AND, OR, NOT, context). MorphoRepr is an *agglutinative* language, where primitives are combined by concatenation following morphological rules, and the resulting expression is a single readable token rather than a formula. This distinction matters for human usability: `0.87·mal-far-int-e` is readable and memorable in a way that `¬(ag:past & subject:human)` is not.

### 2.3 Model Editing

ROME (Meng et al., 2022) and MEMIT (Meng et al., 2023) demonstrate that factual knowledge in transformer LLMs can be localized to specific MLP weight matrices and surgically modified. The key insight is that MLP layers in transformers function as associative memories, with key-value pairs corresponding to factual associations. ROME computes a rank-one update to a target weight matrix that inserts a new key-value pair while minimally disrupting existing associations.

The persistent limitation of current model editing approaches is *localization*: determining which weight matrices to modify for a given piece of knowledge requires an empirical causal tracing procedure that is expensive and imperfect. MorphoRepr addresses this by providing a principled semantic map from morphological expressions to SAE feature indices to layer-specific weight directions, potentially transforming localization from an empirical search into a structured lookup.

### 2.4 Complementary Learning Systems

The Complementary Learning Systems (CLS) theory (McClelland et al., 1995; Kumaran et al., 2016) proposes that biological memory is organized into two complementary systems: the hippocampus, which encodes episodic memories rapidly and specifically, and the neocortex, which encodes semantic knowledge slowly and in a distributed fashion. Memory consolidation occurs when the hippocampus replays recent episodes to the neocortex during sleep, gradually integrating new information into long-term semantic knowledge.

The analogy with LLM memory architectures is direct: RAG systems and external vector stores function as hippocampal buffers (fast, specific, episodic), while model weights function as neocortical long-term memory (slow, distributed, semantic). MorphoRepr-guided model editing would provide the consolidation mechanism — the replay — that bridges these two systems.

---

## 3. The MorphoRepr System

### 3.1 Design Principles

MorphoRepr is designed according to four principles that distinguish it from both natural language annotation and existing formal notation systems:

**Morphological compositionality.** Every MorphoRepr expression is a finite concatenation of morphemes drawn from a fixed inventory. The meaning of an expression is fully determined by the meanings of its constituent morphemes and their order of composition. No expression requires external reference to be interpreted.

**Weighted activation encoding.** Each morpheme in an expression is preceded by a real-valued coefficient in [0.0, 1.0] representing the normalized activation strength of the corresponding SAE feature. A complete expression has the form:

```
α₁·m₁[-m₂[-m₃]] [+ α₂·m₄[-m₅] [+ ...]]
```

where `mᵢ` are morphemes, `-` denotes agglutinative concatenation, `+` denotes additive feature combination, and `αᵢ` are activation coefficients. For example:

```
0.87·mal-far-int-e  +  0.41·pens-ad-is
```

is read as: *"not having acted (strength 0.87) plus having continued to think (strength 0.41)"*.

**Formal morpheme semantics.** Each morpheme in the inventory has a formally specified definition consisting of: (a) a denotation in terms of a semantic primitive, (b) a scope statement specifying what the morpheme covers and what it excludes, and (c) a set of attested SAE features that the morpheme reliably encodes.

**Bounded expressiveness.** MorphoRepr does not attempt to encode all information in an activation vector. It is explicitly designed as a *lossy projection* that captures the morpho-syntactic and broadly semantic content of SAE features while acknowledging that pragmatic, cultural, and deeply contextual content lies outside its scope. The residual — the information not captured by any MorphoRepr expression — is a first-class output of the system, not a failure mode.

### 3.2 The Morpheme Inventory

The MorphoRepr inventory is organized into five categories, each inspired by Esperanto's grammatical system but extended to cover the semantic terrain of LLM activation features. Following the grammar formalized in Appendix A, **domain morphemes serve as roots** (the semantic core of a word), while polarity morphemes serve as prefixes that modify those roots. Free roots — induced by the agentic pipeline for concepts not covered by the predefined vocabulary — are also permitted and denoted by lowercase letter sequences of 2–5 characters (e.g., `far`, `pens`, `ver`); see footnote 1.

**Temporal morphemes** (suffixes encoding verb tense and aspect):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|-------------------|
| `-as` | present, ongoing | present tense `-as` |
| `-is` | past, completed | past tense `-is` |
| `-os` | future, anticipated | future tense `-os` |
| `-us` | conditional, hypothetical | conditional `-us` |

**Participial infixes** (inserted between root and suffix):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|-------------------|
| `-ad-` | iterative, habitual | iterative suffix `-ad-` |
| `-int-` | active past participle | `-int-` |
| `-at-` | passive present participle | `-at-` |
| `-ist-` | habitual agent, professional | `-ist-` |
| `-ant-` | current agent, actor | active present participle |
| `-ig-` | causative, to cause | `-ig-` |
| `-iĝ-` | inchoative, to become | `-iĝ-` |

**Polarity and degree prefixes** (modify the root they precede):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|-------------------|
| `mal-` | negation, opposite | `mal-` |
| `ne-` | absence, lack | `ne` (adverb) |
| `pli-` | comparative increase | `pli` |
| `plej-` | superlative | `plej` |
| `duon-` | partial, approximate | `duon-` |

**Domain roots** (predefined semantic field roots; these are the `root` production in the grammar):

| Root | Meaning | Notes |
|------|---------|-------|
| `sci` | knowledge, fact, belief | covers epistemic features |
| `emo` | affect, emotion, valence | covers sentiment features |
| `ag` | physical action, motion | covers action features |
| `dir` | direction, spatial relation | covers spatial features |
| `soc` | social relation, role | covers interpersonal features |
| `dat` | numeric, code, data | covers technical/computational features |
| `tem` | time, sequence, order | covers temporal ordering features |
| `lok` | location, place | covers spatial grounding features |

**Syntactic role suffixes** (the final element of every word):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|-------------------|
| `-o` | noun (entity, concept) | noun suffix `-o` |
| `-a` | adjective (property, attribute) | adjective suffix `-a` |
| `-e` | adverb (manner, degree) | adverb suffix `-e` |
| `-i` | infinitive (abstract action) | infinitive suffix `-i` |

---

*Footnote 1: Free roots such as `far` (to do/make) and `pens` (to think) are not part of the predefined vocabulary but are valid MorphoRepr roots because they satisfy the grammar's `root ::= [a-z]{2,5}` production. They are induced by the agentic pipeline (Phase 2) when no predefined domain root covers a feature cluster. Free roots inherit all composition rules and must be registered in the versioned lexicon.*

---

### 3.3 Example Encodings

The following examples illustrate MorphoRepr encodings for SAE features drawn from the public Neuronpedia interface for Claude 3 Sonnet. Each encoding is parsed against the grammar of Appendix A to verify structural validity.

**Feature #892** (natural language description: *"tokens in past-tense contexts, especially completed actions"*):
```
0.91·ag-is
```
Parse: `ag` (domain root) + `-is` (suffix). Reading: *"completed physical action (past)"*, strength 0.91.

**Feature #1204** (description: *"negation markers and negative polarity items"*):
```
0.88·mal-o  +  0.34·ne-a
```
Parse, term 1: `mal-` (polarity prefix) + implied root `∅` → here `mal` functions as root¹ + `-o` (suffix). Parse, term 2: `ne-` + `-a`. Reading: *"negation as entity (0.88) plus absence as property (0.34)"*.

> ¹ *Note on `mal-o` and `ne-a`*: In these two cases, the polarity morphemes `mal` and `ne` function directly as roots (a construction permitted in Esperanto: `malo` = "the opposite", `neo` = "the no"). This is the only case where a polarity morpheme doubles as a root; the grammar permits it under the `root ::= [a-z]{2,5}` production when no domain root is applicable.

**Feature #3871** (description: *"human agents performing intentional actions, especially in narrative contexts"*):
```
0.79·soc-ant-o  +  0.45·ag-int-a
```
Parse, term 1: `soc` (domain root) + `-ant-` (participial infix) + `-o` (suffix). Parse, term 2: `ag` (domain root) + `-int-` (participial infix) + `-a` (suffix). Reading: *"social actor currently acting (0.79) plus entity that has physically acted (0.45)"*.

**Feature #4102** (description: *"Python code involving for-loops and iteration patterns"*):
```
0.94·dat-ad-o
```
Parse: `dat` (domain root) + `-ad-` (participial infix, iterative) + `-o` (suffix). Reading: *"iterative data/code process"*, strength 0.94.

**Feature #7823** (description: *"tokens occurring in emotionally negative contexts, especially grief and loss"*):
```
0.86·mal-emo-a  +  0.51·pens-is
```
Parse, term 1: `mal-` (polarity prefix) + `emo` (domain root) + `-a` (suffix). Parse, term 2: `pens` (free root, induced) + `-is` (suffix). Reading: *"negative affective property (0.86) plus past cognitive state (0.51)"*.

### 3.4 Relationship to the MDE Abstraction Hierarchy

Model-Driven Engineering organizes modeling artifacts into four abstraction levels:

- **M0**: Real-world instances (a specific running process)
- **M1**: Models describing instances (a UML object diagram)
- **M2**: Metamodels describing model structure (the UML metamodel)
- **M3**: The MOF, the self-describing meta-metamodel

MorphoRepr occupies a position analogous to M2 in this hierarchy, applied to the domain of LLM representations:

- **M0**: A specific token in a specific context, with its activation vector
- **M1**: A SAE feature — a direction in activation space with a natural language description
- **M2**: A MorphoRepr expression — a formal compositional encoding of one or more SAE features
- **M3**: The MorphoRepr morpheme inventory — the self-describing set of primitives that defines all valid expressions

The crucial property of M3 in MDE is self-reference: the MOF can describe itself using its own constructs. MorphoRepr approaches this property: its morphemes can, in principle, describe other morphemes. `sci-o` (knowledge-entity) can describe the morpheme `sci` itself; `ag-i` (to act as an agent) can describe the role of agentive morphemes. This self-referential capacity is not merely a formal curiosity — it is what allows MorphoRepr to scale to new feature types without requiring external extension mechanisms.

---

## 4. Agentic Feasibility Study

### 4.1 Motivation for an Agentic Approach

The induction of a MorphoRepr lexicon from SAE features is a task that is simultaneously too repetitive for manual execution and too semantically nuanced for a deterministic algorithm. Encoding 500 features requires consistent application of formal rules (amenable to automation) combined with semantic judgment about which morphemes best capture each feature's meaning (requiring LLM-level reasoning). This combination is precisely the operational niche of agentic AI systems.

Three structural properties make this task particularly well-suited to an agentic pipeline:

**Measurable convergence criteria.** The coverage rate — the fraction of features receiving a MorphoRepr encoding with confidence ≥ 0.6 — is a real number that the pipeline can compute autonomously and use to decide whether to iterate, extend the lexicon, or terminate.

**Iterative refinement structure.** The lexicon induction process is naturally iterative: initial morphemes will fail to cover some features, which reveals gaps that motivate new morphemes, which in turn enable new encodings. This feedback loop is easily automated.

**Separation of concerns between agents.** Different phases of the pipeline require qualitatively different capabilities: retrieval and ranking (Phase 1), clustering and abstraction (Phase 2), formal encoding (Phase 3), causal reasoning (Phase 4), and synthesis (Phase 5). Assigning these to specialized agents allows each to be optimized independently.

### 4.2 Pipeline Architecture

The pipeline consists of five phases, each implemented as a set of specialized LLM agents orchestrated by a stateful controller. Full prompt templates for each agent are provided in Appendix B.

#### Phase 1: SAE Feature Extraction

**Objective**: Construct a corpus of 500 annotated SAE features with activation examples.

**Data sources**:
- Public SAEs for Claude 3 Sonnet, accessible via the Neuronpedia API (neuronpedia.org), with 16k to 1M features depending on the target layer
- SAE-Bench (EleutherAI), a standardized benchmark with labeled features
- `sae_lens`, an open-source Python library providing unified access to SAEs across multiple models

The *Loader agent* queries the Neuronpedia API for each target layer, retrieving for each feature its index, its 20 highest-activating examples (with activation scores), its existing interpretability score from Anthropic's autointerpretability pipeline, and its activation frequency on a reference corpus. The *Ranker agent* filters to the top-500 features by a composite score weighting frequency (50%) and existing interpretability score (50%). Features with interpretability score below 0.7 are excluded to ensure the corpus contains features with clear semantic identity. Results are stored in a *Feature store* (SQLite database) supporting the encoding and evaluation phases.

#### Phase 2: MorphoRepr Lexicon Induction

**Objective**: Identify, through empirical analysis of the feature corpus, a minimal set of morphemes that covers the semantic space of the top-500 features.

The *Cluster agent* embeds the natural language descriptions of all 500 features using nomic-embed-text and applies k-means clustering with k ≈ 20, where each cluster represents a candidate morpheme family. The *Label agent* receives each cluster and proposes a morpheme — either from the predefined domain root vocabulary or as a new free root — along with a formal definition, scope statement, and coverage examples (see Appendix B.1 for the full prompt). The *Consistency agent* validates the proposed lexicon against three criteria: non-redundancy (cosine similarity between morpheme representations < 0.7), coverage (each feature can receive at least one morpheme), and composability (morphemes concatenate without ambiguity per the grammar of Appendix A). Failures trigger a feedback loop to the Label agent, running for a maximum of 5 iterations.

#### Phase 3: Feature Encoding and Coverage Measurement

**Objective**: Encode each of the 500 features as a MorphoRepr expression and compute coverage statistics.

The *Encoder agent* processes each feature individually, producing a weighted MorphoRepr expression or an `UNCOVERED` response with justification (see Appendix B.2 for the full prompt). The *Scorer agent* computes three aggregate metrics: (a) **raw coverage rate** — percentage of features with encoder confidence ≥ 0.6; (b) **fidelity score** — a second LLM judge evaluates whether the MorphoRepr expression correctly predicts high-activating examples, following the simulation scoring of Paulo et al. (2024); (c) **UNCOVERED rate** — percentage of features the encoder cannot express with confidence ≥ 0.5, analyzed by feature type. The *Fallback agent* clusters UNCOVERED features, proposes new morpheme candidates, and resubmits them to the Phase 2 validation loop.

#### Phase 4: Causal Validation via Activation Steering

**Objective**: Verify that MorphoRepr morphemes are causally valid predictors of model behavior under feature intervention, not merely descriptive labels.

For each encoded feature, the *Steer agent* amplifies the target SAE feature by +5 activation units (standard steering magnitude from Templeton et al., 2024) on 20 neutral probe sentences, records the output shift, and generates a causal prediction based solely on the MorphoRepr expression (see Appendix B.3). A *judge LLM* evaluates whether the observed shift matches the prediction. The *Causal agent* computes a causal alignment score per morpheme and an aggregate causal validity score across all morphemes.

**Go/no-go threshold**: An aggregate causal validity score exceeding 0.65 (65%) constitutes validation of MorphoRepr as a causally predictive system.

#### Phase 5: Synthesis and Reporting

The *Report agent* generates structured coverage statistics, fidelity distributions, and causal validity scores per morpheme. The *Gap analyst* classifies UNCOVERED features into categories (named-entity features, pragmatic features, technical domain-specific features) and quantifies the fraction of the feature space outside MorphoRepr's expressible scope by design. The *Paper draft agent* produces a structured results summary for inclusion in a conference submission.

### 4.3 Technical Stack

```
Orchestration:    Claude Code (agentic loop) or LangGraph
LLM agents:       Claude Sonnet (semantic judgment tasks)
                  Claude Haiku (repetitive scoring and formatting tasks)
SAE access:       sae_lens + Neuronpedia API (neuronpedia.org)
Embeddings:       nomic-embed-text (feature description clustering)
Clustering:       scikit-learn k-means + UMAP (visualization)
Storage:          SQLite (feature corpus) + JSON (versioned lexicon)
Evaluation:       SAE-Bench (EleutherAI) as external benchmark
Checkpoints:      Full pipeline state snapshot after each phase
```

### 4.4 Success Criteria

| Metric | Minimum threshold | Publication threshold |
|--------|------------------|-----------------------|
| Raw coverage (confidence ≥ 0.6) | 55% | 70% |
| Causal validity | 50% | 65% |
| Final lexicon size | < 250 morphemes | < 150 morphemes |
| UNCOVERED features analyzed | — | ≥ 80% categorized |

A raw coverage below 40% does not invalidate the contribution. It would instead constitute a negative result with analytic value: it would precisely quantify which properties of SAE features resist morphological encoding, and why — a contribution to the theory of feature structure in LLMs.

---

## 5. Toward MorphoRepr-Guided Memory Consolidation

### 5.1 Inverting the Pipeline: From Reading to Writing

The feasibility study described in Section 4 treats MorphoRepr as a *read-only* system: it projects activation states into human-readable expressions without modifying the model. Should this projection prove valid, a natural next step is to invert the pipeline — to use MorphoRepr expressions as a structured interface for *writing* new knowledge into model weights.

This inversion would proceed as follows:

1. A piece of knowledge is expressed in Esperanto, exploiting Esperanto's agglutinative structure to produce a morphologically parsed input.
2. The Esperanto text is automatically converted to a MorphoRepr expression via the morphological parser developed in the feasibility study.
3. The MorphoRepr expression is mapped to a set of target SAE features via the lexicon.
4. The target features are localized to specific weight matrices using the causal maps established in Phase 4.
5. A targeted weight update (ROME/MEMIT-style) is applied to encode the new knowledge.

The key contribution of MorphoRepr to this pipeline would be in step 4: transforming the expensive, empirical, case-by-case localization procedure of ROME into a structured lookup in a semantically typed address space.

### 5.2 The Hybrid Memory Architecture

We propose a two-stage memory architecture inspired by the Complementary Learning Systems theory:

**Stage 1: Episodic buffer (hippocampal analogue)**. An external vector store — in the tradition of Karpathy's graph-based knowledge systems using tools such as Obsidian — holds Esperanto-encoded content indexed by MorphoRepr embeddings. This store functions as a fast, high-capacity episodic memory: new information can be added instantly, retrieved by semantic similarity, and updated without risk of interference with other stored memories. The use of MorphoRepr embeddings rather than raw LLM embeddings as the indexing mechanism provides human-auditable retrieval: a query in MorphoRepr syntax can be interpreted by a human operator.

**Stage 2: Parametric consolidation (neocortical analogue)**. A consolidation mechanism selectively transfers frequently accessed or causally important knowledge from the episodic buffer into model weights via low-rank adaptation (LoRA). The consolidation criterion is dual: frequency (knowledge accessed more than a threshold number of times) and causal validation (knowledge whose MorphoRepr encoding has been confirmed as causally predictive in Phase 4). This mirrors the selectivity of hippocampal-to-neocortical consolidation during sleep, which prioritizes emotionally salient and repeatedly activated memories.

The two-stage design addresses the central tension in current model editing: the speed of episodic acquisition (accommodated by Stage 1) and the stability requirements of parametric memory (managed by Stage 2's selective consolidation).

### 5.3 Open Problems and Limitations

**Compositional writability.** Reading from activation spaces reduces to linear projection, which is well-understood. Writing in a compositional and interference-free manner into a nonlinear dynamical system is not guaranteed by any current theory. The weight matrices of a transformer are not an addressable memory; a local modification has global effects that are difficult to predict. MorphoRepr does not solve this problem; it reframes it as a structured search problem over a semantically typed address space, which is a necessary precondition for any principled solution.

**Catastrophic forgetting.** Current sequential model editing approaches degrade model performance after a few thousand edits. This is not a limitation specific to MorphoRepr; it is a fundamental property of the current transformer architecture. MorphoRepr's contribution is to make the editing process more principled, not to resolve the architectural limitation.

**Episodic specificity.** MorphoRepr operates at the level of semantic and morpho-syntactic features. Episodic memories — "I spoke with person X on date Y about topic Z" — require a level of contextual specificity that Esperanto morphology cannot capture directly. Stage 1 (the episodic buffer) can store such memories as structured records; Stage 2 (parametric consolidation) can only encode their semantic content, not their episodic specificity.

This memory consolidation direction is proposed here as a future research program contingent on the feasibility results of Section 4. It is included in this paper to situate MorphoRepr within the broader challenge of building LLMs with persistent, human-auditable, and morphologically structured long-term memory.

---

## 6. Positioning Within the Current Literature

MorphoRepr occupies a distinctive position in the interpretability landscape, differentiated from the closest related works as follows:

| Approach | Compositionality | Human readability | Coverage | Causal validity |
|----------|-----------------|-------------------|----------|----------------|
| Natural language labels (Bills et al., 2023) | None | High | High | Not assessed |
| Semantic Regexes (Boggust et al., 2025) | Logical | Moderate | High | Not assessed |
| SAELing (Huang et al., 2025) | None | High | Moderate | Partial |
| TCAV (Kim et al., 2018) | None | Moderate | Low | Partial |
| **MorphoRepr (proposed)** | **Agglutinative** | **High** | **To be measured** | **Central criterion** |
| First-order logic | Full | Low | High | High |

The distinctive contribution of MorphoRepr relative to Semantic Regexes — the most direct competitor — is the agglutinative composition mechanism. Where Semantic Regexes express `feature #1204` as `¬token("not") | field("negation")`, MorphoRepr expresses it as `0.88·mal-o + 0.34·ne-a`. The second form is compact, phonetically pronounceable, and compositionally transparent in the same way that the Esperanto word `malfeliĉa` (*unhappy*) is transparently composed of `mal-` (opposite) + `feliĉ-` (happy) + `-a` (adjective suffix). This transparency is not merely aesthetic: it enables human operators to *construct* new feature descriptions from scratch by composing morphemes, rather than merely *reading* descriptions generated by an LLM.

---

## 7. Discussion

### 7.1 What MorphoRepr Can and Cannot Express

MorphoRepr is explicitly designed as a lossy projection. It captures:
- Morpho-syntactic properties (tense, aspect, negation, agentivity, syntactic role)
- Broad semantic domain (knowledge, affect, action, space, social relation, data)
- Activation strength (via coefficients)

It does not capture:
- Highly specific named-entity features ("features about the Eiffel Tower")
- Deeply pragmatic features (irony, register, cultural connotation)
- Features whose meaning is defined by a specific textual context rather than a semantic property
- Inter-feature relationships (how two features interact causally)

The estimated coverage of 55–70% (pending empirical validation) means that roughly 30–45% of the top-500 SAE features lie outside MorphoRepr's expressible scope by design. This is not a failure — it is a quantification of the boundary between the morpho-semantic and the contextual-pragmatic in LLM feature space, which is itself a scientifically interesting result.

### 7.2 Why Esperanto and Not Another Agglutinative Language

Turkish, Finnish, Hungarian, Swahili, and Japanese are all agglutinative or polysynthetic languages with well-studied morphological systems. Esperanto is chosen for four reasons specific to this application:

1. **Designed regularity**: Esperanto's morphology is fully regular by construction, with no exceptions. Natural agglutinative languages have irregular forms, suppletive morphemes, and phonological alternations that would complicate formal specification.

2. **Finite affix inventory**: Esperanto has approximately 40 affixes with formally defined meanings. This finite inventory is precisely the kind of controlled vocabulary needed for MorphoRepr's morpheme set.

3. **Latin-script notation**: Esperanto uses a Latin-derived alphabet, making MorphoRepr expressions directly embeddable in standard text formats, code, and data schemas without encoding issues.

4. **Human learnability**: The Esperanto morphological system can be learned in hours. This means MorphoRepr expressions will be interpretable, without training, by any researcher familiar with a small reference table of morphemes.

---

## 8. Conclusion

We have proposed MorphoRepr, a morphologically-structured meta-language for annotating SAE features in LLMs, and described a five-phase agentic pipeline for conducting a feasibility study of its coverage and causal validity. This paper presents the formal framework and evaluation protocol; experimental results will be reported in a subsequent version upon completion of the pipeline run.

The theoretical case for MorphoRepr rests on three convergent observations: the documented compositionality of LLM activation spaces (the Linear Representation Hypothesis), the structural analogy between agglutinative morphology and the additive composition of SAE features, and the demonstrated insufficiency of natural language labels for formal interpretability tasks. Whether this theoretical case translates into a practically useful system is an empirical question that the pipeline described in Section 4 is designed to answer.

Beyond interpretability, the prospective memory consolidation architecture sketched in Section 5 suggests that MorphoRepr, if validated, could serve as a principled interface between the fast episodic memory of external vector stores and the slow parametric memory of transformer weights — a computational implementation of the Complementary Learning Systems theory at the scale of production LLMs.

The code for the agentic pipeline, the MorphoRepr lexicon specification, and all experimental results will be made available at: `https://github.com/michaellaunay/morphorepr`.

---

## References

Bills, S., Cammarata, N., Mossing, D., Tillman, H., Gao, L., Goh, G., Sutskever, I., Leike, J., Wu, J., & Saunders, W. (2023). *Language models can explain neurons in language models*. OpenAI Blog.

Boggust, A., Ren, D., Assogba, Y., Moritz, D., Satyanarayan, A., & Hohman, F. (2025). *Semantic Regexes: Auto-Interpreting LLM Features with a Structured Language*. arXiv:2510.06378.

Bricken, T., Templeton, A., Batson, J., Chen, B., Jermyn, A., Conerly, T., Turner, N., Anil, C., Denison, C., Askell, A., Lasenby, R., Wu, Y., Kravec, S., Schiefer, N., Maxwell, T., Joseph, N., Hatfield-Dodds, Z., Tamkin, A., Nguyen, K., … Henighan, T. (2023). *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning*. Transformer Circuits Thread.

Cunningham, H., Ewart, A., Sherburn, L., Tuck, R., & Sharkey, L. (2023). *Sparse Autoencoders Find Highly Interpretable Features in Language Models*. arXiv:2309.08600.

Elhage, N., Hume, T., Olsson, C., Schiefer, N., Henighan, T., Kravec, S., Hatfield-Dodds, Z., Lasenby, R., Drain, D., Chen, C., Grosse, R., McCandlish, S., Kaplan, J., Amodei, D., Wattenberg, M., & Olah, C. (2022). *Toy Models of Superposition*. Transformer Circuits Thread.

Huang, J., et al. (2025). *Sparse Auto-Encoder Interprets Linguistic Features in Large Language Models*. arXiv:2502.20344.

Kim, B., Wattenberg, M., Gilmer, J., Cai, C., Wexler, J., Viegas, F., & Sayres, R. (2018). *Interpretability Beyond Classification Accuracy: Quantifying Interpretability of Machine Learning Models via Concept Activation Vectors (TCAV)*. ICML 2018.

Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). *What learning systems do intelligent agents need? Complementary learning systems theory updated*. Trends in Cognitive Sciences, 20(7), 512–534.

McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex: Insights from the successes and failures of connectionist models of learning and memory*. Psychological Review, 102(3), 419–457.

Meng, K., Bau, D., Andonian, A., & Belinkov, Y. (2022). *Locating and Editing Factual Associations in GPT*. NeurIPS 2022.

Meng, K., Sharma, A. S., Andonian, A., Belinkov, Y., & Bau, D. (2023). *Mass-Editing Memory in a Transformer*. ICLR 2023.

Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). *Efficient Estimation of Word Representations in Vector Space*. arXiv:1301.3781.

Object Management Group. (2016). *Meta Object Facility (MOF) Core Specification, Version 2.5.1*. OMG Document formal/2016-11-01.

Park, K., Hernandez-Garcia, A., Sharma, S., Gontier, N., & Schölkopf, B. (2023). *The Linear Representation Hypothesis and the Geometry of Large Language Models*. arXiv:2311.03658.

Paulo, G., Mallen, A., Juang, C., & Belrose, N. (2024). *Automatically Interpreting Millions of Features in Large Language Models*. arXiv:2410.13928.

Templeton, A., Conerly, T., Marcus, J., Lindsey, J., Bricken, T., Chen, B., Pearce, A., Citro, C., Ameisen, E., Jones, A., Cunningham, H., Turner, N., McDougall, C., MacDiarmid, M., Freeman, C. D., Sumers, T. R., Rees, E., Batson, J., Jermyn, A., … Henighan, T. (2024). *Scaling and evaluating sparse autoencoders*. Anthropic Research.

Zamenhof, L. L. (1887). *Unua Libro* [International Language]. Warsaw.

---

## Appendix A: MorphoRepr Grammar Specification

### A.1 Formal Grammar (BNF)

```
expression    ::= term ('+' term)*
term          ::= coefficient '·' word
coefficient   ::= [0-9]'.'[0-9][0-9]
word          ::= (prefix)* root (infix)* suffix
prefix        ::= 'mal-' | 'ne-' | 'pli-' | 'plej-' | 'duon-'
root          ::= root-predefined | root-free
root-predefined ::= 'sci' | 'emo' | 'ag' | 'dir' | 'soc'
                  | 'dat' | 'tem' | 'lok' | 'mal' | 'ne'
root-free     ::= [a-z]{2,5}
                  (* pipeline-induced roots, registered in lexicon *)
infix         ::= '-ad-' | '-int-' | '-it-' | '-ist-' | '-ant-'
                | '-at-' | '-ig-' | '-iĝ-'
suffix        ::= '-o' | '-a' | '-e' | '-i' | '-as' | '-is'
                | '-os' | '-us' | '-u'
```

### A.2 Composition Rules

1. A word must contain exactly one root.
2. Prefixes precede the root; infixes follow the root; the suffix is final.
3. Multiple prefixes are allowed and compose left-to-right: `mal-ne-X` = "not-absent-X" ≠ `ne-mal-X` = "non-opposite-X".
4. Coefficients must be in [0.01, 1.00]; a coefficient of 0.00 indicates an absent feature and must not appear in expressions.
5. Terms in an expression are ordered by descending coefficient.
6. Free roots (`root-free`) must be registered in the versioned lexicon before use; unregistered free roots are syntactically valid but semantically undefined.

---

## Appendix B: Agentic Pipeline Prompt Templates

### B.1 Label Agent System Prompt

```
You are a formal linguist designing MorphoRepr, an agglutinative
meta-language for annotating internal features of large language models.

MorphoRepr morphemes must satisfy four constraints:
1. FORMAL: The meaning is precisely bounded — you must specify
   both what the morpheme covers and what it excludes.
2. COMPOSITIONAL: The morpheme must compose unambiguously with
   other morphemes following Esperanto agglutinative rules.
3. MINIMAL: The morpheme should be as short as possible (2-5 chars)
   while remaining phonetically distinct from other morphemes.
4. EMPIRICAL: The morpheme must be grounded in observed SAE feature
   behavior, not theoretical linguistic categories.

You will receive a cluster of semantically related SAE features.
If the cluster is covered by a predefined domain root (sci, emo, ag,
dir, soc, dat, tem, lok), propose that root. Otherwise, propose a
new free root of 2-5 lowercase characters that does not conflict
with the existing lexicon. In both cases, provide a formal definition,
scope statement, and coverage examples.
```

### B.2 Encoder Agent System Prompt

```
You are encoding SAE features into MorphoRepr expressions.

MorphoRepr is an agglutinative formal language where:
- Each term has the form: coefficient · morpheme-chain
- Coefficients are in [0.01, 1.00] (two decimal places)
- Morpheme chains follow the grammar: (prefix)* root (infix)* suffix
- Domain roots (sci, emo, ag, dir, soc, dat, tem, lok) and
  registered free roots are the only valid roots
- An expression contains 1-4 terms, ordered by descending coefficient
- If you cannot encode a feature with confidence ≥ 0.50 using the
  available lexicon, respond UNCOVERED and explain what semantic
  content the lexicon cannot express.

Be precise about confidence. Overconfident encodings that fail
causal validation are more harmful than honest UNCOVERED responses.
```

### B.3 Causal Prediction Agent System Prompt

```
You are predicting the effect of amplifying a SAE feature on LLM output.

Given a MorphoRepr expression for a feature, predict:
1. In which semantic direction will outputs shift when this feature
   is amplified by +5 activation units?
2. Which of the following output properties would you expect to increase?
   [list of measurable output properties]
3. What is your confidence in this prediction? [0.0 - 1.0]

Base your prediction ONLY on the MorphoRepr expression provided.
Do not use the natural language description of the feature.
This constraint is intentional: we are testing whether MorphoRepr
expressions alone are sufficient for causal prediction.
```

---

*Version 0.23 — June 2026*
*Michaël Launay — michaellaunay@logikascium.com*
*Logikascium EURL — https://www.logikascium.com*
*GitHub: https://github.com/michaellaunay/morphorepr*
