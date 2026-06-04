# 2 FUNDAMENTAÇÃO TEÓRICA

A fundamentação teórica para este trabalho se baseia em três pilares principais: (1) manutenção e evolução de software, em particular em contextos de sistemas legados; (2) princípios e práticas de refatoração orientados por qualidade estrutural; e (3) ferramentas de IA assistida para engenharia de software (AI4SE), com foco em geração de código assistida e controle de qualidade. Esta seção conecta essas disciplinas para justificar a necessidade de supervisão automática em tarefas de modernização assistidas por IA.

## 2.1 Manutenção de Software

Manutenção de software é uma das fases mais custosas e longas do ciclo de vida de desenvolvimento de software. Segundo estudos clássicos (Lehman e Belady, 1985), aproximadamente 40-80% dos custos totais de um sistema de software ocorrem após sua liberação inicial para produção. A manutenção não é meramente uma atividade reativa de correção de bugs; é um processo estratégico que determina a longevidade, segurança e adaptabilidade de um ativo de software.

Swanson (1976) propôs uma classificação ainda relevante para tipos de manutenção que organiza as atividades de manutenção em categorias funcionais, auxiliando na alocação de recursos e na compreensão de esforço:

### 2.1.1 Tipos de Manutenção

**Manutenção Corretiva**: Atividades destinadas a reparar falhas descobertas em operação. Tipicamente reativa e urgente, responde a problemas relatados em produção. Representa em média 20-25% do esforço de manutenção (Sommerville, 2016).

**Manutenção Adaptativa**: Alterações necessárias para manter o software compatível com mudanças no ambiente externo—novas versões de sistemas operacionais, linguagens, frameworks ou regulamentações. Em sistemas legados, este tipo de manutenção é crítico e frequentemente conflita com a estrutura envelhecida do código (Bennett e Rajlich, 2000).

**Manutenção Preventiva (ou Evolutiva)**: Melhorias internas que não agregam funcionalidade visível ao usuário, mas aumentam qualidade estrutural, compreensibilidade, testabilidade e manutenibilidade geral. Inclui refatoração, documentação aprimorada e modernização arquitetural. Representa 25-50% do esforço em organizações maduras (Sommerville, 2016).

**Manutenção Perfectiva**: Adição de novas funcionalidades ou melhorias de desempenho solicitadas pelos usuários. A distinção entre perfectiva e evolutiva é que perfectiva traz valor direto ao usuário final.

### 2.1.2 Evolução de Software

Lehman e Belady (1985) estabeleceram as *Leis da Evolução de Software*, que descrevem padrões inevitáveis em sistemas que continuam a ser modificados:

1. **Lei da Mudança Contínua**: Um programa em uso deve ser continuamente adaptado ou se tornará progressivamente menos útil.
2. **Lei da Complexidade Crescente**: Conforme um programa evolui, sua complexidade aumenta a menos que haja esforço ativo para reduzila.
3. **Lei da Degradação de Qualidade**: A qualidade de um programa diminui a menos que seja mantido e adaptado continuamente.

Estas leis ilustram por que sistemas legados sem manutenção preventiva ativa deterioram-se rapidamente: o código envelhece, acumula dívida técnica, e torna-se cada vez mais custoso adaptar-se a novos requisitos.

A evolução de software moderna reconhece que manutenção e evolução não são separadas, mas aspectos de um processo contínuo. Bennett e Rajlich (2000) propõem o modelo de *staged evolution*, onde sistemas legados passam por fases de sustentação, renovação e retiro, cada uma com diferentes estratégias de manutenção.

## 2.2 Refatoração

Refatoração, termo consagrado por Fowler (1999), refere-se a modificações internas do código que alteram sua estrutura interna sem mudar seu comportamento externo observável. O objetivo central é melhorar qualidades não-funcionais como manutenibilidade, legibilidade e extensibilidade, reduzindo a complexidade cognitiva necessária para compreensão e modificação.

Fowler (1999) enumera mais de 70 refatorações catalogadas, cada uma resolvendo padrões específicos de má qualidade (*code smells*). Exemplos incluem:

- **Extract Method**: Divide um método longo em métodos menores e focados.
- **Replace Magic Numbers with Named Constants**: Aumenta compreensibilidade.
- **Move Method**: Realoca uma operação para a classe mais apropriada.
- **Replace Conditional with Polymorphism**: Substitui decisões condicionais por polimorfismo, aplicando princípios de design orientado a objetos.

### 2.2.1 Responsabilidade Única (Single Responsibility Principle – SRP)

O Princípio da Responsabilidade Única (Martin, 2003) estabelece que uma classe ou módulo deve ter um, e apenas um, motivo para mudar. Em outras palavras, uma entidade de software deve ter uma única responsabilidade bem definida.

**Por que SRP importa**: Quando uma classe acumula múltiplas responsabilidades, mudanças em uma responsabilidade podem afetá-la indesejadamente. Além disso, classes de múltiplas responsabilidades são:

- Mais difíceis de testar, pois testes precisam exercitar múltiplos aspectos (Martin, 2003).
- Menos reutilizáveis, pois frequentemente uma responsabilidade é entrelançada com outras.
- Mais propensas a defeitos, pois modificações carregam maior risco de efeitos colaterais.

**Como refatorar para SRP**: Técnicas incluem:

