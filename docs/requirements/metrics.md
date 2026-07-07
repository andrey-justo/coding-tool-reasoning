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
| M-1 | Structural improvement delta | Primary DV | Language-specific local static analysis strategy bundle | Not implemented (no multi-strategy runner wired into evaluation harness) |
| M-2 | Testability gate outcome | Prerequisite | Repo build + unit test commands | Not implemented (no build/test gate runner wired) |
| M-3 | Cyclomatic complexity | Must (syntax/maintainability signal) | Static analysis / CI quality tools | Not implemented |
| M-4 | Test coverage | Must (testability signal) | Coverage tool + CI | Not implemented |
| M-5 | Code duplication | Must (maintainability signal) | Clone detection / static analysis | Not implemented |
| M-6 | Code conventions | Must (style/compliance signal) | Linter/formatter/analyzers | Not implemented |
| M-7 | Code security findings | Must (security signal) | SAST / security analyzers | Not implemented |
| M-8 | Semantic similarity (optional) | Optional | Code-aware similarity model | Partially implemented (BERTScore tooling exists; integration into judge/harness not fully wired) |

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

### M-1 — Structural improvement delta (Primary DV)

- **Definition**: normalized change in aggregated structural-violation count between
  *before* and *after* for a given execution, using a pre-registered set of
  language-specific analyzers and rule mappings.
- **Purpose**: primary dependent variable for structural-quality effectiveness questions.
- **Instrument**: local static-analysis strategy bundle configured per language.
- **Recorded fields (minimum)**:
  - `violations_before`
  - `violations_after`
  - `delta` (definition must be recorded; normalized improvement ratio)
    - Standard case (`violations_before > 0`):
      $\Delta = (violations_before - violations_after) / violations_before$
    - Zero-baseline edge cases (`violations_before = 0`):
      - if `violations_after = 0`, define `delta = 0.0` (no change from a clean baseline)
      - if `violations_after > 0`, define `delta = -1.0` (maximal regression from a clean baseline)
    - `delta` is therefore bounded to `[-1.0, 1.0]` under this definition.
  - `absolute_delta` (`violations_after - violations_before`) must also be recorded to preserve raw-count interpretability, especially for zero-baseline cases.
  - `ruleset_id` / `ruleset_version`
  - `strategy_id` (selected analyzer strategy bundle)
  - `scope` (what was analyzed)
- **Notes**: the exact rule mappings used to operationalize structural quality
  must be documented in metadata. SOLID-oriented rules are a subset of this
  structural set when language/tool support exists.

#### Suggested local strategy bundles (language-oriented)

- C/C++: `cppcheck + clang-tidy + flawfinder + semgrep + codeql`
- C#: `roslyn analyzers + semgrep + codeql`
- Java: `pmd + spotbugs + checkstyle + semgrep + codeql`
- Python: `pylint + flake8 + semgrep + codeql`
- JavaScript/TypeScript: `eslint + semgrep + codeql`

Each bundle should be pinned by tool version and ruleset profile for reproducibility.

#### SonarQube positioning

SonarQube can be used as an external enrichment backend in future cycles, but
it is not required by the initial local-first evaluation design.

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
