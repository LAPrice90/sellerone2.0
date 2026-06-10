# O PO File Shape And Construction Summary v1

## Manager Authority
- task_id: MGR_O_PO_FILE_SHAPE_AND_CONSTRUCTION_SUMMARY_V1
- job_ref: O-PO-FILE-SHAPE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_larger_safe_bundle
- luke_action_required: 0

## Plain-English Purpose
Add the next local PO preview layer and a single construction summary for the whole PO preview chain.

This adds a file-shape preview after the current hold-review layer. It shows what a future local PO draft file could need to look like, but it does not create purchase orders, write PO files, write PO hold files, commit buying, receive stock, or send anything to Amazon.

## Boundary
- allowed_scope: O PO draft file-shape preview contracts, local builder, PO preview construction summary contracts, local builder, UI preview view, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O file-shape/session/UI/MOT tests must pass, the full local O preview builder chain must run once, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local file-shape or construction-summary output is malformed, rebuild through O482 and O484 only after upstream local preview files are safe.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O482_build_po_draft_file_shape_preview.py`
- `scripts/flows/O/O484_build_po_preview_construction_summary.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o482_po_draft_file_shape_preview.py`
- `tests/test_o484_po_preview_construction_summary.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O484_build_po_preview_construction_summary.py scripts\flows\O\O482_build_po_draft_file_shape_preview.py scripts\flows\O\O480_build_po_draft_hold_review.py scripts\flows\O\O478_build_po_draft_packet_review.py scripts\flows\O\O476_build_po_line_design_preview.py scripts\flows\O\O474_build_po_draft_readiness_preview.py scripts\flows\O\O472_build_purchase_approval_guardrails.py scripts\flows\O\O470_build_purchase_approval_preview.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o484_po_preview_construction_summary.py tests\test_o482_po_draft_file_shape_preview.py tests\test_o480_po_draft_hold_review.py tests\test_o478_po_draft_packet_review.py tests\test_o476_po_line_design_preview.py tests\test_o474_po_draft_readiness_preview.py tests\test_o472_purchase_approval_guardrails.py tests\test_o470_purchase_approval_preview.py tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O470_build_purchase_approval_preview.py`
- `python scripts\flows\O\O472_build_purchase_approval_guardrails.py`
- `python scripts\flows\O\O474_build_po_draft_readiness_preview.py`
- `python scripts\flows\O\O476_build_po_line_design_preview.py`
- `python scripts\flows\O\O478_build_po_draft_packet_review.py`
- `python scripts\flows\O\O480_build_po_draft_hold_review.py`
- `python scripts\flows\O\O482_build_po_draft_file_shape_preview.py`
- `python scripts\flows\O\O484_build_po_preview_construction_summary.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show the local PO preview chain in one place: readiness, line design, packet review, hold review, and file-shape preview. The new outputs stay separate from existing live PO files and cannot create or commit a buy.

## Proof Result
- proved_utc: 2026-06-03T10:20:52Z
- Full compile passed for O400, O484, O482, O480, O478, O476, O474, O472, O470, O schemas, and O MOT.
- O-scoped proof tests passed: 130 tests, 101 deselected.
- Live local builder chain passed: O470 -> O472 -> O474 -> O476 -> O478 -> O480 -> O482 -> O484.
- Live O482 output: 0 line rows, 0 summary rows, 4 health rows, health ok.
- Live O484 output: 5 construction-summary rows, 4 health rows, health ok.
- O MOT result: 0 fails, 1 existing stale-proof warning; `o_po_draft_file_shape_preview=ok`; `o_po_preview_construction_summary=ok`; `o_user_working_readiness=ok`.
- Streamlit AppTest Restock Session render: 0 exceptions and both new panels visible.
- Broad shared `tests/manager/test_hourly_mot.py` still has unrelated B-flow failures from missing `_b_return_token_matching_audit_rows`; no B code was changed inside this O packet.
- No Google Sheets write, price change, queue edit, Product DB/local DB alignment, real PO, PO file write, existing PO hold-file write, purchase commitment, receiving, send-to-Amazon, H pause, market scan, output deletion, or live worker cycle was performed.
