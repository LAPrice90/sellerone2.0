# H Repair Package - Transient Token Network Boundary - 2026-06-02

## Manager Authority
- task_id: MGR_H_repair_h_transient_token_network_boundary
- job_ref: H-TRANSIENT-TOKEN-NETWORK
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `scripts/cycles/run_H_pricing_cycle.py` - `scripts/tools/H_own_offer_lookup.py` - `scripts/tools/H_item_offers_lookup.py` - `scripts/api/get_listing_item_price.py` - `scripts/api/get_pricing.py` - `scripts/flows/H/H130_build_phase1_observation_sheet.py`, only for status-only error classification and proof wording - focused H lifecycle, token-boundary, and manager MOT tests under `tests/` - this repair package and `CODING_PLAN.md`
- forbidden_actions: - Do not run H from Codex. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align local DB facts. - Do not delete outputs. - Do not restart workers. - Do not hand-edit manifests, terminal markers, publish markers, MOT rows, health rows, or H output files to make proof look clean. - Do not widen into A, B, E, F, or O.
- proof_required: - First prove the token/network failure path in focused tests. - A safe code repair may improve retry, classification, or manager-visible proof for transient token/network failure. - A safe code repair must not convert a real failed run into success. - Compile every touched H/API/proof file. - Run focused H tests for the changed code. - Run manager H MOT tests. - Retest with the read-only H MOT command. - Real H recovery is proved only when a natural or separately approved H-owned run leaves: - latest manifest final state `completed` - terminal state `finalized` - publish status `ok` or a clearly safe parked state - independent H MOT clears `h_latest_manifest_state`, `h_terminal_publish_truth`, and `h_boundary_finalizer_truth`
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: - Use git diff for code rollback. - Do not alter H output files to satisfy proof. - If future code changes affect token/network handling, revert only the touched token-boundary or proof-classification code and rerun focused tests plus H MOT.
- stop_condition: - Stop if the repair would require a live H run, scheduler pause/resume, publish, price change, queue edit, Sheet write, DB alignment, output deletion, worker restart, or scope widening. - Stop if evidence shows the next failure is not token/network-boundary related. - If the newer natural H run finalizes cleanly, record that as proof and mark the MOT packets proved after read-only H MOT clears.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_H_TRANSIENT_TOKEN_NETWORK_BOUNDARY_20260602
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_H_TRANSIENT_TOKEN_NETWORK_BOUNDARY_20260602.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_H_TRANSIENT_TOKEN_NETWORK_BOUNDARY_20260602",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_H_TRANSIENT_TOKEN_NETWORK_BOUNDARY_20260602.md"
}
```
