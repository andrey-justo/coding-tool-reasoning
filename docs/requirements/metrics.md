# Metrics Specification (v1)

This document defines the **evaluation metrics** used by the project.

The intent is to keep the proposal and requirements **high-level** while this
file captures the metric definitions and what must be recorded for
reproducibility.

---

## 0. At-a-Glance (Current State)

This table is a quick view of **what we measure** and **whether the repo
currently implements it end-to-end**.

| ID | Metric | Role | Typical instrument / source | Current repo status |
|---|---|---|---|---|
| M-1 | Composite structural improvement delta | Primary DV | Pre-registered analyzer reports; configurable Ruff, Roslyn/SARIF and SonarQube collection | Implemented calculation, comparability checks, judge/runner integration and reporting; production rule mapping must still be pre-registered |
| M-2 | Testability gate outcome | Prerequisite | Repo build + unit test commands | Implemented in issue runner; M-1 never replaces this gate |
| M-3 | Cyclomatic complexity | Must (syntax/maintainability signal) | Static analysis / CI quality tools | Partial: runner reports a lightweight heuristic; not a calibrated analyzer measurement |
| M-4 | Test coverage | Must (testability signal) | Coverage tool + CI | Not implemented |
| M-5 | Code duplication | Must (maintainability signal) | Clone detection / static analysis | Not implemented |
| M-6 | Code conventions | Must (style/compliance signal) | Linter/formatter/analyzers | Not implemented |
| M-7 | Code security findings | Must (security signal) | SAST / security analyzers | Not implemented |
| M-8 | Semantic similarity (optional) | Optional | Code-aware similarity model | Partially implemented (BERTScore tooling exists; integration into judge/runner not fully wired) |

Additional metrics planned for future implementation are documented in `docs/requirements/metrics-future.md`.

---

## 1. Principles

- **Objective-first**: prefer tool-verifiable metrics over LLM self-reporting.
- **Pinned instruments**: each metric must record instrument version/ruleset.
- **Comparable scope**: metric values must be computed on a declared scope
  (repo/module/path/PR diff) so results are comparable.
- **Provenance**: every recorded metric value must carry its provenance.

---

## 2. Metric Catalog

### M-1 — Composite structural improvement delta (Primary DV)

The primary measure is a composite **defect density**, not an unqualified
count of findings or an LLM quality rating:

$$
V_{\mathrm{struct}} =
0.50 V_{\mathrm{solid}} + 0.30 V_{\mathrm{arch}} + 0.20 V_{\mathrm{smell}}
$$

The reference weights prioritize design quality. Alternative weights must be
nonnegative, sum to one, and be pre-registered before confirmatory experiments.
They must not be tuned after observing results.

The measurement rationale follows the product-quality model in ISO/IEC
25010:2023 and internal quality measurement in ISO/IEC 25023. McCabe (1976),
Chidamber and Kemerer (1994), and Halstead (1977) support interpretation of
complexity/design signals. The composite, severity weights and normalization
here are this experiment's operational definitions, not formulas mandated by
those standards.

For each component $c$, in the same target-file scope:

$$
N_c = \sum_{r \in R_c} s(r)n(r), \qquad
V_c = \frac{N_c}{\max(1,\mathrm{KLOC})}, \qquad
\mathrm{KLOC} = \frac{\mathrm{LOC}}{1000}
$$

Severity weights are **minor = 1, major = 3, critical = 5**. The rule mapping,
not analyzer-specific severity spelling or model interpretation, fixes each
rule's component, severity, counting unit and rationale.

- `solid`: structural SOLID/design-principle and equivalent maintainability rules.
- `arch`: coupling, cohesion and complexity rules/thresholds, such as CBO,
  LCOM, cyclomatic complexity and inheritance depth.
- `smell`: structural smells and duplication with maintenance impact.
- `excluded`: explicitly registered findings not included in the score.

A rule belongs to exactly one component per instrument. A protocol combining
instruments must pre-register how overlapping findings are avoided; the runner
does not guess conceptual equivalence or deduplicate different rule IDs.
Counts can represent occurrences or duplicated lines, but units must be declared
per rule. Live issue collectors count **occurrences** only; duplicated-line
measures require a normalized report with a pre-registered line-count rule.
Raw complexity values are not automatically treated as violation counts:
an analyzer must report violations of a registered complexity threshold.

Each snapshot uses its own LOC denominator on exactly the same file paths.
The floor is **one KLOC**, not one line: scopes below 1000 LOC have denominator
one, as prescribed by the protocol.

For baseline $V_b$ and candidate $V_a$:

