# SO21 Control Flow Confirmation v1

## Manager Authority
- task_id: MGR_SO21_CONTROL_FLOW_CONFIRMATION_V1
- job_ref: SO21-CONTROL-FLOW-CONFIRMATION
- flow: SO21
- task_type: control_confirmation
- status: proved
- authority: luke_approved_blueprint_finalisation
- priority: high
- luke_action_required: 0

## Plain English
SellerOne 2.1 has the new coding-management shape in place. This ticket confirms the route works before more old material is removed.

The route is: Luke talks to Rep, Rep creates or explains tickets, Builders work one approved ticket, Reviewers prove or return it, and Operations/Custodian report through control files instead of noisy chat.

## Allowed Work
- inspect the current 2.1 control files
- inspect the approved task packet index and generated current work views
- confirm the Rep, Builder, Reviewer, Operations, and Custodian responsibilities are written down and non-conflicting
- confirm temporary worker threads can execute from approved packets without using this Rep chat as technical memory
- identify any missing instruction or queue link that would stop the new process working
- write a short confirmation report under `CONTROL/`

## Forbidden Work
- no business runtime changes
- no Windows Task Scheduler changes
- no Codex automation changes
- no worker runs or restarts
- no queue status movement
- no price changes
- no Google Sheets writes
- no Product DB or local DB alignment
- no output deletion
- no Amazon login or security action
- no redesign beyond the current SellerOne 2.1 model

## Acceptance Proof
- The report confirms whether the new flow is ready for normal use.
- The report lists any exact gaps that still block temporary worker-thread execution.
- The report confirms business runtime is outside SellerOne 2.1 stabilisation unless Luke separately approves a specific runtime task.
- The report does not create a second task list outside the packet queue.

## Retest
- retest_command: python -m sellerone_manager.app --refresh-approved-tasks

## Stop Condition
Stop and return to Luke if the work discovers that the canonical queue, role split, or protected-action boundaries disagree in a way that would make worker execution unsafe.
