# E Missing ROI Reason Output v1

## Manager Authority
- task_id: MGR_E_MISSING_ROI_REASON_OUTPUT_V1
- job_ref: E-MISSING-ROI-REASONS
- flow: E
- task_type: build_gap
- priority: high
- status: proved
- authority: luke_requested_build_list
- luke_action_required: 0

## Plain-English Purpose
Make E explain why a product has no ROI proof.

Right now E can show that many SKUs are velocity-only, but Luke needs to know the reason, not just the count.

## Boundary
- allowed_scope: E missing-ROI reason design, E output-contract planning, E manager proof mapping, focused E tests, and E/O confidence handoff notes.
- forbidden_actions: no E live run without approved proof window; no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no output deletion; no B data correction; no fake ROI fill; no hiding velocity-only rows; no worker restart; no business decision; no scope widening into B, F, H, or O implementation without a separate packet.
- proof_required: E must be able to show a clear missing-ROI reason for SKUs that have velocity/restock evidence but no ROI row.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: Use git diff for code rollback. Do not hand-edit E output files to create reasons.
- stop_condition: Stop if the work needs protected action or cross-flow data correction.

## Expected Build Output
- A reason field or companion output that groups missing ROI into:
  - no recent sales truth
  - missing COGS
  - missing fee proof
  - missing refund proof
  - missing current price proof
  - stock-only SKU with no ROI window
  - upstream B money proof bridge-labelled only

## Acceptance Proof
- Fixture test where 161 SKUs exist and only a smaller subset has ROI.
- E proof shows each missing-ROI SKU has a reason.
- E keeps those rows out of business-ready restock status.
