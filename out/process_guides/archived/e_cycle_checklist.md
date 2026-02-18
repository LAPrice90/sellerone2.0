# E Cycle Checklist (Execution)

## Start
1) Confirm B is stopped or idle.
2) Confirm latest Order_Master exists.
3) Confirm token_cogs_ledger exists.

## Run order
1) Build velocity
2) Build ROI snapshot
3) Build restock signals
4) Build performance summary
5) Publish to sheets

## Pass/Fail checks
- Any missing input -> FAIL, stop.
- Any SKU with stock days = 0 but velocity > 0 -> FAIL.
- Any SKU with missing COGS and non-blank ROI -> FAIL.

## Output checks
- Velocity file written and non-empty.
- ROI file written and non-empty.
- Restock file written and non-empty.
- Summary file written and non-empty.

## Health check
- Add E checks into A015 (counts + schema)
- Fail if any E output missing

## Notes
- E cycle never changes orders or tokens.
- E cycle is read-only.
