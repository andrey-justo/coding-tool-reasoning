# Project Timeline

**Title**: Supervisor Agent for LLM-Assisted Legacy Software Modernization  
**Total estimated duration**: 26 months  
**Start date**: To be confirmed with supervisor  

Related documents:
- DSR design cycles: [`docs/risks/design-science-framing.md`](risks/design-science-framing.md)
- RQ falsifiability and null hypotheses: [`docs/risks/rq-scope-falsifiability.md`](risks/rq-scope-falsifiability.md)
- Experiment procedures: [`docs/experiments/experiment-design.md`](experiments/experiment-design.md)
- Requirements specification (Volere): [`docs/requirements/requirements.md`](requirements/requirements.md)
- Requirements implementation roadmap: [`docs/requirements/roadmap.md`](requirements/roadmap.md)

---

## Phase Overview

The schedule is organized around two delivery horizons:

- **Qualification horizon**: first 2 months, focused on defensible scope,
  methodology, and a small but credible pilot.
- **Thesis horizon**: the following 24 months, focused on implementation,
  full experiments, analysis, writing, and final defense.

| Phase | DSR Cycle | Milestone | Duration | Cumulative |
|---|---|---|---|---|
| 1 | Relevance | Qualification framing: problem statement, novelty delta, scope, RQs, and metrics baseline | 2 months | Qualification |
| 2 | Design | Prototype hardening; metric pipeline completion; baseline implementation; reproducibility scaffolding | 6 months | M8 |
| 3 | Design | Empirical data collection; prompt-variation corpus construction; local strategy bundle rollout | 6 months | M14 |
| 4 | Rigor | Statistical analysis (RQ1â€“RQ4); Îº-based annotation validation; developer trust/control survey | 6 months | M20 |
| 5 | Rigor | Thesis writing; revisions; replication package; pre-defense and final defense | 6 months | M26 |

---

## Phase 1 â€” Qualification Cycle (Months 1â€“2)

**DSR cycle**: Cycle 1 â€“ Relevance  
**Goal**: Produce a qualification-ready research core with a defensible problem,
falsifiable hypotheses, a narrow scope, and a small pilot showing feasibility.

### Tasks
- [ ] Finalize Volere-style requirements specification and priorities (Must/Should/Could) and agree the implementation roadmap with supervisor.
- [ ] Integrate completed SLR into Related Work: identify closest prior art, state the precise delta, and tighten novelty wording accordingly.
- [ ] Validate novelty statement against SWE-bench, SWE-agent, Plan4Code, OpenHands literature and align claims with the SLR evidence.
- [ ] Define **testability as the baseline NFR** for legacy refactoring evaluation: specify a per-repo testability gate (build succeeds; unit tests run; no decrease in pass rate; add tests for behavioral changes) and a testability DV (tests-added count, pass/fail, optional coverage delta).
- [ ] Freeze the initial metric framing around **structural improvement delta** and document the local-first strategy bundle approach.
- [ ] Finalize RQ phrasing and hypotheses â€” choose between basic and complex RQ forms per [`docs/risks/rq-scope-falsifiability.md`](risks/rq-scope-falsifiability.md).
- [ ] Select empirical corpus: 5 open-source repositories (mix of legacy and actively maintained; public license; GitHub issue tracker).
- [ ] Plan human-data activities: (a) annotation protocol for verdict/pattern labels with Îº target; (b) tool-use survey instrument for perceived trust/control.
- [ ] Conduct initial developer interviews or survey to confirm NFR misalignment is a real practitioner pain point (validates DSR G2).
- [ ] Write Problem Statement and Corpus Description sections.

### Deliverables
- Requirements baseline: Volere spec + roadmap (requirements frozen for Phase 2).
- SLR report confirming novelty gap.
- Qualification-ready methodology narrative and novelty delta.
- Corpus list with repository rationale.
- Finalized RQs with null hypotheses signed off by supervisor.
- Pilot plan and validation criteria for the post-qualification implementation phase.

---

## Phase 2 â€” Design Cycle: Prototype Hardening (Months 3â€“8)

