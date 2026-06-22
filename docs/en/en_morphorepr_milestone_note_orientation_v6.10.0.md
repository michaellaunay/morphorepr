# MorphoRepr — Milestone Note: v6.9.0 → v6.10.0 Orientation

**Status: orientation accepted (architecture decision).** This note is not a delivered version: it freezes *the decision* and *the plan* for the next work package. The code, configs, and tests described here remain to be produced in v6.10.0.

**Scope.** Decide the *source of truth for the code* and prepare the **Phase 4 end-to-end orchestrator** (reproducible dev run, without a full run). No scientific claim from the paper (v0.29) is affected; procedure v6.9.0 remains frozen as the reference.

Companion document to `morphorepr_test_procedure_v6.9.0.md`. It comes from the synthesis of three cross-reviews (two external and one internal), all of which converged.

---

## 1. Decision

Starting with **v6.10.0**, the **Python repository becomes the source of truth for the code** (option **B**). Markdown remains, but it stops being the single artifact: it carries the **scientific specification, methodological rules, ADRs, and changelog**. Executable code, tests, configs, prompts, and SQL now live in real versioned files.

```text
Markdown   = scientific protocol, rules, decisions (ADR), changelog, allowed/disallowed claims
Repository = canonical code (.py), pytest tests, YAML configs, prompts, db/schema.sql, data/probes/
```

We **do not adopt** DOCX/PDF: that would be worse for reproducibility, Git diffs, tests, and auditability. The right form for a reproducible scientific protocol remains **Markdown + versioned code/config files**.

Option **C** (canonical MD + committed extractor `make build && make test`) was considered as a temporary bridge. It is rejected as a durable form: it keeps code editing *inside prose* (therefore keeping the corruption risk) and adds another tooling layer to maintain.

---

## 2. Why change now

The trigger is not aesthetic: the next work package is **execution-centered**. Its acceptance criterion is no longer “it is well specified,” but “it really chains end-to-end.” Three concrete signals:

1. **The test cannot import code that remains in prose.** A `tests/test_pipeline_phase4_e2e.py` does `from agents import steerer`, `import orchestrator`. As long as these modules exist only as text in the v6.9.0 MD, `pytest` cannot import anything. The target *docs-as-code* form therefore presupposes materializing the embedded code — this is the point of no return.
2. **Two fence corruptions in a single session** (`CREATE TABLE api_usage` header swallowed; closing fence for `causal_scorer` swallowed, taking the `## 8 bis` title with it). This is a typical symptom of editing code *inside* a ~7,700-line document via string replacement. In real `.py` files, these two bugs do not exist.
3. **The extraction tax** has become infrastructure in its own right, unversioned, and growing at every session: extracting blocks by marker, stubbing `anthropic` / `transformer_lens` / `sae_lens`, loading modules via `exec`, replaying tests with a fake `monkeypatch` / `conftest`. In a real repository, the **69 existing tests run under native `pytest`** without a homemade harness.

---

## 3. Migration order (mandatory)

The target structure (ADR + `dev_phase4.yaml` + tests + orchestrator) cannot be put in place before the modules actually exist. The proper order is therefore:

```text
1. Materialize the canonical repository from v6.9.0 (mechanical extraction by marker)
2. Add conftest.py + test_db / monkeypatch fixtures → make the 69 tests pass under native pytest
3. Fix the orchestrator phase order (see §4)
4. Add ADR-001 + configs/dev_phase4.yaml (+ minimal variant)
5. Implement the Phase 4 end-to-end orchestrator + tests (fakes + real opt-in)
```

Building the orchestrator **before** step 1 would mean continuing to build on code embedded in an MD — exactly what we want to stop doing.

### Target tree (already described by the README)

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
docs/              morphorepr_test_procedure_v6.9.0.md (frozen reference),
                   morphorepr_test_procedure_v6.10.0.md (short orchestrator section),
                   adr/ADR-001-phase4-orchestrator.md
orchestrator.py
```

---

## 4. Corrected Phase 4 sequence (the most important correction)

The v6.9.0 orchestrator currently lists the phases in this order:

```text
p4_steer → p4_controls → p4_predict → p4_predict_baselines → p4_score → p4_qualitative → p5_report
```

This is **harmless while everything is disabled** (each phase self-guards and performs a no-op), but **wrong for a dev run where all flags are enabled**: `p4_controls` is placed **before** `p4_predict` and `p4_score`. However:

- `causal_scorer._load_pairs()` (primary) needs outputs from the **MorphoRepr predictor** (`p4_predict`);
- `run_intervention_controls()` / `assert_intervention_controls_ready()` depend on both **MorphoRepr predictions** and **primary steering**, and control scoring compares against the primary score.

Without `p4_predict` upstream, both the primary score **and** the controls fail. (An earlier proposed sequence omitted `p4_predict` altogether; this is the error corrected in the synthesis.)

**Correct dev sequence (v6.10.0 target):**

```text
p4_steer
→ p4_predict            (MorphoRepr prediction — REQUIRED before scoring and controls)
→ p4_predict_baselines  (nl_labels, semantic_regex — Option B)
→ p4_score              (primary macro-F1 + paired baseline comparisons)
→ p4_controls           (intervention controls + score_intervention_controls, LAST)
→ p4_dev_summary        (dev summary — NEW phase; produces NO full/pilot claim)
```

The v6.10.0 work therefore includes an **ordering fix** in the `PHASES` list (move `p4_controls` after `p4_score`) and the addition of `p4_dev_summary`. `p4_qualitative` (LLM judge, secondary) and `p5_report` remain unchanged.

---

## 5. `configs/dev_phase4.yaml` — requirements

The Phase 4 end-to-end dev run is driven by a **dedicated config** (the only supported one for this test), derived from `run_v1.yaml` with the guards explicitly enabled. Beyond the skeleton, two additions are required (caught during review):

- `proxy_model.enabled: true` — explicit, because `steer_feature()` / `_get_sae()` depend on the open-weight proxy path (this is already the default, but a dev-run config must make it visible);
- the statistical **comparison targets**, which live under `stats`, **not** under `causal_scoring`.

```yaml
run_mode: "dev"

