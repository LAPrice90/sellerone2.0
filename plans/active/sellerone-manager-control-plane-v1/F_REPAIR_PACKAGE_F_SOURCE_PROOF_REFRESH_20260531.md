# F Repair Package - Source Proof Refresh - 2026-05-31

## Root Cause Summary
- F scanner ownership is not the current problem.
- F child heartbeat is fresh and the live owner state is running.
- The open F issue is stale source-proof evidence for source intake, URL source proof, email source proof, and queue recommendation explanation.
- This should be handled as one source-proof package, not as scanner repair or queue work.

## Approved Check
- `f_source_proof_refresh`

## Allowed Files For A Future Repair Batch
- `sellerone_manager/hourly_mot.py`
- F manager/source-proof reporting code under `sellerone_manager/`
- focused F manager tests under `tests/manager/`
- this package and `CODING_PLAN.md` for proof notes

## Forbidden Files And Actions
- Do not run F061.
- Do not edit F061 queue state.
- Do not approve scanner handoff.
- Do not fetch Gmail or delete Gmail.
- Do not download supplier files.
- Do not move, delete, or rewrite supplier files.
- Do not write Google Sheets.
- Do not change prices or queues.
- Do not align local DB facts.
- Do not delete outputs.
- Do not restart workers.
- Do not use a separate login browser workaround.

## Proof Path For A Future Repair
- Keep current scanner heartbeat and live owner state separate from source-proof freshness.
- If a safe manager-only proof refresh exists, run it and retest F through MOT.
- If refresh requires supplier downloads, Gmail fetch, F061, queue edits, handoff approval, or worker restart, park it and leave the stale proof warning visible.
- Success means F MOT can explain scanner state and source-proof state without raw scanner chaos.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow F

## Rollback Path
- Use git diff for code rollback.
- Do not rewrite F outputs to make source proof look fresh.
- Rerun the read-only F MOT after rollback.

## Stop Condition
- Stop when F source-proof warnings are either cleared by safe manager proof or parked as stale source-proof work with protected boundaries named.
- Stop immediately if the work requires F061, queue edits, Gmail fetch/deletion, supplier downloads, output deletion, Sheets, prices, local DB alignment, worker restart, business judgement, or scope widening.
