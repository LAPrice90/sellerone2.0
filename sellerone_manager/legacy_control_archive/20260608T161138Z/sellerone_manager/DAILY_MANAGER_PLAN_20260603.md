# Daily Manager Plan - 2026-06-03

Status: Luke working manually with cycle managers.

## Today Focus

Plain English:

Luke is working on two lanes today:

- B cycle: refunds and fees accuracy, moving the proof toward API-backed truth.
- O cycle: wider restocking/system design work, to analyse and tidy later.

## B Lane

Goal:

- Prove refunds, fees, shipping, and ROI using API-backed evidence where possible.
- Keep Sellerboard as outside comparison evidence, not live ROI truth.
- Avoid double-counting refunds.
- Keep historical/backdated corrections as proof work first, not live output rewriting.

Watch-outs:

- Do not run B live from the manager.
- Do not restart B.
- Do not clear locks or maintenance markers.
- Do not write Sheets.
- Do not align local DB facts.
- Do not backfill or promote recovered orders without protected approval.
- Do not use Sellerboard bridge values as live ROI or restocking truth.

## O Lane

Goal:

- Keep shaping the restocking system and user decision flow.
- Capture what Luke is learning today.
- Analyse later rather than forcing the system to decide automatically too early.
- Use the UI audit to stop O/UI work from becoming another messy pile of screens.

Watch-outs:

- Urgent restocking remains manual.
- O must not create purchase orders automatically.
- O must not approve uncertain supplier rows automatically.
- O must not change prices, queues, Sheets, or local DB facts.
- O expected profit still needs refund drag, inbound/FBA-send cost, and confidence labels before automatic restock decisions are safe.
- Current UI is not the trusted restocking surface yet. Build the operator shell, Today page, and manual restocking workspace before trusting it for ordering.

## Manager Position

The manager should stay quiet unless:

- B refund/fee proof needs a protected historical correction.
- F Seller Central login/code-forwarding is needed for live proof.
- O reaches a real business decision rather than a technical proof question.
- A new fail appears or an existing fail materially worsens.

## Next Manager Step

Continue tracking B refund/fee API proof and O restocking/system design as today's active lanes. For UI work, continue with the operator shell from `sellerone_manager/UI_AUDIT_20260603.md`, then the Today page, then the manual restocking workspace.
