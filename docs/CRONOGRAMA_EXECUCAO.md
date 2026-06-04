# Cronograma de Execução da Pesquisa
**Supervisor Agent for LLM-Assisted Legacy Software Modernization**

## Visão Geral

- **Duração total:** 14 meses
- **Data de início:** A confirmar com orientador
- **Estrutura:** 3 ciclos de Design Science Research (DSR)
- **Referência methodology:** Hevner et al. (2004); Wohlin et al. (2012); Basili et al. (1986)

---

## 1. Estrutura DSR e Mapeamento de Fases

A pesquisa segue **3 ciclos DSR** com **2 feedback loops explícitos** (iterações):

| Ciclo | Objetivo | Fases do projeto | Output principal |
|---|---|---|---|
| **Ciclo 1: Relevância** | Validar o problema; estabelecer fundação de pesquisa | Fase 1 (M1–M3) | RQs operacionalizadas; corpus definido; requisitos congelados |
| **Ciclo 2: Design** | Construir e iterar o artefato (agente supervisor) | Fase 2–2.5–3–3.5 (M4–M8) | Prototipo endurecido; dados brutos coletados; harness experimental |
| **Ciclo 3: Rigor** | Validação científica; análise estatística; publicação | Fase 4–5 (M9–M14) | Resultados estatísticos; paper; tese |

### Iterações Explícitas (Feedback Loops)
- **Iteração 1 (M5→M6)**: Pilot 10 issues → validação → refinamentos → scale para 50 issues
- **Iteração 2 (M8→M9)**: Análise preliminar dados coletados → protocol refinement → análise confirmativa

---

## 2. Cronograma Detalhado por Fase

### ⏰ FASE 1: Ciclo de Relevância (Meses 1–3)
**Objetivo:** Validar o problema e estabelecer a fundação de pesquisa.

#### 2.1.1 Atividades-chave

- [ ] **Finalizar especificação de requisitos** (Volere-style)
  - Ajustar prioridades Must/Should/Could com orientador
  - Congelar requisitos para Fase 2
  - Deadline: **fim M1**

- [ ] **Integrar SLR em Related Work**
  - Identificar trabalhos mais próximos (SWE-bench, SWE-agent, Plan4Code, OpenHands)
  - Definir delta preciso de novelty
  - Redefinir wording de contribuições
  - Deadline: **fim M1**

- [ ] **Revisar framing de Design Science** 
  - Documentar como pesquisa segue 7 guidelines de Hevner et al.
  - Mapear ciclos DSR aos objetivos das RQs
  - Ref: [`docs/risks/design-science-framing.md`](risks/design-science-framing.md)
  - Deadline: **M1/M2**

- [ ] **Validar escopo e falsificabilidade das RQs**
  - Confirmar hipóteses nulas (H₀) para RQ1–RQ4
  - Definir baselines (zero-shot para RQ2–RQ4; design review para RQ1)
  - Ref: [`docs/risks/rq-scope-falsifiability.md`](risks/rq-scope-falsifiability.md)
  - Deadline: **M2**

- [ ] **Mapear ISO 25010 → Taxonomy nodes**
  - Adicionar coluna `ISO25010Characteristic` a todos os CSVs da taxonomia:
    - `clean_code_nfr_nodes.csv`
    - `legacy_code_nodes.csv`
    - `security_nfr_nodes.csv`
  - Validar rastreabilidade SRP/OCP/DIP → Maintainability/Modifiability (ISO 25010)
  - Deadline: **M2**

- [ ] **Selecionar corpus empírico**
  - 5 repositórios C# públicos (mix legacy + ativos)
  - Licença pública (GitHub)
  - Tracker de issues disponível
  - Armazenar em [`data/subjects/subject_data.csv`](data/subjects/subject_data.csv)
  - Deadline: **M2**

- [ ] **Planejar atividades com humanos**
  - (a) Protocolo de anotação (verdict/pattern labels, target κ ≥ 0.6)
  - (b) Instrumento de survey (confiança/controle/usabilidade)
  - (c) Decisão ética/IRB (se necessário)
  - Deadline: **M2/M3**

- [ ] **Conduzir entrevistas iniciais com desenvolvedores**
  - Validar que misalinhamento NFR é um pain point prático
  - Confirmar relevância do problema (DSR G2)
  - Deadline: **M3**

#### 2.1.2 Entregáveis

- **Baseline de requisitos:** Spec Volere + roadmap de implementação (congelado)
- **Relatório SLR:** Confirmação de gap de novelty
- **Taxonomia enriquecida:** CSVs com coluna `ISO25010Characteristic` + referential integrity
- **Lista de corpus:** 5 repositórios com justificativa
- **RQs finalizadas:** Null hypotheses assinadas pelo orientador

#### 2.1.3 Marcos de risco para M3

