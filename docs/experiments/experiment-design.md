# Experiment Design

---

## Summary Table

| RQ | Method | Baseline | Primary Metric | Statistical Test | Min N | Pass Criterion |
|---|---|---|---|---|---|---|
| RQ2 | Within-subjects (paired supervised vs. prompt-only per issue) | Zero-shot, same LLM and run protocol | Structural improvement delta | Wilcoxon signed-rank (paired) | 3-5 sets × 10 issues (paired supervised vs. baseline) = 30-50 pairs | median improvement ≥ 10 pp; target p < 0.05 |
| RQ3 | Within-subjects (10 paraphrases per task set) | Zero-shot, same 10 paraphrases over the same repository/issue-anchored task | Verdict consistency ratio | McNemar (paraphrase-level) + descriptive consistency gap | 3-5 sets × 10 anchored tasks = 30-50 observations | Consistency ≥ 0.80 and supervised > baseline |
| RQ4 | Within-subjects (paired supervised vs. prompt-only) on legacy corpus | Prompt-only on same legacy hotspot issues | Structural improvement delta on legacy-only subset | Wilcoxon signed-rank (paired) | 3-5 legacy sets × 10 issues (paired supervised vs. baseline) = 30-50 pairs | median improvement > 0 on legacy corpus; target p < 0.05 |

RQ1 remains in the project as an artifact qualification question (knowledge base design and traceability), but it is not part of the controlled experiment matrix.

### Practical v1 Run Budget (Simplified)

To keep execution feasible, v1 uses a low-cost repeated-set protocol:

- A **set** is a fixed bundle of 10 paired comparisons over the same repository/issue-anchored software engineering tasks across supervised and baseline.
- Run **3 sets minimum**; run **up to 5 sets** if time/compute allows.
- Within each set, keep prompt order, model configuration, and evaluation pipeline identical across conditions.
- Report both per-set results and pooled results (30-50 paired observations total).

---

## Core Metrics (Lean Protocol)

Primary and supporting metrics for v1 claims:

- Structural improvement delta (primary)
- Cognitive complexity delta
- Requirements coverage ratio
- Readability proxy delta
- Duplication delta
- Code smell delta by smell family

Pillar alignment:

- Design quality / maintainability: structural improvement delta.
- Structural load: cognitive complexity.
- Intent adherence: requirements coverage.
- Readability: readability proxy.
- Structural debt hygiene: duplication + smells.

Additional metrics for future implementation are tracked separately in `docs/requirements/metrics-future.md`.

---

## RQ2 — Structural Improvement Effectiveness

**Null hypothesis H₀²**: structural improvement under supervised generation is not greater than under zero-shot generation.

**Procedure**:
1. Select 3-5 sets x 10 issues with fixed repository/issue anchoring.
2. For each issue, run supervised vs. zero-shot conditions under matched seeds.
3. Compute structural-violation counts before and after each generated change using the same pre-registered local strategy bundle and mapping profile.
4. Compute per-condition reduction rate `delta` using the pre-registered M-1 definition.
5. Apply Wilcoxon signed-rank test on paired `delta` values (supervised vs. baseline) over 30-50 pairs; report median improvement in percentage points.
6. Report secondary DVs with Holm correction for multiple comparisons.

**Why structural static analysis over BERTScore as primary**: BERTScore measures semantic similarity to a reference; it cannot distinguish between code that *looks* similar and code that actually improves structural quality. Static analysis counts are objective, tool-verifiable, and independent of LLM self-reporting.

---

## RQ3 — Verdict Robustness Across Prompt Variations

**Null hypothesis H₀³**: Verdict consistency ratio under supervised generation ≤ verdict consistency ratio under zero-shot generation.

**Procedure**:
1. Select **3-5 task sets**, each composed of 10 software engineering tasks anchored to a specific repository/issue pair.
2. For each anchored task, produce **10 human-authored paraphrases** that preserve the same repository/issue context and requested change:
   - Formal specification style ("The system shall…")
   - Casual bug report ("This thing breaks when…")
   - Imperative command ("Refactor X to do Y")
   - Passive description ("X is not working because…")
   - Non-native speaker phrasing (simplified vocabulary, direct translation patterns)
3. Run each paraphrase through the supervised agent and the zero-shot baseline while keeping repository, issue, code revision, and evaluation pipeline fixed.
4. Compute verdict consistency ratio = (trials agreeing with majority verdict) / 10 per anchored task.
5. Apply McNemar's test on paraphrase-level paired verdict agreement (supervised vs. baseline), and report the consistency-ratio gap descriptively per set.

