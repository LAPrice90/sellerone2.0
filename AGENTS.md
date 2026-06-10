# AGENTS.md

## SellerOne 2.1 Codex Bootstrap

These rules tell Codex how to work in the SellerOne repo. They are the short live bootstrap for the 2.1 control system.

For the full control model, read:

- `sellerone_manager/CONTROL/ROLE_BOOTSTRAP.md`
- `sellerone_manager/CONTROL/RUNTIME_SAFETY_RULES.md`
- `sellerone_manager/CONTROL/CURRENT_STATE.md`
- `sellerone_manager/CONTROL/CURRENT_TICKETS.md`
- `sellerone_manager/CONTROL/BACKLOG.md`

Chat is not the source of truth. The queue, control files, MOT evidence, and approved task packets are.

## Plain-English Style

- Luke is not a coder. Explain decisions in plain English.
- If Luke asks "is this right?", answer `YES` or `NO` first.
- Keep replies operational and avoid raw logs unless Luke asks.
- Use standard ASCII hyphens only.
- End completed work with one concrete next move:
  - `no further action needed now`
  - `wait until <specific time or condition> and check <specific file or output>`
  - `continue with <specific follow-up task>`
  - `needs user decision on <specific choice>`

## Role Routing

- Manager chat: read `sellerone_manager/MANAGER_CHAT.md` and the 2.1 control files.
- Worker chat: read `sellerone_manager/WORKER_CHAT.md`, claim one approved packet, and work only inside it.
- Cycle sub-manager chat: read `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md` and extend the independent MOT for that cycle first.
- Reviewer work: use fresh evidence and the named proof path, not the Builder chat history.
- Custodian work: measure, classify, and report. Do not delete without an approved manifest.

## Source Of Truth

Use this order when files disagree:

1. Protected Luke decisions captured in durable files.
2. Latest direct proof artifact for the flow.
3. Latest MOT evidence.
4. Approved task packet markdown.
5. Generated packet index at `out/systems/M/approved_task_packets.csv`.
6. `sellerone_manager/CONTROL/CURRENT_STATE.md`.
7. Manager Task Board and Manager Briefing as read-only views.
8. Old plans, prompt folders, `CODING_PLAN.md`, `WORK_LOG.md`, and chat history as context only.

## Protected Actions

Stop and ask Luke before:

- price changes
- queue edits
- Google Sheets writes
- local DB or Product DB alignment
- output deletion
- worker restarts
- live worker cycles without an approved proof window
- scheduler ownership changes outside an approved proof packet
- publishing
- purchase commitments
- receiving stock
- send-to-Amazon actions
- Amazon security bypass
- scope widening beyond the approved packet

## Worker Repair Rule

Before worker repair, refresh and claim an approved task packet:

```powershell
python -m sellerone_manager.app --refresh-approved-tasks
python -m sellerone_manager.app --claim-approved-task
```

Safe non-Luke repairs inside a claimed packet have standing approval. Stay inside the allowed scope and forbidden actions. After code work, update the packet instead of using chat as the tracker:

```powershell
python -m sellerone_manager.app --approved-task-status <task_id-or-job_ref> --status fixed_needs_retest
```

A task is not proved because code changed. It is proved only when the named MOT or proof path clears it.

## Runtime Safety

For detailed runtime rules, read `sellerone_manager/CONTROL/RUNTIME_SAFETY_RULES.md`.

Minimum rules:

- Fix root causes upstream, not downstream display symptoms.
- Do not run A scripts ad hoc unless Luke explicitly asks.
- Before any B script, check B ownership and maintenance safety.
- Do not run worker cycles unless an approved proof window says so.
- Do not hand-edit MOT, health, queue, or proof outputs to make a status look better.
- For live-loop work, separate `code fix applied`, `isolated verification passed`, and `live loop verification confirmed`.
- If proof depends on future runtime evidence, record the follow-up in a durable artifact before ending.
- For F061 login, do not open a separate Chrome workaround. Login recovery must stay on the scanner-owned path unless Luke explicitly asks otherwise.

## Manager Views

Use the 2.1 control files first:

- `sellerone_manager/CONTROL/CURRENT_STATE.md`
- `sellerone_manager/CONTROL/CURRENT_TICKETS.md`
- `sellerone_manager/CONTROL/BACKLOG.md`
- `sellerone_manager/CONTROL/OPERATIONS.md`

Manager Task Board and Manager Briefing remain read-only. They must not move cards, approve protected actions, run workers, or become the queue source of truth.

## Storage And Cleanup

Custodian cleanup is manifest-first:

- measure
- classify
- write dry-run manifest
- exclude protected files
- prove recovery path
- ask approval before destructive cleanup

No cleanup automation should run before the policy and manifest are approved.

## Prompt Number Rule

If Luke provides `PROMPT NUMBER: XXX`, the final reply must end with that exact line.
