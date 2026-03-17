# SellerOne Zone Index

## A. Title And Purpose
This is the top-level navigation map for SellerOne.

It helps you move from big zones to the right plan, roadmap, and expectation documents without needing technical detail first.

## B. How To Use This Index
- Start with the six zones to understand the full machine.
- Pick the zone that matches the work you want to do.
- Use the linked documents for detail.
- Use this file for navigation, not detailed checklist tracking.

## C. The Six Top-Level Zones
- Supplier Discovery
- Product Sourcing / Feeder
- Operations Loop
- Data / Intelligence
- Portfolio Management
- System Governance

## D. Zone-By-Zone Breakdown
### 1) Supplier Discovery
- Purpose: find new market opportunities, find suppliers, and obtain supplier price lists.
- Main type: discovery.
- Key components:
- market discovery
- Amazon-direct exclusion
- manufacturer-direct exclusion
- distributor discovery
- supplier onboarding
- price-list acquisition
- handoff to feeder
- Main linked documents:
- `project_control/SUPPLIER_DISCOVERY_PLAN.md`
- `project_control/EXPECTATIONS/supplier_discovery_expectations.md`
- `project_control/TASK_QUEUE.md`

### 2) Product Sourcing / Feeder
- Purpose: convert supplier price lists into qualified product candidates ready for buying decisions.
- Main type: decision.
- Key components:
- price list normalization
- barcode / identity validation
- viability checks
- profit / demand checks
- test-buy recommendation
- approval queue
- handoff to operations loop
- Main linked documents:
- `project_control/FEEDER_CYCLE_PLAN.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- `project_control/TASK_QUEUE.md`

### 3) Operations Loop
- Purpose: run day-to-day execution from approved decisions through stock movement to Amazon.
- Main type: execution.
- Key components:
- Restock Advisor
- Purchase Orders
- supplier order tracking
- inventory receiving
- Send To Amazon
- token-safe stock flow
- Main linked documents:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`
- `project_control/TASK_QUEUE.md`

### 4) Data / Intelligence
- Purpose: produce live data, analytics, and repricing intelligence that powers decisions and execution.
- Main type: analysis.
- Key components:
- A cycle
- B cycle
- E cycle
- H cycle
- Main linked documents:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/A_cycle_expectations.md`
- `project_control/EXPECTATIONS/B_cycle_expectations.md`
- `project_control/EXPECTATIONS/E_cycle_expectations.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`

### 5) Portfolio Management
- Purpose: manage product lifecycle outcomes across active, recoverable, and terminal states.
- Main type: mixed (decision + governance).
- Key components:
- dropped products
- discontinued products
- recoverable vs terminal outputs
- product revival / alternative sourcing pathways
- Main linked documents:
- `project_control/FEEDER_CYCLE_PLAN.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/TASK_QUEUE.md`

### 6) System Governance
- Purpose: control how progress is measured, reviewed, and kept reliable across the whole system.
- Main type: governance.
- Key components:
- roadmap
- expectations
- completion scoring
- reliability scoring
- health monitoring
- warning triage
- prompt/session workflow
- Main linked documents:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/`
- `project_control/OPERATING_SYSTEM.md`
- `project_control/PROMPT_WORKFLOW.md`
- `project_control/TASK_QUEUE.md`

## E. Relationship To Roadmap And Expectations
- `ROADMAP_SYSTEM_MAP.md` is the big-picture status map across systems.
- `SYSTEM_PROGRESS_CHART.md` is the at-a-glance live progress and reliability dashboard.
- `EXPECTATIONS/` files define what completion and reliability mean inside each system.
- This Zone Index sits above both and tells you where to go first.

## F. Suggested Next Step For Checklist Expansion
- Expand one zone at a time in separate sessions.
- Recommended order:
- Supplier Discovery -> Product Sourcing / Feeder -> Operations Loop.
- For each zone, add or refine expectation checklists before implementation tasks.

## G. Review/Update Notes
- Review this index whenever a new major system or zone is added.
- Keep it high-level and plain-English.
- If zone boundaries change, update this index first, then update roadmap and expectations links.
