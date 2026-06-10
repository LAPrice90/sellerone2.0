# A MOT: a_manifest_step_traversal needs repair

## Manager Authority
- task_id: MOT_A_A_MANIFEST_STEP_TRAVERSAL
- job_ref: A-MANIFEST-STEP-TRAVERSAL
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: A runner manifest finalizer only; no worker data changes.
- forbidden_actions: no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a_manifest_step_traversal` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow A
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_A_A_MANIFEST_STEP_TRAVERSAL
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\A\2026-06-09\20260609T095535Z.json

## Exact Source Row
```json
{
  "allowed_scope": "A runner manifest finalizer only; no worker data changes.",
  "check": "a_manifest_step_traversal",
  "created_utc": "2026-05-26T17:33:01Z",
  "flow": "A",
  "forbidden_actions": "no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening",
  "job_ref": "A-MANIFEST-STEP-TRAVERSAL",
  "last_seen_utc": "2026-06-09T11:38:22Z",
  "luke_action_required": "0",
  "manager_action": "If fail, create a bounded A repair task for the first missing or stopped step.",
  "notes": "3/11",
  "observed_utc": "2026-06-09T11:38:22Z",
  "priority": "high",
  "producer": "scripts/cycles/run_A_all.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a_manifest_step_traversal` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow A",
  "root_cause_guess": "A did not traverse every configured step.",
  "safe_repair_boundary": "A runner manifest finalizer only; no worker data changes.",
  "seen_count": "141",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\A\\2026-06-09\\20260609T095535Z.json",
  "status": "new",
  "title": "A MOT: a_manifest_step_traversal needs repair",
  "updated_utc": "2026-06-09T11:38:22Z",
  "work_item_id": "MOT_A_A_MANIFEST_STEP_TRAVERSAL"
}
```
