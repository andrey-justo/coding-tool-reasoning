from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from mcp.server.fastmcp import FastMCP

from src.experiments.issue_mcp_experiment import GitHubIssueClient, _build_parser
from src.mcp.tools.apply_plan_swe_code_change_tool import ApplyPlanSweCodeChangeTool
from src.mcp.tools.swe_mcp_tools import SweMcpToolRegistry
from src.models.code_gen_plan import CodeGenPlan
from src.models.issue_planning import GroundedImplementationPlan, IssueUnderstanding
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.models.swe_edge import SweEdge
from src.models.swe_node import SweNode
from src.service.intent_planner import IntentPlanner
from src.service.issue_discussion_service import IssueDiscussionService
from src.service.issue_planning_service import IssuePlanningService
from src.service.swe_knowledge_base_service import SweKnowledgeBase

SOURCE = (
    "public class Counter\n{\n    private int value;\n"
    "    public void Increment() { value++; value++; }\n}\n"
)


def _issue():
    return {
        "title": "Counter increments twice",
        "body": "Calling Increment once increases the count by two. Expected one increase.",
        "updated_at": "2026-01-01T12:00:00Z",
        "html_url": "https://github.com/example/project/issues/1",
    }


def _discussion():
    return IssueDiscussionService().build(_issue(), [])


def _kb():
    kb = SweKnowledgeBase(ground_data_dir="unused", linked_data_dir="unused")
    kb.nodes = {
        "NFR-R": SweNode(
            "NFR-R", "NFR", "Reliability", "Reliability", "Correct operation"
        ),
        "NFR-M": SweNode(
            "NFR-M", "NFR", "Maintainability", "Maintainability", "Ease of change"
        ),
    }
    kb.edges = [
        SweEdge("NFR-R", "supports", "NFR-M", "Reliable code supports safe changes")
    ]
    return kb


def _understanding():
    return {
        "summary": {
            "observed_behavior": [
                {"text": "The count increases twice.", "evidence_ids": ["issue"]}
            ],
            "expected_behavior": [
                {"text": "Increase once per invocation.", "evidence_ids": ["issue"]}
            ],
            "reproduction_steps": [],
            "requirements": [
                {
                    "requirement_id": "R1",
                    "text": "Increment once.",
                    "evidence_ids": ["issue"],
                    "acceptance_check": "One invocation increases value by one.",
                }
            ],
            "constraints": [],
            "non_goals": [],
            "unresolved_questions": [],
        },
        "nfr_discovery": [
            {
                "nfr_id": "NFR-R",
                "evidence_ids": ["issue"],
                "rationale": "Incorrect event counting violates correct operation.",
            }
        ],
    }


def _implementation():
    return {
        "high_level_steps": ["Correct counting and test a single invocation."],
        "implementation_plan": [
            {
                "step_id": "S1",
                "requirement_ids": ["R1"],
                "target_file": "Counter.cs",
                "symbol": "Increment",
                "action": "modify",
                "start_line": 4,
                "end_line": 4,
                "depends_on": [],
                "validation": ["Assert one invocation increments by one."],
            }
        ],
    }


def _review(*concerns):
    return {
        "approved": not concerns,
        "rationale": "Scripted declaration and requirement review.",
        "concerns": list(concerns),
    }


class _Llm:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def chat(self, prompt):
        self.prompts.append(prompt)
        return json.dumps(next(self.responses))


def test_implicit_nfr_discovery_preserves_kb_expansion_and_endorsement():
    client = _Llm([_understanding(), _implementation(), _review()])
    result = IntentPlanner(kb=_kb(), llm_client=client, config=SweMcpConfig()).plan(
        problem_description=IssueDiscussionService.render(_discussion()),
        issue_discussion=_discussion(),
        baseline_code_by_file={"Counter.cs": SOURCE},
    )
    assert "Reliability" not in _issue()["body"]
    assert result.nfr_discovery_source == "issue_evidence"
    assert [item.nfr_id for item in result.nfr_discovery] == ["NFR-R"]
    assert set(result.resolved_nfr_ids) == {"NFR-R", "NFR-M"}
    assert set(result.nfr_focus) == {"Reliability", "Maintainability"}
    assert "SWE knowledge-base endorsement context" in result.llm_prompt
    endorsement = result.llm_prompt
    assert "Correct operation" in endorsement and "Ease of change" in endorsement
    assert "Reliable code supports safe changes" in endorsement
    assert result.implementation_plan[0].symbol == "Increment"
    assert len(client.prompts) == 3
    assert "Review the semantic quality" in client.prompts[2]
    assert "no preset NFR focus" in client.prompts[0]


