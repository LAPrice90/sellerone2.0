# SO21 Legacy Control Retirement Manifest

Job: `SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST`

Created: 2026-06-08

Status: preview-only manifest

## Plain-English Decision

This manifest labels old SellerOne control material before any cleanup happens.

Think of this like putting colored labels on old office folders. The labels say what should stay on the current desk, what belongs in the records room, what can become a future template, and what needs Luke approval before anyone touches it.

No cleanup was performed by this ticket.

## Hard Boundary

This ticket did not move, delete, compress, purge, archive, rename, disable, re-enable, restart, or rewrite any existing file, folder, scheduler, automation, queue, runtime output, Sheet, database, price, or Amazon state.

Any future cleanup apply step needs a separate approved apply manifest and Luke approval for destructive or risky actions.

## Evidence Read

- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\SELLERONE_2_1_CONTROL_INVENTORY.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\QUEUE_CONTRACT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\RUNTIME_SAFETY_RULES.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\STORAGE_POLICY.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\approved\MGR_SO21_LEGACY_CONTROL_RETIREMENT_MANIFEST_V1.md`

Observed counts during this preview:

| Area | Observed preview count |
|---|---:|
| `sellerone_manager/tasks/approved` | 185 files |
| `sellerone_manager/tasks/blocked` | 35 files |
| `sellerone_manager/tasks/proposed` | 11 files |
| `sellerone_manager/tasks/archive` | 1 file |
| `sellerone_manager/tasks/done` | 1 file |
| `sellerone_manager/tasks/in_progress` | 1 file |
| `sellerone_manager/tasks/rejected` | 1 file |
| `sellerone_manager/agent_launch_prompts` | 8 files |
| `sellerone_manager/thread_prompts` | 13 files |
| `sellerone_manager/thread_starters` | 6 files |
| `sellerone_manager/project_threads` | 24 files |
| `plans/active` | 475 files |
| `plans/archive` | 85 files |
| `project_control` | 281 files, 508376579 bytes |
| `out/systems/M` | 264 files, 13911577 bytes |
| `docs/manager-briefing` | 6 files |
| `config/manager` | 73 files |

## Keep-Current

These are current control sources or current read-only control views. They should stay in place.

| Path | Reason | Recommended next step |
|---|---|---|
| `C:\Users\Luke\Desktop\SellerOne 2.0\AGENTS.md` | Root operating instructions remain current. | Keep. Only shorten through a separate instruction-cleanup ticket. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\AGENTS.md` | Manager/project instructions remain current. | Keep. Only shorten through a separate instruction-cleanup ticket. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\ROLE_BOOTSTRAP.md` | Current 2.1 role router. | Keep as current control. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\RUNTIME_SAFETY_RULES.md` | Current protected-action and proof rules. | Keep as current control. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\QUEUE_CONTRACT.md` | Current queue contract. | Keep as current control. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\CURRENT_STATE.md` | Human-readable state anchor. | Keep. Generate or refresh through approved state tooling only. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\CURRENT_TICKETS.md` | Current human-readable ticket summary. | Keep. Do not hand-edit as a cleanup shortcut. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\BACKLOG.md` | Current backlog anchor. | Keep. Add old-plan carryovers through queue-approved work only. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\ARCHITECTURE_DECISIONS.md` | Durable decision record. | Keep. Add future cleanup decisions here only through approved process. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\STORAGE_POLICY.md` | Current Custodian policy. | Keep as cleanup rulebook. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\approved` | Canonical approved queue packet source. | Keep current. No cleanup movement under this ticket. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\blocked` | Canonical Luke-blocked packet source. | Keep current. Reconcile proved-in-blocked oddities only through a future queue cleanup ticket. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\proposed` | Candidate packet source. | Keep current, but not active until approved. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\archive` | Current archive folder now exists. | Keep. Use only through approved archive policy. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\task_packets.py` | Packet engine. | Keep. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\app.py` | Manager app entrypoint for packet commands. | Keep. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv` | Generated queue index. | Keep as generated support, not the source of truth. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot` | Independent MOT evidence. | Keep as evidence, not a second live queue. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\hourly_mot.py` | MOT generator. | Keep. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\task_board.py` | Read-only board support. | Keep as view support. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\task_board_ui.py` | Read-only board UI. | Keep as view support. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\run_Manager_Task_Board_UI.bat` | Board launcher. | Keep as view launcher. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\manager_briefing.py` | Rep briefing support. | Keep, but continue migration away from stale state inputs. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\manager_briefing_ui.py` | Rep briefing UI support. | Keep as read-only communication layer. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\run_Manager_Briefing_UI.bat` | Briefing launcher. | Keep as view launcher. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\communications` | Generated communication evidence. | Keep as generated evidence. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\docs\manager-briefing` | Generated communication mirror. | Keep as generated mirror. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\config\manager` | Manager config and policy support. | Keep as config support. |

