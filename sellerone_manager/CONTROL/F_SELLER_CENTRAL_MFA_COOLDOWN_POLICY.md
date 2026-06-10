# F Seller Central MFA Cooldown Policy

Created UTC: 2026-06-08
Job reference: `F-SELLER-CENTRAL-MFA-COOLDOWN-POLICY`
Evidence source: `C:\Users\Luke\Downloads\deep-research-report (26).md`

## Purpose

This policy gives F a safe rulebook for Amazon Seller Central MFA and login-challenge behavior.

Plain English: Seller Central login is like a locked front door with an alarm. If the key code fails or the alarm asks for extra proof, SellerOne must not keep rattling the handle. It must step back, wait, and ask Luke when the next step needs a human choice.

The goal is to prevent repeated SMS, voice-call, OTP, or login-challenge attempts from making Amazon access worse.

## Scope

This policy applies to F-cycle behavior that detects or approaches Amazon Seller Central login, MFA, SMS, phone verification, voice-call verification, authenticator, trusted-device, or account-recovery prompts.

It covers planning rules only:

- when F must enter cooldown
- when F must stop all login attempts
- when F may continue read-only non-login work
- when Luke must be asked by email
- what future guard work must enforce

## Hard No-Touch Boundary

This policy does not approve any Amazon interaction.

This policy does not approve:

- Seller Central interaction
- login attempts
- OTP requests
- OTP entry
- OTP storage
- voice-call requests
- authenticator setup
- account recovery submission
- Amazon security bypass
- disabling MFA
- browser profile changes
- cookie clearing
- session mutation
- VPN, proxy, IP, device, or network changes
- F runtime changes
- F061 or worker starts, restarts, or live proof windows
- Task Scheduler changes
- Codex automation changes
- queue edits
- Google Sheets writes
- local DB or Product DB alignment
- price changes
- output deletion
- business runtime changes

Any action in that list needs a separate approved packet or Luke decision before it happens.

## Evidence Basis

The research report supports these operating assumptions:

- Seller Central verification can involve SMS, voice call, or an authenticator app.
- Amazon does not publish a clear public numeric Seller Central OTP retry limit.
- Repeated verification attempts can trigger cooldown or rate-limit behavior.
- Some seller reports describe short waits escalating into 24-hour blocks.
- Amazon-related recovery can take 1 to 2 days, and repeated recovery submissions may restart the wait.
- Trusted-device status can be disturbed by cookie clearing, browser changes, device changes, VPN/proxy use, IP/location/network changes, and logged-out app states.
- SMS failure can be Amazon-side security friction, carrier blocking, handset settings, coverage, short-code filtering, or regional/operator outage.

Because the exact cause is often unclear from the page text alone, SellerOne must use the safer interpretation: repeated attempts are risky until a human confirms the recovery path.

## Login-Risk Triggers

F must treat any of these as a login-risk trigger:

- Seller Central says SMS cannot be sent.
- Seller Central says to wait before requesting another OTP.
- Seller Central says too many OTPs were requested.
- Seller Central says to try again later, tomorrow, or after 24 hours.
- The SMS option is not available or not clickable.
- An OTP/code wait appears and no fresh code is safely available.
- Two delivery failures occur in the same incident.
- SMS and voice-call routes both fail in the same incident.
- The page shows MFA, CVF, phone verification, authenticator-only, passkey, security-key, captcha, or manual challenge evidence.
- The next step would require changing cookies, browser profile, device, network, VPN/proxy, IP, or location.
- The next step would require choosing between trusted device, backup method, voice call, cookie clear, different browser, different network, or account recovery.

## Cooldown States

F login control should use these plain states:

- `normal_scan_only`: F may continue safe non-login scanner work. It must not attempt Seller Central phone, SMS, OTP, voice, or MFA flows.
- `login_attempt_mode`: A separately approved, bounded state for a deliberate login attempt. This policy does not activate or approve that state.
- `soft_cooldown`: F saw early login-risk evidence and must pause login attempts for a short wait.
- `hard_cooldown`: F saw rate-limit, repeated-failure, or stronger challenge evidence and must stop login attempts for a long wait.
- `manual_challenge`: F reached a point where Luke or a trusted human must choose the official recovery route.

## Soft Cooldown Rule

Enter `soft_cooldown` immediately after the first weak MFA or delivery failure signal.

Examples:

- SMS cannot be sent.
- The page says to wait before requesting another OTP.
- One SMS delivery route fails.
- One OTP/code wait appears with no safe fresh code available.

Minimum soft cooldown:

- 15 minutes from the last trigger.

During soft cooldown:

- do not request another SMS
- do not request a voice call
- do not enter an OTP
- do not refresh or loop the login flow to provoke another challenge
- do not change browser, cookies, profile, device, VPN/proxy, IP, or network
- allow only safe non-login work that cannot create another Seller Central verification prompt

If the same incident produces a second delivery failure, explicit rate-limit wording, or a stronger manual challenge, upgrade to `hard_cooldown` or `manual_challenge`.

