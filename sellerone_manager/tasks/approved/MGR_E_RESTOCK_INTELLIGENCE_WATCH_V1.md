# E Restock Intelligence Watch v1

## Manager Authority
- task_id: MGR_E_RESTOCK_INTELLIGENCE_WATCH_V1
- job_ref: E-RESTOCK-INTEL-WATCH
- flow: E
- task_type: manager_monitoring
- priority: normal
- status: proved
- authority: e_cycle_sub_manager_monitoring
- luke_action_required: 0

## Plain-English Purpose
Keep E visible on the Manager Task Board even when it has warning-only proof instead of an active repair failure.

E is Restock Intelligence. This card tracks whether E is still safe to use as evidence support for restocking while it is not yet clean enough to become buying authority.

## Boundary
- allowed_scope: Read-only E MOT checks, E expectation reconciliation, E coverage and confidence proof, and manager-board visibility notes.
- forbidden_actions: no E live run; no worker cycle; no publish enablement; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no worker restart; no business restock decision; no scope widening into A, B, H, F, or O repairs.
- proof_required: E MOT must show 0 E failures, E warnings must remain visible rather than hidden, optional publish proof must stay not_verified unless publishing becomes required, and E must not be treated as final buying authority while ROI coverage or B money proof is warning-labelled.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: Remove this board visibility packet if it misrepresents E status. Do not edit E outputs or MOT rows to make the card look better.
- stop_condition: Stop if E gets a real MOT failure, if E needs a live proof run, or if the work would require any protected action.

## Acceptance Proof
- Refresh E MOT without running E.
- Refresh approved task packets so this card appears on the Manager Task Board.
- Confirm E remains warning-labelled if ROI coverage is weak or B money proof is bridge-labelled.
- Confirm no buying decision, Sheet write, price change, queue edit, DB alignment, output deletion, or live worker run happened.

## Expected End State
Luke can follow E on the Manager Task Board as a visible monitoring job:

- proved outputs stay visible
- warning-only gaps stay visible
- no fake repair is created
- no automatic restock authority is implied
