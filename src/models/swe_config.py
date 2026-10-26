from __future__ import annotations

import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class KnowledgeBaseConfig(BaseModel):
    """Configuration for SWE knowledge bases used by the MCP server.

    Paths are optional; when omitted, the server falls back to the default
    `knowledge/data` for node discovery and `knowledge/linked_data` for edge
    discovery under the repository root.
    """

    ground_data_dir: Optional[str] = Field(
        default=None,
        description=(
            "Optional absolute or repo-relative root for knowledge base nodes. "
            "Defaults to knowledge/data."
        ),
    )
    linked_data_dir: Optional[str] = Field(
        default=None,
        description=(
            "Optional absolute or repo-relative root for knowledge base edge CSVs. "
            "Defaults to knowledge/linked_data and is scanned recursively."
        ),
    )
    relationship_depth: int = Field(
        default=1,
        ge=1,
        description=(
            "How deep to traverse relationships between knowledge base nodes when "
            "building summaries (1 = direct neighbors only)."
        ),
    )
    lazy_load_nodes: bool = Field(
        default=False,
        description=(
            "When true, discover knowledge base nodes from knowledge/data eagerly but "
            "defer loading rich data.json payload details until a node is read."
        ),
    )


class PlanningConfig(BaseModel):
    """Configuration for Stage 1 planning behavior."""

    max_steps: int = Field(
        default=8,
        ge=1,
        description="Maximum number of highâ€‘level planning steps to keep.",
    )
    default_nfr_focus: List[str] = Field(
        default_factory=lambda: ["Maintainability", "Readability"],
        description="Fallback NFR focus when none can be inferred from the request.",
    )
    max_intent_inference_loops: int = Field(
        default=2,
        ge=0,
        description=(
            "Maximum knowledge base-expansion passes used to infer additional intent "
            "NFR candidates from already resolved NFR nodes."
        ),
    )
    infer_target_language_when_missing: bool = Field(
        default=True,
        description=(
            "When true, infer target language from the user request if "
            "target_language is not explicitly provided."
        ),
    )


class JudgingConfig(BaseModel):
    """Configuration for Stage 2 judging and explanation behavior."""

    strictness: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How strict the judge should be when accepting changes (0 = very "
            "lenient, 1 = very strict). This is exposed as guidance in prompts."
        ),
    )
    max_risks: int = Field(
        default=5,
        ge=1,
        description="Maximum number of risk bullet points to keep in explanations.",
    )


class WorkflowConfig(BaseModel):
    """Configuration for the highâ€‘level software engineering workflow.

    The stages describe the intended lifecycle from requirements to
    monitoring/diagnosis. Agents can use this ordering to organize plans
    and explanations.
    """

    stages: List[str] = Field(
        default_factory=lambda: [
            "requirements",
            "planning",
            "implementation",
            "testing",
            "documentation",
            "deployment",
            "monitoring",
            "diagnosis",
        ],
        description="Ordered software engineering workflow stages.",
    )
    cycle_enabled: bool = Field(
        default=True,
        description="Whether to treat the workflow as a continuous improvement cycle.",
    )


class ConcernAssetsConfig(BaseModel):
    """Configuration for concern-specific data and prompt templates.

    Files are loaded from:
    - knowledge/template/*.md (concern prompt templates)
    - knowledge/template/tool/*.md (tool prompt templates, not injected as concerns)
    - knowledge/data/<swe_concern>/<swe_subject>/data.json
    """

    swe_concern: str = Field(
        default="reliability",
        description="Concern name used under knowledge/data.",
    )
    swe_subject: Optional[str] = Field(
        default=None,
        description=(
            "Optional subject/pattern folder under the selected concern. "
            "When set, only this subject is loaded."
        ),
    )
    data_root_dir: Optional[str] = Field(
        default=None,
        description=(
            "Optional absolute or repo-relative root for concern data. "
            "Defaults to knowledge/data."
        ),
    )
    templates_root_dir: Optional[str] = Field(
        default=None,
        description=(
            "Optional absolute or repo-relative root for concern templates. "
            "Defaults to knowledge/template."
        ),
    )


