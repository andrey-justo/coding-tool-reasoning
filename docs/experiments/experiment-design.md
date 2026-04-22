# Experiment Design

Links back to RQ definitions: [`docs/risks/rq-scope-falsifiability.md`](../risks/rq-scope-falsifiability.md)

Subject/corpus tracking (repo + issue/commit/PR metadata): [`data/subjects/subject_data.csv`](../../data/subjects/subject_data.csv)
Run-level comparison tracking (baseline vs supervised vs human studies): [`data/subjects/experiment_runs.csv`](../../data/subjects/experiment_runs.csv)

---

## Summary Table

| RQ | Method | Baseline | Primary Metric | Statistical Test | Min N | Pass Criterion |
|---|---|---|---|---|---|---|
| RQ1 | Within-subjects (paired supervised vs. zero-shot per issue) | `IntentPlanner` with `nfr_focus=[]`, `relationship_depth=0`, same LLM, `temperature=0` | SOLID violation count delta (static analysis) | Wilcoxon signed-rank (paired) | 3-5 sets × 10 issues (paired supervised vs. baseline) = 30-50 pairs | median paired improvement > 0; target p < 0.05 |
| RQ2 | Within-subjects (paired supervised vs. prompt-only per issue) | Zero-shot, same LLM and run protocol | SOLID violation count reduction (%) | Wilcoxon signed-rank (paired) | 3-5 sets × 10 issues (paired supervised vs. baseline) = 30-50 pairs | median improvement ≥ 10 pp; target p < 0.05 |
| RQ3a | Within-subjects (10 repeated trials per set) | Zero-shot, same LLM and run protocol | Std-dev of SOLID violation count delta | Wilcoxon signed-rank on per-set variance | 3-5 sets × 10 issues (10 repeats per condition) = 30-50 observations | ≥ 20 % std-dev reduction |
| RQ3b | Within-subjects (10 paraphrases per set) | Zero-shot, same 10 paraphrases | Verdict consistency ratio | McNemar (paraphrase-level) + descriptive consistency gap | 3-5 sets × 10 intents (10 paraphrases per intent) = 30-50 observations | Consistency ≥ 0.80 and supervised > baseline |
| RQ4 | Within-subjects (paired supervised vs. prompt-only) on legacy corpus | Prompt-only on same legacy hotspot issues | Strangler Fig / ACL pattern adoption rate + SRP/OCP/DIP violation delta | Fisher's exact test (pattern rate) + Wilcoxon (paired violation delta) | 3-5 legacy sets × 10 issues (paired supervised vs. baseline) = 30-50 pairs | pattern adoption higher and median violation delta improvement > 0 |

### Practical v1 Run Budget (Simplified)

To keep execution feasible, v1 uses a low-cost repeated-set protocol:

- A **set** is a fixed bundle of 10 paired comparisons (same issues/intents across supervised and baseline).
- Run **3 sets minimum**; run **up to 5 sets** if time/compute allows.
- Within each set, keep prompt order, model configuration, and evaluation pipeline identical across conditions.
- Report both per-set results and pooled results (30-50 paired observations total).

---

## RQ1 — SOLID-Guided NFR Representation

**Null hypothesis H₀¹**: Taxonomy-guided generation does not produce lower SOLID
violation smell count than zero-shot generation.

**Procedure**:
1. Select **3-5 issue sets**, each with 10 issues (30-50 total paired observations). Reuse the same set definitions across RQ1/RQ2 for comparability. Prioritize repositories with known SOLID debt (high LCOM4, high concrete dependency count).
2. For each issue, run two conditions in the same session:
   - *Supervised*: `plan_swe_code_change` → `build_swe_code_context` → LLM code generation → `judge_swe_code_change`.
   - *Baseline*: same LLM prompt with no taxonomy injection (`nfr_focus=[]`, `relationship_depth=0`).
