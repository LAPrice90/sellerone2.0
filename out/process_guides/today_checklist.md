# Today Checklist - Stability to Z

## Phase 1 - Freeze and rebuild
- Stop B loop
- Run B004 (full) + health check (chained)
- Pass criteria: no FAIL in health check

## Phase 2 - Fix token coverage
- Open out/health_order_master_blank_cogs_lvl1plus.csv
- For each SKU listed: run SKU-only backdate
- Run B025 + B004 + health check
- Pass criteria: blank COGS warn = 0 (or only approved exceptions)

## Phase 3 - Resume loops
- Start B loop
- Confirm Order_Master updates at end of cycle
- Pass criteria: health check stays green after 1 full cycle

## Phase 4 - Daily guardrails
- Run A (morning)
- Confirm A015 runs and prints alerts
- Pass criteria: no FAIL, investigate any WARNs

## Notes
- Always chain health check after B004.
- Do not run A and B at the same time.
