# Volere-Style Requirements Specification (v1)

This document refactors the project requirements into a **Volere-aligned**
structure.

The requirements are intentionally **not implementation-level**. Architectural
documentation can later map each requirement to components, modules, and
controls.
---

## 1. Purpose and Background

The purpose of the system is to supervise LLM-assisted software changes for legacy modernization by grounding planning and judging in configurable software-engineering taxonomies, and to support reproducible empirical evaluation.

---

## 2. Stakeholders and Users

- **Primary users**: software developers and engineers working on legacy codebases.
- **Secondary users**: researchers running controlled experiments and collecting evidence for RQ1–RQ4.
- **Reviewers/maintainers**: people validating artifacts, methodology, and replication packages.

---

## 3. Scope (v1)

- Evaluation scope focuses on **C#** repositories.
- The NFR lens for v1 is SOLID (**SRP/OCP/DIP**) as an operationalization of
  ISO 25010 Maintainability/Modifiability.
- Minimum empirical corpus target is **5 repositories × 30 issues each** for
  between-condition comparisons.

---

## 4. Constraints

- **Public-by-default corpus** for primary experiments.
- **Determinism controls** must be available where supported by the chosen LLM provider/client (e.g., temperature/seed).
- **Measurement instrumentation** (static analysis rulesets, scorers) must be versioned/pinned and changes must be traceable.
- **Metrics specification**: metric definitions are centralized in [`docs/requirements/metrics.md`](metrics.md).
- **Priority scheme**: priorities use **Must / Should / Could** as an initial ordering based on requirement dependencies and the research evaluation critical path.

---

## 5. Assumptions and Dependencies

- The system may call third-party LLM services. Data retention/training behavior is governed by the provider’s policy; the tool cannot guarantee third-party storage behavior.
- Repository build/test execution and static analysis depend on repository tooling and environment availability.

---

## 6. Glossary

- **FR**: Functional Requirement.
- **NFR**: Non-Functional Requirement.
- **MCP**: Model Context Protocol.
- **SOLID**: SRP, OCP, DIP used here as a maintainability/modifiability lens.
- **SRP**: Single Responsibility Principle — a module/class should have one reason to change.
- **OCP**: Open/Closed Principle — software entities should be open for extension but closed for modification.
- **DIP**: Dependency Inversion Principle — depend on abstractions, not on concretions.
- **SonarQube**: static analysis platform that reports code quality and security metrics.
- **Roslyn analyzers**: C# compiler-based analyzers that report diagnostics (rules/violations) and code quality signals.
- **Baseline**: a named comparison condition where taxonomy supervision is disabled.
- **Fit Criterion**: an observable/measurable condition that indicates the requirement has been satisfied (Volere terminology).

---

## 7. Functional Requirements (Volere shells)

### FR-1 — Supervisor workflow

- **Statement**: The system shall support a two-stage supervision workflow that (a) produces a quality-aware plan from a natural-language request and (b) explains/judges a proposed code change against selected quality objectives.
- **Fit Criterion**: Given an intent + code change, the system outputs a plan, an overall verdict, quality impacts, and recommended tests.
- **Rationale**: Provide developer control and NFR alignment beyond raw LLM generation.
- **Source**: Main Goal, Workflow.
- **Priority**: Must.
- **Dependencies**: FR-3.

### FR-2 — Configurable quality focus

- **Statement**: The system shall allow users to set a desired quality focus and a strictness level that influences planning and judging.
- **Fit Criterion**: Under controlled runs, changing focus/strictness yields measurably different plans and/or verdict distributions.
- **Rationale**: Enable RQ4 (developer control) and support diverse quality profiles.
- **Source**: `docs/PROPOSAL.md` (RQ4), `docs/risks/risk-register.md`.
- **Priority**: Must.
- **Dependencies**: FR-1.

### FR-3 — Taxonomy-driven guidance

