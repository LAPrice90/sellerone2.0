# B Token Shortage Corrections - 2026-05-06

## Current Phase
Reopened for the 2026-06-04 approved AK token correction.

User approved corrections for all currently listed token shortages after SKU-level review.
On 2026-05-10, user approved the current `6Q-9G2A-IKVV` `legacy_baseline_gap` correction from the morning MOT.
On 2026-06-04, user approved the current `AK-OB6V-HIYD` correction using the previous cost basis of `1.21`.

## Allowed Files
- `scripts/one_off/T030_apply_approved_token_corrections.py`
- `tests/test_t030_apply_approved_token_corrections.py`
- `out/manual_token_corrections_approved.csv`
- `out/manual_token_correction_events.csv`
- B local token outputs touched by the approved one-off correction applier
- this plan file

## Source Evidence
- `out/token_shortages_by_sku.csv` at `2026-05-06T08:16:36Z` listed 6 shortage rows.
- Current classes: `legacy_baseline_gap` 4 rows, `true_live_shortage` 2 rows.
- User approval text: "approve all corrections".
- 2026-05-10 MOT evidence: `out/token_shortages_by_sku.csv` listed `6Q-9G2A-IKVV`, missing quantity 1, class `legacy_baseline_gap`, next action `needs_user_decision_baseline_correction_or_exception`.
- 2026-05-10 user approval text: "approve".
- 2026-05-30 manager MOT evidence: `out/token_shortages_by_sku.csv` lists `AK-OB6V-HIYD`, missing quantity 3, class `true_live_shortage`, next action `wait_for_receipt_or_approved_stock_correction`.
- 2026-05-30 user approval text: "Approve correction".
- 2026-06-04 B evidence: `out/token_shortages_by_sku.csv` lists `AK-OB6V-HIYD`, missing quantity 1, class `true_live_shortage`, next action `wait_for_receipt_or_approved_stock_correction`.
- 2026-06-04 user approval text: "AK-OB6V-HIYD you can adjust the token amount to the same cost of the previous we've only ever paid 1.21 for them".

## Correction Scope
- Add 8 available correction tokens:
  - `0R-GRRH-W0Z9`: 1
  - `6Q-9G2A-IKVV`: 1
  - `MW-9K5M-VKW8`: 2
  - `R4-0AXZ-ZZ9D`: 1
  - `SE-UITZ-7CPY`: 2
  - `SZ-UL4K-SE7W`: 1
- Correction source file: `out/manual_token_corrections_approved.csv`.
- Audit artifact: `out/manual_token_correction_events.csv`.
- 2026-05-10 additional approved correction token:
  - `6Q-9G2A-IKVV`: 1
- 2026-05-10 approval reference: `TOKEN_SHORTAGE_20260510_USER_APPROVED_6Q_9G2A_IKVV`.
- 2026-05-30 additional approved correction tokens:
  - `AK-OB6V-HIYD`: 3
- 2026-05-30 approval reference: `TOKEN_SHORTAGE_20260530_USER_APPROVED_AK_OB6V_HIYD`.
- 2026-06-04 additional approved correction tokens:
  - `AK-OB6V-HIYD`: 1 at cost `1.21`
- 2026-06-04 approval reference: `TOKEN_SHORTAGE_20260604_LUKE_APPROVED_AK_OB6V_HIYD_COST_1_21`.

## 2026-06-04 Implementation Plan
- Narrow the B047/B048 protected repair boundary to `AK-OB6V-HIYD` only for this approval.
- Build the read-only B047 preview and confirm it creates exactly one allocated sale token at cost `1.21`.
- Request B maintenance and wait for matching `out/locks/maintenance.ready` before any live token write.
- Apply B048 with the matching maintenance request ID.
- Release only the maintenance markers created for this request.
- Monitoring target: `out/token_shortages_by_sku.csv`, `out/orders_missing_tokens.csv`, `out/token_allocations_live.csv`, `out/token_cogs_ledger.csv`, `out/cycle_alerts/checklist_B_split.csv`, and the next finalized B log cycle.
- Success threshold: AK shortage row removed, AK missing-token order removed, one AK allocation created at `1.21`, one COGS row created at `1.21`, and the next finalized B proof no longer blocks on `token_shortages_by_sku`.
- Timeout rule: if B does not produce a post-correction finalized run within 60 minutes after release, park as `parked pending next proof window` and keep the artifacts above as the resume trigger.

