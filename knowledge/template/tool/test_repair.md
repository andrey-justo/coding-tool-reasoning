You are repairing failing tests for one source file that was modified by an automated change.

Hard output contract:
1) Output exactly one fenced code block containing the FULL corrected file.
2) Do not output prose, JSON, a diff, or explanations.
3) Make the failing tests pass by fixing the real defect, not by weakening the
   assertion, deleting the test, skipping it, or special-casing the expected
   value.
4) Preserve the intent of the original problem and every test that already passes.
5) If the failing assertion exposes missing behavior, implement that behavior.
6) Respect the declarations shown in the AST context and in the related-files
   index: use the real symbol names, types and signatures instead of inventing
   new ones.
7) If the correct fix clearly belongs to a different file than the one given,
   still return this file unchanged rather than introducing a wrong change here.

=== Problem being solved (original intent) ===
{{ PROBLEM_SUMMARY }}

Target file: {{ TARGET_PATH }}
Repair attempt: {{ ATTEMPT }}/{{ MAX_ATTEMPTS }}
Test command: {{ TEST_COMMAND }}
Test results parser: {{ FAILURES_PARSER }}

=== Failing tests ===
{{ FAILURES_JSON }}

=== AST context around the failing locations ===
Each entry lists the enclosing declarations (outermost first) and the numbered
source neighborhood of one failure.
{{ AST_CONTEXT_JSON }}

=== Related files changed in the same task (declarations only) ===
Use this index to understand which types and members exist in the other
modified files. Their content is not shown and must not be rewritten here.
{{ RELATED_FILES_JSON }}

=== Related declarations from the repository (read-only) ===
Declarations of symbols named by the failures above, resolved from files that
were not modified by this task. Use them as the authoritative source for the
exact member names and signatures the target file must implement or call. Do
not edit these files.
{{ RELATED_SYMBOLS_JSON }}

=== Test output tail ===
```
{{ TEST_OUTPUT_TAIL }}
```

=== Current content of the target file ===
```
{{ CURRENT_CODE }}
```
