# Coding Plan

Date: 2026-05-19
Scope: planning first for supplier price-list cost, actual purchase cost, discount assumptions, and O stock-decider max purchase price.

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Research and planning only | this plan folder only | document review | no | completed |
| Phase 1 | Stabilize F source truth before stock-decider consumption | F source-shape checks, FPM TD active-run repair files only after approval | targeted FPM tests | yes | guard implemented and live-proven; active-run replacement needs user decision |
| Phase 2 | Add O supplier buy-cost truth output | O flow/schema files and tests | targeted O tests | no first, live proof later | implemented and locally proven |
| Phase 3 | Add discount assumption and user-confirm queue | O flow/schema/UI files and tests | targeted O tests | no first, live proof later | implemented and locally proven |
| Phase 4 | Add max purchase price to O recommendations | O recommendation and coverage files and tests | targeted O tests | yes for real sample | implemented and locally proven |
| Phase 5 | Small real-SKU proof | approved O/F read paths only | targeted tests plus artifact review | yes | completed for current O live file set |

## 2) Phase details

### Phase 0 - Research and planning
Goal:
- Understand where repricer, price-list, stock-decider, Product DB, and active plans stand.
- Write a plan before code changes.

Files allowed to change:
- `plans/active/repricing-stock-cost-bridge-2026-05-19/*`

Implementation tasks:
- Read current roadmap, repricer contract, O reorder rules, F price-list guidebook, active H/F/O plans, and current output artifacts.
- Record current gaps and blockers.
- Define a phased plan for approval.

Isolated verification:
- command:
  - document review only
- expected result:
  - research report, plan, coding plan, and status file exist

Monitored validation:
- live proof needed:
  - no
- forced proof window:
  - none
- artifacts to poll:
  - none
- poll cadence:
  - none
- success threshold:
  - plan describes exact data needed and safe implementation phases
- timeout rule:
  - none
- fallback if forced proof is blocked:
  - none
- next automatic step after success:
  - wait for user approval before Phase 1
- notification mode:
  - milestone only
- user interruption threshold:
  - user approval needed before any code or runtime changes

Phase status:
- code fix applied:
  - no runtime code changed
- isolated verification passed:
  - research completed from local artifacts
- monitored validation:
  - not needed

### Phase 1 - F source truth stabilization
Goal:
- Prevent malformed price-list rows from feeding stock decisions.
- Resolve the current TD Synnex live active-run contradiction at a safe F boundary.

Files allowed to change after approval:
- `scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py`
- `scripts/flows/F/price_list_manager/FPM100_apply_f061_handoff.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_fpm070_stage_f061_handoff.py`
- `tests/test_fpm100_apply_f061_handoff.py`
- `tests/test_fpm130_live_cycle.py`
- this plan folder

Implementation tasks:
- Add or run a source-shape guard that catches shifted supplier rows before handoff.
- TD Synnex shape rule example:
  - `supplier_sku` must not look like a brand name
  - `supplier_title` must not look like a numeric price
  - `unit_cost` must match the source cost column
- At a safe F drain boundary, retire or quarantine the old bad active run if it is still active.
- Reapply the clean TD Synnex active run only through guarded FPM handoff.
- Record whether previous bad-run outputs must be quarantined from future memory/cost use.

Isolated verification:
- command:
  - `python -m py_compile scripts\flows\F\price_list_manager\FPM070_stage_f061_handoff.py scripts\flows\F\price_list_manager\FPM100_apply_f061_handoff.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py`
  - `python -m pytest tests\test_fpm070_stage_f061_handoff.py tests\test_fpm100_apply_f061_handoff.py tests\test_fpm130_live_cycle.py -q`
