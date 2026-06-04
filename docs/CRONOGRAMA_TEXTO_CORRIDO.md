# Cronograma de Execução da Pesquisa — Texto Corrido

**Supervisor Agent for LLM-Assisted Legacy Software Modernization**

**Duração Total:** 14 meses  
**Estrutura:** 3 ciclos de Design Science Research (DSR) com 2 iterações de feedback explícitas  
**Referência Metodológica:** Hevner et al. (2004); Wohlin et al. (2012); Basili et al. (1986)

---

## Ciclo 1: Relevância (Meses 1–3) — Fase 1

A pesquisa inicia-se com o Ciclo de Relevância, que estabelece toda a fundação científica do projeto durante os três primeiros meses. Nos primeiros trinta dias, o trabalho concentra-se em três frentes paralelas: finaliza-se a especificação de requisitos usando o método Volere, ajustando prioridades e congelando escopo; integra-se a revisão sistemática de literatura nos capítulos de Related Work, identificando trabalhos próximos como SWE-bench, SWE-agent, Plan4Code e OpenHands, e definindo com precisão o delta de novelty que a pesquisa almeja; e documenta-se como o projeto adere aos 7 guidelines de Hevner et al. para Design Science Research, mapeando os ciclos DSR aos objetivos das questões de pesquisa.

Até o final da segunda semana do mês 2, prossegue-se com validação rigorosa do escopo e falsificabilidade das RQs. Definem-se formalmente as hipóteses nulas para cada questão, especificam-se os baselines (zero-shot para RQ2–RQ4; design review para RQ1) e documentam-se critérios de sucesso. Simultaneamente, realiza-se mapeamento das características da ISO/IEC 25010 para os nós da taxonomia SWE, adicionando coluna `ISO25010Characteristic` aos arquivos CSV de taxonomia e garantindo rastreabilidade entre SOLID (SRP, OCP, DIP) e Maintainability/Modifiability.

Até meados do mês 2, seleciona-se o corpus empírico consistindo de 5 repositórios C# públicos no GitHub que representem mix entre software legado com débito técnico e sistemas ativamente mantidos, todos com licença permissiva e tracker de issues. Em paralelo, planeja-se as atividades com participação humana: desenvolve-se protocolo de anotação para que engenheiros sênior rotulem outputs com Cohen's κ ≥ 0,6; desenha-se instrumento de survey Likert sobre confiança, controle e usabilidade; toma-se decisão sobre aprovação ética/IRB.

No mês 3, conduzem-se entrevistas com desenvolvedores experientes para validar que o misalinhamento entre objetivos de qualidade e saídas de ferramentas de geração de código é um pain point prático real, confirmando que a pesquisa adere ao requisito de relevância do Design Science Research.

Ao final de M3, conclui-se o Ciclo de Relevância com entregáveis assinados pelo orientador: especificação Volere congelada, relatório SLR, taxonomia mapeada para ISO 25010, corpus de 5 repositórios justificados, e RQs operacionalizadas com hipóteses nulas, baselines e critérios de sucesso. Neste ponto ocorre o primeiro milestone crítico (M3: Qualification), onde toma-se decisão go/no-go para Fase 2. Prossegue-se se todos documentos estão assinados e nenhum risco crítico de R1–R5 permanece aberto.

---

## Ciclo 2a: Design — Endurecimento de Protótipo (Meses 4–5) — Fase 2

O Ciclo 2 de Design inicia-se com a Fase 2, que se propõe a resolver todos os gaps de implementação bloqueadores para experimentos reproduzíveis. Durante os meses 4 e 5, o foco concentra-se em criar uma baseline funcional, instrumentar a coleta de dados primários através de análise estática de violações SOLID, implementar rigorosos controles de determinismo no cliente LLM, e validar toda a harness experimental com um pilot de 10 issues.

