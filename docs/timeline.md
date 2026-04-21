# Project Timeline

**Title**: Supervisor Agent for LLM-Assisted Legacy Software Modernization  
**Total estimated duration**: 14 months  
**Start date**: To be confirmed with supervisor  

Related documents:
- DSR design cycles: [`docs/risks/design-science-framing.md`](risks/design-science-framing.md)
- RQ falsifiability and null hypotheses: [`docs/risks/rq-scope-falsifiability.md`](risks/rq-scope-falsifiability.md)
- Experiment procedures: [`docs/experiments/experiment-design.md`](experiments/experiment-design.md)
- Requirements specification (Volere): [`docs/requirements/requirements.md`](requirements/requirements.md)
- Requirements implementation roadmap: [`docs/requirements/roadmap.md`](requirements/roadmap.md)

---

## Phase Overview

| Phase | DSR Cycle | Milestone | Duration | Cumulative |
|---|---|---|---|---|
| 1 | Relevance | Literature review; ISO 25010 taxonomy mapping; RQ operationalization | 3 months | M3 |
| 2 | Design | Prototype hardening; CodeBERT scorer; reproducible LLM calls; baseline implementation | 2 months | M5 |
| 3 | Design | Empirical data collection; prompt-variation corpus construction | 3 months | M8 |
| 4 | Rigor | Statistical analysis (RQ1–RQ4); κ-based annotation validation; developer trust/control survey | 3 months | M11 |
| 5 | Rigor | Paper writing; internal review; conference submission | 3 months | M14 |

---

## Phase 1 — Relevance Cycle (Months 1–3)

**DSR cycle**: Cycle 1 – Relevance  
**Goal**: Validate the problem and establish the research foundation.

### Tasks
- [ ] Finalize Volere-style requirements specification and priorities (Must/Should/Could) and agree the implementation roadmap with supervisor.
- [ ] Integrate completed SLR into Related Work: identify closest prior art, state the precise delta, and tighten novelty wording accordingly.
- [ ] Validate novelty statement against SWE-bench, SWE-agent, Plan4Code, OpenHands literature and align claims with the SLR evidence.
- [ ] Define **testability as the baseline NFR** for legacy refactoring evaluation: specify a per-repo testability gate (build succeeds; unit tests run; no decrease in pass rate; add tests for behavioral changes) and a testability DV (tests-added count, pass/fail, optional coverage delta).
- [ ] Map ISO 25010 sub-characteristics to existing taxonomy nodes; add `ISO25010Characteristic` column to all taxonomy CSVs (`clean_code_nfr_nodes.csv`, `legacy_code_nodes.csv`, `security_nfr_nodes.csv`).
- [ ] Finalize RQ phrasing — choose between basic and complex RQ forms per [`docs/risks/rq-scope-falsifiability.md`](risks/rq-scope-falsifiability.md).
- [ ] Select empirical corpus: 5 open-source repositories (mix of legacy and actively maintained; public license; GitHub issue tracker).
- [ ] Plan human-data activities: (a) annotation protocol for verdict/pattern labels with κ target; (b) tool-use survey instrument for perceived trust/control.
- [ ] Conduct initial developer interviews or survey to confirm NFR misalignment is a real practitioner pain point (validates DSR G2).
- [ ] Write Problem Statement and Corpus Description sections.

### Deliverables
- Requirements baseline: Volere spec + roadmap (requirements frozen for Phase 2).
- SLR report confirming novelty gap
- `ISO25010Characteristic` column added to all taxonomy CSVs
- Corpus list with repository rationale
- Finalized RQs with null hypotheses signed off by supervisor

---

## Phase 2 — Design Cycle: Prototype Hardening (Months 4–5)

**DSR cycle**: Cycle 2 – Design (Build–Evaluate loop)  
**Goal**: Resolve all implementation gaps blocking reproducible experiments.

