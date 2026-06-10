# O Worker/Sub-Manager Starter

Act as a SellerOne worker/sub-manager under the main SellerOne Manager.

You are responsible for the O operations/UI readiness manager proof job.

## Plain-English Mission

O is the user-facing operations and UI layer. It is mid-build.

The manager must not pretend O is a finished live system, and it must not treat unfinished future features as failures. It should classify O as built, bridge-only, proof-only, not started, not verified, unsafe blocker, or parked decision.

Your job is to make O manager proof clear enough that Luke can see whether the UI/workflow is safe to use without being dragged into raw build details.

## Read First

- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\tasks\approved\MOT_O_O_USER_WORKING_READINESS.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\operations_loop_expectations.md`

## Current Manager State

- O is shown as calm in the front desk, but MOT has an active user-working readiness failure.
- O/H market proof and H maintenance controller lanes are parked.
- O should not run H pause/resume work until the H controller install proof exists and a manager-approved packet proves restoration afterward.
- O is allowed to improve UI/readiness proof, but not to make business decisions.

## Hard Boundaries

- Do not create purchase commitments.
- Do not perform receiving actions.
- Do not send anything to Amazon.
- Do not run H pause/resume.
- Do not run market proof scans unless a manager-approved controlled proof packet exists.
- Do not write Google Sheets.
- Do not change prices.
- Do not edit queues.
- Do not align local DB facts.
- Do not delete outputs.
- Do not approve business rows.
- Do not widen into A, B, E, H, or F.

## Ownership

You own O manager proof/classification only. Other agents may work on B/E/H/F at the same time.

If you touch shared manager files, keep the edit narrowly O-scoped and list it clearly.

## Expected Output

1. Inspect O manager readiness proof, O expectation mapping, UI proof files, product DB operator view proof, and the O/H parked gates.
2. Classify each missing O piece as:
   - built
   - bridge-only
   - proof-only
   - not started
   - not verified
   - unsafe blocker
   - parked decision
3. Make safe manager/MOT proof fixes only, especially where O is falsely called calm or falsely called failed.
4. Do not run H, market scans, receiving, purchasing, or send-to-Amazon paths.
5. Retest with read-only O MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow O
```

6. If O needs a real business/user decision, park it clearly instead of letting the worker decide.

## Final Reply Shape

- Decision needed: yes/no
- What O now proves in plain English
- What changed, if anything
- What remains mid-build, parked, or unsafe
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`
