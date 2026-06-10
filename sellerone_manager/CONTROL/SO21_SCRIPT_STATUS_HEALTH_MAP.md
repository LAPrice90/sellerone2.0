# SO21 Script Status Health Map

Job: `SO21-SCRIPT-STATUS-HEALTH-MAP`
Created: 2026-06-09
Mode: read-only planning

## Plain-English Purpose

This file is SellerOne's first script and check health map.

Think of it like a noticeboard beside the machine room. It does not press any buttons. It lists the important scripts and checks, what they are meant to prove, where their proof should appear, how quickly that proof can go stale, and the safest repair route when something looks wrong.

This map does not change Task Scheduler, runtime, workers, queues, databases, Google Sheets, prices, outputs, Amazon, or security state.

## Evidence Used

- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- `CONTROL/RUNTIME_CONTROL.md`
- `CONTROL/SO21_SCHEDULER_STATE_RECONCILIATION.md`
- `CONTROL/DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md`
- `CONTROL/AUTOMATION_REBUILD.md`
- `CONTROL/SO21_RUNTIME_STATUS_READONLY_DESIGN.md`
- `CONTROL/SO21_MAINTENANCE_RECORD_SPEC.md`
- `../out/systems/M/mot/mot_latest.md`
- `../out/systems/M/mot/mot_latest.csv`
- `tasks/approved/MGR_SO21_SCRIPT_STATUS_HEALTH_MAP.md`

## Current Safety Note

Scheduler state has changed across reports.

Older evidence said several SellerOne scheduled tasks were disabled. A later read-only reconciliation on 2026-06-08 found most mapped tasks back in `Ready` state, plus one extra unmapped task named `CodexHProbe_20260327_005911`.

Plain-English rule: use `CONTROL/SO21_SCHEDULER_STATE_RECONCILIATION.md` as the latest scheduler-state clue before any future decision. Do not use this health map to pause, enable, disable, restart, edit, or delete any scheduled task.

## Health Map