3. For each generated output, run static analysis on the diff:
   - **SonarQube** (open source) or **Roslyn Analyzers** (C#-specific): count SRP, OCP, DIP violation rules triggered.
   - Compute `delta` using the M-1 definition in `docs/requirements/metrics.md` (including the `violations_before = 0` edge cases), and record `absolute_delta`.
4. Secondary metric: Score each output with `ExplanationService` NFR coverage metric (fraction of ISO 25010 sub-characteristics covered in `nfr_impacts`).
5. Apply Wilcoxon signed-rank test on paired deltas across the pooled 30-50 pairs; also report per-set medians.

**Confound controls**:
- Fix `temperature=0` in both conditions.
- Same LLM model and version; document exact model hash/tag.
- Run static analysis with identical ruleset and threshold in both conditions; disable rules unrelated to SOLID.
- Blind scoring: SOLID count computed by automated tool, not human judgment.

---

## RQ2 — SOLID Violation Reduction

**Null hypothesis H₀²**: SOLID violation count reduction under supervised generation is not greater than under zero-shot generation.

**Procedure**:
1. Select the same 3-5 sets × 10 issues from RQ1.
2. For each issue, run supervised vs. zero-shot conditions (identical to RQ1 Step 2).
3. Compute SOLID violation count before and after each generated change using the same static analysis ruleset.
4. Compute per-condition reduction rate `delta` using the M-1 definition in `docs/requirements/metrics.md`.
5. Apply Wilcoxon signed-rank test on paired `delta` values (supervised vs. baseline) over 30-50 pairs; report median improvement in percentage points.

**Implementation**: Wire `_run_supervised_trial` and `_run_baseline_trial` in `src/evaluation/reproducibility_experiment.py` to also invoke the static analysis runner and store `solid_violation_delta` in `TrialResult`.

**Why static analysis over BERTScore as primary**: BERTScore measures semantic similarity to a reference; it cannot distinguish between code that *looks* similar and code that actually *respects* SOLID. Static analysis counts are objective, tool-verifiable, and independent of LLM self-reporting.

---

## RQ3 — Verdict Robustness Across Prompt Variations

**Null hypothesis H₀³**: Verdict consistency ratio under supervised generation ≤ verdict consistency ratio under zero-shot generation.

**Procedure**:
1. Select **3-5 intents** (one per set).
2. For each intent, produce **10 human-authored paraphrases**:
   - Formal specification style ("The system shall…")
   - Casual bug report ("This thing breaks when…")
   - Imperative command ("Refactor X to do Y")
   - Passive description ("X is not working because…")
   - Non-native speaker phrasing (simplified vocabulary, direct translation patterns)
3. Run each paraphrase through the supervised agent and the zero-shot baseline.
4. Compute verdict consistency ratio = (trials agreeing with majority verdict) / 10 per intent.
5. Apply McNemar's test on paraphrase-level paired verdict agreement (supervised vs. baseline), and report the consistency-ratio gap descriptively per set.

**Paraphrase methodology**: internal paraphrase protocol (WIP).

---

## RQ4a — Configuration Effectiveness

**Null hypothesis H₀⁴ᵃ**: Verdict distribution and SOLID-violation reduction are independent of the `strictness` configuration value.

**Conditions / levels**:
- `strictness=low`: permissive supervisor; emits guidance with minimal rejection/escalation.
- `strictness=medium`: default supervisor setting and **reference baseline** for the configuration study.
- `strictness=high`: conservative supervisor; applies the strongest rejection/escalation thresholds before allowing a generation to proceed.

**Outcome measures**:
1. **Primary**: verdict distribution across `{accept, revise, reject}` per run.
2. **Secondary**: SOLID violation count delta relative to the issue's pre-change baseline, using the same static-analysis ruleset and M-1 delta definition referenced in `docs/requirements/metrics.md`.
3. **Secondary**: acceptance rate (`accept` / total runs) and escalation rate (`reject` / total runs).

**Procedure**:
1. Select **3-5 issue sets**, one intent per set, reusing the same issue-selection criteria as the main supervised study (RQ1).
2. For each set, execute the supervised pipeline under all three `strictness` levels: `low`, `medium`, and `high`.
3. Run **10 repeated trials per set per level** using the same seed schedule and LLM configuration, varying only `strictness`.
4. Record the final supervisor verdict (`accept`, `revise`, `reject`) and the resulting SOLID violation delta for each run.
5. Treat `strictness=medium` as the pre-declared baseline for pairwise follow-up comparisons (`low` vs `medium`, `high` vs `medium`).

**Sample size**: **3-5 sets × 10 repeated runs × 3 levels = 90-150 total runs**; for pairwise repeated-measures comparisons against the `medium` baseline, this yields **30-50 paired observations** per comparison.

**Planned statistical tests**:
- For the 3-level verdict distribution: **chi-square test of independence** on the aggregated contingency table of verdict × `strictness`; if any expected cell count is < 5, use **Fisher's exact test** instead.
- For repeated-measures comparison of SOLID violation delta across the three levels: **Friedman test** by set/run block.
- If the Friedman test is significant, run post-hoc **Wilcoxon signed-rank** tests for `low` vs `medium` and `high` vs `medium`, with Holm correction.

**Pass criterion**: reject H₀⁴ᵃ only if verdict distribution differs significantly by `strictness` and at least one non-default level shows a practically meaningful change versus `medium` (≥ 10 percentage-point change in acceptance rate or a positive median SOLID-delta improvement).

---

## RQ4 — Legacy System Modifiability Impact

**Null hypothesis H₀⁴**: Strangler Fig / Anti-Corruption Layer pattern adoption rate is not higher under supervised generation than under prompt-only generation, and SRP/OCP/DIP violation delta is not greater.

**Procedure**:
1. Curate **3-5 legacy sets**, each with 10 issues from repositories with SOLID debt indicators (age ≥ 5 years, ≤ 40 % test coverage, ≥ 10 SOLID violation smells per KLOC from SonarQube baseline scan).
2. For each issue, run supervised and prompt-only conditions as paired comparisons.
3. **Pattern detection**: classify each generated output using a structural rubric:
   - *Strangler Fig*: new facade class introduced that delegates to existing legacy module while intercepting new behavior.
   - *Anti-Corruption Layer*: new translation interface between legacy subsystem and caller, preventing propagation of legacy contracts.
   - Classification is binary (applied / not applied), performed by two independent reviewers (Cohen's κ ≥ 0.7 required).
4. **Violation delta**: run the same SonarQube SOLID ruleset as RQ1; record SRP, OCP, DIP deltas per issue using the M-1 definition in `docs/requirements/metrics.md`.
5. **Correlation**: test whether pattern application correlates with SOLID violation reduction (Spearman ρ).
6. Statistical tests: Fisher's exact test for pattern adoption rate; Wilcoxon for violation delta; compute Cohen's d on violation delta.

**Rationale**: Strangler Fig operationalizes OCP at the system level (you extend by adding a new facade, not by modifying the legacy module). ACL operationalizes DIP (new code depends on the abstraction, not the concrete legacy subsystem). Their adoption is therefore a concrete proxy for OCP+DIP compliance — detectable structurally without requiring expert code review for every line.

---

## Scope Exclusions

The following are explicitly **out of scope** for the primary study. They may
appear as future work:

| Exclusion | Reason |
|---|---|
| Full automated test execution (pass@k) | Requires runnable test harness per repository |
| Ontology vs. taxonomy comparison | Parallel OWL/RDF pipeline out of scope; see [`docs/risks/avoiding-ontologies.md`](../risks/avoiding-ontologies.md) |
| Multi-language evaluation (Python, Java, TypeScript) | C# corpus sufficient for v1 claims; external validity threat noted |
| Longitudinal developer productivity study | Requires long-term organizational access and ethics approval |
| Prompt engineering ablation (CoT vs. ReAct vs. RAG) | Supervisor architecture is the artifact under study, not prompt technique |

---

## References

