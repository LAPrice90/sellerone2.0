# Debug Batch 001

## Status
- Not active for this ticket.

## Trigger rule
- Use this file only if a later batch finds a real contract failure such as:
  - stale health versus newer live files
  - unresolved join mismatch affecting trusted rows
  - CSV structure or schema drift
  - raw versus qualified demand mismatch that cannot be solved inside the planned build scope

## Working rule
- Debug work must stay root-cause first.
- Do not patch downstream outputs to hide a broken owner path.