## 2026-06-04 Proof Result
- Focused checks passed:
  - `python -m py_compile scripts/flows/B/B047_build_token_shortage_repair_preview.py scripts/flows/B/B048_apply_token_shortage_repair.py sellerone_manager/app.py`
  - `python -m pytest tests/test_b047_b048_token_shortage_repair.py -q` with 11 passed.
- Read-only B047 preview was ready with 1 sale token row, 0 adjustment token rows, SKU `AK-OB6V-HIYD`, order `171-4557891-8556333`, and cost `1.21`.
- B maintenance handoff:
  - requested with `B048_AK_OB6V_HIYD_20260604T161130Z`
  - ready at `2026-06-04T16:11:39Z`
  - released at `2026-06-04T16:12:39Z`
- B048 applied under matching B maintenance at `2026-06-04T16:12:02Z`: 1 created token, 1 allocated token, 0 disposed tokens, 1 shortage row removed, 1 missing-order row removed.
- Backup snapshot written: `out/systems/B/token_shortage_repair/b048_token_shortage_repair_snapshots/20260604_161202Z`.
- Immediate ledger proof:
  - `out/token_shortages_by_sku.csv` has no `AK-OB6V-HIYD` row.
  - `out/orders_missing_tokens.csv` has no `AK-OB6V-HIYD` row.
  - `out/token_allocations_live.csv` has order `171-4557891-8556333` allocated to the new AK correction token at `1.21`.
  - `out/token_cogs_ledger.csv` has order `171-4557891-8556333` with `cogs_exvat=1.21`, `cogs_vat=0.24`, and `cogs_total=1.45`.
- First post-correction B proof cycle `B_20260604T161239Z` finalized at `2026-06-04T16:19:09Z` with active split health `fail=0`, `warn=0`; `token_shortages_by_sku`, `order_master_missing_token_no_placeholder_rows`, and `order_master_placeholder_cogs_rows` were all `ok`.
- Publish gate proof cycle `B_20260604T161909Z` saw `health_gate snapshot FAIL=0 WARN=0`, published Order Master, Order Ledger FX, and P&L, and ran `D001_build_pnl_daily.py` successfully.
- Separate non-AK issue observed after a later B069 maintenance interruption:
  - `B_20260604T161909Z` and `B_20260604T162711Z` ended with `l1_keys_missing_in_master` fail.
  - Current `l1_missing_fee_keys.csv` names order `S02-6203744-6940028`, SKU `QM-QAGK-D2UQ`.
  - Current token placeholder warning names order `202-9364806-5461939`, SKU `VF-3T0K-DR5O`, with `token_shortage_units=0`.
  - This is not an AK token shortage and is outside this approved AK correction scope.
- Verification status for AK correction: live loop verification confirmed.
- Verification status for broader B health: not clean because of separate `l1_keys_missing_in_master` fail.
- Recommended next step: create or use a separate B work item for the `l1_keys_missing_in_master` fail instead of widening this AK correction.

## 2026-05-30 Implementation Plan
- Add the approved correction row to `out/manual_token_corrections_approved.csv`.
- Run focused isolated checks:
  - `python -m py_compile scripts/one_off/T030_apply_approved_token_corrections.py`
  - `python -m pytest tests/test_t030_apply_approved_token_corrections.py -q`
  - `python scripts/one_off/T030_apply_approved_token_corrections.py`
