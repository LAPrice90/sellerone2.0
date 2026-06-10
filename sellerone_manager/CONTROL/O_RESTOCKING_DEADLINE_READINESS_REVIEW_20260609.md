# O Restocking Deadline Readiness Review

job_ref: O-RESTOCKING-DEADLINE-PLANNING-20260609
created_uk: 2026-06-09
owner: O restocking planning/evidence Worker
business_deadline: Luke goes to North Wales on 2026-06-18
output_type: planning and evidence review only

## Plain-English Result

Blocked with exact reason.

O is ready for proposal-lane planning, but it is not ready for clean ordering decisions today. The restocking system has many of the review screens, guardrails, proof drawers, PO-preview shapes, and supplier-proof controls already proved, but the current live evidence still blocks every candidate from a clean buy.

Simple analogy: the buying desk has the forms and safety rails built, but the rows still do not have enough trusted numbers on them to sign an order.

## Boundary Followed

This review was read-only except for this new control note.

No protected business action was taken:

- no orders placed
- no purchase commitments
- no receiving action
- no send-to-Amazon action
- no supplier email or supplier commitment
- no price change
- no Google Sheets write
- no queue edit
- no Product DB or local DB alignment
- no supplier file move, delete, rewrite, import, download, or fetch
- no Gmail fetch or attachment download
- no F061 run or F source-status rewrite
- no O runtime or live worker cycle
- no output deletion
- no Task Scheduler change
- no Amazon or security action

## Evidence Checked

Control files:

- `CONTROL/O_RESTOCKING_DEADLINE_PLAN_20260609.md`
- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- `CONTROL/QUEUE_CONTRACT.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`

Current queue and MOT evidence:

- `../out/systems/M/approved_task_packets.csv`
- `../out/systems/M/mot/mot_latest.md`
- `../out/systems/M/mot/mot_latest.csv`

O evidence files:

- `../out/systems/O/live/reorder_input_readiness_summary.md`
- `../out/systems/O/live/restock_recommendations_live.csv`
- `../out/systems/O/live/restock_session_review_live.csv`
- `../out/systems/O/live/restock_session_supplier_summary_live.csv`
- `../out/systems/O/live/reorder_input_coverage_report.csv`
- `../out/systems/O/live/restock_profit_checks_live.csv`
- `../out/systems/O/live/restock_market_refresh_candidates_live.csv`
- `../out/systems/O/live/restock_token_cost_trust_gate_live.csv`
- `../out/systems/O/live/restock_profit_input_blocker_breakdown_live.csv`

O packets checked:

- `tasks/approved/MOT_O_O_ACTIVE_RESTOCK_PROOF_FILES.md`
- `tasks/approved/MOT_O_O_USER_WORKING_READINESS.md`
- `tasks/approved/MOT_O_O_H_MARKET_PROOF_GATE.md`
- `tasks/approved/MOT_O_O_H_MAINTENANCE_CONTROLLER_GATE.md`
- `tasks/blocked/MGR_O_user_decision_plans_active_o_reorder_p.md`

## Current O Queue Position

Active O Builder-ready repairs:

- `O-ACTIVE-RESTOCK-FILES` - approved - O MOT says active restock proof files still fail because 2 proof files are stale-fail.
- `O-USER-WORKING-READINESS` - approved - O MOT says user working readiness is not ready because 1 safety blocker remains.

O support work already proved:

- Many O proposal and guardrail packets are proved, including purchase approval preview, real PO readiness gate, PO draft preview controls, supplier proof work queue, supplier readiness summary, token cost trust gate, and restock session controls.

Plain-English meaning:

- The review tools and safety rails exist.
- The current data still says no row should be treated as clean buy-ready.

## Current Row Evidence

Latest current O evidence seen:

- `restock_recommendations_live.csv`: 608 rows.
- `restock_session_review_live.csv`: 608 rows.
- `reorder_input_coverage_report.csv`: 608 rows.
- `restock_profit_checks_live.csv`: 608 rows.

Decision state:

- `reorder_input_readiness_summary.md` says:
  - total rows considered: 608
  - action candidates: 0
  - rows actionable now: 0
  - rows blocked now: 608
- `restock_recommendations_live.csv` says all 608 rows have `recommendation_status=wait`.
- `restock_session_review_live.csv` says all 608 rows have `row_status=blocked`.
- `restock_session_review_live.csv` says all 608 rows have `action_safety_state=blocked_from_clean_buy`.
- `reorder_input_coverage_report.csv` says all 608 rows have `action_ready_now=0`.

Profit and price state:

- `restock_profit_checks_live.csv`:
  - 556 rows are `needs_price_check`.
  - 23 rows are `missing_profit_inputs`.
  - 20 rows are `drop_review_only`.
  - 9 rows are `test_only`.
