# Agent Execution Architecture: Data Flow and Component Integration

This document describes how data moves through the supervisor-agent pipeline and how components integrate during execution.

## 1) End-to-End Data Flow

```mermaid
flowchart LR
    U[Developer or MCP Client]
    P1[plan_swe_code_change]
    B1[build_swe_code_context]
    J1[judge_swe_code_change]

    CFG[swe_mcp_config.yaml]
    KB[SweKnowledgeBase]
    GD[knowledge/data]
    LD[knowledge/linked_data]
    AS[Concern Assets Loader]
    TM[knowledge/template]
    CA[Concern data.json]

    PL[CodeGenPlan]
    CTX[SweContext]
    GEN[Downstream Code Generation Agent]
    OC[Original Code]
    MC[Modified Code]
    EX[SweCodeChangeExplanation]

    U --> P1
    U --> B1
    U --> J1

    CFG --> P1
    CFG --> B1
    CFG --> J1

    GD --> KB
    LD --> KB
    KB --> P1
    KB --> B1
    KB --> J1

    TM --> AS
    CA --> AS
    AS --> B1

    P1 --> PL
    PL --> B1
    B1 --> CTX
    CTX --> GEN
    GEN --> MC
    U --> OC
    OC --> J1
    MC --> J1
    CTX --> J1
    J1 --> EX
    EX --> U
```

## 2) Data Components Integration

```mermaid
flowchart TB
    subgraph Runtime[Runtime Layer]
        MCP[SweMcpServerContextProvider]
        REG[SweMcpToolRegistry]
        T1[IntentPlanner]
        T2[ExplanationService]
    end

    subgraph CoreData[Core Data Layer]
        CFG[SweMcpConfig]
        KB[SweKnowledgeBase]
        NODES[SweNode map]
        EDGES[SweEdge list]
        SPECS[Node specs and hydration state]
    end

    subgraph PersistentInputs[Persistent Input Layer]
        GROUND[knowledge/data/<domain>/<slug>/data.json]
        LINKED[knowledge/linked_data/*.csv]
        TEMPLATES[knowledge/template/*.md]
        CONCERN[knowledge/data/<concern>/<group>/data.json]
    end

    subgraph Contracts[Execution Contracts]
        PLAN[CodeGenPlan]
        CONTEXT[SweContext]
        EXPL[SweCodeChangeExplanation]
    end

    MCP --> CFG
    MCP --> KB
    MCP --> REG

    KB --> NODES
    KB --> EDGES
    KB --> SPECS

    GROUND --> KB
    LINKED --> KB
    TEMPLATES --> MCP
    CONCERN --> MCP

    REG --> T1
    REG --> T2
    T1 --> PLAN
    PLAN --> CONTEXT
    T2 --> EXPL
```

## 3) Sequence: Agent Execution

```mermaid
sequenceDiagram
    participant C as Client
    participant M as MCP Tools
    participant K as SweKnowledgeBase
    participant A as Concern Assets Loader
    participant L as LLM Agent

    C->>M: plan_swe_code_change(problem_description, nfr_focus)
    M->>K: load() if needed
    K-->>M: nodes and edges
    M-->>C: CodeGenPlan

    C->>M: build_swe_code_context(plan)
    M->>K: summarize_for_prompt(nfr_ids)
    M->>A: load templates and concern data
    A-->>M: template/data assets
    M-->>C: SweContext

    C->>L: generate code using SweContext
    L-->>C: modified code

    C->>M: judge_swe_code_change(swe_context, original_code, modified_code)
    M->>K: structured knowledge context + links
    M-->>C: SweCodeChangeExplanation
```

## 4) Data Objects by Stage

| Stage | Input Objects | Output Objects |
|---|---|---|
| Stage 1 Planning | problem description, optional target language, optional NFR focus, SweMcpConfig, SweKnowledgeBase | CodeGenPlan |
| Stage 2a Context Build | CodeGenPlan, SweKnowledgeBase, concern templates/data | SweContext |
| Stage 2b Judge/Explain | SweContext, original code, modified code, SweKnowledgeBase, SweMcpConfig | SweCodeChangeExplanation |

## 5) Notes on Structured Knowledge Integration

- Nodes are discovered from knowledge/data domain folders.
- Structural edges are rebuilt from ground truth entries and categories.
- Linked-data CSV relations act as semantic links and NFR/category hints when endpoints are valid in the discovered graph.
- Lazy node detail loading can be enabled via knowledge_base.lazy_load_nodes in configuration.

## 6) PlantUML Sources

For qualification, keep only a concise architecture subset:

- `docs/architecture/component-interactions.puml` (high-level system components)
- `docs/architecture/domain-uml.puml` (high-level domain concepts)
- `docs/architecture/basic-user-interaction-sequence.puml` (high-level experiment sequence)

Optional appendix diagrams (for implementation-level discussions):

- `docs/architecture/services-layer-connections.puml`
- `docs/architecture/knowledge-base-loading.puml`
