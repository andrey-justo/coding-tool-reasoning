# Experiment Design

Links back to RQ definitions: [`docs/risks/rq-scope-falsifiability.md`](../risks/rq-scope-falsifiability.md)

Subject/corpus tracking (repo + issue/commit/PR metadata): [`data/subjects/subject_data.csv`](../../data/subjects/subject_data.csv)
Run-level comparison tracking (baseline vs supervised vs human studies): [`data/subjects/experiment_runs.csv`](../../data/subjects/experiment_runs.csv)

---

## Summary Table

| RQ | Method | Baseline | Primary Metric | Statistical Test | Min N | Pass Criterion |
|---|---|---|---|---|---|---|
| RQ1 | Between-subjects (supervised vs. zero-shot) | `IntentPlanner` with `nfr_focus=[]`, `relationship_depth=0`, same LLM, `temperature=0` | SOLID violation count delta (static analysis) | Wilcoxon signed-rank | 5 repos × 30 issues = 150 | p < 0.05, Cohen's d ≥ 0.5 |
| RQ2 | Between-subjects (supervised vs. prompt-only) | Zero-shot, same LLM, same seed | SOLID violation count reduction (%) | Wilcoxon signed-rank | 5 repos × 30 issues = 150 | ≥ 10 pp reduction, p < 0.05 |
| RQ3a | Within-subjects (N repeated trials per issue) | Zero-shot, same LLM, same seed | Std-dev of SOLID violation count delta | Paired t-test on per-issue variance | 30 trials × 30 issues = 900 | ≥ 20 % std-dev reduction, p < 0.05 |
| RQ3b | Within-subjects (5 paraphrases per intent) | Zero-shot, same 5 paraphrases | Verdict consistency ratio | McNemar's test on verdict agreement matrices | 5 paraphrases × 30 intents = 150 | Consistency ≥ 0.80, p < 0.05 |
| RQ4 | Between-subjects (supervised vs. prompt-only) on legacy corpus | Prompt-only on same legacy hotspot issues | Strangler Fig / ACL pattern adoption rate + SRP/OCP/DIP violation delta | Fisher's exact test (pattern rate) + Wilcoxon (violation delta) | 5 legacy repos × 30 issues = 150 | p < 0.05, d ≥ 0.5 on violation delta |

---

## RQ1 — SOLID-Guided NFR Representation

**Null hypothesis H₀¹**: Taxonomy-guided generation does not produce lower SOLID
violation smell count than zero-shot generation (Cohen's d < 0.5).

**Procedure**:
1. Select 5 repositories × 30 issues each (see corpus selection in `PROPOSAL.md → # Empirical Experiments`). Prioritize repositories with known SOLID debt (high LCOM4, high concrete dependency count).
2. For each issue, run two conditions in the same session:
   - *Supervised*: `plan_swe_code_change` → `build_swe_code_context` → LLM code generation → `judge_swe_code_change`.
   - *Baseline*: same LLM prompt with no taxonomy injection (`nfr_focus=[]`, `relationship_depth=0`).
3. For each generated output, run static analysis on the diff:
   - **SonarQube** (open source) or **Roslyn Analyzers** (C#-specific): count SRP, OCP, DIP violation rules triggered.
   - Compute delta = (violations\_before − violations\_after) / violations\_before.
4. Secondary metric: Score each output with `ExplanationService` NFR coverage metric (fraction of ISO 25010 sub-characteristics covered in `nfr_impacts`).
5. Apply Wilcoxon signed-rank test on paired deltas; compute Cohen's d.

**Confound controls**:
- Fix `temperature=0` and `seed=42` in both conditions.
- Same LLM model and version; document exact model hash/tag.
- Run static analysis with identical ruleset and threshold in both conditions; disable rules unrelated to SOLID.
- Blind scoring: SOLID count computed by automated tool, not human judgment.

---

## RQ2 — SOLID Violation Reduction

**Null hypothesis H₀²**: SOLID violation count reduction under supervised generation is not greater than under zero-shot generation (Cohen's d < 0.5).

**Procedure**:
1. Select the same 5 repositories × 30 issues from the RQ1 corpus.
2. For each issue, run supervised vs. zero-shot conditions (identical to RQ1 Step 2).
3. Compute SOLID violation count before and after each generated change using the same static analysis ruleset.
4. Compute per-condition reduction rate: Δviolations = (before − after) / before.
5. Apply Wilcoxon signed-rank test on paired Δviolations (supervised vs. baseline); compute Cohen's d.

**Implementation**: Wire `_run_supervised_trial` and `_run_baseline_trial` in `src/evaluation/reproducibility_experiment.py` to also invoke the static analysis runner and store `solid_violation_delta` in `TrialResult`.

**Why static analysis over BERTScore as primary**: BERTScore measures semantic similarity to a reference; it cannot distinguish between code that *looks* similar and code that actually *respects* SOLID. Static analysis counts are objective, tool-verifiable, and independent of LLM self-reporting.

---

## RQ3 — Verdict Robustness Across Prompt Variations

**Null hypothesis H₀³**: Verdict consistency ratio under supervised generation ≤ verdict consistency ratio under zero-shot generation.

**Procedure**:
1. Select 30 distinct software engineering intents from the corpus.
2. For each intent, produce 5 human-authored paraphrases:
   - Formal specification style ("The system shall…")
   - Casual bug report ("This thing breaks when…")
   - Imperative command ("Refactor X to do Y")
   - Passive description ("X is not working because…")
   - Non-native speaker phrasing (simplified vocabulary, direct translation patterns)
3. Run each paraphrase through the supervised agent and the zero-shot baseline.
4. Compute verdict consistency ratio = (trials agreeing with majority verdict) / 5 per intent.
5. Apply McNemar's test on paired verdict agreement matrices (supervised vs. baseline).

**Paraphrase methodology**: Eger et al. (2019).

---

## RQ4a — Configuration Effectiveness

**Null hypothesis H₀⁴ᵃ**: Verdict distribution is independent of the `strictness` configuration value.

## RQ4 — Legacy System Modifiability Impact

**Null hypothesis H₀⁴**: Strangler Fig / Anti-Corruption Layer pattern adoption rate is not higher under supervised generation than under prompt-only generation (d < 0.5), and SRP/OCP/DIP violation delta is not greater.

**Procedure**:
1. Curate a **legacy corpus**: 5 repositories with SOLID debt indicators (age ≥ 5 years, ≤ 40 % test coverage, ≥ 10 SOLID violation smells per KLOC from SonarQube baseline scan).
2. For each of 30 legacy issues per repo, run supervised and prompt-only conditions.
3. **Pattern detection**: classify each generated output using a structural rubric:
   - *Strangler Fig*: new facade class introduced that delegates to existing legacy module while intercepting new behavior.
   - *Anti-Corruption Layer*: new translation interface between legacy subsystem and caller, preventing propagation of legacy contracts.
   - Classification is binary (applied / not applied), performed by two independent reviewers (Cohen's κ ≥ 0.7 required).
4. **Violation delta**: run the same SonarQube SOLID ruleset as RQ1; record SRP, OCP, DIP deltas per issue.
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

- Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., & Wesslén, A. (2012). *Experimentation in Software Engineering*. Springer.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum.
- Eger, S., Şahin, G. G., Rücklé, A., Lee, J.-U., Schulz, C., Mesgar, M., ... & Gurevych, I. (2019). Text Processing Like Humans Do. *NAACL-HLT*.
- Popper, K. (1959). *The Logic of Scientific Discovery*. Routledge.
