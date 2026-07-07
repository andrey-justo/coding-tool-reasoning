# Requirements Implementation Roadmap (v1)

This roadmap sequences implementation work to satisfy the Volere-style
requirements in [`docs/requirements/requirements.md`](requirements.md), using
priorities (**Must/Should/Could**) and declared dependencies.

Status legend used below:
- **Done**: implemented in codebase and usable.
- **Partial**: present as docs/schema/scaffold, or implemented but not end-to-end wired.
- **Not started**: no implementation found in the codebase.

---

## Roadmap Principles

- **Must first**: implement all **Must** requirements before expanding scope.
- **Dependency order**: prerequisites land before dependents.
- **Evidence-first**: anything required to run controlled experiments (baseline,
  determinism controls, static analysis, testability gate, traceability) is
  scheduled early.
- **Traceability by default**: every execution produces an auditable record.

---

## Milestones

### M0 â€” Requirements baseline (now)

- **Status**: Partial.
- **Outcome**: requirements and priorities stabilized.
- **Deliverables**:
  - Volere requirements spec finalized (FR/NFR shells, priorities). **Status**: Done.
  - This roadmap agreed with supervisor. **Status**: Not started.

### M1 â€” Core supervisor workflow + knowledge base grounding (Must)

- **Status**: Done.
- **Requirements**: FR-1, FR-2, FR-3
- **Outcome**: the supervisor workflow is usable end-to-end for one repo.
- **Deliverables**:
  - Two-stage workflow produces plans + judgments for a given change. **Status**: Done (MCP tools implemented).
  - Configurable focus/strictness demonstrated on controlled examples. **Status**: Done (config-driven strictness/default focus present).

### M2 â€” Experiment harness foundations (Must)

- **Status**: Partial.
- **Requirements**: FR-4, FR-5, NFR-3, NFR-4
- **Outcome**: issue-centric experiments can be executed safely.
- **Deliverables**:
  - Issue-centric inputs recorded with stable identifiers. **Status**: Partial (CSV schema exists in `data/subjects/*`, not yet wired into an execution pipeline).
  - Baseline (no-knowledge base supervision) condition runnable. **Status**: Not started (experiment runner baseline path is scaffold only).
  - Prompt-ingestion safety rule is enforced and sources are logged. **Status**: Not started (no enforcement found).
  - Public-corpus protocol documented. **Status**: Partial (documented in risks/docs; not enforced by tooling).

### M3 â€” Traceability & reproducibility backbone (Must)

- **Status**: Partial.
- **Requirements**: FR-9, NFR-1, NFR-8
- **Outcome**: every run is reproducible and auditable.
- **Deliverables**:
  - Execution record schema (execution id, issue/feature id, repo, revisions,
    commits, user approval, external/internal prompts).
    **Status**: Partial (execution metadata and report artifacts exist for experiment runs, but traceability is not yet unified across all workflows).
  - Determinism parameters recorded where supported. **Status**: Partial (`temperature`/`seed` are supported in LLM clients/tools and recorded in experiment outputs, but not enforced end-to-end across all execution paths).

### M4 â€” Static analysis + primary DV (Must)

- **Status**: Partial.
- **Requirements**: FR-14, FR-6, NFR-2
- **Outcome**: primary metric is objective and tool-verifiable.
- **Deliverables**:
  - Local language-specific strategy adapters (e.g., Cppcheck/Clang-Tidy/Flawfinder/CodeQL for C/C++, Roslyn for C#, PMD/SpotBugs/Checkstyle for Java, etc.) with pinned ruleset support. **Status**: Not started (design defined in docs; runner/orchestration still missing).
  - Before/after violation counts and deltas stored per trial. **Status**: Partial (metric evaluator and structural-delta computation are implemented; end-to-end multi-strategy collection pipeline is not yet wired).

### M5 â€” Testability gate (Must)

- **Status**: Not started.
- **Requirements**: FR-7
- **Outcome**: quality claims are gated by build/test results.
- **Deliverables**:
  - Build + unit-test execution status recorded per trial. **Status**: Not started.
  - Trials failing the gate are flagged and excluded from claims. **Status**: Not started.

### M6 â€” Expanded metrics & enrichment (Should)

- **Status**: Partial.
- **Requirements**: FR-15
- **Outcome**: multi-dimensional quality reporting.
- **Deliverables**:
  - Metric collection for: cyclomatic complexity, test coverage, duplication,
    conventions, security.
    **Status**: Partial (complexity/readability/intent metrics exist in evaluator; coverage/duplication/conventions/security are not yet implemented end-to-end).
  - External enrichment support with provenance logging. **Status**: Partial (optional external static-analysis enrichment path exists, but local-first multi-tool provenance orchestration is still pending).

### M7 â€” Robustness experiments + usability enhancements (Should/Could)

- **Status**: Partial.
- **Requirements**: FR-8, FR-11, NFR-6
- **Outcome**: prompt-variation robustness and improved developer guidance.
- **Deliverables**:
  - Paraphrase dataset support and verdict consistency reporting. **Status**: Not started.
  - Contextual guidance integrated into outputs. **Status**: Partial (judge outputs include risks + recommended tests; broader contextual help is not implemented as a dedicated feature).

### M8 â€” Integrations & advanced assistance (Should/Could)

- **Status**: Partial.
- **Requirements**: FR-10, FR-13, FR-12, NFR-5, NFR-7
- **Outcome**: adoption-friendly integrations and proactive recommendations.
- **Deliverables**:
  - Skills/tools exported for multiple agent runtimes. **Status**: Partial (MCP server exists; multi-runtime registration not validated in-repo).
  - Repository/config-aware recommendations. **Status**: Not started.
  - Proactive risk detection and follow-up actions. **Status**: Not started.

---

## Tracking

Suggested tracking unit for implementation and experiments:

- **Issue/Feature ID** â†’ multiple **Executions** â†’ each execution produces an
  auditable record (FR-9 / NFR-8), metrics, and artifacts.

This creates a natural grouping for debugging and for comparing supervised vs.
baseline runs.

