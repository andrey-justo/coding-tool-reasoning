Repair the supplied source according to the LLM review and requirements.
Parser diagnostics are literal evidence, not a diagnosis or prescribed fix.

Hard output contract:
1) Output exactly one fenced code block containing the FULL corrected file.
2) Do not output prose, JSON, a diff, or explanations.
3) Address the reviewed concerns without weakening requirements or verification.
4) Preserve the intended change and all unaffected original behavior.

Target file: {{ TARGET_PATH }}
Repair attempt: {{ ATTEMPT }}/{{ MAX_ATTEMPTS }}
=== Parser diagnostics ===
{{ DIAGNOSTICS_JSON }}

=== Requirements and LLM review ===
{{ REVIEW_CONTEXT }}

=== Original file before the attempted change ===
```
{{ ORIGINAL_CODE }}
```

=== Current generated file ===
```
{{ GENERATED_CODE }}
```
