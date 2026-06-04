# Cronograma de Execução da Pesquisa (v2 — Dois Ciclos DSR)
**Supervisor Agent for LLM-Assisted Legacy Software Modernization**

## Visão Geral

- **Duração total:** 24 meses (jun/2026 — mai/2028)
- **Data de início:** junho 2026
- **Estrutura:** 3 ciclos de Design Science Research (DSR) com **2 ciclos completos de coleta/análise/escrita**
- **Referência methodology:** Hevner et al. (2004); Wohlin et al. (2012); Basili et al. (1986)

---

## 1. Estrutura DSR Duplicada

A pesquisa segue **3 ciclos DSR** (Relevance → Design → Rigor) com **dois ciclos de coleta-análise-escrita**:

| Ciclo | Objetivo | Fases | Período | Output principal |
|---|---|---|---|---|
| **Ciclo 1: Relevância** | Validar problema; estabelecer fundação | Fase 1 | jun–set 2026 (M1–M4) | RQs operacionalizadas; corpus definido |
| **Ciclo 2: Design** | Construir e iterar artefato | Fase 2 | out 2026–fev 2027 (M5–M9) | Protótipo endurecido; harness experimental |
| **Ciclo 3a: Rigor (Coleta I)** | Coleta de dados I | Fase 3 | mar–ago 2027 (M10–M15) | 30–50 pares por RQ; dados brutos |
| **Ciclo 3b: Rigor (Análise I)** | Análise preliminar + confirmativa I | Fase 3.5–4 | jul–out 2027 (M16–M19) | Resultados confirmados; validação humana |
| **Ciclo 3c: Escrita I** | Paper preliminar | Fase 5 | out–dez 2027 (M16–M20) | Conference paper submetido |
| **Ciclo 3d: Rigor (Coleta II)** | Coleta de dados II (replicação/expansão) | Fase 3 (II) | nov 2027–dez 2027 (M21–M22) | Amostra expandida ou novo subset |
| **Ciclo 3e: Rigor (Análise II)** | Análise preliminar + confirmativa II | Fase 3.5–4 (II) | jan–abr 2028 (M23–M26) | Validação de replicação; negative/positive results |
| **Ciclo 3f: Escrita II** | Paper final + tese | Fase 5 (II) | abr–mai 2028 (M27–M29) | Journal paper + capítulo de tese |

---

## 2. Cronograma Detalhado por Fase

### ⏰ FASE 1: Ciclo de Relevância (Junho–Setembro 2026 / M1–M4)
**Objetivo:** Validar o problema e estabelecer fundação de pesquisa.

#### 2.1.1 Atividades-chave

