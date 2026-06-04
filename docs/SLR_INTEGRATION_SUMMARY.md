# Integração da Revisão Sistemática da Literatura (SLR)
## AI Techniques for Legacy Software

**Objetivo**: Síntese dos achados da SLR para integração na Fundamentação Teórica (Seção 2.6 - Trabalhos Relacionados) e outras seções da qualificação.

---

## 1. SÍNTESE EXECUTIVA DA SLR

A SLR "Artificial Intelligence Techniques for Legacy Software: A Systematic Literature Review" (Justo, Molleri, Martins, 2025) analisou 52 estudos primários publicados entre 2017 e 2024, investigando como técnicas de IA (especialmente LLMs e Generative AI) são aplicadas em problemas de modernização e manutenção de código legado.

**Achados principais**:
- **Técnicas predominantes**: Prompt Engineering (29 estudos), Fine-tuning (10 estudos), Deep Learning (9 estudos), Machine Learning tradicional (4 estudos)
- **Algoritmos mais usados**: 39/52 estudos usam Transformers; 5 usam ML tradicional (Random Forest, SVM, etc.)
- **Modelos de IA**: GPT-4, GPT-3, Codex, CodeT5, Llama, Claude mais frequentemente citados
- **Benefícios documentados**: Produtividade (+19 estudos), manutenibilidade (+16 estudos), modernização de legacy (+8 estudos)
- **Desafios principais**: Refinamento de prompts (15 estudos), limitações de treinamento (10 estudos), acurácia semântica/sintática (9 estudos)

---

## 2. MAPEAMENTO PARA SEÇÃO 2.6 (TRABALHOS RELACIONADOS)

### 2.1 Geração de Código com LLMs

**Contexto**: A geração automática de código assistida por IA é tema bem estabelecido na literatura com múltiplas abordagens.

**Achados da SLR**:
- Sistemas como Copilot, CodeT5 e Codex podem gerar código sintaticamente correto e funcionalmente viável
- **Validado em estudos sobre**: Código translation (C++ para Java/Python), refatoração automática, síntese de testes
- **Ferramentas citadas**: GitHub Copilot (9+ estudos), ChatGPT (12+ estudos), modelos de código especializados
- **Linguagens predominantes**: Java (25 estudos), Python (10 estudos), C (4 estudos)

**Lacuna identificada pela SLR**: 
> Embora ferramentas modernas de geração de código demonstrem capacidade técnica, *nenhum trabalho fornece supervisão explícita para atributos de qualidade estrutural (ISO 25010)* na geração automática. A validação é tipicamente funcional (testes passam), não estrutural (princípios SOLID respeitados).

**Relevância para sua pesquisa**: Sua abordagem com taxonomias de SOLID + supervisão MCP preenche essa lacuna.

---

### 2.2 Benchmarks de LLM4SE

**Contexto**: Múltiplos benchmarks foram desenvolvidos para avaliar desempenho de LLMs em tarefas de SE.

**Achados da SLR**:
- **Benchmarks identificados**: SWE-bench (Jimenez et al., 2024), HumanEval, CodeBLEU
- **Métrica típica**: Compilação bem-sucedida, taxa de passar testes, similaridade sintática
- **Limitação**: Benchmarks focam em correção funcional, não em qualidade estrutural ou aderência a princípios

**Lacuna identificada pela SLR**:
> Não avaliam *alinhamento com requisitos não-funcionais de qualidade estrutural*. ISO 25010 (manutenibilidade, testabilidade) não é operacionalizado como métrica de avaliação.

**Relevância para sua pesquisa**: Suas métricas de violação SOLID + ISO 25010 expandem avaliação além funcional.

---

### 2.3 Agentes para SE

**Contexto**: Agentes autônomos como SWE-agent, OpenHands, Devin podem executar tarefas complexas de engenharia.

**Achados da SLR**:
- **Capacidades**: Quebra de tarefas em subtarefas, validação com ferramentas, iteração baseada em feedback
- **Limitação**: Sem camada explícita de supervisão orientada para NFRs (requisitos não-funcionais)
- **Validação típica**: Sucesso da tarefa (problema resolvido?), não qualidade estrutural

**Lacuna identificada pela SLR**:
> Agentes não oferecem *configurabilidade para guiar geração hacia atributos específicos de qualidade estrutural*. Lógica de validação é implícita (passar testes) não explícita (seguir princípios).

**Relevância para sua pesquisa**: Seu agente supervisor com configuração via `swe_mcp_config.yaml` e taxonomias preenche essa brecha.

---

### 2.4 Engenharia de Prompts

**Contexto**: Técnicas avançadas de prompting (CoT, RAG, ReAct) melhoram desempenho de LLMs em tarefas complexas.