- Request B maintenance, wait for `out/locks/maintenance.ready`, apply the correction, then release maintenance.
- Confirm the next boundary-safe B owner proof after the correction finalizes before treating the B publish block as cleared.
- Monitoring target: `out/token_shortages_by_sku.csv`, `out/cycle_alerts/checklist_B_split.csv`, latest `out/manifests/B/**/*.json`, and `out/systems/M/mot/mot_worklist.csv`.
- Success threshold: `token_shortages_by_sku` clears, latest finalized B run no longer blocks on that check, and B MOT no longer marks `b_pnl_daily` as `decision_needed`.
- Timeout rule: if B does not produce a post-correction finalized run within 60 minutes after release, park as `parked pending next proof window` and keep the exact artifacts above as the resume trigger.

## 2026-05-30 Proof Result
- Focused tests passed:
  - `python -m py_compile scripts/one_off/T030_apply_approved_token_corrections.py`
  - `python -m pytest tests/test_t030_apply_approved_token_corrections.py -q` with 3 passed.
  - `python -m pytest tests/manager -q` with 151 passed.
- Dry run before apply passed: 8 approval rows, 3 created tokens, 0 skipped, 7 already applied.
- B maintenance handoff:
  - requested with `B_TOKEN_SHORTAGE_CORRECTION_20260530_AK_OB6V_HIYD`
  - ready at `2026-05-30T19:12:46Z`
  - released at `2026-05-30T19:13:31Z`
- Applied under B maintenance at `2026-05-30T19:13:08Z`: 3 created tokens, 0 skipped, 7 already applied.
- Backup written: `out/backups/manual_token_corrections_20260530T191308Z/token_ledger_live.pre_correction.csv`.
- Audit row written: `T030-TOKEN_SHORTAGE_20260530_USER_APPROVED_AK_OB6V_HIYD-AK-OB6V-HIYD`.
- Post-apply dry run passed: 8 approval rows, 0 created tokens, 0 skipped, 8 already applied.
- First post-correction B allocator cycle `B_20260530T191409Z` cleared `out/token_shortages_by_sku.csv` to header only and finalized with split health `fail=0`, `warn=0`.
- Publish proof cycle `B_20260530T191754Z` logged `health_gate snapshot FAIL=0 WARN=0`, then `publish P&L`, then `ok D001_build_pnl_daily.py`, and finalized with split health `fail=0`, `warn=0`.
- Active split checklist proof: `token_shortages_by_sku=ok 0`, `order_master_missing_token_no_placeholder_rows=ok 0`, `order_master_placeholder_cogs_rows=ok 0`.
- Manager proof: B MOT after proof is `status=warn`, `fail_count=0`, with no Luke decision; remaining B warnings are refund/fee/ROI and marketplace proof gaps only.

## 2026-05-10 Implementation Plan
- Make `T030_apply_approved_token_corrections.py` idempotent by treating existing `ok` audit event IDs as already applied.
- Add the single approved 2026-05-10 correction row to `out/manual_token_corrections_approved.csv`.
- Run focused isolated checks:
  - `python -m py_compile scripts/one_off/T030_apply_approved_token_corrections.py`
  - `python -m pytest tests/test_t030_apply_approved_token_corrections.py -q`
  - `python scripts/one_off/T030_apply_approved_token_corrections.py`
- Request B maintenance, wait for `out/locks/maintenance.ready`, apply the correction, then release maintenance.
- Confirm the next boundary-safe B owner proof after the correction finalizes before treating the B publish block as cleared.

## 2026-05-10 Proof Result
- Idempotency patch applied to `T030_apply_approved_token_corrections.py`.
- Focused tests passed: `python -m py_compile scripts/one_off/T030_apply_approved_token_corrections.py`.
- Focused tests passed: `python -m pytest tests/test_t030_apply_approved_token_corrections.py -q` with 3 passed.
- Dry run passed: 7 approval rows, 1 created token, 0 skipped, 6 already applied.
- B maintenance handoff:
  - requested at `2026-05-10T18:46:44Z`
  - ready at `2026-05-10T18:46:59Z`
  - active at `2026-05-10T18:47:07Z`
  - released at `2026-05-10T18:47:19Z`
