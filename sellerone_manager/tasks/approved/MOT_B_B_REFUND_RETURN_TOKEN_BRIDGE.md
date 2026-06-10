# B MOT: b_refund_return_token_bridge needs repair

## Manager Authority
- task_id: MOT_B_B_REFUND_RETURN_TOKEN_BRIDGE
- job_ref: B-REFUND-TOKEN-BRIDGE
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B refund return-token proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_return_token_bridge` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_REFUND_RETURN_TOKEN_BRIDGE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_return_token_bridge.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\B\refunds\b_refund_return_token_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B refund return-token proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.",
  "check": "b_refund_return_token_bridge",
  "created_utc": "2026-06-03T09:44:50Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-REFUND-TOKEN-BRIDGE",
  "last_seen_utc": "2026-06-04T16:03:08Z",
  "luke_action_required": "0",
  "manager_action": "Build or repair the read-only return-token bridge. Do not create tokens, run B, write Sheets, align the DB, or let unproved stock recovery affect ROI/restocking.",
  "notes": "Luke approved the protected B correction bundle. Generic bridge card is now actively covered by B-DAMAGED-RETURN-REUSE and B-ORIGINAL-B009-REVIEW; stock-adjustment-only lane is proved-safe excluded from ROI/restocking.",
  "observed_utc": "2026-06-04T16:03:08Z",
  "priority": "normal",
  "producer": "B038_build_refund_return_token_bridge.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_return_token_bridge` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Refund money, Amazon return proof, and token-return proof do not fully agree yet.",
  "safe_repair_boundary": "B refund return-token proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.",
  "seen_count": "243",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_return_token_bridge.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_return_token_summary.csv",
  "status": "in_progress",
  "title": "B MOT: b_refund_return_token_bridge needs repair",
  "updated_utc": "2026-06-04T16:04:19Z",
  "work_item_id": "MOT_B_B_REFUND_RETURN_TOKEN_BRIDGE"
}
```
