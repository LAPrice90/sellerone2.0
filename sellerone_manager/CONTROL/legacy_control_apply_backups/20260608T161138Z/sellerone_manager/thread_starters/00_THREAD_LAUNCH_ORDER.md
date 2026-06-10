# SellerOne Manager Worker Thread Launch Order

Use these prompts to start separate Codex chats without re-explaining the manager setup.

The main rule is simple:

- Main Manager owns the board.
- Cycle sub-managers own proof and classification for one cycle.
- Worker agents only repair from an approved manager task packet.
- Nobody claims complete without MOT or named proof clearing the same issue.

## Current Board

Observed from the manager state on 2026-05-30:

- A is calm and proved.
- B is the active blocker.
- E is warning/proof-gap work, not a live emergency.
- H is high-risk and must stay guarded until its independent manager/MOT layer is strong.
- F is mostly calm, but login/snapshot/source proof needs cleanup.
- O is mid-build and should be treated as user-working readiness work, not as a failed live cycle.

## Recommended Thread Order

1. B worker/sub-manager
   - Reason: B is the active blocker on the main board.
   - Starter file: `thread_starters/B_WORKER_STARTER.md`

2. H sub-manager
   - Reason: H controls repricing and must not be trusted until its manager/MOT layer is stronger.
   - Starter file: `thread_starters/H_WORKER_STARTER.md`

3. F sub-manager
   - Reason: F needs cleaner proof around login/snapshot/source state, without touching the scanner queue.
   - Starter file: `thread_starters/F_WORKER_STARTER.md`

4. O sub-manager
   - Reason: O is mid-build. It needs readiness classification and proof, not false failure noise.
   - Starter file: `thread_starters/O_WORKER_STARTER.md`

5. E sub-manager
   - Reason: E has warnings but no active fail. It can be handled after the blockers.
   - Starter file: `thread_starters/E_WORKER_STARTER.md`

## How Each Worker Must Finish

Every worker reply should end with:

- Decision needed: yes/no
- What their cycle now proves in plain English
- What changed
- What remains parked or blocked
- Exact files changed
- Exact proof run and result
- Recommended next move, without saying `no further action needed now`

## Main Manager Follow-Up

After a worker finishes, the main manager should refresh:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow all
python -m sellerone_manager.app --flow all --read-only --write-report
python -m sellerone_manager.app --refresh-approved-tasks
python -m sellerone_manager.app --what-next
```

The main manager should then update Luke in plain English only if:

- a blocker cleared
- a new blocker appeared
- a real decision is needed
- a protected boundary was reached
- the next worker lane has changed
