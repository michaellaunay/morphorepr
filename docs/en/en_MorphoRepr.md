# MorphoRepr: a morphologically structured controlled language for describing SAE features in LLMs
## A position paper and evaluation protocol

**Title (English):** MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol

**Michaël Launay**  
Logikascium (EURL), Fretin, France  
Adjunct lecturer, Université de Lille / ENSAM Lille / Polytech Lille  
michaellaunay@logikascium.com

---

*Preprint — position paper and evaluation protocol — submitted to arXiv cs.CL / HAL*  
*Version 0.27 — June 2026*  
*Replaces version 0.26. No experimental results are claimed in this version; results will be reported after the pipeline has been executed.*

**Version note:** this is the long HAL/arXiv version. A shorter workshop version (core concept, main metrics, condensed appendices) is available on request and will be submitted separately to venues focused on interpretability and human-centered AI. The detailed list of changes from version 0.26 appears in Appendix C.

---

## Abstract

Natural-language descriptions of sparse-autoencoder (SAE) features in large language models (LLMs) can be useful and often accurate, but they are insufficiently structured for systematic evaluation, cross-feature comparison, statistical aggregation, and causal prediction. They are vague, inconsistent across annotation runs, and resistant to formal manipulation. We propose **MorphoRepr**, a controlled language with morphological structure, inspired by a regular Esperanto-like agglutinative morphology, designed as a human-readable annotation layer for sparse features produced by SAEs trained on LLM activations. Each MorphoRepr expression encodes human hypotheses about the semantics of one or more SAE latents as a compositional chain of morphemes with formally defined semantics, weighted by normalized coefficients. MorphoRepr does not claim to decode the internal representations of LLMs; it encodes structured human hypotheses about SAE latent semantics, which must be validated through activation-prediction and causal-intervention experiments. From the outset, we stress that MorphoRepr evaluates the *predictivity of an annotation*, not the raw power of a steering method.

We present the formal framework, a five-phase agentic evaluation pipeline, and a complete evaluation protocol specifying coverage, fidelity (as an AUC-ROC discrimination task), causal validity (through stratified output-property classifiers, with a primary macro-F1 score and bootstrap confidence intervals on the **paired difference** between methods), morphological productivity, and morpheme-level annotation consistency metrics — including direct comparisons, **on a shared feature set**, to natural-language labels, Semantic Regexes (Boggust et al., 2025), controlled keyword tags, and a within-split shuffled-annotation control. The central open question is whether agglutinative morphological composition provides a measurable advantage over these alternatives in annotation consistency, compactness, and causal predictive power. Experimental results will be reported in a future version after the pipeline has been executed.

**Keywords:** mechanistic interpretability, sparse autoencoders, agglutinative morphology, Esperanto, SAE feature annotation, controlled language, causal validity, morphological productivity

---

## 1. Introduction

The internal representations of large language models (LLMs) remain largely opaque to human inspection. Sparse autoencoders (SAEs) have emerged as a scalable tool for decomposing these representations into sparser and more monosemantic feature directions (Bricken et al., 2023; Cunningham et al., 2023; Anthropic, 2024). The resulting latents are more interpretable than individual neurons, but the problem of *labeling* them at scale — assigning them precise, consistent, and formally manipulable descriptions — remains a major bottleneck.

Current approaches rely on LLM-generated natural-language labels. These can be useful and often accurate, but they have well-known limitations as a formal notation system: imprecision, inconsistency across runs, and poor suitability for compositional reasoning or statistical comparison over large feature inventories (Boggust et al., 2025; Paulo et al., 2024). The challenge is not that natural language is inexpressive in principle — it can describe nearly anything at the cost of verbosity. The challenge is that natural-language descriptions are **insufficiently structured** for the systematic tasks required by large-scale interpretability: cross-feature comparison, morpheme-level statistics, causal prediction from the label alone, and programmatic search through feature spaces.

MorphoRepr belongs to the tradition of *controlled natural languages* (CNL; Kuhn, 2014): notations with restricted syntax and vocabulary, designed for precision and manipulability. Its closest precedent in interpretability is the structured language of Semantic Regexes (Boggust et al., 2025), a strong baseline — with public code and package, and already validated by a user study — against which MorphoRepr must be evaluated. The difference lies in the mechanism of composition: logical operators for Semantic Regexes, agglutinative morphological concatenation for MorphoRepr.

This paper proposes **MorphoRepr**, a controlled language for annotating SAE features. It addresses these limitations by borrowing the structural logic of a regular Esperanto-like agglutinative morphology — agglutinative composition, a finite morpheme inventory, transparent derivational rules — and extending it with a controlled vocabulary of semantic primitives induced empirically from the SAE feature space of a production LLM. The central claim is not that MorphoRepr captures the internal geometry of LLM representations — it explicitly does not — but that it may provide a more consistent, compact, and causally predictive annotation system than existing alternatives for the subset of SAE latents whose content is stable and morpho-semantically expressible.

**Scope note.** MorphoRepr encodes human hypotheses about SAE latent semantics. An SAE latent is not equivalent to a human concept: latents are learned directions in activation space, dependent on reconstruction objectives, sparsity constraints, corpus statistics, and model architecture. Their interpretability is promising but partial. MorphoRepr descriptions are hypotheses about latent content, not truths about the model’s internal representations.

### 1.1 Contributions

This paper makes the following contributions:

1. **Conceptual:** we propose MorphoRepr as a controlled language for SAE feature annotation and ground it theoretically in the linear representation hypothesis and the superposition hypothesis, while explicitly distinguishing its two mechanisms of composition (additive and agglutinative), which have different epistemic status (Section 3.1).

2. **Methodological:** we describe a five-phase agentic pipeline for empirically inducing a MorphoRepr lexicon from SAE features, and specify a complete evaluation protocol including: coverage on stratified splits; fidelity as an AUC-ROC discrimination task; causal validity through stratified output-property classifiers (robust, semi-robust, and fragile), with a **primary macro-F1 score** and **bootstrap confidence intervals on the paired difference between methods**, computed **on a shared feature set**; morphological productivity metrics; morpheme-level annotation consistency metrics; a within-split shuffled control; and planned human audit and user study. The primary causal validation is designed to run on an open-weight proxy model (Section 4.2).

3. **Prospective:** we identify the open research questions future experimental versions must address, discuss threats to validity, and sketch a longer-term research agenda.

### 1.2 Status of the paper

This paper is a **position paper and evaluation protocol**. It presents a formal framework and a complete experimental protocol; it reports no experimental results. Results will be reported in a future version (v1.0) after the agentic pipeline described in Section 4 has been executed.

To clarify what is and is not claimed, the following table aligns each claim with its status in the present version and the planned evidence for testing it.

| Claim | Status (v0.27) | Planned evidence |
|------|----------------|------------------|
| MorphoRepr is more compact than NL labels | Hypothesis | length / entropy / user study |
| MorphoRepr is more consistent than NL labels | Hypothesis | Jaccard over two runs |
| MorphoRepr is more causally predictive than Semantic Regexes | **Main hypothesis** | steering + classifiers (Section 4) |
| MorphoRepr is more readable than Semantic Regexes | Hypothesis | user study (Section 4.6) |
| MorphoRepr covers all SAE latents | **Not claimed** | categorized UNCOVERED rate |
| Agglutination adds value beyond shared primitives | **Open question** | ablation study (Section 4.7) |

---

## 2. Background and related work

### 2.1 Sparse autoencoders and mechanistic interpretability

The linear representation hypothesis (LRH) posits that neural networks encode interpretable concepts as linear directions in their activation spaces (Mikolov et al., 2013; Park et al., 2023). The superposition hypothesis (Elhage et al., 2022) proposes that models compress many such features into fewer neurons by exploiting approximate orthogonality, creating polysemantic neurons that respond to several unrelated concepts. However, the LRH is not universal: Engels et al. (2024) show the existence of irreducibly multidimensional features (for example circular structures for weekdays or months), which bounds the validity of any strictly additive composition of one-dimensional latents.

Sparse autoencoders address superposition by projecting activations into a higher-dimensional space while imposing sparsity. Bricken et al. (2023) show that SAE features are more monosemantic and more interpretable than individual neurons. Anthropic (2024) scales this approach to production models (Claude 3 Sonnet). Gao et al. (2024) provide a complementary analysis of SAE training dynamics, reconstruction quality, and sparsity trade-offs.

