# ⑤ AGENTIC BLUEPRINT — Execution contract

The merged prompt is designed to run in a single capable LLM, but its workflow can also be distributed across specialized agents.

| Agent | Responsibility | Output |
|---|---|---|
| Intent Router | Classify input | General / Venture / Hybrid |
| Divergence Engine | Generate 35+ mechanisms | I01–I35+ |
| Novelty Mapper | Track conceptual overlap and lens coverage | Diversity matrix |
| Synthesis Engine | Produce first-order hybrids | H01–H05 |
| Meta-Synthesis Engine | Recombine hybrids | M01–M03 |
| Research Analyst | Check claims and competing concepts | Evidence register |
| Venture Evaluator | Score candidate concepts | Ranked shortlist |
| Execution Architect | Design first experiment | Testable blueprint |
| Validation Controller | Check output completeness | Pass/fail report |

The agents are logical roles, not a claim that independent software agents have been launched.

The corresponding state machine is:

01 INPUT_RECEIVED
02 INTENT_CLASSIFIED
03 IDEAS_GENERATED
04 WILDCARDS_IDENTIFIED
05 HYBRIDS_GENERATED
06 META_HYBRIDS_GENERATED
07 EVIDENCE_REVIEWED
08 CANDIDATES_SCORED
09 EXPERIMENT_DEFINED
10 OUTPUT_VALIDATED

A production implementation should persist concept IDs, parent lineage, input hashes, scoring configurations, and validation results. That enables reproducible comparisons between runs, but identical outputs cannot be guaranteed across nondeterministic language-model executions.
