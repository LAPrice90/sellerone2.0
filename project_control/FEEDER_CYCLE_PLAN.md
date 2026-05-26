# Feeder Cycle Plan

## A. Title And Purpose
This document defines the feeder cycle for SellerOne.

The feeder cycle is the new-product intake and qualification system. It sits below Restock Advisor and above the main operations loop handoff point.

## B. Plain-English Summary
The feeder cycle takes supplier product lists, standardizes them, checks if products look viable, recommends test-buy quantities, and routes each candidate to a clear status.

Approved new products then enter the main loop at Purchase Orders.

Key intent:
- reduce manual bridging between disconnected tools
- keep human approval for important decisions
- ensure new products can join token-based stock, COGS, and returns tracking cleanly

Reuse-first rule:
- SellerOne should reuse proven logic from `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1` wherever that logic is still valid.
- Do not rebuild known-good pass logic from zero unless the old implementation is Google-bound or otherwise structurally wrong.
- The new design must separate supplier-specific file conversion from the shared feeder manager so new suppliers can be added without editing the main manager flow.

## C. Boundary Map
| Area | What It Owns | What It Does Not Own |
|---|---|---|
| Feeder cycle | New product intake, normalization, qualification, test-buy recommendation, approval queue, PO-ready handoff package | Existing SKU replenishment decisions and downstream execution |
| Restock Advisor | Existing active SKU reorder recommendations | New product onboarding and supplier-list parsing |
| Main loop (PO -> Receiving -> Send To Amazon) | Execution after commitment: buying, receiving, outbound to Amazon, stock-state updates | New SKU qualification and go/no-go screening |

## D. Stage-By-Stage Feeder Flow
1. Supplier list intake
- Import supplier files and source metadata.

2. List normalization
- Convert different supplier formats into one canonical candidate structure.
- Use one converter script per supplier to emit a universal layout.
- Keep supplier-specific parsing out of the shared feeder manager.

3. Product identity and barcode validation
- Validate barcode structure and capture listing match state (matched, ambiguous, unmatched).

4. Sellability and marketplace viability checks
- Apply baseline viability checks and route uncertain cases to Manual Review.

5. Profitability and demand checks
- Estimate demand and margin/ROI from available data.

6. Test-buy recommendation
- Propose test quantity and confidence/reason codes.

7. Approval queue
- Human reviews, approves, rejects, watches, drops, or discontinues candidates.

8. Handoff into Purchase Orders
- Approved candidates emit a PO-ready package and join the main loop at Purchase Orders.

## E. Like-For-Like Baseline Vs Future Intelligence
### Like-for-like baseline replacement
- Supplier-specific converter scripts that map raw supplier files into one universal layout.
- Supplier list import and normalization.
- Reuse of the old scanner's proven pass/fail logic where still valid.
- Candidate staging and manual approval workflow.
- Basic viability, demand, and profitability checklist outputs.
- Test-buy recommendation output.
- PO handoff package for approved candidates.
- Dropped/discontinued status behavior.
- Token-safe handoff prerequisites for downstream traceability.

### Extended future intelligence
- Automated brand gating and restrictions checks.
- Strong barcode-to-listing confidence scoring.
- Rank/rating/seller-count competition scoring.
- Smarter test-buy quantity logic with learning feedback.
- Alternative supplier recovery logic for dropped products.

## E.1 Reuse Baseline From Old Scanner
Existing proven source:
- `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1`

Relevant reusable shape already present there:
- supplier/file conversion pattern
- one shared screening pipeline after input standardization
- pass/fail style logic for rank, pricing, fees, ROI, and related screening
- explicit fail reasons rather than silent drops

What should be reused in principle:
- screening order and pass/fail decision shape
- reusable calculations and thresholds that are still operationally valid
- explicit failure labeling and routing style

What should not be copied blindly:
- Google Sheets control flow
- Google-specific state handling
- any hardcoded external paths, tokens, or manual browser-driven workflow that does not fit SellerOne