**Important caveat:** SAE latents are learned decompositions, not verified feature detectors. They depend on reconstruction objectives, sparsity penalties, dictionary size, training corpus, and model architecture. A latent with a plausible natural-language description is not necessarily a clean human concept; it may be a statistical artifact, a corpus-specific regularity, or a superposition of several weaker patterns. Documented structural limitations aggravate this risk: Chanin et al. (2025) show that too-narrow SAEs, in the presence of correlated features, **merge** components of distinct features (*feature hedging*), undermining the expected monosemanticity — a phenomenon suspected to contribute to SAE underperformance against supervised baselines. Any annotation system — including MorphoRepr — encodes hypotheses about latent content, not facts about the model’s internal representations, and must not presuppose that all latents are clean.

The current bottleneck is *labeling*: assigning human-readable descriptions to the tens of thousands of features discovered by large SAEs. Existing approaches use LLMs to generate natural-language descriptions by inspecting high-activation examples (Bills et al., 2023; Paulo et al., 2024). These descriptions can be useful and often accurate, but they are insufficiently structured for systematic evaluation and formal reasoning.

### 2.2 Structured languages for feature annotation

Boggust et al. (2025) introduce *Semantic Regexes*, a structured language for automatically describing LLM features by combining primitives for exact token patterns, syntactic forms, and semantic categories with modifiers for contextualization, composition, and quantification. Their work reports that Semantic Regexes match the accuracy of natural-language labels while producing more concise and more consistent descriptions, and that a user study shows they help users build accurate mental models of features. Their code and Python package are public. This is the closest predecessor of MorphoRepr and the main baseline against which MorphoRepr must be evaluated: we use their official implementation in the protocol (Section 4).

The key structural difference is the mechanism of composition. Semantic Regexes combine primitives through logical operators (AND, OR, NOT, context). MorphoRepr is an *agglutinative* controlled language, where primitives are combined by concatenation according to morphological rules, producing a single pronounceable token rather than a formula. Whether this distinction yields a measurable advantage in annotation consistency, cognitive load, or causal predictive power is the central empirical question this paper prepares to answer. Since Semantic Regexes have already demonstrated concision and consistency relative to NL, the specific challenge for MorphoRepr is *with respect to Semantic Regexes*, not merely natural language.

The claim of better human readability — that `0.87·mal-far-int-e` is more readable than `¬(ag:past & subject:human)` — is an ergonomic hypothesis, not an established result. It will be tested in the planned user study (Section 4.6).

**Fidelity as a detection task.** The fidelity metric we adopt (Section 4) — discriminating high-activation examples from matched controls using only the annotation — belongs to the tradition of *detection scoring* in automatic interpretation (Bills et al., 2023; Paulo et al., 2024), reformulated here as AUC-ROC. We do not present it as novel, but as a reusable testable endpoint.

### 2.3 Model editing

ROME (Meng et al., 2022) and MEMIT (Meng et al., 2023) show that factual associations in transformers can be localized in specific MLP weight matrices and surgically modified. These techniques are relevant as a longer-term application target for MorphoRepr, briefly discussed in Section 5.

### 2.4 Complementary learning systems

Complementary learning systems (CLS) theory (McClelland et al., 1995; Kumaran et al., 2016) — fast hippocampal memory and slow neocortical memory — motivates only the longer-term research agenda sketched in Section 5 (MorphoRepr-Memory) and is not a justification of the present contribution.

### 2.5 Agentic explanation, natural-language autoencoders, and steering benchmarks

Several recent works delimit MorphoRepr’s position.

**Agentic explanation.** SAGE (Han et al., 2025) is an agentic framework that, for each feature, formulates multiple explanations, designs activation experiments to test them, and refines explanations using empirical feedback. MorphoRepr shares the agentic spirit (Section 4) but aims at a *controlled notation* rather than free-language explanation.

**Natural-language autoencoders (NLA).** Anthropic (2026) trains a model to translate its activations into text (activation verbalizer) and then reconstruct the activation from that text alone (activation reconstructor). MorphoRepr is also a textual layer between activation and interpretation, but with a different goal: NLAs optimize natural language for *activation reconstruction*, whereas MorphoRepr optimizes a controlled notation for *consistency, search, comparison, and causal prediction*. The validation paradigms differ (activation reconstruction vs causal intervention).

**Steering benchmarks and representational baselines.** AxBench (Wu et al., 2025) directly compares prompting, finetuning, SAEs, difference-in-means (DiffMean), linear probes, and representation finetuning (ReFT). For steering, prompting outperforms all methods, followed by finetuning; for concept detection, DiffMean is strongest; SAEs are not competitive in that benchmark. A recent response (Jørgensen & Hansen, 2026) nuances this picture: SAEs become nearly on par with a LoRA baseline on AxBench when features are selected and labeled by a supervised pipeline. This debate is directly relevant: MorphoRepr does not evaluate the power of a steering method but the **causal predictivity of an annotation**, and we include DiffMean / ReFT as intervention comparison points (Section 4.2).



---

## 3. The MorphoRepr system

### 3.1 Design principles

MorphoRepr is designed around four principles.

**Morphological compositionality.** Every MorphoRepr expression is a finite concatenation of morphemes drawn from a fixed inventory. The meaning of an expression is entirely determined by the meanings of its constituent morphemes and their order of composition.

**Weighted encoding.** Each term in an expression is preceded by a real-valued coefficient in [0.01, 1.00] (see Section 3.2 for its interpretation). A complete expression has the form:

```
c₁·m₁[-m₂[-m₃]] [+ c₂·m₄[-m₅] [+ ...]]
```

where the `mᵢ` are morphemes, `-` denotes agglutinative concatenation, `+` denotes additive combination of terms, and `cᵢ ∈ [0.01, 1.00]` are coefficients ordered by decreasing value. For example:

```
0.87·mal-far-int-e  +  0.41·pens-ad-is
```

is read as: *“not having (really) acted (coefficient 0.87) plus having continued to think (0.41).”*

**Two mechanisms of composition with different epistemic status.** MorphoRepr combines morphemes in two ways that must not be conflated. The *additive* combination between terms (`c₁·m₁ + c₂·m₂`) is the natural analogue of linear superposition: under the LRH, feature directions add in activation space. By contrast, *agglutinative* concatenation inside a word (`mal-far-int-e`) is ordered and non-commutative and **corresponds to no operation in SAE activation algebra** (neither sum nor projection). At this stage, it is an ergonomic bet: producing a single pronounceable and compositional token that may be more readable than a formula. This is precisely what distinguishes MorphoRepr from Semantic Regexes, and it is also what must be demonstrated rather than assumed. The ablation study (Section 4.7) is designed to isolate empirically the contribution of agglutination and order.

**Formal semantics of morphemes.** Each morpheme in the inventory has a formally specified definition including: (a) a denotation in terms of a semantic primitive, (b) a scope statement specifying what the morpheme covers and excludes, and (c) a set of attested SAE features that the morpheme reliably encodes.

**Bounded expressivity.** MorphoRepr is explicitly designed as a *lossy projection*. It captures morpho-syntactic and broad semantic content of SAE features. Pragmatic, cultural, named-entity-specific, and deeply contextual content is outside its scope by design. The residual — features that the system cannot encode with confidence ≥ 0.50 — is a first-class output (UNCOVERED), not a failure mode.

### 3.2 Interpretation and normalization of coefficients

MorphoRepr uses two types of coefficients, distinguished by context of use, and the pipeline explicitly tracks them through the `coefficient_type` field:

- **Confidence coefficient `γ`** (*static annotation* mode): when an expression annotates a feature `f` independently of an instance, `γᵢ ∈ [0.01, 1.00]` represents the encoder’s confidence in the assignment of morpheme `mᵢ`. **This is the mode used by the evaluation protocol in Section 4**, and the coefficients in the examples in Section 3.4 are `γ` values (pedagogical annotation confidences), not measured activations.

- **Activation coefficient `α`** (*contextualized instance* mode): when an expression annotates a specific activation instance `x`, `αᵢ(x)` represents the normalized activation strength of the corresponding latent. The normalization reference is the 99th percentile of activations observed for latent `f` on a reference corpus:

```
α(f, x) = clip( a(f, x) / p99(f), 0.01, 1.00 )
```

This convention ensures that (a) the coefficient reflects the relative strength of the feature in the current context; (b) values remain bounded and comparable across features and layers; and (c) the additive combination expresses the relative contribution of two features in the same context, not their absolute activation amplitudes.

The two families have the same surface form (a real number in [0.01, 1.00]); only their semantics differ, and the pipeline preserves the type. A static expression has the form `γ₁·m₁ + γ₂·m₂`; a contextualized expression has the form `α₁(x)·m₁ + α₂(x)·m₂`. *Planned extension:* since Phase 4 measures real before/after activations, it will allow empirical comparison between `γ`-mode annotations and `α`-mode annotations on the steered subset.