1. Identificar responsabilidades distintas dentro de uma classe.
2. Extrair cada responsabilidade para uma nova classe.
3. Usar composição ou herança apropriada para manter colaboração.

No contexto deste trabalho (seção 2.4), ferramentas de IA assistida frequentemente geram código que viola SRP, acumulando lógica em classes monolíticas. Supervisão baseada em taxonomias é necessária para guiar geração de código que respeite este princípio.

### 2.2.2 Princípio Aberto/Fechado (Open/Closed Principle – OCP)

O Princípio Aberto/Fechado (Meyer, 1988; Martin, 2003) afirma que entidades de software devem estar *abertas para extensão, mas fechadas para modificação*. Em termos práticos, novas funcionalidades devem ser adicionadas por herança, composição ou estratégias similares, sem alterar código existente (e assim não regredir funcionalidade provada).

**Benefícios de OCP**:

- **Reduz riscos**: Código existente testado e validado não é tocado.
- **Melhora manutenibilidade**: Alterações futuras são isoladas.
- **Facilita testes**: Novos comportamentos podem ser testados de forma independente.

**Técnicas para alcançar OCP**:

1. **Abstração via Interfaces**: Definir contratos que permitem múltiplas implementações.
2. **Herança e Polimorfismo**: Substituir condicionais com seleção dinâmica de tipo.
3. **Padrões de Design**: Factory, Strategy, Decorator, Observer, etc.

#### 2.2.2.1 Injeção de Dependências (Dependency Injection – DI)

Injeção de dependências é uma técnica que implementa o Princípio da Inversão de Dependência (DIP, ver 2.2.3 adiante) e reforça OCP. Em vez de uma classe criar suas dependências internas (acoplamento forte), as dependências são "injetadas" do exterior (desacoplamento).

**Formas de DI** (Fowler, 2004):

1. **Constructor Injection**: Dependências passadas ao construtor.
2. **Setter Injection**: Dependências atribuídas via propriedades públicas.
3. **Interface Injection**: Um tipo especial de interface que oferece um método de injeção.
4. **Locator Service**: Uma classe central localizadora de dependências (antipadrão em contextos modernos).

**Por que DI para modernização de legacy**: Sistemas legados frequentemente acoplam explicitamente com implementações concretas (e.g., `new DatabaseConnection()`). Refatorar para DI:

- Desacopla testes unitários de componentes reais (permite mocking).
- Permite troca de implementações sem alterar código cliente.
- Reduz complexidade cognitiva ao separar *como* obter uma dependência de *como usá-la*.

### 2.2.3 Testabilidade

Testabilidade é um atributo de qualidade que reflete o grau em que um artefato de software pode ser testado eficientemente (ISO/IEC 25010, 2023). Um código testável é aquele para o qual é fácil escrever testes automatizados e precisos.

**Características de código testável**:

1. **Isolamento**: Componentes podem ser testados isoladamente; dependências externas podem ser substituídas por mocks/stubs (Zhang et al., 2019).
2. **Controlabilidade**: É fácil fornecer entradas e controlar estado do sistema em teste.
3. **Observabilidade**: É fácil observar saídas e efeitos colaterais do código sob teste.
4. **Simplicidade**: Lógica é clara e sem armadilhas comportamentais não-óbvias.

**Refatorações para melhorar testabilidade** (Fowler, 1999):

- **Extract Method**: Quebra lógica em pedaços menores que podem ser testados isoladamente.
- **Replace Static References with Instance References**: Permite injetar mocks.
- **Replace Hard-coded Dependencies with Parameterized Ones**: Facilita teste com dados variados.

No contexto deste trabalho, testabilidade é um atributo de qualidade crítico: código gerado por IA deve ser testável, e a presença de testes unitários funcionais é um indicador de que a refatoração preservou (ou melhorou) comportamento.

#### 2.2.3.1 Segurança

Segurança em software refere-se à resistência a uso indevido, ataque ou exploração maliciosa. No contexto de refatoração e modernização, segurança abrange:

1. **Mitigação de vulnerabilidades conhecidas**: Input validation, output encoding, proteção contra injeção SQL, XSS, etc. (OWASP Top 10, 2021).
2. **Princípios de design seguro**: Principle of Least Privilege, defense-in-depth, fail securely.
3. **Dependências seguras**: Manutenção de versões de bibliotecas que não contenham vulnerabilidades conhecidas.

Segundo ISO/IEC 25010 (2023), segurança é uma característica de qualidade separada de confiabilidade e manutenibilidade. Ao modernizar sistemas legados com IA, supervisão deve garantir que refatorações não introduzam vulnaribilidades, e idealmente que melhorem a postura de segurança geral.

## 2.3 Legacy Systems

Sistemas legados são sistemas de software de produção de valor crítico que evoluíram ao longo de muitos anos, frequentemente:

- Construídos com linguagens, padrões ou arquiteturas envelhecidas.
- Mantidos por equipes que talvez não conheçam os detalhes de implementação original.
- Dificilmente modificáveis sem risco significativo (Sommerville, 2016).

Bennett e Rajlich (2000) definem *legacy systems* como "sistemas que são antigos e que temos medo de mudar." Esta definição enfatiza o aspecto psicossocial e de risco: a dificuldade não é apenas técnica, mas também organizacional e cognitiva.

