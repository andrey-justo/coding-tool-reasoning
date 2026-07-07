# Research Questions Scope and Falsifiability

## Basic RQs

Use these for early committee discussions, grant applications, or the
introduction section of a paper. They communicate intent without committing
to specific thresholds.

**RQ1 â€“ knowledge base Encoding for Planning**
> How should the SWE knowledge base encode SRP/OCP/DIP and legacy-modernization
> patterns to support planning for AI-assisted C# legacy refactoring?

**RQ2 â€“ Structural Improvement Effectiveness**
> For AI-assisted code-generation tools, does knowledge-base-guided supervision
> improve structural quality compared with a prompt-only baseline?

**RQ3 â€“ Verdict Robustness Across Prompt Variations**
> For AI-assisted code-generation tools, does knowledge-base-guided supervision
> improve consistency across semantically equivalent prompt paraphrases for
> the same repository/issue-anchored software engineering task?

**RQ4 â€“ Legacy-Corpus Structural Effectiveness**
> For AI-assisted code-generation tools applied to legacy software tasks,
> does knowledge-base-guided supervision improve structural quality compared
> with a prompt-only baseline?

---

## RQ Structure Note

RQ1 is a **design question** about the structure of the knowledge base artifact.
It is answered through the proposed knowledge base schema, ISO 25010 traceability,
and its ability to support planning for C# legacy refactoring tasks (should we include other programming languages???).

RQ2â€“RQ4 are the **empirical evaluation questions**. A null result in RQ2 would
weaken the practical value of the supervisor, but it would not logically
invalidate RQ3 or RQ4. Instead, RQ3 would still test robustness of the
supervisor's behavior under paraphrase, and RQ4 would still test whether the
same supervision approach has a stronger or weaker effect when the study is
restricted to legacy-software tasks as a domain-focused subject set.

---

## Complex RQs (Falsifiable)

Use these for the Methods section, ethics/IRB submissions, and statistical
analysis planning. RQ1 is artifact-design oriented; RQ2-RQ4 are framed as
falsifiable evaluation questions with a null hypothesis, effect threshold,
and baseline.

**RQ1 â€“ knowledge base Encoding for Planning**
> How should the SWE knowledge base encode SRP/OCP/DIP and legacy-modernization
> patterns so that planning outputs expose explicit modifiability constraints,
> related design steps, and traceable knowledge base entities for C# legacy
> refactoring performed with AI-assisted code-generation tools?

- **Design criteria**: the knowledge base must (a) map SRP/OCP/DIP and legacy-modernization patterns to explicit nodes/relations, (b) preserve traceability to ISO 25010 Maintainability/Modifiability where relevant, and (c) support plan outputs with explicit steps and linked knowledge base entities.
- **Evidence**: knowledge base schema, mapping tables, representative planning outputs, and pilot review of whether the generated plans expose the intended constraints.

**RQ2 â€“ Structural Improvement Effectiveness**
> For AI-assisted code-generation tools, does knowledge-base-guided supervision
> improve structural quality by a statistically greater amount than a
> prompt-only baseline, with a target improvement of at least 10 percentage
> points and Cohen's d â‰¥ 0.5?

- **Hâ‚€Â²**: structural-improvement delta is equal between the supervised and prompt-only conditions (d < 0.5).
- **Baseline**: Direct LLM call with a well-crafted zero-shot prompt (no `IntentPlanner`, no `ExplanationService`); represents the best current practice without a supervisor.
- **Note**: This replaces the earlier "acceptable verdict proportion" metric. Structural static-analysis counts provide objective ground truth that does not rely on LLM self-reporting.

**RQ3 â€“ Verdict Robustness Across Prompt Variations**
> For AI-assisted code-generation tools, does knowledge-base-guided supervision
> produce the same `overall_verdict` for at least 80 % of semantically
> equivalent but syntactically varied paraphrases of the same
> repository/issue-anchored software engineering task?

- **Hâ‚€Â³**: Supervised consistency ratio â‰¤ prompt-only consistency ratio.
- **Baseline**: Zero-shot, same repository/issue-anchored task, same paraphrase set.
- **Paraphrases**: formal spec, casual bug report, imperative, passive, non-native phrasing.

**RQ4 â€“ Legacy-Corpus Structural Effectiveness**
> For AI-assisted code-generation tools applied to legacy software tasks,
> does knowledge-base-guided supervision improve structural quality by a
> statistically greater amount than a prompt-only baseline, with Cohen's d â‰¥ 0.5?

- **Hâ‚€â´**: On the legacy-only corpus, structural-improvement delta is equal between the supervised and prompt-only conditions (d < 0.5).
- **Baseline**: Prompt-only generation on the same legacy corpus, with identical repository/issue-anchored tasks and LLM configuration.
- **Interpretation**: RQ4 is a domain-focused effectiveness question over the legacy subset of study subjects rather than a mechanism question about pattern adoption.
- **Legacy corpus definition**: repositories selected for high change frequency, low test coverage, and documented structural debt.
- **Measurement**: static-analysis structural count (language-specific local strategy bundles) before and after the generated change on the legacy-only subset, using the delta definition in [`docs/requirements/metrics.md`](../requirements/metrics.md).

---

## Key References

- Popper, K. (1959). *The Logic of Scientific Discovery*. Routledge.
- Wohlin, C., Runeson, P., HÃ¶st, M., Ohlsson, M. C., Regnell, B., & WesslÃ©n, A. (2012). *Experimentation in Software Engineering*. Springer.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum.
- Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design Science in Information Systems Research. *MIS Quarterly*, 28(1), 75â€“105.