### 3.3 Morpheme inventory

The MorphoRepr inventory is organized into five categories. In accordance with the grammar formalized in Appendix A, **domain morphemes serve as roots** (the semantic nucleus of a word), while polarity morphemes serve as prefixes. Free roots — induced by the agentic pipeline for concepts not covered by the predefined vocabulary — are allowed and denoted by lowercase letter sequences of 2 to 5 characters; see Note 1.

**Tense suffixes** (encode verbal tense and aspect; production `tense-suffix`):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|--------------------|
| `-as` | present, ongoing | present tense `-as` |
| `-is` | past, completed | past tense `-is` |
| `-os` | future, anticipated | future tense `-os` |
| `-us` | conditional, hypothetical | conditional `-us` |
| `-u` | volitive, imperative | volitive `-u` |

**Participial infixes** (inserted between the root and suffix):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|--------------------|
| `-ad-` | iterative, habitual | iterative suffix `-ad-` |
| `-int-` | past active participle | `-int-` |
| `-it-` | past passive participle | `-it-` |
| `-at-` | present passive participle | `-at-` |
| `-ist-` | habitual/professional agent | `-ist-` |
| `-ant-` | current agent, actor | present active participle |
| `-ig-` | causative, to cause to do | `-ig-` |
| `-iĝ-` | inchoative, to become | `-iĝ-` |

**Polarity and degree prefixes** (modify the root they precede):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|--------------------|
| `mal-` | negation, opposite | `mal-` |
| `ne-` | absence, lack | `ne` (adverb) |
| `pli-` | comparative increase | `pli` |
| `plej-` | superlative | `plej` |
| `duon-` | partial, approximate | `duon-` |

**Domain roots** (predefined semantic roots; production `predefined-root`):

| Root | Meaning | Notes |
|------|---------|-------|
| `sci` | knowledge, fact, belief | covers epistemic features |
| `emo` | affect, emotion, valence | covers sentiment features |
| `ag` | physical action, movement | covers action features |
| `dir` | direction, spatial relation | covers spatial features |
| `soc` | social relation, role | covers interpersonal features |
| `dat` | numerical, code, data | covers technical/computational features |
| `tem` | time, sequence, order | covers temporal-ordering features |
| `lok` | place, location | covers spatial anchoring features |
| `mal` | opposite, negation (as entity) | **dual role**: also prefix `mal-`; see below |
| `ne` | absence, lack (as entity) | **dual role**: also prefix `ne-`; see below |

**Note on the dual role of `mal` and `ne`.** These two tokens are both *prefixes* (`mal-emo-a` = “negative affective property”) and *predefined roots* (`mal-o` = “the opposite, as entity”; Esperanto `malo`). Disambiguation is positional: `mal`/`ne` are roots when no other root follows before the suffix, and prefixes otherwise. Encoders must explicitly declare the chosen parse (Section 3.4).

**Syntactic-role suffixes** (the final element of a word when nominal, adjectival, adverbial, or infinitival):

| Morpheme | Meaning | Esperanto analogue |
|----------|---------|--------------------|
| `-o` | noun (entity, concept) | nominal suffix `-o` |
| `-a` | adjective (property, attribute) | adjectival suffix `-a` |
| `-e` | adverb (manner, degree) | adverbial suffix `-e` |
| `-i` | infinitive (abstract action) | infinitive suffix `-i` |

**Note on suffix types.** MorphoRepr uses two distinct suffix families: *syntactic-role suffixes* (`-o`, `-a`, `-e`, `-i`) and *tense suffixes* (`-as`, `-is`, `-os`, `-us`, `-u`). A word ends in exactly one suffix. A word with a tense suffix is verbal; a word with a syntactic suffix is nominal, adjectival, adverbial, or infinitival. This distinction is explicit in the grammar (Appendix A), and the inventory above is exhaustively aligned with the grammar and the reference parser.

---