| Script or check | Purpose | Owner | Proof output | Stale threshold | Failure threshold | Safe repair route |
|---|---|---|---|---|---|---|
| `run_manager_hourly_mot.bat` / `SellerOne Manager Hourly MOT` | Runs the manager MOT view that watches A/B/E/H/F/O evidence from outside the business flows. | Control Desk / Operations | `../out/systems/M/mot/mot_latest.md`, `.csv`, `.json`, and history files | Roughly 1 hour during active monitoring, because the scheduler name says hourly | Missing MOT output, unreadable output, or MOT status with fail/decision rows that are not mapped into packets | Treat as control evidence first. Create or use a bounded SO21 MOT/control packet. Do not repair A/B/E/H/F/O from the MOT itself. |
| `run_morning_mot_system.bat --phase post_a` / `AMZ Morning MOT Post A` | Morning MOT after A-side work or restart timing. It should inspect evidence, not become a hidden A runner. | Control Desk / A evidence | MOT files under `../out/systems/M/mot/` and any phase-specific MOT proof named by the scheduler action | Same day for morning proof | Missing proof after expected morning window, repair-style MOT action without approved packet, or stale A failures remaining unclassified | Use A approved packets such as `A-MANIFEST`, `A-MAINTENANCE-HANDOFF`, or `A-MANIFEST-STEP-TRAVERSAL`. Do not run A ad hoc unless Luke or a proof packet approves it. |
| `run_morning_mot_system.bat --phase post_restart` / `AMZ Morning MOT Post Restart` | MOT after restart chain timing. It should confirm evidence after restart, not restart anything itself. | Control Desk / Restart evidence | MOT files under `../out/systems/M/mot/` and restart post-check evidence where named | Same day for restart-window proof | Missing proof after restart window or contradiction between restart evidence and current scheduler/runtime evidence | Use a runtime-control or scheduler-state packet. Do not restart runtime from this map. |
| `run_A_all.bat` / `AMZ Pricing Summary` / `AMZ Pricing Summary Hourly` | A source-fact refresh for listings, catalog, inventory, fees, and pricing-support intelligence. | A | A outputs and SQL-compatible proof checked by A MOT rows, including latest manifest, inventory, fee, catalog, listing, and daily-intel proof | Same day for daily source facts unless a specific A check says otherwise | A manifest partial/stale, manifest step traversal incomplete, unsafe A/B maintenance handoff, stale lock beyond active run | Use the matching A approved packet. Inspect the stopped manifest step before trusting downstream data. Do not run A manually without explicit approval or an approved proof packet. |
| `run_B_cycle.bat` / `AMZ Orders` | B order, token, refund, Sellerboard comparison, and order-truth cycle. | B | B order outputs, B manifests, token and COGS proof, Sellerboard bridge proof, and B MOT rows | Same day for active order proof; per-marketplace cursor proof should be current enough that quiet marketplaces are not hidden | Missing/stale marketplace cursors, active maintenance marker while B owner present, order truth incomplete, unsafe token/order correction need | Use B approved packets and B independent MOT first. Check ownership and locks before any manual B script. Protected token/order/DB alignment repairs need Luke. |
| `run_F_price_list_manager_cycle.bat` / `AMZ Price List Manager` | F price-list manager and supplier/scanner flow. | F | F manager snapshot, F child scanner heartbeat, F login mode proof, source intake proof, queue controls, and F MOT rows | Current during scanner work; login/session proof should not be treated as healthy if owner is alive with no progress | RESCAN rows parked behind timeout, live owner alive with no progress, login still required, Seller Central auth warning, BBP iframe/plugin blocked | Use F approved packets such as browser session durability, DHB progress, or MFA cooldown policy. Keep login recovery on the script-owned path. Do not open a separate browser or bypass security. |
| `run_H_cycle.bat` / `AMZ H Cycle` | H pricing/repricing cycle and related proof. | H | H manifest, boundary/finalizer proof, owner proof, terminal/publish markers, reliability window, and H MOT rows | Recent run-window proof, not only latest-run proof | Reliability window not clean enough, manager readiness warnings, unclear floor-source proof, contradictory terminal/publish markers | Keep H repairs parked or packeted until the independent H manager/MOT layer is ready. Do not change prices, Sheets, DB facts, or H runtime from this map. |
| `run_O_operator_ui.bat` and O proof checks | O user/restocking readiness and operator-facing proof. | O | O active restock proof files, user-working readiness checks, PO preview proof, supplier proof, profit input labels, and O MOT rows | Current enough for user-facing review; active proof files should not be stale when O is being presented as ready | Stale active restock proof files, safety blockers, weak profit inputs, inbound/FBA cost gaps, token cost trust gaps | Use O approved repair packets. Do not create purchase orders, receive stock, send to Amazon, write Sheets, change prices, align DBs, or patch outputs. |
| E analytics checks | E ROI, restock intelligence, performance, and sales-truth confidence. | E | E manifest, run log, ROI/performance/restock/study outputs, confidence labels, and E MOT rows | Recent successful analytics run tied to latest manifest | Missing/stale required outputs, stale lock, B money dependency warning treated as clean truth | Use E independent MOT and E approved packets. Keep bridge-only money proof warning-labelled until B money proof is API-backed. |
| `SO21-REP-BRIEFING` | Active Rep briefing pilot. Reads control files and tells Luke only about real decisions or material blockers. | Rep / Control Desk | Briefing output from the Codex automation and control-file summaries | Twice daily or on demand, based on automation plan | First scheduled briefing run not proved, or briefing starts doing worker/runtime/protected work | Prove the first scheduled briefing run through `SO21-REP-BRIEFING-FIRST-RUN-PROOF`. Do not expand automations before the pilot is reviewed. |
| `SO21-HEALTH-WATCHER` candidate | Future health watcher concept. Would read MOT and control state and report material changes only. | Operations / Control Desk | Future control summary, not built yet | Hourly during working window if Luke approves pilot | Any design that repairs MOT rows, starts workers, changes scheduler, or writes business data | Keep as candidate paused-first automation. Needs Luke approval before creation or activation. |
| `SO21-STORAGE-CUSTODIAN` candidate | Future storage pressure report. | Custodian | `CONTROL/STORAGE_INDEX*.csv`, `CONTROL/CUSTODIAN_DRY_RUN_MANIFEST.*`, storage summaries | Weekly if Luke approves pilot | Any cleanup apply, deletion, movement, compression, purge, archive apply, or protected output touch | Measure and report only. Any cleanup needs exact manifest, recovery route, live-owner checks, and Luke approval. |
| `SO21-USAGE-REPORTER` candidate | Future AI usage-pressure summary. | Custodian | `CONTROL/AI_USAGE.csv` and `CONTROL/AI_USAGE.md` | Weekly if Luke approves pilot | Claims real billing without a billing source, restarts automations, or starts new tasks | Report pressure only. Do not claim cost truth or restart automations. |
| `SO21-REVIEW-WATCHER` candidate | Future review-ready ticket watcher. | Reviewer / Control Desk | Current tickets and packet proof routes | Triggered only by stable review-ready state | Edits code, runs workers, or changes protected state | Keep deferred until the queue exposes a stable review-ready lane. |
| `run_controlled_restart_controller.bat` / `AMZ Controlled Restart` | Restart-chain runtime task. | Business Runtime / Restart chain | Restart controller logs and post-restart proof where named by runtime-control packets | Only trusted inside a named maintenance/restart window | Missing restart proof, stale postcheck, or mismatch between scheduler state and maintenance record | Requires maintenance record and explicit authority. Do not restart from this map. |
| `run_controlled_restart_postcheck.bat` / `AMZ Restart Postcheck` | Restart-chain postcheck. | Business Runtime / Restart chain | Postcheck output where named by restart proof packet | Same restart window | Missing or stale postcheck after an approved restart | Use a restart or runtime-control packet. Do not enable or run scheduled task from this map. |
| `run_H_maintenance_controller_install.bat` / `scripts/tools/install_h_maintenance_controller.ps1` | Installer-like H maintenance controller entrypoint. | Maintenance Protected | Install proof only when a separate approved packet names it | Not applicable until approved use | Any attempt to install, alter scheduler ownership, or manage H/O maintenance without an approved record | Separate approved maintenance-controller packet only. Do not run from this map. |
| `CodexHProbe_20260327_005911` | Extra visible scheduler probe found by reconciliation, not in the original map. | Maintenance Protected / Unknown | Unknown local probe output, action points to `C:\Temp\h_scheduler_probe.20260327T005911Z.schedprobe.ps1` | Unknown | Because purpose and owner are unmapped, any Ready state is a control gap | Create or use a scheduler classification packet. Do not change, run, delete, disable, or trust it until classified. |