### Tasks
- [ ] Add `temperature` and `seed` parameters to `LocalAIClient.chat()`.
- [ ] Replace `bert-base-uncased` with `microsoft/codebert-base` in `ReliabilityEvaluationTool`.
- [ ] Wire `_run_supervised_trial` and `_run_baseline_trial` in `src/evaluation/reproducibility_experiment.py`.
- [ ] Implement the zero-shot baseline condition (`IntentPlanner` with `nfr_focus=[]`, `relationship_depth=0`).
- [ ] Implement **execution trace capture** and provenance logging: per execution record repo, revisions/commits, user approval, and prompts (external + internal) to support audit/replay.
- [ ] Integrate static analysis for the primary DV using **SonarQube and/or Roslyn analyzers** with pinned rulesets.
- [ ] Add collection of additional quality metrics where available (cyclomatic complexity, test coverage, duplication, conventions, security) and record provenance when fetched from external systems.
- [ ] Implement **testability gate + logging** in the evaluation harness (build/test execution status, tests-added count, optional coverage delta) and make it a prerequisite for interpreting other DVs.
- [ ] Write prompt-variation robustness experiment (RQ3 counterpart to `reproducibility_experiment.py`).
- [ ] Add unit tests for `IntentPlanner` and `ExplanationService` with mock `MultiModelLLMClient`.
- [ ] Remove or implement `src/migration/analyzer.py` stub.
- [ ] Run end-to-end pilot (10 issues) to validate: determinism controls, SOLID metric collection, and testability gate.
- [ ] Run κ pilot on 10 labelled items (≥ 3 senior engineers) to validate label rubric feasibility.

### Deliverables
- All High-priority implementation gaps from `PROPOSAL.md → # WIP` resolved
- Passing CI test suite with assertions (F1 ≥ 0.3 guard + unit tests)
- RQ1 pilot report confirming measurement pipeline works
- Execution trace schema + sample run artifacts (auditable replay)

---

## Phase 3 — Design Cycle: Data Collection (Months 6–8)

**DSR cycle**: Cycle 2 – Design (continued)  
**Goal**: Collect the full empirical dataset for RQ1–RQ4a.

### Tasks
- [ ] Execute the **practical v1 run budget** from [`docs/experiments/experiment-design.md`](experiments/experiment-design.md): 3 sets minimum (up to 5), each set with 10 paired supervised vs. baseline runs.
- [ ] Run full RQ1 experiment (paired): 3–5 sets × 10 issue pairs = 30–50 paired observations.
- [ ] Run full RQ2 experiment (paired): reuse the same 3–5 sets × 10 issue pairs = 30–50 paired observations.
- [ ] Run full RQ3a experiment (repeated-trial robustness): 3–5 sets × 10 repeated trials per condition = 30–50 runs per condition.
- [ ] Construct prompt-variation corpus for RQ3b: 3–5 intents (one per set) × 10 paraphrases = 30–50 prompts.
- [ ] Run full RQ3b experiment (paraphrase robustness): 30–50 supervised + 30–50 baseline runs.
- [ ] Run RQ4 legacy paired experiment: 3–5 legacy sets × 10 paired runs = 30–50 pairs.
- [ ] Run RQ4a configuration experiment on the same sets: compare `strictness=0.2` vs `strictness=0.8` with 3–5 sets × 10 paired runs = 30–50 pairs.
- [ ] Store all raw results in versioned JSON files under `data/experiments/`.
- [ ] Capture and store metric provenance for static analysis and any enriched metrics (ruleset/version, scope, timestamps).

### Deliverables
- Raw experiment data (versioned, anonymized) for RQ1, RQ2, RQ3a, RQ3b, RQ4, and RQ4a using the 3–5 set protocol
- Data quality report (missing values, outliers, LLM failures)

---

## Phase 4 — Rigor Cycle: Analysis & Survey (Months 9–11)

**DSR cycle**: Cycle 3 – Rigor  
**Goal**: Produce statistical evidence for or against each null hypothesis.