*Note 1: Free roots such as `far` (do/act) and `pens` (think) are valid MorphoRepr roots under the grammar production `free-root ::= [a-z]{2,5}`. They are induced by the agentic pipeline (Phase 2) when no predefined domain root covers a feature cluster. Free roots must be registered in the versioned lexicon before use. A free root cannot be identical to an already defined prefix token (`mal`, `ne`, `pli`, `plej`, `duon`), infix token (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) or suffix token (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`). Unregistered free roots are syntactically valid but semantically undefined.*

---

### 3.4 Encoding examples

The following examples illustrate MorphoRepr encodings for SAE features. **They are pedagogical illustrations**, not experimentally validated encodings, and their coefficients are annotation confidences (`γ`, Section 3.2). The encoding choices reflect informed human judgment and are explicitly interpretive — they may vary across annotators, which is precisely what the evaluation protocol is designed to measure. Feature indices and descriptions are drawn from the public Neuronpedia interface for Claude 3 Sonnet (layer and SAE version to be specified in the experimental version; in proxy mode, see Section 4.2, features and SAEs are those of the proxy model and these examples remain purely illustrative).

**Feature #892** (natural-language description: *“tokens in past-tense contexts, especially completed actions”*):

```
0.91·ag-is
```

Parse: `ag` (domain root) + `-is` (tense suffix, past). Reading: *“completed physical action (past)”*, confidence 0.91. The tense suffix `-is` is used here because the feature encodes a verbal and temporal property; `-o` would encode action-as-entity.

**Feature #1204** (description: *“negation markers and negative-polarity elements”*):

```
0.88·mal-o  +  0.34·ne-a
```

Parse, term 1: `mal` (predefined root) + `-o` (syntactic suffix). Parse, term 2: `ne` (predefined root) + `-a`. Reading: *“negation as entity (0.88) plus absence as property (0.34).”* Note: `mal` and `ne` function here as roots (Esperanto: `malo` = “the opposite”), not as prefixes — positional disambiguation (no root follows them before the suffix); encoders must explicitly declare this parse choice.

**Feature #3871** (description: *“human agents performing intentional actions, especially in narrative contexts”*):

```
0.79·soc-ant-o  +  0.45·ag-int-a
```

Parse, term 1: `soc` (root) + `-ant-` (infix) + `-o` (suffix). Parse, term 2: `ag` (root) + `-int-` (infix) + `-a` (suffix). Reading: *“social actor currently acting (0.79) plus entity having physically acted (0.45).”*

**Feature #4102** (description: *“Python code involving for-loops and iteration patterns”*):

```
0.94·dat-ad-o
```

Parse: `dat` (root) + `-ad-` (infix, iterative) + `-o` (suffix). Reading: *“iterative data/code process”*, confidence 0.94. **Recognized limitation:** this encoding cannot distinguish between code iteration, numerical series, textual repetition, or syntactic patterns — a known limitation of the predefined domain-root vocabulary, motivating the induction of free roots.

**Feature #7823** (description: *“tokens appearing in emotionally negative contexts, especially grief and loss”*):

```
0.86·mal-emo-a  +  0.42·ne-soc-a
```

Parse, term 1: `mal-` (prefix) + `emo` (root) + `-a` (suffix). Parse, term 2: `ne-` (prefix) + `soc` (root) + `-a`. Reading: *“negative affective property (0.86) plus absence of social relation (0.42).”* **Encoding rationale:** grief and loss involve both negative valence (`mal-emo-a`) and relational absence (`ne-soc-a`). **Recognized limitation:** the encoding remains interpretive and could vary across annotators; the evaluation protocol directly measures this variance.

**Scope note for an expression.** An expression may annotate either *one* SAE latent (its terms then being co-present facets, as for feature #7823), or *a small cluster* of co-activated latents. The contract is fixed by the usage context: in Phase 4 (causal validation), an expression annotates the **single latent** being steered, and its coefficients are `γ` confidences over facets of that latent. This clarification removes ambiguity between one coefficient per latent and multiple coefficients per expression.

### 3.5 Note: optional analogy with the MDE abstraction hierarchy

For readers familiar with model-driven engineering, MorphoRepr admits an abstraction-level reading (instance/token → described latent → expression → morpheme inventory), analogous to the M0–M3 levels of MDE. This analogy is purely illustrative, is not a scientific justification, and can be ignored without loss of continuity; a fuller discussion is available on request.

---

## 4. Agentic feasibility study

### 4.1 Motivation for an agentic approach

Inducing a MorphoRepr lexicon from SAE features requires both consistent application of formal rules (amenable to automation) and semantic judgment about morpheme relevance (requiring LLM-level reasoning). This combination motivates a multi-agent pipeline. We acknowledge upfront that the pipeline uses LLMs for annotation, judgment, prediction, and reporting. The safeguards described in this section, together with the human audit described in Section 4.3, are designed to bound the resulting circularity.

### 4.2 Pipeline architecture

The pipeline consists of five phases, plus a planned human audit, user study, and ablation study. Complete prompt templates are provided in Appendix B.

#### Phase 1: SAE feature extraction

**Objective:** build a stratified corpus of SAE features with activation examples.

**Data sources:** public SAEs through the Neuronpedia API; SAE-Bench (EleutherAI); `sae_lens`. **Model/layer consistency:** all features in a run come from the same model and, unless otherwise stated, the same layer; in proxy mode (see below), the feature source is the proxy model, and the Claude 3 Sonnet examples in Section 3.4 remain purely illustrative.

The *loader agent* retrieves, for each feature, its index, its top 20 activation examples with activation values, its existing interpretability score, activation frequency, layer, and activation statistics (including the 99th percentile, for normalization and OOD detection). The *ranking agent* constructs **three disjoint evaluation splits** to avoid selection bias:

- **Easy set** (n=200): features with interpretability score ≥ 0.7 and high frequency.
- **Random set** (n=200): features sampled uniformly **from the complement of easy ∪ hard** (disjointness guaranteed).
- **Hard set** (n=100): features with interpretability score < 0.5, or context-dependent features, or domain-specific features (code, mathematics, named entities, multilingual).

All main go/no-go thresholds are evaluated on the **random set**.

#### Phase 2: MorphoRepr lexicon induction

**Objective:** identify a minimal set of morphemes covering the semantic space of the feature corpus.

The *clustering agent* embeds natural-language descriptions using nomic-embed-text and applies k-means clustering (k ≈ 20) with a **fixed seed** (as well as the UMAP visualization), ensuring reproducibility of lexicon induction. The *labeling agent* proposes morphemes per cluster (see Appendix B.1). The *consistency agent* validates them according to three criteria: non-redundancy (cosine similarity < 0.7), coverage, and composability. Failures trigger a feedback loop (max 5 iterations).

**Lexicon governance:** free roots are registered in a versioned lexicon with a formal definition, scope statement, inducing feature cluster, and version timestamp. A free root cannot collide with an existing prefix, infix, or suffix token.

**Morphological productivity metrics** (computed at the end of Phase 2 and updated after Phase 3):

| Metric | Definition |
|--------|------------|
| Features per root | Mean number of features covered by each root |
| Free-root rate | New free roots introduced per 100 encoded features |
| Base-lexicon coverage | Proportion of annotations using only predefined domain roots |
| Free-root coverage | Proportion of annotations requiring at least one free root |
| Morpheme entropy | Shannon entropy of the morpheme-use distribution |

A high free-root rate or low morpheme entropy would indicate that MorphoRepr is drifting toward a compressed dictionary rather than a genuinely compositional system. *These metrics rely on correct morphemic decomposition: the reference parser is tested on all examples in the present paper, including infix cases and `mal`/`ne` roots.*

#### Phase 3: Feature encoding, fidelity, and coverage measurement

**Objective:** encode each feature and compute stratified coverage, fidelity, and consistency statistics over two independent annotation runs.

**Coverage metrics** (per split): raw coverage rate (encoder confidence ≥ 0.6); UNCOVERED rate categorized by feature type.

**Fidelity metric — discrimination task:** for each encoded feature `f`, we construct 20 top-activating examples (positive set) and 20 matched control examples (negative set). A *fidelity judge agent* receives the MorphoRepr annotation and ranks which examples belong to the positive set. Fidelity is the **AUC-ROC** of this discrimination task (related to *detection scoring*, Section 2.2), turning fidelity into a testable prediction task rather than a subjective plausibility judgment.

**Annotation consistency metrics** (morpheme level, between two independent runs):

| Metric | Definition |
|--------|------------|
| Exact-match rate | Proportion of features receiving identical expressions in both runs |
| Root Jaccard | Jaccard similarity of root sets between the two runs |
| Morpheme Jaccard | Jaccard similarity of full morpheme sets |
| Coefficient correlation | Pearson correlation of coefficients for matched terms |
| Morphemic edit distance | Mean number of morpheme substitutions between the two annotations |

ROUGE-L is retained as a secondary metric for comparison to natural-language baselines only.

**Baseline comparisons** (run in parallel on the same corpus):

| Baseline | Description |
|----------|-------------|
| Natural-language labels | Generated by LLM, unconstrained |
| Semantic Regexes | Official implementation of Boggust et al. (2025) |
| Controlled keyword tags | Single noun phrase, no composition |
| Shuffled MorphoRepr | See below |

**Shuffled MorphoRepr baseline:** real MorphoRepr annotations from other features are randomly reassigned *within the same split* and with comparable expression length (±1 term). Within-split shuffling avoids cross-contamination between easy and hard features; length matching avoids a trivial detectable divergence. This tests whether the morphological form alone carries predictive power independently of meaning.

#### Phase 4: Causal validation through activation steering

**Objective:** verify that MorphoRepr expressions are causally predictive of model behavior under interventions on features.

**Validation model (proxy by default).** Full experimental access to Claude 3 Sonnet activations (controlled steering with before/after generation) is not guaranteed by public interfaces. Therefore, the primary causal validation runs on an **open-weight proxy model with public SAEs** (e.g. GPT-2, Pythia, or Mistral via `sae_lens`). In this case: (a) all causal conclusions are limited to the proxy model; (b) the entire pipeline (Phases 1–5) operates on the proxy SAEs; (c) this is explicitly stated in the Methods section of the experimental paper. If direct access to a production model’s activations is obtained, the same protocol applies.

**Steering protocol:** for each encoded feature, the *steering agent* amplifies the target SAE latent **at its own layer** (the feature’s `layer` column) over 20 neutral probe sentences and records the output shift. The **primary magnitude is normalized per feature** (a multiple of the feature’s 99th activation percentile), making interventions comparable across features and layers; the historical fixed magnitude of +5 units (Anthropic, 2024) is retained as a secondary condition. A dose-response curve (several multiples of `p99`) is executed on a subsample; its monotonicity serves as evidence of a real causal effect. A *causal prediction agent* generates a behavioral prediction based **only on the MorphoRepr expression** — see Appendix B.3. A *judge agent* evaluates whether the observed output shift matches the prediction.

**Exclusion of out-of-distribution (OOD) outputs:** an instance whose achieved activation exceeds `p99 × OOD_threshold` is marked OOD and **excluded from the primary metric** (reported separately): steering that pushes the model out of distribution measures noise, not the causal role of the feature.

**Methodological safeguard against circularity:** the judge agent receives only the MorphoRepr expression and the observed output shift, not the natural-language description. The shuffled MorphoRepr baseline further quantifies how much predictive power is attributable to morphological form alone, independently of the encoding step.

**Fair comparison between methods.** The head-to-head causal-validity comparison (MorphoRepr vs NL labels vs Semantic Regexes) is computed **on the same feature set** — the intersection of features covered by MorphoRepr (confidence ≥ 0.5) — to avoid giving MorphoRepr an advantage by evaluating it only on its clearest features. Baselines are also reported on the full set for transparency. **Predictor symmetry:** each baseline has a parallel prediction prompt (taking its annotation and predicting the same properties), engineered with equal care and frozen before the run, so that comparison does not hinge on differential prompt quality.

**Output-property classifiers — stratified by robustness level:**

Rather than a single binary judgment, the protocol measures a set of output properties, stratified by classifier reliability:

*Robust properties* (high classifier reliability; primary metrics):

| Property | Measurement method |
|----------|--------------------|
| Negation presence | Syntactic parser (carefully pruned negation lexicon; no ambiguous prefixes) |
| Tense (past/present/future) | POS tagger |
| Code presence | Token-level classifier |
| Conditional modality | Syntactic pattern matching |

*Semi-robust properties* (moderate reliability; secondary metrics):

| Property | Measurement method |
|----------|--------------------|
| Emotional valence | Transformer-based sentiment classifier (full label distribution) |

*Fragile properties* (lower reliability; reported separately with caveats):

| Property | Measurement method | Known limitations |
|----------|--------------------|-------------------|
| Agent presence | NER + dependency analysis | Parser errors on complex sentences |
| Social reference | NER + coreference | Coreference-resolution noise |
| Spatial reference | NER + syntactic parse | Ambiguous prepositional phrases |
| Iterative structure | Pattern matching | High false-positive rate |

Results for fragile properties are reported separately and interpreted with explicit caveats. Causal-validity conclusions are drawn primarily from robust and semi-robust properties. All classifier outputs are checked on a random sample of 50 features before the full run, with confusion matrices reported.

**Causal-validity score.** The causal prediction agent predicts the direction of change for each property ({increase, decrease, no_change}); the judge measures the observed direction. The **primary score is macro-F1 over these three directions**, restricted to robust properties and **computed per feature then averaged** over the random set (per-property accuracy is retained as a secondary metric). Macro-F1 explicitly handles the `no_change` class and is not biased by direction imbalance. Cases where the agent predicts no property, or where steering fails, are handled according to a pre-registered rule (prediction failure = zero score for the relevant property); OOD instances are excluded as described above.

**Causal-validity outcome categories:** each feature is assigned to one of four categories: *confirmed* (a majority of robust properties move as expected), *partial* (some properties move), *null* (no measurable shift), *mixed/ambiguous* (shifts in unexpected directions).

**Additional intervention controls** (beyond the shuffled-annotation control):
- random SAE feature from the **same layer**;
- random direction of the **same norm**;
- feature with **comparable activation frequency**;
- **negative steering** (−magnitude) when semantically relevant;
- **prompt-only**: provide the label in the prompt without steering;
- supervised **DiffMean / ReFT** baseline (cf. Section 2.5).

**Additional validity controls:**
- Shuffled MorphoRepr annotations as a negative control (expected: causal validity near chance). *To remain comparable to treatment, a subset of shuffled annotations is scored through the same predictor + judge path as treatment; the rest through classifiers to bound cost.*
- Causal validation executed separately for easy / random / hard splits.
- Two independent prediction runs; Cohen’s κ on categorical outcomes.

**Go/no-go criterion:** the main publication criterion is **relative improvement over baselines**, evaluated by a **paired** comparison (methods annotating the same features):

> MorphoRepr is considered to demonstrate causal utility if, on the random set and shared feature set, the **95% bootstrap confidence interval of the paired difference** in causal-validity score (MorphoRepr − baseline, per feature) **excludes 0** in the positive direction, both against natural-language labels and against Semantic Regexes.

This paired formulation replaces the earlier “non-overlap of marginal confidence intervals” criterion, which was unnecessarily conservative. The operational floor of 0.50 (macro-F1) on the random set is retained as an absolute minimum threshold below which the system has no practical utility, regardless of comparison to baselines.

**Statistical methodology.** All confidence intervals are bootstrap intervals (10,000 resamples, **stratified by split**, fixed seed). Main comparisons (pre-declared: causal validity on random set, robust properties, vs NL and vs Semantic Regexes) are corrected with **Holm-Bonferroni**; exploratory analyses (other splits, fragile properties, secondary metrics) are flagged as such and corrected with **Benjamini-Hochberg**. An indicative power analysis is reported (with ≈100 paired features entering causal validation and an expected effect of about 0.05–0.10, power to detect a MorphoRepr vs Semantic Regexes difference is limited and explicitly quantified).

#### Phase 5: Synthesis and publication

The *reporting agent* generates stratified statistics on coverage, fidelity, consistency, causal validity (by property robustness tier), and productivity across all splits and baselines. The *gap-analysis agent* categorizes UNCOVERED features by type. The *writing agent* produces a structured summary of results for inclusion in the v1.0 experimental paper.

### 4.3 Human audit

To bound the circularity introduced by using LLMs throughout the pipeline, the v1.0 experimental paper will include a **human audit** on a subset of 50 features randomly sampled from the random split. For each feature in this subset:

- Two independent human annotators (NLP/ML researchers) produce MorphoRepr annotations after a standardized training session.
- Human annotations are compared to pipeline annotations using morpheme Jaccard, root overlap, and coefficient correlation.
- Disagreements are adjudicated by a third annotator.
- Agreement between human annotations and pipeline annotations is reported as a calibration metric for pipeline reliability (not as a hard threshold, given the limited sample size).

The human audit does not replace the automated pipeline for the full corpus, but provides a calibration point of ground truth that bounds interpretation of pipeline results.

### 4.4 Technical stack

```
Orchestration:           deterministic orchestrator (frozen/auditable state);
                         Claude Code used for development/supervision only
LLM agents:              semantic judgment model; lightweight scoring/formatting model
SAE access:              sae_lens + Neuronpedia API (neuronpedia.org)
Validation model:        open-weight proxy model by default (Section 4.2)
Embeddings:              nomic-embed-text (feature-description clustering, fixed seed)
Clustering:              scikit-learn k-means + UMAP (visualization), fixed seeds
Storage:                 SQLite (feature corpus) + JSON (versioned lexicon)
Output classifiers:      spaCy (syntax/NER/dependencies),
                         transformer-based sentiment classifier (valence),
                         custom classifiers for code/modality; confusion matrices reported
Evaluation:              SAE-Bench (EleutherAI) as external benchmark
Baselines:               NL labels, Semantic Regexes (official code), keyword tags,
                         within-split shuffled MorphoRepr; DiffMean/ReFT as intervention controls
Checkpoints:             complete pipeline-state snapshot after each phase
Human audit:             50 features, 2 annotators + adjudicator
```

*Reproducibility note.* The run is **frozen and auditable** rather than strictly deterministic: code, configuration, prompts, corpus, and lexicon are fixed and hash-verified; however, LLM call outputs are stochastic (and necessarily so for the two consistency runs). All raw agent outputs are archived, so the run can be re-analyzed even if it cannot be regenerated identically.

### 4.5 Success criteria

| Metric | Minimal floor | Publication criterion |
|--------|---------------|-----------------------|
| Raw coverage — easy set (conf ≥ 0.6) | 65% | 80% |
| Raw coverage — random set (conf ≥ 0.6) | 45% | 60% |
| Raw coverage — hard set (conf ≥ 0.6) | 20% | 35% |
| Fidelity AUC-ROC — random set | 0.60 | 0.72 |
| Causal validity (macro-F1) — random set, robust props (floor) | 0.50 | 0.65 |
| Causal validity vs NL labels, random set (shared set) | — | Paired difference > 0, 95% CI excluding 0 |
| Causal validity vs Semantic Regexes, random set (shared set) | — | Paired difference ≥ 0, 95% CI |
| Annotation consistency — root Jaccard, random set | 0.60 | 0.75 |
| Annotation consistency — exact match, random set | 0.30 | 0.50 |
| Human audit — pipeline vs human morpheme Jaccard | — | ≥ 0.60 |
| Final lexicon size | < 250 morphemes | < 150 morphemes |
| Free-root rate | — | < 5 per 100 features |
| UNCOVERED features categorized | — | ≥ 80% |

### 4.6 Planned user study

The claim that MorphoRepr annotations are more human-readable and less cognitively demanding than alternatives requires human evaluation. We plan the following study, to be reported together with experimental results in v1.0:

**Participants:** 20 NLP/ML researchers with no prior exposure to MorphoRepr.

**Design:** within-subject, counterbalanced. Each participant annotates 30 SAE features with three systems (MorphoRepr, Semantic Regexes, natural-language labels) in random order, after a short training session.

**Measures:** learning time (time to complete the training session); interpretation time (mean per feature); interpretation accuracy (agreement with expert gold annotations **independent of MorphoRepr’s designers**); annotation consistency (agreement between two participants per feature); subjective cognitive load (NASA-TLX); preference ranking.

**Hypothesis:** MorphoRepr annotations will be interpreted faster and with higher consistency than Semantic Regexes, at the cost of lower initial learnability. This hypothesis is empirical, not assumed.

### 4.7 Planned ablation study

To isolate the contribution of MorphoRepr’s distinctive components — especially agglutination and order, whose theoretical grounding is weak (Section 3.1) — we plan an ablation comparing, on consistency and causal-validity metrics: (a) full MorphoRepr; (b) without coefficients; (c) roots only; (d) morphemes **without order** (bag of morphemes); (e) suffixes/infixes only; (f) randomized coefficients. The “without order” condition is decisive: if it causes no measurable loss, ordered agglutination adds nothing beyond a set of primitives, and the value of MorphoRepr would then be purely ergonomic (to be decided by the user study).

---

## 5. Research agenda

*This section sketches longer-term research directions conditional on the experimental results from Section 4. It is not a contribution of the present paper.*

If MorphoRepr proves causally valid as an annotation system, two natural extensions emerge.

**MorphoRepr-Edit.** If MorphoRepr expressions can be validated as causally predictive at the feature level, they might eventually serve as a structured addressing space for model editing (ROME/MEMIT-style). This is highly speculative: MorphoRepr addresses SAE latents, not weight matrices directly, and mapping latents to editable weight directions requires substantial additional work.

**MorphoRepr-Memory.** A hybrid memory architecture inspired by CLS theory could combine an external vector store (episodic buffer indexed by MorphoRepr embeddings) with selective parametric consolidation via LoRA, producing a human-auditable retrieval interface.

These directions are proposed as a three-paper research program: the present paper (framework and protocol), a second paper (experimental results), and a third paper (editing or memory application).

---

## 6. Positioning in the current literature

| Approach | Compositionality | Human readability | Consistency | Causal validity |
|----------|------------------|-------------------|-------------|-----------------|
| Natural-language labels (Bills et al., 2023) | None | High | Low | Not evaluated |
| Semantic Regexes (Boggust et al., 2025) | Logical | Moderate | High | Not evaluated |
| LinguaLens (2025; see references, authors to confirm) | None | High | Moderate | Partial |
| Agentic explanation — SAGE (Han et al., 2025) | None (free language) | High | Moderate | Partial |
| Natural Language Autoencoders (Anthropic, 2026) | None | High | Moderate | Reconstruction |
| TCAV (Kim et al., 2018) | None | Moderate | Moderate | Partial |
| **MorphoRepr (proposed)** | **Agglutinative** | **High (hypothesis)** | **To be measured** | **Central criterion** |
| First-order logic | Complete | Low | High | High |

The central open question distinguishing MorphoRepr from Semantic Regexes is whether agglutinative morphological composition produces a measurable advantage in annotation consistency and causal predictive power. The evaluation protocol in Section 4 is designed to measure this empirically.

---

## 7. Discussion

### 7.1 What MorphoRepr can and cannot express

MorphoRepr captures: morpho-syntactic properties (tense, aspect, negation, agentivity, syntactic role), broad semantic domains (knowledge, affect, action, space, social relation, data), and activation strength (through coefficients). It does not capture: very specific named-entity features, deeply pragmatic features (irony, register, cultural connotation), features defined by a specific textual context, or inter-feature relations.

The estimated 45–65% coverage on the random set (pending empirical validation) means that a substantial fraction of SAE latents lies, by design, outside MorphoRepr’s expressive scope. This is not a failure — it quantifies the boundary between morpho-semantic and contextual-pragmatic content in the LLM feature space.

### 7.2 Why Esperanto and not another agglutinative language?

The choice of an Esperanto-like morphology as structural model rests on four properties: fully regular morphology (no exceptions), a finite inventory of affixes (~40 affixes with formally defined meanings), Latin alphabet notation, and human learnability. We do not claim that Esperanto morphology is intrinsically optimal; the scientific claim concerns *regular agglutinative composition* in general, of which Esperanto is merely a convenient instantiation. If the evaluation protocol shows no measurable advantage over alternatives, another notation system should be used.

### 7.3 Lexicon governance and versioning

MorphoRepr’s extensibility through free roots creates a tension: a small closed lexicon limits coverage; an unconstrained extensible lexicon risks becoming an ad hoc compressed vocabulary. The resolution is a **governed and versioned lexicon** with registered definitions, scope statements, and version timestamps. The morphological productivity metrics (Section 4.2) operationalize this tension: a high free-root rate or low morpheme entropy would indicate drift from compositionality toward a dictionary.

### 7.4 Threats to validity

**Threats to internal validity:**

- *The protocol may fail to detect MorphoRepr’s distinctive contribution.* The robust properties (negation, tense, code, modality), on which the main conclusions rest, are morpho-syntactic; Semantic Regexes encode them as well, so the two systems may converge. MorphoRepr’s truly distinctive content (semantic domain roots, agglutination) appears more in fragile, downweighted properties. Possible consequence: concluding absence of advantage because the protocol fails to measure where it would lie. The ablation study (Section 4.7) and the effort to promote at least one semantic property to semi-robust mitigate this risk.
- *Residual annotation circularity:* the encoder and fidelity judge are both LLMs. Even though the causal judge is removed from the primary metric, the encoding step has been informed by the natural-language description. The shuffled MorphoRepr baseline quantifies the predictive power attributable to morphological form alone; the human audit (Section 4.3) provides a ground-truth calibration point.
- *Dependence on initial NL descriptions:* if the NL descriptions used for clustering are poor, the induced lexicon will also be poor. Mitigated by using multiple description sources and a consistency-validation loop.
- *Output-property classifier errors:* automatic classifiers have non-zero error rates, especially for fragile properties. All outputs are checked on 50 features before the full run, with confusion matrices; negation lexicons are pruned of ambiguous prefixes.
- *Steering magnitude calibration:* a fixed magnitude may not be comparable across features and layers. The primary magnitude is normalized per feature (multiple of `p99`); achieved magnitude distributions are reported and OOD instances are excluded from the primary metric.
- *Comparability of the shuffled control:* the negative control is strictly comparable to treatment only if scored through the same path; a subset of shuffled annotations therefore goes through the predictor + LLM judge path to calibrate the comparison.

**Threats to external validity:**

- *Dependence on the validation model:* the primary causal validation runs on an open-weight proxy model; its conclusions do not automatically generalize to other models, SAE architectures, or feature dictionaries. Generalization requires separate replication studies. The Claude 3 Sonnet examples in the paper are illustrative and do not constitute validated results.
- *Variance and quality of SAE latents:* latents may suffer from merging (feature hedging), absorption, or splitting (Chanin et al., 2025), and some features are irreducibly multidimensional (Engels et al., 2024), bounding any notation based on additive composition of directions. UNCOVERED results in the hard set may reflect latent quality rather than limitations of the system; they are analyzed separately.
- *A strong and already validated baseline:* Semantic Regexes have already demonstrated concision, consistency, and user-study benefit relative to NL; surpassing this baseline, especially in causal validity (which it did not evaluate), is demanding. Surpassing this baseline, especially in causal validity (which it has not evaluated), is a demanding objective and the right comparison frame.
- *English-language bias:* the current protocol annotates English-language features. MorphoRepr’s morphology is language-agnostic in principle, but its usefulness for multilingual feature spaces or code-heavy spaces is not tested.
- *Cognitive cost of learning MorphoRepr:* if the notation requires substantial training time, its practical advantage over NL labels is reduced. The user study (Section 4.6) measures this directly.
- *Risk of ad hoc lexicon growth:* if free-root induction is too permissive, MorphoRepr loses its compositional property. Productivity metrics and governance rules are designed to detect and constrain this drift.

---

## 8. Conclusion

We have proposed MorphoRepr, a controlled language with morphological structure for annotating SAE features in LLMs, and described a five-phase agentic pipeline and a complete evaluation protocol for assessing its coverage, fidelity, causal validity, productivity, and annotation consistency against several baselines — including a within-split shuffled control, intervention controls, a human audit, and an ablation study.

This paper is a position paper and evaluation protocol; it claims no experimental results. The theoretical case for MorphoRepr rests on three convergent observations: the documented compositionality of LLM activation spaces (the linear representation hypothesis), the structural analogy between additive term composition and additive SAE latent composition, and the demonstrated insufficiency of natural-language labels for systematic interpretability tasks. We explicitly distinguish this foundation (which concerns additive combination) from the intra-word agglutinative mechanism, distinctive but without a counterpart in activation algebra, whose contribution must be demonstrated by ablation.

The central open question is not whether MorphoRepr is better than natural language — it is almost certainly better in consistency and worse in coverage. The central question is whether it is better than Semantic Regexes, and specifically whether agglutinative composition provides a measurable advantage in causal predictive power and annotation consistency that justifies the additional cognitive cost of learning a new notation.

MorphoRepr is not a solution for reading the internal representations of LLMs; it is a testable hypothesis for structured annotation of SAE latents, evaluated against already published and validated structured baselines.

The agentic pipeline code, MorphoRepr lexicon specification, and all experimental results will be made available at: `https://github.com/michaellaunay/morphorepr`.

---

## References

Anthropic. (2024). *Extracting Interpretable Features from Claude 3 Sonnet*. Transformer Circuits Thread. https://transformer-circuits.pub/2024/scaling-monosemanticity/

Anthropic. (2026). *Natural Language Autoencoders*. https://www.anthropic.com/research/natural-language-autoencoders

Bills, S., Cammarata, N., Mossing, D., Tillman, H., Gao, L., Goh, G., Sutskever, I., Leike, J., Wu, J., & Saunders, W. (2023). *Language models can explain neurons in language models*. OpenAI Blog.

Boggust, A., Ren, D., Assogba, Y., Moritz, D., Satyanarayan, A., & Hohman, F. (2025). *Semantic Regexes: Auto-Interpreting LLM Features with a Structured Language*. arXiv:2510.06378. (Code: https://github.com/apple/ml-semantic-regex)

Bricken, T., Templeton, A., Batson, J., Chen, B., Jermyn, A., Conerly, T., Turner, N., Anil, C., Denison, C., Askell, A., Lasenby, R., Wu, Y., Kravec, S., Schiefer, N., Maxwell, T., Joseph, N., Hatfield-Dodds, Z., Tamkin, A., Nguyen, K., … Henighan, T. (2023). *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning*. Transformer Circuits Thread.

Chanin, D., Dulka, T., & Garriga-Alonso, A. (2025). *Feature Hedging: Correlated Features Break Narrow Sparse Autoencoders*. arXiv:2505.11756.

Cunningham, H., Ewart, A., Sherburn, L., Tuck, R., & Sharkey, L. (2023). *Sparse Autoencoders Find Highly Interpretable Features in Language Models*. arXiv:2309.08600.

Elhage, N., Hume, T., Olsson, C., Schiefer, N., Henighan, T., Kravec, S., Hatfield-Dodds, Z., Lasenby, R., Drain, D., Chen, C., Grosse, R., McCandlish, S., Kaplan, J., Amodei, D., Wattenberg, M., & Olah, C. (2022). *Toy Models of Superposition*. Transformer Circuits Thread.

Engels, J., Riggs, L., & Tegmark, M. (2024). *Not All Language Model Features Are Linear*. arXiv:2405.14860.

Gao, L., la Tour, T. D., Tillman, H., Goh, G., Troll, R., Radford, A., Sutskever, I., Leike, J., & Wu, J. (2024). *Scaling and evaluating sparse autoencoders*. arXiv:2406.04093.

Han, J., Xu, W., Jin, M., & Du, M. (2025). *SAGE: An Agentic Explainer Framework for Interpreting SAE Features in Language Models*. arXiv:2511.20820.

Jørgensen, M. G., & Hansen, L. K. (2026). *Steering LLMs? Actually, Sparse Autoencoders can outperform simple baselines*. arXiv:2605.31183.

Kim, B., Wattenberg, M., Gilmer, J., Cai, C., Wexler, J., Viegas, F., & Sayres, R. (2018). *Interpretability Beyond Classification Accuracy: Quantifying Interpretability of Machine Learning Models via Concept Activation Vectors (TCAV)*. ICML 2018.

Kuhn, T. (2014). *A Survey and Classification of Controlled Natural Languages*. Computational Linguistics, 40(1), 121–170.

Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). *What learning systems do intelligent agents need? Complementary learning systems theory updated*. Trends in Cognitive Sciences, 20(7), 512–534.

[To confirm — authors to verify] *LinguaLens: Towards Interpreting Linguistic Mechanisms of Large Language Models via Sparse Auto-Encoder* (2025). arXiv:2502.20344. *(This entry replaces the “Huang et al., SAELing” reference from v0.26: the verified title of arXiv:2502.20344 is “LinguaLens”; the author list must be confirmed against the source before submission.)*

McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex: Insights from the successes and failures of connectionist models of learning and memory*. Psychological Review, 102(3), 419–457.

Meng, K., Bau, D., Andonian, A., & Belinkov, Y. (2022). *Locating and Editing Factual Associations in GPT*. NeurIPS 2022.

Meng, K., Sharma, A. S., Andonian, A., Belinkov, Y., & Bau, D. (2023). *Mass-Editing Memory in a Transformer*. ICLR 2023.

Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). *Efficient Estimation of Word Representations in Vector Space*. arXiv:1301.3781.

