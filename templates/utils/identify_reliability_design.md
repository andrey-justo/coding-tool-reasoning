## Prompt: Identify Reliability Design Patterns

You are given a description or implementation of a reliability design pattern. Your task is to identify which of the following reliability design patterns it represents, based on the available patterns in the system:

- Circuit Breaker
- Load Balancing
- NHPP (Non-Homogeneous Poisson Process)
- Rate Limiting
- Sharding/Partitioning
- Throttling

For each input, output a JSON object in the following format:
```json
{
	"original_name": "<the name or description as given>",
	"formatted_design_pattern_name": "<the canonical name of the identified design pattern, formatted in Title Case with spaces, e.g., 'Circuit Breaker'>"
}
```

If the pattern does not match any of the above, return the original name and set "formatted_design_pattern_name" to "Unknown".

Only output the JSON object, and do not include any explanations or additional text.

# Input

{{input}}