- `restock_recommendations_live.csv` purchase price safety:
  - 448 rows are blocked by `missing_net_fee_model`.
  - 119 rows are blocked by `missing_expected_cost`.
  - 18 rows are `above_break_even_max`.
  - 7 rows are `above_target_roi_max`.
  - 16 rows are within target ROI max, but they are still not clean buy-ready because other proof gates remain missing.

Supplier concentration:

- The largest current supplier groups in recommendations are Stax, Bliss Distribution, ABGee, CLF, unknown supplier, Shure Cosmetics, DHB, TD Synnex, Heo, Rashmian, Jones Wholesale, and DK Tools.
- Supplier summary shows no supplier has ready-for-review order rows right now.
- Top supplier block patterns include missing supplier cost, missing market price, legacy bridge not native truth, missing inbound cost confidence, and missing order quantity.

## Safe Reorder-Candidate Evidence

There are no safe reorder candidates for buying today.

There is still useful proposal evidence:

- 608 rows exist for review and sorting.
- 59 market-refresh candidate rows exist in `restock_market_refresh_candidates_live.csv`.
- 7 rows have minimum restock inputs according to the blocker breakdown evidence.
- 16 rows appear within target ROI max in purchase-price safety, but they are not order-safe because the wider proof gates still block clean buy.
- The supplier and row-level dashboards can be used to prepare a proposal explaining what proof is missing per supplier and per row.

Plain-English handling:

- These rows can be used as a worklist.
- They must not be used as purchase instructions.

## Blocked Or Unsafe Order Evidence

Current order evidence is unsafe for real ordering because:

- 608 of 608 rows are blocked from clean buy.
- 0 rows are actionable now.
- O MOT has 2 active O failures:
  - `o_active_restock_proof_files`
  - `o_user_working_readiness`
- O MOT has O warnings affecting buy confidence:
  - inbound/FBA cost allocation proof has 0 safe rows and 608 missing rows.
  - inbound/FBA source options has 0 direct safe routes and 3 protected routes.
  - profit input blocker breakdown shows only 7 minimum-input rows and those still have weak inputs.
  - refund/restock confidence fields still warn on weak profit inputs.
  - token cost trust gate has 23 untrusted rows.
- E MOT says restock business-ready SKUs are 0.
- B warnings still say some recovered, bridge, or fallback values must not feed live ROI/restocking.
- A blocked Luke decision still exists for pausing H before a controlled restock-candidate market proof scan.

## What Luke Should Expect Tomorrow

Tomorrow, Operations can safely route a planning/proposal lane, not an ordering lane.

Expected useful output tomorrow:

- a supplier-by-supplier restocking proposal draft
- a list of the nearest reorder candidates
- a list of why each candidate is blocked
- a split between:
  - rows needing market price proof
  - rows needing supplier cost proof
  - rows needing inbound/FBA cost proof
  - rows needing token-cost trust proof
  - rows stuck behind legacy bridge truth
  - rows needing quantity, pack, or MOQ proof
- a Luke-facing decision list for anything protected before 2026-06-18

Expected limitation tomorrow:

- Unless the blockers clear, the proposal should recommend what to prove next, not what to order.

## Decisions Needed Before 2026-06-18

Luke will need decisions only when the proposal reaches protected business action.

Likely decisions before 2026-06-18:

- whether to approve a controlled H isolation path for O market proof, if still needed
- whether to approve any protected source route for inbound/FBA cost proof
- whether to allow any legacy-bridge-only candidate to be manually reviewed as an exception
- whether to approve actual order candidates once the proof package is clean enough

Do not ask Luke to approve actual buying from the current 608-row evidence. The current evidence says 0 rows are clean buy-ready.

## Next Safe Packet Or Action To Route

Route this next:

`O-USER-WORKING-READINESS`

Reason:

- It is already approved.
- It is current in `CURRENT_TICKETS.md`.
- It targets the user-facing readiness blocker.
- Its boundary is safe: walkthrough and manager proof only, with no purchase, PO creation, receiving, send-to-Amazon, Sheet write, price change, queue edit, DB alignment, output deletion, H pause, or market scan.

Then route:

`O-ACTIVE-RESTOCK-FILES`

Reason:

- It is already approved.
- It targets the stale proof-file blocker.
- It should make the current proof map trustworthy before proposal work leans on the restocking files.

After those two clear, route a planning-only Operations proposal:

`O-RESTOCKING-DEADLINE-PROPOSAL-20260610`

Suggested scope:

- read-only supplier-by-supplier proposal draft
- no ordering, no supplier contact, no sheets, no database alignment, no runtime cycle
- output a candidate list and blocker list for Luke before 2026-06-18

## Final Readiness Classification

Status: blocked for ordering, ready for proposal work.

Exact reason:

- Current O evidence contains 608 rows, but 608 are blocked, 0 are actionable, 0 are clean buy-ready, and MOT still has 2 O failures plus several O warnings that directly affect restocking confidence.

Completion recommendation:

- continue with `O-USER-WORKING-READINESS`
