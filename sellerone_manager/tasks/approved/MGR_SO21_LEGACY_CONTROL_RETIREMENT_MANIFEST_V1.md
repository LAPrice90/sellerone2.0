# SO21 Legacy Control Retirement Manifest v1

## Manager Authority
- task_id: MGR_SO21_LEGACY_CONTROL_RETIREMENT_MANIFEST_V1
- job_ref: SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST
- flow: SO21
- task_type: custodian_manifest
- status: proved
- authority: luke_approved_blueprint_finalisation
- priority: normal
- luke_action_required: 0

## Plain English
The old coding-management material is still physically present. This ticket produces the exact retirement manifest before anything is moved, deleted, or compressed.

The goal is to separate old useful history from old live-looking control material, so future Codex threads do not accidentally revive work logs, old prompt folders, old plans, or previous manager generations as the current system.

## Allowed Work
- inspect old control folders and files already named in the 2.1 inventory
- classify each old control source as keep-current, history, template, archive-candidate, or needs-Luke-decision
- produce a readable manifest under `CONTROL/`
- include a recommended next step for each class
- preserve business runtime separation in the manifest
- identify anything that still looks like a live control source but should not be one

## Forbidden Work
- no deletion
- no moving files
- no compression
- no purging
- no queue status movement
- no business runtime changes
- no Windows Task Scheduler changes
- no Codex automation changes
- no worker runs or restarts
- no price changes
- no Google Sheets writes
- no Product DB or local DB alignment
- no Amazon login or security action

## Acceptance Proof
- A preview-only legacy control retirement manifest exists under `CONTROL/`.
- The manifest clearly separates new-current control files from old/history/template material.
- The manifest names exact paths before any future cleanup is considered.
- The manifest marks anything destructive or risky as needing Luke approval.
- No files are deleted, moved, compressed, purged, or archived by this ticket.

## Retest
- retest_command: Inspect the generated retirement manifest and confirm no file movement or deletion occurred.

## Stop Condition
Stop and return to Luke before any action that would move, delete, compress, purge, disable, re-enable, or otherwise alter old files, schedulers, automations, queues, or runtime assets.