**Achados da SLR**:
- **Técnicas documentadas**:
  - Zero-shot (11 estudos): simples, menos efetivo para tarefas complexas
  - Few-shot (13 estudos): melhora significativa com exemplos
  - Chain-of-Thought (4 estudos): raciocínio explícito melhora precisão
  - Prompt Chaining (2 estudos): decomposição em subtarefas
  - RAG (4 estudos): contexto recuperado melhora especialização
  
- **Desafio principal**: Refinamento iterativo necessário; não há framework sistemático baseado em princípios de SE

**Lacuna identificada pela SLR**:
> Técnicas aplicadas *genericamente*, não *enraizadas em taxonomias de qualidade específicas de SE ou modelos estabelecidos (ISO 25010)*. Aplicações a refatoração carecem de estruturação baseada em princípios.

**Relevância para sua pesquisa**: Sua abordagem combina prompting (Few-shot + CoT) com taxonomias SOLID (princípios de SE estruturados).

---

### 2.5 Modernização de Legacy

**Contexto**: Literatura clássica descreve estratégias para renovar sistemas envelhecidos (Strangler Fig, refatoração incremental, etc.).

**Achados da SLR**:
- **Estratégias clássicas referenciadas**: Big Bang rewrite (raramente recomendado), incremental refactoring, service extraction, wrapping
- **Novidade**: 22/52 estudos abordam especificamente legacy; 13 usam AI tools para legacy
- **Benefícios documentados**: Tradução de COBOL para Java, refatoração de sistemas mainframe, manutenção de Fortran legado
- **Desafios**: Código verbose, acoplamento forte, falta de testes, documentação desatualizada

**Lacuna identificada pela SLR**:
> Literatura precedente (pré-2017) não considera *role de ferramentas de IA em acelerar modernização* nem *avalia qualidade de código gerado automaticamente em contextos legados*. Deixa aberta a questão de como supervisionar geração de código em tarefas complexas de modernização.

**Relevância para sua pesquisa**: Seu trabalho é um dos primeiros a operacionalizar supervisão de IA para modernização de legacy com foco em qualidade estrutural.

---

### 2.6 Modelos de Qualidade de Software

**Contexto**: Normas estabelecidas (ISO 25010, Boehm, McCall) fornecem frameworks para caracterizar e medir qualidade.

**Achados da SLR**:
- **Modelos mencionados**: ISO/IEC 25010:2023, Boehm et al. (1976), McCall et al. (1977)
- **Problema**: Esses modelos *não foram operacionalizados como restrições ou objetivos de supervisão de LLMs*
- **Típica avaliação**: Validação funcional via testes, não contra características ISO (manutenibilidade, confiabilidade, segurança)

**Lacuna identificada pela SLR**:
> *Modelos estabelecidos de qualidade não foram implementados como camada ativa de validação de código gerado por IA*, mapeando características ISO (manutenibilidade, confiabilidade, segurança) para regras de supervisão que guiem e validem refatoração assistida.

**Relevância para sua pesquisa**: Seu trabalho é um dos primeiros a implementar ISO 25010 como supervisão de geração de código via taxonomias mapeadas para características ISO.

---

## 3. BENEFÍCIOS DOCUMENTADOS (RQ3)

A SLR identificou benefícios em 4 áreas principais:

### 3.1 Produtividade (19 estudos)

- **Achado**: AI tools aumentam velocidade de desenvolvimento em ~2x para tarefas de código
- **Exemplos**: Code completion, automated refactoring suggestions, test generation
- **Mecanismo**: Reduz esforço manual em tarefas repetitivas; permite foco em lógica complexa

**Integração na sua pesquisa**: Você mede produtividade indiretamente via tempo de execução e qualidade do código gerado.

### 3.2 Manutenibilidade (16 estudos)

- **Achado**: Code generation pode melhorar legibilidade, testabilidade e estrutura
- **Contexto**: Quando supervisionado (Few-shot com exemplos, prompting estruturado)
- **Desafio**: Sem supervisão, código gerado é muitas vezes sintaticamente correto mas semanticamente questionável

**Integração na sua pesquisa**: Manutenibilidade é seu KPI primário via SOLID violations e ISO 25010.

### 3.3 Modernização de Legacy (8 estudos)

- **Achado**: LLMs facilitam tradução de código antigo para linguagens modernas (COBOL→Java, Fortran→Python)
- **Vantagens**: Reduz carga de conhecimento de linguagens antigas; acelera migração
- **Crítico**: Requer validação humana; contextualização com exemplos melhora qualidade

**Integração na sua pesquisa**: Seu RQ4 explicitamente avalia efetividade em corpus legacy.

### 3.4 Segurança (2 estudos) & Outros (12 estudos)

- **Segurança**: Alguns estudos mostram que LLMs podem gerar padrões de segurança, mas com limitações
- **Outros**: Documentação automática, sumário de código, extração de requisitos

