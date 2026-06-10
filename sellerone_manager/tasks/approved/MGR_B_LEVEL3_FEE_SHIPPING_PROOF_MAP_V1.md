# B Level 3 Fee Shipping Proof Map v1

## Manager Authority
- task_id: MGR_B_LEVEL3_FEE_SHIPPING_PROOF_MAP_V1
- job_ref: B-LEVEL3-FEE-MAP
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: normal
- luke_action_required: 0

## Plain English
The next safe job is to prove whether B's existing Level 3 financial-event outputs already contain enough API-backed proof for commission, FBA fee, shipping income, shipping fee/chargeback, and refund fee reversals.

## Allowed Work
- build a read-only proof map from existing local Level 3 financial-event outputs
- inspect only current local files such as `financial_events_level3_raw`, `financial_events_level3_summary`, `financial_events_level3_official`, `financial_events_refunds`, `order_master`, B067, E performance, and O restock source
- label each money field as `api_source_available`, `api_source_missing`, `repo_path_unclear`, or `protected_live_pull_required`
- add a B MOT row and focused tests for the proof map if code is changed
- keep Sellerboard as comparison only

## Forbidden Work
- no B run or restart
- no live Amazon API pull
- no refund, fee, shipping, ROI, restocking, order, token, allocation, or COGS data correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no Sellerboard values as final live ROI/restocking truth
- no scope widening into E/O live decisions

## Acceptance Proof
- The proof map exists and has stable columns.
- Commission, FBA fee, shipping income, shipping fee/chargeback, and refund fee reversals have source row counts and required-key checks.
- The proof map explains why `fee_detail_ledger_api` being empty is not enough to prove order-level fee failure.
- Any remaining unclear field stays warning-labelled and blocked from live ROI/restocking.
- B MOT retest keeps B067 warning visible until fee/shipping API proof is connected safely.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before live Amazon API pulling, writing fee/shipping facts into business outputs, using fee/shipping proof in ROI/restocking, writing Sheets, aligning local DB facts, deleting outputs, running/restarting B, or widening beyond the Level 3 fee/shipping proof map.
