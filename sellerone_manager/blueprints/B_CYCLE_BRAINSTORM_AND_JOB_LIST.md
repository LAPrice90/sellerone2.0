# B Cycle Brainstorm And Job List

## Purpose
This file is for improving B without turning every idea into an immediate repair.

B is the daytime order and money-paperwork cycle. It pulls orders, rebuilds the order master, updates token/cost ledgers, refreshes daily P and L support, and keeps stock/parking proof current.

The manager job is to ask:
- Did B really collect the right order facts?
- Did B keep one clean owner and a fresh heartbeat?
- Did B leave enough proof for Codex to repair safely later?
- Are there better outside checks we can add before trusting the numbers?

## Current Manager Truth
- B has independent MOT proof for fresh outputs, row counts, heartbeat, lock state, ownership, maintenance marker state, and proof files.
- The old B checklist is only a clue, not the main truth.
- B is currently manager-covered, but that does not mean every possible business mismatch is impossible.
- Sellerboard bridge proof is being added as a second-ruler check for the 7-day order picture and refund/fee/ROI gaps.

Plain English:
- The manager now knows the B van moved today and has one driver.
- The next improvement is checking whether everything that should have been in the van actually arrived.

## Brainstorm Areas

### 0. Refunds, Shipping Fees, And ROI Gap
Question:
- Are refunds, shipping fees, and fee adjustments connected back to SKU-level ROI?

Why this matters:
- B feeds the ROI information used for restocking.
- If sales and stock cost are connected, but refunds and shipping/transaction fees are not connected to SKUs, ROI can look better than reality.

Current constraint:
- Direct API access is still a blocker for the clean long-term fix.
- Until API access is sorted, Sellerboard data may be the practical bridge for filling the reporting gap.

Near-term bridge:
- Use Sellerboard daily/product information, if available locally, to compare or fill refund, shipping, fee, and profit gaps at product/SKU level.
- Clearly label this as `Sellerboard bridge evidence`, not final source-of-truth API allocation.

Long-term fix:
- After API access is sorted, connect refunds, shipping fees, adjustments, and transaction fees directly into SKU/order-level B proof.
- Then ROI/restocking can use direct source facts instead of a Sellerboard bridge.

Possible proof:
- Count SKU/order rows where sales exist but refund, shipping, or fee allocation is missing.
- Compare SellerOne SKU ROI against Sellerboard SKU profit where Sellerboard data exists.
- Track rows filled by Sellerboard separately from rows proved by direct API allocation.

Possible job:
- Build a read-only gap report showing which SKU/order ROI rows are missing refunds, shipping fees, or fee adjustments.
- Add a Sellerboard bridge column/report for the same SKUs where local Sellerboard data is available.

Luke decision needed if:
- We need a manual Sellerboard export habit.
- Sellerboard and SellerOne disagree and a business rule is needed for which figure to trust temporarily.
- API access needs credentials, setup, or approval.

### 1. External Order Reconciliation
Question:
- If Amazon/Sellerboard says we sold 20 units today, does SellerOne also show 20 units?

Why this matters:
- B can be internally neat but still miss an outside order page, timing window, or late-posted order.

Possible proof:
- Compare SellerOne daily order count, unit count, and sales value against Sellerboard daily totals.
- Keep timezone and date-window rules explicit so the comparison does not create false alarms.

Possible job:
- Build a read-only B external order reconciliation report from existing local Sellerboard/SellerOne files.

Luke decision needed if:
- New Sellerboard login, download, or manual export process is required.
- We need a business tolerance rule, such as whether a small same-day timing difference is acceptable.

### 2. Missed Order Window Detection
Question:
- Are there gaps in the Amazon order pull timeline?

Why this matters:
- A script can succeed but accidentally skip a time slice.

Possible proof:
- Check latest order timestamp, previous pull timestamp, and expected pull window.
- Alert if there is an unexplained gap.

Possible job:
- Add a B MOT check for order-pull time-window continuity.

Luke decision needed if:
- Fixing the gap requires rerunning live order collection or backfilling business data.

### 3. Pending, Cancelled, And Refunded Order Handling
Question:
- Are pending, cancelled, refunded, and late-posted orders being counted in the same way everywhere?

Why this matters:
- Two systems can both be correct but count different stages of the order lifecycle.

Possible proof:
- Separate sold, pending, cancelled, refunded, and adjusted rows in a daily comparison report.

Possible job:
- Add a B order-state reconciliation view.

