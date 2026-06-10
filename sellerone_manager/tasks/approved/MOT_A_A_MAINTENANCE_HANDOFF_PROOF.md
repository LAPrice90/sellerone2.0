# A MOT: a_maintenance_handoff_proof needs repair

## Manager Authority
- task_id: MOT_A_A_MAINTENANCE_HANDOFF_PROOF
- job_ref: A-MAINTENANCE-HANDOFF
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: A runner proof-writing only; do not create, delete, or edit lock files from MOT.
- forbidden_actions: no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a_maintenance_handoff_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow A
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_A_A_MAINTENANCE_HANDOFF_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\A\live\a_maintenance_handoff_latest.json

## Exact Source Row
```json
{
  "allowed_scope": "A runner proof-writing only; do not create, delete, or edit lock files from MOT.",
  "check": "a_maintenance_handoff_proof",
  "created_utc": "2026-05-27T09:08:07Z",
  "flow": "A",
  "forbidden_actions": "no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening",
  "job_ref": "A-MAINTENANCE-HANDOFF",
  "last_seen_utc": "2026-06-09T11:38:22Z",
  "luke_action_required": "0",
  "manager_action": "If fail, treat A/B handoff safety as blocked. If not_checked, keep it as a proof-mapping gap until the next full A-owned run writes this artifact.",
  "notes": "fail",
  "observed_utc": "2026-06-09T11:38:22Z",
  "priority": "high",
  "producer": "scripts/cycles/run_A_all.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a_maintenance_handoff_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow A",
  "root_cause_guess": "Latest A maintenance handoff proof recorded an unsafe or failed handoff.",
  "safe_repair_boundary": "A runner proof-writing only; do not create, delete, or edit lock files from MOT.",
  "seen_count": "139",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\A\\live\\a_maintenance_handoff_latest.json",
  "status": "new",
  "title": "A MOT: a_maintenance_handoff_proof needs repair",
  "updated_utc": "2026-06-09T11:38:22Z",
  "work_item_id": "MOT_A_A_MAINTENANCE_HANDOFF_PROOF"
}
```
