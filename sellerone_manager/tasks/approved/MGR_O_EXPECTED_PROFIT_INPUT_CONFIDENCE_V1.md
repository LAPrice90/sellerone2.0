# O Expected Profit Input Confidence v1

## Manager Authority
- task_id: MGR_O_EXPECTED_PROFIT_INPUT_CONFIDENCE_V1
- job_ref: O-EXPECTED-PROFIT-INPUT
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: o_cycle_sub_manager_from_mot_o_refund_restock_confidence_fields
- luke_action_required: 0

## Plain-English Purpose
Make O show whether expected restock profit is trustworthy before a row can move toward approval or buying.

O already has useful supplier, price, Max-pay, and PO-preview guardrails. This task adds the missing refund, inbound/FBA-send cost, and combined profit-input confidence proof so missing cost drag is labelled as unknown instead of silently becoming zero.

## Boundary
- allowed_scope: O expected-profit confidence fields, refund/inbound input labels, read-only local O builders, O manager/MOT proof, focused tests, Restock Session display, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused O source/session/UI/MOT tests must pass, the local read-only O proof chain must refresh without external writes, Restock Session must label refund/inbound/profit confidence clearly, O MOT must show `o_refund_restock_confidence_fields` no longer waiting, and O must keep real-PO readiness closed unless all required proof is safe.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if missing refund, inbound, fee, market, supplier, or Max-pay proof is treated as clean expected profit.

## Source Evidence
- MOT check: `o_refund_restock_confidence_fields`
- Current MOT state: `not_checked`
- Current proof clue: O restock source view is missing refund confidence fields and O still treats inbound cost confidence as missing.
- Research note: `O_EXPECTED_RESTOCK_PROFIT_RESEARCH_20260601.md`

## Allowed Files
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/O021_build_restock_profit_checks.py`
- `scripts/flows/O/O460_build_restock_session_view.py`
- `scripts/flows/O/O464_build_restock_supplier_batch_drafts.py`
- `scripts/flows/O/O470_build_purchase_approval_preview.py`
- `scripts/flows/O/O474_build_po_draft_readiness_preview.py`
- `scripts/flows/O/O476_build_po_line_design_preview.py`
- `scripts/flows/O/O478_build_po_draft_packet_review.py`
- `scripts/flows/O/O480_build_po_draft_hold_review.py`
- `scripts/flows/O/O482_build_po_draft_file_shape_preview.py`
- `scripts/flows/O/O488_build_po_draft_export_preview.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- focused O tests under `tests/`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/`

## Acceptance Checks
- O source view carries refund-rate, refund drag, refund proof state, inbound/FBA-send cost proof, and combined `profit_input_confidence`.
- Missing refund or inbound proof is labelled `missing` or `weak`, never silently treated as clean zero cost.
- Restock Session shows refund, inbound, and profit-confidence blockers in plain English.
- Real-PO readiness remains closed while refund/inbound/profit proof is missing or weak.
- O MOT retest shows the expected-profit confidence check visible and safe.
- Render/browser proof changes no proof, draft, approval, PO-control, purchase, receiving, or send-to-Amazon event rows.

## Expected End State
O can tell Luke whether a restock profit estimate is clean, weak, or missing before any approval or PO step is trusted.
