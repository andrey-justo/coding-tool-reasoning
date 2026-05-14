from __future__ import annotations

import os
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class TaxonomyConfig(BaseModel):
    """Configuration for SWE taxonomies used by the MCP server.

    Paths are optional; when omitted, the server falls back to the default
    `taxonomies/ground_data` and `taxonomies/linked_data` folders under the
    repository root.
    """

    ground_data_dir: Optional[str] = Field(
        default=None,
        description="Optional absolute or repo‑relative path for ground taxonomy CSVs.",
    )
    linked_data_dir: Optional[str] = Field(
        default=None,
        description="Optional absolute or repo‑relative path for linked taxonomy CSVs.",
    )
    relationship_depth: int = Field(
        default=1,
        ge=1,
        description=(
            "How deep to traverse relationships between taxonomy nodes when "
            "building summaries (1 = direct neighbors only)."
        ),
    )


class PlanningConfig(BaseModel):
    """Configuration for Stage 1 planning behavior."""

    max_steps: int = Field(
        default=8,
        ge=1,
        description="Maximum number of high‑level planning steps to keep.",
    )
    default_nfr_focus: List[str] = Field(
        default_factory=lambda: ["Maintainability", "Readability"],
        description="Fallback NFR focus when none can be inferred from the request.",
    )
    max_intent_inference_loops: int = Field(
        default=2,
        ge=0,
        description=(
            "Maximum taxonomy-expansion passes used to infer additional intent "
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
    """Configuration for the high‑level software engineering workflow.

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
    - templates/data/<swe_concern>/*.md
    - templates/data/<swe_concern>/<swe_subject>/(base_design.json|test_design.json)
    - knowledge/data/<swe_concern>/<swe_subject>/data.json
    """

    swe_concern: str = Field(
        default="reliability",
        description="Concern name used under knowledge/data and templates/data.",
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
            "Defaults to templates/data."
        ),
    )
    enable_related_subject_discovery: bool = Field(
        default=False,
        description="When True, automatically discover and attach related subjects.",
    )
    max_related_subjects: int = Field(
        default=3,
        description="Maximum number of related subjects to attach when discovery is enabled.",
    )


class SweMcpConfig(BaseModel):
    """Top‑level configuration object for the SWE MCP server and tools."""

    taxonomy: TaxonomyConfig = Field(default_factory=TaxonomyConfig)
    planning: PlanningConfig = Field(default_factory=PlanningConfig)
    judging: JudgingConfig = Field(default_factory=JudgingConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    concern_assets: ConcernAssetsConfig = Field(default_factory=ConcernAssetsConfig)

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
