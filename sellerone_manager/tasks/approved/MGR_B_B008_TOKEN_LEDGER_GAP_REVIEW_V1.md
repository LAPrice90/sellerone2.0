# B B008 Token Ledger Gap Review v1

## Manager Authority
- task_id: MGR_B_B008_TOKEN_LEDGER_GAP_REVIEW_V1
- job_ref: B-B008-TOKEN-LEDGER-GAPS
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: b_cycle_sub_manager_packet
- priority: high
- luke_action_required: 0

## Plain English
B has 5 refund-token rows where the allocation names a token, but that token is not visible in the current token ledger. Codex can inspect this safely, but must not create substitute tokens.

## Allowed Work
- inspect B042 token-ledger-gap rows
- inspect token allocations and token ledger proof
- inspect previous approved repair manifests where the token ID starts with manager correction IDs
- classify each row as stale proof, missing ledger proof, protected correction needed, or not yet proven
- create a read-only proof summary
- rerun read-only B MOT

## Forbidden Work
- no B run or restart
- no token correction
- no replacement token creation
- no allocation or COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no live ROI/restocking use
- no Sellerboard-as-final truth

## Acceptance Proof
- The 5 token-ledger-gap rows are no longer vague.
- Each row has a clear manager label.
- Any real data correction becomes a protected Luke decision, not a silent fix.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before any token, allocation, COGS, order, Sheet, DB, output, price, queue, ROI, or restocking change.