$$
\Delta_{\mathrm{struct}} =
\begin{cases}
(V_b - V_a)/V_b & V_b > 0 \\
0.0 & V_b = 0 \land V_a = 0 \\
-1.0 & V_b = 0 \land V_a > 0
\end{cases}
\qquad
\Delta_{\mathrm{abs}} = V_a - V_b
$$

Positive relative deltas indicate improvement; negative relative deltas indicate
regression. Absolute deltas have the opposite sign. **The relative delta is not
bounded below by -1 when the baseline is nonzero**: a change from 1 to 4 yields
-3. The implementation does not clamp this result.

The deterministic `effectiveness_verdict` uses the absolute delta and the
protocol's nonnegative `regression_tolerance` (default zero): within tolerance
is `neutral`, lower is `improved`, higher is `regressed`. The raw deltas remain
unchanged. This is separate from the LLM's `overall_verdict` and does not establish
behavioral correctness or passing builds/tests.

#### Pre-registration, evidence and comparability

The validated schemas are `StructuralProtocol`, `AnalyzerReport` and
`StructuralMetricInput` in `src/models/structural_metrics.py`.

The protocol contains `protocol_id`, `mapping_version`, weights, tolerance,
and rules (`instrument`, `rule_id`, `component`, `severity`, `unit`,
`rationale`). All three primary components must have registered rules, including
components with zero observed findings. No production mapping is supplied by
default; synthetic test mappings are **not research instruments**.

Each report records:

- instrument and instrument version;
- ruleset ID/version and configuration SHA-256;
- timezone-qualified analysis timestamp and source/report reference;
- exact analyzed rule inventory;
- repository-relative file paths, source SHA-256 and per-file LOC;
- LOC counting method and nonnegative integer counts by rule and file.

Before/after reports must use the same instruments, versions, rulesets,
configuration, rule inventory, target paths and LOC method. All instruments
within a snapshot must agree on source hashes and LOC. Missing coverage,
unknown rules, duplicate counts, stale sources, naive timestamps and
incomparable configurations fail explicitly rather than becoming zero defects.
The runner validates source hashes against the **final generated candidate**,
not a reference PR or an earlier repair checkpoint. JSON preserves the full
mapping, input reports, component counts/densities, composite values and protocol
hash. CSV includes primary/component/sensitivity rows with provenance; Markdown
summarizes the result and identifies the companion JSON evidence.

#### Discovery and configurable collection

Discovery only describes repository configuration; it does not authorize code
execution, choose a scientific rule mapping or enable every detected tool:

```powershell
python -m src.evaluation.structural_analysis --discover-repo C:\path\to\subject
```

It recognizes Ruff configuration, C# project files as Roslyn candidates, and
Sonar configuration files, excluding common dependency/build directories.
SonarQube can also be explicitly configured without any repository marker.

The issue runner accepts `--structural-analysis-config C:\path\to\block.json`.
This JSON contains a `protocol` plus an `analyzers` list. Configuration is read
before generation; local before/after collection uses separate disposable
worktrees. All collectors are configurable and may be disabled, but enabled
instruments must exactly cover the registered protocol. Repository discovery
and explicit selection are retained in the report's evidence/configuration.

Export the complete validated configuration schema (including required fields,
rule mappings and reference weight defaults) without invoking any analyzer:

```powershell
python -m src.evaluation.structural_analysis --config-schema --output C:\reports\structural-config.schema.json
```

Common analyzer fields: `instrument`, `kind`, `enabled`, `expected_version`,
`ruleset_id`, `ruleset_version`, `timeout_seconds`.

| Kind | Configuration | Collection behavior |
|---|---|---|
| `report` | `before_report`, `after_report` (relative to block JSON) | Imports normalized `AnalyzerReport` JSON with declared scope/LOC and verifies configured provenance |
| `ruff` | Optional command prefix, e.g. `["python", "-m", "ruff"]`; default uses the runner's Python | Runs the pinned Ruff version, selects registered rules, clears rule ignores/per-file ignores, ignores `noqa`, disables forced exclusion, and parses JSON findings without applying fixes |
| `roslyn` | Explicit tokenized `command` containing `{report}`; `{repo_path}` is also supported | Runs a configured project build and reads SARIF 2.1.0; requires successful execution, pinned driver version, rule inventory and target-file coverage |
| `sonarqube` | `sonar_url`, `sonar_project`, `sonar_before_branch`, `sonar_after_branch`, `sonar_token_env` (default `SONAR_TOKEN`) | Reads existing completed analyses; checks server version, installed-plugin/profile fingerprint, active mapped rules, analysis identity and exact remote source contents |

