# Supplier Discovery Plan

## A. Title And Purpose
This document defines the Supplier Discovery cycle for SellerOne.

Its purpose is to discover new market opportunities, find viable suppliers, secure supplier price lists, and hand those lists into the Product Sourcing / Feeder cycle.

## B. Plain-English Summary
Supplier Discovery sits above the feeder cycle.

It does not decide final buy quantities or run purchase execution. Its core output is supplier price lists plus clean handoff context.

Flow intent:
- discover products and brands worth exploring
- filter out bad-fit opportunities early
- find and onboard suppliers/distributors
- acquire usable price lists
- pass those lists into the feeder cycle, where they become product candidates

## C. Boundary Map (Supplier Discovery vs Feeder vs Operations Loop)
| Area | What It Owns | What It Does Not Own |
|---|---|---|
| Supplier Discovery | Market discovery, direct-seller exclusions, supplier research, onboarding tracking, price-list acquisition, handoff artifact creation | Product-level buy/no-buy decisioning and order execution |
| Product Sourcing / Feeder | List normalization, candidate qualification, profitability/viability checks, test-buy recommendation, approval queue, PO handoff | Upstream supplier hunting and account onboarding |
| Operations Loop | Purchase Orders, Inventory Receiving / Ordered Stock Tracking, Send To Amazon | Upstream discovery and supplier account work |

## D. Stage-By-Stage Discovery Flow
1. Market product discovery
- Discover opportunity candidates using keyword/category search and catalog signals.

2. Candidate filtering
- Remove low-signal or invalid candidates before deeper supplier work.

3. Amazon-direct exclusion
- Mark or reject candidates where Amazon sells directly.

4. Manufacturer-direct exclusion
- Mark or reject candidates where manufacturer/direct-brand selling is detected.

5. Brand and opportunity identification
- Group surviving products into brand/opportunity clusters.

6. Distributor discovery
- Research likely distributors for target brands/products.

7. Supplier qualification and onboarding
- Track contact, account setup, and approval state.

8. Price-list acquisition
- Capture supplier list files and validate acquisition status.

9. Handoff into Product Sourcing / Feeder
- Emit handoff artifact so feeder can convert supplier lists into product candidates.

## E. Baseline Inspiration Vs New Design
### Baseline inspiration from existing tools
- Keyword/category discovery pattern from prototype sourcing scripts.
- Amazon-direct exclusion pattern from prototype first-check pass.
- ASIN/barcode enrichment and rank/hazmat/ROI-style filtering concepts from first-check tooling.
- Status-based progression pattern across staged checks.

### New design (not fully present in prototype)
- Full supplier/distributor discovery workflow.
- Supplier onboarding and account-state tracking.
- Manufacturer-direct exclusion as a governed rule set.
- Price-list acquisition lifecycle and artifact governance.
- Explicit structured handoff contract into feeder intake.

## F. Output Statuses
- Candidate Found: opportunity identified and recorded.
- Rejected: failed mandatory checks and removed from active path.
- Watch: held for later re-check due to uncertainty.
- Supplier Research Needed: candidate valid but supplier not yet found.
- Supplier Found: at least one viable distributor/supplier identified.
- Account Pending: supplier selected, onboarding in progress.
- Price List Acquired: usable list file received.
- Handoff Ready: minimum handoff fields complete for feeder intake.

## G. Minimum Output Data Model
Minimum fields:
- discovery_candidate_id
- discovery_run_id
- keyword_source
- category_source
- asin
- barcode
- title
- brand
- amazon_direct_flag
- manufacturer_direct_flag
- demand_rank_indicator
- qualification_status
- qualification_reason_codes
- supplier_research_status
- distributor_candidates
- chosen_supplier_id
- account_status
- price_list_status
- price_list_artifact_path
- handoff_ready_flag
- last_reviewed_utc

## H. Handoff To Product Sourcing Loop
Handoff artifact:
- `supplier_discovery_handoff.csv` (required)
- `supplier_discovery_handoff.json` (optional mirror)

Minimum required before feeder entry:
- product identity key (`asin` and/or validated barcode)
- brand
- chosen supplier reference (or explicit supplier-candidate set if unresolved)
- price-list artifact path
- price-list status = acquired
- handoff ready flag = true

Supplier-to-many-product model:
- one supplier can feed many discovery candidates
- represent supplier once (supplier master) and reference it from many candidate rows

## I. Stalled / Rejected Opportunity Model
Rejected and stalled opportunities should remain in an upstream opportunity sink, not in product dropped/discontinued lifecycle.

Suggested lanes:
- Rejected Opportunity: closed unless reason code changes.
- Watch Opportunity: deferred for re-check on trigger.
- Supplier Stall: valid candidate but supplier/account/list blocked.

Re-entry rules:
- Watch and Supplier Stall can re-enter active discovery.
- Rejected re-enters only with explicit override or new evidence.

## J. Phased Delivery Plan
### v1
- Market discovery + candidate filtering + Amazon-direct exclusion.
- Manual supplier research queue.
- Basic status model and handoff schema.

### v1.1
- Supplier/account tracking.
- Manufacturer-direct exclusion baseline rules.
- Opportunity sink with reason codes.

### v1.2
- Price-list acquisition tracking and handoff artifact generation.
- Structured join into feeder intake.

### Later
- AI-assisted distributor discovery.
- Prioritization scoring for highest expected return opportunities.
- Assisted outreach and onboarding acceleration.

## K. Review/Update Notes
- Review weekly and after major discovery logic changes.
- Keep wording plain-English and decision-focused.
- Update order:
- boundaries
- stage flow
- statuses
- handoff contract
- phased plan
- expectations alignment
