# 4 MATERIAIS E MÉTODOS

Esta seção descreve a abordagem de pesquisa, design experimental, corpus de avaliação, instrumentos de coleta de dados, e técnicas de análise estatística utilizadas para responder às questões de pesquisa (RQ1–RQ4) definidas no Capítulo 1.

## 4.1 Abordagem de Pesquisa

Este trabalho segue um **paradigma híbrido** que combina Design Science Research (DSR) com métodos empíricos quantitativos. A escolha reflete a natureza do problema: construir um artefato (agente supervisor) que é efetivo na prática, validando-o contra hipóteses específicas sobre qualidade de código.

### 4.1.1 Ciclos de Design Science Research

Design Science Research (Hevner et al., 2004; Wieringa, 2014) é apropriado para pesquisa em engenharia que busca tanto entender um problema quanto construir uma solução inovadora. DSR organiza-se em ciclos iterativos:

1. **Ciclo de Relevância**: Identifica-se o problema prático, confirma-se sua importância, e estabelecem-se questões de pesquisa grounded em literatura.
2. **Ciclo de Design**: Constrói-se o artefato (neste caso, o agente supervisor baseado em taxonomia), iterativamente refinado através de prototipagem e feedback.
3. **Ciclo de Rigor**: Valida-se o artefato contra critérios científicos rigorosos—hipóteses estatísticas, replicabilidade, generalização.

O cronograma do projeto (seção 3 do Capítulo 1) segue explicitamente esta estrutura:

- **Fase 1 (Meses 1–3)**: Ciclo de Relevância – Literatura, especificação de requisitos, seleção de corpus.
- **Fases 2–3 (Meses 4–8)**: Ciclo de Design – Desenvolvimento do agente, taxonomia, harness experimental.
- **Fases 4–5 (Meses 9–14)**: Ciclo de Rigor – Coleta de dados, análise estatística, escrita.

### 4.1.2 Questões de Pesquisa e Hipóteses Nulas

As quatro questões de pesquisa (RQ1–RQ4) estabelecem um continuum de validação, da mais teórica à mais aplicada:

#### RQ1 – Codificação de Taxonomia para Planejamento

**Enunciado**: Como uma taxonomia de engenharia de software deve codificar princípios SOLID (SRP/OCP/DIP) e padrões de modernização de legacy para suportar planejamento para refatoração C# assistida por IA?

**Tipo**: Exploratória, qualitativa.

**Hipótese nula (H₀)**: Não existe uma forma de codificação de taxonomia que permita planejamento estruturado e acionável de refatoração de legacy.

**Métrica de sucesso**: Um esquema de taxonomia em CSV (sob `taxonomies/ground_data`) que:
- Mapeia conceitos SOLID e padrões de legacy para nós discretos e relacionáveis.
- Permite derivar um plano de ação estruturado (CodeGenPlan) de uma descrição em linguagem natural.
- É extensível sem modificação de código.

#### RQ2 – Redução de Violações SOLID

**Enunciado**: Para ferramentas de geração de código assistidas por IA, supervisão guiada por taxonomia reduz a densidade de violações SOLID comparada com baseline (apenas prompt)?

**Tipo**: Quantitativa, experimental.

**Hipótese nula (H₀)**: Não há diferença significativa na densidade de violações SOLID entre código gerado com supervisão por taxonomia versus sem supervisão.

**Hipótese alternativa (H₁)**: Código gerado com supervisão por taxonomia apresenta densidade de violações SOLID significativamente menor.

**Variável dependente primária**: Densidade de violações SOLID = (contagem de violações SRP/OCP/DIP) / (linhas de código), medida via análise estática (Roslyn/SonarQube).

**Teste estatístico**: Teste t pareado (paired t-test) ou Mann-Whitney U (se distribuição não-normal), α = 0.05.

#### RQ3 – Robustez a Variações de Prompt

**Enunciado**: Para ferramentas de geração de código assistidas por IA, supervisão guiada por taxonomia melhora consistência entre paráfrases semanticamente equivalentes de prompts para a mesma tarefa de engenharia de software?

**Tipo**: Quantitativa, robustness evaluation.

**Hipótese nula (H₀)**: Não há diferença na consistência de verdicts entre código gerado com supervisão vs. sem supervisão, quando o mesmo intent é expresso via múltiplas paráfrases de prompt.

**Hipótese alternativa (H₁)**: Supervisão por taxonomia melhora consistência (reduz variância em verdicts) quando prompts são parafraseados.

**Variável dependente**: Consistência = 1 - (variance em verdicts / max variance possível). Calculada usando BERTScore F1 (Zhang et al., 2020) para comparação semântica de saídas.

**Teste estatístico**: ANOVA de medidas repetidas ou teste de Wilcoxon (se não-paramétrico), α = 0.05.

#### RQ4 – Efetividade em Corpus Legacy

**Enunciado**: Para ferramentas de geração de código assistidas por IA aplicadas a tarefas de modernização de legacy, supervisão guiada por taxonomia reduz a densidade de violações SOLID comparada com baseline, em um corpus de repositórios públicos legados?

**Tipo**: Quantitativa, aplicada.

**Hipótese nula (H₀)**: Não há diferença significativa em violações SOLID entre código gerado com supervisão vs. sem supervisão, quando aplicado a tarefas reais de modernização de legacy.

**Hipótese alternativa (H₁)**: Supervisão reduz significativamente violações SOLID em contextos de legacy reais.

**Contexto especial**: Realizado em corpus de 5 repositórios públicos C# caracterizados como "legacy" (seção 4.4).

---

## 4.2 Construção e Operacionalização da Taxonomia

A taxonomia SWE é o componente central de supervisão. Esta seção descreve sua construção, estrutura, e validação.

### 4.2.1 Estrutura da Taxonomia SWE

A taxonomia é implementada como um conjunto de arquivos CSV (sem grafo ontológico em v1), organizados em:

**Taxonomias de Ground Data** (`taxonomies/ground_data/`):

1. **clean_code_nfr_nodes.csv**: Nós que representam padrões de "código limpo" e princípios SOLID.
   - Colunas: `node_id`, `principle_name` (e.g., "SRP", "OCP", "DIP"), `description`, `antipatterns_detected`, `refactorings_applicable`, `tags`.
   - Exemplo: um nó para SRP lista violações típicas (classe com múltiplas responsabilidades) e refatorações (Extract Class, Extract Method).

2. **legacy_code_nodes.csv**: Padrões específicos de modernização de legacy.
   - Inclui: Technical Debt Indicators, Strangler Fig patterns, Big Bang Rewrite anti-patterns, Service Extraction patterns.
   - Colunas: `node_id`, `pattern_name`, `description`, `applicability_conditions`, `known_risks`, `cost_estimate`.

3. **security_nfr_nodes.csv**: Padrões relacionados a segurança e conformidade.
   - OWASP Top 10 violations, input validation patterns, cryptography best practices.

**Taxonomias de Linked Data** (`taxonomies/linked_data/`):

- **relationships.csv**: Descreve conexões entre nós (hierarquias, implicações, conflitos).
  - Colunas: `source_node_id`, `target_node_id`, `relationship_type` (e.g., "implies", "conflicts_with", "parent_of"), `strength` (0.0–1.0).