### Tasks
- [ ] Run Wilcoxon signed-rank (paired) for RQ1 and RQ2 on pooled 30–50 paired observations; report per-set medians.
- [ ] Run RQ3a robustness analysis using paired variance comparisons across sets (as defined in [`docs/experiments/experiment-design.md`](experiments/experiment-design.md)).
- [ ] Run McNemar's test on paraphrase-level verdict agreement for RQ3b and report consistency-ratio gaps.
- [ ] Run RQ4 tests as specified in [`docs/experiments/experiment-design.md`](experiments/experiment-design.md): Fisher's exact test for pattern adoption rate + Wilcoxon (paired) for violation delta.
- [ ] Apply multiple-comparison correction where applicable across metrics.
- [ ] Run κ-based annotation validation:
  - (a) validate `overall_verdict` label agreement on a sampled set of outputs
  - (b) validate pattern adoption labels (Strangler Fig / ACL) when applicable
- [ ] Design and run tool-use survey instrument (trust/control/usability): define tasks, Likert items, and analysis plan.
- [ ] Obtain ethics/IRB approval if required for the survey/annotation activities.
- [ ] Recruit participants and execute annotation + survey; report κ and descriptive stats.
- [ ] Write statistical analysis and results sections.

### Deliverables
- Statistical results report (p-values, effect sizes, confidence intervals)
- RQ4b survey data (anonymized)
- Draft Results and Discussion sections

---

## Phase 5 — Rigor Cycle: Writing & Submission (Months 12–14)

**DSR cycle**: Cycle 3 – Rigor (continued)  
**Goal**: Produce a publishable paper and thesis chapter.

### Tasks
- [ ] Write Introduction (incorporating novelty statement from [`docs/risks/design-science-framing.md`](risks/design-science-framing.md)).
- [ ] Write Related Work (positioned against SWE-bench, SWE-agent, Plan4Code, ISO 25010).
- [ ] Write DSR Methodology section (seven guidelines mapped to the project).
- [ ] Write Threats to Validity section.
- [ ] Internal review with supervisor; address feedback.
- [ ] Select target venue (e.g., ICSE, FSE, TOSEM, EMSE) and format accordingly.
- [ ] Submit.

### Deliverables
- Camera-ready paper draft
- Submitted paper

---

## Current Status (April 2026)

| Area | Status | Blocker |
|---|---|---|
| Prototype (Stage 1 + Stage 2 MCP tools) | ✅ Implemented | — |
| Configuration (`swe_mcp_config.yaml`) | ✅ Implemented | — |
| Taxonomy CSVs (clean code, legacy, security) | ✅ Implemented | ISO 25010 column missing |
| `overall_verdict` type safety | ✅ Fixed (`Literal`) | — |
| Test assertions | ✅ Added (F1 ≥ 0.3) | — |
| `reproducibility_experiment.py` scaffold | ✅ Created | Trial methods not wired (Phase 2) |
| CodeBERT scorer | ❌ Not replaced | Phase 2 task |
| `temperature=0` / `seed` in LLM calls | ❌ Not implemented | Blocks RQ2, RQ3 |
| Baseline (no-taxonomy) condition | ❌ Not implemented | Blocks RQ1, RQ2 |
| Prompt-variation experiment | ❌ Not created | Phase 2–3 task |
| Unit tests (IntentPlanner, ExplanationService) | ❌ Not written | Phase 2 task |
| SLR / novelty validation | ✅ Done | Integrate findings into Related Work + tighten novelty delta |
| Testability baseline (gate + DV) | ❌ Not defined/implemented | Phase 1–2 task |
| κ-based annotation pilot (verdict/pattern labels) | ❌ Not run | Phase 2 task |
| ISO 25010 column in taxonomy CSVs | ❌ Not added | Phase 1 task |
| Requirements spec (Volere) + roadmap | ✅ Implemented | — |
| Execution trace capture (repo/commit/prompts/approval) | ❌ Not implemented | Blocks auditability/traceability requirements |
| Static analysis integration (SonarQube/Roslyn) | ❌ Not implemented | Blocks primary DV collection |
| Expanded metric collection (coverage/duplication/security etc.) | ❌ Not implemented | Optional enrichment (Phase 2–3) |
| Skill/tool export for other runtimes | ❌ Not implemented | Follow-up integration task |
