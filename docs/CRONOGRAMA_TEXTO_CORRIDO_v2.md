# Cronograma de Execução — Texto Corrido (v2)
**Supervisor Agent for LLM-Assisted Legacy Software Modernization**

Duração: 24 meses (junho 2026 — maio 2028)

---

## Visão Geral da Estrutura

A pesquisa segue uma arquitetura de **Design Science Research (DSR)** com **dois ciclos completos de coleta, análise e escrita**, permitindo replicação interna e publicação em múltiplos venues (conference para Ciclo I, journal para Ciclo II). Os três ciclos DSR (Relevance, Design, Rigor) distribuem-se ao longo de 24 meses, com decisões go/no-go explícitas em 8 milestones críticos que permitem detecção cedo de anomalias e refinement iterativo.

---

## Ciclo 1: Relevância (Junho–Setembro 2026 / Meses 1–4) — Fase 1

A pesquisa inicia-se com o Ciclo 1 de Relevância, estabelecendo a fundação científica do projeto. Durante os primeiros quatro meses, valida-se o problema de pesquisa, operacionalizam-se as Research Questions (RQs), define-se o corpus de experimentação, e congela-se o protocolo via preregistro. No primeiro mês de junho, finaliza-se especificação de requisitos usando metodologia Volere, ajustando prioridades Must/Should/Could com o orientador e congelando o requirements document para que Fase 2 possa começar com escopo bem-definido. Em paralelo, integra-se o Systematic Literature Review (SLR) na seção de Related Work, identificando trabalhos proximais (SWE-bench, SWE-agent, Plan4Code, OpenHands, abordagens clássicas de refatoração) e criando um "Gap Ledger" que explicitamente lista: closest prior art, o que cada um cobre, o que deixa aberto, e como cada contribuição do presente projeto mapeia a um gap específico. Isso estabelece rastreabilidade 1-para-1 entre novelty claims e gaps reais.

Durante a segunda semana de junho, revisa-se o framing de Design Science Research mapeando os 7 guidelines de Hevner et al. (2004) ao projeto: Design as Artifact (agente supervisor construído iterativamente), Problem Relevance (entrevistas com desenvolvedores validan pain point), Design Evaluation (pilot, preliminary, confirmative phases), Research Contributions (Gap Ledger), Research Rigor (testes não-paramétricos, preregistro, multiple comparison correction), Design as Search Process (iterações explícitas com feedback), Communication (conference + journal papers + tese). Cria-se um documento de Design Science Framing que será referência metodológica durante 24 meses.

Em paralelo, operacionaliza-se cada Research Question. Para RQ1 (agent gera plans com design constraints SOLID explícitos?), define-se hypothesis H1, dependent variables (SRP/OCP/DIP coverage %, entidades rastreáveis %), teste estatístico (design review + manual inspection com κ), e procedure (ambas condições em 30–50 issues). Para RQ2–RQ4 (efeito em SOLID delta), hypothesis sobre delta > 0, DVs (mediana delta, effect size r), teste (Wilcoxon signed-rank pareado), procedure (supervisado vs. baseline). Para RQ3 (robustez a paráfrases), hypothesis sobre verdicts consistentes, DV (consistency ratio), teste (McNemar). Para RQ4a (efeito de configuração), hypothesis sobre strictness levels, DVs (delta por config, verdict distribution), teste (Kruskal-Wallis com post-hoc). Cada RQ é operacionalizada em um memo formal.

Na terceira semana de junho até final de julho, identifica-se e valida-se o corpus de experimentação: 5 repositórios C# públicos (GitHub) com permissive licenses, functional issue trackers, mix de legacy systems (com technical debt identificado) e actively maintained projects. Cada repo é avaliado por: (a) presença de SOLID violations identificáveis via static analysis, (b) tamanho suficiente (100–500 issues potencialmente tratáveis), (c) comunidade ativa (comentários em issues, maintainers responsivos), (d) acesso público aos git hashes e build artifacts. Documenta-se corpus selection report com motivação de cada repositório.

Até final de julho, desenha-se o experiment design completo com flowchart: para cada issue, (1) Supervisor e Baseline conditions executam em paralelo, (2) Output é coletado (plans, verdicts, SOLID delta), (3) Human validation acontece (κ-based), (4) Survey feedback é coletado, (5) Provenance é auditada. Documenta-se procedure completo com timing estimates, responsáveis, e quality gates.

Em agosto, pré-registra-se o protocolo no Open Science Framework (OSF). As hypotheses, DVs, testes estatísticos, corpus, e procedure são congelados e linkados publicamente. Isso compromete o pesquisador antes de ver dados, prevenindo p-hacking. A versão congelada é armazenada em dois repositórios (OSF + git tag).

Até final de agosto, redige-se Introduction + Related Work draft (~4–5 páginas). Introduction descreve problem statement (desenvolvedores precisam suporte estruturado para refatoração SOLID), motivação prática (ferramentas existentes carecem de supervisão), e research gap (falta de artefatos que combinem LLM com critérios de qualidade estruturados). Related Work cobre SWE-bench, SWE-agent, Plan4Code, OpenHands, ISO 25010, e inclui Gap Ledger explícito.