No início de M4, adicionam-se os parâmetros `temperature=0` e `seed` ao cliente LLM, garantindo que sejam persistidos em logs de cada trial para auditoria. Na primeira semana de M4, executa-se um micro-estudo com 5–10 issues para medir qualquer variância residual apesar dos controles. Em paralelo, integra-se o motor de análise estática (SonarQube ou Roslyn), pinando uma versão específica de ruleset, e documenta-se cuidadosamente o mapeamento entre violações SOLID desejadas (SRP, OCP, DIP) e as regras concretas. Implementa-se captura de violações antes e depois de cada mudança de código gerada, armazenando-as em `TrialResult`. No final de M4, executa-se pilot manual validando 10 issues com 3+ engenheiros sênior, calculando Cohen's κ. Se κ ≥ 0,6, o protocolo está pronto; caso contrário, revisa-se e refaz-se o pilot.

Também em M4, implementa-se a condição de baseline (zero-shot) definindo `nfr_focus=[]` e `relationship_depth=0` no planejador, efetivamente desligando supervisão. Garantindo que baseline use exatamente o mesmo modelo, temperatura, seed e pipeline de avaliação que a condição supervisionada, diferindo apenas na supervisão. Conectam-se as funções `_run_supervised_trial` e `_run_baseline_trial` em `reproducibility_experiment.py`, capturando artefatos de trial completos para auditoria. Implementa-se captura de traces: para cada run, registra-se repositório testado, revisões específicas, aprovações do usuário, e todos prompts (externos e internos), armazenados em JSON versionado em `data/experiments/runs/`. Adiciona-se logging completo em todo pipeline.

Em M5, implementa-se o portão de testabilidade que registra status de build, status de testes unitários, contagem de testes adicionados e delta de cobertura. Este portão é pré-requisito interpretativo: outputs de mudanças que não constroem ou falham testes não podem ser interpretados como "melhor" até resolução. Documentam-se instruções de harness de testes por repositório. Coletam-se métricas de qualidade adicionais onde disponíveis: complexidade ciclomática, cobertura, duplication, conventions, segurança, cada uma com tool, versão e timestamp registrados.

No início de M4, escreve-se protocolo de paráfrase para RQ3 definindo 10 estilos semanticamente equivalentes. Até final de M5, implementa-se executor que gera automaticamente as 10 paráfrases. Ainda em M4, adicionam-se testes unitários para `IntentPlanner` e `ExplanationService`, usando mock do cliente LLM, verificando schema validity e determinismo. Remove-se ou implementa-se qualquer stub. Em M4, substitui-se o scorer de similaridade por `microsoft/codebert-base`, treinado especificamente em código. Ao final de M5, o CI deve estar verde com todos testes passando.

Ao final de Fase 2, entregam-se: todos high-priority gaps resolvidos, CI verde com unit tests, pilot RQ1 confirmando pipeline funciona, schema de execution trace com exemplos auditáveis, relatório κ-pilot mostrando κ ≥ 0,6, testability gate implementado, e relatório de determinismo. Todos os riscos R7–R15 devem estar fechados.

---

## Iteração I: Validação de Pilot (Final de M5 → Início de M6) — Fase 2.5

Antes de escalar para coleta de 50 pares por RQ, executa-se uma iteração crítica de feedback e validação que funciona como go/no-go gate. Na última semana de M5, executa-se um pilot de 10 issues que testa o pipeline inteiro. Para RQ1, tomam-se 5 issues e geram-se planos usando `IntentPlanner`, inspecionando se constraints de design (SRP, OCP, DIP) e padrões legados estão explicitamente documentados com entidades rastreáveis até a taxonomia, atingindo cobertura de pelo menos 80%. Para RQ2–RQ4, tomam-se outras 5 issues executando ambas condições (supervisionada e baseline), coletando delta SOLID via análise estática, e validando com 3+ engenheiros calculando Cohen's κ. Se κ < 0,6, o protocolo não está pronto e deve-se voltar para refinements.

