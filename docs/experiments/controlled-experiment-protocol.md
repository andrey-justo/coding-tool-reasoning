# Controlled Experiment Protocol (Wohlin-Aligned)

This protocol operationalizes the methodology from *Experimentation in Software Engineering* (Wohlin et al.) for this repository's MCP-assisted code-change experiments.

It is designed to be executable with the current artifact structure in `out/experiments` and the current runner in `src/experiments/issue_mcp_experiment.py`.

## 1. Goal and Object of Study

Goal template (GQM style):

- Analyze: MCP-assisted code-change pipeline
- For the purpose of: evaluating effectiveness, robustness, and quality impact
- With respect to: correctness proxies, maintainability proxies, and run reproducibility
- From the viewpoint of: engineering researcher / tool maintainer
- In the context of: repository+issue anchored software maintenance tasks

Primary object of study:

- Experimental unit: one complete run for one issue/repo target (one execution_id)
- Example run artifact family:
  - `out/experiments/openssl-issue-31332-mcp-report-llm-20260703T023927Z-iofmt.json`
  - `out/experiments/openssl-issue-31332-mcp-report-llm-20260703T023927Z-iofmt.csv`
  - `out/experiments/openssl-issue-31332-llm-debug-20260703T023927Z-iofmt/`

## 2. Hypotheses

Use one hypothesis set per research question in the experimental track.

Core set for current pipeline:

- Scope note: RQ1 is an artifact qualification/design question and is not part of this controlled experiment track.

- H0-RQ2: MCP-assisted generation does not improve structural quality relative to baseline prompt-only generation.
- H1-RQ2: MCP-assisted generation improves structural quality relative to baseline prompt-only generation.

- H0-RQ3: Verdict consistency ratio under supervision is less than or equal to baseline prompt-only consistency.
- H1-RQ3: Verdict consistency ratio under supervision is higher than baseline prompt-only consistency.

- H0-RQ4: On legacy-focused tasks, MCP-assisted generation does not reduce harmful complexity/maintainability regressions relative to baseline prompt-only generation.
- H1-RQ4: On legacy-focused tasks, MCP-assisted generation reduces harmful complexity/maintainability regressions relative to baseline prompt-only generation.

Prototype/implementation checks are tracked separately and are not treated as research hypotheses.

## 3. Variables

### 3.1 Independent Variables (Factors)

Core factors to record and vary intentionally:

- Treatment strategy:
  - `baseline_prompt_only`
  - `mcp_supervised`
- Prompt wording variant (RQ3 robustness only):
  - `v1`, `v2`, ..., `v10`
- Supervisor strictness (RQ4a configuration study only):
  - `low`, `medium`, `high`

Engineering ablation factor (non-RQ, optional):

- Formatting normalization in apply stage:
  - `off`
  - `on`

### 3.2 Dependent Variables (Responses)

Core response set (lean protocol):

- Structural improvement delta (primary objective quality metric)
- Cognitive Complexity delta
- Requirements coverage ratio
- Readability proxy delta (Buse-Weimer)
- Code duplication delta
- Code smell count delta (Long Method, Large Class, Duplicate Code, Long Parameter List, Divergent Change, Shotgun Surgery, Data Clumps, Switch Statements, Speculative Generality, Temporary Fields, Message Chains, Middle Man)
- Final verdict (`acceptable`, `revise`, `reject`)
- Build/test status (`pass/fail/not-run`) when available

Extended metrics (Halstead, C&K, hotspot concentration, semantic similarity, and others) are tracked in a future-implementation catalog and are not required for core claims in this protocol.

### 3.3 SWE Pillar Mapping (Why These Metrics)

- Design quality and maintainability (primary): structural improvement delta.
- Structural complexity load: cognitive complexity delta.
- Intent adherence: requirements coverage ratio.
- Human readability/maintainability perception: readability proxy delta.
- Structural debt hygiene: duplication and code smell deltas.
- Execution reliability gate: build/test status.

Interpretation rule:

- Structural improvement delta is the primary quality outcome and is expected to co-vary with maintainability signals.
- Structural improvement delta does not, by itself, prove intent adherence or readability; these are evidenced by their own supporting metrics.

Strategy rule for primary metric collection:

- Compute `violations_before`/`violations_after` from a language-specific local tool bundle (configured and pinned).
- Aggregate violations using the pre-registered mapping profile for each language.
- Apply the same normalized delta formula across all languages.

### 3.4 Control Variables (Constants)

Keep fixed within each comparison block:

- Repository and target file
- Issue URL / PR context
- Base/head refs
- Model id (`gpt-5.3-codex`)
- Endpoint version
- Temperature (`0.0`)
- Seed (`42` for deterministic runs)
- MCP tool sequence and prompt templates
- Metric extraction implementation version

## 4. Experimental Design

Recommended default design:

- Type: paired within-subjects controlled experiment
- Pair definition: same issue/task under different treatment strategies
- Blocking: block by issue (or by repository) to reduce task heterogeneity noise
- Replication: at least 10 paired issues per set, 3 sets minimum (30 pairs)

Minimum viable design (quick cycle):

- 1 issue block x 5 repeated runs per condition (same seed schedule)
- Use only for pilot calibration, not final claims

## 4.1 Research Control Experiments (Mapped to RQs)

Control experiments are mandatory because each RQ needs a counterfactual.

### Control Definitions

- Primary control (C1, baseline): `baseline_prompt_only`
  - No MCP planning/context/judging tools.
  - Same model, same seed schedule, same issue/repo, same output metrics.
- Treatment (T1): `mcp_supervised`
  - Full MCP flow (`plan -> context -> apply -> judge`).
- Robustness control (C3): paraphrase set under C1
  - 10 paraphrases per anchored task with baseline strategy.
- Robustness treatment (T3): paraphrase set under T1
  - Same 10 paraphrases and same anchored task with supervised strategy.

### RQ-to-Control Matrix

- RQ2 (effectiveness vs baseline): compare C1 vs T1.
  - Answers: does supervision outperform prompt-only for target metrics?
- RQ3 (robustness under wording variation): compare C3 vs T3.
  - Answers: does supervision improve verdict consistency across paraphrases?
- RQ4 (legacy-focused effectiveness): compare C1 vs T1 on legacy-only issue blocks.
  - Answers: is supervision still effective in legacy task subsets?

### Positive and Negative Controls

- Negative control task set:
  - Issues expected to require minimal/no structural change.
  - Expected outcome: both C1 and T1 show near-zero metric deltas.
  - Purpose: verify pipeline does not invent artificial gains.
- Positive control task set:
  - Issues with known accepted fixes (linked PR already merged/validated).
  - Expected outcome: treatments should recover improvement directionally.
  - Purpose: verify sensitivity (experiment can detect a true effect).

### Randomization and Blocking Rules

- Block by issue: run all compared conditions on the same issue before moving on.
- Randomize condition order inside each block to reduce order effects.
- Keep seed list fixed per block (for example, seeds 41..50 for all conditions).

### Minimal Executable Control Plan (Per 10 Issues)

- For RQ2: run C1 and T1 for each issue (20 runs total).
- For RQ3 pilot: choose 3 issues and run 10 paraphrases with C3 and T3 (60 runs total).
- For RQ4 pilot: choose 10 legacy-labeled issues and run C1 and T1 (20 runs total).

This yields direct counterfactual evidence, not just single-arm performance numbers.

## 4.2 Prototype Validation Track (Non-RQ)

These checks are implementation-quality controls, not research questions.

### Prototype Controls

- P1 control: `mcp_supervised_no_format_norm`
- P1 treatment: `mcp_supervised_with_format_norm`

### Purpose

- Validate that formatting normalization reduces artificial metric drift.
- Validate that artifact formatting/debug outputs remain auditable.

### Reporting Rule

- Report prototype checks in an engineering memo section labeled Non-RQ Validation.
- Do not use prototype-only outcomes to claim RQ support/rejection.

## 5. Environment Specification

Record these for every run in a run sheet:

- Date/time (UTC)
- OS and version
- Python version
- Virtual environment identifier (`.venv` path)
- Git commit SHA of this repository
- Git commit SHA of target repository under experiment
- Hardware summary (CPU/RAM)
- Network mode (online/offline; API region)

Current known example configuration:

- OS: Windows
- Model: `gpt-5.3-codex`
- Endpoint: Azure Responses API (`2025-04-01-preview`)
- Run outputs rooted at: `out/experiments`

## 6. Execution Procedure

1. Pre-register run plan:
   - define hypotheses, factors, sample size, and statistical tests before running.
2. Prepare clean run namespace:
   - use unique `execution_id` and `--clean-output`.
