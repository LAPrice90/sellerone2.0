# SO21 Credential Token Status Check

## Manager Authority
- task_id: MGR_SO21_CREDENTIAL_TOKEN_STATUS_CHECK
- job_ref: SO21-CREDENTIAL-TOKEN-STATUS-CHECK
- flow: SO21
- task_type: credential_validation
- status: proved
- authority: luke_requested_safe_token_status_check_2026-06-09
- priority: high
- luke_action_required: 0

## Plain English
Luke has rotated the Amazon LWA credential used for Amazon API access and wants to know whether the new credential works.

This task is a safe status check only. The worker may prove whether a token request succeeds, but must never print, store, copy, paste, or expose the token or secret value.

## Business Reason
SellerOne needs confidence that the rotated credential is valid before relying on it in normal work.

## Target
- Amazon LWA credential used for Amazon API access.

## Allowed Work
- inspect Amazon LWA credential names, environment variable names, config keys, and timestamps without printing secret values
- request an Amazon LWA token/status only through the existing Amazon API credential path
- report only:
  - provider or credential label, expected to be Amazon LWA
  - HTTP/status code
  - pass/fail
  - expiry/validity status if returned without exposing token content
  - any non-secret error category
- write a short result note under `CONTROL/`

## Forbidden Work
- no token value printed in chat, files, logs, screenshots, or reports
- no secret value printed in chat, files, logs, screenshots, or reports
- no credential rotation
- no provider account changes
- no Amazon security bypass
- no MFA bypass
- no password reset
- no Task Scheduler change
- no worker restart
- no business runtime pause, stop, kill, or restart
- no price changes
- no queue edits outside approved packet status updates
- no Google Sheets writes
- no database writes or alignment
- no purchase, receiving, or send-to-Amazon

## Stop Condition
Stop and report `needs user decision` if:

- the Amazon LWA credential target is not clear from safe metadata
- more than one possible Amazon LWA credential could be the rotated one
- a provider requires MFA, browser login, or security confirmation
- the token request would expose token content to normal output
- any change would be needed to make the credential work

## Acceptance Proof
- A result note exists under `CONTROL/`.
- The note contains only provider/credential label, status code, pass/fail, and non-secret error category.
- No token or secret value is present in the result note.
- No provider, scheduler, runtime, business, price, Sheet, database, Amazon/security, purchase, receiving, or send-to-Amazon action occurred.

## Retest
- retest_command: inspect the result note and confirm no token or secret value is present.
