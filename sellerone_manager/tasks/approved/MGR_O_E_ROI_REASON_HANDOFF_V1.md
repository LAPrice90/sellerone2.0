# O E ROI Reason Handoff v1

## Manager Authority
- task_id: MGR_O_E_ROI_REASON_HANDOFF_V1
- job_ref: O-E-ROI-HANDOFF
- flow: O
- task_type: bounded_o_handoff
- priority: high
- status: proved
- authority: e_roi_coverage_build_gap
- luke_action_required: 0

## Plain-English Purpose
Show E's missing-ROI reason labels inside the O restock working view.

E now explains why a SKU has no clean ROI. O needs to carry that explanation forward so Luke can see whether a restock row is clean, weak, or only a clue.

## Boundary
- allowed_scope: O restock source view read-only carry-through of E confidence fields, O source contract update, focused O source-view tests, O UI use of existing missing-proof display/filter fields, O MOT proof, and E/O handoff notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no purchase decision; no PO creation; no Product DB or local DB alignment; no output deletion; no B correction; no fake ROI fill; no hiding velocity-only rows; no E live run; no O live business action; no worker restart; no scope widening into B, F, H, or pricing.
- proof_required: O restock source view carries `missing_roi_reason`, `missing_roi_reason_detail`, `restock_decision_state`, `restock_missing_proof`, `restock_business_ready`, `stock_signal`, `profit_confidence`, and `sales_truth_state` from E without changing business facts; missing ROI rows stay blocked from buy-ready wording; focused O tests pass; O MOT stays safe.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not edit O or E outputs by hand to improve proof.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, Sheet write, price change, queue edit, purchase decision, PO creation, Product DB/local DB alignment, output deletion, B repair, E live run, worker restart, or cross-flow scope widening.

## Acceptance Proof
- O source contract names the E confidence fields it expects.
- O restock source view carries the E fields for matching SKUs.
- Rows without clean ROI do not become buy-ready because of this handoff.
- O missing-proof card/filter logic can see the carried proof labels when those rows appear in O.
- Focused O source-view tests pass.
- O MOT retest does not create unsafe buying action warnings.

## Expected End State
Luke can use the O restock screen and see the same plain missing-ROI reason that E proved, instead of seeing a vague or hidden profit gap.
