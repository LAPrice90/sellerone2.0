# F Cycle Expectations

## Purpose
F is the price-list intake, scanner-control, and new-product review handoff lane. It should make supplier files traceable from source proof, through import proof, through queue control, scanner ownership, recovery, and review readiness.

The manager must be able to tell whether F is running, stuck, stale, blocked, waiting for login, missing proof, or waiting for a protected Luke decision without running F061.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Manager front door and snapshot | The manager can read the F state, current owner summary, and script registration coverage from outside F. | In Progress | Proved by `f_manager_snapshot_current` and `f_manager_registration_coverage`. |
| Live owner and scanner heartbeat | F can prove whether the live owner and F061 child are running, stale, idle, or contradictory. | In Progress | Proved by `f_live_owner_status` and `f_child_scanner_heartbeat`; this must not restart workers. |
| Storage drift safety | F can prove CSV and SQL-compatible storage are aligned where F expects mirrored live proof. | In Progress | Proved by `f_storage_drift_clear`; this must not change local DB facts. |
| Supplier source intake proof | F can link supplier source status, local files, import batches, and row counts without fetching files from MOT. | In Progress | Proved by `f_source_intake_chain_proof`, `f_email_price_list_source_proof`, and `f_url_source_download_proof`; old fallback proof stays warning only. |
| Queue recommendation and handoff controls | F can explain which supplier is next and whether handoff controls are readable without approving live handoff. | In Progress | Proved by `f_queue_recommendation_explainable` and `f_queue_handoff_control_proof`; this must not edit queue state. |
| Login and browser control | F can separate BBP account login, Seller Central eligibility login, and visible-login maintenance state. | In Progress | Proved by `f_login_mode_state`, `f_bbp_account_login_state`, `f_seller_central_eligibility_auth_state`, and `f_visible_login_control_proof`; only the normal F061-owned browser is allowed for scanner login recovery. |
| Recovery and parked-row protection | F can prove recovered rows are reconciled and protected decision rows stay parked until a real decision or approved recovery exists. | In Progress | Proved by `f_recovery_progress_proof` and `f_parked_decision_rows`; this must not publish or accept parked rows. |
| Review and production-line readiness | F can prove review handoff, AI gate, split rollout, and production-line readiness before rows reach operator review. | In Progress | Proved by `f_review_handoff_ai_gate`, `f_review_ai_production_readiness`, and `f_production_line_stage_health`; this must not run scanner stages or enable rollout. |

## SECTION 2 - Reliability Measurement
Measure F reliability from independent MOT and manager proof, not from scanner self-report alone:

- Fail: missing owner proof, stale running child heartbeat, unsafe storage drift, missing source/import chain proof, unapproved live handoff, or review rows presented without AI/production proof.
- Warning: stale but readable queue/source proof, source fallback import proof, parked quiet-autonomy rows, or manual supplier proof waiting for a separate approved refresh.
- Decision: protected row choice, live scanner proof window, queue edit, handoff approval, price change, Sheet write, local DB alignment, output deletion, or worker restart.

## SECTION 3 - Acceptance Criteria
- Replacement complete: F has manager-readable proof from source intake through review handoff.
- Stable: independent F MOT has 0 active FAIL rows.
- Manageable: active WARN rows clearly say whether they are stale proof, fallback proof, waiting proof, or protected parked work.
- Safe: no F manager proof path runs F061, edits queues, writes Sheets, changes prices, changes local DB facts, deletes outputs, restarts workers, or opens a separate login browser.

## SECTION 4 - Improvement Backlog
- Refresh source proof through an approved source task so ABGee, Shure, Stax, and CLF warnings stop relying on old proof.
- Replace old fallback source links with cleaner source-to-batch trace rows.
- Improve manual login usability in the normal script-owned browser path.
- Keep Seller Central eligibility login as a separate proof gate from BBP account login.
