# Reliability Design Pattern Prompt Template

## Add Design Pattern Template

### Assumptions:
- Do not remove code and comments.
- If you don't understand code, return as it is.
- Do not output any explanation or chat messages.
- Don't forget to change Target Code.

### Background:
- You're an expert on implementing reliability aspects on existing code.
- Use Examples as baseline to implement the design pattern {Design Pattern Name}

### Steps to Apply:
1. Analyze the target code for reliability gaps related to {Reliability Problem}.
2. Identify where the design pattern should be applied to address {Reliability Problem}.
3. Adapt the pattern to the target language and conventions.
4. Integrate the pattern without removing existing code/comments.
5. Validate changes with unit tests focused on {Reliability Problem}.
6. Perform statistical analysis to estimate and validate reliability improvements (e.g., failure rates, mean time to failure, event distributions).

### Example 1: {Example Description}

```
{CODE EXAMPLE}
```

## Target Code: {Code to be changed}

## Unit Tests: {Code to be changed}