| Risco | Descrição | Mitigação |
|---|---|---|
| R1 | Design Science framing/novelty | SLR concluído; Hevner mapeado; claims apertadas |
| R2 | Claim de novelty não suportada | Gap Ledger em Related Work; delta bem definido |
| R3 | RQs mal definidas/não falsificáveis | Hipóteses nulas + baselines explícitos |
| R4 | Data privacy não adequada | Apenas repos públicos; anonimização se necessária |
| R5 | Ontologia vs. taxonomia confusa | CSV como trade-off DSR; positioning justificado |
| R6 | Taxonomia incompleta | ISO 25010 mapeado; edges faltando = TBD M2 |

---

### ⏰ FASE 2: Ciclo de Design — Endurecimento de Protótipo (Meses 4–5)
**Objetivo:** Resolver gaps de implementação bloqueadores para experimentos reproduzíveis.

#### 2.2.1 Atividades-chave

**Controles de Determinismo:**
- [ ] Adicionar parâmetros `temperature=0` e `seed` a `LocalAIClient.chat()`
  - Persistir em logs de trial para auditoria
  - Deadline: **M4**
- [ ] Executar micro-estudo (5–10 issues) para medir variância residual
  - Documentar qualquer não-determinismo restante
  - Deadline: **M4**

**Instrumentação de Métrica Primária:**
- [ ] Integrar análise estática (SonarQube OU Roslyn analyzers)
  - Pinnar version de ruleset
  - Documentar mapeamento: SOLID violations ← SonarQube rules
  - Deadline: **M4**
- [ ] Capturar violações SOLID before/after por issue
  - Armazenar em `TrialResult`
  - Deadline: **M4**
- [ ] Executar pilot manual (10 issues) para validar contra-análise
  - Cohen's κ ≥ 0.6 para 3+ engenheiros sênior
  - Deadline: **M5**

**Codificação do Baseline (Zero-shot):**
- [ ] Implementar condição baseline (`IntentPlanner` com `nfr_focus=[]`, `relationship_depth=0`)
  - Garantir que baseline use mesmo modelo/temperatura/seed que supervisado
  - Deadline: **M4**
- [ ] Wire `_run_supervised_trial` e `_run_baseline_trial` em `reproducibility_experiment.py`
  - Ambas as condições capturam trial artifacts (LLM output + config + model tag)
  - Deadline: **M4**

**Captura de Execução e Rastreabilidade:**
- [ ] Implementar execution trace capture
  - Por run: repo, revisions/commits, aprovação do usuário, prompts (externos + internos)
  - Armazenar em `data/experiments/runs/`
  - Deadline: **M4**
- [ ] Adicionar logging completo (config, model, outputs, timestamps)
  - Deadline: **M4**

**Portão de Testabilidade:**
- [ ] Implementar testability gate + logging na harness experimental
  - Build status, test status, tests-added count, coverage delta (opcional)
  - Prerequisito interpretativo para outras DVs
  - Ref: [`docs/risks/risk-register.md`](risks/risk-register.md) (R15)
  - Deadline: **M5**
- [ ] Documentar per-repo test harness instructions
  - Deadline: **M5**

**Métricas de Qualidade Adicionais:**
- [ ] Coletar onde disponível: complexidade ciclomática, cobertura, duplicação, conventions, segurança
  - Registrar provenance (tool version, timestamp, scope)
  - Deadline: **M5**

**Experimento de Robustez a Variações de Prompt (RQ3):**
- [ ] Escrever protocolo de paráfrase para RQ3
  - 10 estilos semântica-preservados por task
  - Deadline: **M4**
- [ ] Implementar executor de paraphrases na harness
  - Deadline: **M5**

**Qualidade de Código / Testes:**
- [ ] Adicionar testes unitários para `IntentPlanner` e `ExplanationService`
  - Mock `MultiModelLLMClient`
  - Assertions: schema validity, deterministic parsing
  - Deadline: **M4**
- [ ] Remover ou implementar stub `src/migration/analyzer.py`
  - Deadline: **M4**
- [ ] CI verde + suite de testes (F1 ≥ 0.3 guard, unit tests)
  - Deadline: **M5**

**Scorers de Código:**
- [ ] Substituir `bert-base-uncased` por CodeBERT (`microsoft/codebert-base`)
  - Documentar versão e limitações
  - Deadline: **M4**

#### 2.2.2 Entregáveis

- ✅ **Todos os High-priority gaps do `PROPOSAL.md`** resolvidos
- ✅ **CI verde** com assertions (F1 ≥ 0.3 guard + unit tests)
- ✅ **Pilot RQ1** (10 issues): confirms measurement pipeline works
- ✅ **Execution trace schema** + sample artifacts (auditable replay)
- ✅ **Relatório κ-pilot:** 10 items, 3+ engineers, κ ≥ 0.6 ou justificativa para M3
- ✅ **Testability gate** implementado e documentado
- ✅ **Determinism micro-study:** temperature=0 + seed + variance report

#### 2.2.3 Status de Risco para M5