Object Management Group. (2016). *Meta Object Facility (MOF) Core Specification, Version 2.5.1*. Document OMG formal/2016-11-01.

Park, K., Choe, Y. J., & Veitch, V. (2023). *The Linear Representation Hypothesis and the Geometry of Large Language Models*. arXiv:2311.03658.

Paulo, G., Mallen, A., Juang, C., & Belrose, N. (2024). *Automatically Interpreting Millions of Features in Large Language Models*. arXiv:2410.13928.

Turner, A., Thiergart, L., Udell, D., Leech, G., Mini, U., & MacDiarmid, M. (2023). *Activation Addition: Steering Language Models Without Optimization*. arXiv:2308.10248.

Wu, Z., Arora, A., Geiger, A., Wang, Z., Huang, J., Jurafsky, D., Manning, C. D., & Potts, C. (2025). *AxBench: Steering LLMs? Even Simple Baselines Outperform Sparse Autoencoders*. arXiv:2501.17148.

Zamenhof, L. L. (1887). *Unua Libro* [International Language]. Warsaw.

---

## Appendix A: Formal specification of the MorphoRepr grammar

### A.1 Formal grammar (BNF)

```
expression          ::= term ('+' term)*
term                ::= coefficient '·' word
coefficient         ::= '0.' nonzero-digit digit
                      | '0.' digit nonzero-digit
                      | '1.00'
(* Canonical form: two decimals, coefficient ∈ [0.01, 1.00].             *)
(* The reference parser normalizes to this form and accepts as input      *)
(* any real value in [0.01, 1.00]; see Section 3.2 for the semantics     *)
(* (confidence γ or activation α) according to usage context.            *)
(* digit          ::= '0'|'1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'           *)
(* nonzero-digit  ::= '1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'               *)

word                ::= (prefix)* root (infix)* suffix
prefix              ::= 'mal-' | 'ne-' | 'pli-' | 'plej-' | 'duon-'
root                ::= predefined-root | free-root
predefined-root     ::= 'sci' | 'emo' | 'ag' | 'dir' | 'soc'
                      | 'dat' | 'tem' | 'lok' | 'mal' | 'ne'
free-root           ::= [a-z]{2,5}
                      (* roots induced by the pipeline, registered in the lexicon;
                         must not collide with a prefix, infix, or suffix token *)
infix               ::= '-ad-' | '-int-' | '-it-' | '-ist-' | '-ant-'
                      | '-at-' | '-ig-' | '-iĝ-'
suffix              ::= syntactic-suffix | tense-suffix
syntactic-suffix    ::= '-o' | '-a' | '-e' | '-i'
tense-suffix        ::= '-as' | '-is' | '-os' | '-us' | '-u'
```