**Paraphrase methodology**: internal paraphrase protocol (WIP).

---

## RQ4a — Configuration Effectiveness

**Null hypothesis H₀⁴ᵃ**: Verdict distribution and structural-improvement delta are independent of the `strictness` configuration value.

**Conditions / levels**:
- `strictness=low`: permissive supervisor; emits guidance with minimal rejection/escalation.
- `strictness=medium`: default supervisor setting and **reference baseline** for the configuration study.
- `strictness=high`: conservative supervisor; applies the strongest rejection/escalation thresholds before allowing a generation to proceed.

**Outcome measures**:
1. **Primary**: verdict distribution across `{accept, revise, reject}` per run.
2. **Secondary**: structural-improvement delta relative to the issue's pre-change baseline, using the same strategy bundle and the pre-registered M-1 delta definition.
3. **Secondary**: acceptance rate (`accept` / total runs) and escalation rate (`reject` / total runs).
4. **Secondary**: cognitive complexity, requirements coverage, readability, duplication, and smell deltas.

**Procedure**:
1. Select **3-5 issue sets**, one intent per set, using the same issue-selection criteria declared for the main supervised study.
2. For each set, execute the supervised pipeline under all three `strictness` levels: `low`, `medium`, and `high`.
3. Run **10 repeated trials per set per level** using the same seed schedule and LLM configuration, varying only `strictness`.
4. Record the final supervisor verdict (`accept`, `revise`, `reject`) and the resulting structural-improvement delta for each run.
5. Treat `strictness=medium` as the pre-declared baseline for pairwise follow-up comparisons (`low` vs `medium`, `high` vs `medium`).

**Sample size**: **3-5 sets × 10 repeated runs × 3 levels = 90-150 total runs**; for pairwise repeated-measures comparisons against the `medium` baseline, this yields **30-50 paired observations** per comparison.

**Planned statistical tests**:
- For the 3-level verdict distribution: **chi-square test of independence** on the aggregated contingency table of verdict × `strictness`; if any expected cell count is < 5, use **Fisher's exact test** instead.
- For repeated-measures comparison of structural-improvement delta across the three levels: **Friedman test** by set/run block.
- If the Friedman test is significant, run post-hoc **Wilcoxon signed-rank** tests for `low` vs `medium` and `high` vs `medium`, with Holm correction.

**Pass criterion**: reject H₀⁴ᵃ only if verdict distribution differs significantly by `strictness` and at least one non-default level shows a practically meaningful change versus `medium` (≥ 10 percentage-point change in acceptance rate or a positive median structural-improvement delta).

---

## RQ4 — Legacy-Corpus Effectiveness

**Null hypothesis H₀⁴**: On the legacy-only corpus, structural improvement under supervised generation is not greater than under prompt-only generation.

**Procedure**:
1. Curate **3-5 legacy sets**, each with 10 issues from repositories with structural debt indicators (age, low test coverage, and elevated code-smell/complexity burden).
2. For each issue, run supervised and prompt-only conditions as paired comparisons.
3. Run the same pre-registered local strategy bundle used in RQ2 and record structural delta per issue using the pre-registered M-1 definition.
4. Apply Wilcoxon signed-rank test on paired `delta` values over the legacy-only subset; report median improvement in percentage points and Cohen's d.
5. Compare the legacy-only effect size against the broader RQ2 corpus descriptively to determine whether legacy tasks appear more or less responsive to knowledge-base-guided supervision.
6. Report whether secondary structural metrics move in the same direction as primary structural-improvement deltas.

**Rationale**: RQ4 treats legacy software as a domain-focused subset of study subjects. This keeps the question distinct from RQ2 by asking whether the supervisor remains effective when evaluation is restricted to legacy codebases with known structural debt.

---

## Scope Exclusions

The following are explicitly **out of scope** for the primary study. They may
appear as future work:

| Exclusion | Reason |
|---|---|
| Full automated test execution (pass@k) | Requires runnable test harness per repository |
| Ontology vs. knowledge base comparison | Parallel OWL/RDF pipeline out of scope |
| Multi-language evaluation (Python, Java, TypeScript) | C# corpus sufficient for v1 claims; external validity threat noted |
| Longitudinal developer productivity study | Requires long-term organizational access and ethics approval |
| Prompt engineering ablation (CoT vs. ReAct vs. RAG) | Supervisor architecture is the artifact under study, not prompt technique |

---

## References

