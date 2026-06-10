# SellerOne Manager Progress Tracker

Last updated: 2026-06-06

## Overall Manager Takeover

```text
[#############-------] 67%
```

Plain English:

The manager is organised enough to track the main work without relying on chat memory. A new B token-cost issue is now the top trust problem for reordering and repricing: fallback stock tokens can carry old costs into current available stock. Today should put B fallback-token proof first, then keep H floors and O reordering blocked from clean trust for affected SKUs until B clears.

## Active Work Lanes

| Lane | Owner | Goal | Current Status | Progress |
|---|---|---|---|---|
| F scanner login recovery | F cycle | Let BBP/Seller Central recovery expose Dashboard Yes/No inside the scanner-owned browser | F login controller rewrite is now proved. F found a fresh Seller Central code, submitted it, proved Dashboard Yes/No as `YES`, and scanner continuation/backtrack promotion evidence exists. F has now continued into TD Synnex hidden scanning after login, so Weekend Hometime is monitoring durability rather than treating login as the active blocker. | 78% |
| B refunds, fees, shipping, ROI | B cycle | Tie returns and fees into P&L and ROI truth | B is warning-only again. Stock-receipt/token sync is now proved, but refund/token bridge, fallback-cost proof, marketplace coverage, and bridge-only ROI warnings still keep B from clean buying authority. Existing token correction remains protected and must not happen without preview and Luke approval. | 42% |
| O restocking proof | O cycle | Define exactly what data O needs before making restock decisions | O remains the reordering lane, but affected SKUs must stay out of clean action-ready status while B fallback-token cost risk is active. O-TOKEN-COST-TRUST-GATE is now added. | 48% |
| E confidence bridge | E cycle | Keep ROI/restock signals honest while B money proof is incomplete | E is manager-proved as a restock evidence layer: 10 clean completed E runs, 0 E MOT failures, and the remaining ROI/B-money gaps still warning-labelled instead of treated as buying authority. | 82% |
| H repricing safety | H cycle | Keep repricing controlled and safe while O uses market proof | H is calculating floors from B token evidence. For affected SKUs, H should not call the floor source clean while B fallback-token cost is unproved. H-TOKEN-FLOOR-SOURCE-GUARD is now added. | 62% |
| Main manager board | Main manager | Combine A/B/E/H/F/O into one calm control desk | Combined MOT and Manager Task Board exist. Current board: 21 active cards, 3 not started, 1 blocked, 17 parked. O restock proof is the main safe Codex lane; F is the protected user gate. | 80% |

## Simple Loading Bars

### F - Scanner Can Recover From BBP/Seller Central Login

```text
[################----] 78%
```

Done when:

- F061 detects BBP login page.
- It uses the scanner-owned browser, not a separate Chrome window.
- It fills email and password from local secrets.
- It clicks login.
- It continues scanning.
- Proof file shows `attempted_flag=1` and `succeeded_flag=1`.

Waiting on:

- next natural BBP login challenge.
- Seller Central eligibility login/code-forwarding if Luke wants that proof cleared.
- F source-intake proof repair for ABGee/Gmail evidence before source proof can be called clean.

Latest F result:

- 2026-06-06 weekend update: `F-LOGIN-CONTROLLER-REWRITE` is proved.
- New login controller files now write a redacted attempt log, latest state JSON, and a plain-English report.
- BBP login and Seller Central login now both report into one controller instead of three competing paths.
- FPM130 no longer lets an old UI/manual login request force visible/manual mode when auto-login evidence says the scanner-owned login path can continue.
- Isolated tests passed for controller proof rules, forwarded-code handling, and the login-mode regression.
- Live scanner evidence moved all the way through the target proof: F found a fresh Seller Central code, submitted it, then proved Dashboard Yes/No as `YES`.
- Scanner continuation evidence exists: auth was confirmed, a scanner chunk succeeded, pending moved from 5490 to 5489, and completed login backtrack evidence was promoted.
- F MOT now proves Seller Central eligibility; the remaining F failure is separate protected `F-RESCAN-PRIORITY`, not login.
- Weekend Hometime should keep watching F durability and scanner progress, but the login controller rewrite is no longer the active blocker.
- 2026-06-06 19:56 UK: F durability check stayed clean after login. F MOT now has 0 WARN and only the separate protected RESCAN fail. The scanner is active on TD Synnex in hidden mode, with recent chunks moving the pending count from 5446 to 5421.
- 2026-06-06 update: DHB is no longer treated as healthy just because the scanner process is alive.
- F MOT now fails `f_live_owner_status` as `running/supplier_progress_stalled`.
- Evidence: 5 recent DHB scanner chunks over 24.4 minutes, pending work moved from 5489 to 5490, and 5 recent memory-import blocks were visible.
- Board-visible manager job: `F-SCANNER-PROGRESS`.
- Approved worker repair package: `F-DHB-FORWARD-PROGRESS`.
- The controlled FPM130 owner reload proof moved forward after Luke's approval.
- `F-LOGIN-MODE` is proved again.
- BBP is being reached, the BBP iframe is found, and Dashboard Yes/No is now being read as `YES`.
- Latest manager worklist shows F login mode and F Seller Central eligibility are proved, but F owner progress is now failed until the DHB loop is fixed.
- Seller Central proof shows the code step was reached and the Dashboard Yes/No signal became visible afterward.
- Treat this login work as proved from the manager side. Do not confuse it with the separate protected F rescan-priority row.
- Auto-login is now set up in the normal scanner path and enabled in the local Seller Central login config. Durability proof is pending the next natural Seller Central logout/code challenge, tracked as `F_SELLER_CENTRAL_AUTO_LOGIN_NEXT_CHALLENGE_20260606`.
- The active F focus is now Seller Central/Yes-No proof: email-code handling if a code page appears, then Dashboard Yes/No extraction.
- The next interruption should only be a real login/code action through the scanner-owned browser, a Yes/No proof completion, a Yes/No extraction stall, or the two-hour progress email if the proof is still not complete.
- F source-intake proof is largely proved, but F still has protected rescan-priority recovery parked behind Luke choice.
- Current protected F gate is F-RESCAN-PRIORITY-02. F-SELLER-CENTRAL-ELIGIBILITY is now proved.
- F work must still avoid separate browsers, F061 runs, queue edits, worker restarts, Gmail fetch/download/delete, Sheets, prices, output deletion, and local DB alignment.