## Flow MOT Gates

| Flow | Current main failed or warning health signals | Owner | Proof route | Safe repair route |
|---|---|---|---|---|
| A | Latest manifest partial, maintenance handoff proof failed, manifest traversal 10/11, lock present warning | A | A MOT rows in `../out/systems/M/mot/` | Work only approved A packets. Start at the stopped manifest or handoff proof, not downstream displays. |
| B | Future marketplace cursors stale, maintenance marker conflict, management not ready, order truth incomplete, several warning-only proof gaps | B | B independent MOT rows | Work B approved packets. Use read-only B MOT first. Protected order/token/DB correction needs Luke. |
| E | B money dependency and ROI coverage warnings | E | E independent MOT rows | Keep confidence labels honest. Do not turn bridge-only proof into clean ROI/restock truth. |
| H | Manager readiness, reliability window, cleanup safety, and floor-source warnings | H | H MOT rows and H reliability/window proof | Build or use the independent H manager/MOT layer before broad H repair. No price writes. |
| F | RESCAN priority decision, live owner no progress, login mode warnings, Seller Central auth warning | F | F MOT rows and F manager snapshot | Keep login on the script-owned path. Protected F rescan recovery needs Luke decision. |
| O | Active restock proof stale-fail and user-working readiness blocker, profit/input trust warnings | O | O MOT rows and O proof files | Keep O as proof-only until guardrails clear. No PO, receiving, send-to-Amazon, Sheets, prices, DB alignment, or output patching. |

## Default Threshold Rules Where Unknown

- If a script says hourly, treat proof older than about 1 hour as stale for active monitoring.
- If a script says morning or daily, treat proof from the wrong day as stale unless the packet says a longer cadence is expected.
- If proof is missing, unreadable, contradictory, or older than the code/control change it is meant to prove, treat it as not proved.
- If a check touches Business Runtime, treat any repair as protected until an approved packet names the target and route.
- If a check would require scheduler changes, runtime pause/restart, process kill, output cleanup, queue edits, Sheets, DB writes, prices, Amazon, purchase, receiving, or send-to-Amazon, stop and escalate through the Rep.

## Repair Routing

- A repairs: A approved packets and A MOT retest.
- B repairs: B approved packets and B independent MOT retest, with ownership and lock checks before any manual B action.
- E repairs: E approved packets and E independent MOT retest.
- H repairs: H manager/MOT layer first, then scoped H packets.
- F repairs: F approved packets, script-owned browser/session route, no Amazon security bypass.
- O repairs: O proof/readiness packets only, no live purchase or stock movement.
- SO21 control repairs: SO21 approved packets, control files, and packet proof command.
- Scheduler or maintenance repairs: runtime-control or scheduler-state packets only, with explicit Luke approval for any state change.
- Storage repairs: Custodian manifest-first process only.

## Blockers Found During This Work

- No Windows permission or locked-file blocker was hit while creating this map.
- The repo-level MOT evidence lives at `../out/systems/M/mot/`, not inside `sellerone_manager/out/`.
- Scheduler-state evidence has a known mismatch between older pause proof and later reconciliation. The later reconciliation must be read before future scheduler decisions.

## Verification

- This map exists at `sellerone_manager/CONTROL/SO21_SCRIPT_STATUS_HEALTH_MAP.md`.
- It is a read-only planning document.
- No Task Scheduler change was made.
- No runtime pause, restart, process kill, worker restart, script implementation, deletion, output cleanup, Amazon/security action, price change, Google Sheets write, database alignment, purchase, receiving, or send-to-Amazon action was performed.

## Current Next Move

Recommendation:

- continue with `SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW`.
