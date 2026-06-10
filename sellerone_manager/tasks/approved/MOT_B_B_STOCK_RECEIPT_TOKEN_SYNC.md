# B MOT: b_stock_receipt_token_sync needs repair

## Manager Authority
- task_id: MOT_B_B_STOCK_RECEIPT_TOKEN_SYNC
- job_ref: B-STOCK-RECEIPT-TOKEN
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: B/A receipt-token proof only; no B run or restart, no Sheet write, no token or stock correction, no order edit, no local DB alignment, no output deletion, no price or queue change.
- forbidden_actions: no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_stock_receipt_token_sync` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_B_B_STOCK_RECEIPT_TOKEN_SYNC
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\stock_receipts_latest.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\token_allocations_live.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\order_master.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\orders_missing_tokens.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\A\2026-06-07\20260607T050059Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\b_stock_receipt_token_sync\b_stock_receipt_intake_preview_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "B/A receipt-token proof only; no B run or restart, no Sheet write, no token or stock correction, no order edit, no local DB alignment, no output deletion, no price or queue change.",
  "check": "b_stock_receipt_token_sync",
  "created_utc": "2026-06-04T16:54:04Z",
  "flow": "B",
  "forbidden_actions": "no B run or restart; no lock or maintenance marker edits; no Google Sheets writes; no price or queue changes; no token/data correction; no local DB alignment; no output deletion; no scope widening",
  "job_ref": "B-STOCK-RECEIPT-TOKEN",
  "last_seen_utc": "2026-06-07T17:28:32Z",
  "luke_action_required": "0",
  "manager_action": "Create or continue a bounded B receipt/token proof task. If a Sheet receipt row needs a new order key or a correction, stop for Luke because that changes stock facts. If this is only allocation/order-master timing, retest after the next normal B boundary proof.",
  "notes": "allocated_missing_token_rows=1;allocated_order_master_placeholder_rows=1",
  "observed_utc": "2026-06-07T17:28:32Z",
  "priority": "normal",
  "producer": "B007_allocate_tokens_live.py / B004_build_order_master.py / process_stock_receipts_sheet.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B` and confirm `b_stock_receipt_token_sync` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
  "root_cause_guess": "B has a receipt/token proof gap: either receipt intake is not current, or a later token allocation has not yet cleared the missing-token/order-master evidence.",
  "safe_repair_boundary": "B/A receipt-token proof only; no B run or restart, no Sheet write, no token or stock correction, no order edit, no local DB alignment, no output deletion, no price or queue change.",
  "seen_count": "80",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\stock_receipts_latest.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\token_allocations_live.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\order_master.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\orders_missing_tokens.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\A\\2026-06-07\\20260607T050059Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\M\\b_stock_receipt_token_sync\\b_stock_receipt_intake_preview_summary.csv",
  "status": "new",
  "title": "B MOT: b_stock_receipt_token_sync needs repair",
  "updated_utc": "2026-06-07T17:28:32Z",
  "work_item_id": "MOT_B_B_STOCK_RECEIPT_TOKEN_SYNC"
}
```
