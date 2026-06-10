# H MOT: h_terminal_publish_truth needs repair

## Manager Authority
- task_id: MOT_H_H_TERMINAL_PUBLISH_TRUTH
- job_ref: H-TERMINAL-PUBLISH-TRUTH
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_terminal_publish_truth` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_TERMINAL_PUBLISH_TRUTH
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_cycle_last_terminal_info.txt;C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_cycle_last_publish_info.txt

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_terminal_publish_truth",
  "created_utc": "2026-05-27T22:00:20Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "job_ref": "H-TERMINAL-PUBLISH-TRUTH",
  "last_seen_utc": "2026-06-09T12:48:40Z",
  "luke_action_required": "0",
  "manager_action": "If fail, package a bounded H terminal/publish proof task. Do not publish or rerun H from MOT.",
  "notes": "terminal_state=failed",
  "observed_utc": "2026-06-09T12:48:40Z",
  "priority": "high",
  "producer": "H finalizer and publish marker",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_terminal_publish_truth` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "H terminal marker does not show a finalized state.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "141",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\H\\live\\H_cycle_last_terminal_info.txt;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\H\\live\\H_cycle_last_publish_info.txt",
  "status": "new",
  "title": "H MOT: h_terminal_publish_truth needs repair",
  "updated_utc": "2026-06-09T12:48:40Z",
  "work_item_id": "MOT_H_H_TERMINAL_PUBLISH_TRUTH"
}
```
