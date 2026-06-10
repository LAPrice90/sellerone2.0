# SellerOne Prompt And Plan Folder Archive

Job: `SO21-PROMPT-FOLDER-ARCHIVE`
Date: 2026-06-08

## Plain-English Status

The old prompt and plan folders are now marked as history or template material.

They are not deleted, moved, or treated as bad. They are just no longer live operating memory. The live control desk now uses approved task packets and generated control files instead.

## Archived-As-History Folders

| Folder | Files | Bytes | New Status |
|---|---:|---:|---|
| `plans` | 571 | 35196654 | history/template only |
| `sellerone_manager/thread_prompts` | 13 | 34288 | history/template only |
| `sellerone_manager/agent_launch_prompts` | 8 | 18628 | history/template only |
| `sellerone_manager/thread_starters` | 6 | 20176 | history/template only |
| `sellerone_manager/project_threads` | 24 | 62875 | history/template only |
| `sellerone_manager/goals` | 12 | 12656 | history/template only |

## Live Sources That Replace Them

- `sellerone_manager/tasks/approved/`
- `sellerone_manager/tasks/blocked/`
- `sellerone_manager/CONTROL/CURRENT_STATE.md`
- `sellerone_manager/CONTROL/CURRENT_TICKETS.md`
- `sellerone_manager/CONTROL/BACKLOG.md`
- `sellerone_manager/CONTROL/QUEUE_CONTRACT.md`
- `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md`

## Rules

- Do not use these old folders as the source of active work.
- Do not treat old prompt files as fresh approval.
- Do not start workers from old prompt files unless a current approved packet exists.
- Do not delete these folders from this archive marker.
- If a prompt pattern is still useful, convert it into a 2.1 skill or task template during `SO21-SKILL-SPECS`.

## Rollback

No folder contents were moved or deleted.

Rollback is simple: remove this marker file if Luke decides these folders should become live control memory again.

Inventory snapshot:

- `sellerone_manager/CONTROL/prompt_folder_archive_backups/20260608T132403_so21_prompt_folder_archive/PROMPT_FOLDER_ARCHIVE_MANIFEST.before.csv`
