# SO21 Task Scheduler New-Style Review

Job: `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW`
Created: 2026-06-09
Role: SellerOne 2.1 Worker
Mode: read-only review

## Plain-English Status

This review classifies the visible SellerOne-related Windows scheduled tasks against the SellerOne 2.1 control style.

Think of Task Scheduler like a breaker panel. Some switches appear to run the business machine itself. Some switches appear to run status checks or control reports. Some switches are old, one-shot, or unclear. This file labels those switches, but it does not flip any of them.

No Task Scheduler task was enabled, disabled, edited, deleted, created, restarted, or run by this review. No runtime, process, worker, script, queue, price, Sheet, database, output, Amazon/security, purchase, receiving, or send-to-Amazon state was changed.

## Evidence Used

- `CONTROL/RUNTIME_CONTROL.md`
- `CONTROL/SO21_SCHEDULER_STATE_RECONCILIATION.md`
- `CONTROL/SO21_SCRIPT_STATUS_HEALTH_MAP.md`
- `CONTROL/DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md`
- `CONTROL/WINDOWS_SCHEDULER_PAUSE_DECISION.md`
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`
- `tasks/approved/MGR_SO21_TASK_SCHEDULER_NEW_STYLE_REVIEW.md`
- `CONTROL/SO21_TASK_SCHEDULER_NEW_STYLE_REVIEW_REVIEW.md`
- Read-only Windows Task Scheduler metadata through `Get-ScheduledTask` and `Get-ScheduledTaskInfo`
- Fresh read-only targeted check for `Start Amazon Script` and `C:\Users\Luke\Desktop\run_firstCheck.bat`

## Current Read-Only Scheduler Snapshot

Observed local date: 2026-06-09

Visible SellerOne/Codex-related task count: 13.

| Task | Current state | Last run time | Next run time | Last result | Action |
|---|---|---|---|---:|---|
| `AMZ Controlled Restart` | Ready | 2026-06-09 02:10:01 | 2026-06-10 02:10:00 | 0 | `cmd.exe /c C:\Users\Luke\Desktop\SELLER~1.0\run_controlled_restart_controller.bat` |
| `AMZ H Cycle` | Ready | 2026-06-09 08:07:39 | blank | 0 | `cmd.exe /c "C:\Users\Luke\Desktop\SellerOne 2.0\run_H_cycle.bat"` |
| `AMZ Morning MOT Post A` | Ready | 2026-06-09 06:30:01 | 2026-06-10 06:30:00 | 0 | `cmd.exe /d /c call "C:\Users\Luke\Desktop\SellerOne 2.0\run_morning_mot_system.bat" --phase post_a --repair --proof-wait-seconds 30` |
| `AMZ Morning MOT Post Restart` | Ready | 2026-06-09 02:35:01 | 2026-06-10 02:35:00 | 0 | `cmd.exe /d /c call "C:\Users\Luke\Desktop\SellerOne 2.0\run_morning_mot_system.bat" --phase post_restart --repair --proof-wait-seconds 30` |
| `AMZ Orders` | Ready | 2026-06-09 02:27:38 | blank | 0 | `cmd.exe /c "C:\Users\Luke\Desktop\SellerOne 2.0\run_B_cycle.bat"` |
| `AMZ Price List Manager` | Ready | 2026-06-09 02:32:32 | blank | 0 | `cmd.exe /c "C:\Users\Luke\Desktop\SellerOne 2.0\run_F_price_list_manager_cycle.bat"` |
| `AMZ Pricing Summary` | Ready | 2026-06-09 06:00:01 | 2026-06-10 06:00:00 | 0 | `cmd.exe /c "C:\Users\Luke\Desktop\SellerOne 2.0\run_A_all.bat"` |
| `AMZ Pricing Summary Hourly` | Running | 2026-06-09 07:52:01 | 2026-06-09 08:52:00 | 2147946720 | `cmd.exe /c C:\Users\Luke\Desktop\SELLER~1.0\run_A_all.bat` |
| `AMZ Restart Postcheck` | Disabled | 1958-08-15 13:50:15 | 2026-06-10 02:20:00 | 0 | `cmd.exe /c C:\Users\Luke\Desktop\SELLER~1.0\run_controlled_restart_postcheck.bat` |
| `Codex_H_Phase1_OneShot` | Disabled | 1958-08-16 21:59:40 | blank | 4294967295 | `C:\Temp\codex_h_phase1_run.cmd` |
| `CodexHProbe_20260327_005911` | Ready | 1958-08-18 12:30:14 | blank | 0 | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Temp\h_scheduler_probe.20260327T005911Z.schedprobe.ps1` |
| `SellerOne Manager Hourly MOT` | Ready | 2026-06-09 08:00:01 | 2026-06-09 09:00:00 | 0 | `C:\Users\Luke\Desktop\SellerOne 2.0\run_manager_hourly_mot.bat` |
| `Start Amazon Script` | Ready | 2026-06-09 02:27:38 | blank | 1 | `cmd /c "C:\Users\Luke\Desktop\run_firstCheck.bat"` |