Valida-se determinismo rodando a mesma issue 2x com temperature=0 e seed idêntica, verificando que outputs são idênticos ou que variância residual é muito pequena e documentada. Para RQ3, tomam-se 2–3 issues e geram-se 3 paráfrases de cada testando se variedade e semântica estão adequadas. Se paráfrases não parecerem semanticamente coerentes, refina-se protocolo.

No início de M6, convida-se orientador para reunião formal de Go/No-Go. Apresentam-se resultados do pilot. O critério GO exige que pelo menos 8/10 issues rodem sem erros críticos, κ ≥ 0,6 em 10 outputs com 3+ engenheiros, SOLID delta seja calculável em ≥8/10 issues, temperature=0 + seed produzam outputs deterministicamente idênticos ou variância seja pequena e documentada, e paráfrases pareçam semanticamente coerentes. O critério NO-GO ocorre se κ < 0,6 (protocolo não pronto), SOLID delta não calculável (SonarQube/Roslyn misconfigured), determinismo quebrado (variância residual alta), ou >3/10 issues com erros críticos. Se GO, procede-se à Fase 3 com confiança. Se NO-GO, retorna-se à Fase 2 e refinam-se gaps por 1–2 semanas adicionais. Entregam-se pilot report com 10 issues e resultados por RQ, decision memo assinado pelo orientador, e se NO-GO, documento de refinements com cronograma revisado.

---

## Ciclo 2b: Design — Coleta de Dados (Meses 6–8) — Fase 3

Após go/no-go positivo em M6, inicia-se a Fase 3: Coleta de Dados. Durante os meses 6, 7 e 8, o objetivo é executar todos os experimentos em escala completa, coletando 30–50 observações de pares (supervisado vs. baseline) para cada RQ. Para RQ1, executa-se o planejador em 3–5 sets de 10 issues cada (30–50 observações). Cada set mantém fixo o repositório, o modelo LLM e as condições de execução. Geram-se planos de ação usando `IntentPlanner` e inspeciona-se cada plano verificando se constraints de SRP/OCP/DIP estão explícitos com entidades rastreáveis, registrando cobertura por issue e por set, e armazenando em JSON versionado com provenance incluindo versão de ruleset, timestamp e scope.

Para RQ2, executa-se o experimento pareado com as mesmas 30–50 observações. Cada observação é uma issue testada em ambas condições, coletando delta SOLID via análise estática, registrando violação count antes e depois para ambas condições, e armazenando em JSON. Para RQ3, constrói-se corpus de paráfrases tomando 3–5 sets × 10 tasks (30–50 tasks ancoradas), gerando 10 paráfrases para cada task preservando repositório, issue e revision de código mas variando wording do prompt. Executam-se ambas condições em cada paráfrase, coletando verdict (accept/revise/reject) de cada run e armazenando em JSON com índice de paráfrase.

Para RQ4, filtra-se as issues que pertencem ao subset "legacy" identificado a priori durante seleção de corpus, executando o experimento pareado apenas nesse subset com 30–50 pares, coletando delta SOLID da mesma forma que RQ2 e armazenando em JSON. Para RQ4a (configuração), executa-se experimento adicional variando `strictness ∈ {low, medium, high}`, tomando os mesmos sets e issues mas agora executando em 3 níveis de severidade do supervisor. Para cada nível, registra-se distribuição de verdicts (counts de accept/revise/reject), delta SOLID, taxa de aceitação, e taxa de escalação, armazenando em JSON.

Em M8, valida-se integridade dos dados coletados verificando missing values, outliers e LLM failures, gerando relatório de qualidade de dados. Confirma-se que metadados de provenance estão completos com versão de ruleset pinada, timestamps, e model tag de cada run. Ao final de M8, entregam-se dados brutos de experimento (30–50 pares por RQ, 300–500 paráfrases para RQ3, 90–150 para RQ4a), todos em JSON versionado e anonymizados, relatório de qualidade de dados, e log de provenance.

---

## Iteração II: Análise Preliminar e Refinamento de Protocolo (M8 → M9) — Fase 3.5