**DSR cycle**: Cycle 2 â€“ Design (Buildâ€“Evaluate loop)  
**Goal**: Resolve implementation gaps blocking reproducible experiments and
close the prototype-level evidence needed to start the main study.

### Tasks
- [ ] Add `temperature` and `seed` parameters to all execution paths that generate code or judgments.
- [ ] Wire `_run_supervised_trial` and `_run_baseline_trial` in `src/evaluation/reproducibility_experiment.py`.
- [ ] Implement the zero-shot baseline condition (`IntentPlanner` with `nfr_focus=[]`, `relationship_depth=0`).
- [ ] Implement **execution trace capture** and provenance logging: per execution record repo, revisions/commits, user approval, and prompts (external + internal) to support audit/replay.
- [ ] Integrate static analysis for the primary DV using **language-specific local strategy bundles** with pinned rulesets.
- [ ] Add collection of additional quality metrics where available (cyclomatic complexity, test coverage, duplication, conventions, security) and record provenance when fetched from external systems.
- [ ] Implement **testability gate + logging** in the evaluation harness (build/test execution status, tests-added count, optional coverage delta) and make it a prerequisite for interpreting other DVs.
- [ ] Write prompt-variation robustness experiment over repository/issue-anchored software engineering tasks.
- [ ] Add unit tests for `IntentPlanner` and `ExplanationService` with mock `MultiModelLLMClient`.
- [ ] Remove or implement `src/migration/analyzer.py` stub.
- [ ] Run end-to-end pilot (10 issues) to validate: determinism controls, structural metric collection, and testability gate.
- [ ] Run Îº pilot on 10 labelled items (â‰¥ 3 senior engineers) to validate label rubric feasibility.

### Deliverables
- All High-priority implementation gaps from `PROPOSAL.md â†’ # WIP` resolved
- Passing CI test suite with assertions (F1 â‰¥ 0.3 guard + unit tests)
- RQ1 pilot report confirming measurement pipeline works
- Execution trace schema + sample run artifacts (auditable replay)

---

## Phase 3 â€” Design Cycle: Data Collection (Months 9â€“14)

**DSR cycle**: Cycle 2 â€“ Design (continued)  
**Goal**: Collect the full empirical dataset for RQ1â€“RQ4a.

### Tasks
- [ ] Execute the **practical v1 run budget** from [`docs/experiments/experiment-design.md`](experiments/experiment-design.md): 3 sets minimum (up to 5), each set with 10 paired supervised vs. baseline runs.
- [ ] Run full RQ1 experiment (paired): 3â€“5 sets Ã— 10 issue pairs = 30â€“50 paired observations.
- [ ] Run full RQ2 experiment (paired): reuse the same 3â€“5 sets Ã— 10 issue pairs = 30â€“50 paired observations.
- [ ] Construct prompt-variation corpus for RQ3: 3â€“5 task sets Ã— 10 anchored tasks Ã— 10 paraphrases per task.
- [ ] Run full RQ3 experiment (paraphrase robustness over anchored tasks): 30â€“50 supervised + 30â€“50 baseline task-level observations.
- [ ] Run RQ4 legacy paired experiment: 3â€“5 legacy sets Ã— 10 paired runs = 30â€“50 pairs.
- [ ] Run RQ4a configuration experiment on the same sets: compare `strictness=0.2` vs `strictness=0.8` with 3â€“5 sets Ã— 10 paired runs = 30â€“50 pairs.
- [ ] Store all raw results in versioned JSON files under `data/experiments/`.
- [ ] Capture and store metric provenance for static analysis and any enriched metrics (ruleset/version, scope, timestamps).

### Deliverables
- Raw experiment data (versioned, anonymized) for RQ1, RQ2, RQ3, RQ4, and RQ4a using the 3â€“5 set protocol
- Data quality report (missing values, outliers, LLM failures)

---

## Phase 4 â€” Rigor Cycle: Analysis & Survey (Months 15â€“20)

**DSR cycle**: Cycle 3 â€“ Rigor  
**Goal**: Produce statistical evidence for or against each null hypothesis.

### Tasks
- [ ] Run Wilcoxon signed-rank (paired) for RQ1 and RQ2 on pooled 30â€“50 paired observations; report per-set medians (TBD).
- [ ] Run McNemar's test on paraphrase-level verdict agreement for RQ3 and report consistency-ratio gaps.
- [ ] Run RQ4 tests as specified in [`docs/experiments/experiment-design.md`](experiments/experiment-design.md): Wilcoxon signed-rank on the legacy-only subset and report effect size for structural improvement.
- [ ] Apply multiple-comparison correction where applicable across metrics.
- [ ] Run Îº-based annotation validation:
  - (a) validate `overall_verdict` label agreement on a sampled set of outputs
  - (b) validate pattern adoption labels (Strangler Fig / ACL) when applicable
- [ ] Design and run tool-use survey instrument (trust/control/usability): define tasks, Likert items, and analysis plan.
- [ ] Obtain ethics/IRB approval if required for the survey/annotation activities.
- [ ] Recruit participants and execute annotation + survey; report Îº and descriptive stats.
- [ ] Write statistical analysis and results sections.

### Deliverables
- Statistical results report (p-values, effect sizes, confidence intervals)
- RQ4b survey data (anonymized)
- Draft Results and Discussion sections

---

## Phase 5 â€” Rigor Cycle: Writing & Submission (Months 21â€“26)

**DSR cycle**: Cycle 3 â€“ Rigor (continued)  
**Goal**: Produce a publishable paper and thesis chapter.

### Tasks
- [ ] Write Introduction (incorporating novelty statement from [`docs/risks/design-science-framing.md`](risks/design-science-framing.md)).
- [ ] Write Related Work (positioned against SWE-bench, SWE-agent, Plan4Code, ISO 25010).
- [ ] Write DSR Methodology section (seven guidelines mapped to the project).
- [ ] Write Threats to Validity section.
- [ ] Internal review with supervisor; address feedback.
- [ ] Select target venue (e.g., ICSE, FSE, TOSEM, EMSE) and format accordingly.
- [ ] Prepare qualification-to-defense continuity notes so the post-qualification work remains aligned with the approved scope.
- [ ] Submit.

### Deliverables
- Camera-ready paper draft
- Submitted paper

---

## Current Status (July 2026)

| Area | Status | Blocker |
|---|---|---|
| Prototype (Stage 1 + Stage 2 MCP tools) | âœ… Implemented | â€” |
| Configuration (`swe_mcp_config.yaml`) | âœ… Implemented | â€” |
| knowledge base CSVs (clean code, legacy, security) | âœ… Implemented | ISO 25010 column missing |
| `overall_verdict` type safety | âœ… Fixed (`Literal`) | â€” |
| Test assertions | âœ… Added (F1 â‰¥ 0.3) | â€” |
| `reproducibility_experiment.py` scaffold | âœ… Created | Trial methods not wired (Phase 2) |
| CodeBERT scorer | âœ… Available in evaluator | End-to-end experiment integration still pending |
| `temperature=0` / `seed` in LLM calls | âš ï¸ Partially implemented | Support exists in clients/tools, but not enforced everywhere |
| Baseline (no-knowledge base) condition | âŒ Not implemented | Blocks RQ1, RQ2 |
| Prompt-variation experiment | âŒ Not created | Phase 2â€“3 task |
| Unit tests (IntentPlanner, ExplanationService) | âŒ Not written | Phase 2 task |
| SLR / novelty validation | âœ… Done | Integrate findings into Related Work + tighten novelty delta |
| Testability baseline (gate + DV) | âŒ Not defined/implemented | Phase 1â€“2 task |
| Îº-based annotation pilot (verdict/pattern labels) | âŒ Not run | Phase 2 task |
| ISO 25010 column in knowledge base CSVs | âŒ Not added | Phase 1 task |
| Requirements spec (Volere) + roadmap | âœ… Implemented | â€” |
| Execution trace capture (repo/commit/prompts/approval) | âŒ Not implemented | Blocks auditability/traceability requirements |
| Static analysis integration (local strategy bundles) | âŒ Not implemented | Blocks primary DV collection |
| Expanded metric collection (coverage/duplication/security etc.) | âš ï¸ Partial | Core evaluator exists; enrichment still incomplete |
| Skill/tool export for other runtimes | âŒ Not implemented | Follow-up integration task |

