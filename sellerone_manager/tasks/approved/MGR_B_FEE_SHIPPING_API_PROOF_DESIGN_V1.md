# B Fee Shipping API Proof Design v1

## Manager Authority
- task_id: MGR_B_FEE_SHIPPING_API_PROOF_DESIGN_V1
- job_ref: B-FEE-SHIPPING-API
- flow: B
- task_type: manager_read_only_proof_design
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: normal
- luke_action_required: 0

## Plain English
B067 proved the labels, but the actual fee and shipping API proof is still incomplete. This job designs the next safe proof step so commission, FBA fee, shipping income, and shipping fee can be API-proved before E ROI or O restocking trusts them.

## Allowed Work
- inspect current local B financial proof files, fee detail files, Sellerboard bridge output, E confidence output, and O restock source output
- inspect existing repo code for Amazon financial events, settlement reports, transaction ledgers, and fee/shipping import paths
- identify the safest API-backed source for commission, FBA fee, shipping income, shipping fee, and refund fee reversals
- write a read-only manager plan/proof map showing source, required columns, matching key, expected output, MOT check, and retest rule
- create bounded follow-up worker packets if the proof map shows a safe non-protected implementation path

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
- The manager can say exactly which local/API source should prove each money field.
- The plan labels every field as `api_source_available`, `api_source_missing`, `repo_path_unclear`, or `protected_live_pull_required`.
- The plan includes the matching key for order ID, order item ID, SKU, marketplace, posted date, amount type, and currency where applicable.
- Any live API pull, DB merge, ROI use, or restock use is explicitly stopped for Luke approval.
- B MOT still keeps B067 warning visible until the actual API proof exists.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before live Amazon API pulling, writing fee/shipping facts into business outputs, using fee/shipping proof in ROI/restocking, writing Sheets, aligning local DB facts, deleting outputs, running/restarting B, or widening beyond B fee/shipping proof design.