- expected result:
  - tests prove malformed TD rows are blocked before live active-run use

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - F-owned drain boundary only, no overlapping FPM130/F061 owner
- artifacts to poll:
  - `out/systems/F/price_list_manager/live/live_cycle_status.csv`
  - `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - `out/systems/F/inbox/supplier_price_list_run_state.csv`
  - `out/systems/F/price_list_manager/live/f061_child_stdout.log`
- poll cadence:
  - first check after drain/apply
  - then every 5 minutes up to 60 minutes if live proof is active
- success threshold:
  - active run id belongs to the clean applied run
  - first active rows have real supplier SKU, real title, real unit cost, and barcode
  - pending rows move under the clean active run
  - no second F owner is started
- timeout rule:
  - park as `parked pending F drain boundary` with exact active run id, pending rows, and blocker
- fallback if forced proof is blocked:
  - do not kill F mid-chunk; document the active owner and wait for the safe boundary
- next automatic step after success:
  - Phase 2
- notification mode:
  - milestone only unless new/worse F alert appears
- user interruption threshold:
  - approval needed before live active-run replacement

Phase status:
- code fix applied:
  - yes, source-shape guard added to FPM staging, staged apply, and live active-run resume.
- isolated verification passed:
  - yes.
  - `python -m py_compile scripts\flows\F\price_list_manager\FPM070_stage_f061_handoff.py scripts\flows\F\price_list_manager\FPM100_apply_f061_handoff.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py`
  - `python -m pytest tests\test_fpm070_stage_f061_handoff.py tests\test_fpm100_apply_f061_handoff.py tests\test_fpm130_live_cycle.py -q`
  - Result: 76 passed.
- monitored validation:
  - guard live proof confirmed.
  - Old F owner drained at `2026-05-19T11:57:03Z`.
  - Supervisor restarted F owner as PID `6584` at `2026-05-19T11:58:21Z`.
  - `out/systems/F/price_list_manager/live/live_cycle_status.csv` showed `blocked_source_shape_guard` at `2026-05-19T11:58:50Z`.
  - `out/systems/F/price_list_manager/live/live_cycle_events.csv` recorded `source_shape_guard_blocked` for `td_synnex` / `fpm_td_synnex_20260519T090704Z`.
  - Blocked-state loop sleep was raised to a one-minute floor, then live owner was reloaded again.
  - Current owner after reload: PID `35404`, started `2026-05-19T12:03:36Z`, status `blocked_source_shape_guard`.
  - Active run replacement was not performed because replacing 43,039 live active rows is a separate data-state decision.
  - Proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase1_source_shape_guard_final_20260519T120528Z`.

### Phase 2 - O supplier buy-cost truth output
Goal:
- Create one O-owned file that explains the expected buy cost before O recommends stock.

Files allowed to change after approval:
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- new `scripts/flows/O/O007_build_supplier_buy_cost_truth.py`
- `tests/test_o007_supplier_buy_cost_truth.py`
- this plan folder

Implementation tasks:
- Read F manager batch rows for latest price-list cost.
- Read Product DB or O source identity for seller SKU mapping.
- Read actual purchase evidence from O decision/PO history where available.
- Output:
  - list cost
  - actual paid cost
  - discount ratio
  - expected next cost
  - cost confidence
  - review-required flag
  - source batch and row lineage
- Do not write Product DB or Sheets.

Isolated verification:
- command:
  - `python -m py_compile scripts\flows\O\_schemas.py scripts\flows\O\_source_contracts.py scripts\flows\O\O007_build_supplier_buy_cost_truth.py`
  - `python -m pytest tests\test_o007_supplier_buy_cost_truth.py -q`
- expected result:
  - same-as-list, discounted, missing-cost, bad-source, and changed-list examples produce clear cost states

Monitored validation:
- live proof needed:
  - no for first fixture proof
- forced proof window:
  - none
- artifacts to poll:
  - `out/systems/O/live/supplier_buy_cost_truth.csv`
- poll cadence:
  - not active until approved runtime proof
- success threshold:
  - output rows reconcile to input rows and every row has a confidence state
