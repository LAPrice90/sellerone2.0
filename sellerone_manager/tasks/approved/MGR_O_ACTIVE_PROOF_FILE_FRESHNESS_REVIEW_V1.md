# O Active Proof File Freshness Review v1

## Manager Authority
- task_id: MGR_O_ACTIVE_PROOF_FILE_FRESHNESS_REVIEW_V1
- job_ref: O-PROOF-FILE-FRESHNESS
- flow: O
- task_type: manager_read_only_proof
- priority: normal
- status: proved
- authority: o_cycle_sub_manager_from_mot_o_active_restock_proof_files
- luke_action_required: 0

## Plain-English Purpose
O has a warning because some proof files are older than the manager freshness window.

This job is to work out whether those files are expected bridge evidence, safe to refresh through local O builders, or genuinely stale proof that should stay as a warning. It must not delete, overwrite for appearance, or claim old bridge files are native O completion.

## Boundary
- allowed_scope: inspect O active proof-file ages, row counts, source labels, bridge labels, freshness rules, O manager/MOT wording, focused manager tests, and safe local O proof refresh commands when they do not touch protected actions.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no output rewrite just to make age warnings disappear.
- proof_required: identify each stale O proof file, classify it as bridge/proof-only/native/local-refresh-needed, refresh only safe local O outputs if needed, keep bridge files labelled as bridge, and retest O MOT with truthful freshness status.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if clearing the warning would require deleting outputs, running H market proof, editing bridge data, writing Sheets, changing queues/prices, creating POs, receiving stock, sending to Amazon, or pretending bridge evidence is native O truth.

## Source Evidence
- MOT check: `o_active_restock_proof_files`
- Current MOT state: `warn`
- Current proof clue: `stale_warn=4`
- Stale files currently listed by MOT: `restock_recommendations_live`, `restock_review_queue`, `legacy_purchase_list_bridge`, and `legacy_purchase_list_bridge_health`

## Allowed Files
- `sellerone_manager/hourly_mot.py`
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/flows/O/O021_build_restock_profit_checks.py`
- `scripts/flows/O/O460_build_restock_session_view.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- focused O/MOT tests under `tests/`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/`

## Acceptance Checks
- Each stale proof file is classified in plain English as safe, bridge, proof-only, or needs real refresh.
- The MOT freshness rule is still honest and does not hide stale files.
- Legacy bridge files remain labelled as bridge and are not called native O truth.
- O MOT retest keeps 0 fails and keeps any genuine stale warning visible.
- No protected action is performed.

## Expected End State
The board shows the stale-proof warning as a bounded O maintenance job instead of leaving it as vague background noise.
