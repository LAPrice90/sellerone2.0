# Feeder v1 Approval Queue Guidebook

## Purpose
Build decision-ready feeder recommendations and a human approval queue from shared pass/fail output.

## Input
- `out/systems/F/live/feeder_shared_pass_logic_live.csv`

## Outputs
- `out/systems/F/live/feeder_candidate_recommendations_live.csv`
- `out/systems/F/live/feeder_approval_queue_live.csv`
- `out/systems/F/history/feeder_approval_decisions_log.csv`
- `out/systems/F/live/feeder_approval_health.csv`

## Decision Status Model
- `approve_test_buy`
- `reject`
- `watch`
- `manual_review`

Queue routing:
- `approve_test_buy` -> `needs_review`
- `reject` -> `needs_review`
- `watch` -> `watch`
- `manual_review` -> `manual_review`

## Decision Lineage
- `feeder_approval_decisions_log.csv` is append-only lineage.
- Builder seeds one idempotent `seed_pending_review` event per candidate.
- Human decisions should append new events, never edit existing rows.

## Health Alerts
- `feeder_approval_source_contract`
- `feeder_approval_quality`
- `feeder_approval_manual_review_pressure`
  - warn when manual-review ratio is `>= 0.25`

## Run Command
```
python -m scripts.flows.F.F040_build_feeder_candidate_approval_queue
```