## History

These should be treated as historical evidence. They should not drive current work unless a future packet explicitly extracts a fact from them.

| Path | Why it is history | Recommended next step |
|---|---|---|
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CODING_PLAN.md` | Already trimmed down; old live detail was moved to `CONTROL\CODING_PLAN_ARCHIVE.md`. Still has a live-looking name. | Keep for now as bridge history. Future task can replace it with a short pointer to `CURRENT_STATE.md`, `CURRENT_TICKETS.md`, and `BACKLOG.md`. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\CODING_PLAN_ARCHIVE.md` | Large historical record of old plan/proof material. | Keep as audit history. Do not use as daily control. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json` | Stale machine-support state from 2026-06-06; newer state lives in `CONTROL\CURRENT_STATE.md` and MOT evidence. | Keep as machine support only until a separate migration retires or regenerates it. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\DAILY_MANAGER_PLAN_20260602.md` | Old daily manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\DAILY_MANAGER_PLAN_20260603.md` | Old daily manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\DAILY_MANAGER_PLAN_20260605.md` | Old daily manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\DAYTIME_MANAGER_PLAN_20260606.md` | Old daytime manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\HOMETIME_PLAN_20260605.md` | Old hometime manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\HOMETIME_PLAN_20260606_WEEKEND.md` | Old hometime manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MORNING_ISSUE_PLAN_20260606.md` | Old issue plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\TONIGHT_MANAGER_PLAN_20260604.md` | Old tonight manager plan. | Archive-candidate after Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\plans\archive` | Existing plan archive/history. | Keep as history. No movement by this ticket. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads` | Old thread records and phase completion notes. | Keep as history/template library until a future archive apply is approved. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\DUE_CHECK_REGISTER.csv` | Older due-check control record. Useful evidence, but not the active queue. | Keep as history/governance until queue contract fully absorbs the role. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\TASK_QUEUE.md` | Older queue-looking file. | Mark not current. Future ticket should add a visible pointer to approved packets or archive it with Luke approval. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\ROADMAP_SYSTEM_MAP.md` | Older roadmap/governance file. | Keep as governance history unless a future task extracts current roadmap facts. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS` | Older expectations docs. | Keep as governance history. Extract only if needed by a future policy task. |

## Template

These may contain reusable wording, but they are not current instructions by themselves.

| Path | Template value | Recommended next step |
|---|---|---|
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md` | Useful Rep-facing communication style and manager boundary language. | Keep as current role support for now, then merge useful parts into role bootstrap or a SellerOne skill. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md` | Useful Builder/Worker starter. | Keep as current role support for now, then reduce duplicated safety wording. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md` | Useful MOT investigation method, but the visible cycle-sub-manager role should not be treated as a standing current role. | Convert useful method into bounded Reviewer/Builder templates; retire visible identity only after approved instruction cleanup. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\agent_launch_prompts\README.md` | Prompt-library orientation. | Keep as template/history until approved archive. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_prompts\README.md` | Thread-prompt orientation. | Keep as template/history until approved archive. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_prompts\README_THREAD_STARTERS.md` | Thread-starter orientation. | Keep as template/history until approved archive. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_starters\00_THREAD_LAUNCH_ORDER.md` | Could be reused as historical launch-order reference. | Convert only useful neutral parts into a template; do not use as live launch order. |

## Archive-Candidate

These are good candidates for future archive movement, but only after Luke approves an exact apply manifest. This preview does not archive them.