- timeout rule:
  - if mapping is too weak, park with exact missing identity fields
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 3
- notification mode:
  - milestone only
- user interruption threshold:
  - ask only if identity mapping is ambiguous

Phase status:
- code fix applied:
  - yes.
  - Added O supplier buy-cost truth output and schema/source contracts.
  - Reads Product DB preview plus F price-list manager batch rows and batch metadata.
  - Does not write Product DB or Google Sheets.
- isolated verification passed:
  - yes.
  - `python -m py_compile scripts\flows\O\_schemas.py scripts\flows\O\_source_contracts.py scripts\flows\O\O001_build_restock_source_view.py scripts\flows\O\O002_build_restock_recommendations.py scripts\flows\O\O003_build_restock_review_queue.py scripts\flows\O\O007_build_supplier_buy_cost_truth.py scripts\flows\O\O008_build_supplier_cost_confirmation_queue.py scripts\flows\O\O020_build_reorder_input_coverage_report.py scripts\cycles\run_O_cycle.py`
  - `python -m pytest tests\test_o000_paths_and_schemas.py tests\test_o000_source_contracts.py tests\test_o007_supplier_buy_cost_truth.py tests\test_o008_supplier_cost_confirmation_queue.py tests\test_o_cycle_runner.py -q`
  - Result: 15 passed.
- monitored validation:
  - focused O local proof completed.
  - `out/systems/O/live/supplier_buy_cost_truth.csv` rows: 608.
  - Rows with price-list match: 87.
  - Rows with expected next cost: 196.
  - Rows requiring user price check: 538.
  - Proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase2_to_5_o_cost_bridge_20260519T123903Z`.

### Phase 3 - Discount assumptions and user confirmation queue
Goal:
- Make discounted expected costs visible and confirmable.

Files allowed to change after approval:
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/O007_build_supplier_buy_cost_truth.py`
- new `scripts/flows/O/O008_build_supplier_cost_confirmation_queue.py`
- optional O UI changes only after the file output is proven
- targeted tests
- this plan folder

Implementation tasks:
- Calculate `actual_paid_vs_list_ratio`.
- If ratio is 1.0000, treat next list price as trusted list price.
- If ratio is below 1.0000 and a new list price arrives, apply the ratio but require user confirmation.
- Create a queue row with plain reason:
  - `discount_assumption_needs_confirmation`
  - `price_list_changed_after_discounted_purchase`
  - `actual_paid_above_list_needs_review`
  - `missing_purchase_reference`

Isolated verification:
- command:
  - `python -m pytest tests\test_o007_supplier_buy_cost_truth.py tests\test_o008_supplier_cost_confirmation_queue.py -q`
- expected result:
  - the GBP 2.00 to GBP 1.80 to GBP 2.50 example produces GBP 2.25 expected cost and a user-check flag

Monitored validation:
- live proof needed:
  - no for first fixture proof
- forced proof window:
  - none
- artifacts to poll:
  - `out/systems/O/live/supplier_cost_confirmation_queue.csv`
- poll cadence:
  - not active until approved real sample
- success threshold:
  - all unconfirmed discount assumptions appear in the queue
- timeout rule:
  - park with exact rows missing from queue
- fallback if forced proof is blocked:
  - not applicable
- next automatic step after success:
  - Phase 4
- notification mode:
  - milestone only
- user interruption threshold:
  - only if user wording or approval rules need decision

Phase status:
- code fix applied:
  - yes.
  - Added `out/systems/O/live/supplier_cost_confirmation_queue.csv`.
  - Discounted actual purchase costs now create a user confirmation row instead of being silently trusted.
- isolated verification passed:
  - yes.
  - `python -m pytest tests\test_o007_supplier_buy_cost_truth.py tests\test_o008_supplier_cost_confirmation_queue.py -q`
  - Covered the GBP 2.00 list, GBP 1.80 actual, GBP 2.50 next-list example producing GBP 2.25 expected cost with a user-check flag.
