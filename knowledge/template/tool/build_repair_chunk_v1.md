Build repair chunk prompt contract, version 1.

You are repairing compilation errors in one chunk of a large source file.

Hard output contract:
1) Output exactly one fenced code block containing the COMPLETE updated chunk.
2) The block must cover the entire supplied line range, including every unchanged
   declaration and line. If no change is needed in this chunk, return the chunk
   unchanged.
3) Do not output the full file, prose, JSON, a diff, placeholders, or explanations.
4) Do not omit unchanged code, truncate the chunk, or delete functionality to
   silence an error.
5) Fix reported compilation errors with the smallest correct change.
6) Related repository declarations are READ-ONLY context and must not be output
   or modified.

=== Problem being solved (original intent) ===
{{ PROBLEM_SUMMARY }}

Target file: {{ TARGET_PATH }}
Repair attempt: {{ ATTEMPT }}/{{ MAX_ATTEMPTS }}
Build command: {{ BUILD_COMMAND }}
Chunk: {{ CHUNK_NUMBER }}/{{ TOTAL_CHUNKS }}
Required complete line range: {{ CHUNK_START_LINE }}-{{ CHUNK_END_LINE }}

=== Compiler diagnostics for this file ===
{{ DIAGNOSTICS_JSON }}

=== Previous diagnostic states (last five attempts) ===
Use this history to avoid repeating failed repairs and to distinguish persistent
diagnostics from newly introduced regressions.
{{ REPAIR_HISTORY_JSON }}

=== AST context around failing lines ===
{{ AST_CONTEXT_JSON }}

=== Semantic context for the failing positions ===
For each diagnostic this resolves the call expression at that position and the
declarations of the symbols the diagnostic names. ``origin`` tells you where a
declaration was found: ``target_file`` means it is declared in this same file,
possibly in a chunk you are not being shown, ``repository`` means another file
declares it, and ``external_or_unresolved`` means it comes from a dependency.
Treat a resolved signature as the contract: adapt the failing expression to it
instead of guessing, and do not redeclare it inside this chunk.
{{ SEMANTIC_CONTEXT_JSON }}

=== Related declarations from the repository (read-only) ===
{{ RELATED_SYMBOLS_JSON }}

=== Build output tail ===
```
{{ BUILD_OUTPUT_TAIL }}
```

=== Current complete chunk (return this entire chunk, updated or unchanged) ===
```
{{ CURRENT_CHUNK }}
```