| Risco | Descrição | Remediation | Target Status |
|---|---|---|---|
| R7 | Métrica SOLID não implementada | SonarQube/Roslyn + pilot κ ≥ 0.6 | **CLOSED** |
| R8 | Harness incompleto | `_run_*_trial` wired; artifacts persisted | **CLOSED** |
| R9 | Determinismo faltando | `temperature=0` + `seed` + micro-study | **CLOSED** |
| R10 | Scorer mismatch | CodeBERT em lugar de bert-base-uncased | **CLOSED** |
| R11 | Testes faltando | Unit tests `IntentPlanner` + `ExplanationService` | **CLOSED** |
| R13 | Artefatos incompletos (stubs) | Remover ou implementar `analyzer.py` | **CLOSED** |
| R15 | Testability gate faltando | Implementado; pre-requisito interpretativo | **CLOSED** |

---

### ⏰ FASE 2.5: Iteração I — Validação de Pilot (Final M5 → M6)
**Objetivo:** Validar pipeline experimental antes de scale para 50 issues.  
**Gate de Go/No-Go:** Decisão crítica antes de investir em coleta completa.

#### 2.2.5.1 Atividades-chave

- [ ] **Executar pilot de 10 issues** (reusing preparação de Fase 2)
  - RQ1: 5 issues com `IntentPlanner` — plans expõem SRP/OCP/DIP?
  - RQ2–RQ4: 5 issues supervisado vs. baseline — SOLID delta compute OK?
  - Deadline: **M5 final (fim semana)**

- [ ] **Validação de Métricas:**
  - Rodar análise estática em 10 outputs — SonarQube/Roslyn OK?
  - Validar κ com 3+ engenheiros em 10 outputs — κ ≥ 0.6?
  - Capturar violações SOLID before/after — delta calculável?
  - Deadline: **M5 final**

- [ ] **Validação de Determinismo:**
  - Rodar 2x mesma issue com `temperature=0` + seed — outputs idênticos?
  - Reportar residual variance se houver
  - Deadline: **M5 final**

- [ ] **Revisão do protocolo de paráfrases (RQ3):**
  - Testar 3 paráfrases em 2 issues — variedade adequada?
  - Refinar estilos de paráfrase se necessário
  - Deadline: **M5 final**

- [ ] **Decision Meeting com Orientador:**
  - Apresentar pilot results
  - Go/No-Go: Prosseguir com scale (30–50 pares por RQ)?
  - Se No-Go: refinements adicionais (estender Fase 2 por 1–2 semanas)
  - Deadline: **M6 início**

#### 2.2.5.2 Go-Decision Criteria

✅ **GO para Fase 3 completa** se:
- Pelo menos 8/10 issues rodam sem erros críticos
- κ ≥ 0.6 em 10 outputs (3+ engenheiros)
- SOLID delta calculável em ≥8/10 issues
- Temperature=0 + seed produzem outputs deterministicamente idênticos OU variance documentada é pequena
- Paráfrases parecem semanticamente coerentes

❌ **NO-GO** (volta à Fase 2 refinements) se:
- κ < 0.6 (rubric não pronto; need reannotation pilot)
- SOLID delta não calculável (SonarQube/Roslyn misconfigured)
- Determinismo quebrado (residual variance alto)
- Mais de 3/10 issues com erros críticos

#### 2.2.5.3 Entregáveis

- ✅ **Pilot report:** 10 issues, results por RQ, κ score
- ✅ **Decision memo:** Go/No-Go assinado pelo orientador
- ✅ **Refinement doc:** se No-Go, listar ajustes necessários + cronograma revisado

---


**Objetivo:** Coletar dados brutos para RQ1–RQ4.

#### 2.3.1 Atividades-chave

**Execução do Experimento RQ1–RQ2:**
- [ ] Executar **budget prático v1** (3–5 sets × 10 issues pareados = 30–50 pares)
  - Cada set: mesmo repo, mesma LLM, mesmas condições de run
  - Referência: [`docs/experiments/experiment-design.md`](experiments/experiment-design.md)
  - Deadline: **M6/M7**
- [ ] Armazenar em `data/experiments/runs/`
  - JSON versionado
  - Provenance: ruleset version, timestamp, scope
  - Deadline: **M6/M7**

**RQ1 — Codificação de Taxonomia:**
- [ ] Executar RQ1 pilot (3–5 sets × 10 issues = 30–50 observações)
  - Gerar planos com `IntentPlanner`
  - Inspecionar se planos expõem SRP/OCP/DIP explicitamente + entities rastreáveis
  - Deadline: **M6**

**RQ2 — Redução de Violações SOLID:**
- [ ] Executar RQ2 paired experiment (3–5 sets × 10 = 30–50 pares supervisado vs. baseline)
  - Coletar delta SOLID via análise estática
  - Deadline: **M6/M7**

**RQ3 — Robustez a Paráfrases:**
- [ ] Construir corpus de paráfrases (3–5 sets × 10 tasks × 10 paráfrases = 300–500 runs)
  - 10 estilos: formal spec, casual bug report, imperative, passive, non-native speaker phrasing, etc.
  - Manter repo/issue/revision fixos
  - Deadline: **M7**
- [ ] Executar RQ3 paraphrase robustness (supervisado + baseline)
  - Coletar verdicts (accept/revise/reject)
  - Deadline: **M7/M8**