- monitored validation:
  - focused O local proof completed.
  - `out/systems/O/live/supplier_cost_confirmation_queue.csv` rows: 538.
  - Discount-assumption rows requiring confirmation: 12.
  - Actual-paid-above-list rows requiring review: 5.

### Phase 4 - Max purchase price in stock decider
Goal:
- Let O show the buy-cost limit before a recommendation becomes unsafe.

Files allowed to change after approval:
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O002_build_restock_recommendations.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/_schemas.py`
- targeted O tests
- this plan folder

Implementation tasks:
- Add `max_break_even_purchase_price_gbp`.
- Add `max_target_roi_purchase_price_gbp`.
- Add `target_roi_pct`.
- Add blocker reasons when fees, shipping, market price, or cost basis are missing.
- Use expected next cost from the O cost truth output.
- Block or downgrade rows where expected next cost is over the max purchase price.

Isolated verification:
- command:
  - `python -m pytest tests\test_o001_restock_source_view.py tests\test_o002_restock_recommendations.py tests\test_o020_reorder_input_coverage.py -q`
- expected result:
  - recommendations change correctly when expected cost is above or below max purchase price

Monitored validation:
- live proof needed:
  - yes for approved real sample
- forced proof window:
  - O-owned local rebuild only; no A ad-hoc run
- artifacts to poll:
  - `out/systems/O/live/restock_source_view.csv`
  - `out/systems/O/live/restock_recommendations_live.csv`
  - `out/systems/O/live/reorder_input_coverage_report.csv`
- poll cadence:
  - first check after rebuild, then stop unless real sample proof is approved
- success threshold:
  - expected cost, max purchase price, and recommendation status line up on sampled rows
- timeout rule:
  - park with exact missing field or formula blocker
- fallback if forced proof is blocked:
  - keep status as isolated only, not live-confirmed
- next automatic step after success:
  - Phase 5
- notification mode:
  - milestone only
- user interruption threshold:
  - user decision needed if target ROI policy is not agreed

Phase status:
- code fix applied:
  - yes.
  - O source view now consumes the O cost bridge.
  - O recommendations now carry max break-even price, max target-ROI purchase price, target ROI percent, purchase-price safety status, and user price-check fields.
  - O020 readiness now blocks rows that still need supplier cost confirmation.
- isolated verification passed:
  - yes.
  - `python -m pytest tests\test_o001_restock_source_view.py tests\test_o002_restock_recommendations.py tests\test_o003_restock_review_queue.py tests\test_o020_reorder_input_coverage.py -q`
  - Result: 22 passed.
  - O test pack result: 147 passed.
  - F source-shape regression result: 76 passed.
- monitored validation:
  - focused O local proof completed.
  - `out/systems/O/live/restock_recommendations_live.csv` rows: 608.
  - Recommendation status counts: 602 wait, 6 full_restock.
  - Purchase safety counts: 301 missing_market_price, 244 missing_expected_cost, 62 within_target_roi_max, 1 above_break_even_max.
  - `out/systems/O/live/reorder_input_coverage_report.csv` action-ready rows: 6.
  - Action-ready rows still requiring user price check: 0.

### Phase 5 - Small real-SKU proof
Goal:
- Prove the full bridge on a very small approved sample before wider rollout.

Files allowed to change after approval:
- plan docs
- approved O/F read paths only

Implementation tasks:
- Pick 3 to 5 approved SKUs with supplier price-list cost and at least one actual purchase cost.
- Include one same-as-list example.
- Include one discounted example.
- Include one missing or bad-cost example.
- Prove O recommendation status and max purchase price are understandable.

Isolated verification:
- command:
  - repeat Phase 2 to 4 focused tests
- expected result:
  - all tests still pass after sample wiring

Monitored validation:
- live proof needed:
  - yes
- forced proof window:
  - O local rebuild only unless an F boundary fix is required
- artifacts to poll:
  - `out/systems/O/live/supplier_buy_cost_truth.csv`
  - `out/systems/O/live/supplier_cost_confirmation_queue.csv`
  - `out/systems/O/live/restock_recommendations_live.csv`
- poll cadence:
  - first check after approved sample rebuild
- success threshold:
  - sample rows show the right expected cost, user-check flag, max purchase price, and recommendation outcome
- timeout rule:
  - park with exact sample row and missing evidence
- fallback if forced proof is blocked:
  - do not broaden rollout; keep sample proof pending
- next automatic step after success:
  - ask for approval before broader O real-SKU rollout
- notification mode:
  - milestone only
- user interruption threshold:
  - any mismatch in cost, discount, or max purchase price

Phase status:
- code fix applied:
  - yes.
  - Current real O file set was rebuilt through O007, O008, O001, O002, O003, O004, and O020.
  - Purchase-order and decision-apply steps were not run in this proof.
- isolated verification passed:
  - yes.
  - Same test evidence as Phase 2 to Phase 4.
- monitored validation:
  - completed for the current O live file set.
  - Before-write rollback snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_phase2_20260519T122526Z`.
  - Proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase2_to_5_o_cost_bridge_20260519T123903Z`.
  - The stock-decider readiness report now includes the user confirmation block, so discounted or unclear supplier costs do not become action-ready.
- purchase-order proof:
  - completed as a local proof only; no Google Sheets write and no supplier order placed.
  - Proof folder: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase5_purchase_order_proof_20260519T133233Z`.
  - Current action-ready rows reviewed: 6.
  - Proof decisions generated from those 6 action-ready rows only.
  - PO draft output: 6 headers, 6 lines, 0 holds.
  - Total units: 525.
  - Total value: GBP 1,184.87.
  - All 6 rows were `within_target_roi_max`.
  - All 6 rows had `user_price_check_required=0`.
  - Business caveat: all 6 rows are `price_list_only_no_purchase_reference`, so this proves the pipeline can draft clean POs, but real buying still needs operator approval.
  - Verification: `python -m pytest tests/test_o100_build_purchase_orders.py -q`, result 1 passed.