### B - Refunds And Fees Feed P&L/ROI

```text
[#########-----------] 46%
```

Done when:

- API refunds link to exact order and SKU.
- Refund units are counted.
- Refund percentage is calculated by SKU.
- Refund money is included in P&L once, not twice.
- Fees and shipping are labelled as API-proven or not yet proven.
- E/O can tell whether ROI is safe to trust.
- Historical/backdated refund proof is built before any historical business output rewrite.

Waiting on:

- worker proof that P&L is not double-counting refunds.
- refund-rate bridge and backdated proof.
- fee detail API allocation proof.
- shipping/API confidence proof.
- warning-labelled refund/token bridge cleanup.
- original returned-token live-status conflict proof or a separate protected correction packet.
- direct Amazon return coverage proof or explicit warning exception.

Latest B result:

- Latest B MOT has active FAIL rows again around marketplace/order-truth proof and management-readiness proof.
- B is still manager-watchable, but it is not clean enough to call order truth fully ready for morning restocking until these safe B packets are worked or clearly warning-labelled.
- New investigation found a token-cost source issue:
  - `A2-T2AC-TW3L` has 343 available 4.51 fallback tokens in front of 267 available 4.44 receipt tokens.
  - H is using 4.51 because it reads B's local token ledger.
  - Current B009 fallback logic copies latest local cost instead of proving a matching receipt cost.
  - Direct comparison to the Google Sheet `Tokens` tab found 0 direct Sheet batch tokens with wrong cost.
  - The real problem is fallback tokens: 1473 fallback tokens differ from the latest prior Sheet cost, including 1096 currently available and 377 already allocated.
  - Main affected SKUs are `6V-EEC1-2S9Z` with 753 available fallback tokens at 2.25 instead of 2.22, and `A2-T2AC-TW3L` with 720 fallback tokens at 4.51 instead of 4.44.
- The old disposition conflict packet is parked/proved history, not a current Luke blocker.
- The original returned-token protected apply packet is proved history, not a current Luke blocker.
- Current safe approved B tasks are B-ACTIVE-FAIL-GROUP, B-FUTURE-MARKETPLACE-ORDER, B-MANAGEMENT-READY-FOR, and B-ORDER-TRUTH-COMPLETION.
- New safe approved B tasks are B-FALLBACK-COST-AUDIT and B-FALLBACK-COST-SOURCE.
- Protected future decision card is B-FALLBACK-DATA-CORRECTION.
- Remaining B warning work is marketplace coverage, refund/token bridge cleanup, Sellerboard refund/fee/ROI bridge, stock-receipt/token sync, and order-truth confidence proof.
- 2026-06-06 update: B-STOCK-RECEIPT-TOKEN is now proved in the manager worklist. This removes one active B warning, but does not make B clean for buying because refund/token bridge, fallback-cost proof, marketplace coverage, and bridge-only ROI warnings remain.
- No further live token correction is approved in the current packet.
- Sellerboard remains outside comparison evidence only, not live ROI/restocking truth.

### O - Restocking Decision System

```text
[#########-----------] 47%
```

Done when:

- O knows exactly which data it needs from A, B, E, F, and H.
- O can explain why a product should or should not be restocked.
- O separates safe suggestions from blocked decisions.
- O does not make business commitments automatically.
- The UI shows the restock decision clearly.
- O expected profit includes refund drag.
- O expected profit includes inbound/FBA-send/prep cost.
- O carries one combined `profit_input_confidence` field.

