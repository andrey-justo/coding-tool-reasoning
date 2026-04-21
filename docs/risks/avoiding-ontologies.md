# Risk: Avoiding Ontologies

**Severity**: Medium  
**Blocks**: committee acceptance; related work positioning; contribution framing  
**Source**: [`docs/PROPOSAL.md`](../PROPOSAL.md) → `# WIP → Current Risks`

---

## Why This Risk Exists

Reviewers with a knowledge-representation (KR) background may interpret the
choice of CSV taxonomies over OWL/RDF ontologies as a methodological downgrade
("no formal semantics", "no inference"). This can be framed as a weakness if the
thesis implicitly claims ontology-like benefits.

---

## Remediation Plan

1. **Frame as a deliberate DSR trade-off**: emphasize adoption, integration cost,
   and deployability as primary design constraints.
2. **Make scope explicit**: taxonomy = controlled vocabulary + lightweight graph
   traversal, not logical inference.
3. **Position in Related Work**:
   - contrast ontology pipelines vs. taxonomy pipelines in terms of operational
     friction for practitioners.
   - cite evidence that lightweight artifacts are adopted more often (e.g.,
     Mäder & Egyed, 2015).

---

## Re-evaluation Criteria

- **Re-evaluated level = Low** once Related Work contains an explicit justification
  and the contribution statement no longer implies ontology-grade reasoning.
  and the contribution statement no longer implies ontology-grade reasoning.

---

## Novelty Impact

**None** — the novelty claim is about *configurable taxonomy-guided supervision*
for LLM-assisted SE, not about ontology reasoning.