@pytest.mark.asyncio
async def test_mcp_schema_and_serialization_preserve_grounded_planning():
    class Planner(IntentPlanner):
        def __init__(self, kb, config):
            super().__init__(
                kb, _Llm([_understanding(), _implementation(), _review()]), config
            )

    server = FastMCP("grounded-planning-test")
    registry = SweMcpToolRegistry(
        lambda: SimpleNamespace(kb=_kb(), config=SweMcpConfig()),
        planner_cls=Planner,
    )
    registry.register_on_mcp(server)
    tools = await server.list_tools()
    schema = next(
        tool.inputSchema for tool in tools if tool.name == "plan_swe_code_change"
    )
    assert {"issue_discussion", "baseline_code_by_file"} <= schema["properties"].keys()
    result = await server.call_tool(
        "plan_swe_code_change",
        {
            "problem_description": "Fix counting.",
            "target_file_hints": ["Counter.cs"],
            "issue_discussion": _discussion().model_dump(),
            "baseline_code_by_file": {"Counter.cs": SOURCE},
        },
    )
    content = result[0] if isinstance(result, tuple) else result
    plan = json.loads(content[0].text)
    assert plan["nfr_discovery_source"] == "issue_evidence"
    assert set(plan["related_entities"]) == {"NFR-R", "NFR-M"}
    assert plan["implementation_plan"][0]["symbol"] == "Increment"
    assert plan["issue_summary"]["requirements"][0]["requirement_id"] == "R1"


@pytest.mark.parametrize(
    "invalid", ["citation", "nfr", "duplicate_requirement", "duplicate_nfr"]
)
def test_understanding_rejects_untraceable_or_invented_endorsements(invalid):
    payload = _understanding()
    if invalid == "citation":
        payload["summary"]["requirements"][0]["evidence_ids"] = ["missing"]
    elif invalid == "nfr":
        payload["nfr_discovery"][0]["nfr_id"] = "invented"
    elif invalid == "duplicate_requirement":
        payload["summary"]["requirements"] *= 2
    else:
        payload["nfr_discovery"] *= 2
    with pytest.raises(ValueError):
        IssuePlanningService(_kb(), _Llm([payload])).understand(_discussion())


def test_empty_taxonomy_does_not_silently_substitute_default_nfrs():
    kb = _kb()
    kb.nodes = {}
    with pytest.raises(ValueError, match="populated"):
        IssuePlanningService(kb, _Llm([])).understand(_discussion())


def test_experiment_default_does_not_prescribe_nfr_focus():
    args = _build_parser().parse_args(
        [
            "--issue-url",
            "https://github.com/example/project/issues/1",
            "--repo-path",
            ".",
        ]
    )
    assert args.nfr_focus == ""
    assert args.max_issue_comments == 200


def test_manual_nfr_override_is_explicit_and_reported(caplog):
    kb = _kb()
    kb.edges = []
    result = IntentPlanner(
        kb, llm_client=_Llm([_understanding(), _implementation(), _review()])
    ).plan(
        "Fix counting.",
        nfr_focus=["Maintainability"],
        issue_discussion=_discussion(),
        baseline_code_by_file={"Counter.cs": SOURCE},
    )
    assert result.nfr_discovery_source == "explicit_override"
    assert result.resolved_nfr_ids == ["NFR-M"]
    assert result.nfr_discovery[0].nfr_id == "NFR-R"
    assert "Explicit NFR override" in caplog.text


