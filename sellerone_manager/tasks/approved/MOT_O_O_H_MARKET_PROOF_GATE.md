# O MOT: o_h_market_proof_gate needs repair

## Manager Authority
- task_id: MOT_O_O_H_MARKET_PROOF_GATE
- job_ref: O-MARKET-GATE
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Controlled technical H pause/resume and O candidate-only market proof are allowed only inside a manager-approved proof packet; no purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action.
- forbidden_actions: no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_h_market_proof_gate` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_O_O_H_MARKET_PROOF_GATE
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\O\live\restock_market_refresh_candidates_live.csv;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_pricing_cycle.lock;C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock

## Exact Source Row
```json
{
  "allowed_scope": "Controlled technical H pause/resume and O candidate-only market proof are allowed only inside a manager-approved proof packet; no purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action.",
  "check": "o_h_market_proof_gate",
  "created_utc": "2026-05-27T14:40:23Z",
  "flow": "O",
  "forbidden_actions": "no purchase commitment; no receiving action; no send-to-Amazon action; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no business decision; no uncontrolled worker restart; no market proof scan outside a manager-approved controlled proof packet; no scope widening",
  "last_seen_utc": "2026-05-27T15:41:01Z",
  "luke_action_required": "0",
  "manager_action": "Create a manager-approved controlled proof packet: pause H only inside the packet, run the candidate-only market proof, then prove H scheduler ownership resumed.",
  "notes": "ready_candidates=59;h_active=1",
  "observed_utc": "2026-05-27T15:41:01Z",
  "priority": "normal",
  "producer": "O021 market-refresh bridge / H pricing owner lock",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow O` and confirm `o_h_market_proof_gate` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow O",
  "root_cause_guess": "O has ready market-proof candidates, but H currently owns the market files.",
  "safe_repair_boundary": "Controlled technical H pause/resume and O candidate-only market proof are allowed only inside a manager-approved proof packet; no purchase, send-to-Amazon, price, queue, Sheet, DB, or output-deletion action.",
  "seen_count": "14",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\O\\live\\restock_market_refresh_candidates_live.csv;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\H\\live\\H_pricing_cycle.lock;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\H_pricing_cycle.lock",
  "status": "new",
  "title": "O MOT: o_h_market_proof_gate needs repair",
  "updated_utc": "2026-05-27T15:41:01Z",
  "work_item_id": "MOT_O_O_H_MARKET_PROOF_GATE"
}
```
