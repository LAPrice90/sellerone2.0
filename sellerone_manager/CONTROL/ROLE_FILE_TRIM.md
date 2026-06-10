# SellerOne Role File Trim

Job: `SO21-ROLE-FILE-TRIM`
Date: 2026-06-08

## Plain-English Status

The old role files have been trimmed into short SellerOne 2.1 front-door files.

The old detail was not deleted. It was copied into a rollback backup first.

## Files Trimmed

| File | Before Bytes | New Purpose |
|---|---:|---|
| `MANAGER_CHAT.md` | 14774 | short Manager/Rep front door |
| `CYCLE_SUB_MANAGER_CHAT.md` | 2966 | short cycle sub-manager front door |
| `WORKER_CHAT.md` | 4028 | short Builder/Worker front door |
| `MANAGER_PROGRESS_TRACKER.md` | 15748 | pointer to generated current-state files |

## Replacement Sources

- `CONTROL/ROLE_BOOTSTRAP.md`
- `CONTROL/RUNTIME_SAFETY_RULES.md`
- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/BACKLOG.md`
- `CONTROL/OPERATIONS.md`

## Rule

These role files are now entry points, not full rulebooks.

Current state belongs in generated control files. Active work belongs in approved task packets and generated queue views.

## Rollback

Rollback copies are preserved here:

- `sellerone_manager/CONTROL/role_file_trim_backups/20260608T133533_so21_role_file_trim/`