def test_grounded_plan_must_cover_every_evidence_backed_requirement():
    understanding = _understanding()
    understanding["summary"]["requirements"].append(
        {
            **understanding["summary"]["requirements"][0],
            "requirement_id": "R2",
        }
    )
    with pytest.raises(ValueError, match="uncovered"):
        IssuePlanningService.validate_implementation(
            GroundedImplementationPlan.model_validate(_implementation()),
            IssueUnderstanding.model_validate(understanding),
            IssuePlanningService.repository_context({"Counter.cs": SOURCE}),
        )


@pytest.mark.parametrize(
    "invalid",
    [
        "duplicate_step",
        "duplicate_owner",
        "unknown_file",
        "range",
        "create_existing",
        "unknown_symbol",
        "unknown_requirement",
        "dependency",
        "cycle",
        "partial_declaration",
        "create_multiple_anchors",
    ],
)
def test_grounded_plan_rejects_inconsistent_ownership_and_dependencies(invalid):
    payload = _implementation()
    step = payload["implementation_plan"][0]
    if invalid == "duplicate_step":
        payload["implementation_plan"].append(dict(step))
    elif invalid == "duplicate_owner":
        payload["implementation_plan"].append({**step, "step_id": "S2"})
    elif invalid == "unknown_file":
        step["target_file"] = "Unseen.cs"
    elif invalid == "range":
        step["end_line"] = 100
    elif invalid == "create_existing":
        step["action"] = "create"
    elif invalid == "unknown_symbol":
        step["symbol"] = "Missing"
    elif invalid == "unknown_requirement":
        step["requirement_ids"] = ["unknown"]
    elif invalid == "dependency":
        step["depends_on"] = ["absent"]
    elif invalid == "cycle":
        step["depends_on"] = ["S2"]
        payload["implementation_plan"].append(
            {
                **step,
                "step_id": "S2",
                "symbol": "Counter",
                "start_line": 1,
                "end_line": 5,
                "depends_on": ["S1"],
            }
        )
    elif invalid == "partial_declaration":
        step.update(symbol="Counter", start_line=2, end_line=3)
    else:
        step.update(symbol="NewHelper", action="create", start_line=3, end_line=4)
    with pytest.raises(ValueError):
        IssuePlanningService.validate_implementation(
            GroundedImplementationPlan.model_validate(payload),
            IssueUnderstanding.model_validate(_understanding()),
            IssuePlanningService.repository_context({"Counter.cs": SOURCE}),
            llm_client=_Llm([_review(f"Invalid semantic ownership: {invalid}")]),
        )


def test_repository_context_is_bounded_and_supports_python_declarations():
    source = "class Counter:\n    def increment(self):\n        return 1\n"
    context = IssuePlanningService.repository_context(
        {"counter.py": source}, max_chars=1500
    )
    assert len(json.dumps(context)) <= 1500
    assert any(
        item["name"] == "increment" for item in context["counter.py"]["declarations"]
    )
    with pytest.raises(ValueError, match="budget"):
        IssuePlanningService.repository_context({"counter.py": source}, max_chars=1)


def test_semantic_review_can_distinguish_same_named_overloads():
    payload = _implementation()
    payload["implementation_plan"].append(
        {
            **payload["implementation_plan"][0],
            "step_id": "S2",
            "start_line": 5,
            "end_line": 5,
        }
    )
    source = SOURCE.replace(
        "}\n}\n", "}\n    public void Increment(int count) { value += count; }\n}\n"
    )
    client = _Llm([_review()])
    IssuePlanningService.validate_implementation(
        GroundedImplementationPlan.model_validate(payload),
        IssueUnderstanding.model_validate(_understanding()),
        IssuePlanningService.repository_context({"Counter.cs": source}),
        llm_client=client,
    )
    assert len(client.prompts) == 1
    assert "Increment(int count)" in client.prompts[0]


def test_grounded_plan_failure_is_not_replaced_by_generic_success_steps():
    invalid = _implementation()
    invalid["implementation_plan"][0]["action"] = "create"
    with pytest.raises(ValueError, match="existing symbol"):
        IntentPlanner(
            _kb(),
            llm_client=_Llm(
                [
                    _understanding(),
                    invalid,
                    _review("Cannot create the existing symbol."),
                    invalid,
                    _review("Cannot create the existing symbol."),
                ]
            ),
        ).plan(
            "Fix counting.",
            issue_discussion=_discussion(),
            baseline_code_by_file={"Counter.cs": SOURCE},
        )


