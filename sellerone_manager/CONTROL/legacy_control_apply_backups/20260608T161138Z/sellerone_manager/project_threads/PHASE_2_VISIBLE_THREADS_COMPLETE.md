# Phase 2 Visible Project Threads Complete

Status: complete for thread operating setup.

This does not mean the B, H, F, O, and E work is complete. It means SellerOne now has a clear visible-thread operating model so each worker conversation can start from the right role, boundaries, proof path, and expected output.

## What Phase 2 Now Proves

- There is one canonical visible-thread launch folder:

```text
sellerone_manager/project_threads/
```

- The older duplicate prompt folders are no longer the operating source of truth:

```text
sellerone_manager/thread_prompts/
sellerone_manager/agent_launch_prompts/
sellerone_manager/thread_starters/
```

- A thread register exists:

```text
sellerone_manager/project_threads/THREAD_REGISTER.csv
```

- Every visible worker thread has:

```text
role
read-first files
current job
allowed work
forbidden work
proof command
stop condition
final reply shape
```

- The main manager protocol now has a visible project-thread rule, so future manager chats know not to confuse visible threads with background sub-agents.

## Ready Threads

Ready to open first:

```text
01_B_WORKER_THREAD.md
```

Ready after B or in parallel only if the work stays inside boundaries:

```text
02_H_SAFETY_THREAD.md
03_F_PROOF_THREAD.md
04_O_BUILD_THREAD.md
05_E_PROOF_THREAD.md
```

Ready after worker results return:

```text
06_MAIN_MANAGER_COMBINER_THREAD.md
```

Watch-only:

```text
07_A_WATCH_ONLY_THREAD.md
```

## Current Operating Rule

Use visible project threads like departments:

- B owns B order proof and active blocker work.
- H owns H safety packaging only.
- F owns scanner/source proof only.
- O owns mid-build readiness only.
- E owns analytics confidence proof only.
- Main Manager owns the combined board.

Do not let any thread cross into:

- prices
- queues
- Sheets
- publishing
- local DB alignment
- output deletion
- live worker cycle runs without approved proof
- scheduler ownership changes without restoration proof
- business judgement

## Phase 2 Verification

Verified:

- all canonical project-thread prompt files exist
- `THREAD_REGISTER.csv` gives launch order and ownership
- `MANAGER_CHAT.md` contains the visible project-thread rule
- files are ASCII-safe

## Phase 3 Start Point

Phase 3 is B active blocker execution.

Start with:

```text
sellerone_manager/project_threads/01_B_WORKER_THREAD.md
```

The B thread should return one of:

- B proof cleared
- B bounded repair packets updated
- a real protected decision path for the token shortage/receipt correction issue

