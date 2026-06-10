# Plan Status

## Summary
- Plan slug: `f-new-product-review-fail-automation-v1`
- Current stage: upstream resolution code applied with structured reason themes, identity/profit pass routing, UI reason-code capture, F019 empty-window overwrite guard, and F032 review-intelligence Phase 1/2 outputs
- Current phase: F032 evidence and decision outputs are built and isolated-tested; blind validation seed run is not accepted yet; full live F019/F032 rebuild remains parked until FPM130 is not actively owning F files
- Current batch: Batch 001 expanded with submitted-issue fix tracking
- Overall status: active with May feedback included in F021 triage, structured feedback report rebuilt, F032 Phase 1/2 proof complete, and live scrape-dependent proof still pending
- Monitoring window: none active yet
- Next check UTC: after `out/systems/F/price_list_manager/live/live_cycle.lock` is absent or the FPM130 owner reaches a safe maintenance boundary
- Unlock condition: rerun F019 only when `f_live_price_file_launch_baseline_latest.csv` points at an active source window with matching `f_screening_row_state_live.csv` rows
- Timeout action: keep plan active until implementation begins or scope changes
- Notification mode: milestone only
- User interruption threshold: interrupt only if the weekend scanner stops, errors materially worsen, or approval is needed

## Checklist
- [x] Project brief written
- [x] Plan written
- [x] Coding plan written
- [x] Runbook written
- [x] Batch 001 ready
- [x] First review event received
- [x] Fix list opened
- [ ] Batch 001 complete
- [ ] Batch 002 ready
- [ ] Batch 002 complete
- [ ] Batch 003 ready
- [ ] Batch 003 complete
- [ ] Batch 004 ready
- [ ] Batch 004 complete
- [ ] Ready to archive

## Open blockers
- `feeder_review_events.csv` exists and has passed contract check with `21` rows.
- Current row-state has high pending volume (`32869`), so fail automation should focus first on completed timeout and pass surfaces.
- Any rescan apply step requires explicit approval and bounded queue scope.
- Current live scrape-evidence artifact predates new WebscraperS2 review-field propagation, so propagated parent or variant fields need next scoped F061 proof.
- Seller stock count is not stored in current review artifacts; any stock-count rule must remain Type 3 until evidence is captured.
- Profit code fix is implemented in Webscrape and F071, but full scraper-owned profit field refresh still requires next safe non-overlapping F061 scrape run.
- Seller dashboard YES/NO capture is implemented in Webscrape and F061 schema, but current live scrape evidence has blank `seller_history_dashboard_yes_or_no` until new scraper rows are written.
- F019 now reads `feeder_review_events.csv`; latest manual `fail` removes a clean Pass row before the UI sees it again.
- F021 now reads completed supplier handoff packs referenced by feedback events; May DHB and Entertainment Trading manual fails are no longer outside fail triage.
- Upstream resolution phase plan is written at `plans/active/f-new-product-review-fail-automation-v1/UPSTREAM_RESOLUTION_PHASE_PLAN.md`.
- Webscrape/F061/schema now support structured BBP seller-rank evidence fields, but current live scrape evidence predates this capture for most rows.
- Structured review reason-code capture is implemented in the O UI/F event contract, but existing feedback rows were created before the reason-code field, so current reason-code count is `0`.
- Default F019 live rebuild is blocked by a source-window mismatch: launch baseline points at `stocklist_supplier_rescrape_subset_20260421T103451Z`, while current row-state has no matching active rows.
- F019 now blocks this stale source-window case instead of overwriting review outputs with empty files.

## F032 Review Intelligence Status - 2026-05-20

Status:
- Phase 1 evidence pack: built and isolated-tested
- Phase 2 decision output: built and isolated-tested
- Phase 3 checklist output: built and isolated-tested
- Phase 6 rule-tightening suggestions: built and isolated-tested
- blind validation split: built
- latest three-run blind-agent scoring: improved, not accepted yet because the seed set is still too small

Output files:
- `out/analysis_reports/f032_review_intelligence_evidence_pack_latest.csv`
- `out/analysis_reports/f032_review_intelligence_decisions_latest.csv`
- `out/analysis_reports/f032_review_intelligence_fail_categories_latest.csv`
- `out/analysis_reports/f032_review_intelligence_checklist_latest.csv`
- `out/analysis_reports/f032_rule_tightening_suggestions_latest.csv`
- `out/analysis_reports/f032_review_intelligence_health_latest.csv`
- `out/analysis_reports/f032_review_intelligence_summary_latest.md`
- `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_inputs.csv`
- `plans/active/f-new-product-review-fail-automation-v1/f032_blind_validation_expected.csv`
- `out/analysis_reports/f032_blind_validation_results_latest.csv`
- `out/analysis_reports/f032_blind_validation_case_consistency_latest.csv`

