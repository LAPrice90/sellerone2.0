# Coding Plan

Date:
Scope:

## 1) Phase summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 1 |  |  |  | yes/no | planned |
| Phase 2 |  |  |  | yes/no | planned |

## 2) Phase details

### Phase 1 - Title
Goal:
- 

Files allowed to change:
- 

Implementation tasks:
- 

Isolated verification:
- command:
- expected result:

Monitored validation:
- live proof needed:
- forced proof window:
- artifacts to poll:
- poll cadence:
- success threshold:
- timeout rule:
- fallback if forced proof is blocked:
- next automatic step after success:
- notification mode:
- user interruption threshold:

Phase status:
- code fix applied:
- isolated verification passed:
- monitored validation:

### Phase 2 - Title
Goal:
- 

Files allowed to change:
- 

Implementation tasks:
- 

Isolated verification:
- command:
- expected result:

Monitored validation:
- live proof needed:
- forced proof window:
- artifacts to poll:
- poll cadence:
- success threshold:
- timeout rule:
- fallback if forced proof is blocked:
- next automatic step after success:
- notification mode:
- user interruption threshold:

Phase status:
- code fix applied:
- isolated verification passed:
- monitored validation:

## 3) Global completion rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a forced proof window exists.
- If the monitoring window expires, record the exact parked condition and the exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