3. Execute both conditions for each issue block:
   - baseline and supervised (order randomized per block when possible).
4. Persist all artifacts:
   - JSON, CSV, execution log, and LLM debug folder with input/output markdowns.
5. Validate artifact completeness:
   - confirm expected files exist and are non-empty.
6. Register run metadata into study table (see Section 10).
7. Label each run with `control_group` and `rq_target` for analysis traceability.

## 7. Statistical Analysis Plan

Choose tests by data type and pairing:

- Paired numeric outcomes (delta metrics): Wilcoxon signed-rank (non-parametric default)
- Binary/nominal verdict outcomes: McNemar (paired) or chi-square (independent)
- Multiple factor levels (`off/on`, multiple prompts): Friedman (paired repeated measures) with post-hoc Wilcoxon + Holm correction

Recommended metric handling for the lean core set:

- Treat structural improvement delta as the primary DV for effectiveness claims.
- Treat cognitive complexity, requirements coverage, readability, duplication, and smells as secondary DVs in the lean protocol.
- Apply Holm correction when testing multiple secondary DVs in the same RQ block.

Report always:

- effect size (median paired difference or rank-biserial; for binary outcomes use odds ratio when suitable)
- 95% confidence interval where applicable
- adjusted p-values for multiple comparisons

## 8. Validity and Threat Mitigation (Wohlin Structure)

- Conclusion validity:
  - Mitigation: pre-registered tests, adequate sample size, paired design.
- Internal validity:
  - Mitigation: fixed seeds/config, blocked comparisons, randomized condition order.
- Construct validity:
  - Mitigation: triangulate metrics (complexity, coverage, readability, verdict) and include objective tool-based metrics where possible.
- External validity:
  - Mitigation: include multiple repos/issues/languages over time.

## 9. Artifact Protocol

Mandatory run outputs per `execution_id`:

- `*-mcp-report-llm-<execution_id>.json`
- `*-mcp-report-llm-<execution_id>.csv`
- `*-mcp-report-llm-<execution_id>-execution.log`
- `*-llm-debug-<execution_id>/`
  - `01-...-input.md`
  - `01-...-output.md`
  - `02-...-input.md`
  - `02-...-output.md`
  - `03-...-input.md`
  - `03-...-output.md`
  - `04-...-input.md`
  - `04-...-output.md`
  - code comparison artifacts (`05-*`, `06-*`)

Completeness rule:

- A run is analyzable only if all mandatory artifacts are present and parseable.

## 10. Study Run Sheet (Template)

Use one row per run in a CSV or markdown table.

| run_id | issue_url | repo_path | rq_target | control_group | treatment | formatting_norm | prompt_variant | strictness | model | temp | seed | verdict | structural_delta | strategy_id | ruleset_id | cc_delta | req_cov | readability_delta | dup_delta | smell_delta | build_status | test_status | artifacts_ok |
|---|---|---|---|---|---|---|---|---|---|---:|---:|---|---:|---|---|---:|---:|---:|---:|---:|---|---|---|

`rq_target` examples: `RQ2`, `RQ3`, `RQ4`, `NON_RQ_PROTOTYPE`.

Suggested location:

- `data/subjects/experiment_runs.csv`

## 11. Decision Criteria

Predefine decision thresholds before execution.

- RQ2: reject H0-RQ2 if supervised treatment improves primary target metrics with statistical and practical significance.
- RQ3: reject H0-RQ3 if supervised treatment shows higher paraphrase consistency with statistical and practical significance.
- RQ4: reject H0-RQ4 if supervised treatment outperforms baseline on legacy-only blocks with statistical and practical significance.
- Practical significance rule: do not claim RQ improvement based only on statistical significance without meaningful effect size.
- Prototype validation rule: report P1 outcomes separately as engineering evidence only.
- Multi-metric rule: primary claims must be based on structural improvement delta; secondary metrics are supportive and must be reported with multiple-comparison control.

## 12. Immediate Next Step for This Repository

Run a paired pilot with existing issue-based flow:

1. Select 5-10 issues.
2. Execute `baseline_prompt_only` and `mcp_supervised` with matched seeds.
3. Toggle formatting normalization (`off`/`on`) for ablation.
4. Populate the run sheet.
5. Compute paired tests and publish a short experiment memo under `docs/experiments`.

## Reference

- Wohlin, C. et al. *Experimentation in Software Engineering*. Springer.