# AGENTS.md
## Codex Operating Rules (Plain-English)

These rules tell Codex how to work in this repo. They override speed and convenience.

### 1) Explanation style (I am not a coder)
- Explain concepts clearly and step-by-step.
- Use plain language before code details.
- If I ask "is this right?", answer YES/NO first, then explain why.
- Use standard ASCII hyphen `-` (do not use Unicode dash characters like `-`, `-`, `-`) in output so I can copy/paste into Amazon without manual fixes.

### 2) Root-cause first (no output-masking)
- Fix problems at the earliest stage in the pipeline (A -> B -> C -> D -> E).
- Never "adjust results" downstream to make outputs look right.
- If the root cause is unclear, STOP and ask.

### 3) One-off vs daily
- One-off scripts must never run inside daily loops.
- Daily loops must never import or call one-off scripts.

### 4) Sheet vs local DB boundary
- Do not change Google Sheets unless explicitly asked.
- Do not change local DB to "match" Sheets (or vice versa) without approval.

### 5) Proof before "done"
- If you change code, rerun the relevant script(s).
- Show evidence (row counts, totals, reconciliation) before saying it's fixed.

### 6) Common sense rule
- Prefer the simplest correct fix.
- Do not introduce new processes if the existing process can be corrected.

### 7) Process guidebooks
- Maintain a written guidebook for each core process.
- If data is lost/corrupted, use the guidebook to recover the process.

### 8) User action clarity
- If I need YOU to run a command or do a task, label it clearly as **User Task**.
- Do not mix explanations with instructions.

### 9) Definition of Done (Z)
- A015 gate active (FAIL blocks publish).
- Staged publish active (no partial sheet writes).
- 0 FAIL for 10 consecutive runs.
- WARNs are 0 or only on an explicit exception list.
- Token shortage log is 1 line per SKU per run.
- Last 3 publish snapshots are kept for rollback.

### 9) Alerts and proactive fixes
- If any health check or log shows FAIL or WARN, call it out immediately even if the user asked about another topic.
- Format: "Answer to your question: ..." then "Alert: ..." then "Suggested fix: ...".
- Do not ignore alerts. Stop and address them before marking work done.
- Repeated-alert snooze protocol:
- If the alert is known and waiting for a later cycle/time window (example: "wait until 1pm"), Codex must proactively offer snooze in the same reply.
- Codex must include a concrete snooze command with an absolute UTC time and a short reason using `scripts/one_off/H001_set_health_alert_snooze.py`.
- Codex must keep reporting the underlying FAIL/WARN in health outputs; snooze only suppresses repeated toast interruption.
- Codex must never apply snooze automatically. Explicit user sign-off is required before running any snooze set/clear command.
- If the user asks to apply snooze, Codex should run the snooze command and confirm active status.

### 10) Self-healing development rules
- Any new feature or phase must add a health check item and an alert condition.
- Any new output file must have a schema check (required columns + types).
- Any new write to sheets must be staged (build locally, publish once complete).
- Any new loop step must be idempotent (safe to rerun).
- Update the runbooks whenever these are extended so the system stays self-explaining.

### 11) Work log rules
- The canonical work log is `WORK_LOG.md` at repo root.
- The log is append-only. Never remove or edit previous entries.
- Only append a log entry after the user approves the change.
- Every new entry must include date and time in the header line.
- The work log is the source of truth for system state; chat history is not authoritative.

### 12) Chat termination / rotation rules
- One Codex chat = one ticket.
- A ticket is complete once an approved change is logged in WORK_LOG.md.
- After ticket completion, Codex must:
- Provide a brief completion summary
- Print `SIGN OUT`
- Stop asking for next steps
- Codex must not ask “what would you like to do next?” after completion.
- Any new work requires a new chat and a new ticket declaration.

