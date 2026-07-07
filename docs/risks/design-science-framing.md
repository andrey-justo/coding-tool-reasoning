# Design Science Framing

DSR defines seven guidelines. The table below maps each one to this project:

| DSR Guideline | How This Project Addresses It |
|---|---|
| **G1 â€“ Design as an Artifact** | The artifact is the `SWE-NFR-MCP` supervisor agent: a two-stage MCP server with configurable SWE knowledge bases that mediates between natural language and LLM code generation. |
| **G2 â€“ Problem Relevance** | LLM code generators can produce syntactically correct but structurally degraded code when applied to legacy systems. Structural violations (including SOLID-related signals) correlate with change risk, regression probability, and modernization difficulty. Developers lack a configurable tool to enforce structural-quality-aware generation in AI-assisted legacy refactoring (documented in Introduction / Problem Statement). |
| **G3 â€“ Design Evaluation** | RQ1â€“RQ4 operationalize evaluation as a funnel. RQ1 is the artifact-design question: how the knowledge base should encode SRP/OCP/DIP and legacy-modernization patterns so planning outputs expose explicit constraints and linked entities for AI-assisted C# legacy refactoring. RQ2 measures structural-improvement effectiveness through local static-analysis strategy bundles. RQ3 measures verdict consistency across paraphrased prompts for the same repository/issue-anchored software engineering task. RQ4 measures whether the same supervision approach improves structural quality on a legacy-only corpus. |
| **G4 â€“ Research Contributions** | Four new artifacts: (a) the supervisor agent architecture, (b) the plug-in SOLID-aligned SWE knowledge base framework, (c) a structural static-analysis evaluation methodology with configurable local strategy bundles (decoupling quality measurement from LLM self-reporting), (d) the prompt-robustness evaluation dimension for LLM-assisted SE over repository/issue-anchored software engineering tasks. |
| **G5 â€“ Research Rigor** | Empirical study: 3â€“5 sets Ã— 10 issues/PRs all analysing metrics for each RQ (30â€“50 observations per RQ). Metrics: M-1 (structural improvement delta), M-2 (testability gate), cyclomatic complexity, test coverage, duplication, security findings. Survey: N â‰¥ 20 developers for RQ4 trust/control validation. Analysis: paired statistical hypothesis testing at Î± = 0.05 with Bonferroni correction. |
| **G6 â€“ Design as a Search Process** | Three design cycles (see below). Each cycle refines the artifact based on evaluation feedback. |
| **G7 â€“ Communication of Research** | Dual audience: (a) researchers â€” positioned against SWE-bench, SWE-agent, Plan4Code; (b) practitioners â€” VS Code MCP integration, CI/CD hooks, configurable YAML. |

---

## Three Design Cycles

DSR requires iterative design. This project runs three explicit cycles:

### Cycle 1 â€“ Relevance Cycle
**Input**: Problem environment (practitioners, LLMs, SE quality models).  
**Activity**: Interview or survey developers to confirm that NFR misalignment
in LLM-generated code is a real, recurring pain point. Collect issue-tracker
evidence of reliability/maintainability regressions introduced by AI-assisted
changes.  
**Output**: Validated problem statement; initial ISO 25010 attribute selection;
corpus of 5 open-source repositories.  
**Deliverable**: Problem statement section + corpus description (Phase 1 of Timeline).

### Cycle 2 â€“ Design Cycle (Buildâ€“Evaluate loop)
**Input**: Cycle 1 problem statement; ISO 25010 knowledge base mapping.  
**Activity**: Build Stage 1 (IntentPlanner) â†’ evaluate knowledge base encoding and planning output quality (RQ1 pilot) â†’ refine knowledge base depth and
`relationship_depth` config â†’ build Stage 2 (ExplanationService) â†’ evaluate verdict consistency (RQ3
pilot) â†’ fix `temperature=0` / CodeBERT scorer â†’ iterate.  
**Output**: Stable `SWE-NFR-MCP` prototype with reproducible experiments.  
**Deliverable**: Implementation Gaps resolved (Phase 2 of Timeline).

### Cycle 3 â€“ Rigor Cycle
**Input**: Stable prototype; full empirical corpus.  
**Activity**: Full RQ1â€“RQ4 experiment runs; statistical analysis; developer
trust survey; comparison against zero-shot baseline.  
**Output**: Quantitative evidence for or against the novelty claims.  
**Deliverable**: Evaluation section + Threats to Validity + paper (Phases 3â€“5 of Timeline).

---

## Novelty Statement (draft for Introduction)

> *"To our knowledge, this is the first work to (a) propose a knowledge-base-guided
> supervisor agent that enforces structural-quality constraints (including SOLID-related constraints such as SRP, OCP, DIP) on LLM-assisted legacy code
> generation, and (b) operationalize verdict consistency under prompt
> variation for the same repository/issue-anchored software engineering task.
> Together, these contributions advance the state of the art beyond correctness-only
> benchmarks (SWE-bench, HumanEval) and beyond plan-and-execute agents that
> lack explicit NFR supervision (SWE-agent, OpenHands), by introducing
> static-analysis-grounded quality measurement that does not depend on LLM
> self-reporting."*

This statement must be validated against a systematic literature review before
submission (Phase 1 deliverable).

---

## Differences from Plan4Code (ICSE 2026)

This project is inspired by Plan4Code but makes distinct contributions:

| Dimension | Plan4Code (ICSE 2026) | This Work |
|---|---|---|
| Knowledge representation | Static OWL/RDF ontologies | Configurable CSV knowledge bases; plug-in by directory drop |
| Supervisor configurability | Not addressed | `swe_mcp_config.yaml` with strictness, depth, stage control |
| Prompt-variation robustness | Not measured | RQ3: verdict consistency across paraphrased requests for the same repository/issue-anchored task |
| Integration interface | Standalone | MCP stdio server; composable with GitHub MCP, filesystem tools, VS Code Copilot |
| Legacy system focus | Not addressed | Structural-debt smells in legacy knowledge base (`legacy_god_service`, `legacy_missing_abstraction`, `legacy_concrete_dependency`, `legacy_change_cascade`); Strangler Fig (OCP), ACL (DIP) patterns; structural-improvement delta as primary metric |

---

## Action Checklist

- [ ] Add explicit DSR methodology section to `PROPOSAL.md` (between Related
  Work and Workflow), referencing Hevner et al. (2004) and mapping all seven
  guidelines.
- [ ] Add the three design cycles to the Timeline section, replacing the
  generic phases with cycle-labeled milestones.
- [ ] Conduct a systematic literature review (Phase 1) to validate the novelty
  statement â€” specifically confirm no prior work measures prompt-variation
  robustness under a quality-model constraint for repository/issue-anchored
  software engineering tasks.
- [ ] Write a short "Design Decisions" section explaining why CSV knowledge bases
  were chosen over OWL/RDF ontologies (see `docs/risks/avoiding-ontologies.md`).
- [ ] Add `ISO25010Characteristic` column to all knowledge base CSVs so RQ1 can
  compute alignment against named ISO 25010 sub-characteristics directly.

---

## Key References

- Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design Science in
  Information Systems Research. *MIS Quarterly*, 28(1), 75â€“105.
- Wieringa, R. (2014). *Design Science Methodology for Information Systems and
  Software Engineering*. Springer.
- Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2007). A
  Design Science Research Methodology for Information Systems Research.
  *Journal of Management Information Systems*, 24(3), 45â€“77.
- ISO/IEC 25010:2011. *Systems and software engineering â€” Systems and software
  quality requirements and evaluation (SQuaRE)*.