---

## 4. DESAFIOS DOCUMENTADOS (RQ3)

A SLR identificou 7 categorias de desafios:

| Desafio | # Estudos | Descrição | Implicação para sua pesquisa |
|---------|-----------|-----------|------------------------------|
| **Refinamento de Prompts** | 15 | Prompts genéricos são imprecisos; refinamento iterativo é necessário | Seu Estágio 1 (planejamento baseado em taxonomia) reduz necessidade de refinamento manual |
| **Limitações de Treinamento** | 10 | Modelos não generalizam bem para domínios obscuros (legacy, baixo-nível) | Seu use de taxonomias + RAG fornece contexto especializado sem retreinamento |
| **Acurácia Semântica/Sintática** | 9 | Código compilável != semanticamente correto; violações sutis de lógica | Suas métricas SOLID capturam esses problemas semânticos |
| **Explainability** | 8 | Desenvolvedores querem entender *por quê* código foi gerado assim | Seu Estágio 2b (explicações estruturadas) fornece rastreabilidade |
| **Segurança** | 4 | Pode reproduzir ou amplificar viés de treinamento; backdoors via adversarial prompts | Seu design não resolve, mas registra completamente (rastreabilidade para auditoria) |
| **Integração com Ecossistema** | 4 | Tools não integrados com IDEs/CI/CD; separação de fluxos de trabalho | Seu MCP permite integração modular com ferramentas existentes |
| **Confiança** | 4 (não explícito) | Desenvolvedores hesitam em confiar em código gerado por IA | Sua supervisão explícita aumenta confiança via validação estruturada |

---

## 5. RECOMENDAÇÕES E CONDIÇÕES (RQ4)

A SLR identifica 3 recomendações principais para adoção de AI tools em legacy:

### 5.1 Supervisão Humana

**Recomendação**: Sempre ter human oversight; código gerado por LLM é não-determinístico e criativo.

**Implementação na SLR**:
- Estudos recomendam que humanos validem código de reparação automática
- Iteração pequena melhor que tentativas grandes
- Feedback contínuo melhora acurácia em execuções subsequentes

**Sua implementação**: Seu design prevê aprovação do usuário pós-geração (`user_approval` em logs).

### 5.2 Craft de Prompts com Contexto

**Recomendação**: Prompts precisam de contexto rico (linhas de código, exemplos correlacionados, documentação específica).

