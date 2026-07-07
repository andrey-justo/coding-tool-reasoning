# Metrics Roadmap (Future Implementation)

This document captures additional metrics planned for future experiment cycles.
They are intentionally out of the lean v1 core to keep statistical claims focused.

## F-1 — Halstead volume and effort

- Definition: information-theoretic complexity from distinct/total operators and operands.
- Purpose: complementary complexity signal beyond control-flow complexity.
- Minimum fields:
  - `halstead_volume_before`, `halstead_volume_after`, `halstead_volume_delta`
  - `halstead_effort_before`, `halstead_effort_after`, `halstead_effort_delta`
  - `scope`, `source_system`, `tool_version`, `timestamp`

## F-2 — DIT (Depth of Inheritance Tree)

- Definition: class depth in inheritance hierarchy.
- Purpose: OO architecture coupling/understandability signal.
- Minimum fields:
  - `dit_before`, `dit_after`, `dit_delta`
  - `scope`, `source_system`, `tool_version`, `timestamp`

## F-3 — LCOM (Lack of Cohesion in Methods)

- Definition: cohesion based on attribute sharing across methods.
- Purpose: class-cohesion proxy and SRP support signal.
- Minimum fields:
  - `lcom_before`, `lcom_after`, `lcom_delta`
  - `scope`, `source_system`, `tool_version`, `timestamp`

## F-4 — Hotspot concentration

- Definition: concentration of complexity in a small subset of files/methods.
- Purpose: distribution-of-risk signal for maintenance planning.
- Minimum fields:
  - `hotspot_index_before`, `hotspot_index_after`, `hotspot_delta`
  - concentration formula id (top-k share, Gini-like index, etc.)
  - `scope`, `source_system`, `tool_version`, `timestamp`

## F-5 — Semantic similarity deepening

- Definition: code similarity against trusted references.
- Purpose: supportive signal for behavioral/intention approximation, never a replacement for objective quality metrics.
- Minimum fields:
  - `model_id`, `precision`, `recall`, `f1`
  - `scope`, `timestamp`

## Notes

- Future metrics should be pre-registered before entering hypothesis testing.
- Core claims must remain anchored in the lean protocol primary metric.