The inventory in Section 3.3, this grammar, and the reference parser list the same morpheme inventory (prefixes, infixes including `-it-`, tense suffixes including `-u`, predefined roots including `mal`/`ne`).

### A.2 Composition rules

1. A word must contain exactly one root.
2. Prefixes precede the root; infixes follow the root and precede the suffix; the suffix is final.
3. Multiple prefixes are allowed and compose left-to-right: `mal-ne-X` = “non-absent-X” ≠ `ne-mal-X` = “non-opposite-X”.
4. Coefficients must be in [0.01, 1.00] (canonical two-decimal form). A coefficient of 0.00 indicates an absent feature and must not appear in expressions.
5. Terms in an expression are ordered by decreasing coefficient.
6. Free roots must be registered in the versioned lexicon before use; unregistered free roots are syntactically valid but semantically undefined.
7. A free root cannot be identical to a prefix token (`mal`, `ne`, `pli`, `plej`, `duon`), infix token (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`), or suffix token (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`).
8. **Disambiguation of `mal`/`ne` (prefix vs root):** `mal` and `ne` are parsed as *roots* when no other root follows before the suffix (`mal-o`, `ne-a`), and as *prefixes* otherwise (`mal-emo-a`, `ne-soc-a`, `mal-ne-o` = prefix `mal` + root `ne` + suffix `-o`). The selected parse must be explicitly declared by the encoder. (Implementation note: a strictly positional parser without backtracking is insufficient; segmentation must be performed on hyphens and then classify segments — leading prefixes without ever consuming the last available segment, which is the root.)
9. A word ending in a tense suffix (`-as`, `-is`, `-os`, `-us`, `-u`) is verbal. A word ending in a syntactic suffix (`-o`, `-a`, `-e`, `-i`) is nominal, adjectival, adverbial, or infinitival respectively. These two suffix families are mutually exclusive within a word.