| Path | Reason | Recommended next step |
|---|---|---|
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\done` | Legacy placeholder folder, not a 2.1 queue lane. | Future queue cleanup manifest can move contents to `tasks\archive` after proof. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\in_progress` | Legacy placeholder folder, not a 2.1 queue lane. | Future queue cleanup manifest can reconcile or archive after proof. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\rejected` | Legacy placeholder folder, not a 2.1 queue lane. | Future queue cleanup manifest can archive after proof. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\agent_launch_prompts` | Old manager-per-cycle prompt model; file names look like standing manager roles. | Future instruction cleanup should extract useful templates, then archive the folder with Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_prompts` | Old cycle-manager and sub-manager prompt model. | Future instruction cleanup should extract useful templates, then archive the folder with Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_starters` | Old visible worker/thread starter model. | Future instruction cleanup should extract useful templates, then archive the folder with Luke-approved apply manifest. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\goals` | Parallel goal system with `active`, `blocked`, `done`, and `inbox` folders. | Future cleanup should merge any still-open item into queue/backlog, then archive. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active` | Legacy active-plan store with 475 files; not canonical queue. | Future reconciliation ticket should extract any live commitments into packets/backlog, then mark the folder as history/archive. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\01_B_WORKER_THREAD.md` | Old thread starter/record. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\02_H_SAFETY_THREAD.md` | Old thread starter/record. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\03_F_PROOF_THREAD.md` | Old thread starter/record. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\04_O_BUILD_THREAD.md` | Old thread starter/record. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\05_E_PROOF_THREAD.md` | Old thread starter/record. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\06_MAIN_MANAGER_COMBINER_THREAD.md` | Old manager-combiner model. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\07_A_WATCH_ONLY_THREAD.md` | Old standing A watch thread. | Archive after template extraction. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\project_threads\11_MANAGER_TASK_BOARD_UI_THREAD.md` | Old project thread record for UI work. | Archive after current UI docs are confirmed. |

## Needs-Luke-Decision

These are not safe for a worker to alter without Luke or a separate approved packet.

| Path or area | Why it needs a decision | Recommended next step |
|---|---|---|
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\scheduler_pause_backups` | Scheduler-related backup evidence. Scheduler state is protected. | Do not move or compress until Luke approves an exact retention rule. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\storage_index_backups` | Rollback/audit backups. | Decide retention count before any cleanup. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\coding_plan_archive_backups` | Rollback backup for old plan trimming. | Decide keep count before any cleanup. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\instruction_cleanup_backups` | Rollback backup for instruction cleanup. | Decide keep count before any cleanup. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\prompt_folder_archive_backups` | Rollback backup for prompt-folder archive work. | Decide keep count before any cleanup. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CONTROL\role_file_trim_backups` | Rollback backup for role-file trimming. | Decide keep count before any cleanup. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\project_control` | Large governance and backup area, about 508 MB. Some files may be audit history or recovery material. | Future Custodian storage packet should produce a file-level dry-run manifest before any deletion or compression. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M` | Generated manager evidence and MOT proof. Some files are current proof inputs. | Keep. Clean only with a separate generated-output retention policy. |
| Any Codex automation definitions | Automations are protected and outside this packet. | Leave untouched until an approved automation rebuild or retirement packet. |
| Any Windows Task Scheduler entry | Scheduler ownership is protected and outside this packet. | Leave untouched until an approved scheduler packet. |

## Live-Looking Sources That Should Not Be Live Control

These are the highest drift risks because their names make them look current even though 2.1 says the queue and control files now own the system.

| Path | Risk | Correct interpretation |
|---|---|---|
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CODING_PLAN.md` | Name looks like a current master plan. | Bridge/history only. Current state is in `CONTROL\CURRENT_STATE.md`, `CURRENT_TICKETS.md`, and `BACKLOG.md`. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json` | Looks like the current state source, but is stale against newer evidence. | Machine support only. It must not outrank current MOT, packets, or `CONTROL\CURRENT_STATE.md`. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\TASK_QUEUE.md` | Looks like a queue. | Historical/governance only. Canonical queue is task packet markdown plus generated packet index. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active` | Folder name says active, but 2.1 says packets own active work. | Legacy planning library until reconciled. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\agent_launch_prompts` | Old prompt names imply standing manager roles. | Template/history only, not live launch instructions. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_prompts` | Old thread prompts imply cycle sub-managers. | Template/history only, not live role routing. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\thread_starters` | Old launch-order material can restart old habits. | Template/history only, not live launch order. |
| `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\goals` | Looks like a parallel task system. | Historical/candidate source only; queue packets own work. |

## Business Runtime Separation

This manifest intentionally excludes business runtime changes.

No action was taken on:

- A, B, E, H, F, or O worker cycles
- worker starts or restarts
- Windows Task Scheduler
- Codex automations
- prices
- Google Sheets
- Product DB or local DB alignment
- purchase, receiving, or send-to-Amazon workflows
- Amazon login, MFA, security, cookies, tokens, or credentials

## Future Apply Rule

Before any future cleanup applies changes, the next ticket must create an exact apply manifest with:

- exact source path
- exact target path if moving
- exact action requested
- class
- reason
- rollback or recovery path
- protected-file exclusion check
- Luke approval marker for destructive or risky actions

Until that exists, this file is only a map.

## Result

Preview manifest created.

No files were moved, deleted, compressed, purged, archived, or renamed.

Recommended next move: `continue with SO21-CONTROL-FLOW-CONFIRMATION`
