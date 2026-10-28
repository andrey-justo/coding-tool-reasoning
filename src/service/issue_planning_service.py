from __future__ import annotations

import ast
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.issue_planning import (
    GroundedImplementationPlan,
    IssueDiscussion,
    IssueUnderstanding,
)
from src.models.utility_decisions import SemanticReview
from src.service.ast_context_service import (
    AstContextService,
    AstScope,
    declaration_signature_at,
)
from src.service.localizer.ast.python_symbol_extractor import PythonSymbolExtractor
from src.service.localizer.ast.regex_symbol_extractor import RegexSymbolExtractor
from src.service.swe_knowledge_base_service import SweKnowledgeBase
from src.service.utility_llm_service import UtilityLlmService

logger = logging.getLogger(__name__)


class IssuePlanningService:
    """Ground issue understanding and edit ownership in evidence and baseline code."""

    def __init__(self, kb: SweKnowledgeBase, llm_client: MultiModelLLMClient) -> None:
        self.kb = kb
        self.llm_client = llm_client
        self._utility = UtilityLlmService(llm_client)

    def understand(self, discussion: IssueDiscussion) -> IssueUnderstanding:
        taxonomy = [
            {"nfr_id": node.id, "name": node.name, "description": node.description}
            for node in sorted(self.kb.get_all_nfrs(), key=lambda node: node.id)
        ]
        if not taxonomy:
            raise ValueError(
                "NFR discovery requires a populated knowledge-base taxonomy."
            )
        try:
            result = self._utility.complete(
                "issue_understanding",
                IssueUnderstanding,
                {"nfr_taxonomy": taxonomy, "issue_evidence": discussion.model_dump()},
            )
            known_sources = {source.source_id for source in discussion.evidence}
            claims = [
                claim
                for field in type(result.summary).model_fields
                for claim in getattr(result.summary, field)
            ]
            for claim in [*claims, *result.nfr_discovery]:
                if not set(claim.evidence_ids) <= known_sources:
                    raise ValueError(
                        "Issue understanding cites evidence that was not supplied."
                    )
            known_nfrs = {node["nfr_id"] for node in taxonomy}
            if any(item.nfr_id not in known_nfrs for item in result.nfr_discovery):
                raise ValueError(
                    "Issue understanding invented an NFR outside the knowledge base."
                )
            requirement_ids = [
                item.requirement_id for item in result.summary.requirements
            ]
            if len(set(requirement_ids)) != len(requirement_ids):
                raise ValueError("Issue summary contains duplicate requirement IDs.")
            if len({item.nfr_id for item in result.nfr_discovery}) != len(
                result.nfr_discovery
            ):
                raise ValueError(
                    "Issue understanding contains duplicate NFR endorsements."
                )
            logger.info(
                "Discovered %s evidence-backed NFRs and %s requirements",
                len(result.nfr_discovery),
                len(requirement_ids),
            )
            return result
        except Exception:
            logger.exception(
                "Evidence-backed issue understanding failed; code generation is blocked"
            )
            raise

    @staticmethod
    def repository_context(
        code_by_file: dict[str, str], max_chars: int = 24000
    ) -> dict[str, Any]:
        if not code_by_file:
            raise ValueError("Grounded planning requires baseline source files.")
        ast_service = AstContextService()
        context: dict[str, Any] = {}
        outlines: dict[str, list[AstScope]] = {}
        for path, code in sorted(code_by_file.items()):
            lines = code.splitlines()
            outline = ast_service.describe_outline(path, code, max_declarations=200)
            scopes = outline.declarations
            if not outline.available and Path(path).suffix == ".py":
                try:
                    tree = ast.parse(code)
                    scopes = [
                        AstScope(
                            node_type=type(node).__name__,
                            name=node.name,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                        )
                        for node in ast.walk(tree)
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                        )
                    ]
                except SyntaxError as error:
                    logger.warning(
                        "Cannot build Python baseline outline for %s: %s", path, error
                    )
            outlines[path] = scopes
            extractor = (
                PythonSymbolExtractor()
                if Path(path).suffix == ".py"
                else RegexSymbolExtractor()
            )
            symbols = sorted(
                {scope.name.lower() for scope in scopes if scope.name}
                | extractor.extract(Path(path), code).definitions
            )
            entry: dict[str, Any] = {
                "sha256": hashlib.sha256(code.encode()).hexdigest(),
                "line_count": max(1, len(lines)),
                "declarations": [],
                "symbols": symbols,
                "outline_available": outline.available,
                "outline_error": outline.error,
                "omitted_declarations": len(scopes),
                "source_excerpt": "",
            }
            context[path] = entry
        remaining = max_chars - len(json.dumps(context))
        if remaining < 0:
            raise ValueError(
                "Baseline symbol inventory exceeds the planning context budget."
            )
        for index, (path, entry) in enumerate(context.items()):
            allocation = remaining // (len(context) - index)
            lines = code_by_file[path].splitlines()
            for scope in outlines[path]:
                declaration = {
                    **scope.to_dict(),
                    "signature": scope.header or declaration_signature_at(lines, scope.start_line),
                }
                cost = len(json.dumps(declaration)) + 2
                if cost > allocation:
                    continue
                entry["declarations"].append(declaration)
                entry["omitted_declarations"] -= 1
                allocation -= cost
                remaining -= cost
            if not outlines[path] and allocation > 2:
                excerpt = code_by_file[path][: min(3000, allocation // 6)]
                cost = len(json.dumps(excerpt)) - 2
                entry["source_excerpt"] = excerpt
                remaining -= cost
        if len(json.dumps(context)) > max_chars:
            raise ValueError(
                "Baseline context exceeded the configured planning budget."
            )
        return context

    @staticmethod
    def validate_implementation(
        plan: GroundedImplementationPlan,
        understanding: IssueUnderstanding,
        repository_context: dict[str, Any],
        *,
        llm_client: MultiModelLLMClient | None = None,
    ) -> None:
        requirements = {
            item.requirement_id for item in understanding.summary.requirements
        }
        steps = {step.step_id: step for step in plan.implementation_plan}
        if len(steps) != len(plan.implementation_plan):
            raise ValueError("Implementation plan contains duplicate step IDs.")
        covered: set[str] = set()
        for step in plan.implementation_plan:
            if step.target_file not in repository_context:
                raise ValueError(
                    f"Implementation plan targets an ungrounded file: {step.target_file}"
                )
            entry = repository_context[step.target_file]
            if not 1 <= step.start_line <= step.end_line <= entry["line_count"]:
                raise ValueError(
                    f"Invalid baseline line range for step {step.step_id}."
                )
            if step.action == "create" and step.start_line != step.end_line:
                raise ValueError(
                    "New declarations require one insertion anchor, owned by one chunk."
                )
            if not set(step.requirement_ids) <= requirements:
                raise ValueError("Implementation plan references unknown requirements.")
            covered.update(step.requirement_ids)
            if (
                step.step_id in step.depends_on
                or not set(step.depends_on) <= steps.keys()
            ):
                raise ValueError("Implementation plan has invalid dependencies.")
        if covered != requirements:
            raise ValueError("Implementation plan leaves issue requirements uncovered.")
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("Implementation plan contains a dependency cycle.")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in steps[step_id].depends_on:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in steps:
            visit(step_id)
        review = UtilityLlmService(llm_client).complete(
            "implementation_plan_review",
            SemanticReview,
            {
                "plan": plan.model_dump(),
                "issue_understanding": understanding.model_dump(),
                "baseline_context": repository_context,
            },
        )
        if not review.approved:
            raise ValueError(
                "Implementation plan semantic review rejected: "
                + "; ".join(review.concerns)
            )
