# SellerOne Manager Control Plane V1 - Data Contracts

## Input Contracts
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
  - Owner: F price-list manager live owner.
  - Purpose: tells the manager whether the live F owner is running, blocked, idle, or draining.
- `out/systems/F/price_list_manager/live/storage_drift_report.csv`
  - Owner: F price-list manager storage drift guard.
  - Purpose: gives storage drift evidence when that preflight blocks the live owner.
- `out/systems/F/price_list_manager/test_mode/status_dashboard.csv`
  - Owner: F price-list manager dashboard builder.
  - Purpose: tells the manager which supplier is recommended, queued, missing files, or paused.
- `project_control/DUE_CHECK_REGISTER.csv`
  - Owner: project control.
  - Purpose: durable follow-up register.
- `out/cycle_alerts/summary.csv`
  - Owner: A015 health output.
  - Purpose: broad flow health counts.
- `config/runtime_owner_contract.json`
  - Owner: project control.
  - Purpose: declares which scripts own runtime flow control.
- `project_control/SCRIPT_INVENTORY.csv`
  - Owner: project control inventory.
  - Purpose: lets the manager spot worker-like scripts that are not yet covered by manifests.

## Manager Output Contracts
- Snapshot rows use one row per observed module state.
- Health rows use `check,status,value,notes,observed_utc,source_path`.
- Incident rows use `observed_utc,flow,severity,incident_code,summary,needs_user,root_artifact,remediation_hint`.
- Codex repair queue rows use `observed_utc,created_utc,updated_utc,last_seen_utc,seen_count,flow,task_id,owner,priority,status,source_incident_code,task_summary,root_artifact,allowed_scope,forbidden_actions,proof_required`.
- Codex repair event rows use `event_utc,task_id,event_type,old_status,new_status,actor,note,source`.
- Codex repair task IDs are stable for the same flow, incident code, and root artifact. Repeated sightings update `last_seen_utc` and `seen_count` instead of creating duplicate tasks.
- If a previously queued task is not seen on a later manager run, its status becomes `cleared_pending_review` rather than disappearing.
- The event log is append-only. It records task creation, stable-ID migration, manual status updates, and lifecycle status changes.
- Self-organisation rows use `observed_utc,script_path,flow_group,inferred_role,status,notes`.
- F script registration rows use `observed_utc,script_path,discovery_sources,classification,classification_reason,is_exempt,needs_codex_review,blocks_f_operation,owner,purpose,entrypoint,health_source,expected_outputs,runbook_notes_link,safe_actions_declared,forbidden_actions_declared,missing_fields,manager_module_id,notes`.
- F script registration classifications are `registered`, `unregistered`, `one_off_exempt`, `legacy_exempt`, and `needs_review`.
- V1.1 self-organisation outputs are manager-owned report files only. They do not block F operation and do not edit worker scripts.
- F manifest priority rows use `observed_utc,rank,script_path,classification,priority_score,priority_band,recommended_action,safe_to_manifest_without_worker_changes,reason_codes,reason_summary,referenced_by_manifest,referenced_by_status_or_runtime,live_entrypoint,writes_live_outputs,queue_ownership,storage_drift_or_preflight,supplier_status_dashboard,recently_modified,mtime_utc,defer_reason`.
- F manifest priority output is manager-owned ranking only. It does not create manifests, edit worker scripts, run worker cycles, write Google Sheets, or add safe dispatching.
- F manifest priority top candidates are non-exempt scripts. Already registered scripts, one-off scripts, and legacy scripts are deliberately deferred.
- V1.3 script-level F manifests live under `config/manager/modules/`.
- V1.3 script-level manifests must remain read-only in manager V1. They may declare `read_status` as a safe action, but they must not declare restart, retry, dispatch, queue-change, pricing, delete, Google Sheets, or worker-run actions.
- Self-organisation registration must count all F manifests in `config/manager/modules/`, not only `F_price_list_manager.json`.
- UX V1 current state lives at `sellerone_manager/current_state.json`.
- UX V1 current state is built from existing manager outputs only. It does not read raw worker evidence.
- UX V1 current state fields include `system_status`, `active_flow`, `current_state`, `luke_action_required`, `luke_action`, `codex_task_available`, `codex_task_title`, `next_safe_batch`, `do_not_touch`, `manager_execution_errors`, and `latest_evidence`.
- Multi-flow state rows use `observed_utc,flow,flow_name,rollout_rank,status,classification,needs_luke_decision,luke_decision,codex_task_available,codex_task_title,active_fail_count,active_warn_count,stale_evidence_count,not_verified_count,covered_expectations,total_expectations,first_blocker_code,first_blocker_summary,proof_rule,evidence_paths,notes`.
- Expectation reconciliation rows use `observed_utc,flow,feature,expected_status,manager_status,evidence_status,evidence_checks,notes,source_path`.
- Manager task candidate rows use `observed_utc,flow,task_id,task_type,priority,status,title,root_artifact,allowed_scope,forbidden_actions,proof_required,stop_condition,needs_luke_decision,notes`.
- Multi-flow expectation statuses are `covered`, `not_verified`, `incorrect`, `blocked`, and `not_started`.
- Multi-flow rollout order is A, B, E, H, F, O.
- Multi-flow outputs are task-control-first. They create manager task candidates and proof paths, but they do not dispatch workers.

## Codex Repair Task Statuses
- `queued`: Codex has a technical task to pick up later.
- `in_progress`: Codex has started the technical investigation or repair planning.
- `blocked_needs_user_decision`: Codex cannot continue without Luke choosing a business or safety option.
- `cleared_pending_review`: the manager no longer sees the blocker, but Codex has not reviewed the clear state yet.
- `completed`: Codex has completed and proved the task.
- `reopened`: a task that was previously closed has appeared again.

## Status Meaning
- `ok`: no active blocker found in the checked scope.
- `warn`: checked evidence is unusual, stale, or not fully classified.
- `fail`: the manager cannot read required evidence or its own contract is broken.
- `needs_user`: Luke must supply input, such as a manual file.
- `blocked`: a worker cannot proceed because an earlier technical gate is blocking it.
- `stale_evidence`: evidence exists but is older than the declared freshness rule.
- `not_checked`: the manager did not inspect that item in this run.