- **Statement**: The system shall use a configurable software-engineering taxonomy as the grounding source for plans, summaries, and judgments.
- **Fit Criterion**: Replacing the taxonomy dataset changes the concepts/labels used in outputs without rewriting source code.
- **Rationale**: Avoid fixed ontologies and support extensibility.
- **Source**: `docs/PROPOSAL.md` (Contributions), `docs/risks/avoiding-ontologies.md`.
- **Priority**: Must.
- **Dependencies**: None.

### FR-4 — Issue-centric evaluation inputs

- **Statement**: The evaluation workflow shall support issue-centric prompts bound to a concrete repository artifact (issue or pull request) to provide authoritative context.
- **Fit Criterion**: Each evaluation record includes a stable link/identifier to the underlying artifact and the prompt used.
- **Rationale**: Ensure experimental inputs are concrete and reviewable.
- **Source**: `docs/PROPOSAL.md` (Empirical Experiments), `docs/experiments/experiment-design.md`.
- **Priority**: Must.
- **Dependencies**: NFR-3, NFR-4.

### FR-5 — Baseline comparisons

- **Statement**: The evaluation workflow shall support at least one named baseline condition where taxonomy supervision is disabled.
- **Fit Criterion**: The same intent can be executed under supervised vs baseline conditions and compared.
- **Rationale**: Required for falsifiable RQs and controlled comparisons.
- **Source**: `docs/experiments/experiment-design.md`, `docs/risks/rq-scope-falsifiability.md`.
- **Priority**: Must.
- **Dependencies**: FR-1.

### FR-6 — Primary metric collection

- **Statement**: The evaluation workflow shall collect the primary quality metric defined in the metrics specification.
- **Fit Criterion**: For each trial, store the required primary-metric inputs/outputs (before/after and derived value) under a pinned instrument/ruleset, as defined in [`docs/requirements/metrics.md`](metrics.md).
- **Rationale**: Ensure objective measurement that does not rely on LLM self-reporting.
- **Source**: `docs/experiments/experiment-design.md`, `docs/risks/rq-scope-falsifiability.md`.
- **Priority**: Must.
- **Dependencies**: Versioned metrics specification exists in [`docs/requirements/metrics.md`](metrics.md).

### FR-7 — Testability gate

- **Statement**: The evaluation workflow shall capture build and unit-test
  execution results and use them as a prerequisite for interpreting other
  quality outcomes.
- **Fit Criterion**: Each trial records build status, test status, and a
  testability indicator; trials failing the gate are flagged.
- **Rationale**: Avoid drawing conclusions from changes that do not build or
  regress tests.
- **Source**: `docs/timeline.md`, `docs/risks/risk-register.md` (R15).
- **Priority**: Must.
- **Dependencies**: Repository tooling availability.

### FR-8 — Prompt-variation experiment support

- **Statement**: The evaluation workflow shall support a prompt-variation
  dataset (multiple paraphrases per intent) and compute a verdict consistency
  measure.
- **Fit Criterion**: Results include a consistency ratio per intent across a
  fixed set of paraphrase styles.
- **Rationale**: Evaluate robustness to prompt variation (RQ3).
- **Source**: `docs/experiments/experiment-design.md`.
- **Priority**: Should.
- **Dependencies**: FR-1.

### FR-9 — Execution trace capture

- **Statement**: The system shall capture and persist trace information for
  each execution so developers can reproduce, debug, and group multiple runs
  for the same problem.
- **Fit Criterion**: Each execution is recorded with an execution identifier
  tied to an issue/feature, repository identifier, code revision identifiers
  (before/after and any created commit), user approval/consent status for
  applying changes, and the prompts used (user-supplied and internal).
- **Rationale**: Support debugging, reproducibility, and audit.
- **Source**: `docs/risks/risk-register.md` (reproducibility/validation risks).
- **Priority**: Must.
- **Dependencies**: NFR-3, NFR-8.

### FR-10 — Skill/tool export for agent runtimes

- **Statement**: The system shall expose its capabilities as reusable
  tools/skills that can be invoked from other agent runtimes.
- **Fit Criterion**: The system publishes machine-readable tool interfaces and
  can be registered/invoked from at least two different clients/runtimes
  without per-capability custom glue code.
