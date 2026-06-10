# SO21 Queue Movement Board

Generated UTC: 2026-06-09T09:38:18Z
Worker packet: `SO21-QUEUE-MOVEMENT-BOARD`
Mode: visibility-only

## Plain-English Status

The SO21 queue is moving, but the current timestamps do not make that easy to see.

Think of the packet index like a shop notice board being reprinted. The reprint time proves the notice board was refreshed, but it does not prove every job on the board actually changed. This board separates those two things:

- board refresh time means the view or index was regenerated
- real movement time means a worker note, reviewer note, proof note, handoff, or packet stage change can be tied to that specific job

## Evidence Read

- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/SO21_FIRST_OVERNIGHT_RUN_EFFICIENCY_PLAN.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`
- `CONTROL/QUEUE_CONTRACT.md`
- `out/systems/M/approved_task_packets.csv`
- SO21 approved packet files under `tasks/approved/`
- SO21 control proof, review, retest, and handoff notes under `CONTROL/`

## Timestamp Rules Used Here

| Timestamp Type | Meaning | Trust Level |
|---|---|---|
| Direct proof/review/control note time | A named output exists for that job, such as a worker result, review, retest, or handoff note. | Strong |
| Packet created time | The packet was created or promoted into the queue. | Medium |
| Packet index `updated_utc` / `observed_utc` | The generated packet index refreshed the row. | Weak for movement |
| Mass file modified time | Many packets were rewritten at the same time. | Polluted by board refresh |

## Current SO21 Active Jobs

| Job | Stage | Owner Role | Last Real Movement | Confidence | Age / Idle Risk | Next Action | Blocker |
|---|---|---|---|---|---|---|---|
| `SO21-CREDENTIAL-TOKEN-STATUS-CHECK` | Waiting proof | Worker repair / Operations | 2026-06-09 10:33 UK worker result note, then 2026-06-09 10:35 UK reviewer retest note | Strong | Low technical risk, high closure risk if format repair sits idle | Replace the result note with the exact safe wording requested by the reviewer, then send back for proof | Format-only security-label issue: result passed HTTP 200, but wording still included forbidden credential-label terms in the retest |
| `SO21-REP-BRIEFING-FIRST-RUN-PROOF` | Waiting proof | Reviewer / Operations | 2026-06-08 16:31 UK handoff says first scheduled output was not yet visible | Strong for blocker, weak for later movement | Medium idle risk because it waits on an automation output | Inspect the first scheduled `SO21-REP-BRIEFING` output when visible; keep, adjust, or pause the pilot based on evidence | First scheduled briefing proof output not confirmed in the inspected control notes |
| `SO21-PROPOSAL-REPORT-STANDARD` | Waiting proof | Reviewer | 2026-06-08 22:25 UK control note created | Strong | Medium closure risk because the standard appears written but proof is still open | Reviewer should inspect `CONTROL/SO21_PROPOSAL_REPORT_STANDARD.md` and confirm it is reporting-only | No material blocker found; waiting proof closure |
| `SO21-QUEUE-MOVEMENT-BOARD` | In progress | Worker | 2026-06-09 09:38 UTC this board was generated | Strong | Low risk while this packet is active | Reviewer should inspect this board and confirm it is visibility-only | None |
| `SO21-CONTROL-FLOW-CONFIRMATION` | Ready for Builder | Builder | 2026-06-08 15:01 UTC packet created | Medium | Medium idle risk if higher-priority proof items stay open first | Start a clean Worker from the packet when Operations chooses the next Builder task | No blocker found |
| `SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN` | Ready for Builder | Builder / Custodian | 2026-06-09 07:07 UTC packet created | Medium | Low age, normal queue wait | Start design-only Worker after waiting-proof items are handled | No blocker found |
| `SO21-OPERATIONS-SHIFT-MANAGER-CONTROL` | Ready for Builder | Builder / Operations | 2026-06-08 15:40 UTC packet created | Medium | Medium idle risk because Operations authority affects queue speed | Start Worker to write the durable Operations authority document | No blocker found |
| `SO21-PROOF-CLOSURE-RULES` | Ready for Builder | Builder / Operations | 2026-06-09 09:32 UTC packet created | Medium | Low age, high value because it reduces future proof-stall confusion | Start after or alongside visibility cleanup if file overlap stays safe | No blocker found |
| `SO21-THREAD-ROLE-HYGIENE` | Ready for Builder | Builder / Operations | 2026-06-09 09:32 UTC packet created | Medium | Low age, high value because it prevents worker/reviewer threads looking like managers | Start after movement board, per overnight efficiency plan | No blocker found |
| `SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST` | Ready for Builder | Builder / Custodian | 2026-06-08 15:01 UTC packet created | Medium | Medium idle risk, but not a runtime blocker | Start preview-only manifest work after higher-priority control visibility and proof-closure work | No blocker found |

## Board Refreshes That Should Not Be Treated As Movement

These timestamps are useful, but they are not proof that every job moved:

- `CONTROL/CURRENT_STATE.md`, `CONTROL/CURRENT_TICKETS.md`, and `CONTROL/BACKLOG.md` were regenerated around 2026-06-09 10:35 UK.
- `out/systems/M/approved_task_packets.csv` was regenerated around 2026-06-09 10:35 UK.
- Many packet files under `tasks/approved/` show the same 2026-06-09 10:35 UK file modified time.
- The generated index gives every active SO21 row `updated_utc` and `observed_utc` of 2026-06-09T09:35:25Z.

Plain-English meaning: that 10:35 UK time is a board/index refresh. It should not be used as the last real movement time for every job.

## Weak Or Missing Movement Evidence

The current queue does not yet store enough job-specific movement facts.

Known weak spots:

- No separate `last_real_movement_utc` field exists in the packet index.
- No separate `last_real_movement_type` field exists, such as `worker_note_created`, `review_failed_format_only`, `proof_passed`, or `blocked_waiting_external_output`.
- No separate `owner_role` field exists in the packet index. Owner has to be inferred from stage.
- No separate `assigned_thread` or `thread_label` field exists in the packet index.
- Mass packet file rewrites pollute file modified times, so `LastWriteTime` is not safe as movement evidence.
- Waiting-proof rows do not clearly show whether the proof has actually failed, is waiting reviewer, or is waiting on an external scheduled output.

## Recommended Safe Next Improvement Fields

Future queue generation should add these fields without changing business runtime:

| Field | Why It Helps |
|---|---|
| `last_real_movement_utc` | Shows when the job itself changed, not when the board refreshed. |
| `last_real_movement_type` | Explains what happened, like worker note, reviewer return, proof pass, blocker logged, or packet created. |
| `last_real_movement_source` | Points to the exact packet, proof note, review note, or handoff note used as evidence. |
| `stage_entered_utc` | Lets Operations calculate how long a job has been in the current stage. |
| `owner_role` | Makes it obvious whether Builder, Reviewer, Operations, Rep, Custodian, or Luke owns the next move. |
| `assigned_thread_label` | Keeps Worker and Reviewer threads tied to one job instead of looking like extra managers. |
| `blocker_reason` | Separates a real blocker from ordinary queue waiting. |
| `proof_result_grade` | Separates pass, minor format repair, material proof gap, Luke decision, and safety failure. |
| `board_refreshed_utc` | Keeps generated-view freshness visible without pretending it is job movement. |

## Operations Reading Guide

- Treat waiting-proof jobs as the first closure lane.
- Treat ready-for-Builder jobs as available work, but do not start several overlapping SO21 control-file jobs if they would edit the same files.
- Treat 2026-06-09T09:35:25Z as index refresh time, not real movement for each row.
- If a job has only packet-created evidence, call the movement timestamp weak.
- Do not invent movement times. If evidence is missing, write "unknown" or "packet created only."

## Safety Boundary

This board did not change:

- business runtime
- Windows Task Scheduler
- Codex automations
- prices
- Google Sheets
- local database or Product DB facts
- Amazon login/security
- purchase, receiving, or send-to-Amazon state
- output files outside this control document
- queue statuses
- task packet locations

## Retest

Retest command from packet: inspect this movement board and confirm it is visibility-only.

Expected result:

- `CONTROL/SO21_QUEUE_MOVEMENT_BOARD.md` exists.
- Active SO21 jobs have stage, owner role, last real movement evidence, next action, and blocker where present.
- Weak or polluted timestamps are clearly labelled.
- Recommended future fields are visibility fields only.