proxy_model:
  enabled: true            # required by steer_feature / _get_sae (open-weight proxy path)

steering:
  run_in_pipeline: true

baseline_predictions:
  enabled: true
  methods: [nl_labels, semantic_regex]

causal_scoring:
  run_in_pipeline: true
  run_baseline_comparisons: true
  strict_baselines: true

stats:                      # paired-comparison targets (read by causal_scorer.run)
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

`configs/dev_phase4_minimal.yaml`: same idea, but with reduced volume (minimal subsample, restricted `controls_to_run`, possibly `run_baseline_comparisons` off) — for fast CI wiring.

**Key-consistency note** (verified against v6.9.0 code): `steering.run_in_pipeline`, `baseline_predictions.enabled` / `methods`, `causal_scoring.run_in_pipeline` / `run_baseline_comparisons` / `strict_baselines`, `stats.superiority_vs` / `non_inferiority_vs`, and `intervention_controls.*` all exist exactly as written.

---

## 6. Test strategy (two levels)

A single “real” opt-in test is not enough: in a restricted environment (without `transformer_lens` / `sae_lens`, and with network limited to PyPI/GitHub/npm), the real GPT-2/Pythia + SAE run is **systematically skipped**. We therefore need:

1. **Fakes-backed orchestration test (runs everywhere).** Model, SAE, and provider are monkeypatched. It proves the **wiring**: the corrected sequence (§4) chains without error, each guard activates, and idempotence/resume behavior holds. This is the test that provides immediately provable value.
2. **Real e2e test, opt-in (skipped here).** Explicit guard:

```python
pytestmark = pytest.mark.skipif(
    os.environ.get("MORPHOREPR_RUN_DEV_PHASE4") != "1",
    reason="Phase 4 e2e test is opt-in (real proxy + SAE)",
)
```

**Assertions (names verified against v6.9.0):**

- `steering_results` is non-empty (at the primary magnitude);
- prediction `agent_outputs` are present: `predictor` (MorphoRepr) **and** `predictor_nl_labels` / `predictor_semantic_regex`;
- `metrics` contains `causal_macro_f1_global` (primary);
- `intervention_control_results` is non-empty;
- `metrics` contains `intervention_control_macro_f1:*` (and `intervention_control_paired_diff:*`), `model_run_id` is populated, `phase='p4_controls'`;
- **no** full/pilot scientific claim is produced.

---

## 7. Guardrails (unchanged)

- `run_v1.yaml` keeps Phase 4 **disabled by default**; `dev_phase4.yaml` is the **only** config that enables the end-to-end sequence. **No automatic activation** of the full run.
- Primary metric is **deterministic**, **without an LLM judge**; controls are **secondary metrics only**.
- `diffmean_reft` remains **not implemented** (`NotImplementedError` if enabled).
- `model_run_id`-aware, `split`-aware, `intervention_space`-aware; OOD policy respected.
- **No full causal validation is claimed**; paper claims (v0.29) are unchanged.

---

## 8. What remains frozen

- `morphorepr_test_procedure_v6.9.0.md`: **frozen methodological reference** (spec + changelog through §28). Once the migration is done, it will no longer embed the code; it will *point* to the repository.
- The **scientific claims** and logical schema (17 tables, including `intervention_control_results`) are unchanged.

---

## 9. Next request to formulate

The v6.10.0 work package is therefore **not** “add a section to the Markdown,” but:

> **Materialize the canonical repository from v6.9.0 + `conftest.py` + make the 69 tests pass under native `pytest`; fix the phase order; add `ADR-001` + `configs/dev_phase4.yaml` (+ minimal variant); implement the Phase 4 end-to-end orchestrator with a fakes-backed orchestration test (executable) and a real opt-in e2e test (`MORPHOREPR_RUN_DEV_PHASE4=1`).**

Reference Phase 4 sequence to implement:

```text
p4_steer → p4_predict → p4_predict_baselines → p4_score → p4_controls → p4_dev_summary
```
