# E B Money Dependency Clearance v1

## Manager Authority
- task_id: MGR_E_B_MONEY_DEPENDENCY_CLEARANCE_V1
- job_ref: E-B-MONEY-CLEARANCE
- flow: E
- task_type: dependency_gap
- priority: normal
- status: parked
- authority: luke_requested_build_list
- luke_action_required: 0

## Plain-English Purpose
Track the upstream B money proof that E needs before E ROI/restock can become clean business truth.

This is visible in E because it blocks E confidence, but the root data work belongs to B.

## Boundary
- allowed_scope: E-side dependency tracking, manager proof wording, E/O confidence handoff notes, and read-only MOT evidence.
- forbidden_actions: no B run; no B data correction; no token correction; no Sellerboard value promotion into live ROI; no E live run without approved proof window; no Google Sheets write; no price change; no queue edit; no local DB alignment; no output deletion; no worker restart; no scope widening.
- proof_required: E must keep ROI/restock warning-labelled until B money proof is API-backed enough for live ROI use.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: Remove or revise this dependency card if B proof becomes clean. Do not edit E/B outputs by hand.
- stop_condition: Stop if the work requires B repair or protected correction; create or use a B packet instead.

## Expected Build Output
- E card stays open while B money proof is `bridge_labelled_only`.
- E tells O that restock evidence is support-only until B money proof clears.

## Acceptance Proof
- E MOT shows the B money dependency warning while B proof is weak.
- When B proof becomes API-backed, E can downgrade or close this dependency through the manager board.

## Manager Proof Update - 2026-06-04T13:05Z
- status: parked
- E MOT now reads the current B067 refund/fee/shipping gap review before falling back to the older Sellerboard bridge summary.
- Current E proof now shows:
  - refund money: API-proved
  - commission: API-proved
  - FBA fee: API-proved
  - shipping income: API-proved
  - Sellerboard return-gap witness: bridge estimate only
  - shipping cost/chargeback: API-proved source evidence after the B068 refresh
  - live ROI safety: blocked
- This means E is no longer waiting on stale commission/FBA labels.
- E remains parked because the remaining B money gaps are real:
  - Sellerboard return gap needs API proof or an approved rule
  - downstream E/O confidence rows need to refresh from the improved B proof before live ROI can clear
  - bridge values must not feed live ROI or restocking
- Retest proof:
  - focused E/B MOT tests passed
  - full manager MOT test file passed
  - read-only B MOT returned 0 FAIL and 10 WARN
  - read-only E MOT returned 0 FAIL and 2 WARN
- Next clearing condition:
  - B067 has no bridge/not-yet-proven money rows
  - E `e_b_money_truth_dependency` clears to OK through the same read-only E MOT

## Manager Proof Update - 2026-06-04T13:52Z
- status: parked
- B067 now proves the Sellerboard return-gap order through the API-backed refund bridge.
- E now sees these B source fields as API-proved:
  - refund money
  - Sellerboard return-gap order
  - commission
  - FBA fee
  - shipping income
  - shipping fee/chargeback source
- E remains warning-labelled because `sku_performance_summary` still carries bridge-labelled money confidence rows from before this B proof cleanup.
- This is not a Luke decision unless Codex needs to run a live E/O refresh or use weak values in restocking.
- Next clearing condition:
  - a manager-approved E/O confidence refresh rebuilds downstream labels from the improved B source proof
  - E `e_b_money_truth_dependency` clears through read-only E MOT
