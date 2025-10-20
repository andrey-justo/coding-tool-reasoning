## Prompt: Extract Reliability Design Pattern Input

Given a natural language description, extract the following information as a JSON object:

```json
{
    "selected_design_pattern": "<the identified reliability design pattern, e.g., 'Circuit Breaker'>",
    "code_examples_path": "<the folder path where code examples for this pattern are located>",
    "code_examples": [
        {
            "description": "<a brief description of what the code example demonstrates>",
            "example": "<the normalized code example>"
        }
        // ... more examples if available ...
    ],
    "location_for_unit_tests": "<the recommended folder or file path for unit tests related to this pattern>",
    "location_for_target_code": "<the recommended folder or file path for the main implementation of this pattern>"
}
```

- Only output the JSON object, with all fields filled if possible.
- If a field cannot be determined, leave it as an empty string or an empty array as appropriate.
- Do not include any explanations or extra text, only the JSON object.
