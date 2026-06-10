# F Seller Central MFA Cooldown Guards

## Manager Authority
- task_id: MGR_F_SELLER_CENTRAL_MFA_COOLDOWN_GUARDS
- job_ref: F-SELLER-CENTRAL-MFA-COOLDOWN-GUARDS
- flow: F
- task_type: bounded_code_repair
- status: parked
- authority: waits_for_f_mfa_cooldown_policy
- priority: high
- luke_action_required: 0

## Plain English
After the F MFA cooldown policy exists, SellerOne may need code or configuration guards so F login automation stops safely when Amazon MFA risk appears.

This ticket is parked until the policy document is complete and reviewed. It is not approval to touch Amazon or run F.

## Allowed Work
- inspect the completed `CONTROL/F_SELLER_CENTRAL_MFA_COOLDOWN_POLICY.md`
- inspect F login controller code and tests
- propose or implement bounded local guards if the policy clearly defines them
- add or adjust focused tests for cooldown detection and stop conditions
- write proof that the guard prevents repeated OTP/login attempts

## Forbidden Work
- no Seller Central login attempt
- no OTP request
- no voice-call request
- no authenticator setup
- no account recovery submission
- no Amazon security bypass
- no browser profile reset
- no cookie clearing
- no F scanner restart unless a later approved proof packet explicitly allows it
- no business runtime change
- no Windows Task Scheduler change
- no Codex automation change
- no Google Sheets write
- no Product DB or local DB alignment
- no price change
- no output deletion

## Acceptance Proof
- F login guard behaviour matches the approved cooldown policy.
- Focused tests prove soft cooldown, hard cooldown, and human escalation states.
- The guard stops repeated login/OTP attempts instead of retrying.
- No Amazon interaction occurred during implementation or tests.

## Retest
- retest_command: Run focused local F login/cooldown tests only.

## Stop Condition
Stop if implementation requires Amazon access, live F runtime, browser/session mutation, scheduler changes, or any protected action.
