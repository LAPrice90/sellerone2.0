# E Reliability Baseline 10 Runs v1

## Manager Authority
- task_id: MGR_E_RELIABILITY_BASELINE_10_RUNS_V1
- job_ref: E-10-RUN-BASELINE
- flow: E
- task_type: proof_gap
- priority: normal
- status: proved
- authority: luke_requested_build_list
- luke_action_required: 0

## Plain-English Purpose
Make the E reliability target visible on the Manager Task Board.

The expectation file says E should be measured across the last 10 comparable runs. That is not a repair failure, but it is a real proof job.

## Boundary
- allowed_scope: Read-only E run-history analysis, E reliability scoring plan, E manager proof mapping, and board-visible proof notes.
- forbidden_actions: no E live run without approved proof window; no worker cycle; no output deletion; no Google Sheets write; no price change; no queue edit; no local DB alignment; no fake success; no worker restart.
- proof_required: E reliability should be summarised from the last 10 completed E runs using existing run logs, manifests, and MOT results.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: Remove or revise this board card if the reliability metric is superseded. Do not edit E run history or proof outputs by hand.
- stop_condition: Stop if the proof needs a live E run or any protected action.

## Expected Build Output
- A clear 10-run E reliability summary:
  - completed runs
  - failed runs
  - warning runs
  - clean runs
  - recurring warning reasons
  - whether E is stable enough for expansion

## Acceptance Proof
- Reliability is calculated from outside evidence.
- Warnings are kept visible.
- E is not called finished just because the latest run has 0 failures.
