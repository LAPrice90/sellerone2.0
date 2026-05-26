# Storage Housekeeping Implementation Plan

## Current Phase
- Phase: approved live H/B safe recovery
- Started UTC: 2026-05-25T09:45:00Z
- Goal: extend the existing housekeeping tool into a registry-backed storage cleanup system with dry-run proof, directory-family cleanup, storage health output, and future-cycle agent rules.

## Allowed Files
- `scripts/tools/log_housekeeping.py`
- `project_control/log_housekeeping_registry.json`
- `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md`
- `AGENTS.md`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `tests/test_log_housekeeping.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/cycles/run_H_pricing_cycle.py`
- `out/systems/F/inbox/suppliers/stocklist_supplier/manifest.json`
- `project_control/storage_housekeeping/CODING_PLAN.md`

## Safety Rules
- No Google Sheets changes.
- No local database alignment changes.
- `out/sql/sellerone_dev.sqlite3` must remain protected.
- Live apply must stay dry-run-first and fail closed when blocker state is unknown.
- Directory deletion is allowed only for registry-declared families that are inside the repo and outside the housekeeping output folder.
- Existing user/runtime changes in the dirty worktree must not be reverted.

## Proof Checklist
- `python -m py_compile scripts\tools\log_housekeeping.py` - passed
- `python -m pytest tests\test_log_housekeeping.py -q` - passed, 10 tests
- `python scripts\tools\log_housekeeping.py` - passed in dry-run mode
- Confirm latest storage outputs exist - passed:
  - `out/housekeeping/storage_housekeeping_report.latest.csv`
  - `out/housekeeping/storage_housekeeping_actions.latest.csv`
  - `out/housekeeping/storage_housekeeping_summary.latest.json`
  - `out/housekeeping/storage_health.latest.csv`

## Latest Dry-Run Evidence
- Latest dry-run UTC: 2026-05-25T10:58:33Z
- Mode: dry-run, no files deleted
- Total scanned items: 166635
- Decisions: keep 4571, would_delete 342, blocked_by_safety 161442, unknown_unclassified 280
- Candidate delete recovery: 7188279 bytes
- Apply status: blocked safely because H is unfinalized
- Storage health: 13 PASS, 2 WARN, 0 FAIL

## Flow-Hook Rollout Evidence
- Updated UTC: 2026-05-25T15:35:30Z
- FPM130 now runs `python scripts/tools/log_housekeeping.py --flow F` in dry-run mode when the live owner exits its lock.
- H cycle now runs `python scripts/tools/log_housekeeping.py --flow H` in dry-run mode only after successful finalizer confirmation.
- Flow hook status files are written as `out/housekeeping/storage_housekeeping_hook.<FLOW>.latest.json`.
- F-only dry-run: 798 scanned items, 9 PASS, 0 WARN, 0 FAIL.
- H-only dry-run: 166621 scanned items, 10 PASS, 1 WARN, 0 FAIL.
- Central dry-run UTC: 2026-05-25T15:33:24Z, 166725 scanned items, 17 PASS, 1 WARN, 0 FAIL.
- Central dry-run mode only: no files deleted.
- Candidate delete recovery remains 7188279 bytes, but apply is blocked while H is unfinalized.
- Focused verification passed: `python -m py_compile scripts\tools\log_housekeeping.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\cycles\run_H_pricing_cycle.py`.
- Focused regression passed: `python -m pytest tests\test_log_housekeeping.py tests\test_fpm130_live_cycle.py tests\test_h_worker_lifecycle_contract.py -q` returned 136 passed.
- F source-hash warning was resolved by narrowing raw-source scope and adding `out/systems/F/inbox/suppliers/stocklist_supplier/manifest.json`.
- H stale recovery was dry-run only: `out/locks/recovery/HB_safe_recover_background.latest.json` says H has no live owner and would clear `H_run_in_progress.txt`; B ownership would be preserved.

## Open Non-Blocking Warnings
- Trigger/time to check: next storage-housekeeping rollout pass before enabling live apply.
- Artifact to inspect: `out/housekeeping/storage_health.latest.csv`.
- Success condition: no `FAIL`; WARNs either resolved or explicitly accepted.
- Current WARN 1: 280 legacy H-live unclassified items older than the 7-day fail window.
- Resolved WARN: F raw inbox source-hash sidecar evidence is now complete for the scanned supplier source folders.
- Remediation path if this fails: add or tighten registry rules for the named output family, then rerun `python scripts\tools\log_housekeeping.py` in dry-run mode before any apply.

## Live Monitoring Target
- No live-loop ownership change is required for this implementation.
- Central housekeeping is introduced as dry-run-first tooling; automatic destructive scheduling is not enabled in this phase.
- Next live adoption step is to run approved H stale-runtime recovery, then rerun central dry-run and only then consider `--apply-safe`.

## Approved Live Recovery - 2026-05-26
- Trigger/time: user approved `proceed` on 2026-05-26.
- Target artifact to inspect: `out/locks/recovery/HB_safe_recover_background.latest.json`.
- Success condition: stale H runtime marker cleared, H/B/monitor ownership proof recorded, and storage housekeeping dry-run returns 0 FAIL.
- Remediation path if it fails: leave `--apply-safe` disabled, inspect the recovery report, and do not delete cleanup candidates until H ownership state is clear.

## Restart And MOT Schedule Investigation - 2026-05-26
- Trigger/time: user asked whether the restart schedule was working and asked to check MOT logs.
- Evidence inspected:
  - `out/locks/restart_control/restart_controller.latest.json`
  - `out/cycle_alerts/morning_mot_system_check.json`
  - `out/cycle_alerts/morning_mot_system_check.csv`
  - Windows scheduled tasks `AMZ Controlled Restart`, `AMZ Morning MOT Post Restart`, `AMZ Morning MOT Post A`, and `AMZ H Cycle`.
- Finding: `AMZ Controlled Restart` did run at `2026-05-26T01:10:01Z`, but skipped the reboot/restart path because stale H markers produced `H_RUN_IN_PROGRESS_NOT_FINALIZED` and `H_LAUNCHER_HEARTBEAT_STALE`.
- Finding: `AMZ H Cycle` is disabled. This explains the restart-controller `h_cycle_task_relaunch_reason=failed_rc_1` and blocks reliable future H relaunch after overnight restart.
- Finding: MOT scheduled tasks had last result `1` because `project_control/DUE_CHECK_REGISTER.csv` had a hidden BOM/quoted `check_id` header that `scripts/tools/due_check_register.py` did not normalize.
- Fix applied: `scripts/tools/due_check_register.py` now normalizes BOM/quoted headers; `tests/test_due_check_register.py` covers that parser edge case.
- Proof:
  - `python -m py_compile scripts\tools\due_check_register.py scripts\tools\morning_mot_system.py scripts\tools\log_housekeeping.py` passed.
  - `python -m pytest tests\test_due_check_register.py tests\test_morning_mot_system.py tests\test_log_housekeeping.py -q` passed with 26 tests.
  - Manual MOT command returned `rc=0`, `status=warn`, `fail_rows=0`, `warn_rows=1`.
  - Task Scheduler start of `AMZ Morning MOT Post Restart` returned task result `0` and refreshed MOT logs at `2026-05-26T07:08:50Z`.
- Blocked admin action: re-enabling `AMZ H Cycle` failed with `Access is denied` from both `Enable-ScheduledTask` and `schtasks /Change`, so the next check is recorded in `project_control/DUE_CHECK_REGISTER.csv`.
- Storage safety note: central housekeeping dry-run now blocks apply with `apply_allowed=False`, `apply_block_reason=h_lock_active`, so cleanup will not delete H-adjacent files while H has an active lock.

## Restart Schedule Admin Fix - 2026-05-26
- Operator action received: user re-enabled `AMZ H Cycle` from elevated PowerShell.
- Codex verification UTC: 2026-05-26T08:40:23Z.
- Evidence:
  - Windows Task Scheduler reports `AMZ H Cycle` state `Ready`.
  - Fresh MOT run returned `rc=0`, `fail_rows=0`, `warn_rows=1`.
  - H MOT row says `status=ok`, `runtime_mode=RUNNING`, `task_state=Ready`, and `task_enabled=True`.
- Due-check update:
  - `OPS_ENABLE_AMZ_H_CYCLE_TASK_20260526` marked `completed`.
  - `OPS_CONTROLLED_RESTART_H_RELAUNCH_PROOF_20260527` added for the next overnight proof window.
- Next proof trigger: after the 2026-05-27 02:10 UK controlled restart window.
- Artifact to inspect: `out/locks/restart_control/restart_controller.latest.json`.
- Success condition: the latest restart controller run after `2026-05-27T01:10:00Z` does not end with `h_cycle_task_relaunch_reason=failed_rc_1`, and the MOT H row remains `task_enabled=True`.
- Remediation path if it fails: inspect Windows Task Scheduler permissions for `AMZ H Cycle` and the controlled restart controller task context before relying on restart recovery.

