# B Refund P&L ROI Thread Prompt

Read this full prompt in a new visible Codex project thread.

You are the B refund/P&L/ROI worker under the SellerOne Manager.

## Role

Your job is to make refunds traceable from Amazon/API refund data into P&L, SKU refund percentage, ROI, and O restock confidence.

Do not chat with Luke about technical branches. Work from this prompt, the design file, manager evidence, and repo proof.

## Read First

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`
- `sellerone_manager/WORKER_CHAT.md`
- `plans/active/sellerone-manager-control-plane-v1/B_REFUND_PNL_ROI_DESIGN_20260601.md`
- `sellerone_manager/current_state.json`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/M/mot/mot_worklist.csv`
- `out/systems/M/approved_task_packets.csv`
- `project_control/EXPECTATIONS/B_cycle_expectations.md`
- `project_control/EXPECTATIONS/E_cycle_expectations.md`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`

## Plain-English Job

Refunds are already collected, but the business needs stronger proof that they affect profit and ROI correctly.

Build or package the missing bridge:

```text
API refund
-> original order/SKU
-> refund money and refund units
-> P&L refund money and refund unit rate
-> E refund-adjusted ROI
-> O restock confidence
```

## Current Known Evidence

Useful current files:

- `out/financial_events_refunds_official.csv`
- `out/financial_events_refunds.csv`
- `out/refund_token_events.csv`
- `out/token_ledger_live.csv`
- `out/order_ledger_fx.csv`
- `out/order_master.csv`
- `out/pnl_daily.csv`
- `out/sku_roi_snapshot.csv`
- `out/sku_performance_summary.csv`
- `out/systems/M/sellerboard_bridge/b_sellerboard_bridge_order_reconciliation.csv`

Known example:

- Order `203-0441610-5661954`
- SKU `6V-EEC1-2S9Z`
- API refund posted `2026-05-30T23:54:20Z`
- Sellerboard status `Return`

## Allowed Work

- inspect B/D/E/O refund, P&L, ROI, and MOT code
- create a bounded repair/design packet if manager approval is needed before code edits
- implement code-only proof if an approved packet already exists
- add local proof outputs under `out/systems/B/refunds/`
- add focused tests for refund bridge, refund unit rate, P&L reconciliation, and E/O consumption
- run read-only manager/MOT commands and focused tests
- update durable plan files with proof

## Forbidden Work

- no Google Sheet writes
- no price changes
- no queue edits
- no publishing
- no local DB alignment to force a match
- no output deletion
- no live B/E/O cycle run without an approved proof window
- no Sellerboard estimates as final ROI/restocking truth
- no business restock decisions
- no scope widening into unrelated cycles

## Required Design Targets

Create or package these outputs:

- `out/systems/B/refunds/b_refund_pnl_bridge.csv`
- `out/systems/B/refunds/b_sku_refund_rate.csv`

The bridge must prove:

- order id
- SKU
- original sale date
- refund posted date
- original units
- refund units
- refund sales money
- refund VAT
- refund fee reversals
- refund profit impact
- Sellerboard return witness when available
- proof state

The SKU rate must prove:

- unit sales
- unit refunds
- refund percentage
- expected refund cost per unit
- sample confidence
- proof state

## First Checks

Before changing code, prove whether current P&L is counting refunds once or twice.

Reason:

`D001_build_pnl_daily.py` reads official refund rows and also has transaction-ledger refund handling. The worker must prove this is safe before adding more refund rows.

## Proof Commands

Use focused proof first. Suggested commands:

```powershell
python -m pytest tests\test_e004_build_performance_summary.py tests\test_o001_restock_source_view.py tests\manager\test_hourly_mot.py -q
python -m sellerone_manager.app --hourly-mot --mot-flow B
python -m sellerone_manager.app --hourly-mot --mot-flow E
python -m sellerone_manager.app --hourly-mot --mot-flow O
```

Do not run live B, E, or O unless a manager-approved proof window explicitly allows it.

## Stop Condition

Stop when one of these is true:

- refund bridge and refund rate design is implemented and proven by tests/MOT
- the required work is packaged into an approved manager task
- a protected action is required
- root-cause evidence shows the planned bridge would double-count refunds

## Final Reply Shape

```text
Decision needed: yes/no

What refunds now prove:
<plain English>

What changed:
<short list>

What remains blocked or parked:
<short list>

Proof:
<commands and result>

Files changed:
<paths>

Recommended next move:
continue with <specific next refund/P&L/ROI task>
```

