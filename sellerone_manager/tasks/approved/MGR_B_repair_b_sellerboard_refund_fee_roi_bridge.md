# B Repair Package - Refund Fee Shipping ROI Proof - 2026-05-31

## Manager Authority
- task_id: MGR_B_repair_b_sellerboard_refund_fee_roi_bridge
- job_ref: B-REFUND-FEE-SHIPPING
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `sellerone_manager/sellerboard_bridge.py` - `sellerone_manager/hourly_mot.py` - `sellerone_manager/multi_flow.py` - focused B manager tests under `tests/manager/` - B proof documentation under `plans/active/sellerone-manager-control-plane-v1/`
- forbidden_actions: - Do not run or restart B. - Do not edit B locks or maintenance markers. - Do not write Google Sheets. - Do not correct token, order, refund, fee, shipping, stock, or ROI data. - Do not align local DB facts. - Do not delete outputs. - Do not merge recovered orders into live data. - Do not feed Sellerboard bridge values into live ROI or restocking as final truth. - Do not change prices or queues. - Do not widen into A, E, H, F, or O.
- proof_required: - Add or confirm explicit proof labels for refund evidence: - `API proved` - `Sellerboard bridge estimate` - `not yet proven` - Add or confirm explicit proof labels for fee and shipping evidence: - commission - FBA fee - shipping income or shipping fee where relevant - Add or confirm ROI confidence labels so downstream E/O logic can tell the difference between clean API-backed ROI and bridge-only estimates. - Keep Sellerboard values as outside comparison or bridge evidence only. - Retest through B independent MOT, not by editing final reports.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: - Use git diff for code rollback. - Do not rewrite business output files to make the warning disappear. - If proof labels are wrong, revert the manager proof-label code and rerun the read-only B MOT.
- stop_condition: - Stop when the manager can clearly say which refund, fee, shipping, and ROI values are API-proved, bridge-only, or not yet proven. - Stop immediately if the repair would require a protected action: B run, B restart, data correction, local DB alignment, Sheets, output deletion, ROI substitution, prices, queues, or scope widening.

## Source
- source_type: repair_package
- source_id: B_REPAIR_PACKAGE_MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE_20260531
- source_path: plans\active\sellerone-manager-control-plane-v1\B_REPAIR_PACKAGE_MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE_20260531.md

## Exact Source Row
```json
{
  "source_id": "B_REPAIR_PACKAGE_MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE_20260531",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\B_REPAIR_PACKAGE_MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE_20260531.md"
}
```