Waiting on:

- Luke's urgent manual restock run to stay outside automation.
- B money proof.
- E confidence proof.
- H market/repricing safety where needed.
- O expected-profit input model build.

Latest O result:

- O manual restock support packets show proved in the manager approved-task list, but this does not mean O is ready to order automatically.
- Current approved O tasks are O-ACTIVE-RESTOCK-FILES and O-USER-WORKING-READINESS.
- Luke is handling urgent restocking manually, so O should not push ordering decisions today.
- O confirmed it should not trust expected restock profit yet.
- UI audit completed on 2026-06-03: the current Streamlit UI has useful parts, but it mixes restocking, Product DB, F scanner/admin, PO drafts, receiving, and send-to-Amazon into one cluttered app.
- UI next build order is operator shell, Today page, then manual restocking workspace.
- Refund evidence exists, but O refund drag is currently zero for all O rows.
- Inbound cost evidence exists, but it is not allocated to SKU-level restock decisions yet.
- O currently has 608 restock rows and 0 action-ready rows, which is safe.
- Next O fields: refund rate, refund drag per sold unit, refund confidence, inbound cost per unit, inbound confidence, and `profit_input_confidence`.

### E - Confidence And Signals

```text
[################----] 82%
```

Done when:

- E uses clean sales and ROI truth.
- E carries refund drag.
- E marks weak profit proof clearly.
- E only marks restock rows as business-ready when the money proof is clean.

Waiting on:

- remaining B money proof gaps to improve from warning to trusted.
- Wider ROI coverage if E needs to support more SKUs with clean profit proof.

Latest E result:

- E has 0 MOT failures and 2 warning-only confidence gaps.
- The last 10 completed E runs all completed their 8 E steps with 0 step failures.
- E proves sales velocity, ROI output, restock signals, performance summary, study output, cadence, and E-scoped health/profile proof from outside evidence.
- E still shows ROI coverage as weak: 41 of 161 SKUs have ROI proof, while 120 SKUs remain velocity-only.
- E now reads the newer B067 proof first: refund money, commission, FBA fee, and shipping income are API-proved.
- E still keeps `restock_business_ready` at 0 because Sellerboard return-gap evidence is bridge-only and shipping cost/chargeback is not yet proven.
- Optional E publishing remains `not_verified` and is not required for E evidence support.
- E board jobs are proved except `E-B-MONEY-CLEARANCE`, which is parked until the separate B manager clears the remaining B money proof gaps.

### H - Repricing And Market Safety

```text
[#############-------] 63%
```

Done when:

- H has current independent proof.
- Scheduler/publish/finalizer safety is clean.
- O can request market proof without unsafe H overlap.
- No price-writing path runs without proof.

Waiting on:

- warning-level H manager proof cleanup.
- ten-run reliability window to improve from warning-quality receipts to clean receipts.
- no live H run unless a separate approved proof window exists.

Latest H result:

- B06 defensive listing proof is complete: the latest post-fix receipt stood down with no defensive write when the rival was above us.
- Latest H MOT has 0 FAIL and 4 WARN.
- The H reliability window now has 10 warning-quality receipts, 0 failed receipts, and 0 clean receipts.
- The failed receipt is `H_20260604T101005Z`; newer H runs have completed after it, and the active H run should continue normally under scheduler ownership.
- H reliability remains warning-only until enough clean receipts exist. It must not trigger H runs, scheduler ownership changes, publish, price writes, queue edits, output deletion, or scope widening.
- H remains controlled: no publish, price write, scheduler ownership change, or live manager run without approved proof.

## What To Watch For

Interrupt Luke only if:

- a real business decision is needed
- a protected action is needed
- F rescan recovery needs approval before touching parked scanner rows
- O proof repair would require H pause, market scans, purchase actions, receiving, send-to-Amazon, Sheet writes, DB alignment, or output deletion
- B stock-receipt/token proof requires marker edits, live B runs, DB alignment, or stock correction
- a cycle needs approval for a live proof run
- a warning becomes a failure
- A cycle lock warning becomes stale or blocks the next A proof window

Do not interrupt Luke for:

- normal warnings already parked
- routine MOT refreshes
- worker tests passing
- technical notes that do not change a decision

## Next Manager Step

Continue safe approved O restock proof-file repair and O user-working readiness first, then B stock-receipt/token proof. Keep F rescan recovery parked until Luke approves preview-first recovery or leaves those rows parked. Keep weak money and restocking items warning-labelled, not business-ready.

## Manager Coordinator Automation

Active from 2026-06-02:

```text
SellerOne Manager Coordinator Pulse
```

Cadence:

```text
Every 2 hours
```

Purpose:

- refresh combined MOT
- refresh approved task packets
- refresh the manager front door
- update this tracker only when something materially changes
- report to Luke only for real decisions, new failures, worsened warnings, worker results, approved safe task starts, or major milestones

This is the missing coordination layer between the automated checks and Luke-facing management.