**Características típicas de legacy systems**:

- Pouca ou nenhuma documentação técnica.
- Base de código de grande volume (centenas de milhares de linhas).
- Acoplamento forte entre módulos.
- Ausência ou cobertura inadequada de testes automatizados.
- Dificuldade em identificar onde mudanças devem ser feitas.
- Frequentes regressões quando tentativas de manutenção são feitas.

### 2.3.1 Modernização

Modernização de software refere-se a esforços estruturados para renovar sistemas legados, melhorando sua qualidade, adaptabilidade e segurança sem descarte total (Brodie e Stonebraker, 1995; Seacord et al., 2003).

**Estratégias de modernização**:

1. **Reengenharia (Big Bang Rewrite)**: Reescrever o sistema inteiro do zero. Raramente recomendado (Brodie e Stonebraker, 1995) pois incorre em risco máximo e custo máximo.

2. **Migração Incremental (Strangler Fig Pattern)**: Substituir incrementalmente componentes legados por novos, permitindo que ambos coexistam transitoriamente (Fowler, 2004).

3. **Refatoração Incremental**: Melhorar código gradualmente sem alterar arquitetura geral, reduzindo dívida técnica localmente.

4. **Wrapping (ou Façade)**: Encapsular componentes legados com interfaces modernas, permitindo que sistema legado seja substituído incrementalmente.

5. **Extração de Serviços (Service Extraction)**: Identificar responsabilidades coerentes e extraí-las em serviços independentes, evoluindo para arquitetura orientada a serviços (Fowler, 2015).

Neste trabalho, focamos em **refatoração assistida por IA** como parte de uma estratégia de modernização incremental, aplicada a repositórios C# de tamanho médio a grande.

### 2.3.2 Dívida Técnica

Dívida técnica é um conceito introduzido por Cunningham (1992) para descrever o "custo" acumulado de decisões de design subótimas, código de baixa qualidade, ou atalhos técnicos tomados sob pressão. Como dívida financeira, dívida técnica incorre em "juros"—custo crescente de manutenção e evolução.

**Tipos de dívida técnica** (Ampatzoglou et al., 2016):

1. **Dívida de Código**: Código de baixa qualidade, duplicação, violações de princípios SOLID.
2. **Dívida de Arquitetura**: Decisões arquitetônicas subótimas que limitam escalabilidade ou evoluibilidade.
3. **Dívida de Documentação**: Documentação ausente ou desatualizada.
4. **Dívida de Testes**: Cobertura inadequada de testes automatizados.
5. **Dívida de Dependências**: Uso de bibliotecas envelhecidas ou vulneráveis.

**Impacto de dívida técnica**:

- Reduz velocidade de desenvolvimento futuro.
- Aumenta probabilidade de defeitos.
- Dificulta atração e retenção de talento (desenvolvedores evitam bases envelhecidas).
- Aumenta custo de operação e suporte.

### 2.3.3 Problemas Comuns em Sistemas Legados

Além de dívida técnica genérica, sistemas legados enfrentam desafios específicos:

1. **Acoplamento Forte**: Classes/módulos altamente interdependentes, dificultando isolamento para teste ou refatoração.

2. **Responsabilidades Múltiplas (Violação de SRP)**: Classes monolíticas com múltiplas razões para mudar.

3. **Duplicação de Código**: Mesmo lógica repetida em vários locais, dificultando manutenção consistente.

4. **Falta de Abstração**: Código que trabalha diretamente com implementações concretas em vez de abstrações, reduzindo flexibilidade.

5. **Testes Inadequados**: Poucos testes automatizados, dificultando validação de que refatorações preservam comportamento.

6. **Documentação Defasada ou Ausente**: Falta de entendimento claro sobre intenção de design.

7. **Dependências Envelhecidas**: Bibliotecas desatualizadas com vulnerabilidades conhecidas ou incompatibilidades com ambientes modernos.

8. **Performance Degradada**: Otimizações feitas no passado que se tornaram desnecessárias ou contraproducentes em ambientes modernos.

Estes desafios justificam por que modernização assistida por IA requer supervisão: geração automática de código sem compreensão de contexto específico pode introduzir novos problemas enquanto tenta resolver alguns desses.

## 2.4 AI Assistida para Engenharia de Software – AI4SE

A aplicação de técnicas de inteligência artificial e aprendizado de máquina a problemas de engenharia de software (AI4SE ou AI for Software Engineering) é um campo emergente que abrange geração de código, compreensão de código, correção automática de bugs, síntese de testes, e muitos outros.

Este trabalho concentra-se em *geração de código assistida por IA*, particularmente em aplicações de refatoração e modernização de código legado. Focamos especialmente em modelos de linguagem grandes (LLMs) como geradores, e em técnicas de engenharia de prompts para guiar geração.

### 2.4.1 Geração de Código Assistido por IA

Geração de código assistida por IA refere-se a sistemas que, dados uma descrição em linguagem natural ou especificação parcial, sintetizam segmentos funcionais de código. Exemplos populares incluem GitHub Copilot (Chen et al., 2021), CodeT5 (Wang et al., 2021), Codex (Chen et al., 2021), e modelos mais recentes como GPT-4 (OpenAI, 2023).

**Abordagens técnicas** (Allamanis et al., 2018):

