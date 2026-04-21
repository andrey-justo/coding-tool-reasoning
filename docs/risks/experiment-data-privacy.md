# Risk: Experiment Data — Public vs. Private

**Severity**: High  
**Blocks**: dataset release; reproducibility; ethics/IRB; paper submission  

---

## Why This Risk Exists

Issue bodies, PR diffs, and logs from private or enterprise repositories can
contain:
- proprietary business logic
- secrets (tokens, connection strings)
- personal data (names, emails, internal URLs)

Publishing prompts/diffs or even derived artifacts may violate repository terms
or data-protection regulations.

---

## Remediation Plan

1. **Primary corpus uses only public repositories** with permissive licenses.
2. If a private case study is required:
   - obtain IRB/ethics approval if applicable
   - anonymize identifiers and remove sensitive strings
   - store raw artifacts under access control
   - publish only aggregated metrics and redacted examples

---

## Revaluation Criteria

- **Revaluated level = Medium** once the corpus selection protocol is fixed to
  public repos and a redaction + storage policy is documented.

---

## Novelty Impact

**None** — this is a compliance/reproducibility constraint, not a novelty
constraint.