## Style Categories

| Category | Plain-English meaning | Boundary |
|---|---|---|
| Business Runtime | A task appears to run selling, pricing, orders, scanner, A/B/F/H, or restart-chain work. | Review only. Any scheduler or runtime change needs explicit Luke approval and a named approved packet. |
| Control Desk Automation | A task appears to read and report control evidence, such as MOT, Rep briefing, health checks, queue visibility, or operations reporting. | May be redesigned later as SellerOne 2.1 control automation, but no Windows scheduler change is approved here. |
| Maintenance Protected | A task appears installer-like, one-shot, restart-control-related, or too sensitive to classify as a normal control automation. | Do not touch until a separate approved review names the exact action. |
| Retire/legacy candidate | A task appears old, duplicated, short-path, one-shot, or outside the clean 2.1 control style. | Candidate only. Retirement, deletion, disablement, or replacement still needs approval. |
| Needs rewrite into SellerOne 2.1 control automation | A useful control purpose exists, but the task should not stay as an old Windows scheduler or repair-style entrypoint. | Redesign only. New automation should be paused-first and approval-gated. |
| Unknown/protected-review | The task is visible but purpose, owner, or proof path is unclear. | Treat as protected until classified. |

## Task Classifications

| Task | New-style classification | Evidence source | Recommendation | Protected boundary |
|---|---|---|---|---|
| `AMZ Controlled Restart` | Business Runtime | `RUNTIME_CONTROL.md`; current scheduler action points to `run_controlled_restart_controller.bat`. | Keep under protected restart-chain runtime. Do not rebuild as routine control-desk automation. | No pause, enable, disable, edit, delete, create, run, or restart without explicit Luke approval and a named maintenance/restart packet. |
| `AMZ H Cycle` | Business Runtime | `RUNTIME_CONTROL.md`; `SO21_SCRIPT_STATUS_HEALTH_MAP.md`; current scheduler action points to `run_H_cycle.bat`. | Keep as protected H runtime. Future 2.1 work should use H packets and proof gates, not a casual scheduler tweak. | No scheduler or H runtime change. No price, Sheet, database, Amazon, or H output change. |
| `AMZ Morning MOT Post A` | Needs rewrite into SellerOne 2.1 control automation | Current action runs `run_morning_mot_system.bat --phase post_a --repair`; health map says it should inspect evidence and must not become a hidden A runner. | Redesign as a paused-first Operations control check that reads evidence only. Remove repair-style behavior only through a future approved implementation packet. | No scheduler edit here. No A script run. No MOT output hand-edit. No hidden A repair. |
| `AMZ Morning MOT Post Restart` | Needs rewrite into SellerOne 2.1 control automation | Current action runs `run_morning_mot_system.bat --phase post_restart --repair`; health map says it should confirm evidence after restart, not restart anything itself. | Redesign as a paused-first restart evidence check. Keep restart actions separate from reporting. | No scheduler edit here. No restart. No postcheck run. No runtime change. |
| `AMZ Orders` | Business Runtime | `RUNTIME_CONTROL.md`; health map links it to `run_B_cycle.bat` and B order/token proof. | Keep as protected B runtime. Any future ownership change needs B lock/ownership proof and approval. | No B script run. No order, token, Sellerboard, local DB, Product DB, or Google Sheets alignment. |
| `AMZ Price List Manager` | Business Runtime | `RUNTIME_CONTROL.md`; health map links it to `run_F_price_list_manager_cycle.bat`. | Keep as protected F runtime. Future F work should go through approved F packets and script-owned login/session rules. | No scanner restart. No Amazon security bypass. No price or queue action. |
| `AMZ Pricing Summary` | Business Runtime | Current action points to `run_A_all.bat`; runtime safety says A is source-fact refresh and must not be run ad hoc. | Rename/classify carefully in future because the name sounds like reporting but the action runs A source-fact refresh. Keep protected. | No A run. No price, Sheet, database, manifest, or output change. |
| `AMZ Pricing Summary Hourly` | Business Runtime and Retire/legacy candidate | Current state is `Running`; action points to short path `SELLER~1.0\run_A_all.bat`; reconciliation flagged short-path risk. | Treat as protected live A runtime first. Separately review whether the short-path duplicate belongs in modern SellerOne 2.1 control. | No process kill. No scheduler change. No A run/restart. No attempt to interrupt the current running state. |
| `AMZ Restart Postcheck` | Business Runtime and Maintenance Protected | `RUNTIME_CONTROL.md`; current action points to `run_controlled_restart_postcheck.bat`; current state is Disabled. | Keep protected restart-chain postcheck. It may belong in a future maintenance record model, not a general automation. | No enable, disable, edit, delete, run, or restart without explicit approval. |
| `Codex_H_Phase1_OneShot` | Maintenance Protected and Retire/legacy candidate | Current action points to `C:\Temp\codex_h_phase1_run.cmd`; one-shot style; disabled with failed-looking historical result. | Do not resume. Classify under a separate legacy H scheduler review before any retirement or cleanup proposal. | No deletion, no disable/delete cleanup, no run, no scheduler edit, no temp-file cleanup. |
| `CodexHProbe_20260327_005911` | Unknown/protected-review and Maintenance Protected | Added by scheduler reconciliation as extra unmapped task; current action points to `C:\Temp\h_scheduler_probe.20260327T005911Z.schedprobe.ps1`. | Open a separate classification packet if this task matters. Until then, treat as protected and unmapped. | No run, no disable, no delete, no cleanup of `C:\Temp` script, no trust as official H proof. |
| `SellerOne Manager Hourly MOT` | Control Desk Automation and Needs rewrite into SellerOne 2.1 control automation | `RUNTIME_CONTROL.md`; health map links it to manager MOT proof under `out/systems/M/mot/`; current action points to `run_manager_hourly_mot.bat`. | Keep the purpose but redesign under the 2.1 Operations model so it reports evidence and feeds packets, not old manager noise. Paused-first automation design is preferred over blindly trusting the Windows task. | No scheduler edit here. No MOT repair from the scheduler. No queue edit except approved packet status evidence. |
| `Start Amazon Script` | Unknown/protected-review and Retire/legacy candidate | Reviewer evidence plus fresh read-only check: task is Ready, uses a logon trigger, action is `cmd /c "C:\Users\Luke\Desktop\run_firstCheck.bat"`, and `C:\Users\Luke\Desktop\run_firstCheck.bat` is currently missing. The name says Amazon, but the missing target means this is scheduler-clutter/evidence risk until a separate owner review proves otherwise. | Do not run or repair. Open a separate classification/removal decision packet if Luke wants this old logon task handled. Treat the missing target as evidence of drift, not permission to recreate the script or change the task. | No run, enable, disable, edit, delete, create, restart, script implementation, Amazon login/security action, or target-file cleanup/recreation. |

