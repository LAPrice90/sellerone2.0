# F Repair Package - Source Proof Refresh - 2026-05-31

## Manager Authority
- task_id: MGR_F_repair_f_source_proof_refresh
- job_ref: F-SOURCE-REFRESH-2026
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `sellerone_manager/hourly_mot.py` - F manager/source-proof reporting code under `sellerone_manager/` - focused F manager tests under `tests/manager/` - this package and `CODING_PLAN.md` for proof notes
- forbidden_actions: - Do not run F061. - Do not edit F061 queue state. - Do not approve scanner handoff. - Do not fetch Gmail or delete Gmail. - Do not download supplier files. - Do not move, delete, or rewrite supplier files. - Do not write Google Sheets. - Do not change prices or queues. - Do not align local DB facts. - Do not delete outputs. - Do not restart workers. - Do not use a separate login browser workaround.
- proof_required: - Keep current scanner heartbeat and live owner state separate from source-proof freshness. - If a safe manager-only proof refresh exists, run it and retest F through MOT. - If refresh requires supplier downloads, Gmail fetch, F061, queue edits, handoff approval, or worker restart, park it and leave the stale proof warning visible. - Success means F MOT can explain scanner state and source-proof state without raw scanner chaos.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: - Use git diff for code rollback. - Do not rewrite F outputs to make source proof look fresh. - Rerun the read-only F MOT after rollback.
- stop_condition: - Stop when F source-proof warnings are either cleared by safe manager proof or parked as stale source-proof work with protected boundaries named. - Stop immediately if the work requires F061, queue edits, Gmail fetch/deletion, supplier downloads, output deletion, Sheets, prices, local DB alignment, worker restart, business judgement, or scope widening.

## Source
- source_type: repair_package
- source_id: F_REPAIR_PACKAGE_F_SOURCE_PROOF_REFRESH_20260531
- source_path: plans\active\sellerone-manager-control-plane-v1\F_REPAIR_PACKAGE_F_SOURCE_PROOF_REFRESH_20260531.md

## Exact Source Row
```json
{
  "source_id": "F_REPAIR_PACKAGE_F_SOURCE_PROOF_REFRESH_20260531",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\F_REPAIR_PACKAGE_F_SOURCE_PROOF_REFRESH_20260531.md"
}
```
