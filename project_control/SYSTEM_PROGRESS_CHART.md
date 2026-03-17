# SellerOne System Progress Chart

## A. Title And Purpose
This dashboard is the plain-language view of current SellerOne progress and reliability by major area.

Canonical generated values are in `project_control/SYSTEM_PROGRESS.json`.

## B. How To Read The Dashboard
- Completion Score = how much of an area currently exists.
- Reliability Score = how stable that area runs based on evidence.
- Read status and main focus first.
- Use notes for context where reliability is still being baselined.
- If any value differs from `SYSTEM_PROGRESS.json`, treat `SYSTEM_PROGRESS.json` as authoritative.

## C. Progress Colour Legend
- Red: 0-30 percent completion
- Orange: 31-60 percent completion
- Yellow: 61-80 percent completion
- Green: 81-100 percent completion
- Blue-grey: reliability is `To Baseline`

## D. One-Page Summary Table
| Area | Completion Score | Reliability Score | Current Status | Main Focus | Notes |
|---|---:|---|---|---|---|
| Supplier Discovery | 0 | To Baseline | Planned | Define v1 discovery to price-list handoff path | Planning and expectation scaffolding exist; SellerOne runtime implementation is not started. |
| Product Sourcing / Feeder | 0 | To Baseline | Planned | Build intake normalization and approval queue baseline | Feeder design exists in control docs; runtime implementation is not started. |
| Operations Loop | 0 | To Baseline | Planned | Stand up Restock -> PO -> Receiving -> Send flow | Loop architecture is mapped, but connected runtime delivery is not started. |
| Data / Intelligence | 48 | Mixed | In Progress | Stabilise H while preserving A/B/E cadence quality | A/B/E are operational; H is active but stability-gated. |
| Portfolio Management | 0 | To Baseline | Planned | Define and enforce dropped vs discontinued lifecycle flow | Lifecycle intent is defined in plans; operational enforcement remains to be built. |
| System Governance | 75 | Provisional (75) | In Progress | Keep roadmap, expectations, progress updates, and warning triage aligned | Governance docs and controls are active; reliability remains provisional while health warnings persist. |

## E. Mermaid Progress Chart
```mermaid
flowchart LR
  SD[Supplier Discovery\nC:0 | R:To Baseline]
  PF[Product Sourcing / Feeder\nC:0 | R:To Baseline]
  OP[Operations Loop\nC:0 | R:To Baseline]
  DI[Data / Intelligence\nC:48 | R:Mixed]
  PM[Portfolio Management\nC:0 | R:To Baseline]
  SG[System Governance\nC:75 | R:75 Provisional]

  SD --> PF --> OP
  DI -.powers decisions and execution.- OP
  OP --> DI
  PF --> PM
  OP --> PM
  SG -.oversight and scoring.- SD
  SG -.oversight and scoring.- PF
  SG -.oversight and scoring.- OP
  SG -.oversight and scoring.- DI
  SG -.oversight and scoring.- PM

  classDef red fill:#f8d7da,stroke:#842029,color:#000;
  classDef orange fill:#ffe5b4,stroke:#a35a00,color:#000;
  classDef yellow fill:#fff3cd,stroke:#8a6d00,color:#000;
  classDef green fill:#d1e7dd,stroke:#0f5132,color:#000;

  class SD red;
  class PF red;
  class OP red;
  class DI orange;
  class PM red;
  class SG yellow;
```

## F. Zone Progress Snapshot
- Supplier Discovery: Planned discovery and supplier-enablement lane; outputs supplier price lists for feeder input.
- Product Sourcing / Feeder: Planned conversion lane from supplier lists to approved product candidates.
- Operations Loop: Mapped execution loop; not yet delivered as one stable connected runtime.
- Data / Intelligence: Most advanced live capability; A/B/E active, H active but needs stabilisation.
- Portfolio Management: Lifecycle concepts defined, full operational control path still incomplete.
- System Governance: Strong documentation and control layer in place; continue disciplined updates.

## G. Update Rules
- Update `TASK_LIBRARY.json` first for task/status meaning changes.
- Regenerate `SYSTEM_PROGRESS.json` and `SYSTEM_CONTROL_TOWER.html` from the generator.
- Then update this chart so wording matches generated values exactly.
- Keep scores conservative and evidence-based.

## H. Review Notes
- Review weekly and after major implementation milestones.
- Keep this file lightweight and readable.
- Link detail work back to:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/ZONE_INDEX.md`
- `project_control/EXPECTATIONS/`
- `project_control/SYSTEM_PROGRESS.json`