- **Rationale**: Enable integration with IDE assistants and external
  tool-calling frameworks.
- **Source**: `docs/PROPOSAL.md` (Integrations section).
- **Priority**: Should.
- **Dependencies**: NFR-7.

### FR-11 — Contextual help and guidance

- **Statement**: The system shall provide contextual guidance to developers
  based on the current task intent and quality focus.
- **Fit Criterion**: For a given execution, outputs include actionable next
  steps and clearly state assumptions, gaps, and suggested inputs.
- **Rationale**: Improve developer usability and trust.
- **Source**: `docs/PROPOSAL.md` (RQ4 Developer Control), `docs/risks/risk-register.md`.
- **Priority**: Should.
- **Dependencies**: FR-1.

### FR-12 — Proactive assistance

- **Statement**: The system shall proactively surface relevant quality
  considerations and workflow actions when signals indicate risk or missing
  prerequisites.
- **Fit Criterion**: When risk/prerequisite signals are detected, the system
  proposes mitigations and follow-up actions without requiring an additional
  user prompt.
- **Rationale**: Reduce failure modes in legacy modernization workflows.
- **Source**: `docs/risks/risk-register.md`.
- **Priority**: Could.
- **Dependencies**: FR-13.

### FR-13 — Repository- and configuration-aware recommendations

- **Statement**: The system shall generate recommendations informed by the
  developer’s repository context and local configuration.
- **Fit Criterion**: Recommendations adapt to detected repository/tooling
  context and state which local signals/configuration drove the
  recommendation.
- **Rationale**: Make guidance relevant and actionable for the current repo.
- **Source**: `docs/PROPOSAL.md` (workflow + integrations).
- **Priority**: Should.
- **Dependencies**: NFR-3, NFR-4.

### FR-14 — Static analysis integration (SonarQube / Roslyn)

- **Statement**: The evaluation workflow shall integrate with static-analysis systems (including SonarQube and/or Roslyn analyzers) to compute and report objective quality signals for code changes.
- **Fit Criterion**: For each execution/trial, the workflow can produce and persist the static-analysis outputs required by the metrics specification under a pinned ruleset/configuration (see [`docs/requirements/metrics.md`](metrics.md)).
- **Rationale**: Provide tool-verifiable evidence and enable richer dependent variables than LLM self-reporting.
- **Source**: `docs/experiments/experiment-design.md`, `docs/risks/rq-scope-falsifiability.md`.
- **Priority**: Must.
- **Dependencies**: NFR-2.

### FR-15 — Quality metric collection and external enrichment

- **Statement**: The evaluation workflow shall collect and persist a set of success/failure quality metrics per execution, and may enrich them by fetching additional data from external systems when available.
- **Fit Criterion**: Each execution/trial records the supplementary/enrichment metrics defined in [`docs/requirements/metrics.md`](metrics.md), including explicit missing markers and provenance for externally retrieved values.
- **Rationale**: Support multi-dimensional evaluation and better developer feedback, while remaining robust across repository toolchains.
- **Source**: `docs/PROPOSAL.md` (Metrics, CI/CD hooks), `docs/risks/risk-register.md`.
- **Priority**: Should.
- **Dependencies**: FR-9, NFR-1, NFR-2.

---

## 8. Non-Functional Requirements (Volere shells)

### NFR-1 — Reproducibility and auditability

- **Statement**: Experiment runs shall be repeatable and auditable.
- **Fit Criterion**: Each trial records model identifier, key generation
  parameters (e.g., temperature/seed where supported), configuration, and raw
  outputs sufficient to re-run and verify the result.
- **Rationale**: Required for credible empirical results.
- **Source**: `docs/experiments/experiment-design.md`, `docs/PROPOSAL.md` (Threats to Validity).
- **Priority**: Must.
- **Dependencies**: NFR-8.

### NFR-2 — Measurement validity

- **Statement**: Measurement instruments shall be fit for purpose for source
  code and remain stable across runs.
- **Fit Criterion**: Static-analysis rulesets and any similarity models are
  versioned/pinned and documented; changes in instrumentation are traceable.
