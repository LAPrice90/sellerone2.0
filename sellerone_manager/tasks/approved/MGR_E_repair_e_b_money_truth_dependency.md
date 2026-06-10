# E Repair Package - Confidence And ROI Consumption Safety - 2026-05-31

## Manager Authority
- task_id: MGR_E_repair_e_b_money_truth_dependency
- job_ref: E-CONFIDENCE-AND-ROI
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `sellerone_manager/hourly_mot.py` - focused E manager tests under `tests/manager/` - `tests/test_e_confidence_outputs.py` if E confidence helper coverage needs a narrow test - this package and `CODING_PLAN.md` for proof notes
- forbidden_actions: - Do not run E live. - Do not fake ROI fill. - Do not hide missing profit proof downstream. - Do not make business reorder decisions. - Do not write Google Sheets. - Do not change prices or queues. - Do not align local DB facts. - Do not delete outputs. - Do not widen into A, B, H, F, or O worker logic.
- proof_required: - Add or confirm an E manager/MOT check that reads the B money-proof labels as outside evidence. - The check should say whether E ROI/restock outputs are safe, warning-labelled, or not yet money-proven. - If B money proof is bridge-only or not yet proven, E must remain warning-labelled instead of pretending ROI is clean business truth. - Existing E confidence fields must stay intact: - `profit_confidence` - `sales_truth_state` - `stock_signal` - `restock_business_ready` - `missing_reason` - Retest E through independent MOT.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: - Use git diff for code rollback. - Do not rewrite E output files to make a warning disappear. - Rerun the read-only E MOT after rollback.
- stop_condition: - Stop when E MOT clearly shows whether upstream B money proof is `api_backed_safe`, `sellerboard_bridge_only`, `bridge_labelled_only`, or `not_yet_proven`. - Stop immediately if the work would require an E live run, data correction, local DB alignment, Sheets, prices, queues, output deletion, business judgement, or scope widening.

## Source
- source_type: repair_package
- source_id: E_REPAIR_PACKAGE_E_CONFIDENCE_ROI_CONSUMPTION_SAFETY_20260531
- source_path: plans\active\sellerone-manager-control-plane-v1\E_REPAIR_PACKAGE_E_CONFIDENCE_ROI_CONSUMPTION_SAFETY_20260531.md

## Exact Source Row
```json
{
  "source_id": "E_REPAIR_PACKAGE_E_CONFIDENCE_ROI_CONSUMPTION_SAFETY_20260531",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\E_REPAIR_PACKAGE_E_CONFIDENCE_ROI_CONSUMPTION_SAFETY_20260531.md"
}
```