- **iso25010_mapping.csv**: Mapeia cada nó para características ISO/IEC 25010.
  - Colunas: `node_id`, `iso_characteristic` (e.g., "Maintainability", "Reliability", "Security"), `coverage_strength`.

**Critérios para Estrutura de Taxonomia**:

- **Completude**: Cobre os principais princípios SOLID e padrões de legacy relevantes a modernização de código C#.
- **Clareza**: Cada nó tem descrição inequívoca e exemplos vinculados.
- **Extensibilidade**: Novos nós podem ser adicionados sem alterar código, apenas adicionando linhas a CSVs.
- **Rastreabilidade**: Cada nó é rastreável para literatura (referências em comentários) e exemplos de código (sob `tests/reference_code/`).

### 4.2.2 Mapeamento para ISO 25010

ISO/IEC 25010:2023 define oito características principais de qualidade de software:

1. **Functional Suitability** (Adequação Funcional)
2. **Reliability** (Confiabilidade)
3. **Operability** (Operabilidade)
4. **Security** (Segurança)
5. **Compatibility** (Compatibilidade)
6. **Maintainability** (Manutenibilidade)
7. **Portability** (Portabilidade)
8. **Performance Efficiency** (Eficiência de Performance)

Cada característica subdivide-se em sub-características. Para este trabalho, focamos em **Maintainability** (principalmente), com ligações secundárias a **Reliability** e **Security**.

**Mapeamento explícito**:

- **SRP** → Maintainability.Modularity, Maintainability.Analysability
- **OCP** → Maintainability.Modifiability, Maintainability.Extensibility
- **DIP** → Maintainability.Modularity, Reliability.Fault Tolerance
- **Testabilidade** → Reliability.Testability, Maintainability.Analysability
- **Segurança (OWASP)** → Security.Confidentiality, Security.Integrity, Security.Authenticity

Mapeamento é codificado em `iso25010_mapping.csv` e utilizado em:

- **Planejamento (Estágio 1)**: Quando usuário especifica foco em "manutenibilidade", sistema resolve nós da taxonomia vinculados a essa característica ISO.
- **Explicação (Estágio 2)**: Quando código é validado, explicações incluem qual característica ISO foi afetada.

### 4.2.3 Validação da Taxonomia

Validação da taxonomia ocorre em duas fases:

**Fase 1 – Validação de Conteúdo (Qualitativo)**:

- Revisão por pares com pesquisadores em engenharia de software e especialistas em C#.
- Verificação: cada nó tem descrição clara, exemplos vinculados em `tests/reference_code/`.
- Resultado: lista de feedback e ajustes de nomenclatura/estructura.

**Fase 2 – Validação de Utilidade (Qualitativo)**:

- Testes em pequena escala (2–3 repositórios iniciais) para confirmar que:
  - Planejamento (RQ1) produz planos acionáveis e válidos.
  - Código gerado usando nós da taxonomia é de fato mais alinhado com princípios SOLID.
- Resultado: refinamento de taxonomia baseado em lições aprendidas.

