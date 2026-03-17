# Supplier Discovery Expectations

## Purpose
The Supplier Discovery cycle finds new market opportunities, identifies suppliers/distributors, secures supplier price lists, and hands those lists into the Product Sourcing / Feeder cycle.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Market discovery engine | Discovery run can produce candidate opportunities from market signals | Not Started | Core v1 scope |
| Keyword/category discovery | Category and keyword sources are tracked per candidate | Not Started | Baseline inspired by prototype |
| Amazon-direct exclusion | Candidates are flagged/rejected when Amazon sells directly | Not Started | Required baseline control |
| Manufacturer-direct exclusion | Candidates are flagged/rejected when manufacturer appears to sell directly | Not Started | Baseline rule set with manual override |
| Distributor discovery workflow | Supplier research queue records candidate distributors and confidence | Not Started | New design scope |
| Supplier onboarding tracking | Account/contact state is tracked through pending to approved | Not Started | New design scope |
| Price-list acquisition tracking | Supplier list receipt and artifact path/status are tracked | Not Started | Core handoff dependency |
| Handoff artifact creation | `supplier_discovery_handoff.csv` can be produced for feeder intake | Not Started | Required for feeder connection |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed discovery runs:
- Fails: discovery pipeline crash, status-routing corruption, missing handoff-required fields, or invalid artifact output.
- Warnings: partial discovery, unresolved supplier research overflow, stale account updates, or incomplete price-list metadata.
- Clean runs: discovery-to-handoff path completes with valid status outputs and no contract defects.

Before live run history exists:
- Reliability Score = `To Baseline`.

Suggested scoring baseline (post-implementation):
- Start at 100.
- Subtract 25 if any fail in window.
- Subtract 10 per warned run, up to 30.
- Subtract 20 if handoff artifact fails feeder contract validation.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- Discovery can find candidates, apply direct-seller exclusions, track supplier research/onboarding, record price-list acquisition, and emit handoff-ready artifacts for feeder.
- Stable:
- No fail in last 10 runs.
- At least 8 of last 10 runs are clean.
- Handoff artifact contract passes on all handoff-ready records.
- Ready for expansion:
- Stable across 2 review windows.
- AI-assisted discovery can be added without breaking baseline outputs.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- AI-assisted distributor discovery and ranking.
- Smarter manufacturer-direct detection confidence model.
- Automated supplier prioritization by expected margin/velocity.
- Automated outreach templates and response classification.
- Closed-loop learning from feeder/main-loop outcomes back into discovery prioritization.
