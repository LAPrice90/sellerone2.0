# Feeder v1 PO Handoff Guidebook

## Purpose
Build an approved-only PO handoff package from feeder approval queue and decision lineage.

## Inputs
- `out/systems/F/live/feeder_approval_queue_live.csv`
- `out/systems/F/history/feeder_approval_decisions_log.csv`
- `out/systems/F/live/feeder_candidate_recommendations_live.csv` (cost/currency context)

## Outputs
- `out/systems/F/live/feeder_po_handoff_ready_live.csv`
- `out/systems/F/live/feeder_po_handoff_holds.csv`
- `out/systems/F/live/feeder_po_handoff_health.csv`

## Approval Rule
Rows enter PO handoff only when latest decision status is one of:
- `approved`
- `approved_for_test_buy`
- `approved_for_po`
- `approved_test_buy`

Everything else stays explicit in holds with reason codes.

## Shure-only proof run
```
python -m scripts.flows.F.F050_build_feeder_po_handoff --supplier-id shure_cosmetics
```

## Notes
- This stage is isolated proof. It does not claim live-loop adoption.
- If there are no approved decisions yet, ready output can be empty and that is truthful.
