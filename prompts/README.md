# Prompts

Frozen prompt files referenced by `configs/run_v1.yaml` (hashed by `register_prompts()`
at run initialization — Rule 3: prompts are pinned and verified by hash).

Materialized at the **v6.10.0 cleanup** from the frozen v6.9.0 procedure (the only two
prompts embedded verbatim there):

- `predictor_nl_labels_v1.txt` — baseline causal predictor, natural-language labels (Option B, v6.8.0)
- `predictor_semantic_regex_v1.txt` — baseline causal predictor, Semantic Regexes (Option B, v6.8.0)

Still to materialize (orchestrator milestone, v6.10.0 step 2):

- `label_agent_v1.txt`, `encoder_agent_v1.txt`, `predictor_agent_v1.txt` — templates in
  paper v0.30, Annex B.1 / B.2 / B.3 (the paper is the spec source for these three);
- `fidelity_judge_v1.txt`, `causal_judge_v1.txt` — to be authored (the causal judge is
  secondary/qualitative only; the primary metric uses no LLM judge — Rule 8).
