You are repairing compilation errors in one source file that was modified by an automated change.

Hard output contract:
1) Output exactly one fenced code block containing the FULL corrected file.
2) Do not output prose, JSON, a diff, or explanations.
3) Fix the reported compilation errors with the smallest correct change.
4) Preserve the intent of the original problem and all unaffected behavior.
5) Never delete functionality to silence an error, and never stub a method body
   just to make it compile.
6) Respect the declarations shown in the AST context: use the real symbol names,
   types and signatures instead of inventing new ones.
7) The related declarations section is READ-ONLY context from other files in the
   repository. Never output or modify those files; implement the target file so
   that it satisfies the signatures exactly as declared there.

=== Problem being solved (original intent) ===
{{ PROBLEM_SUMMARY }}

Target file: {{ TARGET_PATH }}
Repair attempt: {{ ATTEMPT }}/{{ MAX_ATTEMPTS }}
Build command: {{ BUILD_COMMAND }}

=== Compiler diagnostics for this file ===
{{ DIAGNOSTICS_JSON }}

=== Previous diagnostic states (last five attempts) ===
Use this history to avoid repeating failed repairs and to distinguish persistent
diagnostics from newly introduced regressions.
{{ REPAIR_HISTORY_JSON }}

=== AST context around the failing lines ===
Each entry lists the enclosing declarations (outermost first) and the numbered
source neighborhood of one diagnostic.
{{ AST_CONTEXT_JSON }}

=== Semantic context for the failing positions ===
For each diagnostic this resolves the call expression at that position and the
declarations of the symbols the diagnostic names. ``origin`` tells you where a
declaration was found: ``target_file`` means it is declared in the file you are
editing (possibly outside the excerpt shown), ``repository`` means another file
declares it, and ``external_or_unresolved`` means it comes from a dependency.
Treat a resolved signature as the contract: adapt the failing expression to it,
or change the declaration deliberately, but never invent a different one.
{{ SEMANTIC_CONTEXT_JSON }}

=== Related declarations from the repository (read-only) ===
Declarations of symbols named by the diagnostics above, resolved from other
files in the repository. Use them as the authoritative source for the exact
member names and signatures the target file must implement or call. Do not edit
these files.
{{ RELATED_SYMBOLS_JSON }}

=== Build output tail ===
```
{{ BUILD_OUTPUT_TAIL }}
```

=== Current file content that fails to compile ===
```
{{ CURRENT_CODE }}
```