## Carryover vs Next (deferred work rules)
1) WORK_LOG fields:
- Next: optional, immediate suggestion for the very next chat only.
- Carryover: optional, used to persist an important pending task across interrupts.
2) Limits:
- Carryover should be used only when a phase/task is interrupted.
- Carryover max 1 item by default (max 3 only if explicitly approved).
- Carryover must be copied forward into subsequent WORK_LOG entries until completed.
- When Carryover is completed, log "Carryover: - None" in the completion entry.
3) Chat start behavior:
- If the user provides an explicit Ticket/Layer/Scope, Codex must ignore WORK_LOG suggestions (Next and Carryover) and execute only the explicit ticket.
- Codex may consult Next/Carryover only when the user explicitly asks for help selecting the next task.
- When consulted, Codex must offer Carryover first (if present), then Next, and must request permission before doing any work.
4) Non-autonomy:
- Codex must never begin a suggested task without explicit user approval.

- Clarification: the three lines that follow "After ticket completion, Codex must:" are sub-requirements of that rule, not separate rules.

### 13) B cycle maintenance safety (mandatory)
- Before running any `B` script manually, check if `out/B_cycle.lock` exists and is active.
- If `B` loop is active, do not run overlapping `B` scripts.
- Use maintenance mode first:
- A cycle must request maintenance via `out/locks/maintenance.requested` and wait for `out/locks/maintenance.ready`.
- B cycle must finish its current full cycle before setting `maintenance.ready` (no mid-cycle pause for A handoff).
- A cycle sets `out/locks/maintenance.active` while running, and clears maintenance flags after completion.
- Legacy manual maintenance toggle `out/locks/b_cycle.maintenance` is still supported for manual pauses.
- After maintenance checks pass, remove `out/locks/b_cycle.maintenance` (or unset env mode) to resume loop.
- Codex must follow this in every new chat without waiting for a user reminder.

### 14) Verification policy (no ad-hoc A runs by Codex)
- Codex must not run `A015_build_system_health_check.py` or other `A` scripts on its own during investigation.
- Codex may run an `A` script only if the user explicitly asks for that run.
- Default behavior is evidence from last completed cycle artifacts, not a fresh ad-hoc run.
- Use existing files as source of truth first:
- `out/system_health_checklist.csv` (latest health snapshot)
- `out/B_cycle.log` and `out/run_cycle.log` (cycle timing and stage)
- If Codex changed code at time `T_change` and latest completed health snapshot is `T_health < T_change`, Codex must mark status as pending verification, not confirmed.
- Required handoff text format in replies:
- `Verification status: Pending next cycle check`
- `Changed at: <UTC timestamp>`
- `Latest health snapshot at: <UTC timestamp>`
- `Next verifier: next scheduled cycle A015`
- When a later cycle confirms health after `T_change`, Codex can mark the task verified.

### 15) Flow-owned testing rule (mandatory)
- Each flow must run and gate on its own scoped test profile.
- No flow may be blocked by checks that belong to a different flow.
- Global profile is observability-only unless a flow explicitly declares it as its own gate.
- Required split for current core flows:
- A flow gates on A-scoped profile only.
- B flow gates on B-scoped profile only.
- E flow gates on E-scoped profile only.

### Roadmap awareness (scoped, not rigid)
- Codex must consult roadmap/progress sources when a task touches mapped systems or loop components.
- Mapped systems include: A cycle, B cycle, E cycle, H cycle, feeder cycle, and operations loop components.
- Source of truth for map/progress:
  - project_control/ROADMAP_SYSTEM_MAP.md
  - project_control/EXPECTATIONS/*.md
- If a task is unrelated to mapped systems, Codex must not force roadmap interaction.

### Progress updates (semi-automatic)
- For Implementation tasks affecting mapped systems, Codex should update roadmap/expectation progress in the same ticket when evidence supports the change.
- Do not update roadmap/expectation files for unrelated work.
- Do not inflate completion or reliability without evidence artifacts.

### Prompt number footer (mandatory)
- If the user message includes `PROMPT NUMBER: XXX`, Codex must end its final reply with the exact same line as the last line.
- Codex must not ask for prompt number when already provided.
- This applies to Inspection, Planning, Implementation, and Validation tasks.