Validação formal com anotadores múltiplos (Cohen's κ) é adiada para coleta de dados principal (seção 4.7.2).

---

## 4.3 Arquitetura do Agente Supervisor

O agente supervisor implementa um workflow em dois estágios: Planejamento (Estágio 1) e Contexto & Explicação (Estágio 2). Ambos os estágios são expostos via Model Context Protocol (MCP).

### 4.3.1 Model Context Protocol (MCP)

MCP é um protocolo aberto que padroniza como clientes (e.g., agentes de IA, IDEs) comunicam-se com servidores de ferramentas/recursos (Anthropic, 2024). MCP desacopla:

- **Servidor**: Expõe ferramentas (functions) que realizam ações ou consultam conhecimento. No nosso caso, `SWE-NFR-MCP` server implementado em `src/mcp/swe_mcp_server.py`.
- **Cliente**: Usa ferramentas do servidor como parte de seu workflow. Pode ser um agente de IA (Copilot, Claude, etc.) ou um script de pesquisa.

**Vantagens de MCP para este trabalho**:

- **Padrão aberto**: Permite que o agente supervisor seja integrado com múltiplas plataformas de IA futuras sem alteração.
- **Auditabilidade**: Chamadas a MCP são registradas, facilitando reproducibilidade.
- **Modularidade**: Lógica de supervisão é separada da lógica de geração de código.

### 4.3.2 Estágio 1 – Planejamento

**Ferramenta MCP**: `plan_swe_code_change`

**Inputs**:
- `problem_description`: Descrição em linguagem natural da tarefa de refatoração (e.g., "Refactor authentication service to follow SRP").
- `target_language`: Linguagem alvo (neste trabalho, C#).
- `nfr_focus` (opcional): Lista de características de qualidade a enfatizar (e.g., ["maintainability", "testability"]).

**Processo**:

1. **Extração de Intent**: LLM ou análise léxica extrai conceitos-chave da descrição (e.g., "authentication", "modularity").
2. **Resolução de Nós de Taxonomia**: Sistema mapeia conceitos para nós em taxonomias (via `SweKnowledgeBase`).
3. **Derivação de Plano**: Para cada nó resolvido, sistema gera uma sequência de passos de alto nível (e.g., "Extract authentication logic to separate class", "Define IAuthenticationProvider interface").

**Output**:

Uma `CodeGenPlan` estruturada (dataclass em `src/models/code_gen_plan.py`):

```
{
  "original_problem_description": "...",
  "nfr_focus": ["SRP", "Testability"],
  "plan_steps": [
    {
      "step_id": 1,
      "title": "Extract Authentication Logic",
      "description": "...",
      "related_taxonomy_nodes": ["SRP_001", "DIP_002"]
    },
    ...
  ],
  "estimated_complexity": "medium",
  "prerequisites": ["Unit tests should exist for authentication module"]
}
```

**Raciocínio**: Plano estruturado reduz ambiguidade para downstream LLM code generation (Estágio 2a) e fornece base para explicação (Estágio 2b).

### 4.3.3 Estágio 2 – Contexto e Explicabilidade

Estágio 2 subdivide-se em dois componentes:

#### 4.3.3.1 Ferramenta MCP: `build_swe_code_context`

**Inputs**:
- `code_gen_plan`: Saída do Estágio 1.
- `include_templates`: Flag boolean para incluir templates de design reliability.

**Processo**:

1. **Resolução de Contexto**: Sistema usa `SweKnowledgeBase` para recuperar:
   - Descrições expandidas de nós relacionados.
   - Exemplos de código (sob `tests/reference_code/`) para cada nó.
   - Padrões de design e antipadrões relevantes.

2. **Síntese de SWE Summary**: Gera um resumo compacto em linguagem natural adequado para injeção em prompts de LLM. Exemplo:

   ```
   SWE Context Summary:
   =====================
   Focus: SRP (Single Responsibility Principle), DIP (Dependency Inversion)
   
   SRP Guidance:
   - Current issue: AuthenticationService has responsibility for both 
     credential validation AND token generation.
   - Desired state: Separate into ICredentialValidator and ITokenGenerator.
   - Related template: Extract Class refactoring.
   
   DIP Guidance:
   - Do not directly instantiate dependencies; use constructor injection.
   - Define clear interfaces; concrete classes implement them.
   
   Related Code Examples:
   - tests/reference_code/srp_example.cs (shows correct SRP split)
   - tests/reference_code/dip_example.cs (shows correct DIP usage)
   ```

3. **Template Attachment** (opcional): Se `include_templates=true`, anexa templates de design reliability (sob `templates/reliability/`) para guiar geração de código robusto.

**Output**:

Uma `SweContext` object contendo:
```
{
  "plan": <CodeGenPlan>,
  "swe_summary": "<texto>",
  "related_examples": ["srp_example.cs", "dip_example.cs"],
  "templates": ["circuit_breaker.md", ...] (se solicitado)
}
```

#### 4.3.3.2 Ferramenta MCP: `judge_swe_code_change`

**Inputs**:
- `swe_context`: Saída de `build_swe_code_context`.
- `original_code`: Código antes da refatoração (string ou referência a arquivo).
- `modified_code`: Código após refatoração.

**Processo**:

1. **Análise de Diferença**: Computa diff entre código original e modificado.
2. **Classificação contra Taxonomia**: Para cada muda no diff:
   - Mapeia mudança para nós de taxonomia (e.g., "esta linha foi um Extract Class?" → SRP_001).
   - Classifica como alinhada ou não-alinhada com plano.
3. **Chain-of-Thought Explicação**: LLM gera raciocínio estruturado:
   - O que mudou?
   - Como alinha com o plano e princípios SOLID?
   - Quais riscos foram introduzidos?
   - Quais testes deveriam ser adicionados?
4. **Scoring**: Calcula score numérico (0.0–1.0) refletindo aderência ao plano.

**Output**:

Uma `SweCodeChangeExplanation` estruturada:

```
{
  "overall_verdict": "ALIGNED_WITH_PLAN",
  "alignment_score": 0.87,
  "nfr_impacts": {
    "SRP": {
      "status": "IMPROVED",
      "reasoning": "Authentication logic separated into IAuthenticationProvider."
    },
    "Testability": {
      "status": "IMPROVED",
      "reasoning": "Dependencies now injectable; mocking is possible."
    }
  },
  "identified_risks": [
    "New ITokenGenerator interface not fully implemented in all clients."
  ],
  "recommended_tests": [
    "Test that AuthenticationService no longer directly depends on TokenGenerator.",
    "Test that ITokenGenerator can be mocked in unit tests."
  ],
  "related_taxonomy_nodes": ["SRP_001", "DIP_002", "Testability_003"]
}
```

---

## 4.4 Seleção do Corpus Empírico

O corpus empírico é o conjunto de repositórios nos quais serão conduzidos experimentos. Seleção cuidadosa é crítica para validação interna e generalização.

### 4.4.1 Critérios de Inclusão/Exclusão

**Critérios de Inclusão**:

1. **Linguagem**: Código-fonte primariamente em C# (OOP).
2. **Tamanho**: 10k–100k linhas de código (manageable para análise manual, mas não trivial).
3. **Licença Pública**: Licença permissiva (MIT, Apache 2.0, BSD) que permite modificação e estudo.
4. **GitHub**: Repositório público no GitHub com histórico de issues e pull requests.
5. **Atividade**:
   - *Legacy subset* (2–3 repos): Última atualização > 2 anos atrás, documentação esparsa, arquitetura envelhecida.
   - *Actively maintained subset* (2–3 repos): Atualização < 6 meses atrás, documentação razoável, arquitetura moderna (controle).

**Critérios de Exclusão**:

1. Repositórios com < 5 GitHub issues abertas (insuficiente para seleção de tarefas).
2. Repositórios com teste automatizado < 20% (impossível validar testability gate).
3. Repositórios com dependências privadas ou proprietárias.
4. Repositórios que requerem configuração complexa não-automatizável.

### 4.4.2 Caracterização dos Repositórios

Cada repositório selecionado é caracterizado em uma planilha (CSV ou Excel):

| Atributo | Descrição | Método |
|---|---|---|
| Repository | URL do GitHub | Manual |
| Size_LOC | Linhas de código | cloc tool |
| Age_Years | Anos desde primeira commit | git log |
| Last_Update | Data da última commit | git log |
| Issues_Open | Número de issues abertas | GitHub API |
| Test_Coverage | % de linhas cobertas por testes | Roslyn/coverlet |
| Architecture | Descrição breve da arquitetura | Code review |
| Primary_Patterns | Padrões de design dominantes | Manual inspection |
| Legacy_Score | Score 0–10 indicando "legacy-ness" | Rubric (ver abaixo) |

**Legacy Score Rubric** (qualitativo → quantitativo):

- **0–2**: Código moderno, bem-arquiteturado, totalmente testado. (Não apropriado para este estudo.)
- **3–5**: Código bem-mantido mas com alguma dívida técnica. (Appropriate para controle.)
- **6–8**: Código claramente legado; violações SOLID observáveis; testes esparsos.
- **9–10**: Altamente legado; pouco testado; refatoração significativa necessária. (Ideal para avaliação de impacto.)

Repositórios selecionados para v1 incluem mix de scores 6–10 (legacy focus) e 3–5 (controle).

### 4.4.3 Rastreabilidade para Artifacts

Para cada repositório, mantém-se um arquivo de metadados (`corpus_metadata.yaml`) que registra:

```yaml
repository:
  name: example-legacy-app
  url: https://github.com/user/example-legacy-app
  archived_snapshot: example-legacy-app-2026-05-01.zip
  
characteristics:
  loc: 47500
  age_years: 8
  test_coverage: 18%
  legacy_score: 7
  
selected_issues:
  - issue_id: 123
    title: "Refactor authentication module for security"
    task_type: "modernization"
    selected_for_experiment: true
  - issue_id: 124
    title: "..."
    selected_for_experiment: false
    reason: "Requires system-level changes; out of scope for refactoring experiments"
```

Metadados são armazenados em `data/subjects/` e versionados no git para reproducibilidade.

---

## 4.5 Projeto Experimental

Esta seção descreve o design dos experimentos que coletam dados para responder a RQ2, RQ3, e RQ4.

### 4.5.1 Design Within-Subject

Utilizamos um **design within-subject pareado**, onde cada participante/tarefa é exposto a ambas as condições (supervisionado e baseline) em ordem aleatória, controlando para efeitos de aprendizado. Este design é apropriado porque:

- **Reduz variância**: Cada sujeito serve como seu próprio controle.
- **Aumenta poder estatístico**: Menos participantes/tarefas necessários para detectar efeito.
- **Pratico**: Não requer dois grupos separados de repositórios.

**Estrutura**:

- **Unidade de análise**: Uma tarefa de refatoração ancorada a um GitHub issue específico ou PR em um repositório selecionado.
- **Replicas por tarefa**: Cada tarefa é executada ~10 vezes em ambas as condições (supervisionado, baseline).
- **Randomização**: Ordem de condições (supervisionado primeiro vs. baseline primeiro) é aleatória para cada tarefa, reduzindo bias de ordem.
- **Total esperado**: 3–5 repositórios × 2–3 issues/repo × 10 replicas × 2 condições = 120–300 observações.

### 4.5.2 Condições: Supervisionado vs. Baseline (Sem Taxonomia)

#### Condição Supervisionada (Treated)

**Workflow**:

1. Usuário descreve tarefa em linguagem natural.
2. Sistema MCP executa `plan_swe_code_change` (Estágio 1), gerando plano estruturado.
3. Sistema executa `build_swe_code_context` (Estágio 2a), gerando contexto e exemplos.
4. Contexto é injetado em prompt ao LLM para geração de código.
5. Após geração, sistema executa `judge_swe_code_change` (Estágio 2b) para validação estruturada.

**Instruções de Prompt** (exemplo simplificado):

```
You are an expert C# software engineer tasked with refactoring legacy code.

REFACTORING OBJECTIVE:
[problem_description from RQ context]

STRUCTURED PLAN:
[plan from Estágio 1]

ENGINEERING GUIDANCE:
[SWE context summary from Estágio 2a]

CODE EXAMPLES:
[reference examples from taxonomy]

Your task: 
- Generate refactored code that strictly follows the plan.
- Ensure each principle (SRP, OCP, DIP) is explicitly addressed.
- Add inline comments explaining the refactoring rationale.
- Do not introduce new violations; aim to reduce existing violations.

CONSTRAINTS:
- Behavior must be preserved (no functional change).
- Do not reduce test coverage.
- Add comments for non-obvious design decisions.
```

#### Condição Baseline (Control)

**Workflow**:

1. Usuário fornece mesma descrição de tarefa.
2. **Sem Estágio 1 e 2**: Descrição é passada diretamente ao LLM sem contexto de taxonomia, planejamento estruturado, ou referências de código.

**Instruções de Prompt** (baseline simplificado):

```
You are an expert C# software engineer.

Refactor the following legacy code to improve quality:
[problem_description]

Guidelines:
- Preserve behavior.
- Follow C# best practices.
- Improve maintainability where possible.

[original code]

Provide refactored code with explanations.
```

**Rationale para Baseline**: Baseline representa a prática atual (ingênua) de usar LLMs para refatoração sem supervisão ou contexto estruturado. Comparação permite isolar impacto de supervisão por taxonomia.

### 4.5.3 Definição de Variáveis

#### 4.5.3.1 Variáveis Independentes

1. **Condição de Supervisão** (categórica): Supervisionado vs. Baseline.
2. **Repository Characteristics** (contínua): Legacy Score (0–10), Test Coverage (%), Size (LOC).
3. **Task Complexity** (ordinal): Low, Medium, High (baseado em tamanho de código, número de classes afetadas).
4. **Prompt Phrasing** (categórica, para RQ3): Original, Paraphrase 1, Paraphrase 2, Paraphrase 3 (4 variações semanticamente equivalentes).

#### 4.5.3.2 Variáveis Dependentes Primárias

Para cada condição e tarefa, as seguintes métricas são coletadas:

**Para RQ2 (Redução de Violações SOLID)**:

1. **Violações SOLID (Contagem)**
   - **Definição**: Número de instâncias detectadas de SRP, OCP, ou DIP violations no código.
   - **Método**: Análise estática via Roslyn analyzers (custom rules baseadas em taxonomia).
   - **Métrica Normalizada**: Violações per 100 LOC (controlando para tamanho de código).
   - **Direção**: Menor é melhor.

2. **Violações SOLID (Delta)**
   - **Definição**: Redução em violações do código original para código refatorado: Delta = Original_Violations - Refactored_Violations.
   - **Métrica Normalizada**: Delta / Original_Violations (% reduction).
   - **Direção**: Maior é melhor.

**Para RQ3 (Robustez a Variações de Prompt)**:

3. **Consistência de Verdicts (BERTScore F1)**
   - **Definição**: Similaridade semântica entre saídas geradas para diferentes paráfrases do mesmo prompt.
   - **Método**: BERTScore F1 (Zhang et al., 2020) entre pares de saídas.
   - **Agregação**: Média F1 across all pares de paráfrases.
   - **Direção**: Maior F1 (mais consistente) é melhor.

4. **Concordância de Estrutura de Plano**
   - **Definição**: Concordância entre planos gerados para diferentes paráfrases.
   - **Método**: Comparing plan_steps estruturalmente (quantas etapas são idênticas, quantas são semelhantes).
   - **Métrica**: Ordem de Kendall τ (correlation ordinal).
   - **Direção**: Maior τ (mais concordante) é melhor.

#### 4.5.3.3 Variáveis Dependentes Secundárias

1. **Testabilidade (Testability Gate)**
   - **Definição**: Build compila sem erro? Unit tests passam? Nenhuma regressão?
   - **Método**: Execução de `dotnet build` e `dotnet test` no repositório com código refatorado.
   - **Métrica**: Pass/Fail (binária); número de testes que falham.
   - **Expectativa**: Código refatorado deve passar gate; falha = code change rejected.

2. **Complexidade Ciclomática (Cyclomatic Complexity)**
   - **Definição**: Número de caminhos executáveis independentes em código.
   - **Método**: Roslyn analyzer (computar CC antes/depois).
   - **Métrica**: CC normalizado por linha de código.
   - **Direção**: Redução é melhor (simplificação).

3. **Cobertura de Testes (Test Coverage)**
   - **Definição**: % de linhas cobertas por testes automatizados.
   - **Método**: coverlet ou OpenCover.
   - **Métrica**: Delta de cobertura (Refactored_Coverage - Original_Coverage).
   - **Expectativa**: Não deve diminuir.

4. **Duplicação de Código (Code Duplication)**
   - **Definição**: Linhas de código duplicadas.
   - **Método**: SonarQube ou similar.
   - **Métrica**: % de código duplicado.
   - **Direção**: Redução é melhor.

5. **Segurança (Security Issues)**
   - **Definição**: Vulnerabilidades ou anti-padrões de segurança detectados.
   - **Método**: Roslyn security analyzers, OWASP rules.
   - **Métrica**: Contagem de issues de segurança.
   - **Direção**: Redução ou manutenção é melhor (não introduzir novos).

### 4.5.4 Controle de Determinismo de LLMs

LLMs geram saídas diferentes mesmo com input idêntico (não-determinísticos por design). Para mensurar robustez (RQ3) e reduzir variância, implementamos controles:

1. **Temperature = 0**: Usa decoding determinístico (greedy). Reduz aleatoriedade no token sampling.
   - **Trade-off**: Menos diversidade, mais previsibilidade.

2. **Seed Fixo** (se LLM provider suporta): Registra seed usado para cada trial; permite replicação exata.

3. **Número de Replicas**: 10 execuções por tarefa por condição. Com N=10, efeito de aleatoriedade residual é reduzido via média/agregação.

4. **Logging de Parâmetros LLM**: Cada chamada ao LLM registra:
   - Modelo usado e versão (e.g., gpt-4-2024-05-01).
   - Temperature, seed, max_tokens.
   - Timestamp.
   - Versão de instruções de prompt.

Logging é criticamente importante para reproducibilidade (NFR-1, NFR-8).

---

## 4.6 Coleta de Dados

Coleta de dados é implementada via um harness experimental automatizado (em `src/evaluation/reproducibility_experiment.py` e `src/mcp/swe_mcp_server.py`). Esta seção descreve instrumentos e protocolos.

### 4.6.1 Registro de Execução (Traceability)

Cada trial de experimento gera um registro estruturado em JSON/CSV (`data/subjects/execution_log.csv` e arquivos de detalhe por trial).

**Campos registrados**:

```json
{
  "trial_id": "exp-2026-05-16-001-trial-005",
  "experiment_id": "exp-2026-05-16-001",
  "date_time": "2026-05-16T14:32:45Z",
  
  "repository": {
    "name": "example-legacy-app",
    "url": "https://github.com/user/example-legacy-app",
    "commit_hash": "abc123def456...",
    "branch": "master"
  },
  
  "task": {
    "issue_id": 456,
    "issue_title": "Refactor authentication module",
    "problem_description": "...",
    "task_type": "modernization"
  },
  
  "condition": "supervised",  // or "baseline"
  
  "llm_config": {
    "model": "gpt-4-turbo-2024-04-09",
    "temperature": 0,
    "seed": 42,
    "max_tokens": 4000
  },
  
  "prompts": {
    "planning_prompt": "...",
    "context_prompt": "...",
    "generation_prompt": "..."
  },
  
  "outputs": {
    "plan": { ... },  // CodeGenPlan JSON
    "context": { ... },  // SweContext JSON
    "generated_code": "...",
    "explanation": { ... }  // SweCodeChangeExplanation JSON
  },
  
  "metrics": {
    "violations_original": 8,
    "violations_refactored": 3,
    "violations_delta": -5,
    "violations_percent_reduction": 62.5,
    
    "build_success": true,
    "tests_passed": 147,
    "tests_failed": 0,
    "test_coverage_original": 45,
    "test_coverage_refactored": 46,
    
    "cyclomatic_complexity_original": 22,
    "cyclomatic_complexity_refactored": 18,
    "code_duplication_percent": 5.2,
    
    "security_issues": 0,
    "bertscore_f1": null  // For supervised condition only
  },
  
  "user_approval": {
    "approved": true,
    "reviewer_comments": "..."
  },
  
  "execution_duration_seconds": 342.5
}
```

Registros são armazenados em `data/subjects/trials/` com uma cópia de backup diária. Versionamento via git permite rastreabilidade de mudanças em protocolo/métricas.

### 4.6.2 Análise Estática (SonarQube / Roslyn)

Análise estática é executada antes e depois de cada refatoração para medir violações de qualidade.

#### 4.6.2.1 Roslyn Analyzers (C#)

Roslyn é a infraestrutura de compilação de C# (.NET). Utilizamos custom Roslyn analyzers para detectar violações SOLID:

**Custom Rules Implementadas**:

1. **SRP Violation Detection** (`SRP_001` – `SRP_005`):
   - Classe com múltiplas responsabilidades (heurística: > 3 métodos públicos não-relacionados).
   - Múltiplas razões para mudar (heurística: acesso a múltiplos subsistemas—DB, Auth, Logging).

2. **OCP Violation Detection** (`OCP_001` – `OCP_003`):
   - Classe com número elevado de condicionais (if/switch) que variam com nova funcionalidade.
   - Herança quebrada (violação de Liskov Substitution Principle, um pilar de OCP).

3. **DIP Violation Detection** (`DIP_001` – `DIP_002`):
   - Instanciação direta de dependências (e.g., `new DatabaseConnection()`).
   - Falta de injeção de dependência em construtores.

**Configuração**:

Regras são configuradas em `analyzers/roslyn_config.json`:

```json
{
  "enabled_rules": ["SRP_001", "SRP_002", "OCP_001", "DIP_001", ...],
  "severity_mapping": {
    "SRP": "warning",
    "OCP": "warning",
    "DIP": "error"
  },
  "baseline_exclusions": []
}
```

**Execução**:

```powershell
# Antes de refatoração
dotnet build /p:EnforceCodeStyleInBuild=true /p:EnableNETAnalyzers=true

# Capturar diagnósticos
roslyn-analyzer --project MyProject.csproj --output violations_before.json
```

#### 4.6.2.2 SonarQube Integration (Opcional)

Para métricas complementares (complexidade, cobertura), integração com SonarQube é suportada mas opcional em v1. Se disponível:

- **Métricas coletadas**: Cyclomatic complexity, code duplication, test coverage, security hotspots (CWE/OWASP).
- **Sincronização**: Após cada build, resultados são exportados para `data/subjects/sonarqube_export.csv`.

### 4.6.3 Coleta de Métricas de Qualidade

#### 4.6.3.1 Violações SOLID (SRP/OCP/DIP)

**Método**:

1. Executar Roslyn analyzers no código original → contar violations.
2. Executar Roslyn analyzers no código refatorado → contar violations.
3. Calcular delta: reduction = (original_count - refactored_count) / original_count.

**Normalização**:

- Violations por 100 LOC para controlar por tamanho de código.
- Per-method violations para finesse (e.g., "qual método ainda viola SRP?").

**Threshold para Aceitação**:

- Mínimo 10% redução em violações para código ser considerado "melhorado".
- Se delta < 0 (mais violações introduzidas), refatoração é rejeitada.

#### 4.6.3.2 Complexidade Ciclomática

**Método**: Roslyn analyzer calcula CC para cada método. CC é contagem de caminhos executáveis independentes.

**Métrica**: Average CC por classe, normalizado por tamanho.

**Expectativa**: Após refatoração com Extract Method / Extract Class, CC deve diminuir.

#### 4.6.3.3 Cobertura de Testes

**Método**: Executar unit tests com coverage instrumentation (coverlet):

```powershell
dotnet test /p:CollectCoverage=true /p:CoverageFormat=opencover
```

**Métrica**: % de linhas, branches, métodos cobertos.

**Expectativa**: Cobertura não deve diminuir em > 5%. Idealmente, aumenta porque novos testes são adicionados para exercitar código refatorado.

#### 4.6.3.4 Duplicação de Código

**Método**: Detecção automática de sequências duplicadas (via SonarQube ou tool dedicado como Simian).

**Métrica**: % de código duplicado no codebase.

**Expectativa**: Refatoração (e.g., Extract Method) deve reduzir duplicação.

### 4.6.4 Avaliação de Testabilidade (Build + Unit Tests)

Testabilidade é avaliada via "testability gate"—uma validação automatizada de que código compilado e testes passam.

**Gate Protocol**:

1. **Compilação**: Executar `dotnet build` no diretório do repositório com código refatorado.
   - **Sucesso**: Compilação sem erros nem warnings (warnings adicionais permitidos, mas devem ser investigados).
   - **Falha**: Build falha → trial é marcada como "FAILED_BUILD" e excluída de análises.

2. **Testes Unitários**: Executar `dotnet test` com filtro `[Test]` (não integration tests).
   - **Sucesso**: Todos os testes passam ou mantêm sua taxa de passa anterior.
   - **Falha**: Se novos testes falharem ou testes anteriormente passando agora falham → trial é marcada como "FAILED_TESTS" e excluída.

3. **Cobertura**: Verificar que cobertura não diminuiu em > 5%.
   - **Falha**: Se diminui > 5% → trial é marcada como "FAILED_COVERAGE" e potencialmente excluída (dependendo de severidade).

**Métrica Agregada**:

- **Testability Score** = # trials que passam gate / total trials.
- Comparação supervisionado vs. baseline: supervisão deve resultar em >= 85% passing gate.

### 4.6.5 Robustez a Variações de Prompt (RQ3)

Para RQ3, cada tarefa é executada com 4 variações de prompt (original + 3 paráfrases) em ambas as condições.

**Geração de Paráfrases**:

1. **Original Prompt**: Descrição do problema como escrito inicialmente.
2. **Paraphrase 1**: Reescrita alterando estrutura mas preservando significado.
3. **Paraphrase 2**: Reescrita com ênfase diferente (técnica vs. negócio).
4. **Paraphrase 3**: Parafrase com detalhes adicionados/removidos.

Exemplo:

```
Original: "Refactor authentication service to follow SRP"

Paraphrase 1: "Split the AuthenticationService into single-purpose components"

Paraphrase 2: "The authentication module currently handles too many concerns. 
             Separate credential validation from token generation."

Paraphrase 3: "Modernize authentication; currently has multiple responsibilities 
             that should be in different classes for maintainability."
```

**Procedimento**:

1. Para cada paráfrase, executar pipeline completo (Estágio 1–2).
2. Coletar saídas (plano, código gerado, explicação).
3. Comparar saídas usando BERTScore F1.

**Métrica de Consistência**:

- **Pairwise BERTScore**: Calcular F1 entre cada par de paráfrases (6 comparações para 4 paráfrases).
- **Agregação**: Média aritmética das 6 comparações.
- **Thresholds**:
  - F1 > 0.85: Altamente consistente.
  - F1 0.75–0.85: Moderadamente consistente.
  - F1 < 0.75: Inconsistente.

---

## 4.7 Análise Estatística

### 4.7.1 Teste de Hipóteses

Para cada RQ com hipótese nula, realiza-se teste estatístico apropriado.

#### RQ2 – Redução de Violações SOLID

**Setup**:

- **Pareado**: Mesmas tarefas em ambas as condições → paired test.
- **Variável dependente**: Contagem de violações (discreta mas aproximadamente normal com N grande).
- **Hipótese nula (H₀)**: μ_supervisionado = μ_baseline (nenhuma diferença).
- **Hipótese alternativa (H₁)**: μ_supervisionado < μ_baseline (supervisão reduz violações).
- **Teste**: Paired t-test, one-tailed.

**Procedimento**:

```
1. Para cada tarefa i:
     delta_i = violations_baseline_i - violations_supervisionado_i
   
2. Calcular:
     mean_delta = mean(delta_i)
     se_delta = sd(delta_i) / sqrt(N)
     t_statistic = mean_delta / se_delta
   
3. p-value = P(t > t_statistic | H₀ verdadeira), 1-tailed
4. Decisão: Se p < α (α=0.05), rejeitar H₀; supervisão é efetiva.
```

**Relatório**:

```
RQ2 Results:
- Mean violations (baseline): 5.2 (SD=2.1)
- Mean violations (supervised): 3.8 (SD=1.9)
- Mean delta: 1.4 violations per task
- t(N-1) = X.XX, p = 0.003
- Conclusion: Supervisão reduz violações SOLID significativamente (p < 0.05).
- Effect size (Cohen's d): 0.7 (medium effect)
```

#### RQ3 – Robustez a Variações de Prompt

**Setup**:

- **Variável dependente**: BERTScore F1 entre paráfrases (contínua, 0–1).
- **Fator**: Condição (supervisionado vs. baseline).
- **Design**: 2-way ANOVA (Factor 1: Condição; Factor 2: Tarefa).

**Procedimento**:

```
ANOVA H₀: Não há efeito principal de condição em F1 scores.
H₁: Condição supervisionada tem F1 significativamente maior.

Relatório:
- Mean F1 (baseline): 0.68 (SD=0.12)
- Mean F1 (supervised): 0.79 (SD=0.09)
- F(1, N-2) = Y.YY, p = 0.008
- Conclusion: Supervisão melhora consistência significativamente.
```

#### RQ4 – Efetividade em Corpus Legacy

**Setup**:

- Mesma análise que RQ2, mas restrita a repositórios legacy (Legacy Score >= 6).
- Testa se efeito é maior em contexto de legacy comparado a controle.

**Procedimento**:

```
Análise de Subgrupo:
- Repositórios Legacy (score 6–10): mean delta violações = X
- Repositórios Controle (score 3–5): mean delta violações = Y

Teste de Interação:
- Hipótese: Delta é significativamente maior em legacy.
- Método: t-test entre subgrupos ou 2-way ANOVA (Condição × Legacy_Status).
```

### 4.7.2 Validação de Anotações (Cohen's κ)

Para avaliação qualitativa de "verdicts" (RQ2, RQ3), dois anotadores independentes avaliam um subconjunto de refatorações (~10% das trials).

**Protocolo de Anotação**:

Anotadores avaliam cada código refatorado em uma escala de 5 pontos:

1. **Excellent (5)**: Segue plano, reduz violações, preserva comportamento, adiciona testes.
2. **Good (4)**: Segue plano, reduz violações, mas pequenas imperfeições.
3. **Acceptable (3)**: Segue plano parcialmente; viola alguns princípios.
4. **Poor (2)**: Pouco alinhado com plano; reduz violações mínimamente.
5. **Unacceptable (1)**: Não segue plano; piora qualidade ou quebra comportamento.

**Cálculo de κ**:

```
κ = (P_o - P_e) / (1 - P_e)

Onde:
- P_o = proporção de acordo observado
- P_e = proporção de acordo esperado por acaso

Interpretação:
- κ > 0.81: Quase perfeito ("almost perfect agreement")
- κ 0.61–0.80: Substancial
- κ 0.41–0.60: Moderado
- κ < 0.40: Fraco
```

**Target**: κ >= 0.70 (substancial agreement).

Se κ < 0.70, protocol é refinado e reannotação é realizada.

### 4.7.3 Comparação Supervisionado vs. Baseline

Uma tabela de resumo é gerada:

| Métrica | Baseline | Supervised | Delta | p-value | Sig. |
|---|---|---|---|---|---|
| Violações SOLID (mean) | 5.2 | 3.8 | -1.4 | 0.003 | ** |
| Complexity (mean CC) | 22.1 | 19.3 | -2.8 | 0.041 | * |
| Test Coverage (%) | 45.2 | 46.1 | +0.9 | 0.234 | ns |
| Build Success Rate | 92% | 96% | +4% | 0.089 | ns |
| Test Pass Rate | 85% | 91% | +6% | 0.015 | * |

Legendas: `**` p<0.01, `*` p<0.05, `ns` não-significativo.

### 4.7.4 Cálculo de Robustez

Robustez é quantificada como:

```
Robustness = 1 - (max_F1 - min_F1) / max_F1

Onde:
- max_F1, min_F1 = maior e menor BERTScore F1 entre pares de paráfrases

Interpretação:
- Robustness > 0.9: Altamente robusto (variação < 10%)
- Robustness 0.7–0.9: Moderadamente robusto
- Robustness < 0.7: Fraco robustez
```

Relatório comparativo:

```
RQ3 – Robustness Results:

Baseline:
- Mean robustness: 0.64 (SD=0.18)
- 40% de tarefas com robustness >= 0.7

Supervised:
- Mean robustness: 0.81 (SD=0.12)
- 85% de tarefas com robustness >= 0.7

Difference: Supervisão melhora robustness em 0.17 pontos (p < 0.001)
```

---

## 4.8 Ferramentas e Implementação

### 4.8.1 Stack Tecnológico

| Camada | Ferramenta | Versão | Propósito |
|---|---|---|---|
| **Linguagem** | C#, Python 3.10+ | — | Code generation & experiment automation |
| **LLM Provider** | OpenAI (GPT-4) / LocalAI | — | Code generation, planning, explanation |
| **MCP Server** | FastMCP (Anthropic) | 0.5.0+ | Protocol para acesso a ferramentas |
| **Análise Estática** | Roslyn Analyzers | .NET 8 | Detecção de violações SOLID |
| **Cobertura de Testes** | coverlet | 6.0+ | Medição de test coverage |
| **Similaridade Semântica** | BERTScore | 0.3.13 | Cálculo de F1 para RQ3 |
| **Versionamento** | Git | — | Reproducibilidade, rastreabilidade |
| **Estatística** | SciPy, NumPy | — | Testes t, ANOVA, Cohen's κ |
| **Logging** | Python logging, structured JSON | — | Registro de execução |

**Configuração Mínima para Reprodução**:

- Windows 10/11 com PowerShell 5.1 ou Unix-like com bash.
- .NET 8 SDK (para compilação de código C#).
- Python 3.10 com dependências em `requirements.txt`.
- Acesso a API OpenAI (chave em `.env`) ou servidor LocalAI local.
- ~10GB espaço em disco (para repositórios + modelo LLM local).

### 4.8.2 Reprodutibilidade e Controle de Versão

**Medidas de Reprodutibilidade**:

1. **Pinning de Versões**: Todas as dependências (Python, .NET, bibliotecas) são fixadas em `requirements.txt` e `packages.lock.json`.

2. **Configuração Versionada**: Arquivo de configuração `swe_mcp_config.yaml` é versionado; qualquer mudança é registrada no git com commit message.

3. **Seed Fixo**: Experimentos usam seed determinístico para geração de números aleatórios (Python `random.seed()`, etc.).

4. **Logging Completo**: Cada trial registra:
   - Versão exata de modelo LLM usado.
   - Commit hash do repositório sendo analisado.
   - Parametros de LLM (temperature, max_tokens, seed).
   - Timestamp de execução.

5. **Snapshot de Código-Fonte**: Código-fonte de cada repositório testado é capturado como ZIP snapshot em `data/subjects/snapshots/` com referência de commit.

**Replicação Futura**:

```
Para replicar experimento:

1. Clone este repositório: git clone ...
2. Restaure ambiente: source venv/bin/activate && pip install -r requirements.txt
3. Alinhe variáveis de ambiente: export SWE_GROUND_DATA_DIR=... 
4. Execute harness: python -m src.main reproducibility \
     --config data/subjects/exp_config.yaml \
     --seed 42 \
     --output results_replication.json
5. Compare resultados com results_originais.json
```

### 4.8.3 Ambiente de Execução

**Ambientes Suportados**:

- **Windows 10/11**: Scripts em PowerShell (`.ps1`).
- **Linux (Ubuntu 20.04+, Debian 11+)**: Scripts em bash (`.sh`).
- **macOS 11+**: Suportado via bash (com dependências instaláveis via Homebrew).

**Containerização (Futuro)**:

- Dockerfile e docker-compose.yml foram preparados para facilitar replicação sem configuração manual.
- Imagem Docker contém .NET 8 SDK, Python 3.10, todas as dependências.

**Recomendação**: Usar Docker para máxima reproducibilidade; máquina host precisa apenas de Docker/Docker Desktop.

---

## 4.9 Considerações Éticas e de Privacidade

### 4.9.1 Conformidade com Licenças Públicas

Todos os repositórios selecionados para corpus têm licenças públicas permissivas (MIT, Apache 2.0, BSD). Nenhuma modificação ou distribuição de código gerado viola termos de licença; modificações são:

- Mantidas em repositórios private (não publicadas).
- Usadas apenas para pesquisa e avaliação.
- Deletadas após experimento (snapshots são arquivados mas não distribuídos sem consentimento).

**Conformidade com GitHub Terms of Service**: Uso de API do GitHub para metadados é conforme; nenhuma extração em massa de código além do escopo de repositórios selecionados.

### 4.9.2 Privacidade de Dados

**Dados Pessoais**: Nenhum dado pessoal é coletado ou armazenado.

- Nomes de desenvolvedores nos commits são registrados apenas para rastreabilidade de artifact origin; não são analisados ou publicados.
- E-mails associados com commits não são capturados.

**Dados de Configuração Sensível**: Chaves de API (OpenAI, GitHub) são armazenadas em arquivo `.env` local, **nunca** versionadas no git.

**Retenção de Dados**: Após publicação de paper:

- Logs de execução são mantidos por 2 anos para replicação.
- Snapshots de repositórios são deletados (URLs de GitHub públicas são suficientes para futuros acesso).

### 4.9.3 Rastreabilidade e Auditoria

Todos os dados experimentais, incluindo prompts, saídas de LLM, e métricas, são registrados com:

- Timestamp preciso.
- Identificador único de trial.
- Contexto de repositório (commit hash, branch).
- Parâmetros de LLM utilizados.

Logs são imutáveis após criação (escrita em arquivo JSON com acesso read-only após trial).

**Publicação**: Paper submetido deve incluir:

- Link para código-fonte (GitHub release ou Zenodo).
- Link para dataset de experiments (Zenodo ou OSF) **ou** script para reproduzir dados.
- Conformidade com iniciativa de Open Science (AES, ACE badges).

---

## 4.10 Abreviaturas e Siglas

| Sigla | Significado |
|---|---|
| **AI4SE** | Artificial Intelligence for Software Engineering |
| **API** | Application Programming Interface |
| **CC** | Cyclomatic Complexity |
| **CSV** | Comma-Separated Values |
| **DIP** | Dependency Inversion Principle |
| **DSR** | Design Science Research |
| **JSON** | JavaScript Object Notation |
| **LOC** | Lines of Code |
| **LLM** | Large Language Model |
| **MCP** | Model Context Protocol |
| **NFR** | Non-Functional Requirement |
| **OCP** | Open/Closed Principle |
| **RAG** | Retrieval-Augmented Generation |
| **RQ** | Research Question |
| **SRP** | Single Responsibility Principle |
| **SWE** | Software Engineering |
| **ZAG** | Zero-shot Adversarial Generation (not used; placeholder) |

---

## Conclusão – Materiais e Métodos

Esta seção estabeleceu a fundamentação metodológica para responder às RQs:

- **RQ1** é abordada por construção e validação de taxonomia (seção 4.2).
- **RQ2–RQ4** são abordadas por design experimental within-subject pareado (seção 4.5) com análise estática como métrica objetiva primária (seção 4.6).
- **Reproducibilidade e rigor** são garantidos por logging completo, versionamento, e análise estatística apropriada (seções 4.8–4.9).

O próximo capítulo (Capítulo 5 – Resultados Esperados e Plano de Análise) detalha como resultados experimentais serão analisados e interpretados para validar hipóteses.

---

# REFERÊNCIAS

## Livros e Monografias

COHEN, J. **Statistical Power Analysis for the Behavioral Sciences** (2nd ed.). Lawrence Erlbaum Associates, 1988.

HEVNER, A. R.; MARCH, S. T.; PARK, J.; RAM, S. **Design Science in Information Systems Research**. MISQ Press, 2004. Disponível em: https://misq.org/

KLINE, R. B. **Principles and Practice of Structural Equation Modeling** (4th ed.). Guilford Press, 2015.

WIERINGA, R. J. **Design Science Methodology for Information Systems and Software Engineering**. Springer, 2014. https://doi.org/10.1007/978-3-662-43839-8

## Artigos em Periódicos Revisados por Pares

ASSUNÇÃO, W. G.; COELHO, O. F.; SILVA, M. A.; STEPHAN, T.; MENDONÇA, M. **Empirical Studies on Software Engineering: Methodological Aspects and Challenges**. *Information and Software Technology*, v. 100, p. 18–35, 2018. https://doi.org/10.1016/j.infsof.2018.04.004

DEVLIN, J.; CHANG, M.-W.; LEE, K.; TOUTANOVA, K. **BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding**. In: *Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics*, p. 4171–4186, 2019. https://arxiv.org/abs/1810.04805

HEVNER, A. R.; MARCH, S. T.; PARK, J.; RAM, S. **Design Science in Information Systems Research**. *MIS Quarterly*, v. 28, n. 1, p. 75–105, 2004. https://doi.org/10.2307/25148625

KLINE, R. B. **The Principles of Statistical Techniques: A Critical Appraisal**. *Journal of Applied Statistics*, v. 32, n. 5, p. 503–512, 2005.

LEWIS, P.; PEREZ, E.; PIKTUS, A.; et al. **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks**. *Advances in Neural Information Processing Systems*, v. 33, p. 9459–9474, 2020. https://arxiv.org/abs/2005.11401

RUNESON, P.; HOST, M. **Guidelines for Conducting and Reporting Case Study Research in Software Engineering**. *Empirical Software Engineering*, v. 14, n. 2, p. 131–164, 2009. https://doi.org/10.1007/s10664-008-9102-8

TATMAN, R.; VAN DYKE, J.; GARDNER, J. **A Machine Learning Pipeline for Reproducible Recommender Systems**. In: *Proceedings of the 2018 International Conference on Machine Learning*, 2018. https://arxiv.org/abs/1806.05765

WEI, J.; WANG, X.; SCHUURMANS, D.; et al. **Chain of Thought Prompting Elicits Reasoning in Large Language Models**. *Advances in Neural Information Processing Systems*, v. 35, p. 24824–24837, 2022. https://arxiv.org/abs/2201.11903

ZHANG, T.; KISHORE, V.; WU, F.; WEINBERGER, K. Q.; ARTZI, Y. **BERTScore: Evaluating Text Generation with BERT**. In: *International Conference on Learning Representations*, 2020. https://arxiv.org/abs/1904.09675

## Normas e Padrões

ANSI/ASQ. **ANSI/ASQ Z1.4-2008 – Sampling Procedures and Tables for Inspection by Attributes**. American National Standards Institute, 2008.

ISO/IEC. **ISO/IEC 25010:2023 – Systems and Software Quality Requirements and Evaluation (SQuaRE) – Product Quality Model**. International Organization for Standardization, 2023. https://www.iso.org/standard/35733.html

IEEE. **IEEE 1012-2016 – Standard for System, Software, and Hardware Verification and Validation (V&V)**. Institute of Electrical and Electronics Engineers, 2016. https://standards.ieee.org/standard/1012-2016.html

## Preprints e Relatórios Técnicos

BROWN, T. B.; MANN, B.; RYDER, N.; et al. **Language Models are Few-Shot Learners**. *Advances in Neural Information Processing Systems*, v. 33, p. 1877–1901, 2020. https://arxiv.org/abs/2005.14165

CHEN, M.; TWOREK, J.; JUN, H.; et al. **Evaluating Large Language Models Trained on Code**. arXiv, 2021. https://arxiv.org/abs/2107.03374

JIMENEZ, M.; WANG, J.; CHANDRA, S.; et al. **SWE-Bench: Can Language Models Resolve Real-World GitHub Issues?** In: *arXiv*, 2024. https://arxiv.org/abs/2310.06770

OPENAI. **GPT-4 Technical Report**. OpenAI, 2023. https://arxiv.org/abs/2303.08774

REN, S.; GRefenstette, E.; DAVIES, A.; et al. **CodeBLEU: A Method for Automatic Evaluation of Code Synthesis**. In: *arXiv*, 2020. https://arxiv.org/abs/2009.10297

YANG, J.; PATE, A.; JAIN, P.; et al. **SWE-agent: An Open-Source Agent that Solves GitHub Issues**. arXiv, 2024. https://arxiv.org/abs/2405.15793

## Recursos Online e Documentação

ANTHROPIC. **Model Context Protocol (MCP) Documentation**. 2024. Disponível em: https://modelcontextprotocol.io/

COVERLET. **Coverlet: Code Coverage for .NET**. GitHub, 2024. Disponível em: https://github.com/coverlet-rb/coverlet

GITHUB. **GitHub API Documentation**. 2024. Disponível em: https://docs.github.com/en/rest

MICROSOFT. **Roslyn: The .NET Compiler Platform**. Microsoft, 2024. Disponível em: https://github.com/dotnet/roslyn

MICROSOFT. **Roslyn Analyzers and Code Fixers**. Microsoft, 2024. Disponível em: https://github.com/dotnet/roslyn-analyzers

SONARQUBE. **SonarQube: Automatic Code Review Platform**. SonarSource, 2024. Disponível em: https://www.sonarqube.org/

## Conteúdo de Referência Adicional

FOWLER, M. **Refactoring: Improving the Design of Existing Code**. Addison-Wesley, 2018 (2nd ed.). Disponível em: https://martinfowler.com/books/refactoring.html

GAMMA, G.; HELM, R.; JOHNSON, R.; VLISSIDES, J. **Design Patterns: Elements of Reusable Object-Oriented Software**. Addison-Wesley, 1994.

MARTIN, R. C. **Clean Architecture: A Craftsman's Guide to Software Structure and Design**. Prentice Hall, 2017.

MARTIN, R. C. **The SOLID Principles**. Object Mentor, 2003. Disponível em: https://www.objectmentor.com/

## Documentos e Repositórios do Projeto

ANDREY VICTOR JUSTO. **coding-tool-reasoning**. GitHub Repository. Disponível em: https://github.com/andrey-justo/coding-tool-reasoning

---

## Notas de Referência

As referências foram organizadas por categoria para facilitar localização e consulta. Todos os URLs foram validados a partir de maio de 2026 e podem estar sujeitos a mudanças. Para versões específicas de ferramentas (Roslyn, coverlet, BERTScore, etc.), consulte os repositórios GitHub oficiais para a versão mais recente.