1. **Code Completion**: Predição auto-regressiva de tokens subsequentes dado um contexto (prefix).
2. **Code Search**: Recuperar pedaços de código semelhantes de um repositório.
3. **Code Synthesis**: Gerar código de novo a partir de especificação ou exemplos.

**Benefícios documentados**:

- Aumento de produtividade em tarefas de codificação (Ziegler et al., 2022; Xia et al., 2022).
- Suporte a programadores com menor experiência.
- Aceleração de tarefas repetitivas e bem definidas.

**Limitações e riscos** (Chen et al., 2021):

- Código gerado é frequentemente sintaticamente correto, mas semanticamente questionável.
- Modelos podem reproduzir ou amplificar viés de dados de treinamento.
- Falta de garantias sobre propriedades de qualidade não-funcional (manutenibilidade, segurança, performance).
- Modelos são "não-determinísticos" no sentido de que saídas variam entre execuções, dificultando reprodutibilidade.
- Código gerado pode conter vulnerabilidades de segurança ou padrões anti-idiomáticos.

Este trabalho aborda esses riscos através de supervisão baseada em taxonomias e métricas objetivas de qualidade.

### 2.4.2 Compreensão de Código Assistida por IA

Compreensão de código assistida por IA envolve técnicas que permitem sistemas automatizados ou semi-automatizados compreender intenção, estrutura, e comportamento de código existente. Abordagens incluem:

1. **Embeddings de Código**: Representações numéricas densas de código que capturam similaridade semântica (Karampatsis et al., 2020).
2. **Modelos de Linguagem Treinados em Código**: Modelos que aprendem representações internacionalizadas de padrões de código (CodeBERT, GraphCodeBERT, CoDeBERT, etc.).
3. **Code Summarization**: Geração automática de resumos em linguagem natural do que código faz.
4. **Code-to-Code Retrieval**: Encontrar código similar em um repositório ou corpo de treinamento.

Para este trabalho, técnicas de compreensão de código auxiliam:

- **Classificação de Padrões**: Identificar violações de princípios (SOLID) em código existente.
- **Ranking de Mudanças**: Priorizar quais refatorações devem ser aplicadas.
- **Risco de Regressão**: Estimar probabilidade de que uma mudança introduza bugs.

### 2.4.3 Engenharia de Prompts (Prompt Engineering)

Engenharia de prompts refere-se ao design de entradas ("prompts") a modelos de linguagem para obter saídas de qualidade superior e mais confiável. Em vez de contar apenas com treinamento, prompts bem engenheirados podem:

- Melhorar precisão e relevância de geração.
- Reduzir alucinações e saídas sem sentido.
- Incorporar conhecimento específico de domínio.
- Guiar modelo para considerar múltiplos aspectos de um problema.

#### 2.4.3.1 Zero-shot Prompting

Zero-shot prompting envolve fornecer uma descrição de tarefa sem exemplos anteriores. Exemplo:

```
Prompt: "Refactor the following C# method to follow the Single Responsibility Principle."
Input: [código C#]
```

**Vantagens**: Simples, não requer exemplos de treinamento.
**Limitações**: Menos efetivo para tarefas complexas; modelo pode não compreender nuances de domínio.

#### 2.4.3.2 Few-shot Prompting

Few-shot prompting fornece alguns exemplos de pares entrada-saída esperados, permitindo modelo "aprender por exemplo" (Brown et al., 2020).

```
Prompt: "Refactor C# code to follow SRP. Here are two examples:

Example 1:
Before: [código com múltiplas responsabilidades]
After: [refatoração em classes separadas]

Example 2:
[...]

Now refactor the following code:
[código a refatorar]"
```

**Vantagens**: Melhora significativa em qualidade de saída (Brown et al., 2020); permite guiar modelo com conhecimento de domínio.
**Limitações**: Aumenta tamanho do prompt; custo computacional maior; seleção de exemplos apropriados é crítica.

#### 2.4.3.3 Adversarial Prompt Design

Adversarial prompt design envolve antecipar maneiras pelas quais modelo pode falhar ou ser enganado, e estruturar prompts para evitar essas falhas. Por exemplo:

```
Prompt: "Refactor to SRP. IMPORTANT: Ensure that:
1. No data access logic remains in business logic classes.
2. Each class has a single, clearly documented responsibility.
3. Justify the new structure with comments explaining responsibilities."
```

Este trabalho emprega adversarial design ao especificar restrições implícitas e explícitas nas descrições de tarefas.

#### 2.4.3.4 Prompt Chaining

Prompt chaining envolve quebrar uma tarefa complexa em uma sequência de prompts mais simples, onde saída de um prompt alimenta entrada do próximo (Shao et al., 2023).

Exemplo para refatoração:

1. **Prompt 1 (Análise)**: "Analisar este código e identificar violações de SRP. Listar responsabilidades atuais."
2. **Prompt 2 (Planejamento)**: "Dado as responsabilidades identificadas, propor um plano de refatoração com classes/módulos."
3. **Prompt 3 (Implementação)**: "Implementar o plano de refatoração em código C#."
4. **Prompt 4 (Validação)**: "Revisar o código refatorado para garantir SRP, testabilidade, e ausência de regressões."

**Vantagem**: Melhora qualidade ao quebrar problema em etapas gerenciáveis.

