# F MOT: f_source_intake_chain_proof needs repair

## Manager Authority
- task_id: MOT_F_F_SOURCE_INTAKE_CHAIN_PROOF
- job_ref: F-SOURCE-INTAKE-CHAIN
- status: in_progress
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Source intake proof only; metadata/read-status checks only; no remote supplier check, no price-file download, no ready-source import, no supplier file move/delete, no F061 run, no queue edit, no Sheet write, no price change, no output deletion, no local DB alignment, and no worker restart.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_source_intake_chain_proof` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_SOURCE_INTAKE_CHAIN_PROOF
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\test_mode\source_acquisition_status.csv

## Exact Source Row
```json
{
  "allowed_scope": "Source intake proof only; metadata/read-status checks only; no remote supplier check, no price-file download, no ready-source import, no supplier file move/delete, no F061 run, no queue edit, no Sheet write, no price change, no output deletion, no local DB alignment, and no worker restart.",
  "check": "f_source_intake_chain_proof",
  "created_utc": "2026-06-02T10:30:40Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "job_ref": "F-SOURCE-INTAKE-CHAIN",
  "last_seen_utc": "2026-06-04T12:14:29Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded F source-intake task for the failed supplier proof.",
  "notes": "failed=1",
  "observed_utc": "2026-06-04T12:14:29Z",
  "priority": "high",
  "producer": "FPM010_check_acquisition_sources.py / FPM011_import_ready_sources.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_source_intake_chain_proof` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "At least one active F supplier source is reporting failed or config-needed source intake proof.",
  "safe_repair_boundary": "Source intake proof only; metadata/read-status checks only; no remote supplier check, no price-file download, no ready-source import, no supplier file move/delete, no F061 run, no queue edit, no Sheet write, no price change, no output deletion, no local DB alignment, and no worker restart.",
  "seen_count": "244",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\test_mode\\source_acquisition_status.csv",
  "status": "in_progress",
  "title": "F MOT: f_source_intake_chain_proof needs repair",
  "updated_utc": "2026-06-04T12:14:29Z",
  "work_item_id": "MOT_F_F_SOURCE_INTAKE_CHAIN_PROOF"
}
```
