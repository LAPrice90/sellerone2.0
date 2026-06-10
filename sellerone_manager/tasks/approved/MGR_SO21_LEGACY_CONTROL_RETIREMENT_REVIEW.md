# SO21 Legacy Control Retirement Review

## Manager Authority
- task_id: MGR_SO21_LEGACY_CONTROL_RETIREMENT_REVIEW
- job_ref: SO21-LEGACY-CONTROL-RETIREMENT-REVIEW
- flow: SO21
- task_type: reviewer_packet
- status: parked
- authority: waits_for_legacy_control_manifest
- priority: normal
- luke_action_required: 0

## Plain English
After the old-control retirement manifest is created, a fresh Reviewer should check it before any follow-up cleanup plan is trusted.

This prevents the cleanup worker from becoming its own proof.

## Allowed Work
- review `CONTROL/SO21_LEGACY_CONTROL_RETIREMENT_MANIFEST.md`
- confirm all listed paths match the old-control inventory scope
- confirm no business runtime is included as cleanup material
- confirm no destructive action was performed
- return clear findings to Operations and Rep

## Forbidden Work
- no file deletion
- no file moving
- no compression
- no purging
- no archiving
- no renaming
- no Task Scheduler changes
- no business runtime changes
- no queue movement unless proof rules allow it after review
- no price, Sheet, database, or Amazon changes

## Acceptance Proof
- Reviewer confirms the manifest is complete enough to use as a planning base, or returns exact gaps.
- Reviewer confirms no destructive cleanup occurred.
- Reviewer confirms future destructive actions remain approval-gated.

## Retest
- retest_command: Inspect the retirement manifest and compare it against the approved packet scope.

## Stop Condition
Stop if the manifest proposes destructive work without exact paths, recovery route, and Luke approval gate.