**RQ4 — Corpus Legacy:**
- [ ] Executar RQ4 paired experiment no subset legacy (3–5 sets × 10 = 30–50 pares)
  - Mesmo protocolo que RQ2, mas apenas repos "legacy"
  - Deadline: **M8**

**RQ4a — Configuração (Strictness):**
- [ ] Executar experimento de configuração: `strictness ∈ {low, medium, high}`
  - 3–5 sets × 10 = 30–50 pares por nível
  - DVs: verdict distribution, SOLID delta, acceptance/escalation rates
  - Deadline: **M8**

**Qualidade e Aúdito de Dados:**
- [ ] Validar integridade de dados (missing values, outliers, LLM failures)
  - Deadline: **M8**
- [ ] Capturar metadados de provenance (versão ruleset, timestamps, scope)
  - Deadline: **M8**

#### 2.3.2 Entregáveis

- ✅ **Raw experiment data** (3–5 sets, anonymized, versioned JSON)
  - RQ1: 30–50 plan observations
  - RQ2: 30–50 SOLID delta pairs (supervisado vs. baseline)
  - RQ3: 300–500 paraphrase runs (10 per task)
  - RQ4: 30–50 legacy pairs
  - RQ4a: 90–150 config-level pairs
- ✅ **Data quality report:** missing values, outliers, LLM failures
- ✅ **Provenance tracking:** ruleset versions, timestamps, pinned model tags

#### 2.3.3 Status de Risco para M8

| Risco | Descrição | Target Status |
|---|---|---|
| R6 | Taxonomia incompleta | Edges + ISO25010 mapping finalizados antes de M6 |
| R12 | Drift de CSV | Linter + CI gate para CSV integrity |
| R14 | Input injection (issue content) | Sanitization + "untrusted" framing |
| R16 | Annotation readiness | Rubric finalizado; 10-item κ-pilot done antes de M6 |

---

### ⏰ FASE 3.5: Iteração II — Análise Preliminar e Refinement de Protocolo (M8 → M9)
**Objetivo:** Validar análise estatística antes de confirmar resultados finais. Detectar anomalias de dados e ajustar protocolo se necessário.

#### 2.4.1 Atividades-chave (Semana M8 final / M9 início)

**Data Cleaning e QA:**
- [ ] Validar integridade de dados coletados (todas as 30–50 pares por RQ)
  - Missing values? Outliers? LLM failures?
  - Deadline: **M8 final**

- [ ] Verificar provenance integrity
  - Ruleset versions todas consistentes?
  - Model tags salvos corretamente?
  - Temperature=0 + seed aplicados em todos os runs?
  - Deadline: **M8 final**

**Análise Preliminar (Exploratory):**
- [ ] **RQ1:** Review piloto de 10–15 plans
  - SRP/OCP/DIP coverage ainda ≥80%?
  - Se cair abaixo, qual é o pattern de falha?
  - Deadline: **M9 início**

- [ ] **RQ2:** Calcular SOLID delta preliminar em 50 pares
  - Mediana improvement preliminary: ≥10 pp ou menor?
  - Distribution shape: normal ou skewed?
  - Deadline: **M9 início**

