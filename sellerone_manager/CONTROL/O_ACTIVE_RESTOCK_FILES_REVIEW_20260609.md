# O Active Restock Files Review

job_ref: O-ACTIVE-RESTOCK-FILES
created_uk: 2026-06-09
owner: O restocking evidence Worker
output_type: planning and evidence review only

## Plain-English Result

Blocked with exact reason.

The active O restock file set is partly ready for planning use, but it is not fully safe as a clean proof base yet. Think of it like a planning folder where 7 current worksheets are up to date, but 2 old reference sheets are still from an older shop visit, so the folder is useful for triage but not strong enough to sign off as fully current.

## Boundary Followed

This review was read-only except for writing this dated control note.

No protected business action was taken:

- no orders placed
- no purchase commitments
- no receiving stock
- no send-to-Amazon action
- no supplier email or supplier commitment
- no price change
- no Google Sheets write
- no queue edit
- no Product DB or local DB alignment
- no supplier file move, delete, rewrite, import, download, or fetch
- no Gmail fetch or attachment download
- no F061 run or F source-status rewrite
- no O runtime or live worker cycle
- no output deletion
- no Task Scheduler change
- no Amazon or security action

## Evidence Checked

Control and queue files:

- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`
- `CONTROL/QUEUE_CONTRACT.md`
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md`
- `CONTROL/O_RESTOCKING_DEADLINE_PLAN_20260609.md`
- `CONTROL/O_RESTOCKING_DEADLINE_READINESS_REVIEW_20260609.md`
- `CONTROL/O_USER_WORKING_READINESS_REVIEW_20260609.md`
- `tasks/approved/MOT_O_O_ACTIVE_RESTOCK_PROOF_FILES.md`
- `tasks/approved/MOT_O_O_USER_WORKING_READINESS.md`

Current MOT evidence:

- `..\out\systems\M\mot\mot_latest.md`
- `..\out\systems\M\mot\mot_latest.csv`

Active O proof files named by the packet:

- `..\out\systems\O\live\restock_source_view.csv`
- `..\out\systems\O\live\restock_recommendations_live.csv`
- `..\out\systems\O\live\restock_review_queue.csv`
- `..\out\systems\O\live\reorder_input_coverage_report.csv`
- `..\out\systems\O\live\legacy_purchase_list_bridge.csv`
- `..\out\systems\O\live\legacy_purchase_list_bridge_health.csv`
- `..\out\systems\O\live\restock_profit_checks_live.csv`
- `..\out\systems\O\live\restock_profit_check_health.csv`
- `..\out\systems\O\live\restock_market_refresh_candidates_live.csv`

Planning-facing O review files also checked:

- `..\out\systems\O\live\reorder_input_readiness_summary.md`
- `..\out\systems\O\live\restock_session_review_live.csv`
- `..\out\systems\O\live\restock_session_supplier_summary_live.csv`
- `..\out\systems\O\live\restock_token_cost_trust_gate_live.csv`
- `..\out\systems\O\live\restock_profit_input_blocker_breakdown_live.csv`

## Exact MOT Finding

Latest O MOT observed UTC: `2026-06-09T15:00:33Z`

`o_active_restock_proof_files` is still `fail` with:

- `missing=0`
- `short=0`
- `unreadable=0`
- `stale_warn=0`
- `stale_fail=2`

The MOT row names the exact stale-fail files:

- `legacy_purchase_list_bridge.csv`
- `legacy_purchase_list_bridge_health.csv`

Everything else in the packet proof-file list exists and has current-enough row output for planning review.

## File-By-File Readiness

Fresh enough to use for planning review:

- `restock_source_view.csv` - 608 rows - last written `2026-06-05 13:46:32 UTC`
- `restock_recommendations_live.csv` - 608 rows - last written `2026-06-05 13:46:34 UTC`
- `reorder_input_coverage_report.csv` - 608 rows - last written `2026-06-05 13:46:38 UTC`
- `restock_profit_checks_live.csv` - 608 rows - last written `2026-06-05 13:46:44 UTC`
- `restock_market_refresh_candidates_live.csv` - 59 rows - last written `2026-06-05 13:46:44 UTC`
- `restock_profit_check_health.csv` - 270 rows - last written `2026-06-05 13:46:44 UTC`
- `restock_review_queue.csv` - 608 rows - last written `2026-06-04 12:09:03 UTC`

Present but stale-fail for the packet proof map:

- `legacy_purchase_list_bridge.csv` - 72 rows - last written `2026-05-22 09:43:38 UTC`
- `legacy_purchase_list_bridge_health.csv` - 10 rows - last written `2026-05-22 09:43:38 UTC`

