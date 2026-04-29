from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Callable, List, Optional


class PromptAssetWriterService:
    """Write prompt-related debug artifacts for SWE MCP context generation."""

    def __init__(self, now_provider: Optional[Callable[[], datetime]] = None) -> None:
        self._now_provider = now_provider or datetime.utcnow

    def persist_generated_prompt_assets(
        self,
        repo_root: str,
        output_folder: str,
        plan,
        swe_summary: str,
        templates: List[dict],
        security_extra_context: Optional[str],
        prompt_context: str,
        executed_prompts: Optional[List[dict]] = None,
    ) -> str:
        resolved_output_root = self._resolve_output_root(repo_root, output_folder)
        run_folder = self._build_run_folder(resolved_output_root, plan.problem_description)
        os.makedirs(run_folder, exist_ok=True)

        self._write_plan_json(run_folder, plan)
        self._write_text_file(os.path.join(run_folder, "swe_summary.md"), swe_summary)
        self._write_text_file(os.path.join(run_folder, "prompt_context.md"), prompt_context)

        self._write_templates_folder(run_folder, templates, executed_prompts)
        self._write_executed_prompts_file(run_folder, executed_prompts)

        return run_folder

    def _resolve_output_root(self, repo_root: str, output_folder: str) -> str:
        if os.path.isabs(output_folder):
            return output_folder
        return os.path.join(repo_root, output_folder)

    def _build_run_folder(self, output_root: str, problem_description: str) -> str:
        run_id = self._now_provider().strftime("%Y%m%dT%H%M%SZ")
        return os.path.join(output_root, f"{run_id}-{self._slugify_for_filename(problem_description)}")

    def _write_plan_json(self, run_folder: str, plan) -> None:
        plan_payload = plan.model_dump()
        with open(os.path.join(run_folder, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan_payload, f, ensure_ascii=False, indent=2)

    def _write_text_file(self, file_path: str, content: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_templates_folder(
        self,
        run_folder: str,
        templates: List[dict],
        executed_prompts: Optional[List[dict]],
    ) -> None:
        templates_to_persist = executed_prompts if executed_prompts is not None else templates
        if not templates_to_persist:
            return

        templates_folder = os.path.join(run_folder, "templates")
        os.makedirs(templates_folder, exist_ok=True)
        for index, template in enumerate(templates_to_persist, start=1):
            template_name = template.get("name") or template.get("concern_group") or f"template-{index}"
            template_file = f"{index:02d}-{self._slugify_for_filename(str(template_name))}.md"
            template_content = str(template.get("content", ""))
            self._write_text_file(os.path.join(templates_folder, template_file), template_content)

    def _write_executed_prompts_file(
        self,
        run_folder: str,
        executed_prompts: Optional[List[dict]],
    ) -> None:
        if not executed_prompts:
            return

        executed_prompts_path = os.path.join(run_folder, "executed_prompts.md")
        with open(executed_prompts_path, "w", encoding="utf-8") as f:
            f.write(f"Generated At (UTC): {self._utc_now_iso()}\n\n")
            for index, prompt in enumerate(executed_prompts, start=1):
                f.write(
                    f"[{self._utc_now_iso()}] Prompt {index}: {prompt.get('name', 'template')}\n\n"
                )
                content = str(prompt.get("content", ""))
                f.write(content)
                if not content.endswith("\n"):
                    f.write("\n")
                f.write("\n")

    def _utc_now_iso(self) -> str:
        return self._now_provider().isoformat(timespec="milliseconds") + "Z"

    @staticmethod
    def _slugify_for_filename(text: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
        if not slug:
            return "prompt"
        return slug[:48]
