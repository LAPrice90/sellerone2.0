# Daily Manager Plan - 2026-06-02

Status check time: 2026-06-02 10:00 Europe/London

## Control Board

```text
Overall state: BLOCKED
Fails: 4
Warnings: 16
User/admin gate: 1
Approved Codex tasks: 4
Hourly manager MOT: running, last result 0, next run 11:00
```

Plain English:

Today is not an all-calm day. The business control desk is working, but H has real proof failures, and F has one protected Seller Central auth gate that needs Luke/code-forwarding before that specific proof can continue.

## Cycle Status

| Cycle | Status | What It Means Today |
|---|---|---|
| A | Calm | Daily source-fact proof is okay. No A work today unless a new A failure appears. |
| B | Warning | Refund/P&L/ROI proof is active work. Do not treat Sellerboard bridge values as final ROI. |
| E | Warning | E confidence is doing its job, but refund/ROI fields still depend on B money proof. |
| H | Failed/Parked | H has 4 proof failures and must stay in bounded repair only. No publish, price, scheduler, or live H action. |
| F | Mostly calm, one protected gate | BBP scanner recovery is okay/pending fresh proof, but Seller Central eligibility proof is blocked by disabled auto-login/code-forwarding. |
| O | Calm as manager state | O is still mid-build. Next work is expected-profit input model with refund drag and inbound cost. |

## Today's Priorities

### 1. Handle The F Protected Gate Only If Luke Is Available

What is blocked:

```text
f_seller_central_eligibility_auth_state
```

This is not the same as the BBP scanner login proof. This is Seller Central eligibility login/code-forwarding proof.

Current evidence:

- secret exists
- credentials are present
- auto-login is disabled
- code-forwarding proof is not complete
- latest proof says `auto_login_disabled`

Plan:

- Keep it parked unless Luke is ready to complete the login/code-forwarding step.
- Do not run F061, edit queues, restart scanner, or open a separate Chrome window from the manager.
- If Luke completes the protected step, retest F MOT only.

Success:

- F MOT changes `f_seller_central_eligibility_auth_state` from `decision_needed` to `ok`.

### 2. Work H Safe Manager Tasks

H is today's main Codex-owned repair lane.

Active approved H tasks:

- `MOT_H_H_BOUNDARY_FINALIZER_TRUTH`
- `MOT_H_H_LATEST_MANIFEST_STATE`
- `MOT_H_H_TERMINAL_PUBLISH_TRUTH`

Plan:

- Claim H tasks only from approved packets.
- Inspect proof and package/source-fix only inside the task boundary.
- Do not run H.
- Do not pause scheduler ownership.
- Do not publish.
- Do not touch prices.
- Do not edit queues.
- Do not delete outputs.

Success:

- H failure rows become either `proved`, `fixed_needs_retest`, or parked with a stricter repair package.

### 3. Continue B Refund/P&L/ROI Proof

B is not failing, but it is not clean enough for ROI/restocking.

Current B warning focus:

- refund/P&L/ROI proof
- Sellerboard bridge is still a witness, not final money truth
- fee detail API proof is incomplete
- live ROI is not safe from bridge values alone

Plan:

- Continue the refund/P&L/ROI worker lane.
- Prove API refunds link into P&L once, not twice.
- Build/refine SKU refund rate.
- Backdate proof first, before any historical output rewrite.
- Keep Sellerboard as outside witness only.

Success:

- B can show one refund from API row to P&L and ROI confidence.
- E/O can consume refund proof without treating weak data as final.

### 4. Continue O Expected-Profit Input Model

O is calm because it is correctly not making restock decisions yet.

Current O finding:

- refund drag is needed
- inbound/FBA-send/prep cost is needed
- combined `profit_input_confidence` is needed

Plan:

- Build expected-profit input model.
- Carry refund drag and inbound cost into O proof rows.
- Keep action-ready rows blocked until profit inputs are clean.

Success:

- O can explain expected restock profit using all required cost inputs.
- O still makes no business commitment automatically.

### 5. Keep E As Confidence Guard

E is warning because B money proof is not clean enough yet.

Plan:

- Do not force E to look clean.
- Let E keep warning until B refund/fee/ROI proof improves.
- Add/confirm E proof gap task only if it helps expose refund ROI confidence fields.

Success:

- E separates "possible restock signal" from "business-ready restock truth".

### 6. Keep A Quiet

A is calm.

Plan:

- No A work today unless the next MOT shows a new A failure.

## Today Loading Bar

```text
Manager day readiness: [##########----------] 50%
```

Why 50%:

- A/F/O are mostly calm.
- B/E are warning-labelled and useful.
- H has active failures.
- One F protected auth gate needs Luke if that proof is to continue.

## Interrupt Luke Only If

- Seller Central code-forwarding/login step is needed now.
- H repair needs a live H proof run, scheduler change, publish path, or price-write boundary.
- B refund proof shows current P&L is double-counting and needs a protected historical correction.
- O needs business judgement on restock decisions.

## Do Not Do Today Without Approval

- no price changes
- no queue edits
- no Google Sheets writes
- no publishing
- no local DB alignment
- no output deletion
- no H live run
- no F061 live run or restart
- no Sellerboard values as final ROI

