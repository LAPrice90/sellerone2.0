# Runbook

## Purpose
- What this plan or system does:

## Standard run order
```powershell
# add commands here
```

## Validation steps
- Step 1:
- Step 2:
- Step 3:
- Step 4:
  - if live proof can clash with an active owner, run `python scripts/one_off/P002_plan_forced_proof_window.py --flow <flow>` first and use the safe boundary it reports

## Expected outputs
- Output:
- Path:
- What good looks like:

## Health checks
- Check:
- Pass condition:
- Warning condition:
- Fail condition:

## Failure recovery
- If input is stale:
- If output is missing:
- If tests fail:
- If runtime ownership is unclear:
- If proof would clash with a live loop:
  - do not wait vaguely for the next cycle
  - use the forced proof planner and record the exact boundary required

## Archive note
- What to preserve when this plan is finished:
