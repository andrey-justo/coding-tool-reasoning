from __future__ import annotations

import json
from typing import Dict, List


class PromptDataMappingService:
    """Build a flattened key-value map from concern data assets."""

    def extract_prompt_data_map(self, templates: List[dict]) -> Dict[str, str]:
        data_map: Dict[str, str] = {}
        for item in templates:
            if item.get("kind") != "swe_concern_data":
                continue

            raw_content = item.get("content")
            if not raw_content:
                continue

            try:
                payload = json.loads(str(raw_content))
            except json.JSONDecodeError:
                continue

            data_map.update(self._flatten_prompt_data(payload))

        return data_map

    def _flatten_prompt_data(self, value: object, prefix: str = "") -> Dict[str, str]:
        flat: Dict[str, str] = {}

        if isinstance(value, dict):
            for key, child in value.items():
                key_str = str(key)
                full_key = f"{prefix}.{key_str}" if prefix else key_str
                flat.update(self._flatten_prompt_data(child, full_key))
        elif isinstance(value, list):
            if all(not isinstance(item, (dict, list)) for item in value):
                if prefix:
                    flat[prefix] = "\n".join(f"- {item}" for item in value)
            elif prefix:
                flat[prefix] = json.dumps(value, ensure_ascii=False, indent=2)
        elif prefix:
            flat[prefix] = str(value)

        return flat