def test_invalid_ownership_gets_one_correction_without_rediscovering_nfrs():
    invalid = _implementation()
    invalid["implementation_plan"].append(
        {
            **invalid["implementation_plan"][0],
            "step_id": "S2",
        }
    )
    client = _Llm(
        [
            _understanding(),
            invalid,
            _review("Multiple plan steps own the same declaration"),
            _implementation(),
            _review(),
        ]
    )
    result = IntentPlanner(_kb(), llm_client=client).plan(
        "Fix counting.",
        issue_discussion=_discussion(),
        baseline_code_by_file={"Counter.cs": SOURCE},
    )
    assert len(client.prompts) == 5
    assert "Multiple plan steps own the same declaration" in client.prompts[3]
    assert len(result.implementation_plan) == 1
    assert result.nfr_discovery_source == "issue_evidence"


def test_comments_are_paginated_to_the_total_budget(monkeypatch):
    client = GitHubIssueClient()
    pages = []

    def get(path, params):
        pages.append(params)
        return [{"id": len(pages) * 100 + index} for index in range(100)]

    monkeypatch.setattr(client, "_get", get)
    assert len(client.fetch_issue_comments("example", "repo", 1, per_page=205)) == 205
    assert [page["page"] for page in pages] == [1, 2, 3]
    assert client.fetch_issue_comments("example", "repo", 1, per_page=0) == []
    with pytest.raises(ValueError):
        client.fetch_issue_comments("example", "repo", 1, per_page=-1)
    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: {})
    with pytest.raises(ValueError, match="list of objects"):
        client.fetch_issue_comments("example", "repo", 1)


def test_discussion_ranks_relevant_late_comments_and_preserves_complete_code():
    comments = [
        {"id": index, "body": "Thanks!", "user": {"login": "reader"}}
        for index in range(8)
    ] + [
        {
            "id": 99,
            "body": "Reproduction: Counter increments twice.\n\n```csharp\n"
            + "x++;\n" * 150
            + "```\n",
            "user": {"login": "maintainer"},
            "author_association": "MEMBER",
            "html_url": "https://example/comment/99",
        }
    ]
    result = IssueDiscussionService().build(_issue(), comments, max_sources=2)
    assert [source.source_id for source in result.evidence] == ["issue", "comment:99"]
    assert len(result.evidence[1].body) > 500
    assert result.evidence[1].body.count("```") == 2
    assert result.evidence[1].url == "https://example/comment/99"
    assert result.omitted_comments == 8
    assert "Top comments" not in IssueDiscussionService.render(result)


def test_discussion_budget_omissions_and_fingerprint_are_explicit():
    issue = _issue()
    issue["body"] = "Expected one increment.\n\n```csharp\n" + "x" * 2000 + "\n```\n"
    service = IssueDiscussionService()
    result = service.build(issue, [], max_chars=1000)
    assert result.omitted_blocks == 1
    assert "```" not in result.evidence[0].body
    assert sum(len(source.body) for source in result.evidence) <= 1000
    assert (
        result.notes
        and result.fingerprint == service.build(issue, [], max_chars=1000).fingerprint
    )
    issue["updated_at"] = "2026-01-02T12:00:00Z"
    assert result.fingerprint != service.build(issue, [], max_chars=1000).fingerprint


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_discussion_preserves_complete_fences_and_omits_incomplete_ones(fence):
    issue = _issue()
    issue["body"] = (
        f"Expected behavior.\n\n{fence}csharp\nx++;\n{fence}\n\n{fence}\nunfinished"
    )
    result = IssueDiscussionService().build(issue, [])
    assert f"{fence}csharp\nx++;\n{fence}" in result.evidence[0].body
    assert "unfinished" not in result.evidence[0].body
    assert result.omitted_blocks == 1


def test_title_only_issue_remains_attributed_evidence():
    issue = _issue()
    issue["body"] = None
    discussion = IssueDiscussionService().build(issue, [])
    assert discussion.evidence[0].source_id == "issue"
    assert discussion.evidence[0].body == "Title: Counter increments twice\n"