- **Rationale**: Avoid invalid conclusions due to measurement drift.
- **Source**: `docs/PROPOSAL.md` (Threats to Validity), `docs/risks/risk-register.md`.
- **Priority**: Must.
- **Dependencies**: FR-6.

### NFR-3 — Data privacy and licensing compliance

- **Statement**: The study shall avoid leaking proprietary or personal data
  and shall respect corpus licensing.
- **Fit Criterion**:
  - The tool does not collect or store additional telemetry/analytics data
    beyond what is required for intended operation (e.g., execution traces,
    experiment logs, and user-provided inputs explicitly supplied to the
    workflow).
  - The primary corpus is public-by-default; if private data is used, a
    documented redaction + access-control policy is followed and only
    aggregated/redacted artifacts are published.
  - Users are explicitly informed that LLM providers (especially cloud
    services) may have their own data retention/training policies and that the
    tool cannot guarantee third-party storage behavior.
- **Rationale**: Preserve compliance, ethics, and reproducibility.
- **Source**: `docs/risks/experiment-data-privacy.md`, `docs/risks/risk-register.md` (R4).
- **Priority**: Must.
- **Dependencies**: FR-4, FR-9.
- **Conflicts**: Potential tension with FR-9/NFR-8 (logging) — must minimize
  stored data and apply access controls/redaction.

### NFR-4 — Prompt-ingestion safety

- **Statement**: Retrieved issue/PR text shall be treated as untrusted input
  and must not be allowed to override system instructions.
- **Fit Criterion**: The workflow includes an explicit rule to ignore
  instruction-like content from external artifacts and logs all sources.
- **Rationale**: Prevent prompt injection and unsafe instruction following.
- **Source**: `docs/risks/risk-register.md` (R14).
- **Priority**: Must.
- **Dependencies**: FR-4.

### NFR-5 — Extensibility

- **Statement**: The system shall be extensible to new taxonomies and quality
  dimensions without re-architecting the pipeline.
- **Fit Criterion**: New taxonomy datasets can be added and selected via
  configuration; outputs reflect the new taxonomy concepts.
- **Rationale**: Support future research extensions and broader NFR coverage.
- **Source**: `docs/PROPOSAL.md` (Future Work).
- **Priority**: Should.
- **Dependencies**: FR-3.

### NFR-6 — Usability and clarity

- **Statement**: Outputs shall be structured and clear enough for developers
  to understand trade-offs and next actions.
- **Fit Criterion**: Explanations consistently include rationale, risks, and
  test recommendations.
- **Rationale**: Improve adoption and interpretability.
- **Source**: `docs/PROPOSAL.md` (RQ4), `docs/risks/risk-register.md`.
- **Priority**: Should.
- **Dependencies**: FR-11.

### NFR-7 — Portability

- **Statement**: The artifact and evaluation scripts shall be runnable in
  common developer environments.
- **Fit Criterion**: Documented setup works on Windows and Unix-like systems;
  containerized execution is supported for local reproducibility.
- **Rationale**: Support replication and developer onboarding.
- **Source**: `README.md`, `docs/PROPOSAL.md`.
- **Priority**: Should.
- **Dependencies**: Local environment/tooling availability.

### NFR-8 — Traceability and provenance

- **Statement**: Executions shall be traceable end to end so outcomes can be
  audited and reproduced.
- **Fit Criterion**: Execution records allow a reviewer to determine (a) which
  repository and revision were used, (b) what prompts were used externally and
  internally, (c) what changes were proposed/applied (including commit
  identifiers when applicable), (d) whether the user approved applying code
  changes, and (e) how multiple executions relate to the same issue/feature.
- **Rationale**: Enable audit, reproduction, and debugging across runs.
- **Source**: `docs/risks/risk-register.md` (validation/reproducibility risks).
- **Priority**: Must.
- **Dependencies**: FR-9.

---

## 9. Open Items (TBD)

- Validate the initial priorities (Must/Should/Could) with the
  supervisor/research plan and adjust based on study scope.
- Requirement sources can be made more granular by linking to exact proposal
  sections once the paper structure is finalized.
