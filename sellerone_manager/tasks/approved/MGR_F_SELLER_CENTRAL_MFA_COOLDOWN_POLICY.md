# F Seller Central MFA Cooldown Policy

## Manager Authority
- task_id: MGR_F_SELLER_CENTRAL_MFA_COOLDOWN_POLICY
- job_ref: F-SELLER-CENTRAL-MFA-COOLDOWN-POLICY
- flow: F
- task_type: planning_only_login_safety
- status: approved
- authority: luke_approved_planning_ticket
- priority: high
- luke_action_required: 0

## Plain English
SellerOne needs a safe Amazon Seller Central login policy for MFA, SMS failures, voice-call fallback, trusted devices, cooldowns, and human escalation.

This ticket turns the research report into a practical F-cycle operating plan. It does not attempt a login, request an OTP, clear cookies, change browser profiles, bypass MFA, or modify Seller Central.

## Business Reason
Repeated login attempts can make Seller Central access worse. The F cycle needs a clear rule for when to stop automated login attempts, when to wait, and when to ask Luke.

Luke escalation email:

- `laprice90@gmail.com`

## Evidence Basis
Use the report supplied by Luke:

- `C:\Users\Luke\Downloads\deep-research-report (26).md`

Main findings to preserve:

- Seller Central supports SMS, voice call, and authenticator app methods.
- Amazon does not publish a clean numeric Seller Central OTP retry threshold.
- Repeated OTP attempts can trigger cooldown behaviour.
- Trusted-device status can be disturbed by cookie clearing, browser changes, device changes, VPN/proxy/IP/location changes, and logged-out app states.
- SMS failures may also be carrier or handset delivery problems.
- Safer internal posture is a soft cooldown after first failure and hard cooldown after explicit rate-limit language or repeated delivery failures.

## Allowed Work
- read the supplied research report
- inspect existing F login control files and F login recovery notes
- create a planning/control document under `sellerone_manager/CONTROL/`
- define F login cooldown states
- define safe automation stop rules
- define human escalation points
- define what normal non-login F work may continue during cooldown
- define future implementation tickets if needed

## Forbidden Work
- no Seller Central login attempt
- no OTP request
- no voice-call request
- no authenticator setup attempt
- no account recovery submission
- no cookie clearing
- no browser profile reset
- no VPN, IP, proxy, device, or network change
- no Amazon security bypass
- no worker restart
- no F scanner restart
- no business runtime change
- no Windows Task Scheduler change
- no Codex automation change
- no Google Sheets write
- no Product DB or local DB alignment
- no price change
- no output deletion

## Required Deliverable
Create:

- `sellerone_manager/CONTROL/F_SELLER_CENTRAL_MFA_COOLDOWN_POLICY.md`

The document must include:

- login-risk triggers
- soft cooldown rule
- hard cooldown rule
- when to stop all login attempts
- when to ask Luke
- what can continue during cooldown
- official recovery route hierarchy
- notes on authenticator app setup after access is restored
- future implementation approach

## Acceptance Proof
- `CONTROL/F_SELLER_CENTRAL_MFA_COOLDOWN_POLICY.md` exists.
- The policy clearly protects against repeated OTP attempts.
- The policy clearly separates read-only non-login work from login/session work.
- The policy includes Luke escalation via `laprice90@gmail.com`.
- The policy states that Amazon security must not be bypassed.
- No login, OTP, browser, runtime, scheduler, database, Sheet, price, output, or Amazon action occurred.

## Retest
- retest_command: Inspect `CONTROL/F_SELLER_CENTRAL_MFA_COOLDOWN_POLICY.md` and confirm no runtime or Amazon interaction occurred.

## Stop Condition
Stop and return to Rep if the work requires an actual login attempt, OTP request, browser/session change, Amazon recovery action, F runtime restart, or any protected action.
