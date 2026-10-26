You are repairing syntax errors introduced while editing one source file.

Hard output contract:
1) Output exactly one fenced code block containing the FULL corrected file.
2) Do not output prose, JSON, a diff, or explanations.
3) Make the smallest correction needed to restore valid syntax.
4) Preserve the intended change and all unaffected original behavior.

Target file: {{ TARGET_PATH }}
Repair attempt: {{ ATTEMPT }}/{{ MAX_ATTEMPTS }}
=== Parser diagnostics ===
{{ DIAGNOSTICS_JSON }}

=== Original file before the attempted change ===
```
{{ ORIGINAL_CODE }}
```

=== Current invalid generated file ===
```
{{ GENERATED_CODE }}
```
