# F BBP Iframe Progress Stall v1

## Manager Authority
- task_id: MGR_F_BBP_IFRAME_PROGRESS_STALL_V1
- job_ref: F-BBP-IFRAME-STALL
- flow: F
- task_type: bounded_f_worker_repair
- priority: high
- status: proved
- authority: manager_visible_f_scanner_progress_repair
- luke_action_required: 0

## Boundary
- allowed_scope: F BBP/browser evidence detection and manager-visible stall proof only. Make the scanner classify BBP iframe/profile/plugin failure clearly instead of looping as if normal catch-up is moving.
- forbidden_actions: Do not run F061 manually. Do not restart workers. Do not clear locks. Do not edit the F061 queue or active_run files. Do not approve handoff. Do not fetch or download supplier files. Do not write Google Sheets. Do not change prices. Do not align local DB facts. Do not delete outputs. Do not open a separate browser.
- proof_required: F must show whether the 106 catching-up rows are genuinely being scanned, waiting for BBP iframe/plugin recovery, waiting for login, or blocked by page evidence. A fresh heartbeat must not hide repeated BBP iframe/profile failure.
- retest_command: python -m pytest tests/test_f061_run_legacy_first_checks_local.py tests/test_fpm130_live_cycle.py tests/manager/test_hourly_mot.py -k "bbp or iframe or login or progress or f_" -q
- rollback_path: Use git diff for code rollback. Do not alter live scanner outputs to make status look better.
- stop_condition: Stop when the stall reason is code-tested and manager-visible, or stop immediately if proving it requires a live F061 run, worker restart, browser opening, queue edit, output deletion, Sheets, prices, local DB alignment, or scope widening.

## Current Evidence
- The operator UI shows DHB catching up with 106 rows, but the number did not fall after refresh.
- The F child process heartbeat is fresh, so the process is alive.
- The child stderr shows repeated BBP iframe preflight failures while the scanner keeps the browser hidden.
- The same stderr also reports `F061_BBP_PROFILE_HEALTH ok=False reason=buybotpro_extension_missing`.
- The live event stream has not yet shown a newer scanner chunk reducing the 106 catching-up rows.

## Intended Rule
The F manager should say one of these plain states:
- scanning rows, when real scanner chunks are completing
- alive but no row progress, when only heartbeat is fresh
- BBP iframe/plugin blocked, when the browser profile cannot expose BBP proof
- waiting for login, when a real login page is detected
- protected decision needed, only when Luke must choose or approve a live proof window

## Worker Instructions
1. Inspect the BBP iframe/profile health checks in the F061 path.
2. Find why `buybotpro_extension_missing` and repeated iframe preflight failures are not becoming a clear blocked state.
3. Add or adjust read-only proof so FPM130/FPM170/MOT can show `BBP iframe/plugin blocked` instead of generic catching up.
4. Keep the normal scanner-owned browser path. Do not add a separate Chrome login workaround.
5. Add focused tests for extension missing, iframe missing, login detected, and real scanner progress.
6. Retest with offline/unit tests and read-only manager outputs only.