Plain-English meaning:

- the current native O planning outputs are there
- the old legacy bridge pair is too old to treat as current proof
- because O still reads that bridge in several build steps, the MOT correctly keeps the proof map blocked instead of pretending the whole lane is fresh

## What These Files Contain

Useful current planning files:

- `reorder_input_readiness_summary.md` says 608 rows were considered, 0 are actionable now, and 608 are blocked now
- `restock_recommendations_live.csv` is the current row list of restock recommendations and purchase-price safety states
- `restock_session_review_live.csv` is the richer session review layer for row status, blocker reasons, and clean-buy safety state
- `restock_session_supplier_summary_live.csv` is the supplier roll-up for blocked row clusters
- `reorder_input_coverage_report.csv` is the row-level readiness and blocker map
- `restock_profit_checks_live.csv` is the profit and pricing proof layer
- `restock_market_refresh_candidates_live.csv` is the market-proof worklist
- `restock_token_cost_trust_gate_live.csv` is the token-cost confidence gate
- `restock_profit_input_blocker_breakdown_live.csv` is the small breakdown of nearest rows with minimum inputs

What the stale legacy pair contains:

- `legacy_purchase_list_bridge.csv` is an old local bridge export from the Purchase List sheet lane
- `legacy_purchase_list_bridge_health.csv` is the small health summary for that same bridge export

Why that matters:

- those 2 files are not the main planning dashboard anymore
- but they still feed O bridge-aware logic and are still named inside the approved packet proof map
- that makes them unsafe to treat as current evidence without a bounded refresh or a proof-map change

## Safe For Planning Use Right Now

YES, with limits.

These files are safe to use right now for:

- blocker mapping
- supplier clustering
- identifying nearest candidates
- building a read-only proposal
- explaining why no row is ready

They are not safe to use right now for:

- treating the O proof-file packet as cleared
- treating legacy bridge hints as current buying truth
- promoting any row into actual order action

## Empirical Planning Signals

Current live O files still agree on the planning picture:

- 608 rows in `restock_recommendations_live.csv`
- 608 rows in `restock_session_review_live.csv`
- 608 rows in `reorder_input_coverage_report.csv`
- 608 rows in `restock_profit_checks_live.csv`
- 59 rows in `restock_market_refresh_candidates_live.csv`
- 7 rows in `restock_profit_input_blocker_breakdown_live.csv`

Current decision state still says:

- `rows_actionable_now = 0`
- all 608 session-review rows are blocked from clean buy
- the biggest recommendation blocks are `missing_net_fee_model` and `missing_expected_cost`

Largest supplier groups in the current supplier summary include:

- `Stax` - 76 rows
- `Bliss Distribution` - 59 rows
- `CLF` - 46 rows
- `ABGee` - 36 rows
- `TD Synnex` - 36 rows
- `Heo` - 30 rows
- `DHB` - 30 rows

## Exact Blocker Reason

The active restock files are blocked as a proof set because the packet still depends on 2 stale legacy bridge files from `2026-05-22`, while the rest of the current planning outputs are from `2026-06-04` and `2026-06-05`.

That means Operations and Rep can safely read the current native O planning files, but should not describe `O-ACTIVE-RESTOCK-FILES` as cleared until either:

- the stale legacy bridge pair is refreshed inside an approved safe proof path, or
- the proof map is intentionally narrowed by a bounded repair packet and then retested by MOT

## Recommended Next Safe O Packet

Route next:

`O-ACTIVE-RESTOCK-FILES`

Reason:

- it directly targets the exact stale-fail pair
- it stays inside the already approved read-only proof-mapping boundary
- it should make the planning file set trustworthy before any Luke-facing proposal leans on it as current evidence

After that, route:

`O-USER-WORKING-READINESS`

Reason:

- the proof-file map and the user-readiness gate are the two live O blockers in the latest MOT
- clearing both gives Operations the cleanest base for a planning-only supplier proposal lane

## Final Classification

Status: ready for planning review, blocked as a fully current proof set.

Exact reason:

- 7 of the 9 packet-named active restock proof files are present and current enough for planning use
- 2 of the 9 packet-named files are stale-fail legacy bridge files from `2026-05-22`
- the row-level planning outputs still show 0 actionable rows, so no buying decision should be taken from this evidence today

Rollback note:

- no existing evidence file was rewritten
- this review was added as a new dated control note, so previous evidence stays preserved

Completion recommendation:

- continue with `O-ACTIVE-RESTOCK-FILES`
