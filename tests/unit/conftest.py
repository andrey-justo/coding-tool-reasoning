import json
import re

import pytest

from src.service import utility_llm_service


class UtilityModelStub:
    """Offline responses for tests that exercise orchestration, not model judgment."""

    @staticmethod
    def _references(messages):
        names = []
        for message in messages:
            if "RecursiveNode" in message:
                names.append("RecursiveNode")
            names.extend(
                re.findall(r"""(?=['"]([A-Za-z_][A-Za-z0-9_]*)['"])""", message)
            )
            for quoted in re.findall(
                r"""['"\u2018\u2019\u201c\u201d`]([^'"\u2018\u2019\u201c\u201d`\n]+)['"\u2018\u2019\u201c\u201d`]""",
                message,
            ):
                names.extend(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", quoted))
        return list(
            dict.fromkeys(
                name
                for name in names
                if name not in {"object", "string", "int", "void", "bool", "global"}
            )
        )

    def chat(self, prompt):
        if prompt.startswith("Review "):
            return json.dumps(
                {
                    "approved": True,
                    "rationale": "Scripted approval for an orchestration test.",
                    "concerns": [],
                }
            )
        payload = json.loads(prompt.split("\nInput data:", 1)[1])
        if prompt.startswith("Identify declaration names"):
            return json.dumps({"symbols": self._references(payload["messages"])[:32]})
        candidates = payload["candidates"]
        if "max_candidates_per_query" in payload:
            matches = []
            for index, message in enumerate(payload["messages"]):
                refs = [
                    value.removeprefix("global::").replace("::", ".").replace("+", ".")
                    for value in re.findall(
                        r"""(?=['"]([A-Za-z_][A-Za-z0-9_:.\+]*)['"])""", message
                    )
                ]
                ids = [
                    item["candidate_id"]
                    for item in candidates
                    if any(
                        item["symbol"] == ref or item["symbol"].endswith("." + ref)
                        for ref in refs
                    )
                ]
                matches.append({"message_index": index, "candidate_ids": ids})
            return json.dumps(
                {"matches": matches, "rationale": "Scripted declaration matches."}
            )
        refs = (
            [payload["symbol"]]
            if "symbol" in payload
            else self._references(payload["messages"])
        )
        ordered = sorted(
            candidates,
            key=lambda item: (
                not any(
                    kind in item["declarations"][0]["node_type"]
                    for kind in ("class", "interface", "struct", "record", "enum")
                ),
                item["candidate_id"],
            ),
        )
        ids = []
        files = set()
        for item in ordered:
            if item["file"] in files:
                continue
            if item["declarations"][0]["name"] in refs or item["symbol"] in refs:
                ids.append(item["candidate_id"])
                files.add(item["file"])
        return json.dumps(
            {
                "candidate_ids": ids[: payload["limit"]],
                "rationale": "Scripted context selection.",
            }
        )


@pytest.fixture(autouse=True)
def offline_utility_model(monkeypatch):
    monkeypatch.setattr(utility_llm_service, "MultiModelLLMClient", UtilityModelStub)
