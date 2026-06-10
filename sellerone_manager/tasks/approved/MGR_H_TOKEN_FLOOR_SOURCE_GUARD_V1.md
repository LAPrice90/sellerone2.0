# H Token Floor Source Guard v1

## Manager Authority
- task_id: MGR_H_TOKEN_FLOOR_SOURCE_GUARD_V1
- job_ref: H-TOKEN-FLOOR-SOURCE-GUARD
- flow: H
- task_type: manager_read_only_guard
- status: proved
- authority: manager_approved_safe_proof
- priority: high
- luke_action_required: 0

## Plain English
H should not call a floor clean when the cost source is an unproved B fallback token. H can still report the floor, but the manager must label the floor source as risky until B proves the token cost.

## Current Evidence Summary
- H is currently exposed to B token-cost truth.
- Confirmed current H wrong-cost risk:
  - SKU `A2-T2AC-TW3L`
  - H first available token source: `stock_adjustment_fallback`
  - H token cost: 4.51
  - latest prior Sheet cost: 4.44
- B-wide fallback mismatch scale:
  - 1473 fallback tokens differ from latest prior Sheet cost.
  - 1096 are still available.
- Read-only comparison output:
  - `out/systems/M/b_token_sheet_comparison/h_next_available_cost_mismatch.csv`

## Allowed Work
- inspect H floor trace and runtime floor snapshot outputs
- add manager/MOT detection for H floors whose first cost source is an unproved `stock_adjustment_fallback` token
- label affected H floor rows as warning or blocked-from-clean-proof
- add focused H/MOT tests

## Forbidden Work
- no H run
- no scheduler pause or ownership change
- no price change
- no publish action
- no token correction
- no queue edit
- no Google Sheets write
- no local DB alignment
- no output deletion

## Acceptance Proof
- `A2-T2AC-TW3L` is not presented as clean floor proof while H uses the 4.51 fallback token.
- H manager output separates "floor calculated" from "floor source clean".
- H does not hide the B root problem by changing downstream floor math.
- H manager proof links back to B token-cost audit evidence instead of treating this as an H-only fault.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H

## Stop Condition
Stop before any price, publish, scheduler, token, queue, Sheet, DB, or live H action.

