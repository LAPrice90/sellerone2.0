# O Inbound FBA Cost Allocation Proof v1

## Manager Authority
- task_id: MGR_O_INBOUND_FBA_COST_ALLOCATION_PROOF_V1
- job_ref: O-INBOUND-FBA-COST-PROOF
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: o_cycle_sub_manager_from_mot_o_refund_restock_confidence_fields
- luke_action_required: 0

## Plain-English Purpose
O currently blocks every restock row from clean buying because expected profit still has weak cost proof.

This job is to find and connect existing local inbound/FBA-send cost evidence so O can say which SKUs have real cost drag proof and which still need proof. It must use real local evidence only. It must not guess, smooth over, or silently treat missing cost as zero.

## Boundary
- allowed_scope: inspect existing local inbound/FBA-send cost evidence, build or adjust read-only O proof outputs, update O source/session/profit confidence labels, update O manager/MOT checks, add focused tests, and refresh the local O proof chain.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused O source/session/profit/MOT tests must pass, the local read-only O proof chain must refresh without external writes, inbound/FBA-send cost labels must be backed by real source rows, missing cost proof must stay labelled as missing, and O must keep clean-buy and real-PO readiness closed unless all required proof is safe.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action, needs source fact rewriting, needs local DB or Sheet alignment, or requires guessing inbound/FBA-send cost where no source proof exists.

## Source Evidence
- MOT check: `o_refund_restock_confidence_fields`
- Current MOT state: `warn`
- Current proof clue: O source view has 608 rows, but inbound/profit input confidence is still weak enough to keep all rows blocked from clean buy.
- Latest O proof clue: `session_action_safety_counts {'blocked_from_clean_buy': 608}`

## Allowed Files
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/O021_build_restock_profit_checks.py`
- `scripts/flows/O/O022_build_inbound_fba_cost_proof.py`
- `scripts/flows/O/O460_build_restock_session_view.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- focused O tests under `tests/`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/`

## Acceptance Checks
- Existing local inbound/FBA-send cost evidence is inspected and named in the proof notes.
- O only marks inbound/FBA-send cost as proved when a row has real SKU-level source evidence.
- Missing or weak inbound/FBA-send cost stays visible as `missing` or `weak`.
- No row becomes clean-buy or real-PO ready because of guessed or default cost values.
- O MOT retest keeps 0 fails and shows the inbound/profit warning truthfully.
- Render/browser proof changes no proof, draft, approval, PO-control, purchase, receiving, or send-to-Amazon event rows.

## Expected End State
O can separate real inbound/FBA-send cost proof from missing cost proof before expected restock profit is trusted.