Roslyn project detection is not proof that a particular analyzer package or
ruleset is enabled. Some native compiler SARIF exports do not attest the entire
enabled-rule inventory or file coverage: these must be enriched by a trustworthy
exporter or imported as normalized reports; absence of findings is not sufficient.
Only register rules actually supported and enabled by the instrument.
Commands are token lists, not shell strings, and run only from explicitly
supplied trusted configuration. Nonzero Roslyn builds, tool errors, timeouts,
source mutation, or incomplete reports block measurement.

SonarQube collection **does not upload source or launch a scanner**. Both
configured branches must already contain completed scans of the exact baseline
and generated candidate. It rejects stale scans, profiles edited after analysis,
analysis changes during collection, and truncated issue search. Credentials are
read from the configured environment variable, not stored in metric evidence.
SonarQube is optional, not silently included simply because a server exists.

Live Ruff and Roslyn blocks currently require Python-only and C#-only scope,
respectively. Live SLOC counts physical lines containing syntax tokens, excluding
blank/comment-only lines (Python tokenizer or the C# tree-sitter parser).
Sonar collection uses the same declared SLOC method on the verified sources, so
compatible live instruments share a denominator. For other languages or a
different pre-registered LOC definition, import normalized reports. Adding a new
language requires a pinned LOC collector; no generic regex approximation is used.

#### Judge and CI use

The direct judge APIs accept optional `structural_metrics` evidence for a
single file and verify its hashes against `original_code`/`modified_code`.
The experiment runner handles multi-file blocks. Objective results survive an
LLM judgment failure and cannot be supplied by the LLM. Without evidence,
effectiveness is explicitly `unavailable` (runner M-1 status: `not-run`), not
`neutral` or zero.

An evidence-only CLI supports CI without a model call:

```powershell
python -m src.evaluation.structural_analysis --input C:\reports\evidence.json --output C:\reports\m1.json --fail-on-regression
```

`evidence.json` has `protocol`, `before` and `after` fields matching
`StructuralMetricInput`. A regression returns exit code 1 after persisting the
result; omitting `--fail-on-regression` provides reporting-only rollout.
Invalid evidence remains an error in either mode. A production CI job must
supply independently collected, pre-registered evidence, not the synthetic unit
fixtures. M-1 does not yet complete the other #13 deliverables (calibrated
cyclomatic complexity, Maintainability Index, function/diff scope and general
readability/convention gates).

#### Sensitivity analyses (not alternative primary endpoints)

Reports always include:

1. `unweighted_severity`: $s(r)=1$, preserving component weights and KLOC scope.
2. `per_file`: severity-weighted counts normalized by the number of target files.

`reliability_substitution` is included only when the protocol explicitly sets
`reliability_focus=true` and registers separate `reliability` rules/counts.
It replaces the smell density using the same gamma weight, solely for robustness
analysis. The original smell component and primary M-1 remain unchanged.
Enabling the flag without evidence (or supplying these rules without explicit
task focus) is rejected.

#### Suggested local strategy bundles (language-oriented)

- C/C++: `cppcheck + clang-tidy + flawfinder + semgrep + codeql`
- C#: `roslyn analyzers + semgrep + codeql`
- Java: `pmd + spotbugs + checkstyle + semgrep + codeql`
- Python: `pylint + flake8 + semgrep + codeql`
- JavaScript/TypeScript: `eslint + semgrep + codeql`

Each bundle should be pinned by tool version and ruleset profile for reproducibility.

#### SonarQube positioning

SonarQube is an optional configured collection/enrichment backend; it is not
required by the local-first evaluation design. The legacy aggregate
`solid_violation_delta` report field is retained for compatibility and is **not**
the new composite M-1.