def test_historical_cutoff_rejects_late_issue_edits_and_excludes_late_comments():
    service = IssueDiscussionService()
    with pytest.raises(ValueError, match="historical snapshot"):
        service.build(_issue(), [], cutoff="2025-12-01T00:00:00Z")
    with pytest.raises(ValueError, match="timezone"):
        service.build(_issue(), [], cutoff="2026-01-01T00:00:00")
    result = service.build(
        _issue(),
        [
            {
                "id": 1,
                "body": "Later implementation details.",
                "updated_at": "2026-01-03T00:00:00Z",
            }
        ],
        cutoff="2026-01-02T00:00:00Z",
    )
    assert len(result.evidence) == 1
    assert result.omitted_comments == 1


def _registry(llm_cls):
    config = SweMcpConfig()
    config.execution.max_single_shot_code_chars = 2000
    config.execution.chunk_lines = 20
    config.execution.max_generation_concurrency = 3
    return SimpleNamespace(
        _llm_client_cls=llm_cls,
        _create_swe_server_context=lambda: SimpleNamespace(config=config),
        _logger=logging.getLogger(__name__),
    )


def test_generation_requests_only_the_chunk_owning_the_planned_edit():
    source = "\n".join(
        ["public class Counter", "{"]
        + ["// " + "x" * 100] * 58
        + ["public void Increment() { value++; }"]
        + ["// unchanged"] * 60
        + ["}"]
    )
    payload = _implementation()
    payload["implementation_plan"][0].update(start_line=61, end_line=61)

    class Llm:
        prompts = []

        def chat(self, prompt, **kwargs):
            self.prompts.append(prompt)
            chunk = prompt.split("=== Current chunk code ===\n```\n", 1)[1].rsplit(
                "\n```", 1
            )[0]
            return "```csharp\n" + chunk.replace("value++;", "value += 1;") + "\n```"

        def chat_batch(self, prompts, **kwargs):
            return [self.chat(prompt) for prompt in prompts]

    plan = CodeGenPlan(
        problem_description="Increment once.",
        implementation_plan=payload["implementation_plan"],
        baseline_context=IssuePlanningService.repository_context(
            {"Counter.cs": source}
        ),
        issue_summary=_understanding()["summary"],
        nfr_discovery=_understanding()["nfr_discovery"],
        nfr_discovery_source="issue_evidence",
        related_entities=["NFR-R", "NFR-M"],
    )
    result = ApplyPlanSweCodeChangeTool(_registry(Llm)).execute(
        SweContext(plan=plan, swe_summary="NFR endorsement"),
        source,
        target_file="Counter.cs",
    )
    assert len(Llm.prompts) == 1
    assert "Chunk: 4/7 (lines 61-80)" in Llm.prompts[0]
    assert "value += 1;" in result["generated_code"]
    assert "NFR endorsement" in Llm.prompts[0]
    assert result["compact_context"]["nfr_discovery"][0]["nfr_id"] == "NFR-R"
    assert result["compact_context"]["endorsed_entities"] == ["NFR-R", "NFR-M"]
    assert result["compact_context"]["nfr_discovery_source"] == "issue_evidence"


def test_unassigned_files_are_preserved_without_starting_a_model():
    class NoLlm:
        def __init__(self):
            raise AssertionError("Unassigned file must not start a model.")

    plan = CodeGenPlan(
        problem_description="Increment once.",
        implementation_plan=_implementation()["implementation_plan"],
        baseline_context=IssuePlanningService.repository_context(
            {
                "Counter.cs": SOURCE,
                "Other.cs": "class Other {}",
            }
        ),
    )
    tool = ApplyPlanSweCodeChangeTool(_registry(NoLlm))
    result = tool.execute(
        SweContext(plan=plan, swe_summary="kb"), "class Other {}", "Other.cs"
    )
    assert result["generated_code"] == "class Other {}"
    assert result["apply_outcome"] == "unchanged_plan_scope"
    assert result["used_fallback_to_original"] is False
    with pytest.raises(ValueError, match="baseline"):
        tool.execute(
            SweContext(plan=plan, swe_summary="kb"), "changed source", "Other.cs"
        )
