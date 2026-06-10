# SO21 Thread Role Hygiene

## Manager Authority
- task_id: MGR_SO21_THREAD_ROLE_HYGIENE
- job_ref: SO21-THREAD-ROLE-HYGIENE
- flow: SO21
- task_type: control_hygiene
- status: proved
- authority: first_overnight_run_efficiency_plan_2026-06-09
- priority: high
- luke_action_required: 0

## Plain English
SellerOne should have two management chats only: Rep and Operations.

Worker and Reviewer threads may exist, but each must be tied to one approved packet and must not look or behave like another manager.

## Allowed Work
- inspect thread titles and available thread summaries
- classify visible SellerOne threads as Rep, Operations, Worker, Reviewer, unrelated, or legacy
- create `CONTROL/SO21_THREAD_ROLE_HYGIENE.md`
- recommend naming, archiving, and routing rules
- rename or archive only if separately approved by the Rep or Operations authority and tool support is available

## Forbidden Work
- no new manager chats
- no worker execution
- no reviewer execution
- no business runtime changes
- no Task Scheduler changes
- no process kill
- no worker restart
- no Amazon/security action
- no price, Sheet, database, purchase, receiving, or send-to-Amazon action
- no deletion, movement, compression, purge, archive apply, or cleanup apply

## Acceptance Proof
- `CONTROL/SO21_THREAD_ROLE_HYGIENE.md` exists.
- It confirms the intended two-manager model.
- It lists the rule for Worker and Reviewer thread naming.
- It flags any visible thread hygiene risk without exposing unnecessary chat noise to Luke.

## Retest
- retest_command: inspect the hygiene report and confirm no new manager role was created.