Pack-size blocker discovered after Phase 5:
- Trigger:
  - Operator identified that Sika supplier SKU `484651` / seller SKU `6V-EEC1-2S9Z` is sold as a pack of 3, while the proof output treated it as a unit item.
- Evidence:
  - `out/systems/O/live/restock_source_view.csv` currently carries `supplier_pack_size=1`, `amazon_pack_size=1`, `order_qty_mode=raw_units`, `sell_pack_qty=1`, `supplier_case_qty=1`, `valid_order_step=1`, and no confirmed pack note for the Sika row.
  - The previous active pack plan `plans/active/o-restock-pack-and-db-through-use-v1/CODING_PLAN.md` has pack-aware readiness as Phase 3 planned, and real-SKU onboarding as Phase 4 planned, but those phases were not completed before this cost bridge proof.
- Decision:
  - Do not promote the 6-line PO proof to real buying until pack-size truth is wired into O readiness and purchase-order proof.
- Next implementation:
  - Continue with the pack-size SKU profile phase before live PO approval.
  - Add or use a SKU/profile source for confirmed buy pack, sold pack, supplier case quantity, order step, and repack/bundle flags.
  - Make O readiness block rows with unconfirmed or missing pack truth instead of silently using `1`.
  - Rebuild the 6-line proof after the pack-size gate is active, with Sika expected to show sold pack size 3.
- Detailed plan:
  - `plans/active/repricing-stock-cost-bridge-2026-05-19/SKU_PACK_SIZE_IMPLEMENTATION_PLAN.md`.
  - This plan separates Amazon sale-pack truth from supplier/carton buying policy.
  - It includes Sika 20g and 50g hazmat carton handling, supplier box conversion, cost-basis conversion, PO output changes, readiness blockers, and proof criteria.