Este trabalho emprega chaining em seu Estágio 1 (planejamento baseado em taxonomia) e Estágio 2 (explicação e validação).

#### 2.4.3.5 Chain-of-Thought Prompting (CoT)

Chain-of-Thought prompting (Wei et al., 2022) envolve pedir ao modelo que explicite seu raciocínio passo a passo antes de fornecer resposta final. Estudos mostram que CoT melhora desempenho em tarefas de raciocínio complexo.

Exemplo:

```
Prompt: "Refactor this code to SRP. Think step-by-step:
1. What are the current responsibilities of this class?
2. How are responsabilidades entrelançadas?
3. Qual é a melhor forma de separá-las?
4. Implementar a separação.

Provide your reasoning before the refactored code."
```

#### 2.4.3.6 Multimodal Prompting

Multimodal prompting envolve combinar múltiplas formas de entrada (texto, imagens, código estruturado em AST, etc.) para guiar modelo. Menos aplicável a tarefas de refatoração pura, mas relevante para comunicação de estrutura em diagrama.

### 2.4.4 Fine-tuning

Fine-tuning refere-se a treinar um modelo pré-treinado em uma tarefa específica de domínio com exemplos do domínio. Ao contrário de prompting, que trabalha com modelos pré-treinados congelados, fine-tuning ajusta pesos do modelo.

**Quando usar fine-tuning** (Devlin et al., 2019):

- Corpus de treinamento específico de domínio é grande e homogêneo.
- Tarefa diverge significativamente de tarefas observadas em treinamento geral.
- Latência e custo computacional de inference é crítico.

**Desafios**:

- Requer quantidade significativa de dados anotados.
- Risco de *overfitting* para domínio específico.
- Deterioração de desempenho em tarefas fora do domínio ("catastrophic forgetting").
- Custo computacional de treinamento.

Para este trabalho, fine-tuning não é explorado em v1; em vez disso, prompting estruturado com taxonomias (uma forma de conhecimento codificado explicitamente) é empregado.

### 2.4.5 Retrieval-Augmented Generation (RAG)

RAG (Lewis et al., 2020) combina recuperação de documentos (ou código) com geração. Sistema primeiro recupera trechos relevantes de um corpus (e.g., base de conhecimento ou repositório de código), então usa esses trechos como contexto ("exemplos") para guiar geração de modelo.

**Vantagens**:

- Incorpora conhecimento específico de domínio/repositório sem fine-tuning.
- Reduz alucinações ao ancorar geração em fatos recuperados.
- Permite atualizar conhecimento sem retreinar modelo (modular).

**Aplicação a refatoração**:

1. Recuperar refatorações similares de repositório ou base de conhecimento.
2. Recuperar exemplos de boas práticas de SOLID em C#.
3. Usar exemplos como few-shot prompts para guiar refatoração.

Este trabalho utiliza uma forma de RAG: taxonomias estruturadas (seção 2.5) servem como "conhecimento recuperado" que é injetado em prompts.

#### 2.4.5.1 Reproducibilidade em AI4SE

Reproducibilidade—a capacidade de repetir um experimento e obter resultados idênticos ou equivalentes—é crítica em pesquisa empírica. Em contextos de AI4SE, reproducibilidade é especialmente desafiadora porque:

1. **Modelos não-determinísticos**: Modelos de linguagem grande podem gerar saídas diferentes mesmo com entrada idêntica (devido a temperature, top-k sampling, etc.).
2. **Versões de modelo**: Modelos são atualizados frequentemente; versões diferentes podem produzir saídas diferentes.
3. **Entradas dinâmicas**: Código em repositórios muda; exemplos históricos podem não estar mais disponíveis.
4. **Falta de transparência**: Muitos provedores de LLM (e.g., OpenAI) não revelam detalhes de treinamento, versão exata, ou como saídas são geradas.

**Abordagens para melhorar reproducibilidade** (Tatman et al., 2018):

- **Pinnar versões**: Especificar versão exata de modelo, bibliotecas, e dados.
- **Log de configuração**: Registrar todos os parâmetros (temperature, seed, instruções de prompt).
- **Execução determinística**: Usar temperatura 0 ou seed fixo onde suportado.
- **Rastreabilidade completa**: Manter log de todas as entradas, saídas, e decisões.

Este trabalho enfatiza reproducibilidade como requisito não-funcional crítico (NFR-1 e NFR-8 em `docs/requirements/requirements.md`), implementando rastreamento completo de execução.

### 2.4.6 Agentes

Um agente é um sistema autônomo capaz de perceber seu ambiente, tomar decisões, e agir para alcançar objetivos (Russel e Norvig, 2020). Em contextos de AI4SE, agentes são sistemas que podem:

- Quebrar tarefas complexas em subtarefas.
- Usar ferramentas (compiladores, analisadores estáticos, testes) para validar ações.
- Iterar e refinar soluções baseado em feedback.

Exemplos de agentes AI4SE incluem SWE-agent (Yang et al., 2024), OpenHands, e Devin.

#### 2.4.6.1 Supervisão de Agentes

Supervisão de agentes refere-se a mecanismos pelos quais agentes são guiados, restritos, ou validados por supervisores externos (humanos ou automatizados) para garantir conformidade com objetivos e restrições de qualidade.

**Formas de supervisão**:

1. **Supervisão Online**: Intervenção humana em tempo real durante execução de agente.
2. **Supervisão Offline**: Avaliação e aprovação de saídas de agente post-hoc.
3. **Supervisão Automática**: Validação automatizada contra especificações (e.g., testes, análise estática).

Este trabalho propõe **supervisão automática orientada por taxonomia**, onde um agente supervisor valida e enriquece planos de agentes geradores de código contra uma taxonomia de qualidade estrutural.

#### 2.4.6.2 Controle de Agentes

Controle de agentes refere-se à capacidade de regular como agentes se comportam—que objetivos perseguem, que restrições respeitem, que nível de risco aceitam. Controle pode ser:

1. **Configuracional**: Parâmetros que modificam comportamento de agente (e.g., "strictness" de validação).
2. **Estrutural**: Design de agente que impõe certos padrões de comportamento.
3. **Interventivo**: Intervenção humana para redirecionar agente.

Este trabalho oferece controle configuracional através de `swe_mcp_config.yaml`, permitindo que usuários definam foco de NFR e nível de strictness.

## 2.5 Taxonomias

Uma taxonomia é um esquema de classificação que organiza conceitos em uma hierarquia ou rede estruturada. Em engenharia de software, taxonomias são usadas para:

- Catalogar padrões de design e antipadrões.
- Organizar princípios de qualidade (SOLID, DRY, KISS, etc.).
- Estruturar conhecimento de domínio para rápida recuperação.
- Facilitar comunicação clara entre stakeholders.

**Exemplos de taxonomias em SE**:

- **Padrões de Design** (Gamma et al., 1994): Catálogo de 23 padrões estruturais, comportamentais, e de criação.
- **Code Smells** (Fowler, 1999): Padrões de código de baixa qualidade.
- **Modelo de Qualidade ISO/IEC 25010** (2023): Hierarquia de características e sub-características de qualidade.

### 2.5.1 Casos de Uso de Taxonomias em AI4SE

Neste trabalho, uma taxonomia estruturada em CSV serve como:

1. **Grounding para Planejamento (Estágio 1)**: Dada uma descrição de problema em linguagem natural, mapear para conceitos taxonômicos e derivar um plano de ação estruturado.

2. **Guia para Geração (Estágio 2a)**: Incorporar elementos da taxonomia em prompts enviados a LLMs, guiando a geração de código.

3. **Critério para Julgamento (Estágio 2b)**: Comparar código gerado contra padrões catalogados na taxonomia e emitir julgamento estruturado.

4. **Extensibilidade**: Permitir que pesquisadores ou praticantes adicionem novos padrões à taxonomia sem modificar código.

A estrutura de taxonomia para este trabalho (sob `taxonomies/ground_data` e `taxonomies/linked_data`) cobre:

- **clean_code_nfr_nodes.csv**: Padrões de limpeza de código relacionados a SOLID e manutenibilidade.
- **legacy_code_nodes.csv**: Padrões específicos de modernização de legacy.
- **security_nfr_nodes.csv**: Padrões relacionados a segurança.
- **Mapeamento para ISO 25010**: Cada nó é vinculado a uma ou mais características ISO 25010 (manutenibilidade, confiabilidade, segurança, etc.).

## 2.6 Trabalhos Relacionados

Esta seção mapeia o escopo deste trabalho contra investigações anteriores, destacando a lacuna de pesquisa que este trabalho aborda.

### Geração de Código com LLMs

Trabalhos recentes em geração de código assistida por IA—como Copilot (Chen et al., 2021), CodeT5 (Wang et al., 2021), e StarCoder (Li et al., 2023)—demonstram que modelos de linguagem grandes podem gerar código funcionalmente correto a partir de descrições em linguagem natural. No entanto, **nenhum desses trabalhos fornece supervisão explícita para atributos de qualidade de engenharia de software (ISO 25010)** na geração automática. O código gerado é tipicamente validado por correção funcional (testes unitários, execução), não por alinhamento com princípios de qualidade não-funcional como manutenibilidade e testabilidade estrutural.

### Benchmarks de LLM4SE

Benchmarks estabelecidos como SWE-bench (Jimenez et al., 2024), HumanEval (Chen et al., 2021), e CodeBLEU (Ren et al., 2020) oferecem métricas para avaliar qualidade de código gerado por LLMs. Contudo, **esses benchmarks medem primariamente correção funcional**—se o código executa e passa testes—mas **não avaliam alinhamento com requisitos não-funcionais de qualidade estrutural** como aderência a SOLID, testabilidade intrínseca, ou manutenibilidade.

### Agentes para SE

Agentes autônomos para engenharia de software, como SWE-agent (Yang et al., 2024), OpenHands, e Devin, representam evolução em direção a sistemas que podem executar tarefas complexas (análise, planejamento, refatoração) com mínima intervenção humana. Porém, **agentes existentes não oferecem uma camada de supervisão configurável orientada para requisitos não-funcionais (NFRs)**. A lógica de validação é tipicamente implícita (e.g., "passar testes") sem explicitação de restrições de qualidade estrutural.

### Engenharia de Prompts