Latest F032 output counts:
- evidence rows: `1603`
- decision rows: `1603`
- checklist rows: `1603`
- rule suggestion rows: `10`
- remove from clean Pass decisions: `1353`
- rescan needed decisions: `246`
- manual review decisions: `1`
- allow if other checks pass decisions: `3`
- F032 health FAIL rows: `0`
- F032 health WARN rows: `0`

Latest blind validation counts:
- blind input rows: `9`
- hidden answer rows: `9`
- leaked answer columns in blind input: `0`
- agent run files scored: `3`
- agent decision rows scored: `27`
- acceptable action agreement: `100.0%`
- exact action agreement: `96.3%`
- exact bucket agreement: `96.3%`
- action consistency: `88.89%`
- bucket consistency: `88.89%`
- fail-to-clear flip cases: `0`
- minimum seed set ready: `no`

Blind validation finding:
- The Plus-Plus `100 pc` storage-case inconsistency is fixed.
- The remaining consistency warning is TePe missing supplier-title evidence.
- One agent chose `rescan_needed`; the others chose `manual_review`.
- Both outcomes are blocked outcomes, so there were `0` fail-to-clear flips.
- Blind validation is still not accepted because the sample set is only `9` rows and the target is at least `20` clear-pass, `20` clear-fail, and `20` manual/ambiguous rows.