## Single MOT File And Restart Hardening - 2026-05-26
- Trigger/time: user asked to neaten MOT checks into one file and make restart less fragile because the PC must not stay on for days.
- Root cause of missed restart: the 2026-05-26 controlled restart fired, but stale H evidence produced `H_RUN_IN_PROGRESS_NOT_FINALIZED` and `H_LAUNCHER_HEARTBEAT_STALE`; H relaunch then failed because `AMZ H Cycle` was disabled, so the controller skipped with no reboot attempt.
- Single MOT file added: `out/cycle_alerts/morning_mot_latest.md`.
- Compatibility outputs kept:
  - `out/cycle_alerts/morning_mot_system_check.csv`
  - `out/cycle_alerts/morning_mot_system_check.json`
  - `out/cycle_alerts/morning_mot_repair_actions.json`
- Restart hardening applied:
  - stale H marker-only blockers can be overridden during the controlled restart window.
  - `run_controlled_restart_controller.bat` now defaults `CONTROLLED_RESTART_FORCE_REBOOT_ON_SKIP=1`.
  - the MOT single file shows both the latest restart run settings and the current fallback/override settings.
- Proof:
  - `python -m py_compile scripts\tools\morning_mot_system.py scripts\tools\controlled_restart_controller.py` passed.
  - `python -m pytest tests\test_morning_mot_system.py tests\test_controlled_restart_controller.py tests\test_controlled_restart_gate.py -q` passed with 12 tests.
  - MOT rerun wrote `out/cycle_alerts/morning_mot_latest.md` at `2026-05-26T08:51:45Z` with `0 FAIL`, `1 WARN`.
  - Task Scheduler proof for `AMZ Morning MOT Post A` returned last result `0` and refreshed the single MOT file at `2026-05-26T08:53:10Z`.
  - Windows uptime check showed `LastBootLocal=2026-05-26 08:33:36 +01:00`, so the PC has rebooted recently and is not currently on a week-long uptime.
- Next proof trigger: after the 2026-05-27 02:10 UK controlled restart window.
- Artifact to inspect: `out/locks/restart_control/restart_controller.latest.json` and `out/cycle_alerts/morning_mot_latest.md`.
- Success condition: restart controller latest run after `2026-05-27T01:10:00Z` has `reboot_attempted=true` or outcome starts with `reboot_command_submitted`, does not end with `h_cycle_task_relaunch_reason=failed_rc_1`, and the single MOT file shows H `task_enabled=True`.
- Remediation path if it fails: inspect `stale_h_restart_override_applied`, `force_reboot_on_skip_requested`, `home_time_mode_active`, Windows shutdown permissions, and the `AMZ Controlled Restart` task context.

## Quiet Codex Automation Consolidation - 2026-05-26
- Trigger/time: user asked to replace multiple SellerOne Codex automation conversations with one quiet local-log automation.
- Active SellerOne automation created:
  - `sellerone-quiet-daily-log`
  - Name: `SellerOne Quiet Daily Log`
  - Schedule: daily at 06:55 local
  - Workspace: `C:\Users\Luke\Desktop\SellerOne 2.0`
  - Output files:
    - `out/cycle_alerts/codex_quiet_automation.latest.md`
    - `out/cycle_alerts/codex_quiet_automation.latest.json`
    - `out/cycle_alerts/codex_quiet_automation.log.jsonl`
- SellerOne automations paused:
  - `daily-f-ai-review-queue-manager`
  - `f032-codex-ai-review-gate`
  - `o-net-fee-restock-mot-check`
  - `monday-restocking-pickup`
- Unrelated automation left active:
  - `welsh-daily-planner`
- Quiet rule: routine status must be written to local log files. User-facing interruption is only for new FAIL, materially worse WARN, contradictory evidence, or a required user decision.
- Next proof trigger: after the first `sellerone-quiet-daily-log` run on 2026-05-27 at 06:55 UK.
- Artifact to inspect: `out/cycle_alerts/codex_quiet_automation.latest.md`.
- Success condition: latest quiet automation output exists, has an observed time after `2026-05-27T05:55:00Z`, and no superseded SellerOne automation has returned to `ACTIVE`.
- Remediation path if it fails: inspect `C:\Users\Luke\.codex\automations\sellerone-quiet-daily-log\automation.toml`, then either fix the quiet prompt or temporarily reactivate the specific paused automation that owns the missed work.
