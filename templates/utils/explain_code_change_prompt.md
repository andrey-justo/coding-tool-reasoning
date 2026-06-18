[[HEADER]]=== Problem Description ===
[[PROBLEM_DESCRIPTION]]

=== NFR Focus ===
[[NFR_FOCUS_LABEL]]

=== High-Level Plan Steps ===
[[HIGH_LEVEL_STEPS]]

=== Taxonomy Context (SWE taxonomy, not ontologies) ===
[[TAXONOMY_SUMMARY]]

=== SWE/NFR Summary (RAG-style context) ===
[[SWE_SUMMARY]]
[[SECURITY_CONTEXT_SECTION]]
[[RELATED_KNOWLEDGE_SECTION]]
=== Original Code ===
[[ORIGINAL_CODE]]

=== Modified Code ===
[[MODIFIED_CODE]]

Analyse the differences step by step, referencing the SWE taxonomy concepts when relevant (NFRs, principles, practices, smells). Then produce a concise JSON object with this exact shape and nothing before or after it:

{
  "overall_verdict": "acceptable|risky|rejected|manual-review-required",
  "rationale": "High-level explanation in one or two paragraphs...",
  "nfr_impacts": [
    {
      "nfr": "Maintainability",
      "verdict": "improved|neutral|regressed",
      "reasoning": "Short reasoning referencing taxonomy concepts..."
    }
  ],
  "risks": [
    "Short bullet-style risk description..."
  ],
  "recommended_tests": [
    "Concrete test or check the developer should run..."
  ]
}

Do NOT wrap the JSON in markdown and do NOT include commentary outside the JSON block.