## Appendix B: Prompt templates for the agentic pipeline

*All agents produce JSON output whose exact schema is specified in the corresponding prompt, so the parser and downstream queries can use it unambiguously.*

### B.1 Labeling-agent system prompt

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
with the existing lexicon (reserved tokens: mal, ne, pli, plej, duon,
ad, int, it, ist, ant, at, ig, iĝ, o, a, e, i, as, is, os, us, u).

Respond ONLY with a JSON object, no prose, with this exact schema:
{
  "root": "<proposed root>",
  "root_type": "predefined" | "free",
  "definition": "<formal definition>",
  "scope": {"covers": "<...>", "excludes": "<...>"},
  "coverage_examples": ["<feature description>", ...],
  "estimated_features_covered": <integer>
}
```

### B.2 Encoding-agent system prompt

```
You are encoding SAE features into MorphoRepr expressions.

MorphoRepr is an agglutinative formal language where:
- Each term has the form: coefficient · morpheme-chain
- Coefficients are in [0.01, 1.00] (two decimal places), representing
  your CONFIDENCE in the morpheme assignment (annotation context, γ)
- Morpheme chains follow the grammar: (prefix)* root (infix)* suffix
- Suffix is either a syntactic suffix (-o, -a, -e, -i) or a tense
  suffix (-as, -is, -os, -us, -u), not both in the same word
