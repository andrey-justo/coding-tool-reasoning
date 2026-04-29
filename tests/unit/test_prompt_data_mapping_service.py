import json

from src.service.prompt_data_mapping_service import PromptDataMappingService


def _make_service() -> PromptDataMappingService:
    return PromptDataMappingService()


# ---------------------------------------------------------------------------
# extract_prompt_data_map
# ---------------------------------------------------------------------------


def test_extract_prompt_data_map_ignores_non_data_items():
    service = _make_service()
    items = [
        {"kind": "swe_concern_template", "content": json.dumps({"key": "value"})},
    ]
    result = service.extract_prompt_data_map(items)
    assert result == {}


def test_extract_prompt_data_map_parses_flat_json_payload():
    service = _make_service()
    items = [
        {
            "kind": "swe_concern_data",
            "content": json.dumps({"title": "Circuit Breaker", "summary": "Resilience pattern"}),
        }
    ]
    result = service.extract_prompt_data_map(items)
    assert result["title"] == "Circuit Breaker"
    assert result["summary"] == "Resilience pattern"


def test_extract_prompt_data_map_skips_items_with_no_content():
    service = _make_service()
    items = [{"kind": "swe_concern_data", "content": None}]
    result = service.extract_prompt_data_map(items)
    assert result == {}


def test_extract_prompt_data_map_skips_items_with_invalid_json():
    service = _make_service()
    items = [{"kind": "swe_concern_data", "content": "not-json"}]
    result = service.extract_prompt_data_map(items)
    assert result == {}


def test_extract_prompt_data_map_merges_multiple_data_items():
    service = _make_service()
    items = [
        {"kind": "swe_concern_data", "content": json.dumps({"a": "1"})},
        {"kind": "swe_concern_data", "content": json.dumps({"b": "2"})},
    ]
    result = service.extract_prompt_data_map(items)
    assert result["a"] == "1"
    assert result["b"] == "2"


# ---------------------------------------------------------------------------
# _flatten_prompt_data – nested structures
# ---------------------------------------------------------------------------


def test_flatten_prompt_data_nested_dict_produces_dotted_keys():
    service = _make_service()
    payload = {"outer": {"inner": "value"}}
    result = service._flatten_prompt_data(payload)
    assert result["outer.inner"] == "value"


def test_flatten_prompt_data_scalar_list_joins_as_bullet_list():
    service = _make_service()
    payload = {"items": ["alpha", "beta", "gamma"]}
    result = service._flatten_prompt_data(payload)
    assert result["items"] == "- alpha\n- beta\n- gamma"


def test_flatten_prompt_data_mixed_list_serializes_as_json():
    service = _make_service()
    payload = {"mixed": [{"k": "v"}, "string"]}
    result = service._flatten_prompt_data(payload)
    assert "mixed" in result
    parsed = json.loads(result["mixed"])
    assert parsed == [{"k": "v"}, "string"]


def test_flatten_prompt_data_scalar_value_converts_to_string():
    service = _make_service()
    payload = {"count": 42}
    result = service._flatten_prompt_data(payload)
    assert result["count"] == "42"


def test_flatten_prompt_data_deeply_nested_produces_full_dotted_path():
    service = _make_service()
    payload = {"a": {"b": {"c": "deep"}}}
    result = service._flatten_prompt_data(payload)
    assert result["a.b.c"] == "deep"