## Repair Note - 2026-06-09

Reviewer blocker addressed narrowly.

- Added `Start Amazon Script` to the scheduler snapshot and classification table.
- Fresh read-only evidence confirmed the task is `Ready`, has a logon trigger, runs `cmd /c "C:\Users\Luke\Desktop\run_firstCheck.bat"`, last result is `1`, and the local target file is not present.
- No scheduler state, runtime state, process, script, queue, price, Sheet, database, output, Amazon/security, purchase, receiving, or send-to-Amazon state was changed.
- Backup preserved before this repair: `CONTROL/SO21_TASK_SCHEDULER_NEW_STYLE_REVIEW.md.before_start_amazon_repair_20260609T091519.bak`.

## Main Findings

1. The visible scheduler layer is not quiet.
   - The latest read-only check found 9 Ready tasks, 1 Running task, and 2 Disabled tasks.
   - Older pause proof is historical and must not be treated as current machine truth.

2. Some task names are misleading.
   - `AMZ Pricing Summary` and `AMZ Pricing Summary Hourly` sound like reporting, but both point to `run_A_all.bat`.
   - In plain English, those are not harmless dashboard labels. They appear connected to A source-fact refresh and must stay protected.

3. Repair-style MOT scheduler actions do not fit the clean 2.1 style.
   - `AMZ Morning MOT Post A` and `AMZ Morning MOT Post Restart` include `--repair`.
   - The 2.1 style should separate inspection from repair. MOT should be the inspector, not the worker doing hidden fixes.