Antes de entrar na fase confirmativa de análise estatística, executa-se uma **segunda iteração de feedback** para detectar anomalias nos dados e ajustar protocolo se necessário.

Na última semana de M8 e primeira semana de M9, procede-se ao data cleaning. Valida-se a integridade de todos os 30–50 pares por RQ: tem missing values? outliers inesperados? LLM failures? Verifica-se que provenance está íntegro: todas versões de ruleset são consistentes, model tags foram salvos, temperature=0 e seed foram aplicados em todos runs.

Realiza-se análise exploratória preliminar (não confirmativa). Para RQ1, revisa-se 10–15 plans: SRP/OCP/DIP coverage ainda é ≥80%, ou caiu? Se sim, qual é o pattern de falha? Para RQ2, calcula-se delta SOLID preliminar em 50 pares: a mediana de melhoria é ≥10 pontos percentuais, ou menor? A distribuição é normal ou skewed? Para RQ3, calcula-se consistency ratio preliminar em 10–20 paráfrases: qual é a média de supervisado vs. baseline? Um teste McNemar preliminar sugere gap positivo? Para RQ4, filtra-se subset legacy, calcula-se delta preliminar: delta > 0 em legacy, ou ≤ 0? Effect size é comparável a RQ2, ou menor?

No início/meio de M9, reúne-se com orientador. Apresenta-se preliminary results. Detectou-se algum problema fundamental? Exemplo 1: mediana RQ2 < 5 pp (effect muito fraco). Pode-se ajustar scope da RQ (redefinir o que conta como "sucesso") ou reconhecer limitação. Exemplo 2: κ-validation ainda pendente. Estende-se M10 para completar. Exemplo 3: distribuição muito skewed. Muda-se teste estatístico de Wilcoxon signed-rank para outro (Mann-Whitney U ou similar).

Se adjustments são necessários, documenta-se rational para cada mudança (preregistro é atualizado com "post-hoc adaptations" claramente marcadas). Qualquer mudança é assinada pelo orientador.

No meio de M9, toma-se a decisão de **Protocol Lockdown (hard deadline)**. Congela-se as hipóteses, baselines, DVs (dependent variables) e testes estatísticos. Anuncia-se: "Analysis code is now locked for confirmatory phase." Nenhuma outra mudança é permitida sem documentação e assinatura. O código de análise é tagged em versionamento.

Entregáveis de Fase 3.5: (1) data quality report (missing values, outliers, provenance log); (2) preliminary analysis report (coverage %, sample plans, mediana delta, effect size, p-value range preliminar); (3) protocol amendment memo (se applicable, com rational documentado e assinado); (4) analysis code locked e tagged.

---

## Ciclo 3: Rigor — Análise Confirmativa (Meses 9–11) — Fase 4

Com protocolo congelado em M9 meio, inicia-se a **Fase 4: Análise Confirmativa e Validação**. Durante os meses 9, 10 e 11, o objetivo é produzir evidência estatística para cada RQ, validada por humanos e survey.

Para RQ1, realiza-se formal design review. Contrasta-se cada plano gerado contra os critérios de sucesso congelados: planos expõem SRP/OCP/DIP explicitamente e com linked entities rastreáveis? Reporta-se coverage %. Deadline: M9 final.

Para RQ2, executa-se Wilcoxon signed-rank test. O teste é pareado: cada issue tem uma observação de delta_supervisado e uma observação de delta_baseline. A hipótese nula é que não há diferença. Calcula-se mediana de delta por set e pooled sobre 30–50 pares. Reporta-se p-value (two-tailed), effect size (r de Pearson), 95% confidence interval. Critério de sucesso (congelado): mediana ≥ 10 pp, p < 0,05. Deadline: M9 final.