Tests passed:
- `python -m py_compile scripts\one_off\F032_build_review_intelligence_cycle.py tests\test_f032_build_review_intelligence_cycle.py` -> pass
- `pytest tests\test_f032_build_review_intelligence_cycle.py -q` -> `3 passed`
- `pytest tests\test_f031_build_title_match_agent_backlog.py tests\test_f019_build_live_price_file_near_miss_pack.py -q` -> `50 passed`
- `pytest tests\test_f021_build_new_product_review_fail_triage.py tests\test_f030_build_review_feedback_reason_theme_report.py -q` -> `20 passed`
- `pytest tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `17 passed, 53 deselected`
- `python -m py_compile scripts\one_off\F033_build_f032_blind_validation_pack.py tests\test_f033_build_f032_blind_validation_pack.py` -> pass
- `pytest tests\test_f033_build_f032_blind_validation_pack.py -q` -> `2 passed`
- `python -m py_compile scripts\one_off\F034_score_f032_blind_agent_runs.py tests\test_f034_score_f032_blind_agent_runs.py` -> pass
- `pytest tests\test_f034_score_f032_blind_agent_runs.py -q` -> `2 passed`
- `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f031_build_title_match_agent_backlog.py tests\test_f032_build_review_intelligence_cycle.py tests\test_f033_build_f032_blind_validation_pack.py tests\test_f034_score_f032_blind_agent_runs.py -q` -> `58 passed`
- `pytest tests\test_f021_build_new_product_review_fail_triage.py tests\test_f030_build_review_feedback_reason_theme_report.py -q` -> `20 passed`

Verification status:
- code fix applied
- isolated verification passed
- blind validation not yet accepted
- live loop verification not yet proven

Reason live loop is not yet proven:
- `out/systems/F/price_list_manager/live/live_cycle.lock` is active with owner `FPM130_live_cycle`.
- Codex must not overlap the F owner process.

## Latest proof snapshot
- Date: `2026-05-19`
- Evidence:
  - backup snapshot:
    - `out/backups/new_product_review_feedback_triage_20260519T121717Z`
    - `out/backups/all_upstream_phases_20260519T124628Z`
  - focused compile:
    - F019/F020/F030/O400 focused compile -> pass
  - focused pytest:
    - `pytest tests\test_f019_build_live_price_file_near_miss_pack.py -q` -> `45 passed`
    - `pytest tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f020_check_review_event_contract.py tests\test_f030_build_review_feedback_reason_theme_report.py -q` -> `48 passed`
    - `pytest tests\test_o_ui_operator_view.py -k "feeder_review" -q` -> `17 passed, 53 deselected`
    - `pytest tests\test_f021_build_new_product_review_fail_triage.py -q` -> `19 passed`
  - review event contract:
    - `status=pass`
    - `row_count=21`
    - duplicate event ids: `0`
    - invalid review decisions: `0`
    - invalid review reason codes: `0`
    - invalid event UTC rows: `0`
  - rebuilt fail triage (`out/analysis_reports/f_new_product_review_fail_triage_latest.csv`):
    - output rows: `2337`
    - pass input rows: `67`
    - near-miss input rows: `2306`
    - loaded handoff folders: `2`
    - handoff pass rows loaded: `64`
    - handoff near-miss rows loaded: `706`
    - `type_1_data_or_calc=956`
    - `type_2_known_policy_or_memory=27`
    - `type_3_missing_evidence_rescan_needed=1354`
    - `unclassified_rows=0`
  - manual feedback reconciliation:
    - total review feedback rows: `21`
    - manual fail feedback rows: `18`
    - manual fail rows matched in triage: `18`
    - manual pass feedback rows: `3`
    - manual pass rows absent from fail triage: `3`
    - matched fail reason: `review_memory_fail_decision`
  - current warning:
    - seller stock count is still not stored in triage sources, so stock-count-dependent checks remain Type 3 until capture exists.
  - feedback reason-theme report (`out/analysis_reports/f_review_feedback_reason_theme_latest.csv`):
    - feedback rows: `21`
    - manual fail rows: `18`
    - manual pass rows: `3`
    - unclassified manual fail rows: `0`
    - structured reason code rows: `0` because current feedback predates the new UI reason-code field
  - live F019 proof status:
    - stale-window guard proved:
      - F019 command result: `status=blocked_source_window_empty`
      - selected supplier/run: `stocklist_supplier` / `stocklist_supplier_rescrape_subset_20260421T103451Z`
      - row-state source rows: `142685`
      - matching supplier rows: `0`
      - matching source-window rows: `0`
      - no replacement snapshot files were written
    - latest review outputs remained preserved:
      - clean pass rows: `3`
      - near-miss rows: `1600`
    - full rebuild remains `parked pending F-owned proof window`
    - current blocker: `out/systems/F/price_list_manager/live/live_cycle.lock` is active with owner `FPM130_live_cycle`
    - next proof must first confirm active launch baseline and row-state rows match.

## Previous proof snapshot
- Date: `2026-04-29`
- Evidence:
  - review summary (`out/analysis_reports/f_live_price_file_review_summary_latest.csv`):
    - `pass_review_rows=13`
    - `near_miss_review_rows=1607`
    - `near_miss_evidence_gap_rows=1113`
    - `near_miss_commercial_rows=283`
    - `hard_reject_rows=25018`
    - `seller_history_routed_remove_from_clean_pass_rows=26`
    - `seller_history_routed_manual_review_rows=1`
  - fail triage (`out/analysis_reports/f_new_product_review_fail_triage_latest.csv`):
    - `type_1_data_or_calc=489`
    - `type_2_known_policy_or_memory=5`
    - `type_3_missing_evidence_rescan_needed=1113`
    - `unclassified_rows=0`
  - seller dashboard field population:
    - pass rows with `seller_history_dashboard_yes_or_no` populated: `0`
    - near-miss rows with `seller_history_dashboard_yes_or_no` populated: `0`
    - reason: current scrape evidence predates this new captured field
  - dashboard YES/NO rescan plan (`out/analysis_reports/f_dashboard_yes_no_rescan_plan_latest.csv`):
    - `output_rows=1337`
    - `selected_now=13`
    - `deferred_reviewable_near_miss=1191`
    - `deferred_non_reviewable_near_miss=133`
    - `selected_now_queue_match_rows=13`
    - selected rows source: clean Pass only
  - dashboard YES/NO clean Pass F061 proof:
    - selected clean Pass rows queued: `13`
    - F061 run status: `completed`
    - F061 rows done: `13`
    - F061 failed rows: `3`
    - scrape evidence rows written for dashboard run: `14`
    - `bbp_dashboard_yes_or_no` values populated: `0`
    - observed blocker: BBP dashboard element returned `LOGIN`, not `YES` or `NO`
  - rebuilt review outputs after rescan:
    - `pass_review_rows=3`
    - `near_miss_review_rows=1619`
    - `review_memory_routed_remove_from_clean_pass_rows=9`
    - F021 `type_1_data_or_calc=492`
    - F021 `type_2_known_policy_or_memory=10`
    - F021 `type_3_missing_evidence_rescan_needed=1117`
    - F021 `unclassified_rows=0`
  - manual fail-memory proof:
    - F020 contract status: `pass`
    - review event rows: `13`
    - `1167948 / B007SJSX3M`: absent from clean Pass
    - `1167948 / B007SJSX3M`: present in near miss as `review_memory_fail`
    - `1167948 / B007SJSX3M`: present in F021 as `type_2_known_policy_or_memory`
  - structured seller-rank proof:
    - focused compile command: passed
    - focused pytest command: `63 passed`
    - synthetic F019 test: rank-1 brand seller plus multi-seller history routes out as `brand_owner_top_seller`
    - live scraper proof: pending next scoped F061 scrape with BBP competition table visible
  - history borderline near-miss audit v1:
    - output: `out/analysis_reports/f_history_borderline_near_miss_audit_latest.csv`
    - summary: `out/analysis_reports/f_history_borderline_near_miss_summary_latest.md`
    - history conflict rows audited: `163`
    - `history_amazon_below_be_fail_supported=99`
    - `history_recent_weakness_fail_supported=26`
    - `history_recent_recovery_pass_candidate=19`
    - `borderline_but_limited_upside=10`
    - `history_fail_supported=9`
    - unclassified rows: `0`
    - focused pytest: `12 passed`
    - status: audit-only proof complete; F019 upstream routing not yet changed
  - profit conflict audit (`out/analysis_reports/f_profit_formula_conflict_audit_latest.csv`):
    - `rows=3322`
    - `profit_inflated_break_even_subtraction=238`
    - `profit_formula_review_needed=30`
    - `profit_missing_inputs_rescan_needed=3054`
    - `unclassified_rows=0`
  - row-state distribution (`out/systems/F/live/f_screening_row_state_live.csv`):
    - `pending=32869`
    - `timeout+OVER50K=3423`
    - `timeout+ROIFAIL=2207`
    - `timeout+SCRAPEFAIL=1856`
    - `timeout+NOASIN=1149`
    - `timeout+FAIL=784`
    - `timeout+RESCAN=170`
    - `timeout+NODATE=127`
    - `timeout+HAZMATFAIL=5`
  - targeted rescan reason distribution (`out/analysis_reports/f_targeted_rescrape_subset_latest.csv`):
    - `missing_core_price_history=2225`
    - `scrape_not_successful=2220`
    - `missing_bbp_demand_basis=2198`

## Notes
- This ticket is intentionally scoped to fail triage and rescan planning, not full launch release.
- Existing F owner scripts already support targeted subset rebuild and bounded rescans.
- The missing piece is one unified fail automation layer that the user can trust.
- Submitted issue fix tracking now lives in `FIX_LIST.md`.
- Demand range planning folder now lives in `demand-range-controls-bbp-demand-v1/`.
- History risk planning folder now lives in `history-risk-overrides-pass-v1/`.
- Weak UK review planning folder now lives in `weak-uk-variant-review-signal-v1/`.
- Profit correction planning folder now lives in `profit-calculation-correction-v1/`.

## Title Match Agent Status - 2026-05-20

Status:
- read-only checker built
- F019 routing wired
- seed calibration passed
- morning automation not switched on yet

Why this is required:
- barcode is the lookup route, not proof of a correct product match.
- the product identity check must compare the supplier price-file title with the Amazon title.
- ROI/profit must be treated as a warning light when the title match is suspicious.

Durable plan:
- `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_PLAN.md`

Seed sample collection:
- `plans/active/f-new-product-review-fail-automation-v1/TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv`

Seed rows currently pulled:
- `9`

Current sample coverage:
- accessory/consumable vs device
- same-brand wrong product
- completely wrong product
- pack/variant wording risk
- source presence or price-file mapping issue
- title/ownership guidance needed

Acceptance blocker:
- Fail Reason 1 cannot be marked accepted until the title-match decision is wired into upstream clean-Pass routing and proved with F019.

Latest checker proof:
- script: `scripts/one_off/F031_build_title_match_agent_backlog.py`
- focused pytest: `4 passed`
- backlog rows: `1603`
- decision rows: `1603`
- remove from clean Pass decisions: `7`
- manual review decisions: `259`
- allow if other checks pass decisions: `1337`
- seed calibration rows: `9`
- seed calibration mismatches: `0`
- missing Amazon title with ASIN rows: `0`

Fluval ROI finding:
- supplier cost: `3.05`
- estimated profit per unit: `123.72`
- estimated monthly profit: `5196.24`
- approximate profit-on-cost: `4056%`
- decision: suspicious title plus extreme ROI/profit should remove from clean Pass

F019 integration proof:
- shared helper: `scripts/flows/F/_title_match_agent.py`
- F019 now carries `supplier_title` and `amazon_title` separately
- F019 now routes `title_match_action=remove_from_clean_pass` out of clean Pass
- F019 now routes `title_match_action=manual_review` to reviewable near miss
- focused F019 pytest: `46 passed`
- downstream F021/F030 pytest: `20 passed`
- O review UI focused pytest: `17 passed, 53 deselected`

New cycle design:
- `plans/active/f-new-product-review-fail-automation-v1/F032_REVIEW_INTELLIGENCE_CYCLE.md`

Implementation and blind validation plan:
- `plans/active/f-new-product-review-fail-automation-v1/F032_IMPLEMENTATION_AND_BLIND_VALIDATION_PLAN.md`

Real pipeline integration design:
- `plans/active/f-new-product-review-fail-automation-v1/F032_REAL_PIPELINE_INTEGRATION_DESIGN.md`

Real pipeline integration implementation:
- F032 production-safe module added.
- FPM150 raw candidate handoff added.
- FPM155 AI review gate added.
- FPM130 trigger added.
- O400 raw handoff block added.
- F090 AI-gated manifest requirement added.
- review events can carry F032 decision fields.

Codex AI decision gate revision:
- FPM155 now creates an AI review queue and waits for Codex decisions.
- Codex decisions, not rule-only checks, are the final UI release gate.
- Automation guide: `plans/active/f-new-product-review-fail-automation-v1/F032_CODEX_AI_REVIEW_AUTOMATION.md`
- Daily Codex automation created: `f032-codex-ai-review-gate`
- Daily run time: `07:30` UK time

Fail-reason checklist integration:
- checklist source: `plans/active/f-new-product-review-fail-automation-v1/FAIL_REASON_REVIEW_CHECKLIST.md`
- execution/test plan: `plans/active/f-new-product-review-fail-automation-v1/F032_FAIL_REASON_CHECKLIST_EXECUTION_TEST_PLAN.md`
- the daily Codex automation prompt now requires the checklist to be applied before decisions are written
- isolated current New Product Review proof has run
- live F-flow proof has not yet been run

Superseded wrong-scope proof:
- proof root: `out/proof/f032_current_new_product_review_manual_review_test_20260520T135941Z`
- source clean Pass rows tested: `3`
- Codex decision rows written: `3`
- operator clean Pass rows after gate: `0`
- manual review rows after gate: `3`
- O400 loader clean Pass rows: `0`
- O400 loader manual review rows: `3`
- reason superseded: user clarified these were manually passed rows, not the intended unassessed New Product Review rows

Correct unassessed New Product Review proof:
- proof root: `out/proof/f032_unassessed_new_product_review_kuriboh_test_20260520T142028Z`
- source row: Bliss Distribution `KONKKS` / `B09HKZWBDN`
- supplier title: `Yu-Gi-Oh! - Kuriboh Kollection Sleeves 50 Pack`
- Amazon title: `Yu-Gi-Oh! Kuriboh Kollection Card Sleeves`
- approximate profit-on-cost: `65.61%`
- queue rows before Codex decision: `1`
- pending Codex decision rows before decision: `1`
- manifest before decision: not written
- operator ready flag before decision: `0`
- Codex action written: `manual_review`
- Codex category: `pack_size_or_quantity`
- manifest after decision `ai_gate_status`: `passed`
- manifest after decision `operator_ready_flag`: `1`
- operator clean Pass rows after gate: `0`
- manual review rows after gate: `1`
- O400 loader clean Pass rows: `0`
- O400 loader manual review rows: `1`

AI check note and Amazon page evidence update:
- status: code fix applied and isolated verification passed
- O400 now shows `AI check note` for Codex/F032 manual-review rows
- isolated Kuriboh helper text: `AI check: confirm the Amazon listing is for 50 units per pack.`
- F061/F019/F032 now have fields to capture and carry Amazon product description, feature bullets, and product detail text
- Amazon product description is captured from the Amazon page after the BBP/pre-review kill gate passes
- exact first-choice description XPath: `//*[@id="productDescription"]/p[1]/span`
- focused compile: pass
- focused tests: `3 passed`
- exact XPath selector proof: `2 passed`
- broader affected tests: `19 passed, 55 deselected` and `50 passed`
- controlled F061 proof scrape: passed
- Kuriboh controlled proof: stopped before browser scrape with `OVER50K`, proving failed rows do not get unnecessary Amazon description pulls
- successful controlled proof root: `out/proof/f061_amazon_description_xpath_datacollection_20260520T144608Z`
- successful proof row: DHB `PDL504` / `B001AI8AKI`
- successful proof evidence: `scrape_attempted=True`, `scrape_success=True`, `product_description=TePe Interdental Blue Brushes 0.6mm - Pack of 6`, chart daily rows `366`
- controlled FPM150/FPM155 handoff proof: completed
- full scheduled live F-flow handoff proof: not yet completed
- next verifier: full scheduled live F-flow handoff proof
- success condition: live F019/F032 queue rows carry populated scrape fields as `amazon_product_description` or `amazon_feature_bullets`, FPM155 gates release, O400 shows AI notes, and F090 ignores raw fallback rows
- remediation path: add another Amazon description/bullet selector if the fields remain blank on pages that visibly contain those sections