## Hard Cooldown Rule

Enter `hard_cooldown` immediately after any strong rate-limit or repeated-failure signal.

Examples:

- "too many OTPs"
- "try again later"
- "try again tomorrow"
- "wait 24 hours"
- SMS and voice both fail in the same incident
- two consecutive delivery failures in the same incident
- repeated login prompts after browser/session/network churn

Minimum hard cooldown:

- 24 hours from the last trigger.

During hard cooldown:

- stop all automated login attempts
- stop all SMS requests
- stop all voice-call requests
- stop all OTP handling
- stop all browser/session/cookie/profile recovery actions
- keep existing authenticated sessions stable if they already work
- continue only read-only non-login work that cannot touch Seller Central sign-in or generate MFA

If account recovery has been submitted by a human outside this policy, F must not attempt login again until Amazon responds or at least 48 hours have passed, whichever is safer under the current approved packet.

## Stop Conditions

F must stop login work and return control to the manager or Rep if any of these happen:

- Amazon shows explicit rate-limit or cooldown language.
- A second OTP/SMS/voice delivery failure appears in the same incident.
- The page requires captcha, authenticator-only, passkey, security key, identity verification, or manual account recovery.
- The next step needs a human choice about trusted device, backup method, voice call, cookie clear, browser change, device change, network change, or account recovery.
- The root cause cannot be distinguished between Amazon cooldown and telecom delivery failure.
- The next step would touch cookies, profile, browser session, OTP, credentials, scheduler, queue, Sheets, database, prices, outputs, or business runtime.

When stopped, F should record a redacted reason label only. It must not store OTPs, cookies, tokens, credentials, full phone numbers, or raw security-page secrets.

## Luke Escalation Path

Escalate to Luke when the next safe step needs a human decision.

Use this email:

- `laprice90@gmail.com`

The escalation should say, in plain English:

- what F saw
- whether the state is `soft_cooldown`, `hard_cooldown`, or `manual_challenge`
- the last redacted trigger label
- the earliest safe recheck time
- the official recovery choices available, if visible from existing redacted evidence
- that SellerOne has not requested another OTP, entered an OTP, changed the browser/session, or bypassed Amazon security

Do not include OTPs, cookies, credentials, tokens, screenshots with secrets, or full phone numbers.

## Official Recovery Route Hierarchy

Future human recovery should prefer the least disruptive official route first:

1. Use an already trusted device or already enrolled authenticator app if one is available.
2. Use an already registered backup method if Amazon presents it.
3. Use one human-controlled alternative method only if Amazon presents it and Luke chooses it.
4. If normal official methods fail, use Amazon's account-recovery route as a human action only.
5. After access is restored, consider setting up an authenticator app and a different backup method, because that reduces dependence on fragile SMS delivery.

This hierarchy is not permission for automation to perform any of those actions. It is only the decision order for a future approved human recovery path.

## What Can Continue During Cooldown

F may continue work only when the work cannot cause another Seller Central login or MFA prompt.

Allowed during cooldown:

- local read-only planning
- local code inspection
- local tests that use fake fixtures only
- non-login scanner work that does not create or mutate a Seller Central session
- reporting redacted cooldown state to manager control files when a later approved guard packet allows it

Not allowed during cooldown:

- opening Seller Central
- refreshing the login page
- pressing "didn't receive code"
- requesting SMS
- requesting voice call
- entering OTP
- clearing cache or cookies
- changing browser profile
- changing device, VPN/proxy, IP, network, or location
- restarting F to force a new login opportunity

## Future Guard Work Should Enforce

After this policy exists, future F guard work should enforce the policy at the earliest login-control point, like adding a stop sign before a risky road rather than cleaning up after the crash.

Future guards should:

- detect the login-risk trigger labels listed in this policy
- switch to `soft_cooldown` after the first weak trigger
- switch to `hard_cooldown` after explicit rate-limit wording or repeated delivery failure
- switch to `manual_challenge` for captcha, authenticator-only, passkey, security-key, account-recovery, or human-choice paths
- block Seller Central login attempts while `normal_scan_only`, `soft_cooldown`, `hard_cooldown`, or `manual_challenge` is active
- require a separate approved action before `login_attempt_mode` can run
- write a redacted cooldown reason and until-time
- avoid storing OTPs, credentials, cookies, tokens, raw phone numbers, or raw security challenge content
- keep read-only non-login work separate from login/session work
- prove behavior with local fake-page tests before any live proof is considered
- leave live proof, runtime restarts, and Amazon interaction parked unless a later approved proof packet explicitly allows them

## Policy Result

This policy is a planning-only control document.

It protects F by requiring cooldown after Seller Central MFA risk appears, hard stopping repeated OTP or phone attempts, and escalating human recovery choices to Luke at `laprice90@gmail.com`.

It does not approve Amazon interaction, login attempts, OTP request, OTP entry, OTP storage, browser/session mutation, F runtime changes, scheduler changes, queue movement, Sheets writes, database alignment, price changes, output changes, automation changes, or business runtime changes.