class ToolExecutionConfig(BaseModel):
    """Runtime limits for MCP tool execution behavior."""

    max_summary_chars: int = Field(
        default=6000,
        ge=500,
        description="Maximum characters included from SWE summary in generation prompts.",
    )
    max_security_context_chars: int = Field(
        default=2000,
        ge=200,
        description="Maximum characters included from security context in generation prompts.",
    )
    max_single_shot_code_chars: int = Field(
        default=12000,
        ge=2000,
        description=(
            "If original code exceeds this size, generation switches from single-shot "
            "to chunked mode."
        ),
    )
    chunk_lines: int = Field(
        default=160,
        ge=20,
        description="Chunk size in lines when chunked generation mode is used.",
    )
    max_syntax_repair_attempts: int = Field(
        default=2,
        ge=0,
        le=3,
        description=(
            "Maximum diagnostic-guided LLM repair attempts when generated source "
            "does not produce a valid syntax tree."
        ),
    )
    max_syntax_diagnostics: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum tree-sitter syntax diagnostics included in a repair prompt.",
    )
    max_build_repair_attempts: int = Field(
        default=10,
        ge=0,
        le=25,
        description=(
            "Maximum build-diagnostic-guided LLM repair rounds when generated code "
            "parses correctly but fails to compile. Bounds the repair loop so a "
            "model that never converges cannot run indefinitely."
        ),
    )
    max_build_diagnostics: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Maximum compiler diagnostics included in a build repair prompt.",
    )
    max_build_repair_chunks: int = Field(
        default=4,
        ge=1,
        le=20,
        description=(
            "Maximum relevant chunks sent to the model per large-file build repair. "
            "Chunking reuses max_single_shot_code_chars and chunk_lines."
        ),
    )
    max_semantic_diagnostics: int = Field(
        default=6,
        ge=1,
        le=50,
        description=(
            "Maximum diagnostic positions resolved into call-site and symbol "
            "declaration context for a repair prompt."
        ),
    )
    max_escalated_repair_targets: int = Field(
        default=2,
        ge=1,
        le=10,
        description=(
            "Maximum extra files a stalled diagnostic may be routed to, ranked "
            "by how strongly its message names the file."
        ),
    )
    max_build_output_chars: int = Field(
        default=6000,
        ge=500,
        description="Maximum characters of build output tail included in a repair prompt.",
    )
    max_build_ast_locations: int = Field(
        default=5,
        ge=1,
        le=50,
        description=(
            "Maximum failing locations per file described with AST scope and source "
            "neighborhood in a build repair prompt."
        ),
    )
    max_test_repair_attempts: int = Field(
        default=10,
        ge=0,
        le=25,
        description=(
            "Maximum test-failure-guided LLM repair rounds when generated code "
            "compiles but fails its tests. Bounds the repair loop so a model that "
            "never converges cannot run indefinitely."
        ),
    )
    max_test_failures: int = Field(
        default=10,
        ge=1,
        le=200,
        description="Maximum failing tests included in a test repair prompt.",
    )
    max_test_output_chars: int = Field(
        default=6000,
        ge=500,
        description="Maximum characters of test output tail included in a repair prompt.",
    )
    max_test_ast_locations: int = Field(
        default=5,
        ge=1,
        le=50,
        description=(
            "Maximum failing locations per file described with AST scope and source "
            "neighborhood in a test repair prompt."
        ),
    )
    max_test_repair_files: int = Field(
        default=3,
        ge=1,
        le=25,
        description=(
            "Maximum files repaired per test repair round. Bounds prompt and cost "
            "growth when many generated files could explain a failure."
        ),
    )
    max_test_related_declarations: int = Field(
        default=40,
        ge=1,
        le=400,
        description=(
            "Maximum declarations listed per related file in the cross-file index "
            "of a test repair prompt."
        ),
    )
    max_related_symbols: int = Field(
        default=8,
        ge=0,
        le=50,
        description=(
            "Maximum symbols taken from verification diagnostics when resolving "
            "read-only declaration context from the repository."
        ),
    )
    max_related_symbol_files: int = Field(
        default=5,
        ge=0,
        le=25,
        description=(
            "Maximum repository files whose declarations are attached to a repair "
            "prompt as read-only cross-file context."
        ),
    )
    max_related_declarations: int = Field(
        default=12,
        ge=1,
        le=200,
        description=(
            "Maximum declarations listed per resolved repository symbol in a "
            "repair prompt."
        ),
    )


class VerificationCommandOverrideConfig(BaseModel):
    """Explicit build/test command override for one language."""

    build_command: Optional[List[str]] = Field(
        default=None,
        description=(
            "Build command tokens. Supports {repo_path}, {junit_xml} and "
            "{coverage_xml} placeholders."
        ),
    )
    test_command: Optional[List[str]] = Field(
        default=None,
        description=(
            "Test command tokens. Supports {repo_path}, {junit_xml} and "
            "{coverage_xml} placeholders."
        ),
    )

    extra_build_args: Optional[List[str]] = Field(
        default=None,
        description="Arguments appended to the discovered build command.",
    )
    extra_test_args: Optional[List[str]] = Field(
        default=None,
        description="Arguments appended to the discovered test command.",
    )


class VerificationConfig(BaseModel):
    """Configuration for the testability gate verification strategy."""

    project_type: str = Field(
        default="auto",
        description=(
            "Verification strategy selection: auto (detect from repository and "
            "changed-file language), none (skip verification), or an explicit "
            "strategy name such as python or dotnet."
        ),
    )
    language_overrides: Dict[str, VerificationCommandOverrideConfig] = Field(
        default_factory=dict,
        description=(
            "Per-language command overrides keyed by language name (e.g. python, c#)."
        ),
    )


