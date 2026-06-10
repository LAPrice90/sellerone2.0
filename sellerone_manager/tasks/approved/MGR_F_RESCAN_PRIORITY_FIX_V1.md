# F Rescan Priority Fix v1

## Manager Authority
- task_id: MGR_F_RESCAN_PRIORITY_FIX_V1
- job_ref: F-RESCAN-PRIORITY
- flow: F
- task_type: bounded_f_worker_repair
- priority: high
- status: proved
- authority: luke_confirmed_rescan_same_cycle_intent
- luke_action_required: 0

## Boundary
- allowed_scope: F RESCAN queue logic, F scanner timeout policy for RESCAN only, F manager/MOT visibility for RESCAN proof, and focused F tests.
- forbidden_actions: Do not run F061. Do not restart workers. Do not edit the live F061 queue or active_run files. Do not force already parked TD Synnex rows back into the live queue without a separate protected proof window. Do not approve handoff. Do not fetch Gmail, download supplier files, write Google Sheets, change prices, align local DB facts, delete outputs, or open a separate login browser.
- proof_required: RESCAN must mean same-cycle retry after temporary internet, login, or page-load trouble. RESCAN must not be treated as a 30-day cooldown. If a row cannot be retried safely after the allowed same-cycle retry attempts, it must become a clear failed/blocked timeout state, not stay labelled as active RESCAN. The manager must show how many RESCAN rows are retry-now, exhausted, parked, or blocked.
- retest_command: python -m pytest tests/test_f061_run_legacy_first_checks_local.py tests/manager/test_hourly_mot.py -k "rescan or f_" -q
- rollback_path: Use git diff for code rollback. Do not rewrite live queue outputs to make existing TD Synnex rows look fixed.
- stop_condition: Stop when future RESCAN behavior is code-tested and manager-visible, or stop immediately if the fix requires live queue mutation, a worker restart, a live F061 proof run, queue editing, output deletion, Sheets, prices, local DB alignment, or scope widening.

## Current Evidence
- TD Synnex currently has RESCAN rows recorded in live screening evidence.
- The active TD Synnex queue has zero active `rescan_retry_required` rows.
- `config/feeder/f_scanner_timeout_policy.csv` currently sets `RESCAN` to a 30-day fixed wait.
- F061 currently treats `F061_RESCAN_MAX_ACTIVE_ATTEMPTS=2` as only one retry because attempt 1 is already considered exhausted.

## Intended Rule
RESCAN means:
- the row had a temporary scan problem, such as internet loss, login interruption, page load failure, or missing transient evidence
- it should be tried again in the current cycle as soon as the temporary issue is clear
- it should sit ahead of normal new rows, similar to YES/NO recovery
- it should have a bounded retry limit so it cannot loop forever

RESCAN does not mean:
- wait 30 days
- quietly skip the row
- hide the issue as normal timeout cooldown

If the row still cannot be completed after the allowed same-cycle retries, it should become a clear failed or blocked timeout state with a real reason.

## Worker Instructions
1. Inspect the existing F061 same-cycle retry logic and timeout policy before editing.
2. Fix the retry-limit comparison so the configured max active attempts means what it says.
3. Remove the 30-day RESCAN cooldown behavior from future queue eligibility or reclassify exhausted RESCAN rows into a real fail/timeout reason.
4. Add tests proving:
   - first RESCAN is requeued ahead of normal pending rows
   - second allowed RESCAN still retries when max attempts allows it
   - exhausted RESCAN does not remain labelled as a normal active RESCAN
   - RESCAN does not generate a 30-day cooldown as its normal behavior
   - manager proof can show retry-now versus exhausted/parked counts
5. Retest only with offline/unit tests and read-only manager MOT proof.
6. Do not touch the already-running TD Synnex queue unless Luke separately approves a protected live queue repair/proof window.
