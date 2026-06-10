# SO21 Blueprint Finalisation Handoff

Created: 2026-06-08

## Plain-English Purpose

This file keeps the SellerOne 2.1 blueprint finalisation from depending on chat memory.

The Manager project remains the clean Luke-facing Rep chat. Technical execution belongs in clean SellerOne 2.0 worker threads that start from approved task packets, not from a fork of the Rep conversation.

## Operating Model

SellerOne Manager Project:

- Rep Chat talks to Luke, plans priorities, and turns decisions into tickets.
- Operations Chat runs control-desk automations, monitors workers, creates reports, and maintains queue visibility.

SellerOne 2.0 Project:

- Worker Chats execute approved tickets.
- Reviewer Chats verify tickets.

Worker and Reviewer chats must start clean from task packets and must not inherit Rep-chat history.

## Current First Task

- job_ref: `SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST`
- packet: `sellerone_manager/tasks/approved/MGR_SO21_LEGACY_CONTROL_RETIREMENT_MANIFEST_V1.md`
- owner: Custodian-style worker in the SellerOne 2.0 project
- current state: approved

Luke correction:

- The active objective is to clean up old control habits and duplicate management layers.
- `SO21-REP-BRIEFING-FIRST-RUN-PROOF` is not the cleanup gate. It can remain waiting on scheduled evidence in the background.
- Do not block old-control cleanup planning on the Rep briefing proof.

## Worker Start Prompt

Use this prompt in a clean SellerOne 2.0 worker thread:

```text
Read sellerone_manager/WORKER_CHAT.md and work only on approved packet SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST.

Packet:
sellerone_manager/tasks/approved/MGR_SO21_LEGACY_CONTROL_RETIREMENT_MANIFEST_V1.md

This is a preview-only cleanup planning task. Do not delete, move, compress, purge, archive, or rename files.

Create the legacy-control retirement manifest required by the packet. Classify old work logs, prompt folders, old plans, thread starters, duplicate manager files, and previous management generations as keep-current, history, template, archive-candidate, or needs-Luke-decision.

Business runtime is outside scope. Do not run business runtime, change Task Scheduler, edit automations, start workers, edit queues, delete outputs, write Sheets, change databases, change prices, or touch Amazon.
```

## Stop Rules

The worker must stop and report back if:

- cleanup would require deleting, moving, compressing, purging, archiving, or renaming files
- cleanup would require changing an automation
- proof would require starting or restarting a worker
- cleanup would require changing Windows Task Scheduler
- cleanup would require any business runtime change
- cleanup would require queue edits beyond an allowed packet status update

## Success Criteria

The task is complete only when:

- a preview-only legacy control retirement manifest exists under `sellerone_manager/CONTROL/`
- the manifest clearly separates new-current control files from old/history/template material
- exact paths are named before any future cleanup is considered
- anything destructive or risky is marked as needing Luke approval
- no files are deleted, moved, compressed, purged, archived, or renamed

## Background Waiting Task

`SO21-REP-BRIEFING-FIRST-RUN-PROOF` remains waiting proof in the background. It is not the active cleanup task.

## Next Task After This Passes

After `SO21-LEGACY-CONTROL-RETIREMENT-MANIFEST` passes, the next cleanup task is:

- `SO21-CONTROL-FLOW-CONFIRMATION`

Do not perform destructive cleanup until Luke approves an exact apply manifest.