Ao final de M4, toma-se decisão go/no-go: RQs estão operacionalizadas com hypotheses e DVs claros? Corpus está validado com 5 repos confirmados? Preregistro está público em OSF? Se sim, prossegue-se à Fase 2 com confiança. Se não, estende-se Fase 1 por 2–3 semanas. Entregam-se: RQ Operationalization document (congelado), Corpus selection report com motivação, Experiment Design document com flowchart, preregistro URL (OSF), Introduction + Related Work draft.

---

## Ciclo 2: Design (Outubro 2026–Fevereiro 2027 / Meses 5–9) — Fase 2

O Ciclo 2 de Design inicia-se em outubro 2026 com a Fase 2, cujo objetivo é resolver todos os gaps de implementação bloqueadores e criar uma baseline funcional pronta para experimentos reproduzíveis. Durante os 5 meses de outubro até fevereiro, o foco concentra-se em instrumentar controles de determinismo, implementar captura de dados SOLID, endurecercer a harness experimental, e validar tudo via pilot de 10 issues com κ ≥ 0.6.

Em outubro (primeira semana de M5), adicionam-se os parâmetros `temperature=0` e `seed` ao cliente LLM (LocalAIClient.chat()), garantindo que sejam persistidos em logs de cada trial para auditoria posterior. Temperature=0 desabilita randomness do modelo; seed permite reexecução determinística. Implementa-se logging estruturado de seed + model tag + timestamp em cada trial. Na primeira semana de outubro também, executa-se micro-estudo de determinismo com 5–10 issues, rodando cada issue 2 vezes com temperature=0 e seed idêntica, medindo variância residual nos outputs. Se outputs forem idênticos, determinismo está OK; se houver variância, investigam-se fontes (parallelismo, I/O não-determinístico, etc.).