| Atividade | Responsável | Deadline | Entregável |
|-----------|-------------|----------|-----------|
| Finalizar especificação de requisitos (Volere-style) | Pesquisador | fim M1 | Requirements document congelado |
| Integrar SLR em Related Work | Pesquisador | fim M1 | Gap Ledger com 5–10 trabalhos proximais |
| Revisar framing DSR (7 guidelines Hevner) | Pesquisador | fim M2 | Design Science Framing document |
| Operacionalizar RQs (hypotheses, DVs, testes) | Pesquisador | fim M2 | RQ Operationalization memo |
| Identificar e validar corpus (5 C# repos públicos) | Pesquisador + Orientador | fim M3 | Corpus selection report com motivação |
| Desenhar experiment design (procedure, protocol) | Pesquisador | fim M3 | Experiment Design document com flowchart |
| Pré-registrar protocolo (OSF) | Pesquisador | fim M3 | Preregistration URL + versão congelada |
| Redação: Introduction + Related Work draft | Pesquisador | fim M4 | 4–5 páginas de Introduction + Related Work |

#### 2.1.2 Go/No-Go Decision (fim M4)
- ✅ **GO**: RQs operacionalizadas, corpus validado, preregistro congelado → Proceed to Fase 2
- ❌ **NO-GO**: Gaps em operacionalization, corpus insufficiente → Extend Fase 1 por 2–3 semanas

**Entregáveis M4:**
- RQ Operationalization document (congelado)
- Corpus selection report com 5 repositórios
- Experiment Design document com flowchart e procedure
- Preregistration URL (OSF)
- Introduction + Related Work draft (4–5 pp)

---

### ⏰ FASE 2: Ciclo de Design — Endurecimento de Protótipo (Outubro 2026–Fevereiro 2027 / M5–M9)
**Objetivo:** Resolver gaps de implementação; criar baseline funcional; instrumentar coleta de dados; implementar controles de determinismo; validar harness experimental com pilot de 10 issues.

#### 2.2.1 Atividades-chave

| Atividade | M | Responsável | Entregável |
|-----------|---|-------------|-----------|
| Adicionar `temperature=0` + `seed` ao LLM client | M5 | Dev | Code commit; seed logging implementado |
| Micro-estudo determinismo (5–10 issues, 2x runs cada) | M5 | Pesquisador | Micro-study report: variância residual medida |
| Integrar análise estática SOLID (SonarQube/Roslyn); pin ruleset version | M5 | Dev | Ruleset versionado; mappeamento SOLID→rules documentado |
| Captura de violações (antes/depois per issue) | M5 | Dev | TrialResult schema implementado |
| Implementar baseline (zero-shot) condition: `nfr_focus=[]` | M5–M6 | Dev | IntentPlanner suporta supervisão OFF; teste unitário adicionado |
| Wireamento completo: `_run_supervised_trial` + `_run_baseline_trial` | M6 | Dev | reproducibility_experiment.py wired; CI green |
| Implementar execution trace capture (prompts, commits, approvals, timestamps) | M6 | Dev | Execution trace schema JSON versionado; exemplos |
| Implementar testability gate (build status, test status, coverage delta) | M6 | Dev | Gate logic + documentation |
| Coletar métricas de qualidade adicionais (CC, coverage, duplication, security) | M6 | Dev | Metrics collection implemented; CI green |
| Substituir scorer por `microsoft/codebert-base` (code-specific) | M6 | Dev | Scorer swapped; test F1 ≥ 0.3 |
| Adicionar testes unitários para IntentPlanner + ExplanationService | M7 | Dev | Unit tests green; stubs removed |
| Protocol de paráfrase (10 estilos semanticamente equivalentes) | M7 | Pesquisador | Protocol document + exemplos |
| Implementar executor de paráfrases (automático ou manual) | M7 | Dev | Paraphrase executor working; CI green |
| Pilot 10 issues com 3+ engenheiros; calcular Cohen's κ | M8 | Pesquisador | Pilot report: κ ≥ 0.6 ou refined protocol |
| Manual validation 10 plans: SRP/OCP/DIP coverage ≥80% | M8 | Pesquisador | Manual validation report |
| Micro-study de paráfrases (2–3 issues, 3 paráfrases cada) | M8 | Pesquisador | Paraphrase validation report |

#### 2.2.2 Go/No-Go Decision (fim M9, antes de M10 Coleta I)
- ✅ **GO**: CI verde, κ ≥ 0.6, determinismo OK, baseline wired → Proceed to Fase 3 (Coleta I)
- ❌ **NO-GO**: κ < 0.6, CI failures, determinismo broken → Extend M9 por 2 semanas refinement

**Entregáveis M9:**
- CI report: all tests green
- Pilot report: 10 issues, κ scores, design coverage %
- Determinism report: temperature=0 + seed validation
- Baseline implementation report
- Testability gate documentation
- Metrics collection report
- Paraphrase protocol + executor working

---

### ⏰ FASE 3 (Ciclo I): Coleta de Dados I (Março–Agosto 2027 / M10–M15)
**Objetivo:** Executar experimentos em escala completa; coletar 30–50 pares por RQ (supervisado vs. baseline) para RQ1–RQ4a.

#### 2.3.1 Atividades-chave (Ciclo I)

| RQ | Atividade | M | Entregável |
|----|-----------|---|-----------|
| **RQ1** | Executar IntentPlanner em 3–5 sets × 10 issues (30–50 plans) | M10–M12 | Plans com coverage %, rastreabilidade até taxonomia |
| **RQ1** | Inspecionar manualmente coverage (SRP/OCP/DIP, constraints documentados) | M13 | Manual inspection report |
| **RQ2** | Experimento pareado: 30–50 pares × (supervisado + baseline) | M10–M14 | Delta SOLID bruto (antes/depois) |
| **RQ2** | Coleta de SOLID delta via análise estática por par | M10–M14 | TrialResult JSON com violations count |
| **RQ3** | Corpus de paráfrases: 3–5 sets × 10 tasks → 10 paráfrases cada (300–500 tasks) | M11–M13 | Paraphrase corpus com índices |
| **RQ3** | Executar ambas condições em cada paráfrase; coletar verdicts | M13–M14 | Paraphrase results JSON |
| **RQ4** | Coleta subset "legacy" (a priori); executar pareado em 30–50 pares legacy | M14–M15 | Delta SOLID legacy subset |
| **RQ4a** | Executar experimento com variação `strictness ∈ {low, medium, high}` em 90–150 runs | M14–M15 | Config experiment results: verdict dist, delta, rates |
| **All** | Data quality validation: missing values, outliers, LLM failures | M15 | Data quality report |
| **All** | Verificar provenance: ruleset version, timestamps, model tags | M15 | Provenance log audit |

**Dados brutos coletados (fim M15):**
- 30–50 pares por RQ (RQ1–RQ4)
- 300–500 paráfrases (RQ3)
- 90–150 config runs (RQ4a)
- Todos JSON versionados + anonymizados
- Data quality report

---

### ⏰ FASE 3.5 (Ciclo I): Análise Preliminar I (Setembro–Outubro 2027 / M16–M17)
**Objetivo:** Detectar anomalias; análise exploratória; refinements opcionais antes de confirmativa.

#### 2.3.5.1 Atividades-chave (Ciclo I)

| Atividade | M | Entregável |
|-----------|---|-----------|
| Data cleaning: verificar missing, outliers, failures | M16 | Data cleaning report |
| RQ1: revisar 10–15 plans; coverage ainda ≥80%? | M16 | Coverage preliminary analysis |
| RQ2: calcular delta SOLID preliminar (mediana, distribuição) | M16 | Preliminary delta analysis |
| RQ3: calcular consistency ratio (supervisado vs. baseline em paráfrases) | M16 | Paraphrase consistency preliminary |
| RQ4: calcular delta legacy preliminar; comparar com RQ2 | M16 | Legacy effect preliminary |
| RQ4a: visualizar distribuição de verdicts por strictness | M16 | Config effect preliminary |
| Reunião com orientador: apresentar preliminary results | M17 início | Go/No-Go decision memo |
| **Decision**: Protocol lockdown ou adaptações documentadas | M17 início | Protocol amendment memo (se applicable) |
| Congelar análise code; tag em versionamento | M17 | Analysis code locked tag |

**Go/No-Go (M17 início):**
- ✅ **GO**: Sem anomalias fundamentais; protocol congelado → Proceed to Análise Confirmativa
- ❌ **NO-GO**: Distribuição muito skewed, effect muito fraco, κ pending → Ajustes + lock adiado

**Entregáveis M17:**
- Data cleaning report
- Preliminary analysis per RQ (coverage, delta, consistency, legacy, config)
- Protocol amendment memo (if needed)
- Analysis code locked

---

### ⏰ FASE 4 (Ciclo I): Análise Confirmativa I (Julho–Outubro 2027 / M16–M19, paralelo com Preliminar)
**Objetivo:** Análise estatística confirmativa; validação humana; survey; threats to validity.

#### 2.4.1 Atividades-chave (Ciclo I)

| RQ | Teste Estatístico | M | Entregável |
|----|------------------|---|-----------|
| **RQ1** | Design review 15–20 plans; coverage ≥80%? | M18 | Design review report (% passing) |
| **RQ2** | Wilcoxon signed-rank pareado (30–50 pares delta SOLID); mediana, p, r | M18 | RQ2 results: mediana/CI/p/effect |
| **RQ3** | McNemar test pareado (verdicts paráfrases); contagem, p, effect | M18 | RQ3 results: McNemar table/p/effect |
| **RQ4** | Wilcoxon signed-rank subset legacy (30–50 pares); p, r, comparar com RQ2 | M18 | RQ4 results: mediana/CI/p/effect legacy |
| **RQ4a** | ANOVA ou Kruskal-Wallis (strictness effect); post-hoc Tukey/Dunn | M19 | RQ4a results: F/H, p-values, post-hoc |
| **All** | Bonferroni/Benjamini-Hochberg multiple comparison correction | M19 | Corrected p-values applied |
| **Validation** | Human κ study: recrutar ≥3 engenheiros; labelem 20–30 outputs | M18–M19 | κ report (target ≥0.6) |
| **Survey** | Likert 5-point: Trust, Control, Usability; N ≥ 20 developers | M18–M19 | Survey data: mean/SD, Cronbach's α, correlations |
| **Write Results** | Tabelas, gráficos, narrativa de resultados | M19 | Results section draft |
| **Threats** | Mapear ameaças a validade (interna, construto, externa, conclusão) | M19 | Threats to Validity section draft |

**Entregáveis M19:**
- Confirmative analysis report (RQ1–RQ4a com p-values, effect sizes, CIs)
- Human validation: κ scores
- Survey data (N ≥ 20, statistics)
- Results section draft
- Threats to Validity draft

---

### ⏰ FASE 5 (Ciclo I): Escrita e Submissão I (Outubro–Dezembro 2027 / M16–M20, paralelo com análises)
**Objetivo:** Redação de paper preliminar para conference; pode ser submetido durante Análise Confirmativa I.

#### 2.5.1 Atividades-chave (Ciclo I)

| Seção | M | Responsável | Entregável |
|-------|---|-------------|-----------|
| **Introduction** | M16–M17 | Pesquisador | Motivation + problem statement + gap (2–3 pp) |
| **Related Work** | M17 | Pesquisador | SWE-bench, SWE-agent, ISO 25010 + Gap Ledger (3–4 pp) |
| **Methodology (DSR)** | M17–M18 | Pesquisador | 7 guidelines Hevner + 3 ciclos DSR (2–3 pp) |
| **Artifact Design** | M18 | Pesquisador | IntentPlanner + ExplanationService + taxonomy (3–4 pp) |
| **Experiment Design** | M18 | Pesquisador | RQs, hypotheses, DVs, procedures, corpus (4–5 pp) |
| **Results (Preliminary)** | M19 | Pesquisador | Tabelas/gráficos com resultados Ciclo I (5–6 pp) |
| **Internal Review** | M19–M20 | Pesquisador + Orientador | Feedback + correções |
| **Venue Selection** | M20 | Pesquisador | Choice: ICSE/FSE/TOSEM/EMSE/Companion |
| **Format + Polish** | M20 | Pesquisador | Camera-ready draft; template applied |
| **Submit** | M20 | Pesquisador | Paper submitted; tracking number |

**Entregáveis M20:**
- Camera-ready paper (conference format, ~10–15 pp)
- Paper submitted (tracking number confirmed)
- Replication package draft (data + code tagged)

---

### ⏰ FASE 3 (Ciclo II): Coleta de Dados II (Novembro–Dezembro 2027 / M21–M22)
**Objetivo:** Coleta de dados II; replicação ou expansão de Ciclo I com amostra similar ou novo subset.

#### 2.3.2 Atividades-chave (Ciclo II)

**Estratégia de Coleta II (Choose One):**

**Option A (Replicação em novo subset):**
- Mesmos 5 repos, diferentes 30–50 issues novos
- Mesmas condições (supervisado, baseline, strictness levels)
- Valida robustez de Ciclo I em amostra nova

**Option B (Repos adicionais):**
- 2–3 repos novos (legacy-focused)
- Coleta 30–50 pares como Ciclo I
- Expande validade externa

**Option C (Sub-análise + replicação):**
- Toma findings de Ciclo I (e.g., "efeito forte em pequenos arquivos")
- Coleta 20–30 pares specifically in that subgroup
- Valida sub-hypothesis

| Atividade | M | Entregável |
|-----------|---|-----------|
| Decidir estratégia de Coleta II (A/B/C) com orientador | M21 início | Coleta II strategy memo |
| Executar RQ1–RQ4a com Coleta II amostra | M21–M22 | Dados brutos (30–50 pares, paráfrases, configs) |
| Data quality validation | M22 | Data quality report II |
| Verificar provenance (mesmos versions?) | M22 | Provenance audit II |

**Entregáveis M22:**
- Coleta II datasets (JSON, anonymizados)
- Data quality report II
- Provenance audit II

---

### ⏰ FASE 3.5 (Ciclo II): Análise Preliminar II (Janeiro–Fevereiro 2028 / M23–M24)
**Objetivo:** Análise exploratória Ciclo II; comparação com Ciclo I; refinements se necessário.

#### 2.3.5.2 Atividades-chave (Ciclo II)

| Atividade | M | Entregável |
|-----------|---|-----------|
| Data cleaning Ciclo II | M23 | Data cleaning report II |
| Calcular deltas preliminares (RQ1–RQ4a) | M23 | Preliminary stats II per RQ |
| Comparar effect sizes Ciclo I vs. II | M23 | Replication analysis preliminary |
| Reunião com orientador: Ciclo II confirma Ciclo I? | M24 início | Go/No-Go decision memo II |
| **Decision**: Protocol ok para Confirmativa II? Ou ajustes? | M24 início | Protocol amendment memo II (if needed) |
| Congelar análise code Ciclo II | M24 | Analysis code locked tag II |

**Entregáveis M24:**
- Data cleaning report II
- Preliminary analysis Ciclo II (coverage, delta, consistency, legacy, config)
- Replication comparison (effect sizes Ciclo I vs. II)
- Protocol amendment memo II (if applicable)
- Analysis code locked II

---

### ⏰ FASE 4 (Ciclo II): Análise Confirmativa II (Março–Abril 2028 / M25–M26)
**Objetivo:** Análise estatística confirmativa Ciclo II; validação de replicação; human validation II; survey II.

#### 2.4.2 Atividades-chave (Ciclo II)

| RQ | Teste Estatístico | M | Entregável |
|----|------------------|---|-----------|
| **RQ1** | Design review 10–15 plans Ciclo II | M25 | Design review report II |
| **RQ2** | Wilcoxon signed-rank Ciclo II; comparar p-values com Ciclo I | M25 | RQ2 Ciclo II: mediana/CI/p/effect + comparison |
| **RQ3** | McNemar test Ciclo II | M25 | RQ3 Ciclo II results + comparison |
| **RQ4** | Wilcoxon legacy Ciclo II | M25 | RQ4 Ciclo II results + comparison |
| **RQ4a** | Kruskal-Wallis Ciclo II; post-hoc | M26 | RQ4a Ciclo II results + comparison |
| **All** | Multiple comparison correction (Bonferroni/BH) | M26 | Corrected p-values II |
| **Validation** | Human κ study Ciclo II: ≥3 engenheiros, 20–30 outputs | M25–M26 | κ report II (target ≥0.6) |
| **Survey** | Likert survey Ciclo II (N ≥ 20 new developers) | M25–M26 | Survey data II: mean/SD, Cronbach's α |
| **Replication** | Meta-analysis or combined analysis Ciclo I+II | M26 | Combined effect sizes, pooled p-values |
| **Write Results** | Results section integrating Ciclo I + II | M26 | Results section final |
| **Threats + Discussion** | Validade ameaças + discussão de replicação | M26 | Threats + Discussion draft final |

**Entregáveis M26:**
- Confirmative analysis report Ciclo II (RQ1–RQ4a)
- Replication analysis (Ciclo I vs. II meta-analysis or combined)
- Human validation II: κ scores
- Survey data II (N ≥ 20)
- Results section final (Ciclo I + II consolidated)
- Threats to Validity + Discussion final draft

---

### ⏰ FASE 5 (Ciclo II): Escrita e Submissão II (Abril–Maio 2028 / M27–M29)
**Objetivo:** Paper final + capítulo de tese; integración resultados Ciclo I + II; submissão journal.

#### 2.5.2 Atividades-chave (Ciclo II)

| Seção | M | Responsável | Entregável |
|-------|---|-------------|-----------|
| **Update Introduction** | M27 | Pesquisador | Integrar motivação com replicação Ciclo II |
| **Update Related Work** | M27 | Pesquisador | Adicionar referências a replicação em literatura |
| **Methodology (DSR final)** | M27 | Pesquisador | Detalhar 2 ciclos completos de Design-Rigor |
| **Artifact Design (final)** | M27 | Pesquisador | Refinements baseados em Ciclo I feedback |
| **Experiment Design (final)** | M27 | Pesquisador | Inclui ambos Ciclos na descrição |
| **Results (Ciclo I + II)** | M27–M28 | Pesquisador | Consolidated tabelas/gráficos; replication analysis; pooled effects |
| **Discussion** | M28 | Pesquisador | Achados vs. RQs, replicação confirma/contradiz Ciclo I, implications |
| **Threats to Validity (final)** | M28 | Pesquisador | Mitigações completas de validade interna/construto/externa/conclusão |
| **Conclusion + Future Work** | M28 | Pesquisador | Limitações, open problems, extensibilidades |
| **Internal Review + Revisions** | M28–M29 | Pesquisador + Orientador | Feedback + polishing |
| **Venue Selection (Journal)** | M29 | Pesquisador | Choice: TOSEM / EMSE / TSE (journal top-tier) |
| **Format + Final Polish** | M29 | Pesquisador | Template journal applied; reference formatting |
| **Submit to Journal** | M29 | Pesquisador | Paper submitted; tracking number |
| **Tese Capítulo (Methodology + Results + Discussion)** | M28–M29 | Pesquisador | ~40–50 páginas integrado em tese |
| **Replication Package (final)** | M29 | Pesquisador | Git hashes, rulesets, prompts, data anonymizado, DOI |
| **Archive + Link** | M29 | Pesquisador | Replication package in Zenodo/OSF/GitHub; DOI linkado no paper |

**Entregáveis M29:**
- Journal paper (camera-ready, ~15–20 pp, two-cycle findings)
- Paper submitted to journal (tracking number)
- Tese capítulo final (~40–50 pp: Methodology + Results + Discussion)
- Replication package archived (DOI public)
- All results publicly linked

---

## 3. Síntese de Milestones e Decisões Críticas

| Milestone | M | Critério GO | Critério NO-GO | Ação se NO-GO |
|-----------|---|-----------|----------------|--------------|
| **M4 (fim Fase 1)** | M4 | RQs operacionalizadas, corpus validado, preregistro congelado | Gaps em operationalization | Extend Fase 1 por 2–3 semanas |
| **M9 (fim Fase 2)** | M9 | CI verde, κ ≥ 0.6, determinismo OK, baseline wired | κ < 0.6, CI fails, determinismo broken | Extend M9 refinements 2 semanas |
| **M17 (Análise Preliminar I)** | M17 | Sem anomalias fundamentais; protocol congelado | Effect muito fraco, distribuição skewed, κ pending | Ajustes + lock adiado |
| **M24 (Análise Preliminar II)** | M24 | Ciclo II confirma Ciclo I ou complementa | Ciclo II contradiz Ciclo I fortemente | Investigar anomalias; ajustes antes Confirmativa II |
| **M29 (fim Ciclo II)** | M29 | Paper submetido, Replication package archived, Tese capítulo pronto | Paper fails review ou artefato não funciona | Submeter como negative result ou extend M29 |

---

## 4. Estrutura DSR Alinhada com Hevner et al.

Todo o cronograma duplicado segue 7 guidelines de Hevner et al. (2004):

1. **Design as an Artifact** (Fase 2–3): Supervisor agent construído e testado iterativamente em dois ciclos
2. **Problem Relevance** (Fase 1): Problema de modernização legado validado; entrevistas com desenvolvedores
3. **Design Evaluation** (Fase 2.5+3.5, Fase 4): Pilot, preliminary, confirmative analysis; human validation κ
4. **Research Contributions** (Fase 1 + 5): Gap Ledger explícito; novelty claims mapeadas a gaps reais
5. **Research Rigor** (Fase 4): Testes não-paramétricos, preregistro, multiple comparison correction, replicação
6. **Design as a Search Process** (Fase 2.5+3.5): Iterações de feedback; refinements em cada ciclo
7. **Communication** (Fase 5): Conference paper (Ciclo I) + Journal paper (Ciclo II) + Tese capítulo

Os **3 ciclos DSR** (Relevance M1–M4 → Design M5–M9 → Rigor M10–M29) com **2 ciclos de coleta-análise-escrita** garantem robustez, replicação interna e publicabilidade em múltiplos venues.

---

## 5. Matriz de Riscos por Fase

| Risco | Fase(s) | Mitigação | Verificação |
|-------|---------|-----------|------------|
| **R1: DSR framing inadequado** | 1 | Design Science Framing document; 7 guidelines checklist | M4 go/no-go |
| **R2: Novelty gap não claro** | 1, 5 | Gap Ledger com 5–10 trabalhos proximais | M4 go/no-go; M29 Related Work review |
| **R3: RQs não falsificáveis** | 1 | Operationalization memo; hypotheses + DVs + testes explícitos | M4 preregistro |
| **R4: Corpus insuficiente/enviesado** | 1 | Mix legacy+ativos; 5 repos públicos; justificativa de seleção | M4 corpus report |
| **R5: Métrica SOLID não implementável** | 2 | Micro-study determinismo; captura de violações implementado | M9 pilot report |
| **R6: Taxonomia incompleta** | 1, 2 | Integration com ISO 25010; nodes com exemplos código | M4 go/no-go; M9 test coverage |
| **R7: Determinismo falha (LLM não-determinístico)** | 2 | temperature=0, seed pinned, reexecução 2x | M5 micro-study; M9 pilot |
| **R8: Baseline não wired corretamente** | 2 | Code review; CI tests; _run_baseline_trial logic simples | M6 code review; M9 CI green |
| **R9: κ-validation fails (protocolo ambíguo)** | 2, 4 | 3+ engenheiros independentes; treino explicado | M8 pilot; M18 human validation |
| **R10: Paráfrase protocol incoerente** | 2, 3 | 10 estilos pré-definidos; validação semântica manual | M7 protocol document; M8 micro-study |
| **R11: Análise estática misconfigured** | 2, 3 | Ruleset pinned; versionamento; exemplos de output | M5 integration; M10–M15 data audit |
| **R12: Scorer inadequado** | 2 | Swap to microsoft/codebert-base; F1 ≥ 0.3 target | M6 test F1; M9 CI green |
| **R13: Effect size too small (< 0.3 médio)** | 4 | Coleta II pode expandir amostra; or subgroup analysis | M24 preliminary; M25 decision |
| **R14: Escrita pode não ser publicável** | 5 | Internal review M19 + M28; Gap Ledger claro; multiple venues | M20 + M29 submission |
| **R15: Replicação contradiz Ciclo I** | 3 (II), 4 (II) | Investigate; document; meta-analysis pooled; publication value neutral | M24 preliminary II; M26 analysis |

---

## 6. Versioning

- **v1.0** (31 mai 2026): Cronograma inicial 14 meses com feedback loops explícitos
- **v2.0** (31 mai 2026): Cronograma duplicado 24 meses com dois ciclos DSR completos (Coleta I–II, Análise I–II, Escrita I–II)

**Status:** ✅ Pronto para execução (condicionado a assinatura de orientador em M1).

**Próximo passo:** Assinar documento de cronograma com orientador; iniciar Fase 1 (junho 2026).

