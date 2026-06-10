# SO21 Maintenance Script Quality Review

## Manager Authority
- task_id: MGR_SO21_MAINTENANCE_SCRIPT_QUALITY_REVIEW
- job_ref: SO21-MAINTENANCE-SCRIPT-QUALITY-REVIEW
- flow: SO21
- task_type: review_planning
- status: proved
- authority: luke_requested_tomorrow_script_review
- priority: normal
- luke_action_required: 0

## Plain English
Luke wants the maintenance/control script work reviewed for bugs, improvement ideas, and efficiency suggestions that can be sorted tomorrow.

This is review-only. It should not change runtime, scheduler state, or business data.

## Allowed Work
- identify the relevant maintenance/control script or design document
- inspect for likely bugs, fragile assumptions, missing checks, and avoidable inefficiency
- separate must-fix safety issues from nice-to-have improvements
- write a plain-English review note under `CONTROL/`
- create follow-up tickets only for clear, bounded fixes

## Forbidden Work
- no code changes during this review packet
- no runtime pause or restart
- no process kill
- no Task Scheduler change
- no worker restart
- no Amazon login/security action
- no price, Sheet, database, output, purchase, receiving, or send-to-Amazon action
- no permanent deletion

## Acceptance Proof
- A review note exists under `CONTROL/`.
- Findings are grouped as bugs, risks, efficiency improvements, and tomorrow recommendations.
- No implementation or protected action occurred.

## Retest
- retest_command: Inspect the review note and confirm it is review-only.

## Stop Condition
Stop if the review needs access to a script Luke has not identified or if checking it would require running state-changing code.
