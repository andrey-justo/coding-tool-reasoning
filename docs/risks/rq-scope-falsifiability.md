# Risk: RQ Scope and Falsifiability

**Severity**: High  
**Blocks**: PhD committee acceptance; statistical analysis design; experiment planning  

> Full experiment procedures, null hypotheses, baselines, and statistical
> tests for each RQ:
> [`docs/experiments/experiment-design.md`](../experiments/experiment-design.md)

---

## Why This Risk Exists

A research question is **falsifiable** if it is possible, in principle, for
the evidence to show that the answer is *no*. Broad RQs — those that ask
"does X help?" without specifying *how much*, *compared to what*, and *under
what conditions* — cannot be cleanly rejected. A committee will interpret this
as the researcher designing an experiment that cannot fail, which is not
science (Popper, 1959).

A falsifiable RQ must satisfy:
1. **Null hypothesis** — the default assumption that could be disproven.
2. **Effect threshold** — the minimum effect size that is practically meaningful.
3. **Comparison condition** — the named baseline.

---

## Basic RQs

Use these for early committee discussions, grant applications, or the
introduction section of a paper. They communicate intent without committing
to specific thresholds.

**RQ1 – SOLID-Guided NFR Representation**
> How can the SWE taxonomy represent SOLID-principle adherence (SRP, OCP, DIP)
> as modifiability NFR constraints (ISO 25010: Maintainability → Modifiability)
> for LLM-assisted legacy code refactoring?

**RQ2 – SOLID Violation Reduction**
> Does a taxonomy-guided supervisor agent reduce SOLID violation density in
> LLM-generated legacy code changes compared to a prompt-engineering-only
> baseline?

**RQ3 – Verdict Robustness Across Prompt Variations**
> Is the SOLID-violation detection verdict consistent across semantically
> equivalent prompt variations for the same legacy code hotspot?

**RQ4 – Legacy System Modifiability Impact**
> Does the taxonomy-guided supervisor agent guide LLMs toward applying
> Strangler Fig and Anti-Corruption Layer patterns that reduce SOLID violation
> density in legacy hotspots?

---

## Complex RQs (Falsifiable)

Use these for the Methods section, ethics/IRB submissions, and statistical
analysis planning. Each has a null hypothesis, effect threshold, and baseline.

**RQ1 – SOLID-Guided NFR Representation**
> Does the SWE taxonomy-guided supervisor agent produce LLM-generated legacy
> code with a statistically lower SOLID violation smell count — measured by
> static analysis (`smell_god_object`, `smell_tight_coupling`, `smell_large_class`,
> `smell_mixed_concerns`, `legacy_concrete_dependency`, `legacy_change_cascade`)
> — compared to a prompt-engineering-only baseline (same prompt, no taxonomy
> injection, `relationship_depth=0`), with Cohen's d ≥ 0.5?

- **H₀¹**: Taxonomy-guided generation does not produce lower SOLID violation count than the prompt-engineering-only baseline (d < 0.5).
- **Baseline**: Same LLM prompt with `nfr_focus=[]`, `relationship_depth=0`, `temperature=0` — no taxonomy enrichment.
- **Measurement**: Static-analysis smell count (SonarQube + Roslyn Analyzers for C#) before and after the generated change. Delta = (before − after) / before.

**RQ2 – SOLID Violation Reduction**
> Does the taxonomy-based supervisor agent produce LLM-generated legacy code
> changes with a statistically greater reduction in SOLID violation smell count
> (≥ 10 percentage-point delta) compared to a prompt-engineering-only baseline,
> with Cohen's d ≥ 0.5?

- **H₀²**: SOLID violation count reduction is equal between the supervised and prompt-only conditions (d < 0.5).
- **Baseline**: Direct LLM call with a well-crafted zero-shot prompt (no `IntentPlanner`, no `ExplanationService`); represents the best current practice without a supervisor.
- **Note**: This replaces the earlier "acceptable verdict proportion" metric. The SOLID count provides objective ground truth that does not rely on LLM self-reporting.

**RQ3 – Verdict Robustness Across Prompt Variations** *(two operationalizations)*

*RQ3a – Reproducibility*:
> Does the supervisor agent reduce the std-dev of SOLID violation count delta
> across N=30 repeated trials (same intent, same LLM settings) by ≥ 20 %
> compared to the prompt-engineering-only baseline?

- **H₀³ᵃ**: Supervised std-dev of smell-count delta ≥ prompt-only std-dev.
- **Baseline**: Zero-shot, same LLM, same seed sequence.

*RQ3b – Prompt Robustness*:
> Does the supervisor agent produce the same `overall_verdict` for ≥ 80 % of
> 5 semantically equivalent but syntactically varied paraphrases of the same
> legacy hotspot description?

- **H₀³ᵇ**: Supervised consistency ratio ≤ prompt-only consistency ratio.
- **Paraphrases**: formal spec, casual bug report, imperative, passive, non-native phrasing.

**RQ4 – Legacy System Modifiability Impact**
> Does the taxonomy-guided supervisor agent produce code changes that apply
> Strangler Fig or Anti-Corruption Layer patterns (as classified by the
> legacy taxonomy) in statistically more cases than prompt-only generation,
> with Cohen's d ≥ 0.5, and does this correlate with a reduction in SRP, OCP,
> and DIP violation density?

- **H₀⁴**: Pattern adoption rate (Strangler Fig / ACL) under supervised condition is not higher than under the prompt-only baseline (d < 0.5).
- **Baseline**: Prompt-only generation on the same legacy corpus (repositories selected for high change frequency, low test coverage, and documented SOLID debt).
- **Legacy taxonomy**: `legacy_code_nodes.csv` — nodes: `legacy_hotspot`, `legacy_god_service`, `legacy_missing_abstraction`, `legacy_concrete_dependency`, `legacy_change_cascade`, `pattern_strangler_fig`, `pattern_anti_corruption_layer`.
- **Pattern detection**: Structural classifier or code review rubric identifying Strangler Fig / ACL introduction; corroborated by DIP violation count drop.

---

## Key References

- Popper, K. (1959). *The Logic of Scientific Discovery*. Routledge.
- Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., & Wesslén, A. (2012). *Experimentation in Software Engineering*. Springer.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum.
- Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design Science in Information Systems Research. *MIS Quarterly*, 28(1), 75–105.