- Implementation status:
  - completed as isolated O-flow proof at `2026-05-19T15:30:00Z`.
  - O001, O002, O020, and O100 now carry pack profile, component conversion, readiness blocking, and PO carton conversion.
  - O002 blocks unsafe pack profiles before buy recommendations are created.
  - O100 holds approved decisions if the pack profile is missing, unconfirmed, invalid, or missing special carton fields.
  - Focused proof: `python -m pytest tests/test_o001_restock_source_view.py tests/test_o002_restock_recommendations.py tests/test_o020_reorder_input_coverage.py tests/test_o100_build_purchase_orders.py -q`, result 27 passed.
  - O-flow proof pack: `python -m pytest <all tests/test_o*.py> -q`, result 158 passed.
  - Isolated proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/pack_size_o_proof_20260519T154000Z`.
  - Proof result: Sika 20g drafts as 250 Amazon packs / 750 bottles / 30 supplier boxes; PE-G94Y-4PYO and SU-5LQH-2DVN remain blocked as missing/special profile; Sika 50g pack profile is ready but still waits for usable cost evidence.
  - Live O-owned profile files seeded at `out/systems/O/live/sku_quantity_profiles.csv` and `out/systems/O/live/special_order_profiles.csv`.
  - Before-write rollback snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_pack_profiles_20260519T155000Z`.
  - Live O stock-decider outputs refreshed through O001, O002, O003, O004, and O020 only.
  - Live refresh rows: source 608, recommendations 608, coverage 608, action-ready 6.
  - Live check: 6V-EEC1-2S9Z confirmed/3 components/GBP 4.35/full_restock/action-ready; PE-G94Y-4PYO and SU-5LQH-2DVN blocked as missing profile; A2-T2AC-TW3L confirmed but waiting for usable cost evidence.
  - Live O100 purchase-order drafting was not run; no Google Sheets write and no supplier order placed.

### F runtime repair - TD Synnex active run reload
Goal:
- Stop the F061 scanner from reloading the old broken TD Synnex active run after the clean TD Synnex conversion had already been staged.

Root cause:
- `sql_shadow` reads were using SQL before CSV, so a stale SQL shadow table could override the repaired CSV active queue.
- The TD Synnex source-shape guard was also too broad for one real TD row where SKU and description are both the same numeric product code.

Files changed:
- `scripts/core/storage/pandas_bridge.py`
- `scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py`
- `tests/test_storage_adapter.py`
- `tests/test_fpm070_stage_f061_handoff.py`

Runtime data repaired:
- Replaced the blocked bad TD Synnex active run `fpm_td_synnex_20260519T090704Z`.
- Restored clean run `fpm_td_synnex_20260519T095000Z`.
- Preserved previous clean-run progress by trimming 150 already-processed queue rows.
- Final repaired pending rows before live restart: 57,821.
- First live chunk after restart completed successfully and moved pending rows to 57,796.

Rollback snapshots:
- `out/systems/F/price_list_manager/test_mode/f061_handoff_backups/backup_td_synnex_replace_bad_active_20260519T130325Z`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_backups/backup_td_synnex_trim_repaired_active_20260519T130905Z`

Verification:
- focused test pack:
  - `python -m pytest tests/test_storage_adapter.py tests/test_flow_contract_io_sql.py tests/test_fpm070_stage_f061_handoff.py tests/test_fpm100_apply_f061_handoff.py tests/test_fpm130_live_cycle.py -q`
  - result: 91 passed.
- live proof:
  - FPM130 restarted with fixed code.
  - source-shape guard cleared.
  - state-regression guard cleared after progress-preserving trim.
  - scanner event: `2026-05-19T13:09:24Z`, status `success`, rows `25`, `pending_after=57796`.

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a safe forced proof window exists.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