Luke decision needed if:
- A business rule must change for how these orders appear in operator totals.

### 4. Token And Cost Gap Detection
Question:
- Did every sold unit get a sensible cost token?

Why this matters:
- Sales can be pulled correctly while profit is wrong because cost matching failed.

Possible proof:
- Count sales rows with missing cost, placeholder cost, or token shortage reason.
- Compare token shortage rows against the order master.

Possible job:
- Add a B token coverage report that groups issues by SKU and reason.

Luke decision needed if:
- Correcting token data requires changing stock history, receipts, or local database facts.

### 5. Order Master Freshness And Row Stability
Question:
- Did the cleaned order master keep up with raw orders without dropping rows?

Why this matters:
- The order master is what later flows trust.

Possible proof:
- Compare raw order rows, order-item rows, order master rows, blank SKU rows, blank date rows, and row drops across runs.

Possible job:
- Strengthen B MOT row-stability checks and make the manager task wording plain English.

Luke decision needed if:
- Repair needs data correction instead of code/proof correction.

### 6. Sellerboard Comparison Pack
Question:
- Can we build a small daily pack that says, "SellerOne vs Sellerboard: match or explain"?

Why this matters:
- Sellerboard can be the second ruler for sales reality.

Possible proof:
- Daily totals by marketplace/date:
- SellerOne orders
- SellerOne units
- SellerOne revenue
- Sellerboard orders
- Sellerboard units
- Sellerboard revenue
- Difference and explanation bucket

Possible job:
- Find existing local Sellerboard files and build a read-only comparison draft.

Luke decision needed if:
- Sellerboard source files are missing or need a new manual export habit.

Current implementation direction:
- Use the manual Sellerboard OrderList export as the first format sample.
- Build a read-only bridge pack with a summary, order reconciliation, and SKU gap report.
- Feed only the bridge proof state into B MOT.
- Keep bridge values out of live ROI until Luke approves.

## Job List

### Proposed Manager Jobs
1. `B-JOB-001`: Find existing local Sellerboard daily sales files and map available columns. Status: implemented for Sellerboard OrderList CSV format.
2. `B-JOB-002`: Draft a read-only SellerOne vs Sellerboard daily comparison report. Status: implemented as a manager bridge report.
3. `B-JOB-003`: Add B MOT check for order-pull window continuity.
4. `B-JOB-004`: Add B MOT check for token/cost coverage by SKU.
5. `B-JOB-005`: Add B MOT check for order master row stability and blank required fields.
6. `B-JOB-006`: Build a read-only SKU ROI gap report for missing refunds, shipping fees, and fee adjustments. Status: implemented as bridge gap output.
7. `B-JOB-007`: Add a Sellerboard bridge report for refund/shipping/fee gaps while API access is blocked. Status: implemented as temporary manager evidence.
8. `B-JOB-008`: After API access is sorted, replace Sellerboard bridge fields with direct API-backed SKU/order allocation proof.

### Proposed Worker Jobs
These are not approved repair tasks yet. They need manager packaging first.

1. Build a B external reconciliation script if local Sellerboard files already exist.
2. Add a B order-state summary if the current files contain reliable status fields.
3. Improve token coverage reporting if current token proof is too hard to read.
4. Build the SKU ROI gap report without changing ROI outputs.
5. Build the Sellerboard bridge report as separate evidence, not as silent replacement data.

### Protected Items
Stop and ask Luke before:
- running or restarting B
- changing prices
- editing queues
- writing Google Sheets
- aligning or rewriting local database data
- deleting outputs
- correcting token or order data
- creating a new Sellerboard login/download flow
- treating Sellerboard bridge data as final source truth without review
- replacing direct API allocation with Sellerboard bridge data permanently
- widening beyond B

## Next Review Questions
- Do we already have local Sellerboard daily sales exports that B can compare against?
- Do those Sellerboard files include refund, shipping, fee, and profit fields by SKU/product?
- What date window should the comparison use: calendar day, Amazon settlement day, or Sellerboard dashboard day?
- What difference is acceptable before the manager raises a warning?
- Which fields can Sellerboard fill temporarily while API access is blocked?
- Once API access is sorted, which bridge fields must be retired or downgraded to cross-check only?

## Current Recommended Next Job
Continue with `B-JOB-008` after API access is sorted: replace Sellerboard bridge fields with direct API-backed SKU/order allocation proof.

This is safe because it is read-only and does not touch B runtime, Sheets, prices, queues, locks, or business data.