class LocalizerConfig(BaseModel):
    """Configuration for repository issue localizer behavior."""

    enable_semantic_nlp: bool = Field(
        default=False,
        description=(
            "Enable local semantic NLP strategy (TF-IDF cosine). Keep disabled "
            "when minimizing model-related overhead is preferred."
        ),
    )


class SemanticIndexConfig(BaseModel):
    """Configuration for graph-based semantic indexing and retrieval."""

    enable_graph_memory: bool = Field(
        default=True,
        description=(
            "Enable graph-memory retrieval strategy that combines vector similarity "
            "and symbol-relationship propagation without LLM calls."
        ),
    )
    graph_memory_hops: int = Field(
        default=2,
        ge=1,
        le=4,
        description=(
            "Maximum graph-propagation hops used by graph-memory localizer "
            "to include relationship-neighbor files."
        ),
    )
    semantic_index_dir: str = Field(
        default=".semantic_index",
        description=(
            "Repository-relative directory used to persist semantic index files "
            "for graph-memory localizer loading."
        ),
    )
    persist_semantic_index: bool = Field(
        default=True,
        description=(
            "Persist semantic index snapshots to disk so subsequent runs can load "
            "the graph index into memory faster."
        ),
    )
    vector_backend: str = Field(
        default="local_tfidf",
        description=(
            "Vector backend identifier used by the graph-memory strategy. "
            "Current implementation uses local TF-IDF vectors."
        ),
    )
    graph_storage_backend: str = Field(
        default="in_memory",
        description=(
            "Graph storage backend for file relationships. Supported values: "
            "in_memory, neo4j."
        ),
    )
    enable_neo4j_beta: bool = Field(
        default=False,
        description=(
            "Opt-in switch for Neo4j graph storage (beta). When false, the "
            "localizer always uses in-memory graph storage even if Neo4j fields "
            "are provided."
        ),
    )
    neo4j_uri: Optional[str] = Field(
        default=None,
        description="Neo4j Bolt URI (e.g., bolt://localhost:7687).",
    )
    neo4j_username: Optional[str] = Field(
        default=None,
        description="Neo4j username used when graph_storage_backend is neo4j.",
    )
    neo4j_password: Optional[str] = Field(
        default=None,
        description=(
            "Neo4j password. Prefer setting neo4j_password_env_var instead of "
            "committing plain-text secrets."
        ),
    )
    neo4j_password_env_var: str = Field(
        default="NEO4J_PASSWORD",
        description="Environment variable name used to resolve Neo4j password.",
    )
    neo4j_database: str = Field(
        default="neo4j",
        description="Neo4j database name used for localizer graph storage.",
    )


class SweMcpConfig(BaseModel):
    """Topâ€‘level configuration object for the SWE MCP server and tools."""

    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    planning: PlanningConfig = Field(default_factory=PlanningConfig)
    judging: JudgingConfig = Field(default_factory=JudgingConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    concern_assets: ConcernAssetsConfig = Field(default_factory=ConcernAssetsConfig)
    execution: ToolExecutionConfig = Field(default_factory=ToolExecutionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    localizer: LocalizerConfig = Field(default_factory=LocalizerConfig)
    semantic_index: SemanticIndexConfig = Field(default_factory=SemanticIndexConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_semantic_index_keys(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        localizer = data.get("localizer")
        semantic_index = data.get("semantic_index")

        if not isinstance(localizer, dict):
            return data

        if not isinstance(semantic_index, dict):
            semantic_index = {}

        legacy_keys = {
            "enable_graph_memory",
            "graph_memory_hops",
            "semantic_index_dir",
            "persist_semantic_index",
            "vector_backend",
            "graph_storage_backend",
            "enable_neo4j_beta",
            "neo4j_uri",
            "neo4j_username",
            "neo4j_password",
            "neo4j_password_env_var",
            "neo4j_database",
        }
        moved_any = False
        for key in legacy_keys:
            if key in localizer and key not in semantic_index:
                semantic_index[key] = localizer[key]
                moved_any = True

        if moved_any:
            data = dict(data)
            data["semantic_index"] = semantic_index

        return data

    @classmethod
    def load(cls, repo_root: str) -> "SweMcpConfig":
        """Load configuration from `swe_mcp_config.yaml` if present.

        If no file is found or parsing fails, default values are returned.
        """

        config_path = os.path.join(repo_root, "swe_mcp_config.yaml")
        if not os.path.exists(config_path):
            return cls()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return cls.model_validate(raw)
        except Exception:
            # Fall back to defaults on any parsing error to keep the server robust.
            return cls()
