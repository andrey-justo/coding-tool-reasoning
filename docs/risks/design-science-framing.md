# Risk: Design Science Framing / Novelty / Contribution

**Severity**: High  
**Blocks**: PhD qualification; committee acceptance; novelty claim validity  

---

## Why This Risk Is High

Without an explicit Design Science Research (DSR) methodology, a PhD
committee will classify this project as a **software engineering tool**, not a
scientific contribution. Engineering work, however well-executed, is
insufficient for a doctoral thesis unless it is framed within a research
methodology that:

1. Justifies *why* an artifact is the correct form of answer to the research
   problem.
2. Defines evaluation criteria that make the artifact's success or failure
   falsifiable.
3. Positions the contribution within existing knowledge and explains what new
   knowledge is produced.

DSR (Hevner et al., 2004) is the accepted methodology for IS/SE research
where the primary output is a designed artifact. It provides exactly this
framing.

---

## The DSR Framework Applied to This Project

The seminal reference is:

> Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). **Design Science in
> Information Systems Research**. *MIS Quarterly*, 28(1), 75–105.

DSR defines seven guidelines. The table below maps each one to this project:

| DSR Guideline | How This Project Addresses It |
|---|---|
| **G1 – Design as an Artifact** | The artifact is the `SWE-NFR-MCP` supervisor agent: a two-stage MCP server with configurable SWE taxonomies that mediates between natural language and LLM code generation. |
| **G2 – Problem Relevance** | LLM code generators produce syntactically correct but SOLID-violating code when applied to legacy systems; SOLID violations (SRP, OCP, DIP) are directly correlated with change risk, regression probability, and inability to apply Strangler Fig / ACL modernization patterns. Developers lack a tool to enforce SOLID-adherent generation in AI-assisted legacy refactoring (documented in Introduction / Problem Statement). |
| **G3 – Design Evaluation** | RQ1–RQ4 operationalize evaluation. RQ1 and RQ2 measure SOLID violation count delta (static analysis primary) and NFR coverage score (secondary) vs. zero-shot baseline. RQ3 measures verdict consistency across paraphrased prompts. RQ4 measures Strangler Fig / ACL pattern adoption rate and violation delta on a curated legacy corpus. Statistical tests: Wilcoxon signed-rank, Cohen's *d*, Fisher's exact, Bonferroni correction. |
| **G4 – Research Contributions** | Four new artifacts: (a) the supervisor agent architecture, (b) the plug-in SOLID-aligned SWE taxonomy framework, (c) the SOLID violation static-analysis evaluation methodology (decoupling quality measurement from LLM self-reporting), (d) the reproducibility and prompt-robustness evaluation dimensions for LLM-assisted SE. |
| **G5 – Research Rigor** | Empirical study: 5 repositories × 30 issues × 5 trials. Scorers: CodeBERTScore + CodeBLEU. Survey: N ≥ 20 developers. Analysis: statistical hypothesis testing at α = 0.05. |
| **G6 – Design as a Search Process** | Three design cycles (see below). Each cycle refines the artifact based on evaluation feedback. |
| **G7 – Communication of Research** | Dual audience: (a) researchers — positioned against SWE-bench, SWE-agent, Plan4Code; (b) practitioners — VS Code MCP integration, CI/CD hooks, configurable YAML. |

---

## Three Design Cycles

DSR requires iterative design. This project runs three explicit cycles:

### Cycle 1 – Relevance Cycle
**Input**: Problem environment (practitioners, LLMs, SE quality models).  
**Activity**: Interview or survey developers to confirm that NFR misalignment
in LLM-generated code is a real, recurring pain point. Collect issue-tracker
evidence of reliability/maintainability regressions introduced by AI-assisted
changes.  
**Output**: Validated problem statement; initial ISO 25010 attribute selection;
corpus of 5 open-source repositories.  
**Deliverable**: Problem statement section + corpus description (Phase 1 of Timeline).

