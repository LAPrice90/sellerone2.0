# B MOT: b_refund_return_token_bridge needs repair

## Manager Authority
- task_id: MOT_B_B_REFUND_RETURN_TOKEN_BRIDGE
- job_ref: B-REFUND-TOKEN-BRIDGE-02
- status: blocked_needs_luke
- authority: standing_safe_code_repair
- luke_action_required: 1

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
  "last_seen_utc": "2026-06-03T11:31:32Z",
  "luke_action_required": "1",
  "manager_action": "Build or repair the read-only return-token bridge. Do not create tokens, run B, write Sheets, align the DB, or let unproved stock recovery affect ROI/restocking.",
  "notes": "B009 apply stopped before write: active B owner is present and fresh read-only proof shows B008 status did not persist in current token ledger. Need Luke-approved B maintenance handoff before any further local token repair writes.",
  "observed_utc": "2026-06-03T11:31:32Z",
  "priority": "normal",
  "producer": "B038_build_refund_return_token_bridge.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_refund_return_token_bridge` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "Refund money, Amazon return proof, and token-return proof do not fully agree yet.",
  "safe_repair_boundary": "B refund return-token proof only; no B run, Sheet write, local DB alignment, output deletion, token correction, price change, queue edit, or live ROI/restocking use.",
  "seen_count": "18",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_return_token_bridge.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\B\\refunds\\b_refund_return_token_summary.csv",
  "status": "blocked_needs_luke",
  "title": "B MOT: b_refund_return_token_bridge needs repair",
  "updated_utc": "2026-06-03T11:32:00Z",
  "work_item_id": "MOT_B_B_REFUND_RETURN_TOKEN_BRIDGE"
}
```