- **References**:
  - R. C. Martin, *Agile Software Development: Principles, Patterns, and Practices* (SOLID principles background). https://www.pearson.com/en-us/subject-catalog/p/agile-software-development-principles-patterns-and-practices/P200000003268
  - Roslyn analyzers overview (C# diagnostics and analyzer model). https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/overview
  - Cppcheck manual (local static analysis for C/C++). https://cppcheck.sourceforge.io/manual.html
  - Clang-Tidy documentation. https://clang.llvm.org/extra/clang-tidy/
  - PMD documentation. https://pmd.github.io/
  - SpotBugs documentation. https://spotbugs.readthedocs.io/
  - Checkstyle documentation. https://checkstyle.org/
  - Flawfinder documentation. https://dwheeler.com/flawfinder/
  - CodeQL documentation. https://codeql.github.com/docs/

### M-2 — Testability gate outcome (Prerequisite signal)

- **Definition**: build and unit-test execution status for the target repo
  at the evaluated revision(s).
- **Purpose**: gates interpretation of other outcomes (no claims if the gate
  fails or cannot be run).
- **Recorded fields (minimum)**:
  - `build_status` (pass/fail/not-run)
  - `test_status` (pass/fail/not-run)
  - `test_command` / `build_command` (or equivalent reference)

- **References**:
  - ISO/IEC 25010 software product quality model (Maintainability includes Testability as a sub-characteristic). https://www.iso.org/standard/35733.html
  - P. M. Duvall, S. Matyas, A. Glover, *Continuous Integration: Improving Software Quality and Reducing Risk* (build/test gating practice). https://www.pearson.com/en-us/subject-catalog/p/continuous-integration-improving-software-quality-and-reducing-risk/P200000003246

### M-3 — Cyclomatic complexity

- **Definition**: a control-flow complexity measure based on the number of
  linearly independent paths through a program.
- **Purpose**: supporting signal for maintainability/modifiability; helps
  detect overly complex code changes.
- **Instrument**: local static analysis tools that compute cyclomatic complexity.
- **Recorded fields (minimum)**:
  - `value` (and unit/aggregation, e.g., per method / per file)
  - `scope` (what was analyzed)
  - `source_system`
  - `ruleset_id` / `ruleset_version` (or tool version)
  - `timestamp`
- **References**:
  - T. J. McCabe (1976). *A Complexity Measure*. https://doi.org/10.1109/TSE.1976.233837

### M-4 — Test coverage

- **Definition**: the extent to which the code is executed by tests (e.g.,
  statement/line/branch coverage).
- **Purpose**: supporting signal for testability and regression risk; used as
  a quality indicator alongside the testability gate.
- **Instrument**: coverage tools integrated into the build/test pipeline.
- **Recorded fields (minimum)**:
  - `value` and `unit` (line/branch, percentage)
  - `scope`
  - `source_system`
  - `tool_version`
  - `timestamp`
- **References**:
  - H. Zhu, P. A. V. Hall, J. H. R. May (1997). *Software Unit Test Coverage and Adequacy*. https://doi.org/10.1145/267580.267590

### M-5 — Code duplication

- **Definition**: duplicated or near-duplicated code fragments (clones) as
  detected by clone detection or quality tools.
- **Purpose**: maintainability signal; high duplication increases change cost
  and defect risk.
- **Instrument**: clone detection / static analysis.
- **Recorded fields (minimum)**:
  - `value` (and unit/aggregation)
  - `scope`
  - `source_system`
  - `tool_version` / `ruleset_id`
  - `timestamp`
- **References**:
  - C. K. Roy, J. R. Cordy (2007). *A Survey on Software Clone Detection Research*. https://doi.org/10.1007/s10664-007-9034-7

### M-6 — Code conventions

- **Definition**: violations of agreed coding style and conventions.
- **Purpose**: supporting signal for readability/maintainability and
  consistency across changes.
- **Instrument**: linters/analyzers/formatters.
- **Recorded fields (minimum)**:
  - `violations_count` (and/or severity breakdown)
  - `ruleset_id` / `ruleset_version`
  - `scope`
  - `source_system`
  - `timestamp`
- **References**:
  - Microsoft .NET coding conventions. https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions
  - Roslyn analyzers overview. https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/overview

### M-7 — Code security findings

- **Definition**: static security findings (e.g., vulnerable patterns,
  injection sinks, unsafe deserialization) reported by a SAST tool or security
  analyzer.
- **Purpose**: supporting signal for security posture of generated/modified
  code.
- **Instrument**: SAST/security analyzers.
- **Recorded fields (minimum)**:
  - `findings_count` (and/or severity breakdown)
  - `ruleset_id` / `ruleset_version`
  - `scope`
  - `source_system`
  - `timestamp`
- **References**:
  - OWASP Top 10 (security issue categories commonly used for reporting). https://owasp.org/www-project-top-ten/

### M-8 — Semantic similarity (optional)

- **Definition**: code similarity of generated output against a reference
  implementation.
- **Purpose**: secondary metric; should not replace M-1 for SOLID claims.
- **Instrument**: code-aware similarity model (e.g., CodeBERT-family), with
  version pinned.

- **References**:
  - T. Zhang et al. (2019). *BERTScore: Evaluating Text Generation with BERT* (semantic similarity scoring). https://arxiv.org/abs/1904.09675
  - Z. Feng et al. (2020). *CodeBERT: A Pre-Trained Model for Programming and Natural Languages* (code-aware embeddings). https://arxiv.org/abs/2002.08155

---

## 3. Missing Data and Provenance (applies to all metrics)

The system must be able to record explicit `missing`/`not-available` metrics
without failing the run.

---

### Provenance requirements

Every metric record must include enough information to answer:

- **What** was measured? (metric name + definition)
- **On what**? (scope + repo + revision)
- **How**? (instrument + ruleset/version)
- **When**? (timestamp)

This supports auditability and replication.
