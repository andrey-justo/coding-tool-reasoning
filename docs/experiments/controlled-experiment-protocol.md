# Controlled Experiment Protocol (Wohlin-Aligned)

This protocol operationalizes the methodology from *Experimentation in Software Engineering* (Wohlin et al.) for this repository's MCP-assisted code-change experiments.

It is designed to be executable with the current artifact structure in `out/experiments` and the current runner in `src/experiments/issue_mcp_experiment.py`.

## Configured campaign execution

The shared [campaign](../../experiments/campaign.yaml) defines cohorts, study
conditions, comparisons, model/provider, strictness, scheduling limits and
verification/repair settings. The `experiment_config` column in the
[planned-run CSV](../../data/subjects/experiment_runs.csv) references one
[issue configuration](../../experiments/configured) shared by both paired rows.
Paths in task bindings and the CSV resolve from the campaign's `config_root`;
normalized analyzer report paths resolve from their structural configuration.
The original CSV rows and proposal run IDs are retained.

For strictness, [90 execution YAMLs](../../experiments/strictness) materialize the
30 task slots crossed with low/medium/high conditions. The
[execution index](../../experiments/strictness/executions.csv) has one unique
`experiment_config` per row. These are execution definitions, distinct from the
20 shared issue definitions: each records its job/block identity, condition,
strictness, effective runtime hash and blocker snapshot. Shared task references
are present for the 20 proposed tasks; the ten unassigned slots remain null and
blocked. References in the generated YAMLs are relative to their containing
directory, and index references are relative to the CSV.

Execution filenames group by task, followed by subject/issue and condition
(for example `set01-task01-S001-issue131001-low.yaml`). Unassigned slots use
`set03-task01-unassigned-low.yaml`; repetition and wording suffixes are included
only for studies that vary them. Renaming does not change job or pairing IDs.

`study materialize --config experiments\campaign.yaml --study strictness --output
experiments\strictness` regenerates definitions without running workers or
initializing a ledger. Regenerate after qualification changes; unexpected YAML
files in the output directory are rejected rather than removed. A qualified
execution can be selected with `study run --ledger ... --execution-config ...`.
The selection must exactly match a trial in the frozen plan, including shared
references, strictness, runtime hash and blockers; it cannot override that trial
or bypass a blocked condition. Completed selections retain resume semantics.
The existing baseline/supervised proposal CSV is not replaced or repurposed.

The initial configuration expands to 810 executions and 420 comparison records:
60/30 for effectiveness, 90/60 for strictness, 600/300 for robustness, and 60/30
for legacy effectiveness. Each strictness block has three executions and two
comparisons sharing the medium execution. Ten robustness variants are repeated
observations within each task, not ten independent subjects. Multiple issues
from one repository must also be treated as clustered observations.

The 20 imported main tasks and six legacy tasks are proposals, not verified
experimental eligibility or final open/positive/negative-control assignments.
Ten main and 24 legacy slots remain unassigned. The planner audits all 72 subject
rows, flags the 53 malformed rows and does not rewrite or repair them. Unassigned
and blocked trials remain visible in the plan, exports and denominators.

Task YAMLs explicitly leave the baseline commit, local repository, structural
analyzer configuration, paraphrase file and historical evidence cutoff unset;
AI-use approval is false. Qualify these inputs before execution. A paraphrase
file is a JSON object mapping exactly the declared non-original variant IDs to
nonempty human-authored wording. The current issue worker prepends this wording
to the same issue evidence; it does not replace the issue or use future PR fixes.
The reference head is explicitly the baseline commit, so semantic similarity to
that reference must not be interpreted as similarity to a human solution.

Planning does not call models, fetch issues, clone repositories or run analyzers.
It checks available local commits and freezes input hashes, runtime/knowledge
directory membership and trial runtime snapshots. Within-block execution order
is deterministically randomized using the declared order seed; this is **not**
a model-generation seed. The worker currently uses the application-root
`available_models.yaml`, so alternate model registry paths are rejected.
Credentials belong in environment variables, not campaign files or snapshots.

```powershell
python -m src.main study plan --config experiments\campaign.yaml --export out\studies\exploratory-v1\exports
python -m src.main study status --ledger out\studies\exploratory-v1\ledger.sqlite
python -m src.main study export --ledger out\studies\exploratory-v1\ledger.sqlite --output out\studies\exploratory-v1\exports
```

`plan` initializes a SQLite ledger and refuses reuse by a different plan.
Exports contain the frozen plan, summary, all executions (including blockers),
explicit comparison rows and all attempt records. Each export file is replaced
atomically from one ledger snapshot. Changed inputs invalidate execution;
requalification requires a new ledger and artifact root, preserving old evidence.

Execution must be requested separately with `study run --ledger ... --max-trials N`.
Only the supervised issue worker is implemented: the existing reproducibility
scaffold is **not** accepted as a prompt-only baseline. Complete matched blocks
are required by default, so baseline-dependent blocks cannot execute yet.
The supplied configuration consequently has zero runnable trials. Copilot runs
are exploratory; seed/temperature are null/unsupported, not controlled.

The scheduler bounds process duration and campaign concurrency, serializes jobs
sharing a Git common directory, and preserves per-attempt artifacts, logs and
process IDs. Completed executions are never automatically repeated, even when
builds/tests fail, M-1 is unavailable, or the outcome is unfavorable. Only execution
failures/interruption can be retried explicitly with `--retry-failed`, subject to
the registered attempt limit. A `run` returns nonzero for failed/interrupted
executions or when every planned trial is blocked.

Execution completion, complete pairs and gate/M-1-eligible pairs are distinct.
Eligibility requires both build/test gates, available M-1, matching protocol,
baseline score, analyzed source/scope/instrument provenance and issue-discussion
snapshot. Unmatched or failed observations are retained, not silently removed.
These counts do not implement inferential statistics or establish confirmatory
eligibility by themselves.

After an abrupt scheduler failure, inspect the recorded PIDs and artifacts and
stop any remaining owned workers before acknowledging recovery:

```powershell
python -m src.main study recover --ledger out\studies\exploratory-v1\ledger.sqlite --acknowledge-workers-stopped
```

Recovery marks outstanding executions interrupted; it does not kill processes,
clear history or automatically rerun trials. Unconfirmed worker cleanup stops
scheduling and requires this same explicit operator recovery.

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