Latest isolated proof:
- F032/FPM150/FPM155/FPM130/O400/F090 focused proof: `22 passed`
- F019/F031/F032/F033/F034/FPM150/FPM155/F090 proof: `75 passed`
- O feeder-review UI proof: `18 passed, 53 deselected`
- FPM130 live-cycle unit proof: `63 passed`
- F090 listing intake proof: `12 passed`
- F032 wrapper run: `1603` decisions, `0` health FAIL, `0` health WARN
- F035 empty-root runtime proof: `candidate_manifest_count=0`

Remaining blocker before full automatic review intelligence:
- Live F-flow proof is not yet completed.
- The controlled isolated chain has now proven FPM150 raw output, FPM155 AI-gated output, O400 visibility, and F090 intake traceability.
- The remaining proof is the scheduled live F-flow handoff on real runtime data.

Before-execution checklist added:
- checklist location: `plans/active/f-new-product-review-fail-automation-v1/CODING_PLAN.md`
- section: `13) Before Execution Checklist - FPM150/FPM155 Amazon Page Evidence Handoff`
- status: executed and proof results recorded
- backup: `out/backups/f032_handoff_checklist_plan_20260520T145445Z`
- next allowed action: use the recorded checklist results as the baseline for the scheduled live F-flow handoff proof

