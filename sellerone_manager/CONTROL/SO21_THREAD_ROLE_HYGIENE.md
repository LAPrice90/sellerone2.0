# SO21 Thread Role Hygiene

Job: `SO21-THREAD-ROLE-HYGIENE`
Generated: 2026-06-09
Mode: preview/report-only

## Plain-English Decision

SellerOne should have only two management chats:

- Rep Chat
- Operations Chat

Think of this like a small site office. Luke talks to the front desk, which is Rep. Operations works in the back office, checking evidence and preparing clean updates. Worker and Reviewer chats are temporary job benches. They should not become extra front desks.

## Confirmed Control Model

The current control files and architecture decisions confirm this model:

- Rep Chat talks to Luke, explains state, helps plan priorities, and turns decisions into tickets.
- Operations Chat monitors control-desk evidence, worker/reviewer progress, automations, MOT, storage, scheduler, and queue visibility.
- Worker Chats execute one approved packet at a time.
- Reviewer Chats verify one packet from fresh evidence.
- Worker and Reviewer chats belong in the SellerOne 2.0 execution side, not as extra Manager-project front desks.
- Worker and Reviewer chats must not fork or inherit the Rep conversation.

## Visible Thread Classification

Read-only thread title and summary inspection was available through the Codex thread tools.

Visible SellerOne-related threads were classified as:

| Thread Title | Classification | Hygiene View |
|---|---|---|
| `SellerOne Chat Manager` | Rep | Correct primary Luke-facing chat. |
| `SellerOne Operations - SO21 Monitor` | Operations | Correct back-office control chat. |
| `Create thread role hygiene report` | Worker | Correct bounded Worker thread for this packet. |
| `Run controlled login proof window` | Worker | Correct bounded Worker thread, but sensitive F/Amazon boundary means the title should stay job-specific and not manager-like. |
| `Repair F session durability` | Worker | Correct bounded Worker thread. |
| `Review F browser session durability` | Reviewer | Correct bounded Reviewer thread. |
| `Review proposal report standard` | Reviewer | Correct bounded Reviewer thread. |
| `Review staged retention dry-run` | Reviewer | Correct bounded Reviewer thread. |
| `Design H staged dry-run report` | Worker/Custodian Worker | Correct bounded execution thread if it stays inside the packet. |
| Other visible `Review ...`, `Create ...`, `Update ...`, and `Check ...` SellerOne threads | Worker or Reviewer | Acceptable if each remains tied to one packet and does not talk to Luke as a manager. |
| `Use PC apps` | Unrelated | Not part of SellerOne role structure. |

No extra visible Manager chat was found in the inspected SellerOne thread list.

## Naming Rules

Worker thread names should use this shape:

- `<Action verb> <job area or plain task>`
- Example: `Repair F session durability`
- Example: `Create thread role hygiene report`

Reviewer thread names should use this shape:

- `Review <job area or plain task>`
- Example: `Review F browser session durability`
- Example: `Review proposal report standard`

For higher clarity, future handoffs may include the job reference in the first line of the prompt and optionally in the title:

- `Worker - SO21-THREAD-ROLE-HYGIENE - Thread role hygiene report`
- `Reviewer - F-BROWSER-SESSION-DURABILITY - Browser session durability`

Avoid names that sound like permanent management roles:

- `SellerOne Manager 2`
- `New Manager`
- `Luke Manager`
- `Cycle Manager`
- `Dispatch Manager`
- `Operations Manager for Luke`

## Boundary Rules

Each Worker thread must:

- name exactly one approved packet
- use the packet `job_ref`
- read Worker rules
- stay inside allowed scope
- stop before protected actions
- write proof or result evidence to the named control or proof path
- move only its own packet to `fixed_needs_retest` when acceptance proof is satisfied

Each Reviewer thread must:

- name exactly one packet or proof target
- use fresh evidence
- verify the named proof path
- write a review note
- move only that packet to `proved`, `retest_failed`, or another allowed review status when the proof rules allow it

Rep must:

- stay Luke-facing
- keep the conversation clean
- turn ideas into tickets
- not run noisy technical execution

Operations must:

- monitor and report
- keep queue visibility current
- create ticket candidates or handoffs
- not become the normal Luke-facing chat
- not start unapproved work

## Hygiene Risks

The current visible shape is mostly healthy, but these risks should be watched:

| Risk | Why It Matters | Safe Recommendation |
|---|---|---|
| Worker titles sometimes omit the job reference. | It can become harder to prove which chat owns which packet later. | Put `job_ref` in every worker/reviewer handoff and consider adding it to future titles. |
| Some Worker prompts are delegated from Operations, which was delegated from Rep. | The chain is acceptable, but if the Rep conversation is copied into workers, it can recreate a noisy manager thread. | Keep worker prompts packet-first and do not fork the Rep chat for execution. |
| Sensitive F/Amazon Worker titles can look routine. | Login and Amazon/security work has hard protected boundaries. | Keep titles plain but make prompts and proof paths explicit about protected stop conditions. |
| Old or unrelated SellerOne-looking threads may stay visible. | Too many visible threads can make it feel like there are many managers. | Future archive/rename should be previewed first and applied only after separate approval. |

## Archive And Rename Recommendations

This report does not archive, rename, move, or delete any thread.

Future cleanup, if approved separately, should follow this preview-first order:

1. List visible SellerOne threads.
2. Classify each as Rep, Operations, Worker, Reviewer, unrelated, or legacy.
3. Keep Rep and Operations unarchived and clearly named.
4. Keep active Worker and Reviewer threads until their packet is proved or parked.
5. Mark completed Worker and Reviewer threads as archive candidates only after their packet proof is durable.
6. Treat unclear threads as legacy review candidates, not deletion targets.
7. Never archive, rename, or move threads from a Worker packet unless that action is explicitly approved and supported by tools.

## Blockers Or Access Limits

No blocker prevented this report.

One command-path issue was observed:

- Affected job: `SO21-THREAD-ROLE-HYGIENE`
- Attempted action: run `python -m sellerone_manager.app --help` from `sellerone_manager`
- Failure: Python could not import `sellerone_manager.app` from that working folder
- Safest fix: run package commands from the parent project folder, `C:\Users\Luke\Desktop\SellerOne 2.0`

## Proof Of No Protected Action

This work was report-only.

No thread was renamed, archived, moved, pinned, or unpinned.
No worker or reviewer execution was started outside this packet.
No business runtime was changed.
No Task Scheduler change was made.
No process was killed.
No worker was restarted.
No Amazon/security action occurred.
No price, Sheet, database, purchase, receiving, or send-to-Amazon action occurred.
No file deletion, movement, compression, purge, archive apply, or cleanup apply occurred.

## Acceptance Result

Acceptance proof is satisfied:

- `CONTROL/SO21_THREAD_ROLE_HYGIENE.md` exists.
- The intended two-manager model is confirmed.
- Worker and Reviewer thread naming rules are defined.
- Visible thread hygiene risks are flagged without exposing unnecessary thread detail.

Recommended next move:

- mark `SO21-THREAD-ROLE-HYGIENE` as `fixed_needs_retest` so a Reviewer or proof path can confirm the report.
