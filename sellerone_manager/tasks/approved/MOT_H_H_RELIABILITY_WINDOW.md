# H MOT: h_reliability_window needs repair

## Manager Authority
- task_id: MOT_H_H_RELIABILITY_WINDOW
- job_ref: H-RELIABILITY-WINDOW-02
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.
- forbidden_actions: no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_reliability_window` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_H_H_RELIABILITY_WINDOW
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T131521Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T124421Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T115921Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T113000Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T110424Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T102323Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T095736Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T092003Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T085129Z.json;C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\H\2026-06-09\H_20260609T081944Z.json

## Exact Source Row
```json
{
  "allowed_scope": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "check": "h_reliability_window",
  "created_utc": "2026-06-04T11:00:24Z",
  "flow": "H",
  "forbidden_actions": "no H run; no scheduler ownership changes; no publish; no price changes; no queue edits; no Google Sheets writes; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "job_ref": "H-RELIABILITY-WINDOW",
  "last_seen_utc": "2026-06-09T14:00:37Z",
  "luke_action_required": "0",
  "manager_action": "If fail, package the exact failed or ambiguous H run proof. If warn, keep H provisional until the window is clean enough.",
  "notes": "window_runs=10;clean_runs=0;warned_runs=8;failed_runs=2;target_clean_runs=8",
  "observed_utc": "2026-06-09T14:00:37Z",
  "priority": "high",
  "producer": "H manifest reliability window",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow H` and confirm `h_reliability_window` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow H",
  "root_cause_guess": "At least one recent H manifest in the reliability window failed or is ambiguous.",
  "safe_repair_boundary": "H manager proof only; no H run, scheduler ownership change, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart.",
  "seen_count": "273",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T131521Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T124421Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T115921Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T113000Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T110424Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T102323Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T095736Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T092003Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T085129Z.json;C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\H\\2026-06-09\\H_20260609T081944Z.json",
  "status": "new",
  "title": "H MOT: h_reliability_window needs repair",
  "updated_utc": "2026-06-09T14:00:37Z",
  "work_item_id": "MOT_H_H_RELIABILITY_WINDOW"
}
```