Controlled FPM150/FPM155 Amazon page evidence handoff proof completed:
- proof root: `out/proof/fpm155_amazon_page_evidence_handoff_20260520T150009Z`
- seed source: `out/proof/f061_amazon_description_xpath_datacollection_20260520T144608Z`
- proof row: DHB `PDL504` / `B001AI8AKI`
- captured Amazon page evidence: `product_description=TePe Interdental Blue Brushes 0.6mm - Pack of 6`
- FPM150 raw pass rows: `0`
- FPM150 raw near-miss rows: `1`
- FPM155 pre-decision status: `pending_ai_decision`, operator ready flag `0`
- FPM155 final status after controlled Codex decision: `gated`, AI gate `passed`, operator ready flag `1`
- Codex action used: `manual_review`
- final clean-pass operator rows: `0`
- final manual-review rows: `1`
- O400 proof: visible manual-review row shows `AI check note`
- F090 proof: raw fallback trap rows `1`, listing intake rows `0`, listing hold rows `0`, health `ok`
- checklist result file: `plans/active/f-new-product-review-fail-automation-v1/CODING_PLAN.md`
- backup before final checklist update: `out/backups/f032_handoff_final_plan_update_20260520T150700Z/CODING_PLAN.md`

Remaining blocker before live automatic review intelligence sign-off:
- Full scheduled live F-flow handoff proof is still not completed.
- The controlled isolated chain is now proven from F061 evidence through FPM150, FPM155, O400, and F090.
- trigger: next full scheduled F price-list manager live cycle that completes a real supplier run and writes a live FPM150/FPM155 review handoff
- artifacts to inspect: `out/systems/F/price_list_manager/live/review_handoff_manifest.csv`, the matching handoff directory under `out/systems/F/price_list_manager/review_handoffs`, O400 New Product Review loader output, and `out/systems/F/health/amazon_listing_health.csv`
- success condition: live FPM155 `ai_gate_status=passed`, `operator_ready_flag=1`, queued rows carry Amazon page evidence where available, O400 shows only AI-gated rows with AI notes for manual-review rows, and F090 does not consume raw analysis-report pass rows
- remediation path if it fails: pause live release, keep rows out of O400, inspect whether the break is F061 evidence capture, FPM150 carry-forward, FPM155 Codex decision gating, O400 manifest selection, or F090 manifest selection, then fix the earliest broken stage

