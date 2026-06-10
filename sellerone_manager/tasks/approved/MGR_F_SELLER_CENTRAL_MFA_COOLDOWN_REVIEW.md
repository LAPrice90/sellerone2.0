# F Seller Central MFA Cooldown Review

## Manager Authority
- task_id: MGR_F_SELLER_CENTRAL_MFA_COOLDOWN_REVIEW
- job_ref: F-SELLER-CENTRAL-MFA-COOLDOWN-REVIEW
- flow: F
- task_type: reviewer_packet
- status: parked
- authority: waits_for_f_mfa_cooldown_policy_or_guards
- priority: normal
- luke_action_required: 0

## Plain English
The F MFA cooldown policy and any future cooldown guards need fresh review before SellerOne relies on them.

This review confirms the system is safer around Amazon login risk and that it does not create a hidden bypass or retry loop.

## Allowed Work
- review `CONTROL/F_SELLER_CENTRAL_MFA_COOLDOWN_POLICY.md`
- review any later F cooldown guard changes if implemented
- check focused test evidence
- verify no Amazon interaction, login, OTP request, browser reset, or runtime restart occurred
- return clear findings to Operations and Rep

## Forbidden Work
- no Seller Central login attempt
- no OTP request
- no voice-call request
- no authenticator setup
- no account recovery submission
- no Amazon security bypass
- no F runtime restart
- no Task Scheduler change
- no database, Sheet, price, output, or business runtime change

## Acceptance Proof
- Reviewer confirms the policy is safe and clear, or returns exact gaps.
- Reviewer confirms future guards, if present, stop repeated MFA attempts.
- Reviewer confirms Luke escalation and protected-action boundaries are clear.
- Reviewer confirms no Amazon/security action was performed during review.

## Retest
- retest_command: Inspect the policy, diff, and focused local test evidence.

## Stop Condition
Stop if review would require live Amazon access, MFA attempts, session mutation, or protected action.