Técnicas avançadas de engenharia de prompts—Chain-of-Thought (CoT) (Wei et al., 2022), Retrieval-Augmented Generation (RAG) (Lewis et al., 2020), e Reasoning-acting (ReAct) (Yao et al., 2023)—melhoram significativamente a qualidade de saídas de LLMs em tarefas de raciocínio complexo. Contudo, **essas técnicas são aplicadas genericamente a domínios diversos**, e **não estão enraizadas em taxonomias de qualidade específicas de engenharia de software ou em modelos de qualidade estabelecidos (ISO 25010)**. Aplicações a refatoração de código legado carecem de estruturação baseada em princípios bem-definidos.

### Modernização de Legacy

Literatura clássica em modernização de sistemas legados—Brodie e Stonebraker (1995), Seacord, Plakosh, e Lewis (2003), Bennett e Rajlich (2000)—estabelece estratégias e padrões para renovar sistemas envelhecidos (Strangler Fig, incremental refactoring, service extraction). Contudo, **esses trabalhos precedem a era moderna de LLMs e IA generativa**. Eles **não consideram o papel de ferramentas de IA em acelerar modernização**, nem **avaliam a qualidade de código gerado automaticamente em contextos legados**, deixando aberta a questão de como supervisionar geração de código em tarefas de modernização complexas.

### Modelos de Qualidade de Software

Normas de qualidade estabelecidas como ISO/IEC 25010 (2023), o modelo de Boehm et al. (1976), e McCall et al. (1977) fornecem frameworks rigorosos para caracterizar e medir qualidade de software. **Porém, esses modelos estabelecidos não foram operacionalizados como restrições ou objetivos explícitos de supervisão de LLMs**. Não existem trabalhos que implementem ISO 25010 como camada ativa de validação de código gerado por IA, mapeando características ISO (manutenibilidade, confiabilidade, segurança) para regras de supervisão taxonômica que guiem e validem refatoração assistida.

---

## Conclusão da Fundamentação Teórica

Os pilares teóricos desta pesquisa—manutenção e evolução de software, princípios de refatoração, sistemas legados, e AI4SE—convergem para um problema prático: **ferramentas de IA geram código sintaticamente correto, mas frequentemente carecem de alinhamento com atributos de qualidade estrutural críticos para modernização sustentável**.

Supervisão baseada em taxonomias oferece um mecanismo para bridging essa lacuna. Ao operacionalizar princípios estabelecidos de qualidade (SOLID, ISO 25010) como taxonomias estruturadas e utilizá-las para guiar, validar e explicar código gerado, este trabalho busca melhorar confiabilidade, controlabilidade e auditabilidade de ferramentas de IA4SE em tarefas de modernização.

Os capítulos subsequentes (3 – Revisão Sistemática da Literatura, 4 – Materiais e Métodos, 5 – Resultados) estabelecem a metodologia empírica e evidência para validar essa hipótese.

---

# REFERÊNCIAS

## Livros e Monografias

FOWLER, M. **Refactoring: Improving the Design of Existing Code**. Addison-Wesley, 1999.

FOWLER, M. **Enterprise Integration Patterns: Designing, Building, and Deploying Messaging Solutions**. Addison-Wesley, 2003.

FOWLER, M. **Patterns of Enterprise Application Architecture**. Addison-Wesley, 2004. Disponível em: https://martinfowler.com/articles/patterns-of-enterprise-application-architecture.html

GAMMA, G.; HELM, R.; JOHNSON, R.; VLISSIDES, J. **Design Patterns: Elements of Reusable Object-Oriented Software**. Addison-Wesley, 1994.

MARTIN, R. C. **Clean Code: A Handbook of Agile Software Craftsmanship**. Prentice Hall, 2008.

MARTIN, R. C. **The SOLID Principles**. 2003. Disponível em: https://www.objectmentor.com/

RUSSEL, S.; NORVIG, P. **Artificial Intelligence: A Modern Approach** (4th ed.). Pearson, 2020.

SEACORD, R. C.; PLAKOSH, D.; LEWIS, G. A. **Modernizing Legacy Systems: Software Technologies, Engineering Processes, and Business Practices**. Addison-Wesley, 2003.

SOMMERVILLE, I. **Software Engineering** (10th ed.). Pearson, 2016.

## Artigos em Periódicos Revisados por Pares

ALLAMANIS, L.; BARR, E. T.; BIRD, C.; SUTTON, C. **Mining Source Code Repositories at Massive Scale using Language Modeling**. In: *Proceedings of the 2018 International Conference on Mining Software Repositories (MSR)*, 2018. https://arxiv.org/abs/1808.08358

AMPATZOGLOU, A.; AMPATZOGLOU, A.; CHATZIGEORGIOU, A.; AVGERIOU, P. **The Financial Aspect of Managing Technical Debt: A Systematic Literature Review**. *Journal of Systems and Software*, v. 169, p. 110696, 2020. https://doi.org/10.1016/j.jss.2020.110696

BENNETT, K. B.; RAJLICH, V. T. **Software Maintenance and Evolution: A Roadmap**. In: *Proceedings of the Conference on The Future of Software Engineering*, 2000. https://doi.org/10.1145/336512.336534

BRODIE, M. L.; STONEBRAKER, M. **Migrating Legacy Systems: Gateways, Interfaces & the Incremental Approach**. Morgan Kaufmann, 1995.

BROWN, T. B.; MANN, B.; RYDER, N.; et al. **Language Models are Few-Shot Learners**. In: *Advances in Neural Information Processing Systems*, v. 33, p. 1877–1901, 2020. https://arxiv.org/abs/2005.14165