Required adaptation for SellerOne:
- supplier-specific converter scripts output one universal feeder supplier layout
- shared feeder manager reads only that universal layout
- feeder state and outputs live under SellerOne flow-owned paths and contracts
- old logic is migrated into shared manager modules rather than copied into supplier converters

## F. Output Statuses
- Approved for Test Buy: candidate is approved and ready for PO handoff.
- Rejected: candidate failed checks and is closed out.
- Watch: candidate is borderline and held for re-check window.
- Manual Review: candidate needs explicit human decision due to ambiguity.
- Dropped: currently non-viable, recoverable if conditions improve.
- Discontinued: terminal status, removed from active feeder/main loop.

## G. Dropped Vs Discontinued Model
### Dropped
- Recoverable state.
- Candidate can re-enter if a new supplier, cost, or market condition makes it viable.
- Re-entry path: Dropped -> Watch or Manual Review -> Approved for Test Buy.

### Discontinued
- Terminal state.
- No automatic re-entry.
- Should only be reopened by explicit admin override.

### Waste/output channel representation
- Maintain a feeder outcomes channel with:
- Recoverable waste lane: Dropped.
- Terminal waste lane: Discontinued.

## H. Main Loop Handoff Model
Approved new SKUs join the main loop at Purchase Orders.

Minimum data required before Purchase Orders entry:
- chosen_supplier
- supplier_sku
- seller_sku readiness (or reserved seller_sku)
- approved test-buy quantity
- initial unit cost basis
- currency
- decision status and decision timestamp

Minimum data required before clean token lifecycle participation:
- stable seller_sku
- lot or PO linkage key
- unit cost basis
- received quantity event linkage
- order allocation compatibility keys

## I. Token-System Relationship
Token recommendation for feeder integration:
- At PO stage: create pending lot-level token records for planned traceability.
- At receiving stage: finalize into available unit-level token records.

This prevents false available stock before receipt while preserving clean downstream COGS and returns traceability.

## J. Minimum Output Data Model
Suggested feeder output fields:
- candidate_id
- supplier_id
- supplier_name
- supplier_sku
- source_file_id
- source_row_ref
- barcode
- barcode_validation_status
- asin
- listing_match_status
- listing_match_confidence
- brand
- viability_status
- viability_reason_codes
- estimated_demand
- estimated_roi_pct
- estimated_margin_gbp
- recommended_test_qty
- approval_required_flag
- decision_status
- decision_by
- decision_at_utc
- chosen_supplier
- initial_cost_basis
- currency
- seller_sku_ready_flag
- seller_sku
- handoff_ready_flag
- handoff_batch_id
- dropped_reentry_eligible_flag
- discontinued_flag

## K. Phased Delivery Plan
### v1
- Supplier-specific converters into one universal layout.
- Shared feeder manager that reads universal-layout supplier files.
- Reused baseline pass logic migrated from the old scanner where valid.
- Manual approval queue and status routing.
- PO-ready handoff payload for approved candidates.

### v1.1
- Baseline viability and profitability/demand checklist outputs.
- Standard reason-code framework and manual-review routing.

### v1.2
- Purchase Orders integration for approved test-buy candidates.
- Token-safe handoff checks before downstream execution.

### Later
- Automated intelligence checks not clearly encoded in legacy baseline.
- Alternative supplier recovery support for dropped products.

## K.1 Recommended Early Build Order
1. supplier-specific converter framework
- one script per supplier
- output = universal feeder supplier layout

2. shared feeder manager intake
- shared manager reads only the universal layout
- no supplier-specific branching in the manager

3. pass-logic migration
- lift valid pass/fail logic from the old scanner into SellerOne feeder modules
- remove Google-bound behavior while preserving screening intent

4. candidate classification and recommendation outputs
- explicit statuses
- explicit reason codes

5. approval queue and PO-ready handoff
- durable decision lineage
- approved-only downstream handoff

## L. Review/Update Notes
- Review this document weekly and after any feeder logic change.
- Keep wording non-technical and decision-focused.
- Update order:
- boundary map
- stage flow
- status definitions
- handoff contract
- phase plan
- expectations alignment