- 'mal' and 'ne' are ROOTS when no other root follows before the
  suffix (mal-o, ne-a), and PREFIXES otherwise (mal-emo-a)
- Domain roots (sci, emo, ag, dir, soc, dat, tem, lok) and
  registered free roots are the only valid roots
- An expression contains 1-4 terms, ordered by descending coefficient

Respond ONLY with a JSON object, no prose, using EXACTLY this schema.

If you can encode the feature with confidence >= 0.50:
{
  "status": "encoded",
  "expression": "<full MorphoRepr expression string, e.g. 0.88·mal-o + 0.34·ne-a>",
  "terms": [
    {
      "coefficient": <float in [0.01,1.00]>,
      "morpheme_chain": "<e.g. mal-o>",
      "parse": {"prefixes": [...], "root": "<...>", "infixes": [...], "suffix": "<...>"},
      "rationale": "<why this morpheme captures this feature>",
      "not_covered": "<what this term does NOT cover for this feature>"
    }
  ]
}

If you CANNOT encode it with confidence >= 0.50:
{
  "status": "uncovered",
  "uncovered_reason": "<what semantic content cannot be expressed>",
  "missing_morpheme_category": "<which morpheme category is missing>",
  "could_a_free_root_help": true | false
}

Be precise about confidence. Overconfident encodings that fail
causal validation are more harmful than honest "uncovered" responses.
```

### B.3 Causal-prediction-agent system prompt

```
You are predicting the effect of amplifying a SAE feature on LLM output.

Given a MorphoRepr expression for a feature, you must predict which
of the following output properties will measurably change when this
feature is amplified on neutral probe sentences.

ROBUST PROPERTIES (primary; report these first):
- negation_presence: change in negation markers
- past_tense: change in past-tense verb forms
- future_tense: change in future-tense verb forms
- conditional_modality: change in conditional constructions
- code_presence: change in code tokens or technical symbols

SEMI-ROBUST PROPERTIES (secondary):
- negative_valence: change in negative sentiment words
- positive_valence: change in positive sentiment words

FRAGILE PROPERTIES (report but flag as lower-confidence):
- agent_reference: change in explicit agent noun phrases
- social_reference: change in interpersonal or role references
- spatial_reference: change in spatial or directional terms
- iterative_structure: change in repetitive or list-like patterns

For each property, state:
  1. Predicted direction: INCREASE / DECREASE / NO_CHANGE
  2. Confidence: [0.0, 1.0]
  3. For fragile properties, add: FRAGILE

Base your prediction ONLY on the MorphoRepr expression provided.
Do not use the natural language description of the feature.

Format your response as a JSON object with property names as keys
and objects {"direction": "INCREASE"|"DECREASE"|"NO_CHANGE",
"confidence": float, "tier": "robust"|"semi-robust"|"fragile"}
as values.
```

*Note: for each baseline (NL label, Semantic Regex, keyword tag), a parallel prediction prompt uses exactly the same output format and the same set of properties, replacing the MorphoRepr expression with the baseline annotation. These prompts are engineered with equal care and frozen before the run (Section 4.2).*

---

## Appendix C: Changes from version 0.26

This version incorporates a consolidated critical review. Main changes:

**Conceptual — two mechanisms of composition (Section 3.1, new).** An explicit principle now distinguishes *additive* composition between terms (analogue of linear superposition, theoretically grounded) from intra-word *agglutinative* concatenation (distinctive but without counterpart in SAE activation algebra, presented as an ergonomic bet to validate by ablation).

**Coefficients — explicit confidence/activation distinction (Section 3.2, renamed).** Coefficients are now denoted `γ` (annotation confidence, mode used by the protocol) and `α` (normalized activation, instance mode). The section specifies that examples in Section 3.4 are `γ`, and that Phase 4 will allow comparison of the two modes.

**Morpheme inventory completed (Section 3.3).** Added infix `-it-` (past passive participle) and tense suffix `-u` (volitive), absent from v0.26 tables but present in the grammar. Added `mal`/`ne` to the domain-root table with a note on their dual prefix/root role and positional disambiguation rule.

**Expression scope clarified (Section 3.4, new note).** An expression annotates either a single latent (terms = facets) or a small cluster of latents; in Phase 4 the contract is “one steered latent, confidence coefficients over its facets.”

**Section 3.5 (MDE/MOF analogy) reduced.** Reduced to an explicitly optional two-sentence note.

**Causal validity hardened (Section 4.2).** (a) primary validation on an **open-weight proxy model** by default, moved up from the protocol; (b) head-to-head comparison **on a shared feature set**; (c) **feature-normalized steering magnitude** (multiple of `p99`) as primary; (d) **exclusion of OOD instances** from the primary metric; (e) **symmetric baseline predictors** frozen before the run; (f) **intervention controls** added (random feature same layer, random direction same norm, comparable frequency, negative steering, prompt-only, DiffMean/ReFT); (g) steering targets the feature’s **own layer**; (h) splits are **disjoint** and clustering uses a **fixed seed**.

**Causal score and statistics (Sections 4.2, 4.5).** Primary score = **macro-F1** over {increase, decrease, no_change} (robust properties), per feature then averaged, with explicit rule for prediction failures and `no_change`. Go/no-go criterion reformulated as a **paired difference** whose 95% CI excludes 0 (replacing non-overlap of marginal CIs). Stratified bootstrap (10,000, fixed seed); multiple-comparison correction (Holm-Bonferroni primary, Benjamini-Hochberg exploratory); indicative power analysis.

**Ablation study (Section 4.7, new).** Ablation isolates the contribution of agglutination/order (decisive “bag of morphemes” condition), addressing the conceptual tension in Section 3.1.

**Classifiers (Section 4.2).** Negation lexicon pruned of ambiguous prefixes; valence classifier uses the full label distribution; confusion matrices reported.

**Claims-vs-evidence table (Section 1.2, new).** Aligns each claim with its status and planned evidence.

**Reproducibility — terminology (Section 4.4).** The run is described as **“frozen and auditable”** rather than “deterministic”: code/config/prompts/corpus/lexicon are fixed and hash-verified, but LLM outputs are stochastic (necessary for the two consistency runs) and archived.

**Literature and baselines (Sections 1, 2.1, 2.2, 2.5, 6).** Added the controlled-language tradition (Kuhn, 2014); situated fidelity in *detection scoring*; foregrounded Semantic Regexes as a strong public-code, user-validated baseline; nuanced SAE limitations (feature hedging — Chanin et al., 2025; multidimensional features — Engels et al., 2024); new Section 2.5 (SAGE — Han et al., 2025; NLA — Anthropic, 2026; AxBench — Wu et al., 2025; response by Jørgensen & Hansen, 2026); Activation Addition (Turner et al., 2023); reduced CLS mention to a prospective role.

**Citations (References).** Corrected the LRH-geometry reference: actual authors **Park, K., Choe, Y. J., & Veitch, V. (2023)** (v0.26 listed an erroneous author set). Reconciled arXiv:2502.20344 under its verified title **“LinguaLens”**, with author list marked as to be confirmed. Added the verified references listed above.

**Appendices A and B.** Appendix A: note aligning canonical coefficient form and parser behavior, and rule 8 for `mal`/`ne` disambiguation with implementation note (hyphen segmentation). Appendix B: explicit JSON output schemas for labeling and encoding prompts (B.1, B.2), and note on symmetric prediction prompts for baselines.

**Conclusion sentence.** Reformulated: MorphoRepr is evaluated “against already published and validated structured baselines.”

---

*Version 0.27 — June 2026*  
*Michaël Launay — michaellaunay@logikascium.com*  
*Logikascium EURL — https://www.logikascium.com*  
*GitHub: https://github.com/michaellaunay/morphorepr*