**Encontrado na SLR**:
- Few-shot com exemplos do repositório supera few-shot genérico
- Contexto de lado-effects importante para linguagens fortemente tipadas (C#)
- RAG efetivo para recuperar exemplos similares do repositório

**Sua implementação**: Seu Estágio 2a (`build_swe_code_context`) enriquece prompts com contexto taxonomizado + exemplos recuperados.

### 5.3 Integração com Desenvolvimento & Validação

**Recomendação**: AI tools devem estar integrados em CI/CD, testes, build pipelines—não como ferramentas separadas.

**Encontrado na SLR**:
- Automatizar validação (build, testes, análise estática)
- Escolher linguagens fortemente tipadas (melhor detecção de erros)
- Testability gate crítica (código deve compilar + passar testes existentes)

**Sua implementação**: Seu testability gate (Seção 4.6.4) e Roslyn/coverlet integration implementam validação rigorosa.

---

## 6. CONDIÇÕES PARA SUCESSO (RQ4)

A SLR identificou 3 condições críticas:

### 6.1 Validação & Comparação

**Condição**: Código gerado é imperfeito; precisa validação e comparação.

**Implementação recomendada**:
- Humanos experientes avaliam código em escala 1-5
- Comparação estatística entre condições
- Feedback loops para melhorar prompts

**Sua implementação**: Cohen's κ para acordo entre anotadores (Seção 4.7.2); comparação pareada supervisionado vs. baseline (Seção 4.7.3).

### 6.2 Preparação do Código

**Condição**: Código precisa estar "pronto para teste"—good documentation, unit tests existentes, impacto analysis.

**Implementação recomendada**:
- Testes automatizados executáveis
- Build sem erros
- Análise de impacto para escolher mudanças de baixo risco
- Iteração pequena

**Sua implementação**: Suas métricas incluem test coverage, build success, regressão detection (Seção 4.6.3-4).

### 6.3 Disponibilidade de Ambiente

**Condição**: Legacy software pode requerer configuração complexa; ambiente de execução crítico.

**Implementação recomendada**:
- Capacidade de executar código de verdade
- Dados suficientes para coverage tests
- Análise de invariantes para detectar padrões

**Sua implementação**: Seu corpus selection (Seção 4.4) inclui caracterização de ambiente; executabilidade como critério.

---

## 7. ESTUDOS ESPECÍFICOS RELEVANTES PARA SUA PESQUISA

### 7.1 Code Refactoring & SOLID

- **Wu et al. (2024)** - iSMELL: LLMs com toolsets especializados para code smell detection
  - **Relevância**: Detecção de violações de princípios usando LLMs + contexto
  - **Contraste com sua abordagem**: Eles usam LLM para detectar; você usa taxonomia para supervisionar geração

- **Bairi et al. (2024)** - CodePlan: Repository-level coding usando LLMs
  - **Relevância**: Planejamento estruturado antes de geração (similar ao seu Estágio 1)
  - **Convergência**: Ambos reconhecem que planos estruturados melhoram qualidade

### 7.2 Prompt Engineering para Code

- **Sasaki et al. (2024)** - Systematic Review of Prompt Engineering Patterns
  - **Achado chave**: Few-shot + Chain-of-Thought combinadas são mais efetivas
  - **Sua aplicação**: Você combina CoT + Few-shot + Taxonomia

- **Li et al. (2025)** - Structured Chain-of-Thought Prompting for Code Generation
  - **Achado**: CoT estruturado com pseudocódigo supera CoT natural
  - **Potencial relevância**: Poderia ser aplicado em seu Estágio 1 planning

### 7.3 Legacy Code Modernization

- **Pietrini et al. (2024)** - Transforming Fortran Legacies to Python with LLMs
  - **Achado**: LLMs podem traduzir, mas qualidade varia; contexto é crítico
  - **Sua vantagem**: Seu framework operacionaliza "contexto" via taxonomias

- **Gandhi et al. (2024)** - COBOL to Java Translation
  - **Achado**: Few-shot com exemplos do domínio melhora acurácia significativamente
  - **Convergência**: Alinha com sua estratégia de usar exemplos de repositório

### 7.4 Code Quality Assessment

- **Pinto et al. (2024)** - Developer Experiences with Contextualized AI Coding Assistant
  - **Achado**: Contextualização (arquitetura, style, domínio) crítica para aceitação
  - **Sua implementação**: Seu SweContext (Estágio 2a) fornece essa contextualização

---

## 8. COMO INTEGRAR NA SEÇÃO 2.6

Sugestão de estrutura:

```markdown
### 2.6.1 Geração de Código com LLMs

Trabalhos recentes como Copilot (Chen et al., 2021), CodeT5 (Wang et al., 2021)... 
[sua seção atual de texto]

Uma revisão sistemática recente (Justo, Molleri, Martins, 2025) analisou 52 estudos 
de 2017-2024 sobre aplicação de IA em modernização de legacy. Os achados confirmam 
que geração automática é viável, mas identifica lacuna crítica: **nenhum trabalho 
fornece supervisão explícita para atributos de qualidade estrutural (ISO 25010)** 
na geração. Validação é tipicamente funcional (testes passam), não estrutural 
(princípios SOLID respeitados).

### 2.6.2 Benchmarks de LLM4SE

...mesma estrutura...

### [etc para 2.6.3-2.6.6]
```

---

## 9. REFERÊNCIA PARA SEÇÃO DE REFERÊNCIAS

**Adicionar à seção REFERÊNCIAS**:

```
JUSTO, A. V.; MOLLERI, J. S.; MARTINS, L. E. G. **Artificial Intelligence Techniques 
for Legacy Software: A Systematic Literature Review**. In: *Proceedings of the 
[Venue], 2025. [Citação completa quando publicado]
```

Ou, se já publicado/disponível:

```
JUSTO, A. V.; MOLLERI, J. S.; MARTINS, L. E. G. **Artificial Intelligence Techniques 
for Legacy Software: A Systematic Literature Review**. IEEE Access, 2025. 
https://doi.org/[DOI]
```

---

## 10. CHECKLIST DE INTEGRAÇÃO

- [ ] Revisar seção 2.6 reescrita com resumo SLR
- [ ] Adicionar 1-2 frases sobre lacuna em cada subsessão (2.6.1-2.6.6)
- [ ] Verificar se RQ3 (benefícios) alinha com sua operacionalização
- [ ] Verificar se RQ3 (desafios) justifica seus controles metodológicos
- [ ] Adicionar referência SLR em REFERÊNCIAS
- [ ] (Opcional) Adicionar tabela-resumo de técnicas SLR → sua abordagem no Apêndice

---

## 11. NOTAS FINAIS

Esta síntese garante que:

✅ Você integra seus próprios achados da SLR de forma apropriada  
✅ Fundamentação Teórica fica com base empírica sólida  
✅ Lacunas identificadas justificam sua pesquisa  
✅ Recomendações SLR alinham com suas escolhas metodológicas  
✅ Sem reprodução de copyright—apenas síntese e paráfrase apropriadas  

**Próximo passo**: Revisar este documento e aplicar edições correspondentes na `FUNDAMENTACAO_TEORICA.md` seção 2.6.