- Applied under B maintenance at `2026-05-10T18:47:11Z`: 1 created token, 0 skipped, 6 already applied.
- Backup written: `out/backups/manual_token_corrections_20260510T184711Z/token_ledger_live.pre_correction.csv`.
- Audit row written: `T030-TOKEN_SHORTAGE_20260510_USER_APPROVED_6Q_9G2A_IKVV-6Q-9G2A-IKVV`.
- Post-apply dry run passed: 7 approval rows, 0 created tokens, 0 skipped, 7 already applied.
- First post-correction B cycle `B_20260510T184719Z` finalized at `2026-05-10T18:51:24Z`; end-of-cycle split health confirmed `fail=0`, `warn=1`, fail checks empty.
- Publish proof cycle `B_20260510T185124Z` finalized at `2026-05-10T18:56:36Z`; B log showed `health_gate snapshot FAIL=0 WARN=1 source=checklist_B_split.csv`, then `publish Order_Master`, `publish Order_Ledger_FX`, and `publish P&L`.
- Active split checklist proof: `token_shortages_by_sku=ok 0`, `order_master_missing_token_no_placeholder_rows=ok 0`, `order_master_placeholder_cogs_rows=warn 1`.
- `out/token_shortages_by_sku.csv` has header only after proof.
- Remaining WARN is `order_master_placeholder_cogs_rows=1` for `VF-3T0K-DR5O`; it is not a token shortage fail and did not block B publish.
- Legacy `out/cycle_alerts/checklist_B.csv` and manifest `health_summary` still show stale pre-correction counts; active gate evidence is `out/cycle_alerts/checklist_B_split.csv` and B log split-health lines.

## Safety Boundary
- Do not write Google Sheets.
- Do not run overlapping B scripts while B owner is active.
- Request B maintenance, wait for `out/locks/maintenance.ready`, then apply corrections.
- After correction, run one boundary-safe B proof with `B_RUN_ONCE=1`.

## Tests And Proof
- Passed: `pytest tests/test_t030_apply_approved_token_corrections.py tests/test_b007_allocate_tokens_live.py tests/test_b009_apply_stock_adjustments_to_tokens.py -q`.
- Passed: `python -m py_compile scripts/one_off/T030_apply_approved_token_corrections.py`.
- Dry run passed: 6 correction rows, 8 created tokens, 0 skipped.
- Applied under B maintenance handoff at `2026-05-06T08:27:41Z`: 8 created tokens, 0 skipped.
- Backup written: `out/backups/manual_token_corrections_20260506T082741Z/token_ledger_live.pre_correction.csv`.
- Live owner proof cycle: `B_20260506T083023Z`, finalized at `2026-05-06T08:39:10Z`.
- Proof result: `out/token_shortages_by_sku.csv` has header only, `out/orders_missing_tokens.csv` has header only, `out/health_order_master_placeholder_cogs.csv` has header only.
- B split checklist proof: `token_shortages_by_sku=ok 0`, `order_master_placeholder_cogs_rows=ok 0`, `order_master_missing_token_no_placeholder_rows=ok 0`.
- Note: B auto-cut over to split health mode during the proof run. `out/cycle_alerts/checklist_B_split.csv` is the active gate artifact. Legacy `out/cycle_alerts/checklist_B.csv` still contains stale pre-correction rows.

## Verification Status
- 2026-05-06 code fix applied: yes.
- 2026-05-06 correction applied: yes.
- 2026-05-06 isolated verification: passed.
- 2026-05-06 live loop verification: confirmed.
- 2026-05-10 code fix applied: yes.
- 2026-05-10 correction applied: yes.
- 2026-05-10 isolated verification: passed.
- 2026-05-10 live loop verification: confirmed.
- Next verifier: no further action needed now.