Passed-product Amazon page evidence backfill:
- status: queue builder implemented, isolated queue proof passed, forced F061 evidence proof passed, live F scanner restored
- plan section: `plans/active/f-new-product-review-fail-automation-v1/CODING_PLAN.md`, section `14) Passed Product Amazon Page Evidence Backfill`
- backup before plan update: `out/backups/f032_passed_product_page_evidence_backfill_plan_20260520T151500Z`
- current latest Pass rows: `3`
- current latest unique Pass ASINs: `3`
- historical pass-review files inspected: `30`
- historical pass rows found: `2298`
- unique historical pass identities found: `295`
- unique historical Pass ASINs found: `289`
- unique historical Pass ASINs missing the new page evidence: `289`
- implementation: `scripts/one_off/F036_build_passed_product_page_evidence_backfill_queue.py`
- tests: `tests/test_f036_build_passed_product_page_evidence_backfill_queue.py`
- focused proof: `3 passed`
- latest queue proof: queue rows `3`, F061-ready rows `3`, health FAIL `0`, health WARN `0`
- latest queue path: `out/analysis_reports/f_passed_product_page_evidence_backfill_queue_latest.csv`
- latest F061 staging path: `out/analysis_reports/f_passed_product_page_evidence_backfill_f061_active_run_latest.csv`
- historical sample proof: queue rows `10`, F061-ready rows `10`, health FAIL `0`, health WARN `0`
- historical sample queue path: `out/analysis_reports/f_passed_product_page_evidence_backfill_queue_historical_sample_latest.csv`
- isolated proof root staged: `out/proof/f036_passed_product_page_evidence_backfill_latest_queue_20260520T153000Z`
- staged proof rows: `3`
- forced maintenance proof: completed after user instruction to force the proof window
- direct process kill: blocked by Windows access control, then completed through F scanner maintenance drain
- first F061 proof result: `processed_rows=3`, `pass_rows=3`, `scrape_attempted_rows=3`, `scrape_success_rows=3`, `scrape_failed_rows=0`
- supplier-title carry-forward gap found and fixed in F061 evidence/state outputs
- changed files: `scripts/flows/F/_schemas.py`, `scripts/flows/F/F061_run_legacy_first_checks_local.py`, `tests/test_f061_run_legacy_first_checks_local.py`
- second proof root after correction: `out/proof/f036_passed_product_page_evidence_backfill_supplier_title_20260520T153522Z`
- second F061 proof result: `processed_rows=3`, `pass_rows=3`, `scrape_attempted_rows=3`, `scrape_success_rows=3`, `scrape_failed_rows=0`, `chart_daily_rows_captured=1098`
- proof evidence path: `out/proof/f036_passed_product_page_evidence_backfill_supplier_title_20260520T153522Z/out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- proof health path: `out/proof/f036_passed_product_page_evidence_backfill_supplier_title_20260520T153522Z/out/systems/F/live/feeder_legacy_sheet_health.csv`
- confirmed evidence rows: `B082NMTZC2`, `B084CTW7T8`, and `B09FQCWKPW` all carry supplier title plus Amazon page evidence
- verification: compile proof passed, focused F061/page-evidence tests `2 passed`, queue-builder tests `3 passed`, proof health all `ok`
- live F scanner restored: supervisor `ok`, manager PID `21680`, child PID `12776`, active supplier `td_synnex`, pending rows `51847`
- remaining work: wire the backfill queue into a controlled batch runner for the full historical `289` missing-evidence ASINs, still without changing old decisions

Controlled historical backfill runner:
- status: implemented and first forced batch executed
- backup before implementation: `out/backups/f037_historical_backfill_runner_plan_20260520T155114Z`
- scope: full historical passed-product page-evidence backlog
- boundary: prepare and track rows now; execute F061 only inside an isolated proof root and only when the live F scanner is drained or explicitly forced through maintenance
- success condition: durable state file records every queued ASIN and the runner can stage the next batch without touching Google Sheets or the product database
- runner script: `scripts/one_off/F037_run_passed_product_page_evidence_backfill_batch.py`
- tests: `tests/test_f037_run_passed_product_page_evidence_backfill_batch.py`
- full queue rows: `289`
- full queue health: FAIL `0`, WARN `0`
- first batch id: `f037_full_backfill_batch_001_20260520T155600Z`
- first batch result: `5` processed, `5` succeeded, `5` captured page evidence, `0` failed
- durable state: `out/systems/F/page_evidence_backfill/page_evidence_backfill_state.csv`
- durable results: `out/systems/F/page_evidence_backfill/page_evidence_backfill_results.csv`
- durable health: `out/systems/F/page_evidence_backfill/page_evidence_backfill_health.csv`
- state count after batch 001: `5` succeeded, `284` pending
- live-overlap safety proof: execute without force returned `blocked_live_f_active`
- live scanner restored after forced batch: supervisor `ok`, manager PID `25036`, child PID `10156`, active supplier `td_synnex`
- verification: compile proof passed and focused tests `9 passed, 57 deselected`
- remaining work: continue controlled batches, then plan a separate tested merge phase before any live scrape-evidence merge

Continuous execution update - 2026-05-20T17:45:43Z:
- status: running under controlled maintenance/backfill ownership
- heartbeat batch: `f037_full_backfill_auto_0034_20260520T174543Z`
- state file: `out/systems/F/page_evidence_backfill/page_evidence_backfill_state.csv`
- results file: `out/systems/F/page_evidence_backfill/page_evidence_backfill_results.csv`
- health file: `out/systems/F/page_evidence_backfill/page_evidence_backfill_health.csv`
- manifest file: `out/systems/F/page_evidence_backfill/page_evidence_backfill_batch_manifest.csv`
- current counts: `33` captured/succeeded, `52` current-scanner rejects, `204` pending, `0` failed, `0` staged
- health status: all current page-evidence backfill checks `ok`
- fixes added during execution:
  - current scanner hard rejects are recorded as `skipped_current_scanner_fail`
  - `NOASIN` rows from screening state are handled without retrying scraper work
  - current barcode-resolved ASIN changes are matched by backfill row id and stored in `resolved_asin`
- current focused proof: `7 passed` for `tests/test_f037_run_passed_product_page_evidence_backfill_batch.py`
- next action: keep the runner active until pending is `0`, or pause only if a new failure pattern appears that is not a current scanner reject, `NOASIN`, or resolved-ASIN change

Progress update - 2026-05-20T17:53:39Z:
- heartbeat batch: `f037_full_backfill_auto_0038_20260520T175339Z`
- current counts: `37` captured/succeeded, `58` current-scanner rejects, `194` pending, `0` failed, `0` staged
- latest completed batch: `f037_full_backfill_auto_0034_20260520T174543Z`
- latest completed batch result: `10` processed, `4` captured, `6` current-scanner rejects, `0` failed
- health status: all current page-evidence backfill checks `ok`

Unattended runner/watchdog update - 2026-05-20T18:19:10Z:
- user concern: avoid spending chat tokens just to keep the same backfill loop running
- unattended runner already active: `out/systems/F/page_evidence_backfill/run_backfill_until_complete.ps1`
- watchdog added: `out/systems/F/page_evidence_backfill/watch_backfill_completion.ps1`
- watchdog PID at setup: `25452`
- active runner PID at setup: `17728`
- watchdog poll cadence: `60` seconds
- watchdog behavior:
  - if pending reaches `0` with `0` failed and `0` staged, it clears maintenance markers and writes `out/systems/F/page_evidence_backfill/watch_backfill_completion_final.json`
  - if the runner exits unexpectedly while rows remain pending and no failed/staged rows exist, it restarts the runner
  - if a real failed row or orphaned staged row appears, it writes `out/systems/F/page_evidence_backfill/watch_backfill_completion.blocked` and leaves maintenance active for diagnosis
- current setup proof: watchdog process is running and did not block on normal in-progress staged rows

Five-minute monitoring proof - 2026-05-20T18:23:08Z to 2026-05-20T18:28:10Z:
- runner stayed alive: PID `17728`
- watchdog stayed alive: PID `25452`
- no blocked marker was present at the end of the watch
- completed during watch: `f037_full_backfill_auto_0051_20260520T181933Z`
- completed batch result: `10` processed, `4` captured, `6` current-scanner rejects, `0` failed
- next batch started: `f037_full_backfill_auto_0055_20260520T182745Z`
- end-of-watch state: `54` captured/succeeded, `81` current-scanner rejects, `144` pending, `0` failed, `10` staged in the active batch
- next unattended check artifact: `out/systems/F/page_evidence_backfill/watch_backfill_completion_final.json`
- success condition: final JSON exists with `status=complete`, `pending=0`, `failed=0`, and normal F scanner maintenance markers cleared
- remediation if it fails: inspect `out/systems/F/page_evidence_backfill/watch_backfill_completion.blocked`, keep maintenance active, and diagnose the latest proof root named in the runner heartbeat

Progress update - 2026-05-20T18:58:16Z:
- runner PID: `17728`
- watchdog PID: `25452`
- active batch: `f037_full_backfill_auto_0058_20260520T185300Z`
- current state: `57` captured/succeeded, `108` current-scanner rejects, `114` pending, `0` failed, `10` staged in the active batch
- latest completed batch: `f037_full_backfill_auto_0057_20260520T184551Z`
- latest completed batch result: `10` processed, `1` captured, `9` current-scanner rejects, `0` failed
- watchdog status: polling every `60` seconds, no final or blocked marker
- next unattended check artifact: `out/systems/F/page_evidence_backfill/watch_backfill_completion_final.json`

Progress update - 2026-05-20T20:17:28Z:
- runner PID: `17728`
- watchdog PID: `25452`
- active batch: `f037_full_backfill_auto_0079_20260520T201350Z`
- current state: `78` captured/succeeded, `177` current-scanner rejects, `24` pending, `0` failed, `10` staged in the active batch
- latest completed batch: `f037_full_backfill_auto_0074_20260520T200519Z`
- latest completed batch result: `10` processed, `5` captured, `5` current-scanner rejects, `0` failed
- watchdog status: polling every `60` seconds, no final or blocked marker
- maintenance markers are still active because the backfill is still running
- next unattended check artifact: `out/systems/F/page_evidence_backfill/watch_backfill_completion_final.json`

Rejected reason snapshot - 2026-05-20T20:17:28Z:
- rejected rows counted from `out/systems/F/page_evidence_backfill/page_evidence_backfill_results.csv`: `177`
- `LOWROI`: `76`
- `LOW_SALES_CAPITAL_IDLE_RISK`: `66`
- `DASHBOARD_NO_LOW_SELLER_COUNT`: `20`
- scraper/API timeout while checking current scanner state: `10`
- `OVER50K`: `4`
- `NOASIN`: `1`
- note: these are current scanner reject reasons for old historical passes, not AI title-match decisions

NOASIN correction - 2026-05-20T20:24:46Z:
- user challenge accepted: `NOASIN` may be a lookup/reconciliation error because the old pass row already had an ASIN
- code correction: `NOASIN` is no longer counted as a normal current-scanner reject
- new status: `needs_asin_recheck`
- reclassified existing row: `1`
- example row: Davidoff Cool Water Woman 30 ml, old ASIN `B000C1UDWW`, barcode `3414202011820`
- backup: `out/backups/f037_reclassify_noasin_to_recheck_20260520T202445Z`
- focused proof after correction: `pytest tests\test_f037_run_passed_product_page_evidence_backfill_batch.py -q` -> `7 passed`
- meaning: this row should be reviewed/retried for ASIN lookup later, not treated as a bad product reject

NOASIN recheck limit - 2026-05-20:
- policy: do not bulk-recheck every missing ASIN
- reason: broad missing-ASIN rechecks would be slow and would waste scanner time
- allowed exception: only old historical pass rows that already had a prior ASIN may be flagged as `needs_asin_recheck`
- current exception count: `1`
- operational meaning: keep it as a small audit list for later spot-check, not an automatic backlog scan
- if this bucket grows materially, first fix the barcode-to-ASIN source/mapping rule before attempting any bulk retry

Normal-scan ASIN retry policy - 2026-05-20:
- user clarification: the main concern is normal live scans/rescans, not the one-off historical catch-up
- policy for normal scans: do not create a broad missing-ASIN rescan loop
- reason: normal scanner throughput would be damaged if every missing ASIN kept getting retried
- normal behavior should be: missing ASIN is parked or failed early with a clear reason, unless it meets a narrow exception rule
- narrow exception examples:
  - the same supplier SKU or barcode had a previously known ASIN
  - a scanner step changed the ASIN unexpectedly from a prior known value
  - the product was already in a high-value manual-review/pass context and the missing ASIN blocks evidence capture
- implementation note: if this is added to live scanning later, it should be a tiny exception queue with a daily cap, not a general retry backlog
