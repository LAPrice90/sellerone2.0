# B Repair Package - API Refund Fee Shipping ROI Proof - 2026-05-31

## Manager Authority
- task_id: MGR_B_repair_b_refund_fee_shipping_roi_api_proof
- job_ref: B-API-REFUND-FEE
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `sellerone_manager/sellerboard_bridge.py` - `sellerone_manager/hourly_mot.py` - `sellerone_manager/multi_flow.py` - `sellerone_manager/b_marketplace_coverage.py` - focused B manager tests under `tests/manager/` - B manager proof documentation under `plans/active/sellerone-manager-control-plane-v1/`
- forbidden_actions: - Do not run or restart B. - Do not edit B locks or maintenance markers. - Do not write Google Sheets. - Do not correct order, token, refund, fee, shipping, stock, or ROI data. - Do not align local DB facts. - Do not delete outputs. - Do not merge recovered orders into live data. - Do not use Sellerboard bridge values as final ROI or restocking truth. - Do not change prices or queues. - Do not widen into A, E, H, F, or O.
- proof_required: - Read current API-backed proof files from outside the B loop. - Add or confirm explicit manager/MOT proof labels for refunds: - `api_proved` - `sellerboard_bridge_only` - `not_yet_proven` - Add or confirm explicit manager/MOT proof labels for fees: - commission API proof - FBA fee API proof - other fee API proof where available - `not_yet_proven` where unavailable - Add or confirm explicit manager/MOT proof labels for shipping: - shipping income API proof - shipping fee API proof - `not_yet_proven` where unavailable - Add or confirm ROI confidence output so E/O can tell whether ROI is: - API-backed and safe - bridge-labelled only - not yet proven - Retest through B independent MOT. - Keep the B warning if API proof is still incomplete. Do not hide it downstream.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: - Use git diff for code rollback. - Revert only touched manager/MOT proof code or test files if the labels are wrong. - Do not edit business output files to make the warning disappear. - Rerun the read-only B MOT after rollback.
- stop_condition: - Stop when the manager has a clear API-proof map for refund, fee, shipping, and ROI ingredients, or when the missing API proof is explicitly labelled as not proven. - Stop immediately if the repair would require B live execution, B restart, data correction, local DB alignment, Sheets, output deletion, ROI substitution, prices, queues, or scope widening.

## Source
- source_type: repair_package
- source_id: B_REPAIR_PACKAGE_B_REFUND_FEE_SHIPPING_ROI_API_PROOF_20260531
- source_path: plans\active\sellerone-manager-control-plane-v1\B_REPAIR_PACKAGE_B_REFUND_FEE_SHIPPING_ROI_API_PROOF_20260531.md

## Exact Source Row
```json
{
  "source_id": "B_REPAIR_PACKAGE_B_REFUND_FEE_SHIPPING_ROI_API_PROOF_20260531",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\B_REPAIR_PACKAGE_B_REFUND_FEE_SHIPPING_ROI_API_PROOF_20260531.md"
}
```
