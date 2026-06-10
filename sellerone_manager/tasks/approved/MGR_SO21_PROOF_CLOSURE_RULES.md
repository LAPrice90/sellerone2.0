# SO21 Proof Closure Rules

## Manager Authority
- task_id: MGR_SO21_PROOF_CLOSURE_RULES
- job_ref: SO21-PROOF-CLOSURE-RULES
- flow: SO21
- task_type: control_process
- status: proved
- authority: first_overnight_run_efficiency_plan_2026-06-09
- priority: high
- luke_action_required: 0

## Plain English
The first overnight run showed that proof closure needs clearer grades.

A safe business pass should not look blocked just because a report has a tiny formatting issue. Safety and material evidence must stay strict, but format-only repairs should be labelled clearly.

## Allowed Work
- inspect recent worker and reviewer notes
- define proof result grades such as pass, pass with minor format repair, returned material gap, blocked needs Luke, and failed safety
- create `CONTROL/SO21_PROOF_CLOSURE_RULES.md`
- recommend how Operations should close, repair, or escalate waiting-proof items

## Forbidden Work
- no implementation changes
- no weakening safety checks
- no automatic approval of material gaps
- no business runtime changes
- no Task Scheduler changes
- no process kill
- no worker restart
- no Amazon/security action
- no price, Sheet, database, purchase, receiving, or send-to-Amazon action
- no deletion, movement, compression, purge, archive apply, or cleanup apply
- no queue status movement except reporting evidence

## Acceptance Proof
- `CONTROL/SO21_PROOF_CLOSURE_RULES.md` exists.
- It separates safety failures, material proof gaps, Luke decisions, and minor format repairs.
- It defines how Operations should prevent waiting-proof items from sitting idle.
- It does not approve unsafe proof shortcuts.

## Retest
- retest_command: inspect the proof closure rules and confirm safety checks remain strict.