Em paralelo (segunda semana de outubro), integra-se o motor de análise estática SOLID. Escolhe-se entre SonarQube (análise cloud) ou Roslyn analyzers (C#, local). Pina-se uma versão específica do ruleset (ex: SonarQube 10.2). Documenta-se cuidadosamente o mapeamento: SRP (Single Responsibility Principle) ← regra "Cognitive Complexity > threshold", OCP (Open-Closed Principle) ← "Inheritance hierarchy depth", DIP (Dependency Inversion Principle) ← "Direct instantiation of concrete classes". Implementa-se captura de violação count antes (pré-mudança) e depois (pós-mudança) de código gerado, armazenando em estrutura TrialResult com schema JSON versionado.

Em terceira semana de outubro, implementa-se a condição baseline (zero-shot LLM). Configura-se `nfr_focus=[]` e `relationship_depth=0` no IntentPlanner, desligando toda supervisão por taxonomia. Garante-se que baseline use exatamente o mesmo modelo LLM, temperatura, seed, e pipeline de avaliação que supervisado, diferindo apenas na supervisão. Adiciona-se teste unitário validando que baseline output existe e é parseável.

Até final de outubro, wireiam-se completamente as funções `_run_supervised_trial` e `_run_baseline_trial` em `src/evaluation/reproducibility_experiment.py`. Ambas executam experimento pareado (mesma issue, duas condições) capturando artefatos completos: LLM output bruto, configuração aplicada, model tag, timestamp, seed. Todos artefatos são armazenados em JSON em `data/experiments/runs/` com structure versionado. CI deve passar todos testes.

Em novembro (M6), implementa-se captura completa de execution traces. Para cada run, registra-se: repositório testado, commits/revisions específicas, aprovações do usuário (quem validou?), todos prompts usados (tanto externos quanto internos), todos outputs intermediários, e timestamps. Tudo é armazenado em JSON em `data/experiments/runs/` versionado e rastreável para reexecução. Adiciona-se logging completo: config aplicada, versão do modelo, todas decisões intermediárias.

Ainda em novembro, implementa-se testability gate, um pré-requisito interpretativo: para cada issue, registra-se status de build (compila?), status de testes (testes passam?), contagem de testes adicionados, e delta de cobertura (opcional). Outputs de mudanças que não constroem ou falham testes não podem ser interpretados como "melhor em SOLID" até que problemas sejam resolvidos. Documenta-se instrução de harness de testes por repositório (como rodar tests, como medir coverage).

Em paralelo (novembro), coletam-se métricas de qualidade adicionais onde disponíveis: complexidade ciclomática (cyclomatic complexity), cobertura de testes, duplication ratio, adherência a conventions (coding standard violations), flags de segurança. Cada métrica tem seu tool (ex: SonarQube para CC), versão pinada, e timestamp registrado para provenance.

Em novembro também, substitui-se o scorer de similaridade de código. Implementação anterior usava `bert-base-uncased` genérico; troca-se por `microsoft/codebert-base`, treinado especificamente em código C#. Documenta-se versão e limitações do novo scorer. CI deve rodar teste que valida F1 ≥ 0.3 em amostra de paráfrases conhecidas.

Em dezembro (primeira semana de M7), implementa-se protocolo de paráfrase para RQ3. Define-se 10 estilos semanticamente equivalentes mas superficialmente distintos: (1) especificação formal ("The system shall…"), (2) relatório casual de bug, (3) comando imperativo ("Refactor to…"), (4) descrição passiva, (5) frasagem de falante não-nativo, (6) instruções detalhadas passo-a-passo, (7) abstract requirement ("Make maintainable"), (8) code-focused ("Replace this pattern"), (9) domain-specific jargon, (10) simplified explanation. Para cada paráfrase, mantém-se fixo: repositório, issue, revisão de código testada. Varia-se apenas: wording do prompt e sequência de instruções. Documenta-se protocolo com exemplos.

Até final de dezembro, implementa-se executor de paráfrases que, dado um task-token, gera (manualmente ou automaticamente) as 10 paráfrases variadas semanticamente. Executor roda ambas condições (supervisada e baseline) em cada paráfrase, coletando verdicts e armazenando em JSON indexado por paráfrase ID.

Em dezembro também, adicionam-se testes unitários abrangentes para dois componentes críticos: `IntentPlanner` (gerador de planos) e `ExplanationService` (juiz/explicador). Usa-se mock do cliente LLM multi-modelo. Assertions checam schema validity (output é JSON válido?), determinismo (mesmo input → mesmo output?), e edge cases (input vazio, taxonomia ausente, modelo timeout). Remove-se ou implementa-se qualquer stub remanescente (ex: `src/migration/analyzer.py`). CI deve estar verde com coverage > 60%.

Em janeiro (M8), valida-se tudo via pilot de 10 issues. Para RQ1, toma-se 5 issues e gera-se planos usando IntentPlanner, inspecionando cada plano: constraints de SRP/OCP/DIP estão explicitamente documentados? Entidades são rastreáveis até taxonomia? Coverage alcança ≥80%? Documenta-se coverage percentual e padrões de falha.

Para RQ2–RQ4, toma-se outras 5 issues executando ambas condições (supervisada e baseline), coletando delta SOLID via análise estática. Roda-se com 3+ engenheiros sênior (diferentes dos arquivos, independentes) a validação de 10 labels (overall_verdict = accept/revise/reject), calculando Cohen's κ. Se κ < 0.6, protocolo não está pronto e volta-se para refinements. Valida-se determinismo rodando mesma issue 2x com temperature=0 + seed idêntica, verificando outputs idênticos ou variância documentada.

Para RQ3, toma-se 2–3 issues, gera-se 3 paráfrases de cada (em vez de 10 no pilot), testando se variedade e semântica estão adequadas. Se paráfrases não parecerem semanticamente coerentes, refina-se protocolo.

Até final de fevereiro (fim M9, antes de Coleta I), toma-se decisão go/no-go formal com orientador. Critério GO exige: (a) CI verde com todos testes passando, (b) κ ≥ 0.6 em 10 outputs com 3+ engenheiros, (c) SOLID delta calculável em ≥8/10 issues, (d) temperature=0 + seed produzem outputs deterministicamente idênticos ou variância documentada como pequena, (e) paráfrases parecem semanticamente coerentes, (f) design coverage ≥80%. Critério NO-GO ocorre se κ < 0.6, SOLID delta não calculável, determinismo quebrado, ou >3/10 issues com erros críticos. Se GO, procede-se à Fase 3 (Coleta I) com confiança. Se NO-GO, estende-se M9 por 2 semanas refinement. Entregam-se: CI report (green, all tests), pilot report com 10 issues e κ scores, determinism report, baseline implementation report, testability gate documentation, metrics collection report, paraphrase protocol + executor working.

---

## Ciclo 3a: Rigor — Coleta I (Março–Agosto 2027 / Meses 10–15) — Fase 3 (Ciclo I)

Após go/no-go positivo em M9, inicia-se Ciclo 3a em março 2027 com a Fase 3: Coleta de Dados I. Durante os seis meses de março até agosto, executa-se todos os experimentos em escala completa, coletando 30–50 observações de pares (supervisado vs. baseline) para cada RQ. A estratégia é manter o protocolo congelado (preregistrado em M4), executar sistematicamente, e apenas registrar dados sem interpretação prematura.

Para RQ1, executa-se IntentPlanner em 3–5 sets de 10 issues cada (totalizando 30–50 planos). Cada set mantém fixo: repositório, modelo LLM, condições de execução. Geram-se planos de ação usando IntentPlanner e inspeciona-se cada plano verificando se constraints de SRP/OCP/DIP estão explícitos com entidades rastreáveis até taxonomia. Documenta-se coverage por issue e por set (percentual de issues atendendo critério de ≥80% coverage). Armazena-se em JSON versionado com provenance: versão de ruleset, timestamp, scope (qual nó de taxonomia foi usado).

Para RQ2, executa-se experimento pareado com as mesmas 30–50 observações. Cada observação é uma issue testada em ambas condições (supervisada e baseline). Coleta-se delta SOLID via análise estática, registrando violação count antes (pré-mudança) e depois (pós-mudança) para ambas condições. Armazena-se em JSON indexado por issue ID e condition.

Para RQ3, constrói-se corpus de paráfrases tomando 3–5 sets × 10 tasks (30–50 tasks ancoradas). Para cada task, geram-se 10 paráfrases conforme protocolo (variedade de wording, mantendo semântica). Isso resulta em 300–500 runs totais. Executa-se ambas condições (supervisada e baseline) em cada paráfrase, coletando verdict (accept/revise/reject) de cada run. Armazena-se em JSON com índice de paráfrase, permitindo depois calcular consistency ratio entre condições.

Para RQ4, filtra-se as issues que pertencem ao subset "legacy" identificado a priori durante seleção de corpus em M1–M4. Executa-se experimento pareado apenas nesse subset, coletando 30–50 pares. Coleta-se delta SOLID da mesma forma que RQ2. Armazena-se em JSON separado para legacy subset.

Para RQ4a (configuração), executa-se experimento adicional variando `strictness ∈ {low, medium, high}` (três níveis de severidade do supervisor). Toma-se os mesmos sets e issues, mas agora executa em 3 níveis. Para cada nível, registra-se distribuição de verdicts (counts de accept/revise/reject), delta SOLID, taxa de aceitação (accept / total), taxa de escalação (reject / total). Armazena-se em JSON indexado por config.

Durante os meses de março até agosto (M10–M15), executa-se coleta continuamente, monitorando para erros críticos (LLM timeouts, analysis crashes, data corruption). Em agosto (fim M15), valida-se integridade dos dados coletados verificando missing values, outliers inesperados, LLM failures. Gera-se relatório de qualidade de dados. Confirma-se que metadados de provenance estão completos: versão de ruleset pinada (todos runs com mesma versão?), timestamps corretos, model tag de cada run registrado. Ao final de M15, entregam-se dados brutos de experimento (30–50 pares por RQ, 300–500 paráfrases para RQ3, 90–150 para RQ4a), todos em JSON versionados e anonymizados, relatório de qualidade de dados, e log de provenance.

---

## Ciclo 3b: Rigor — Análise Preliminar I (Setembro–Outubro 2027 / Meses 16–17) — Fase 3.5 (Ciclo I)

Antes de entrar na fase confirmativa de análise estatística, executa-se em setembro (M16) Análise Preliminar I para detectar anomalias nos dados e autorizar protocol refinement se necessário. Na primeira semana de setembro, procede-se ao data cleaning validando integridade de todos 30–50 pares por RQ: tem missing values? outliers inesperados? LLM failures? Verifica-se que provenance está íntegro: todas versões de ruleset são consistentes (nenhuma run com versão diferente?), model tags foram salvos, temperature=0 e seed foram aplicados em todos runs (nenhuma exceção?). Gera-se data cleaning report.

Na segunda semana de setembro, realiza-se análise exploratória preliminar (não confirmativa, apenas descritiva). Para RQ1, revisa-se 10–15 plans amostrados: SRP/OCP/DIP coverage ainda é ≥80%, ou caiu abaixo? Se caiu, qual é o pattern de falha (missing from taxonomy? implementation incomplete?)? Documenta-se coverage preliminary analysis. Para RQ2, calcula-se delta SOLID preliminar em todos 50 pares observando: mediana de melhoria é ≥10 pontos percentuais, ou menor? Distribuição é normal (Shapiro-Wilk test) ou skewed? Calcula-se também IQR, min, max. Documenta-se em preliminary delta analysis. Para RQ3, calcula-se consistency ratio preliminar em 10–20 paráfrases observando: supervisado mais aceito que baseline? Média concordância por paráfrase. Executa-se teste McNemar preliminar. Para RQ4, filtra-se subset legacy, calcula-se delta preliminar: delta > 0 em legacy, ou ≤ 0? Effect size comparável a RQ2, ou menor? Para RQ4a, visualiza-se distribuição de verdicts por strictness: há efeito visual de strictness em acceptance rate?

Ao início de outubro (M17), reúne-se com orientador apresentando todos resultados preliminares. Detectou-se algum problema fundamental que invalida Análise Confirmativa? Exemplos de problemas: (1) mediana RQ2 < 5 pp (effect muito fraco, praticamente nulo), (2) κ-validation ainda pendente (engenheiros não conseguiram labelem), (3) distribuição muito skewed violando suposições de Wilcoxon, (4) anomalias sistemáticas em dados (ex: todas issues de certo repo falharam). Se problemas encontrados, decisão é documentada: Pode-se ajustar scope da RQ (redefinir o que conta como "sucesso")? Ou estender análise com sample adicional? Ou reconhecer limitação e proceder mesmo assim? Se adjustments são necessários, documenta-se rational para cada mudança (preregistro é atualizado com "post-hoc adaptations" claramente marcadas). Qualquer mudança é assinada pelo orientador. Se nenhum problema fundamental, protocolo é congelado para Análise Confirmativa.

No meio de outubro (M17), toma-se decisão de Protocol Lockdown como hard deadline. Congela-se as hipóteses, baselines, DVs (dependent variables) e testes estatísticos. Anuncia-se oficialmente: "Analysis code is now locked for confirmatory phase." Nenhuma outra mudança é permitida sem documentação formal e assinatura. O código de análise é tagged em versionamento (git tag "analysis-locked-M17"). Entregam-se: data quality report, preliminary analysis report per RQ (coverage %, sample plans, mediana delta, effect size, p-value range preliminar), protocol amendment memo (se applicable), analysis code locked e tagged.

---

## Ciclo 3b: Rigor — Análise Confirmativa I (Julho–Outubro 2027 / Meses 16–19, paralelo com Preliminar) — Fase 4 (Ciclo I)

Em paralelo com Análise Preliminar I (M16–M17), inicia-se Análise Confirmativa I em meados de setembro (M18, após protocol lockdown). Executa-se análise estatística confirmativa sob protocolo congelado, complementada por validação humana quantitativa e survey qualitativa.

Para RQ1, conduz-se design review formal com orientador sobre 15–20 planos amostrados aleatoriamente. Verifica-se: SRP/OCP/DIP coverage ≥80%? Constraints documentados explicitamente? Rastreabilidade até taxonomia é clara? Documenta-se percentual de issues atendendo critério. Prazo: M18.

Para RQ2 (efeito principal em issues gerais), executa-se teste estatístico Wilcoxon signed-rank pareado sobre os 30–50 pares de delta SOLID. Reporta-se: mediana de melhoria, intervalo de confiança 95%, p-value unicaudal (H1: mediana > 0), effect size r (formula: Z / √N). Aplica-se critério de sucesso: mediana > 0, p < 0,05, effect size r ≥ 0,3 (médio). Prazo: M18 meio.

Para RQ3 (robustez a paráfrases), executa-se teste de McNemar pareado sobre verdicts em paráfrases comparando supervisado vs. baseline. Reporta-se contagem de concordância/discordância, p-value unicaudal (H1: supervisado mais aceito que baseline), effect size (McNemar effect size, ex: odds ratio). Suporta H1? Prazo: M18 meio.

Para RQ4 (legacy repos), executa-se Wilcoxon signed-rank no subset legacy de 30–50 pares de delta SOLID. Reporta-se mediana, CI 95%, p-value, effect size r. Compara-se effect size com RQ2 (interpretação: legacy beneficia mais, ou menos?). Critério: mediana > 0, p < 0,05, effect size ≥ médio. Prazo: M18 meio.

Para RQ4a (configuração strictness), executa-se ANOVA ou Kruskal-Wallis dependendo de normalidade dos dados (teste Shapiro-Wilk). Variável independente: `strictness ∈ {low, medium, high}`. Variáveis dependentes: verdict distribution (counts), SOLID delta, acceptance rate, escalation rate. Reporta-se F-statistic (ANOVA) ou H-statistic (Kruskal-Wallis), p-value, effect size (η² para ANOVA, ε² para Kruskal-Wallis, target ≥ 0,06 pequeno). Executa-se pós-hoc Tukey (ANOVA) ou Dunn (Kruskal-Wallis) com Bonferroni correction para múltiplas comparações. Prazo: M19 final.

Em M19, aplica-se multiple comparison correction (Bonferroni ou Benjamini-Hochberg) sobre todos os testes de RQ (RQ1–RQ4a) para controlar family-wise error rate (FWER). Todos p-values são ajustados; reporta-se ambos raw e adjusted.

Em paralelo (M18–M19), executa-se human validation study κ-based recrutando ≥3 engenheiros sênior diferentes dos que fizeram pilot. Toma-se stratified sample de 20–30 outputs (priorizando edge cases e issues de baixa confiança do modelo). Engenheiros labelem independentemente: (1) overall_verdict = {accept, revise, reject}, (2) pattern adoption = {Strangler Fig, Branch By Abstraction, Anticorruption Layer, None}. Calcula-se Cohen's κ para ambos labels. Target: κ ≥ 0,6; se cair abaixo, documenta-se ambiguidade/edge cases encontrados e implications para protocolo. Prazo: M19 final.

Em paralelo, desenha-se instrumento de survey (Likert 5-point) sobre 3 construtos: (1) Perceived Trust ("I trust the agent's verdicts about whether code improves maintainability"), (2) Perceived Control ("I can configure priorities to match my project context"), (3) Usability ("The planning output was clear and actionable"). Recruta-se N ≥ 20 developers (target 25–30), stratificando por anos de experiência se possível. Segue-se procedimento ético/IRB e documenta-se consentimento informado. Coleta-se respostas via online form. Analisa-se: descriptive stats (mean, SD por item e por construto), Cronbach's α (inter-item reliability, target ≥ 0,7), correlações entre construtos (Spearman ρ). Prazo para design: M18 início; execution: M18–M19 final; análise: M19 final.

Ao final de M19, escreve-se a seção de Resultados integrando achados de RQ1–RQ4a em narrativa científica. Cria-se tabelas com p-values, effect sizes, CIs, κ scores, descriptive stats de survey formatadas apropriadamente. Finaliza-se Reports confirmative analysis com tabelas consolidadas. Entregam-se: confirmative analysis report (RQ1–RQ4a com p-values, effect sizes, CIs), human validation: κ scores (target ≥ 0.6 ou documented edge cases), survey data (N ≥ 20, mean/SD, Cronbach's α, correlações), Results section draft (tabelas/gráficos finais).

---

## Ciclo 3c: Escrita e Submissão I (Outubro–Dezembro 2027 / Meses 16–20, paralelo com análises) — Fase 5 (Ciclo I)

Em paralelo com Análise Confirmativa I (M16–M19), inicia-se redação de paper para venue conference em outubro (M16 início). A estratégia é paralelizar escrita com análise, reduzindo tempo total e permitindo submissão em M20 (fevereiro 2028) enquanto Ciclo II já começou coleta.

Em M16–M17, escreve-se Introduction. Descreve-se problem statement (desenvolvedores precisam de suporte estruturado para refatoração SOLID-aware), motivação prática (ferramentas existentes carecem de supervisão inteligente), research gap que o projeto pretende preencher (artefatos que combinem LLM com critérios de qualidade estruturados), e alinhamento com DSR. Escreve-se ~2–3 páginas de Introduction focada em engajar leitor com problema real.

Em M17, escreve-se Related Work. Cobre-se SWE-bench (benchmark), SWE-agent (agente autônomo), Plan4Code (planejamento), OpenHands (framework), abordagens clássicas de refatoração, ISO 25010 (qualidade). Cria-se um parágrafo de "Gap Ledger" que lista explicitamente: (1) closest prior art (ex: SWE-agent), (2) o que ele cobre bem (general task automation), (3) o que deixa aberto (SOLID-specific supervision), (4) como cada contribuição mapeado a gap. Cria-se rastreabilidade 1-para-1 entre novelty claims e gaps. Escreve-se ~3–4 páginas de Related Work.

Em M17–M18, escreve-se seção de Methodology (DSR). Mapeia-se os 7 guidelines de Hevner et al. ao presente projeto. Descreve-se os 3 ciclos DSR (Relevance M1–M4, Design M5–M9, Rigor M10–M20 ou além). Explica-se como cada ciclo contribui à robustez. Escreve-se ~2–3 páginas de Methodology DSR.

Em M18, escreve-se seção de Artifact Design. Descreve-se arquitetura do supervisor agent: Stage 1 (IntentPlanner) toma issue de refatoração + taxonomia, gera plano SOLID estruturado com constraints e padrões legados documentados; Stage 2 (ExplanationService) toma output LLM + scores + análise estática, gera verdict (accept/revise/reject) + justificativa. Documenta-se estrutura de taxonomia (nodes, relationships, strictness levels). Mapeamento ISO/IEC 25010 Maintainability characteristics (Modifiability, Modularity, Analyzability) ← SOLID principles (SRP, OCP, DIP). Exemplos de plans para issues reais. Escreve-se ~3–4 páginas de Artifact Design.

Em M18, escreve-se seção de Experiment Design. Operacionaliza-se cada RQ: RQ1 hypothesis, DV (coverage %), teste (design review), procedure, corpus. RQ2–RQ4 hypothesis, DV (delta SOLID), teste (Wilcoxon), procedure, corpus. RQ3 hypothesis, teste (McNemar). RQ4a hypothesis, teste (Kruskal-Wallis), DVs por config. Escreve-se ~4–5 páginas de Experiment Design.

Em M19, escreve-se seção de Results (rascunhada em paralelo com Análise Confirmativa). Tabelas com p-values, effect sizes, CIs, κ scores, survey descriptivos. Gráficos: boxplots de deltas SOLID por RQ, scatter de coverage vs. correctness, heatmap de verdict distribution por config. Narrativa científica sincretizando achados. Escreve-se ~5–6 páginas de Results.

Em M19–M20, conduz-se internal review com orientador. Apresenta-se draft de paper (~20–25 páginas no total). Colhem-se feedbacks críticos (clareza, rigor, novidade). Aplicam-se correções.

Em M20, seleciona-se venue para conference (Ciclo I paper). Opções: ICSE (International Conference on Software Engineering, top venue, ~25% acceptance), FSE (Foundations of Software Engineering, top, ~20% acceptance), ou ICSE Companion (track mais inovador, menos rigor estatístico mas visibilidade). Formata-se paper final de acordo com template LaTeX da venue escolhida. Checa-se limites de páginas (10–15 pp típico), referências, figuras, formato de tabelas.

Em M20, submete-se paper via conference portal. Paper é registrado com número de tracking. Uma cópia é tambén armazenada em git tag "paper-submitted-M20" para versionamento. Entregam-se: camera-ready paper (conference format, ~10–15 pp), paper submitted (tracking number confirmado), replication package draft (data + analysis code tagged).

---

## Ciclo 3d: Coleta de Dados II (Novembro–Dezembro 2027 / Meses 21–22) — Fase 3 (Ciclo II)

Em paralelo com Análise Confirmativa I finalizar em outubro, inicia-se Coleta II em novembro 2027. A estratégia de Coleta II é decidida com orientador em M17: (A) Replicação em novo subset (mesmos 5 repos, diferentes 30–50 issues), (B) Expansão a repos adicionais (2–3 repos novos, 30–50 pares), ou (C) Sub-análise targeted (toma findings de Ciclo I e coleta subset específico para validar).

Assumindo estratégia A (replicação novo subset), em novembro (M21–M22), executa-se Coleta II com mesmos protocolos congelados de M4. Para cada RQ, coleta-se 30–50 pares novos das mesmas 5 repos (mas diferentes issues), mantendo condições (supervisado, baseline, strictness levels). Mesmos data quality checks. Mesmos provenance requirements (versão de ruleset, timestamps, model tags). Ao final de M22, entregam-se: Coleta II datasets (JSON, anonymizados), data quality report II, provenance audit II.

---

## Ciclo 3e: Análise Preliminar II (Janeiro–Fevereiro 2028 / Meses 23–24) — Fase 3.5 (Ciclo II)

Em janeiro (M23), repetem-se data cleaning e análise exploratória preliminar para Ciclo II. Calcula-se deltas preliminares (RQ1–RQ4a) per RQ. Compara-se effect sizes Ciclo I vs. II: Ciclo II confirma Ciclo I? Ou diverge sistematicamente?

Em fevereiro (M24 início), reúne-se com orientador. Ciclo II confirma ou complementa Ciclo I? Se confirmação clara (effect sizes similares, p-values mesmo direção), alta confiança em resultados. Se divergência (e.g., Ciclo II mediana < 0 enquanto Ciclo I > 0), investigam-se anomalias: diferentes repos? diferentes issues? mudança em ambiente (ex: modelo LLM updated?).

Em M24 meio, toma-se decisão de Protocol Lockdown II. Análise code Ciclo II é tagged e congelado (git tag "analysis-locked-II-M24"). Entregam-se: data cleaning report II, preliminary analysis Ciclo II per RQ, replication comparison (effect sizes Ciclo I vs. II), protocol amendment memo II (if applicable).

---

## Ciclo 3e: Análise Confirmativa II (Março–Abril 2028 / Meses 25–26) — Fase 4 (Ciclo II)

Em março–abril (M25–M26), executa-se Análise Confirmativa II sob protocolo congelado. Repete-se Wilcoxon, McNemar, Kruskal-Wallis, human validation, survey para Ciclo II. Reporta-se p-values, effect sizes, κ scores, survey stats.

Em paralelo, executa-se meta-análise ou análise combinada de Ciclo I + II: pooled effect sizes, combined p-values (Fisher's method ou Stouffer's Z), teste de heterogeneidade (Q-test, I²). Resultados robustos em ambos ciclos aumentam confiança. Se Ciclo II contradiz Ciclo I fortemente, documenta-se como limitation e possibilidade de subgroup effects.

Ao final de M26, entregam-se: confirmative analysis report Ciclo II (RQ1–RQ4a), meta-analysis Ciclo I + II (pooled effects, combined p-values, heterogeneity), human validation II (κ scores), survey data II (N ≥ 20), Results section final consolidado.

---

## Ciclo 3f: Escrita e Submissão II (Abril–Maio 2028 / Meses 27–29) — Fase 5 (Ciclo II)

Em abril (M27), inicia-se escrita de paper final para journal (top-tier target: TOSEM, EMSE, ou TSE). Objetivo é integrar resultados de Ciclo I + II em narrativa científica coerente.

Em M27, atualiza-se Introduction e Related Work mantendo Gap Ledger, mas mencionando agora replicação interna como validação de robustez. Escreve-se Methodology (DSR final) detalhando os 2 ciclos completos de coleta-análise. Artifact Design é refinado baseado em feedback de Ciclo I. Experiment Design inclui ambos ciclos.

Em M27–M28, integra-se Results consolidados de Ciclo I + II em tabelas finais, gráficos comparativos, e narrativa. Escreve-se Discussion mapando achados vs. cada RQ, discutindo implicações práticas (ferramentas de refatoração LLM-assisted podem usar supervisão SOLID), implicações teóricas (artefatos DSR permitem replicação interna), e limitações (mix de repos, generalizabilidade a outros idiomas).

Em M28, escreve-se Threats to Validity mapeando cada ameaça e mitigação: validade interna (temperature=0, seed, prompts cegados), construto (κ ≥ 0.6, tools versionados), externa (5 repos, mix legacy+ativos, N ≥ 30 pares), conclusão (testes não-paramétricos, preregistro, correction para múltiplas comparações, replicação Ciclo I + II).

Em M28, escreve-se Conclusion + Future Work sintetizando achados, problemas abertos (escalabilidade, generalizabilidade), extensibilidades (integração em IDEs, feedback loops em produção).

Em M28–M29, conduz-se internal review final com orientador. Colhem-se feedbacks. Aplicam-se correções finais.

Em M29, seleciona-se venue journal (TOSEM, EMSE, ou TSE). Formata-se paper final (~15–20 pp journal format, mais espaço que conference). Submete-se paper via journal portal. Número de tracking é registrado.

Também em M29, redige-se capítulo de tese consolidando 24 meses de pesquisa. Capítulo inclui: (1) Methodology (DSR, 2 ciclos, 7 guidelines Hevner), (2) Artifact Design (IntentPlanner, ExplanationService, taxonomia), (3) Experiment Design (RQ1–RQ4a operacionalizadas), (4) Results (Ciclo I + II consolidated, meta-analysis), (5) Discussion (implications, limitations, future work). Capítulo é ~40–50 páginas, integrável em tese de doutorado de 150–200 páginas.

Ainda em M29, prepara-se replication package de qualidade conferindo: (1) git hashes de todos components (IntentPlanner, ExplanationService, LLM client, analysis code) e commits pinados, (2) ruleset de análise estática (versão exata SonarQube/Roslyn com número de versão), (3) versão de scorer (microsoft/codebert-base com model ID e sha256), (4) versão exata de modelo LLM (Llama-3.2-3B ou Phi-3.1, sha256 de arquivo de pesos), (5) todos prompts usados em arquivo YAML versionado com comentários, (6) amostra anotada de 10 outputs (anonymizados, com verdicts + explicações), (7) one-command script reexecutando subset de 5–10 issues para validar pipeline end-to-end, (8) datasets brutos de experimento (30–50 pares por RQ para Ciclo I e II) em CSV/JSON anonymizados com dicionário de variáveis. Tudo é arquivado em Zenodo (DOI atribuído) ou GitHub + OSF, linkado no paper.

Ao final de M29, entregam-se: Journal paper (camera-ready, ~15–20 pp, two-cycle findings, consolidated), paper submitted to journal (tracking number), tese capítulo final (~40–50 pp: Methodology + Results + Discussion + Future Work), replication package archived (DOI público, linkado no paper), repositório público com todos componentes tagged e versionados.

---

## Síntese de Milestones e Decisões Críticas

O cronograma de 24 meses contém **8 milestones críticos** onde decisões go/no-go são tomadas:

**M4 (fim Fase 1):** RQs operacionalizadas? Corpus validado? Preregistro congelado? Se sim, prossegue à Fase 2. Se não, estende Fase 1.

**M9 (fim Fase 2):** CI verde? κ ≥ 0.6 em pilot? Determinismo OK? Se sim, começa Coleta I. Se não, extend M9 refinements 2 semanas.

**M17 (Análise Preliminar I, Protocol Lockdown):** Sem anomalias fundamentais? Protocol pode congelar? Se sim, prossegue Análise Confirmativa I. Se não, adjustments + lock adiado.

**M20 (Escrita I, Submissão):** Paper completo? Formatado? Submetido? Se sim, começa Coleta II em paralelo. Se não, extend M20.

**M24 (Análise Preliminar II, Protocol Lockdown II):** Ciclo II confirma Ciclo I ou diverge sistematicamente? Protocol ok para Confirmativa II? Se sim, prossegue. Se não, investigar + ajustar.

**M26 (Análise Confirmativa II):** Meta-análise Ciclo I + II demonstra robustez? Se sim, prossegue Escrita II. Se não, documenta como limitation ou negative result.

**M29 (fim Ciclo II, Submissão Journal):** Paper journal completo? Replication package archived? Tese capítulo pronto? Se sim, projeto concluído (aguarda review). Se não, extend M29.

---

## Estrutura DSR Alinhada com Hevner et al.

Todo o cronograma de 24 meses com dois ciclos completos é fundamentado nos 7 guidelines de Hevner et al. (2004):

1. **Design as an Artifact** (Fase 2–3): Supervisor agent construído iterativamente, testado em dois ciclos de coleta
2. **Problem Relevance** (Fase 1): Problema de modernização legado validado com desenvolvedores e corpus público
3. **Design Evaluation** (Fases 2.5, 3.5, 4): Pilot validation, preliminary analysis, confirmative analysis, human validation κ, survey
4. **Research Contributions** (Fase 1 + 5): Gap Ledger explícito mapeando novelty claims a gaps reais
5. **Research Rigor** (Fase 4): Testes estatísticos não-paramétricos, preregistro congelado, multiple comparison correction, replicação Ciclo I + II
6. **Design as a Search Process** (Fases 2.5, 3.5): Iterações explícitas com feedback loops; refinements em cada ciclo antes de comprometimento
7. **Communication** (Fase 5): Conference paper (Ciclo I, M20) + Journal paper (Ciclo II, M29) + Tese capítulo (~50 pp)

Os **3 ciclos DSR** (Relevance M1–M4 → Design M5–M9 → Rigor M10–M29) com **2 ciclos completos de coleta-análise-escrita** garantem robustez científica, replicação interna, e publicabilidade em múltiplos venues (conference para Ciclo I, journal para Ciclo II com integração de ambos, tese para documentação completa).

---

## Versioning e Status

- **v1.0** (31 mai 2026): Cronograma 14 meses com feedback loops explícitos
- **v2.0** (31 mai 2026): Cronograma 24 meses com dois ciclos DSR completos

**Status:** ✅ Pronto para execução (condicionado a assinatura de orientador em M1, junho 2026).

**Próximo passo:** Assinar documento de cronograma com orientador; iniciar Fase 1 (junho 2026).

