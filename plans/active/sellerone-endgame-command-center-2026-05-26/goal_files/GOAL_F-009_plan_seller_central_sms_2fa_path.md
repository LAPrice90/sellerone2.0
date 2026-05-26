# Goal F-009 - Plan Seller Central SMS 2FA Path For Scanner Login

Created: 2026-05-26
Status: not started
Priority: Next

## 1. Simple Version For Luke

Decide how the scanner should safely handle Amazon/Seller Central SMS login codes if automation needs a code on the PC.

This is not building the SMS system yet. It is choosing the safest plan first.

## 2. Why This Matters

The price-list scanner can get stuck when Amazon or BuyBotPro needs login attention.

If we build a messy SMS workaround, we could weaken account security or create another fragile login problem. The report says the safest first rule is to avoid Seller Central website automation where SP-API can do the job. If SMS is still needed, we need a controlled path with manual fallback.

## 3. Source Files To Inspect

- `C:\Users\Luke\Downloads\deep-research-report (21).md`
- `project_control/F_PRICE_LIST_SCANNER_LOGIN_MODE_DESIGN.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/F_PRICE_LIST_SCANNER_TODO.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/RESULT_CHECK_REGISTER.md`

## 4. Hard Boundaries

- Planning and decision only.
- Do not build an OTP broker in this goal.
- Do not configure iPhone Shortcuts in this goal.
- Do not configure Twilio, Vonage, Gammu, or a GSM modem in this goal.
- Do not change Amazon Seller Central settings in this goal.
- Do not store OTPs, passwords, tokens, or secrets in repo files.
- Do not bypass Amazon throttles, login controls, 2FA, CAPTCHA, or account protections.
- Prefer SP-API over Seller Central browser automation wherever SP-API can do the job.

## 5. Technical Job Breakdown

- [ ] Read the deep research report.
- [ ] Summarize the three realistic options:
  - iPhone Shortcuts relay
  - USB GSM modem with real SIM as backup method
  - Twilio/Vonage virtual number as backup method
- [ ] Check how this fits current F061/FPM login-mode rules.
- [ ] Decide whether the scanner actually needs automated SMS collection, or whether script-owned visible Login Mode is enough for now.
- [ ] If automated SMS is needed, recommend one path and one fallback.
- [ ] Define the security rules before any build:
  - short TTL
  - one-time claim
  - no message-body logs
  - manual iPhone fallback
  - no repo-stored secrets
- [ ] Add or update delayed result check `RC-F-009` if a pilot is planned.
- [ ] Write the final summary into section 10 of this file.

## 6. Completion Expectation

The goal is complete only when:

- [ ] The preferred SMS/2FA path is chosen or explicitly parked.
- [ ] The decision says whether SP-API can avoid the browser login path.
- [ ] The scanner login-mode impact is clear.
- [ ] Any pilot has a delayed result check.
- [ ] No credentials or OTPs are stored in the repo.

## 7. Test And Proof Required

This is a planning goal, so no live SMS or Amazon login test is required.

Proof must include:

- the report file inspected
- the selected option or parked reason
- security boundaries
- manual fallback path
- whether a delayed pilot check was created

## 8. Delayed Result Tracking Rule

If this goal creates a fix or decision that cannot be proven immediately, do not leave the follow-up only in chat.

Before finishing, add or update a delayed result check in:

- `plans/active/sellerone-endgame-command-center-2026-05-26/RESULT_CHECK_REGISTER.md`
- spreadsheet tab `Result Checks` in `SellerOne_Endgame_Task_Board.xlsx`
- `project_control/DUE_CHECK_REGISTER.csv` if there is a real due time or trigger

A delayed check must include:

- exact trigger or due time
- artifact to inspect
- success condition
- what to do if it fails

## 9. Required Reply Instruction

Do not leave the final answer only in chat.

Before finishing, edit this file and fill in section 10.

## 10. Goal Reply - To Be Filled In By Goal Pursue

Status:

Files changed:

Files inspected:

Evidence found:

Decision made:

Tests or proof:

Remaining blocker:

Recommended next goal:

