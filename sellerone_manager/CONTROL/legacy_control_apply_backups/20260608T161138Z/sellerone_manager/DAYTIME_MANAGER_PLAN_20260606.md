# SellerOne Daytime Manager Plan - 2026-06-06

Observed: 2026-06-06 morning manager refresh

## Goal For Today

Get the evidence clean enough to work on ordering without guessing.

This does not mean the system will auto-buy today. It means the manager should make every restock row show one of these states:
- trusted
- warning
- blocked
- needs Luke business judgement

## Current Board

- A: calm
- B: blocked
- E: warning only
- H: warning only
- F: scanner/login mostly working, one protected rescan issue parked
- O: restock UI/system proof not ready enough yet

## Today Priority Order

### 1. B order truth proof

Job refs:
- `B-ACTIVE-FAIL-GROUP`
- `B-FUTURE-MARKETPLACE-ORDER`
- `B-MANAGEMENT-READY-FOR`
- `B-ORDER-TRUTH-COMPLETION`

Manager job:
- Prove marketplace/order freshness properly.
- Repair B manager proof mapping where needed.
- Retest with B MOT.

Allowed:
- manager proof/code repair inside approved packets
- read-only evidence checks
- B MOT retest

Blocked:
- no live B run unless separately approved
- no B restart
- no order merge
- no token correction
- no Sheet write
- no local DB alignment
- no output deletion

Luke input:
- not needed unless a live B proof run or data correction becomes the only safe next step.

### 2. B token-cost trust

Job refs:
- `B-FALLBACK-PROOF-RECONCILE`
- `B-FALLBACK-DATA-CORRECTION`
- `H-TOKEN-FLOOR-SOURCE-GUARD`
- `O-TOKEN-COST-TRUST-GATE`

Manager job:
- Keep fallback token risk visible.
- Work proof and impact preview.
- Keep affected SKUs out of clean H/O trust until proven.

Allowed:
- read-only audit
- source-link proof
- impact preview

Blocked:
- no token correction
- no stock correction
- no Sheet write
- no local DB alignment
- no price change

Luke input:
- needed only if the preview recommends correcting historical token or stock data.

### 3. O restock readiness

Job refs:
- `O-ACTIVE-RESTOCK-FILES`
- `O-USER-WORKING-READINESS`

Manager job:
- Fix O proof-file mapping.
- Fix user-working readiness proof.
- Make the restock view usable as a review screen, not an auto-buyer.

Allowed:
- O proof mapping repair
- UI/readiness proof repair
- O MOT retest

Blocked:
- no purchase order creation
- no receiving
- no send-to-Amazon
- no H pause
- no market scan
- no Sheet write
- no price change
- no queue edit
- no local DB alignment
- no output deletion

Luke input:
- useful later for urgent SKUs, supplier MOQs, pack sizes, budget, and manual buy judgement.

### 4. F login resilience

Current evidence:
- BBP login state: ok
- Seller Central eligibility auth: ok
- F child scanner heartbeat: ok
- current manager mode: logged in / catching up
- auto-login config: enabled with email, password, and forwarded-code label set

Manager job:
- Keep checking login resilience.
- If Seller Central or BBP logs out, classify whether code/email handling worked or whether Luke needs to use the scanner-owned browser.
- Do not drift into generic scanner repair.

Allowed:
- read-only proof checks
- manager classification
- approved login-proof task refresh

Blocked:
- no F061 manual run
- no queue edit
- no scanner restart
- no separate browser workaround
- no Gmail fetch/download/delete unless packet explicitly allows it
- no Sheet write
- no price change
- no DB alignment
- no output deletion

Luke input:
- needed only if the scanner-owned browser needs a fresh code/login action that the email-code path cannot handle.

### 5. Parked protected decisions

Known protected cards:
- `B-B008-TOKEN-STATE-CONFLICT`
- `B-B009-RETURN-REUSE-APPLY`
- `F-RESCAN-PRIORITY-02`
- `B-FALLBACK-DATA-CORRECTION`

Manager job:
- Keep these visible but quiet.
- Do not keep interrupting Luke for the same parked choices.

Luke input:
- needed only when we intentionally choose to apply a correction, recover rows, or use weak proof for business decisions.

## Automation Setup For Today

Main manager:
- Refresh combined board.
- Refresh approved tasks.
- Keep Luke informed only on real changes.

B manager:
- Work B proof cards first.
- Retest with B MOT.
- Stop for live run, restart, data correction, token correction, Sheet write, DB alignment, output deletion, price, or queue changes.

O manager:
- Work O proof/readiness cards after B is classified.
- Keep purchase actions blocked.

F manager:
- Monitor login resilience and scanner ownership.
- Notify only if login is lost, code action is needed, or scanner proof materially worsens.

## Luke's Useful Inputs Today

These help ordering, but they are not needed for the managers to start proof repair:
- urgent SKUs to consider buying
- supplier MOQ
- pack/case size
- rough budget
- any supplier stock limits
- whether a weak-proof SKU can still be bought manually

## Acceptance For Starting Ordering Work

Ordering work can start when:
- B order proof is clear or warning-labelled with no hidden missing-order risk
- B token-cost risk is either trusted or blocked by SKU
- O restock proof files are fresh enough
- O user screen can show trusted/warning/blocked rows clearly
- protected corrections remain unapplied unless Luke approved them

## Next Manager Move

Start with `B-ACTIVE-FAIL-GROUP`, then the three B MOT proof cards. After B is classified, continue O readiness.
