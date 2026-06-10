# Theory Run Gap Review - 2026-04-28

Created UTC: 2026-04-28

## 1. Theory Run

This is the proposed user flow in plain English:

1. Morning scripts calculate supplier readiness.
2. Restock app badge shows number of suppliers ready to review.
3. User opens Restock.
4. User clicks one ready supplier.
5. Supplier order workspace opens directly.
6. Header shows:
   - total order value
   - expected profit after shipping
   - estimated shipping charge
   - minimum/free-delivery progress bar
7. Product rows show only working information, with detail hidden behind hovers/popovers/copy controls.
8. User changes only exceptions:
   - mark out of stock
   - edit price
   - edit quantity
   - choose bulk option
   - snooze
9. User sends approved rows to order list / PO draft.
10. User copies supplier-ready text or fills supplier basket.
11. User records supplier response:
   - confirmed
   - price changed
   - partial stock
   - backorder
   - unavailable
   - canceled
12. Received stock moves into ordered/received state.
13. Send-to-Amazon queue opens only when received stock is ready.
14. Amazon shipment flow blocks transport/labels until box contents are locally saved and reconciled.

## 2. Target Click Count

For a clean ready supplier where the system got everything right:

| Step | Clicks |
| --- | ---: |
| Open Restock app | 1 |
| Open ready supplier | 1 |
| Build/send supplier order list | 1 |
| Copy order text or open supplier link | 1 |
| Mark order sent/recorded | 1 |
| Total target | 5 |

For normal exceptions:

| Exception | Target clicks |
| --- | ---: |
| Mark one product out of stock and auto-snooze 7 days | 1 |
| Change price | 1 click into field + typing |
| Change quantity | 1 click into field + typing |
| Pick bulk instead of normal | 1 |
| Open product detail/popover | 1 |
| Copy supplier code / barcode / ASIN / order text | 1 |

Design rule:

- Good rows should require zero row-level clicks.
- The user should only touch exceptions.
- Supplier completion should feel like working through an inbox notification, not filling a complicated form.

## 3. Gaps Found

### Gap 1 - Supplier readiness does not exist yet

Current O flow can build product-level recommendations, but the new workflow needs supplier-level readiness first.

Need:

- supplier readiness output
- supplier badge count
- Ready / Building / Needs Stock Check / Snoozed / All grouping
- supplier threshold progress
- reason why supplier is or is not ready

### Gap 2 - Supplier profile is too thin

Current supplier profile scaffolding exists, but the workflow needs richer supplier rules.

Need:

- minimum order value
- free delivery threshold
- delivery charge
- VAT basis for thresholds
- stock source type
- stock freshness rule
- ordering cadence
- friction score
- backorder behavior
- lead time
- supplier contact method

### Gap 3 - Shipping allocation is not built into line economics

The plan now says shipping should split by line value, but the engine must calculate this before final recommendation.

Need:

- supplier basket value
- shipping charge selected by threshold
- line share by value
- shipping cost per line
- ROI/profit after shipping
- supplier-level "not worth ordering today" decision

### Gap 4 - Supplier stock truth is not normalized

Supplier stock can come from API, CSV, email, website, basket check, or manual check.

Need:

- one normalized supplier-stock input shape
- stock confidence
- stock freshness
- unavailable rows removed from ready value
- out-of-stock action creates 7-day snooze

### Gap 5 - Bulk option needs a real option model

The repo has `bulk_review` and `bulk_long_lead_flag`, but not a full normal-vs-bulk purchase option model.

Need:

- one SKU, multiple purchase options
- normal option
- bulk option
- max 4-month cover guardrail
- bulk viable symbol
- option comparison
- double-order prevention

### Gap 6 - Stock-check workflow is not built

For suppliers with no stock data, the user needs a clean message template and snooze path.

Need:

- supplier-ready stock-check text
- copy button
- generated line format:
  - `SUPPLIER-CODE - need 12 units - please confirm stock and price`
- snooze date
- reply outcome fields
- later email send and reply parser

### Gap 7 - PO draft exists as files but not as a user-proven workspace

O has purchase order outputs, but the user has not yet used a clean supplier-order workspace.

Need:

- sample order list
- supplier grouped PO draft
- supplier order text
- supplier response capture
- hold reasons for non-ready lines

### Gap 8 - Receiving and send-to-Amazon are scaffolded, not operationally proven

The files exist, but the full chain has not been walked.

Need:

- sample receiving event
- ordered-stock state update
- send-to-Amazon queue update
- box contents draft
- box content reconciliation
- no Amazon API call until local sample proof is clean

### Gap 9 - Health/schema checks must be added with new outputs

Repo rules require every new output file to have schema checks and every new phase to have health/alert coverage.

Need:

- schema check for supplier readiness output
- schema check for supplier purchase options
- schema check for supplier stock normalized input
- O health rows for:
  - stale supplier readiness
  - missing supplier profile fields
  - invalid shipping threshold
  - bulk option over max cover
  - stock source stale
  - sample row blocked from live PO

## 4. What To Simplify

### Simplify 1 - Do not build a settings-heavy supplier screen

Supplier rules should be managed in a quiet profile view, not cluttering the ordering workspace.

Main order screen should show the outcome:

- ready
- building
- needs stock check
- snoozed
- not worth today

### Simplify 2 - Do not show all math on the row

Use:

- one supplier threshold bar
- one compact profit/ship/order value summary
- hovers for calculation details
- popovers for bulk comparison
- copy buttons for operational fields

### Simplify 3 - Do not require row approval for every normal row

Default should be:

- rows are included if system says ready
- user only edits exceptions
- final supplier-level send/approve records the decision batch

### Simplify 4 - Do not make bulk a separate product

Bulk is one option on one SKU.

This avoids:

- double ordering
- duplicate rows
- confused stock position
- fake demand split

### Simplify 5 - Keep live data switch tiny

First real pass should be 3-5 SKUs only.

Do not try to make all suppliers live at once.

## 5. Phases To Complete The Loop

### Phase A - Close Current Sample Order UI

Goal:

- finish the current Phase 2 sample Test Orders lane.

Proof:

- sample supplier rows can be submitted and reviewed without using live PO outputs.

### Phase B - Supplier Readiness Engine

Goal:

- build supplier-level readiness and app badge logic.

Outputs:

- supplier readiness table
- badge count
- Ready / Building / Needs Stock Check / Snoozed / All states

### Phase C - Supplier Profile And Shipping Rules

Goal:

- store supplier minimums, shipping, free delivery, cadence, and friction.

Outputs:

- richer supplier profile
- threshold progress
- shipping allocation by line value

### Phase D - Supplier Stock Input Layer

Goal:

- normalize supplier stock from different source types.

Outputs:

- supplier-stock snapshot
- freshness/confidence
- stock-unknown / out-of-stock behavior
- stock-check message template

### Phase E - Bulk Purchase Options

Goal:

- support normal and bulk options without duplicate products.

Outputs:

- purchase option rows
- bulk viable state
- max 4-month cover guardrail
- normal vs bulk comparison

### Phase F - Supplier Ordering Workspace

Goal:

- create the clean end-to-end supplier ordering screen.

Must include:

- supplier header summary
- threshold bar
- dense product rows
- hidden detail hovers/popovers
- copy buttons
- stock/price/qty overrides
- one supplier-level send/build action

### Phase G - PO Draft And Supplier Response

Goal:

- turn supplier decisions into a tracked PO draft and record supplier replies.

Must include:

- confirmed price
- confirmed quantity
- unavailable
- backorder
- canceled
- changed price
- expected date

### Phase H - Receiving And Ordered Stock

Goal:

- receive stock against the PO and update ordered-stock state.

Must include:

- partial receipt
- damaged/missing note later
- remaining open quantity
- backorder remains visible

### Phase I - Send-To-Amazon Dry Run

Goal:

- prove local send-to-Amazon workflow before API calls.

Must include:

- send queue
- shipment draft
- box contents
- box total reconciliation
- blocked transport until boxes are valid

### Phase J - Tiny Real SKU Sample

Goal:

- run 3-5 approved real SKUs through the local loop.

Rules:

- no sheet writes
- no Product_DB authority change
- no Amazon inbound API call
- no live PO commitment without approval

### Phase K - Controlled Live Adoption

Goal:

- let one supplier become a real operating lane.

Success:

- no duplicate orders
- no stale data prompts
- user can complete one supplier start to finish
- state survives rerun
- proof artifacts show the chain

## 6. Best Next Build Step

The best next build step is not live SKU onboarding.

Best next build step:

- finish Phase A, then build Phase B and C together enough to show the supplier inbox.

Reason:

- the supplier inbox is the control point for the whole experience.
- until supplier readiness exists, the UI will still feel like a product list rather than an app notification workflow.

## 7. Open Design Question

Decision:

- Supplier readiness should be calculated by the morning run for the official Restock app badge.
- The app should also allow a quiet refresh for the current supplier only.
- Do not add a whole-system refresh button in the main UI for v1.

Reason:

- the morning calculation keeps the app badge stable and avoids noisy recalculation
- current-supplier refresh is useful after the user edits price, marks stock out, switches normal/bulk, or changes quantity
- whole-system refresh risks turning the app into a maintenance tool instead of a clean operating screen

V1 UI wording:

- Show a small `Refresh supplier` action inside the supplier workspace.
- Do not show technical wording such as "rebuild readiness engine".
