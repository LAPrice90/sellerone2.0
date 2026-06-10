# H Reliability Window Proof v1

## Manager Authority
- task_id: MGR_H_RELIABILITY_WINDOW_PROOF_V1
- job_ref: H-RELIABILITY-WINDOW
- flow: H
- task_type: bounded_manager_proof
- status: proved
- authority: standing_safe_manager_proof
- priority: normal
- luke_action_required: 0

## Boundary
- allowed_scope: H manager/MOT proof extension only; read the last completed H manifests, terminal markers, publish markers, existing H MOT history, and H expectation file; add or refine manager-only H reliability-window reporting if needed; focused manager tests only.
- forbidden_actions: no H run; no scheduler ownership change; no publish; no price change; no queue edit; no Google Sheets write; no local DB alignment; no output deletion; no staged snapshot deletion; no worker restart; no repricing logic change; no scope widening.
- proof_required: The manager can report the last 10 completed H runs as clean, warning, or failed using outside proof only; latest-run H MOT rows remain truthful; retest with the read-only H MOT; success does not require live H execution.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: Use git diff for any manager-code rollback. Do not edit H runtime outputs, manifests, terminal markers, publish markers, cleanup ledgers, or MOT CSVs by hand.
- stop_condition: Stop if the work would need a live H run, scheduler change, publish, price write, queue edit, Sheet write, local DB alignment, output deletion, worker restart, repricing-code change, or any protected business action.

## Plain English Purpose
H already has latest-run manager proof. This packet makes the longer stability target visible: the manager should be able to say whether the last 10 completed H runs were clean, warned, or failed before calling H stable.

## Acceptance Proof
- H remains inspected from the outside only.
- A board-visible manager proof exists for the 10-run reliability window.
- The proof separates latest-run readiness from longer-run stability.
- The H expectation file remains the source of the stability target.
