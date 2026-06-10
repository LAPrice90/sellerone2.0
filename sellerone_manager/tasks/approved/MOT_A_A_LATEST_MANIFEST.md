# A MOT: a_latest_manifest needs repair

## Manager Authority
- task_id: MOT_A_A_LATEST_MANIFEST
- job_ref: A-MANIFEST
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: A runner proof only; do not run A unless a flow-owned proof window is approved.
- forbidden_actions: no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a_latest_manifest` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow A
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_A_A_LATEST_MANIFEST
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\manifests\A\2026-06-09\20260609T095535Z.json

## Exact Source Row
```json
{
  "allowed_scope": "A runner proof only; do not run A unless a flow-owned proof window is approved.",
  "check": "a_latest_manifest",
  "created_utc": "2026-05-26T17:33:01Z",
  "flow": "A",
  "forbidden_actions": "no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening",
  "job_ref": "A-MANIFEST",
  "last_seen_utc": "2026-06-09T11:38:22Z",
  "luke_action_required": "0",
  "manager_action": "If fail, inspect the manifest stopped step before trusting downstream data.",
  "notes": "partial",
  "observed_utc": "2026-06-09T11:38:22Z",
  "priority": "high",
  "producer": "scripts/cycles/run_A_all.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a_latest_manifest` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow A",
  "root_cause_guess": "A manifest is stale or not completed.",
  "safe_repair_boundary": "A runner proof only; do not run A unless a flow-owned proof window is approved.",
  "seen_count": "141",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\manifests\\A\\2026-06-09\\20260609T095535Z.json",
  "status": "new",
  "title": "A MOT: a_latest_manifest needs repair",
  "updated_utc": "2026-06-09T11:38:22Z",
  "work_item_id": "MOT_A_A_LATEST_MANIFEST"
}
```