- [ ] **RQ3:** Consistency ratio preliminar em 10–20 paráfrases
  - Média consistency supervisado vs. baseline?
  - Teste preliminar (McNemar's ou similar)?
  - Deadline: **M9 início**

- [ ] **RQ4:** Filtrar subset legacy, calcular delta preliminar
  - Delta > 0 em legacy subset, ou ≤ 0?
  - Effect size comparável RQ2, ou menor?
  - Deadline: **M9 início**

**Decision Point — Refinery Adaptations:**
- [ ] **Reunião com Orientador (M9 início):**
  - Revisar preliminary results
  - Detectado algum problema fundamental?
    - Exemplo 1: mediana RQ2 < 5 pp (weak effect) → ajustar scope da RQ (redefinir "success") ou reconhecer limitação
    - Exemplo 2: κ-validation pendente → estender M10 para completar?
    - Exemplo 3: Distribuição muito skewed → mudar teste estatístico de Wilcoxon para outro?
  - Deadline: **M9 início-meio**

- [ ] **Protocolo Refinement (se necessário):**
  - Ajustar alpha, effect thresholds, statistical test se preliminary findings sugerem
  - Documentar rational para qualquer mudança (preregistro update: "post-hoc adaptations")
  - Deadline: **M9 meio**

- [ ] **Final Protocol Lockdown:**
  - Freeze hipóteses, baselines, DVs, testes estatísticos
  - Announce: "Analysis code is now locked for confirmatory phase"
  - Deadline: **M9 meio** ← **HARD DEADLINE**

#### 2.4.2 Quality Gates (Decision Tree)

```
M8 Coleta Completa (30–50 pares)
  ├─ Data Quality OK? (no outliers, provenance consistent)
  │   ├─ YES
  │   │   └─ RQ1–RQ4 Preliminary Analysis
  │   │       ├─ Major anomaly detected? (κ crash, effect reversed, etc.)
  │   │       │   ├─ YES → ADAPT Protocol (M9 início-meio) → Re-estimate, document
  │   │       │   └─ NO  → Protocol Locked (M9 meio)
  │   │       └─ Proceed to M9–M11 Confirmatory Analysis
  │   └─ NO
  │       └─ Data Remediation (M8 final extend 1–2 weeks) → Rechecklist
  └─ Deadline: M9 início-meio
```

#### 2.4.3 Entregáveis

- ✅ **Data quality report:** Missing values, outliers, provenance log
- ✅ **Preliminary analysis report:**
  - RQ1: coverage % + sample plan review
  - RQ2–RQ4: mediana delta, effect size, preliminary p-value range
- ✅ **Protocol amendment memo:** (if applicable)
  - Rational for any changes to hypothesis / test / threshold
  - Signed off by advisor + preregistered
- ✅ **Analysis code lock:** Confirmatory scripts frozen; code version tagged

#### 2.4.4 Status de Risco para M9

| Risco | Descrição | Mitigação | Target Status |
|---|---|---|---|
| R3 | Statistical rigor compromised | Preliminary analysis catches protocol drift early | **MONITOR** |
| R7 | Metric validity issue detected | Pre-emptive recalibration before confirmatory phase | **MITIGATE** |
| R12 | Data quality issues | Clean data before analysis; provenance validated | **RESOLVE** |

---

### ⏰ FASE 4: Ciclo de Rigor — Análise Confirmativa (Meses 9–11)
**Objetivo:** Produzir evidência estatística confirmativa para hipóteses RQ1–RQ4 (com protocolo locked em M9 meio).

#### 2.5.1 Atividades-chave (M9 meio → M11)

**Análise Confirmativa (Preregistered Protocol Locked):**
- [ ] **RQ1 — Confirmatory Design Review**
  - Formal review against locked success criteria
  - Deadline: **M9 (início-meio, aproveitando preliminary)**

- [ ] **RQ2 — Wilcoxon Signed-Rank (Confirmatory)**
  - Dados: 30–50 delta SOLID pairs (supervisado vs. baseline), locked protocol
  - Reportar: mediana per-set + pooled, p-value (two-tailed), effect size (r), 95% CI
  - Critério de sucesso (locked): mediana ≥ 10 pp, p < 0.05
  - Deadline: **M9 (final)**

- [ ] **RQ3 — McNemar's Test (Confirmatory)**
  - Dados: verdicts concordando com maioria / 10 paráfrases (locked protocol)
  - Reportar: consistency ratio supervisado vs. baseline, McNemar p-value, gap
  - Critério de sucesso (locked): consistency ≥ 0.80, gap > 0, p < 0.05
  - Deadline: **M10 (início)**

- [ ] **RQ4 — Wilcoxon (Legacy Subset, Confirmatory)**
  - Dados: 30–50 delta SOLID pairs (legacy-only repos, locked protocol)
  - Reportar: mediana, p-value, effect size (r), compare effect size vs. RQ2
  - Critério de sucesso (locked): mediana > 0, p < 0.05, effect size ≥ medium
  - Deadline: **M10 (meio)**

- [ ] **RQ4a — ANOVA/Kruskal-Wallis (Confirmatory)**
  - Dados: verdict distribution + SOLID delta por strictness level (90–150 pares)
  - Reportar: test statistic, p-value, post-hoc (if significant)
  - Deadline: **M10 (final)**

- [ ] **Multiple Comparison Correction:**
  - Bonferroni ou Benjamini-Hochberg across all RQ tests
  - Deadline: **M10 (final)**

**Validação com Humanos (κ-based):**
- [ ] Executar annotation study (confirmatory)
  - ≥3 engenheiros sênior em stratified sample de 20–30 outputs
  - Validar labels: overall_verdict, pattern adoption (Strangler Fig, ACL, etc.)
  - Target κ ≥ 0.6; report ambiguity / edge cases
  - Deadline: **M10 (fim)**

**Survey de Confiança/Controle/Usabilidade:**
- [ ] Design de instrumento: Likert items (5-point scale) sobre:
  - Perceived trust in verdicts
  - Perceived control over configuration
  - Usability of planning output
  - Deadline: **M10 início** (finalize questions)
  
- [ ] Recruitment: N ≥ 20 developers
  - Stratified by experience level if possible
  - IRB/ethics decision documented
  - Deadline: **M10 fim**
  
- [ ] Executar survey; coletar + analisar dados
  - Descriptive stats (mean, SD per item)
  - Cronbach's α (inter-item reliability)
  - Correlations between trust/control/usability
  - Deadline: **M11 início**

**Escrita de Resultados:**
- [ ] Seção de Resultados (confirmatory findings)
  - Tabelas: p-values, effect sizes, CIs, κ scores
  - Deadline: **M11 meio**

- [ ] Seção de Discussão (preliminary)
  - Achados vs. RQs, practical implications, limitations
  - Deadline: **M11 fim**

#### 2.4.2 Entregáveis

- ✅ **Relatório de análise confirmativa:**
  - RQ1: Design-review findings (locked criteria)
  - RQ2: Wilcoxon results, mediana improvement, p-value, effect size, 95% CI
  - RQ3: McNemar results, consistency ratio, gap, p-value
  - RQ4: Wilcoxon on legacy subset, effect size vs RQ2, p-value
  - RQ4a: ANOVA/Kruskal-Wallis, effect size, post-hoc
  - Multiple-comparison correction applied
- ✅ **Validação humana (κ):** Cohen's κ ≥ 0.6 (ou documented edge cases)
- ✅ **Survey data (anonymized):** N ≥ 20, descriptive stats, Cronbach's α, correlations
- ✅ **Rascunho de Discussão + Implications**

#### 2.4.3 Status de Risco para M11

| Risco | Descrição | Target Status |
|---|---|---|
| R3 | RQs falsificáveis | Negative results reportados como válidos |
| R7 | Métrica SOLID válida | Pilot κ ≥ 0.6; ameaças à validade documentadas |
| R16 | Dados humanos (κ + survey) | κ confirmatory done; survey N ≥ 20 |

---

### ⏰ FASE 5: Ciclo de Rigor — Escrita e Submissão (Meses 12–14)
**Objetivo:** Produzir paper publicável e capítulo de tese.

#### 2.5.1 Atividades-chave

**Escrita de Seções:**
- [ ] **Introduction**
  - Problem statement, motivação, research gap (DSR G1)
  - Deadline: **M12**

- [ ] **Related Work**
  - SWE-bench, SWE-agent, Plan4Code, OpenHands, ISO 25010
  - Gap Ledger: closest prior art + delta + novelty positioning
  - Deadline: **M12**

- [ ] **Methodology (DSR)**
  - 7 guidelines Hevner et al. mapeadas
  - 3 ciclos DSR (Relevance, Design, Rigor)
  - Deadline: **M12**

- [ ] **Design do Artefato**
  - Arquitectura supervisor (Stage 1 + Stage 2)
  - Taxonomia (estrutura, ISO 25010 mapping)
  - Deadline: **M12/M13**

- [ ] **Experiment Design**
  - RQ operationalization, hypotheses, DVs, statistical tests
  - Corpus description, procedure details
  - Deadline: **M13**

- [ ] **Results**
  - (Já rascunhado em M11)
  - Completar com gráficos/tabelas finais
  - Deadline: **M13**

- [ ] **Threats to Validity**
  - Interna: temperature, seed, prompts cegados
  - Construto: painel κ, versioned instruments
  - Externa: mix legacy+ativos, stratified sampling
  - Conclusão: non-parametric + preregistro
  - Deadline: **M13**

- [ ] **Discussion + Implications**
  - Achados vs. RQs, practical implications, limitations
  - Deadline: **M13**

- [ ] **Conclusion + Future Work**
  - Summary, open problems, extensibility
  - Deadline: **M13**

**Review e Polimento:**
- [ ] Review interno com orientador
  - Address feedback
  - Deadline: **M13**

- [ ] Seleção de venue
  - Opções: ICSE, FSE, TOSEM, EMSE, ICSE Companion
  - Formato accordingly
  - Deadline: **M13**

- [ ] Submissão
  - Deadline: **M14**

**Artefatos de Replicabilidade:**
- [ ] Replication package
  - Git hashes (components, ruleset, taxonomia)
  - Pinned versions (model tag, SonarQube version, scorer version)
  - Prompts salvos + outputs anonymizados
  - One-command rerun para subset
  - Deadline: **M14**

#### 2.5.2 Entregáveis

- ✅ **Camera-ready paper draft** (ICSE/FSE/TOSEM format)
- ✅ **Paper submitted**
- ✅ **Replication package (archived)**
- ✅ **Tese capítulo (Methodology + Results + Discussion)**

---

## 3. Critérios de Sucesso por RQ

| RQ | Critério | Métrica | Threshold | Fase de Validação |
|---|---|---|---|---|
| **RQ1** | Codificação bem-sucedida | Cobertura de plans | Plans expõem SRP/OCP/DIP explicitamente + linked entities rastreáveis | M6 (Fase 3) |
| **RQ2** | Redução SOLID verificada | Wilcoxon signed-rank | Mediana ≥ 10 pp; p < 0.05 | M9 (Fase 4) |
| **RQ3** | Robustez a paráfrases | McNemar's test | Consistency ≥ 0.80; gap supervisado > baseline | M10 (Fase 4) |
| **RQ4** | Generalização em legacy | Wilcoxon signed-rank (legacy subset) | Mediana > 0; p < 0.05; effect size comparable RQ2 | M10 (Fase 4) |
| **RQ4a** | Configurabilidade | ANOVA/Kruskal-Wallis | Verdict distribution + delta dependem de strictness | M10 (Fase 4) |

---

## 4. Milestones Críticos (Marcos de Go/No-Go)

| Milestone | Fase | Deadline | Go-Decision Criteria | No-Go Fallback |
|---|---|---|---|---|
| **M3: Qualification** | 1 (Relevance) | fim M3 | RQs finalizadas + SLR integrado + corpus confirmado | Estender M1–M3 |
| **M5: Prototype Ready** | 2 (Design: Hardening) | fim M5 | CI verde + pilot SOLID κ ≥ 0.6 + determinism validated | Estender Phase 2 |
| **M5→M6: Pilot Validation** | 2.5 (Iteração I) | M6 início | 8/10 issues OK + κ ≥ 0.6 + Go/No-Go signed | Refinements (M6 extend) |
| **M8: Data Collection Done** | 3 (Design: Data) | fim M8 | 30–50 pairs per RQ collected + data quality report | Estender Phase 3 |
| **M8→M9: Analysis Lock** | 3.5 (Iteração II) | M9 meio | Preliminary analysis done + protocol locked | Extend M9 início-meio |
| **M11: Analysis Complete** | 4 (Rigor: Confirmatory) | fim M11 | Todos p-values + κ reportados + survey N ≥ 20 | Estender Phase 4 |
| **M14: Submitted** | 5 (Rigor: Writing) | fim M14 | Paper submitted + replication package archived | Estender Phase 5 ou target alterno venue |

---

## 5. Dependências Críticas e Sequenciamento

```
Fase 1 (M1–M3)
  ├─→ Literature review completo
  ├─→ RQs finalizadas + null hypotheses
  ├─→ Corpus definido (5 repos)
  └─→ Requisitos congelados
         ↓
Fase 2 (M4–M5)
  ├─→ Implementar baseline (zero-shot)
  ├─→ Integrar análise estática (SOLID)
  ├─→ Determinism controls (temp=0, seed)
  ├─→ κ-pilot (annotation validation)
  └─→ Testability gate
         ↓
┌────────────────────────────────────────┐
│ FASE 2.5: M5→M6 — ITERAÇÃO I          │
│ Pilot 10 issues + validation + Go/No-Go│
│ ↓                                       │
│ Decision: Prosseguir com scale? Refine?│
└────────────────────────────────────────┘
         ↓ [GO]
Fase 3 (M6–M8)
  ├─→ Executar RQ1–RQ4 runs (30–50 pares cada)
  ├─→ Coletar corpus de paráfrases (RQ3)
  └─→ Validar integridade de dados
         ↓
┌────────────────────────────────────────┐
│ FASE 3.5: M8→M9 — ITERAÇÃO II          │
│ Preliminary analysis + protocol refine  │
│ ↓                                       │
│ Decision: Protocol adaptations needed?  │
│ → Lock analysis code (hard deadline M9) │
└────────────────────────────────────────┘
         ↓ [Locked]
Fase 4 (M9–M11)
  ├─→ Análise confirmativa (preregistered)
  ├─→ Annotation study (κ-based)
  └─→ Survey (trust/control)
         ↓
Fase 5 (M12–M14)
  ├─→ Escrita seções (Intro, Related Work, Methodology, etc.)
  ├─→ Review com orientador
  ├─→ Polimento + submissão
  └─→ Replication package
```

---

## 6. Recursos e Responsabilidades

| Ator | Responsabilidades | Fases |
|---|---|---|
| **Pesquisador (autor)** | Design de experimento, implementação, coleta, análise, escrita | 1–5 |
| **Orientador** | Revisão, validação scientific rigor, feedback | 1, 2, 4, 5 |
| **Painel de engenheiros sênior** | Annotation (κ-based validation) | 2, 4 |
| **Comunidade (survey)** | Tool-use survey (trust/control) | 4 |
| **Ferramentas externas** | SonarQube/Roslyn (análise estática), LocalAI (LLM) | 2–4 |

---

## 7. Monitoramento de Riscos por Fase

### Riscos de **Fase 1** (Relevance)
- **R1 (DSR framing)** — Mitigation: Hevner mapping in M1
- **R2 (Novelty gap)** — Mitigation: SLR integration + narrow claims in M1
- **R3 (RQ falsifiability)** — Mitigation: explicit H₀ + baselines in M2
- **R4 (Data privacy)** — Mitigation: public repos only; IRB decision in M2
- **R5 (CSV vs. Ontology)** — Mitigation: DSR trade-off justification in M1

### Riscos de **Fase 2 + 2.5** (Design: Hardening + Pilot Validation)
- **R6 (Taxonomy incomplete)** — Mitigation: ISO25010 + edges by M2; linter in Phase 2
- **R7 (SOLID metric)** — Mitigation: SonarQube/Roslyn + κ-pilot in M5; validated in M5→M6
- **R8 (Reproducibility)** — Mitigation: trial artifact persistence + provenance logging by M4
- **R9 (LLM determinism)** — Mitigation: temperature=0 + seed + micro-study in M4; validated in M5→M6
- **R10 (Scorer mismatch)** — Mitigation: CodeBERT by M4
- **R11 (Test coverage)** — Mitigation: unit tests in M4
- **R13 (Artifact stubs)** — Mitigation: analyzer.py removed/implemented in M4
- **R14 (Input injection)** — Mitigation: sanitization + logging in M4
- **R15 (Testability gate)** — Mitigation: gating rule + per-repo test harness in M5

### Riscos de **Fase 3 + 3.5** (Design: Data Collection + Preliminary Analysis)
- **R6 (CSV validation)** — Mitigation: CI linter gate by M6
- **R12 (Data quality)** — Mitigation: validation report in M8; preliminary analysis in M8→M9
- **R16 (Human-data readiness)** — Mitigation: κ-pilot done before M6; recruitment plan in M5; confirmed in M8→M9

### Riscos de **Fase 4** (Rigor: Confirmatory Analysis)
- **R3 (Statistical rigor)** — Mitigation: Wilcoxon/McNemar + multiple-comparison correction in M9–M10 (with locked protocol)
- **R7 (Measurement validity)** — Mitigation: κ-based annotation + threat-to-validity section in M11
- **R16 (κ + survey)** — Mitigation: κ ≥ 0.6 in M10; survey N ≥ 20 in M11

### Riscos de **Fase 5** (Rigor: Writing)
- **R1, R2, R3** — Mitigation: Related Work + Methodology + Threats sections articulate rigor

---

## 8. Qualidade e Entregáveis por Fase

| Fase | Output | Quality Gate | Owner | Deadline |
|---|---|---|---|---|
| **1** | Requirements + SLR + Corpus | Requisitos congelados; RQs assinadas | Pesquisador + Orientador | M3 |
| **2** | Prototipo endurecido | CI verde + κ-pilot ≥ 0.6 + determinism validated | Pesquisador | M5 |
| **2.5** | Pilot report + Go/No-Go | 8/10 issues OK; κ ≥ 0.6; Decision signed | Pesquisador + Orientador | M6 início |
| **3** | Dados brutos + report | 30–50 pares per RQ + data quality validated | Pesquisador | M8 |
| **3.5** | Preliminary analysis + Protocol lock | Analysis code locked; decisions documented | Pesquisador + Orientador | M9 meio |
| **4** | Análise confirmativa + κ + survey | p-values + κ ≥ 0.6 + N ≥ 20 (survey) | Pesquisador + Orientador | M11 |
| **5** | Paper + Replication package | Peer-ready draft + archived artifacts | Pesquisador + Orientador | M14 |

---

## 9. Timeline Consolidada (Gantt Summary)

```
M1  M2  M3  M4  M5  M6  M7  M8  M9  M10 M11 M12 M13 M14
|---|---|---|---|---|---|---|---|---|----|----|----|----|
Fase 1: Relevance
■■■
        Fase 2: Design (Hardening)
        ■■■
           ↓ Iteração I (Pilot validation)
           ▼-----▼
        Fase 2.5: M5→M6 (Pilot + Go/No-Go)
                  ■
                 Fase 3: Design (Data Collection)
                 ■■■
                    ↓ Iteração II (Analysis + Protocol Refinement)
                    ▼-----▼
                 Fase 3.5: M8→M9 (Preliminary Analysis + Lock)
                         ■
                        Fase 4: Rigor (Confirmatory Analysis)
                        ■■■
                           Fase 5: Rigor (Writing + Submission)
                           ■■■
```

### Ciclos de Iteração Explícitos:
- **M5→M6:** Pilot 10 issues → κ-validation → Scale decision
- **M8→M9:** Preliminary analysis → Protocol refinement → Analysis lock


---

## 10. Referências de Documentação

- **Design da Pesquisa:** [`docs/DESIGN_DE_PESQUISA.md`](DESIGN_DE_PESQUISA.md)
- **Materiais e Métodos:** [`docs/MATERIAIS_E_METODOS.md`](MATERIAIS_E_METODOS.md)
- **Proposal:** [`docs/PROPOSAL.md`](PROPOSAL.md)
- **Timeline original:** [`docs/timeline.md`](timeline.md)
- **Requisitos (Volere):** [`docs/requirements/requirements.md`](requirements/requirements.md)
- **Experiment Design:** [`docs/experiments/experiment-design.md`](experiments/experiment-design.md)
- **Riscos e Mitigações:** [`docs/risks/risk-register.md`](risks/risk-register.md)
- **Design Science:** [`docs/risks/design-science-framing.md`](risks/design-science-framing.md)
- **RQ Falsificabilidade:** [`docs/risks/rq-scope-falsifiability.md`](risks/rq-scope-falsifiability.md)
- **Métricas:** [`docs/requirements/metrics.md`](requirements/metrics.md)

---

## 11. Versioning

| Versão | Data | Alterações |
|---|---|---|
| **v1.0** | 2026-05-31 | Consolidação de cronograma baseado em `docs/timeline.md` + `DESIGN_DE_PESQUISA.md` + `MATERIAIS_E_METODOS.md` + `risk-register.md` |
| **v1.1** | 2026-05-31 | Adição de 2 iterações explícitas (Fase 2.5: M5→M6 + Fase 3.5: M8→M9) com feedback loops e Go/No-Go gates; alinhamento com DSR iterativo |

---

**Última atualização:** 31 de maio de 2026  
**Status:** ✅ Pronto para execução com iterações de feedback incorporadas (condicionado a assinatura de orientador em M1)