### Cycle 2 – Design Cycle (Build–Evaluate loop)
**Input**: Cycle 1 problem statement; ISO 25010 taxonomy mapping.  
**Activity**: Build Stage 1 (IntentPlanner) → evaluate plan quality and NFR
coverage (RQ1 pilot) → refine taxonomy depth and `relationship_depth` config
→ build Stage 2 (ExplanationService) → evaluate verdict consistency (RQ2
pilot) → fix `temperature=0` / `seed` / CodeBERT scorer → iterate.  
**Output**: Stable `SWE-NFR-MCP` prototype with reproducible experiments.  
**Deliverable**: Implementation Gaps resolved (Phase 2 of Timeline).

### Cycle 3 – Rigor Cycle
**Input**: Stable prototype; full empirical corpus.  
**Activity**: Full RQ1–RQ4 experiment runs; statistical analysis; developer
trust survey; comparison against zero-shot baseline.  
**Output**: Quantitative evidence for or against the novelty claims.  
**Deliverable**: Evaluation section + Threats to Validity + paper (Phases 3–5 of Timeline).

---

## Novelty Statement (draft for Introduction)

> *"To our knowledge, this is the first work to (a) propose a taxonomy-guided
> supervisor agent that enforces SOLID design principles (SRP, OCP, DIP) as
> configurable Maintainability NFR constraints on LLM-assisted legacy code
> generation, and (b) operationalize two previously unmeasured dimensions of
> LLM-assisted software engineering: output reproducibility under repeated
> intent submission, and verdict consistency under prompt-variation. Together,
> these contributions advance the state of the art beyond correctness-only
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
| Knowledge representation | Static OWL/RDF ontologies | Configurable CSV taxonomies; plug-in by directory drop |
| Supervisor configurability | Not addressed | `swe_mcp_config.yaml` with strictness, depth, stage control |
| Reproducibility evaluation | Not measured | RQ2: variance across N repeated trials; `ReproducibilityReport` |
| Prompt-variation robustness | Not measured | RQ3: consistency across paraphrased requests |
| Integration interface | Standalone | MCP stdio server; composable with GitHub MCP, filesystem tools, VS Code Copilot |
| Legacy system focus | Not addressed | SOLID-violation smells in legacy taxonomy (`legacy_god_service`, `legacy_missing_abstraction`, `legacy_concrete_dependency`, `legacy_change_cascade`); Strangler Fig (OCP), ACL (DIP) patterns; violation delta as primary metric |

---

## Action Checklist

- [ ] Add explicit DSR methodology section to `PROPOSAL.md` (between Related
  Work and Workflow), referencing Hevner et al. (2004) and mapping all seven
  guidelines.
- [ ] Add the three design cycles to the Timeline section, replacing the
  generic phases with cycle-labeled milestones.
- [ ] Conduct a systematic literature review (Phase 1) to validate the novelty
  statement — specifically confirm no prior work measures LLM code generation
  reproducibility or prompt-variation robustness under a quality-model
  constraint.
- [ ] Write a short "Design Decisions" section explaining why CSV taxonomies
  were chosen over OWL/RDF ontologies (see `docs/risks/avoiding-ontologies.md`).
- [ ] Add `ISO25010Characteristic` column to all taxonomy CSVs so RQ1 can
  compute alignment against named ISO 25010 sub-characteristics directly.

---

## Key References

- Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design Science in
  Information Systems Research. *MIS Quarterly*, 28(1), 75–105.
- Wieringa, R. (2014). *Design Science Methodology for Information Systems and
  Software Engineering*. Springer.
- Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2007). A
  Design Science Research Methodology for Information Systems Research.
  *Journal of Management Information Systems*, 24(3), 45–77.
- ISO/IEC 25010:2011. *Systems and software engineering — Systems and software
  quality requirements and evaluation (SQuaRE)*.
