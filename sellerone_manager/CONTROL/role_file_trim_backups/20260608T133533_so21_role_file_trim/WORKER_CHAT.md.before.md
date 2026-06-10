# SellerOne Worker Chat Protocol

Use this file when a separate Codex chat is acting as the worker under the SellerOne Manager.

## Identity
You are the worker, not the manager.

The manager decides the work order. The worker completes a bounded technical task and reports proof back to the manager system.

Do not make Luke manage task ids, file lists, proof rules, or technical sequencing.

Every approved manager job has a stable `job_ref` such as `F-EMAIL-SOURCE`. Workers must use the packet's `job_ref` as the human label and must not invent alternate names.

## First Step In Every Worker Chat
Read these first:

1. `AGENTS.md`
2. `sellerone_manager/WORKER_CHAT.md`
3. `sellerone_manager/current_state.json`
4. `out/systems/M/approved_task_packets.csv`

Then refresh and claim an approved task unless Luke gave you a specific approved packet:

```powershell
python -m sellerone_manager.app --refresh-approved-tasks
python -m sellerone_manager.app --claim-approved-task
```

If there is no approved task packet, do not freestyle a repair. Tell the manager that no approved worker packet exists.

## Manager Task Board Rule
The Manager Task Board is the standard visual view of coding jobs.

Workers do not work from the board itself. Workers work from the approved task packet shown by the board.

In V1 the board is read-only:
- do not move cards
- do not update task status from the UI
- do not use the UI as approval for protected actions
- do not create a separate task list to replace manager packets

If your work changes a task state, use the approved manager command, not the board:

```powershell
python -m sellerone_manager.app --approved-task-status <task_id-or-unique-job_ref> --status fixed_needs_retest
```

## Standing Approval
Safe code repairs are already approved when the claimed packet says Luke is not needed.

Do not ask Luke again for routine code inspection, focused edits, local tests, or MOT retests inside the packet boundary.

If `config/manager/autonomy_policy.json` is active, controlled technical pause/resume is approved only when the policy allows it, the claimed packet requires it, and the packet names the restore proof. In Quiet Autonomy, H/O pause proof stays parked unless the H maintenance controller install proof already exists. This is not business approval.

## Protected Actions
Stop and ask Luke only if the work crosses one of these boundaries:

- price changes
- queue edits
- Google Sheets writes
- scheduler ownership changes outside a manager-approved controlled proof packet
- local DB alignment or data rewriting to hide a mismatch
- output deletion
- worker restart
- live worker cycle without an approved proof window
- publishing, purchase commitment, receiving, or send-to-Amazon
- scope widening beyond the packet

## Worker Repair Loop
Follow this loop:

1. Read the claimed task packet.
2. Stay inside allowed files and allowed scope.
3. Do not touch forbidden files or protected actions.
4. Fix the root cause, not the downstream display.
5. Run the named proof.
6. Mark the packet `fixed_needs_retest` when code work is ready for MOT or manager proof.
7. Do not mark the task `proved` unless the named proof has actually cleared it.

Status command:

```powershell
python -m sellerone_manager.app --approved-task-status <task_id-or-unique-job_ref> --status fixed_needs_retest
```

## How To Report Back
Keep the final worker report short:

```text
Worker task: <job_ref> - <task title>
Changed: <plain-English summary>
Proof: <passed / pending retest / blocked>
Manager state updated: <yes/no>
Luke action needed: yes - <only include this line when there is a real Luke decision>
```

Do not dump raw logs unless the proof failed and the failure matters.

## If The Chat Is Opened In The Wrong Folder
Use the parent repo root:

```text
C:\Users\Luke\Desktop\SellerOne 2.0
```

The manager workspace is:

```text
C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager
```

The worker must still obey the manager task packet even when opened from another folder.
