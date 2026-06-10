# SellerOne 2.1 Runtime Safety Rules

Created: 2026-06-08

## Purpose

This file keeps the detailed safety rules out of the short bootstrap while preserving the rules that protect SellerOne runtime.

## Protected Actions

Stop and ask Luke before:

- changing prices
- editing F061 or business queues
- writing Google Sheets
- aligning local DB facts with Sheets or Product DB
- deleting outputs
- restarting workers
- running a live worker cycle without an approved proof window
- changing scheduler ownership outside an approved proof packet
- publishing
- creating purchase commitments
- receiving stock
- sending anything to Amazon
- bypassing Amazon security
- disabling MFA
- storing OTPs
- exposing cookies, tokens, credentials, or secrets
- widening scope beyond the approved task

## Root-Cause Rule

Fix the earliest real cause in the pipeline.

Do not change downstream reports to make bad data look correct. If the root cause is unclear, stop and ask a clarifying question or open an investigation ticket.

## Proof Rule

A task is not proved by an edit.

Use this language:

- `code fix applied`
- `isolated verification passed`
- `live loop verification pending`
- `live loop verification confirmed`

Health or checklist outputs older than the code change are stale and must not be presented as confirmation.

## Queue Rule

Worker repair requires an approved packet unless Luke explicitly asks for a scoped one-off investigation.

The packet must name:

- allowed scope
- forbidden actions
- proof route
- rollback or recovery expectation
- stop condition

## MOT Rule

The MOT is the outside inspector.

It checks existing evidence:

- files exist
- file age
- row counts
- skipped steps
- locks
- heartbeats
- database tables
- manifest final state

Do not hand-edit MOT, health, queue, or proof outputs to make a status look better.

## A Rule

A is the source-fact refresh flow, not a normal Google Sheets updater.

A should refresh local proof files and local SQL-compatible facts for listings, catalog, inventory, fees, and daily intel.

Do not run A scripts ad hoc unless Luke explicitly asks or an approved proof packet requires it. Use latest evidence first.

## B Rule

Before running any B script manually:

- check B ownership and locks
- use maintenance handoff when B is active
- do not overlap B scripts with the B loop
- do not judge B COGS, order, or token truth halfway through a B cycle

Protected B repairs involving tokens, stock, orders, Sellerboard comparison, or local DB alignment need explicit approval.

## Flow-Owned Proof Rule

Each flow gates on its own scoped proof.

- A gates on A proof.
- B gates on B proof.
- E gates on E proof.
- H gates on H proof.
- F gates on F proof.
- O gates on O proof.

Global health is observability unless a flow explicitly declares it as its gate.

## Forced Proof Window Rule

If a safe forced proof window exists, prefer it over vague waiting.

A safe proof window means:

- natural flow boundary or approved isolation boundary
- no overlapping owner process
- terminal markers can be reached
- proof artifacts are read only after finalization

If no safe forced proof window exists, record the exact wait condition in a durable artifact.

## Monitoring Rule

For multi-phase work or live runtime proof, keep phase state in a durable plan or control artifact.

Do not leave deferred checks only in chat.

Default monitored validation:

- first check after 5 minutes
- second check after 10 minutes
- then every 15 minutes
- stop after 60 minutes unless the plan says otherwise

During passive monitoring, do not interrupt Luke for routine unchanged status. Interrupt only for completion, new or worse failure, contradiction, timeout, or required approval.

## F061 Login Rule

When F061 hits BBP or Amazon login-required evidence:

- do not open a separate standalone Chrome window as the fix
- keep affected rows pending for login backtrack or merge
- use the script-owned browser path
- preserve the BBP Chrome profile session
- classify Amazon security pages with redacted evidence
- stop for real manual challenge, captcha, authenticator-only, passkey/security-key, protected boundary, or missing approved code source

Do not bypass Amazon security, disable MFA, store OTPs, or expose cookies.

## Reliability Planning Rule

Planning can continue when scoped hard blockers are clear, even if soft warnings remain.

Hard blockers:

- active FAIL in the scoped flow gate
- required runtime not running
- duplicate owner or crash loop
- stale core outputs beyond allowed cadence
- unresolved ownership or finalization mismatch

Soft warnings:

- known non-blocking WARN
- stale wording contradicted by newer proof
- intermittent but visible and recoverable fault

Track soft warnings, but do not let them block unrelated planning.

## Storage Rule

Every new output family needs a storage class and cleanup rule.

Cleanup must follow `CONTROL/STORAGE_POLICY.md`:

- measure
- classify
- dry-run manifest
- protected exclusions
- recovery path
- approval before destructive action

## Completion Rule

Every completion must point to one concrete next move:

- no further action needed now
- wait until a named time or condition and check a named artifact
- continue with a named task
- needs user decision on a named choice