Para RQ3, executa-se McNemar's test. Para cada paráfrase, a hypothesis é que verdicts (accept/revise/reject) concordam com maioria com frequência similar supervisionado vs. baseline. Calcula-se consistency ratio = (verdicts concordando com maioria) / 10 por task. Reporta-se McNemar p-value, gap de consistency, descriptive stats. Critério de sucesso: consistency ≥ 0,80 supervisionado, gap > 0 vs baseline, p < 0,05. Deadline: M10 início.

Para RQ4, executa-se Wilcoxon signed-rank no subset legacy. Dados: 30–50 pares de delta SOLID, legacy repos apenas. Reporta-se mediana, p-value, effect size (r), e compara-se effect size com RQ2. Critério de sucesso: mediana > 0, p < 0,05, effect size ≥ médio. Deadline: M10 meio.

Para RQ4a, executa-se ANOVA (se dados normais) ou Kruskal-Wallis (se não). Variável independente: strictness ∈ {low, medium, high}. Variáveis dependentes: verdict distribution (counts), SOLID delta, acceptance rate, escalation rate. Reporta-se test statistic, p-value, effect size (η² ou ε²), post-hoc comparisons (Tukey ou Dunn). Deadline: M10 final.

Aplica-se multiple comparison correction (Bonferroni ou Benjamini-Hochberg) across todos testes de RQ. Deadline: M10 final.

Em paralelo, executa-se human validation study (κ-based). Recruta-se ≥3 engenheiros sênior. Toma-se stratified sample de 20–30 outputs e pede-se que labelem: overall_verdict (accept/revise/reject), pattern adoption (Strangler Fig? Strangler, Branch By Abstraction, Anticorruption Layer?). Calcula-se Cohen's κ. Target: κ ≥ 0,6. Se cair abaixo, documenta-se ambiguity/edge cases. Deadline: M10 final.

Desenha-se instrumento de survey. Likert scale 5-point sobre 3 construtos: (1) Perceived trust in verdicts ("I trust the agent's judgments"), (2) Perceived control ("I can configure the agent to match my priorities"), (3) Usability ("The planning output was easy to understand"). Recruta-se N ≥ 20 developers. Stratifica-se por nível de experiência se possível. Toma-se decisão ética/IRB e documenta-se. Deadline para design: M10 início. Deadline para execution: M10 final. Executa-se survey, coleta-se respostas, analisa-se: descriptive stats (mean, SD por item), Cronbach's α (inter-item reliability), correlações entre os 3 construtos. Deadline para análise: M11 início.

Em M10, escreve-se a seção de Resultados integrando achados de RQ1–RQ4a em narrativa científica. Cria-se tabelas com p-values, effect sizes, CIs, κ scores, descriptive stats de survey com formatação apropriada. Deadline M10 final. Em M11 início, escreve-se a seção de Discussão preliminar discutindo achados vs. cada RQ, implicações práticas para refatoração assistida por LLM, implicações teóricas para design science de agents, limitações reconhecidas (validade interna, construto, externa, conclusão). Deadline M11 início.

Em M11 meio, escreve-se análise de Threats to Validity mapeando cada ameaça potencial a uma mitigação implementada: validade interna (temperature=0, seed, prompts cegados, provenance logging), validade de construto (painel κ de 3+ engenheiros, tools versionados, corpus diverso), validade externa (mix legacy+ativos, stratified sampling, N ≥ 30 pares), validade de conclusão (testes não-paramétricos robustos, preregistro, multiple comparison correction). Deadline M11 meio. Ao final de M11, entregam-se: relatório confirmative analysis (RQ1 design review findings %, RQ2 Wilcoxon mediana/p/r, RQ3 McNemar contagem/p, RQ4 Wilcoxon legacy, RQ4a ANOVA/Kruskal-Wallis com post-hoc, todos com Bonferroni correction aplicada), validação humana com κ scores (target ≥ 0,6 ou documented edge cases), survey data (N ≥ 20, mean/SD, Cronbach's α ≥ 0,7, correlações), rascunho de Discussão + Implications + Threats to Validity.

---

## Ciclo 3 (continuação): Escrita e Submissão (Meses 12–14) — Fase 5

O ciclo de Rigor conclui-se com a Fase 5, dedicada à comunicação científica e disseminação. Durante os últimos 3 meses, constrói-se e submete-se um paper de pesquisa de qualidade publicável e redige-se capítulo de tese integrando toda metodologia, resultados e discussão.

Em M12, inicia-se redação de Introduction situando o problema de modernização de legado assistida por LLM no contexto de refatoração, manutenção de software e agentes autônomos. Descreve-se a motivação prática: desenvolvedores precisam de suporte estruturado para identificar padrões legados e aplicar refatoração SOLID, mas ferramentas existentes carecem de supervisão sobre critérios de qualidade. Define-se explicitamente o research gap que o projeto pretende preencher, alinhado ao guideline DSR de "Problem Relevance".

Em M12, escreve-se seção de Related Work cobrindo SWE-bench (benchmark para code generation), SWE-agent (agente autônomo para tarefas de engenharia), Plan4Code (planejamento estruturado), OpenHands (framework de agentes), abordagens clássicas de refatoração, ISO 25010 (qualidade de software). Cria-se um parágrafo de "Gap Ledger" que lista explicitamente: (1) trabalhos mais próximos ao presente projeto, (2) o que cada um cobre bem, (3) o que cada um deixa aberto ou não endereça, (4) como cada contribuição do presente projeto (planejador supervisionado, juiz com explicações, empirismo em legacy, configurabilidade) se mapeia a um gap específico. Isso estabelece rastreabilidade 1-para-1 entre claims de novelty do paper e gaps reais identificados na literatura.

Em M12, escreve-se seção de Methodology (DSR). Mapeia-se os 7 guidelines de Hevner et al. (2004) ao presente projeto: Design as Artifact (planejador e juiz), Problem Relevance (entrevistas M1–M3), Design Evaluation (pilot M5→M6, preliminary M8→M9, confirmatory M9–M11), Research Contributions (gap ledger), Research Rigor (preregistro, testes não-paramétricos, multiple comparison correction), Design as Search Process (iterações explícitas), Communication (presente paper + tese). Descreve-se os 3 ciclos DSR (Relevance em M1–M3, Design em M4–M8, Rigor em M9–M11) e como cada um contribui à robustez científica.

Durante M12 e M13, escreve-se seção de Artifact Design descrevendo arquitetura do supervisor agent: Stage 1 (IntentPlanner) que toma issue de refatoração e taxonomia gerando plano SOLID estruturado com constraints e padrões legados documentados; Stage 2 (ExplanationService) que toma output LLM, scores de qualidade, análise estática e gera verdict (accept/revise/reject) com justificativa. Documenta-se estrutura da taxonomia (nodes, relationships, strictness levels), mapeamento entre ISO/IEC 25010 Maintainability characteristics (Modifiability, Modularity, Analyzability) e SOLID principles (SRP, OCP, DIP), exemplos de plans para issues reais.

Em M13, escreve-se seção de Experiment Design operacionalizando cada RQ: para RQ1, define-se hypothesis (H1: agent gera plans com SRP/OCP/DIP coverage ≥80%), DV (coverage %, entidades rastreáveis %), teste (design review com κ), procedure (ambos condições em 30–50 issues), corpus (5 repos). Para RQ2–RQ4, define-se hypothesis sobre delta SOLID > 0, DVs (mediana delta, effect size), testes (Wilcoxon signed-rank), procedure (pareado supervisado vs. baseline). Para RQ3, hypothesis sobre robustez, DV (consistency ratio), teste (McNemar). Para RQ4a, hypothesis sobre efeito de configuração, DV (delta por strictness), teste (Kruskal-Wallis com post-hoc).

Em M13, finaliza-se seção de Resultados (iniciada em M10) adicionando gráficos finais (boxplots de deltas SOLID por RQ, scatter de coverage vs. correctness, heatmap de verdict distribution por config), tabelas consolidadas com todos p-values, effect sizes, CIs, κ scores, survey descritivos formatados para venue escolhida.

Em M13, escreve-se seção de Threats to Validity detalhando cada ameaça potencial a conclusões e a mitigação implementada: ameaça 1 (Validade Interna: temperatura não-zero), mitigação: temperature=0 + seed pinned + logging completo; ameaça 2 (Validade de Construto: protocol ambíguo), mitigação: κ de 3+ engenheiros ≥ 0,6, tools versionados; ameaça 3 (Validade Externa: corpus pequeno), mitigação: 5 repos, mix legacy+ativos, stratified sampling; ameaça 4 (Validade de Conclusão: p-hacking), mitigação: preregistro, testes não-paramétricos, Bonferroni correction, protocol lockdown em M9.

Em M13, escreve-se Discussion + Implications sintetizando achados (RQ1: ≥80% coverage alcançado com κ ≥ 0,6? RQ2: effect > 0 com p < 0,05? RQ3: robustez confirma? RQ4: legacy se beneficia?), implicações práticas para ferramentas de refatoração assistida, implicações teóricas para design de agentes autônomos em engenharia de software, limitações reconhecidas.

Em M13, escreve-se Conclusion + Future Work: resumo dos achados, problemas abertos (e.g., escalabilidade a repositórios maiores, generalizabilidade a outras linguagens, outros NFRs além SOLID), extensibilidades do artefato (e.g., integração com IDEs, feedback loops com desenvolvedores em produção).

Em M13, conduz-se internal review formal com orientador. Apresenta-se draft completo, colhem-se feedbacks críticos, aplicam-se correções.

Em M13, seleciona-se venue alvo entre: ICSE (International Conference on Software Engineering, top-tier, ~25% acceptance), FSE (Foundations of Software Engineering, top-tier, ~20% acceptance), TOSEM (ACM Transactions on Software Engineering and Methodology, top-tier journal, mais tempo para revisão), EMSE (Empirical Software Engineering, journal, ~30% acceptance), ou ICSE Companion (track mais inovador com menos rigor estatístico mas visibilidade alta). Formata-se paper final de acordo com template LaTeX/Word do venue escolhido, checando limites de páginas, referências, figuras.

Em M14, submete-se paper via conference/journal portal, completando revisão final, envio de rebuttal se necessário durante review cycle.

Em M14, prepara-se replication package de qualidade conferindo: (1) git hashes de todos components (supervisor agent, baseline LLM client, analysis code) e relatório de reproducibility com commit SHAs pinados; (2) ruleset de análise estática pinado (versão exata de SonarQube/Roslyn rules usadas); (3) versão de scorer (microsoft/codebert-base) e seu modelo; (4) versão exata de modelo LLM (Llama-3.2-3B ou Phi-3.1, com sha256 de pesos); (5) todos prompts usados (internos e externos) em arquivo YAML versionado; (6) amostra anotada de 10 outputs (anonymizados, com verdicts e explicações); (7) one-command script de reexecução (Makefile ou run.sh) que reexecuta subset de 5 issues para validar pipeline; (8) datasets brutos de experimento (30–50 pares por RQ) em CSV/JSON anonymizados. Arquiva-se em GitHub (com DOI via Zenodo), OSF, ou Zenodo diretamente, linkando no paper.

Ao final de M14, entregam-se: (1) paper camera-ready (ICSE/FSE/TOSEM format, ~10–15 páginas, completo com abstract, intro, related, methodology, artifact, experiment design, results, discussion, threats, conclusion, references); (2) paper submitted e tracking number confirmado; (3) replication package archived com DOI público e linkado no paper; (4) capítulo de tese consolidando todo cronograma executado (Methodology + Results + Discussion + Future Work), integrado em tese de doutorado de 150–200 páginas.

---

## Síntese de Milestones e Decisões Críticas

O cronograma contém 7 milestones críticos onde decisões go/no-go são tomadas:

**M3 (fim Fase 1):** RQs operacionalizadas? Corpus definido? SLR integrado? Se sim, prossegue-se a M4. Se não, estende-se Fase 1.

**M5 (fim Fase 2):** CI verde? κ ≥ 0,6? Determinismo OK? Se sim, entra-se em Fase 2.5 (pilot). Se não, refinam-se gaps.

**M6 início (decisão Fase 2.5):** 8/10 issues do pilot rodaram OK? κ ≥ 0,6 mantido? Se sim, **GO** para Fase 3 escala completa. Se não, **NO-GO** retorna a Fase 2 refinements por 1–2 semanas.

**M8 final (fim Fase 3):** 30–50 pares por RQ coletados? Data quality OK? Se sim, prossegue a Fase 3.5.

**M9 meio (decisão Fase 3.5):** Preliminary analysis sem anomalias? Protocol pode ser congelado? Se sim, **lock protocol** e prossegue a Fase 4. Se não, adaptações documentadas, protocol ajustado, lock adiado para M9 final.

**M11 (fim Fase 4):** Análise confirmativa completa? κ ≥ 0,6? Survey N ≥ 20? Se sim, prossegue a Fase 5. Se não, estende-se M11.

**M14 (fim Fase 5):** Paper written, reviewed, submitted? Replication package archived? Se sim, projeto concluído.

---

## Estrutura DSR Alinhada com Hevner et al.

Todo o cronograma é fundamentado nos 7 guidelines de Hevner et al. (2004) para Design Science Research:

1. **Design as an Artifact** (Fase 2–3): Artefato supervisor agent construído iterativamente.
2. **Problem Relevance** (Fase 1): Entrevistas com desenvolvedores validam pain point prático.
3. **Design Evaluation** (Fase 2.5 + 3.5 + 4): Pilot validation, preliminary analysis, confirmatory analysis garantem rigor.
4. **Research Contributions** (Fase 1 + 5): Gap Ledger e novelty statement explicitados.
5. **Research Rigor** (Fase 4): Estatística não-paramétrica, preregistro, multiple comparison correction.
6. **Design as a Search Process** (Fase 2.5 + 3.5): Iterações de feedback e refinement.
7. **Communication** (Fase 5): Paper, replication package, tese.

Os 3 ciclos DSR (Relevance → Design → Rigor) estão distribuídos ao longo de 14 meses, com 2 feedback loops explícitos que garantem que anomalias são detectadas cedo (M5→M6, M8→M9) antes de comprometimento maior de recursos.

---

## Matriz de Riscos por Fase

Fase 1 (M1–M3) mitiga riscos R1–R6 (DSR framing, novelty gap, falsificabilidade, data privacy, ontologia, taxonomia incompleta).

Fase 2 (M4–M5) mitiga riscos R7–R15 (métrica SOLID, harness, determinismo, scorer, testes, stubs, input injection, testability gate).

Fase 2.5 (M5→M6) valida que R7–R15 foram realmente mitigados antes de scale.

Fase 3 (M6–M8) executa experimentos sob controles já estabelecidos.

Fase 3.5 (M8→M9) detecta anomalias de dados e ajusta protocolo se necessário antes de comprometimento de análise.

Fase 4 (M9–M11) executa análise confirmativa sob protocolo congelado.

Fase 5 (M12–M14) documenta e publica.

---

## Versioning

- **v1.0** (31 maio 2026): Cronograma consolidado baseado em `timeline.md`, `DESIGN_DE_PESQUISA.md`, `MATERIAIS_E_METODOS.md`, `risk-register.md`.
- **v1.1** (31 maio 2026): Adição de 2 iterações explícitas (Fase 2.5 + 3.5) com feedback loops e Go/No-Go gates alinhadas com DSR iterativo.

**Status:** ✅ Pronto para execução (condicionado a assinatura de orientador em M1).

**Próximo passo:** Assinar documento de cronograma com orientador e iniciar Fase 1.