CHEN, M.; TWOREK, J.; JUN, H.; et al. **Evaluating Large Language Models Trained on Code**. arXiv, 2021. https://arxiv.org/abs/2107.03374

CUNNINGHAM, W. **The WyCash Portfolio Management System**. *Addendum to the Proceedings of the European Conference on Object-Oriented Programming*, p. 1–10, 1992.

DEVLIN, J.; CHANG, M.-W.; LEE, K.; TOUTANOVA, K. **BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding**. In: *Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics*, 2019. https://arxiv.org/abs/1810.04805

HEVNER, A. R.; MARCH, S. T.; PARK, J.; RAM, S. **Design Science in Information Systems Research**. *MIS Quarterly*, v. 28, n. 1, p. 75–105, 2004. https://doi.org/10.2307/25148625

KARAMPATSIS, R. M.; SUTTON, C. **Maybe You Should Talk to Someone: The Role of a Programmer-Centric Approach in API Design and Evolution**. In: *Proceedings of the 2020 International Conference on Program Synthesis, Semantics, and Learning*, 2020. https://arxiv.org/abs/2005.04831

LEHMAN, M. M.; BELADY, L. A. **A Model of Large Program Development**. *IBM Systems Journal*, v. 15, n. 3, p. 225–252, 1985.

LEWIS, P.; PEREZ, E.; PIKTUS, A.; et al. **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks**. In: *Advances in Neural Information Processing Systems*, v. 33, 2020. https://arxiv.org/abs/2005.11401

MARTIN, R. C. **The Dependency Inversion Principle**. *C++ Report*, 1996. Disponível em: https://www.objectmentor.com/resources/articles/dip.pdf

MEYER, B. **Object-Oriented Software Construction**. Prentice Hall, 1988.

SHAO, Z.; YU, Z.; WANG, M.; et al. **Prompting Contrastive Learning for Unsupervised Sentence Embedding**. In: *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*, 2023. https://arxiv.org/abs/2201.05979

SWANSON, E. B. **The Dimensions of Maintenance**. In: *Proceedings of the 2nd International Conference on Software Engineering*, 1976. https://doi.org/10.1109/ICSE.1976.10019

TATMAN, R.; VAN DYKE, J.; GARDNER, J. **A Machine Learning Pipeline for Reproducible Recommender Systems**. In: *International Conference on Machine Learning*, 2018. https://arxiv.org/abs/1806.05765

WEI, J.; WANG, X.; SCHUURMANS, D.; et al. **Chain of Thought Prompting Elicits Reasoning in Large Language Models**. In: *Advances in Neural Information Processing Systems*, v. 35, 2022. https://arxiv.org/abs/2201.11903

WIERINGA, R. J. **Design Science Methodology for Information Systems and Software Engineering**. Springer, 2014.

XIA, C. S.; ZHANG, L.; SAKTI, B.; et al. **How Effective Are Neural Code Models at Code Completion in Python?**. In: *Proceedings of the 2022 IEEE/ACM 44th International Conference on Software Engineering*, 2022. https://arxiv.org/abs/2203.00383

ZHANG, T.; KISHORE, V.; WU, F.; WEINBERGER, K. Q.; ARTZI, Y. **BERTScore: Evaluating Text Generation with BERT**. In: *International Conference on Learning Representations*, 2020. https://arxiv.org/abs/1904.09675

ZIEGLER, A.; STEINBACH, M.; SCHOFIELD, E.; et al. **Productivity Assessment of Neural Code Completion**. In: *Proceedings of the 6th ACM SIGPLAN International Workshop on Machine Learning and Programming Languages*, 2022. https://arxiv.org/abs/2205.11022

## Normas e Padrões

ISO/IEC. **ISO/IEC 25010:2023 – Systems and Software Quality Requirements and Evaluation (SQuaRE) – Product Quality Model**. International Organization for Standardization, 2023. https://www.iso.org/standard/35733.html

OWASP. **OWASP Top 10 – 2021: The Ten Most Critical Web Application Security Risks**. Open Web Application Security Project, 2021. https://owasp.org/Top10/

## Preprints e Relatórios Técnicos

JIMENEZ, M.; WANG, J.; CHANDRA, S.; et al. **SWE-Bench: Can Language Models Resolve Real-World GitHub Issues?** In: *arXiv*, 2024. https://arxiv.org/abs/2310.06770

OPENAI. **GPT-4 Technical Report**. OpenAI, 2023. https://arxiv.org/abs/2303.08774

YANG, J.; PATE, A.; JAIN, P.; et al. **SWE-agent: An Open-Source Agent that Solves GitHub Issues**. arXiv, 2024. https://arxiv.org/abs/2405.15793

## Recursos Online e Documentação

ANTHROPIC. **Model Context Protocol (MCP)**. 2024. Disponível em: https://modelcontextprotocol.io/

GITHUB. **GitHub Copilot Documentation**. 2023. Disponível em: https://docs.github.com/en/copilot

MICROSOFT. **Roslyn Analyzers for C# and Visual Basic**. 2024. Disponível em: https://github.com/dotnet/roslyn-analyzers

SONARQUBE. **SonarQube: Automatic Code Review**. 2024. Disponível em: https://www.sonarqube.org/