4. The old Windows scheduler should not be treated as the future control desk.
   - Useful control checks can be redesigned as Operations evidence readers.
   - New recurring control automation should be created paused-first, then activated only after exact approval.

5. Unknown or one-shot Codex/H scheduler tasks remain protected.
   - `Codex_H_Phase1_OneShot` and `CodexHProbe_20260327_005911` should not be run, deleted, disabled, enabled, or trusted until separately classified.

6. `Start Amazon Script` is a protected scheduler-clutter risk.
   - It is Ready and Amazon-named, but the action target `C:\Users\Luke\Desktop\run_firstCheck.bat` is missing.
   - In plain English, this looks like a switch wired to a missing appliance. The safe repair here is to label the switch, not rebuild or flip it.

## Recommended Follow-Up Packets

| Proposed packet | Purpose | Boundary |
|---|---|---|
| `SO21-SCHEDULER-DRIFT-CAUSE-INVESTIGATION` | Find why the eight previously paused tasks became Ready again, using read-only evidence first. | No scheduler changes, no process kills, no runtime restart. |
| `SO21-CODEX-H-PROBE-SCHEDULER-CLASSIFICATION` | Classify `CodexHProbe_20260327_005911` and decide whether it belongs in SellerOne 2.1 at all. | No scheduler changes, no temp-file cleanup. |
| `SO21-MOT-SCHEDULER-REWRITE-DESIGN` | Redesign `AMZ Morning MOT Post A`, `AMZ Morning MOT Post Restart`, and `SellerOne Manager Hourly MOT` as clean Operations evidence checks. | Design only unless a later approved implementation packet exists. |
| `SO21-A-SCHEDULER-DUPLICATE-SHORTPATH-REVIEW` | Review `AMZ Pricing Summary` vs `AMZ Pricing Summary Hourly`, especially the `SELLER~1.0` short-path action. | No A run, no scheduler change, no output edits. |
| `SO21-START-AMAZON-SCRIPT-SCHEDULER-CLASSIFICATION` | Decide whether `Start Amazon Script` is old Amazon scheduler clutter, a missing-file setup remnant, or a still-needed protected logon task. | No scheduler changes, no Amazon login/security action, no script recreation, no cleanup without explicit approval. |

## Verification

- This review exists at `CONTROL/SO21_TASK_SCHEDULER_NEW_STYLE_REVIEW.md`.
- Every visible SellerOne/Codex/Amazon-related scheduled task found by the current read-only scheduler metadata checks is listed and classified, including `Start Amazon Script`.
- Recommendations are review-only.
- No Task Scheduler state was changed.
- No runtime pause, runtime restart, process kill, worker restart, script implementation, deletion, movement, compression, purge, archive apply, output cleanup, Amazon/security action, price change, Google Sheets write, database alignment, purchase, receiving, or send-to-Amazon action was performed.

## Current Next Move

Recommendation:

- continue with reviewer retest for `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW`.
