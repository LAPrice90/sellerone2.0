# SO21 Morning Improvement Report - 2026-06-09

Created: 2026-06-09 05:15 UK
Role: Operations
Mode: read-only proposal/reporting only

## Plain-English Summary

The overnight control work did what it was meant to do: it proved that the new SellerOne 2.1 control desk can keep track of work, recover after the expected PC restart, and record blockers without touching the live business.

The main finding is simple: SellerOne is now ready for a professional-grade control pass, but cleanup must stay report-first. The biggest measured storage opportunity is H staged data, not random deletion. Maintenance mode is designed around records and proof, not a panic button.

## Evidence Reviewed

- `CONTROL/SO21_OVERNIGHT_CONTROL_TEST_PLAN.md`
- `CONTROL/SO21_OVERNIGHT_CONTROL_TEST_STATUS.md`
- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/SO21_ACTIVE_SYSTEM_SERVICE_MOT_PLAN.md`
- `CONTROL/SO21_MAINTENANCE_MODE_IMPLEMENTATION_PLAN.md`
- `CONTROL/SO21_DATA_LIFECYCLE_AND_DEDUP_PLAN.md`
- `CONTROL/SO21_DATA_FAMILY_INVENTORY.md`
- `CONTROL/SO21_DUPLICATE_DATA_REPORT.md`
- `CONTROL/SO21_OUTPUT_RETENTION_RULES.md`
- `CONTROL/SO21_DATA_CLEANUP_AUTOMATION_DESIGN.md`
- `CONTROL/SO21_PROFESSIONAL_GRADE_FINALISATION_PLAN.md`
- `CONTROL/SO21_SCRIPT_STATUS_AND_SCHEDULER_STYLE_PLAN.md`
- approved packets for `SO21-ACTIVE-SYSTEM-SERVICE-MOT`, `SO21-MAINTENANCE-SCRIPT-QUALITY-REVIEW`, and `SO21-PROFESSIONAL-GRADE-FINALISATION`

No business runtime, Windows Task Scheduler state, Amazon/security path, price, Sheet, database, output data, purchase, receiving, send-to-Amazon action, worker restart, process kill, deletion, movement, compression, purge, or archive apply was performed.

## Active System MOT Findings

### Healthy

- The canonical queue is now the approved task packet system, with readable views in `CONTROL/CURRENT_STATE.md`, `CONTROL/CURRENT_TICKETS.md`, and `CONTROL/BACKLOG.md`.
- Post-restart recovery evidence is recorded in `CONTROL/SO21_OVERNIGHT_CONTROL_TEST_STATUS.md`.
- Active control automations were confirmed as only:
  - `so21-cleanup-operations-monitor`
  - `so21-rep-briefing`
- No active maintenance marker was found after the expected restart.
- Old manager-noise folders remain pointer-only or archive/quarantine context, not live control.

### Fragile

- `CURRENT_STATE.md` still recommends `SO21-REP-BRIEFING-FIRST-RUN-PROOF`, even though Luke clarified that proof is background only. This can make the queue look more blocked than it is.
- `plans/active` still exists as legacy context. It is not canonical live control, but its name can still confuse humans unless the finalisation pass explains it clearly.
- The MOT still reports `decision_needed` with 16 fails, 19 warnings, and 1 decision. Many of those are business-flow repairs outside this control-desk morning pass.
- Some active tickets are ready for Builder even though the safest next control work is review/proof tidy-up. The no-idle rule helps, but the queue still needs visible sequencing.

### Recommended Fix Order

1. Prove or reviewer-check the planning reports that already exist.
2. Create a compact Operations runbook and proof matrix so Luke can see what is live, what is background, and what needs a decision.
3. Keep business-flow MOT repairs separate from control-desk finalisation.
4. Move storage cleanup only to owner-proof and dry-run-manifest work, starting with H staged retention design.

## Maintenance Script Quality Review

### Bugs Or Safety Risks

- The maintenance-mode design is correct in principle, but it must not become a shortcut for blind pause/restart. Every future use needs a maintenance request, named target, exact restart route, and post-restart proof route.
- The script-status plan still needs a concrete health map. Without it, Luke may still have to interpret scattered MOT checks, scheduler facts, and output timestamps.
- Broad recursive checks can run into Windows permission or timeout behavior. This already happened in earlier review evidence. The safer pattern is narrow read-only checks with blocker logging.
- Cleanup/reporting automation can create more large housekeeping files if retention rules for reports are not added before frequent scheduling.

### Efficiency Improvements

- Build a read-only script health register before any scheduler or runtime work. It should name script, owner, cadence, proof output, stale threshold, failure threshold, and repair owner.
- Standardize the post-restart check as a small command set: refresh views, read active automations, check maintenance markers, check old-control pointers, record blockers.
- Keep maintenance records as plain files first. Do not add scripts that pause or restart anything until the record format and proof route are reviewed.
- Use bounded scans for storage and duplicate reports. Full hashing of large H or DB files should be a separate approved proof-window packet.

### Tomorrow Recommendation

Create a review-only `SO21-SCRIPT-HEALTH-REGISTER` follow-up that turns the script status plan into one plain-English table. Do not change Task Scheduler from that packet.

## Professional-Grade Finalisation Findings

### Missing Finalisation Pieces

- Short operating manual for Luke: how Rep, Operations, Worker, and Reviewer fit together.
- Daily runbook: morning check, post-restart check, stuck-job check, blocker escalation, and maintenance entry/exit.
- Proof matrix: each active SO21 control ticket, proof route, owner role, pass condition, and failure response.
- Automation register: name, purpose, owner, cadence, approved state, pause/restart rule, proof output.
- Risk register: current risk, why it matters, current mitigation, next action, Luke decision needed or not.

### Business Benefit

These documents reduce the chance that Luke has to read technical clutter or decide from memory. They also make it easier to hand work to Workers and Reviewers without accidentally widening scope.

## Data Lifecycle And Dedup Findings

### Measured Storage Priorities

| Area | Measured fact | Safe interpretation |
|---|---:|---|
| `out/systems/` | 140.87 GB | Main storage area to understand before cleanup |
| `out/systems/H/staged/` | 126.29 GB | Largest measured opportunity, but needs H owner proof |
| `out/backups/` | 9.48 GB | Rollback material, not trash |
| `out/systems/F/price_list_manager/` | 28,835 files and 2.24 GB | High file-count area, needs F owner map |
| Duplicate report exact sample | 75.63 MB hash-proven duplicate space | Proved but small sample |
| Duplicate report likely candidates | 17.82 GB same-name and same-size estimate | Candidate only, not deletion proof |

### Bugs Or Risks

- H staged data is the biggest storage pressure, but it may contain current proof, failed partial runs, or pricing/intelligence evidence.
- Database and backup copies look duplicate but may be the fastest rollback route.
- F live/browser profile data may look like cache clutter but is scanner-owned and security-sensitive.
- Same-name and same-size is not enough proof for dedupe apply.
- Cleaning root `out/` by age or extension would be unsafe because live and old files are mixed.

### Efficiency Improvements

- Start with H staged retention dry-run design because it has the largest measured opportunity and a clear owner-proof gap.
- Add housekeeping-report retention before scheduling frequent storage reports, so the reporting layer does not become the next storage problem.
- Keep rollback cleanup separate from output cleanup. Backups need a recovery-route proof and explicit approval.
- Use graphs from measured metadata to show Luke where the space pressure is, rather than raw folder lists.

## Graph Recommendations

Use measured data only. Do not invent values.

| Graph | Data source | X axis | Y axis | Why it helps |
|---|---|---|---|---|
| Storage by top-level family | data inventory | family | GB | Shows that `out/systems/` dominates storage |
| Systems storage by flow | data inventory | A/B/E/F/H/M/O/shared | GB and file count | Shows H is the first practical target |
| H staged run size over time | future H dry-run manifest | staged timestamp | MB per run | Shows repeated staging bulk and current/proof candidates |
| Likely duplicate space by family | duplicate report | family | GB | Separates major opportunities from small noise |
| Exact vs likely duplicates | duplicate report | proof type | MB or GB | Keeps proved duplicates separate from suspicion |
| Backup sets by age and size | future rollback report | backup timestamp | GB | Supports a recovery-safe keep-count decision |
| Housekeeping reports over time | inventory and future report manifest | report timestamp | MB | Shows whether control reports are growing too fast |

## Proposed Follow-Up Tickets

These are proposals only. They do not start work or approve protected actions.

| Proposed job_ref | Purpose | Safe boundary |
|---|---|---|
| `SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN` | Design the H staged owner-proof and dry-run manifest route | No deletion, movement, compression, purge, archive apply, or runtime change |
| `SO21-SCRIPT-HEALTH-REGISTER` | Create the plain-English script health table | Read-only; no Task Scheduler change |
| `SO21-OPERATIONS-RUNBOOK-AND-PROOF-MATRIX` | Create Luke-facing runbook and proof matrix | Planning/control only |
| `SO21-AUTOMATION-REGISTER-FINALISATION` | Consolidate active and paused control automations into one register | Read-only unless a separate automation packet approves changes |
| `SO21-ROLLBACK-KEEP-COUNT-POLICY` | Design backup retention without losing recovery | Planning only; needs recovery proof before any apply |

## Blockers Logged

No new Windows permission, locked-file, Task Scheduler access, credential, connector, machine-level, or protected-decision blocker appeared during this morning report.

Known earlier non-blocking issues remain recorded:

- Broad recursive checks can hit permission/time-out behavior in old temporary output folders.
- A compact PowerShell automation-list parser failed with a brace syntax error, then a simpler read-only parser succeeded.

Safest fix:

- Keep future control checks narrow, bounded, and read-only unless a packet explicitly approves a wider proof window.

## Operations Recommendation

Continue with review/proof tidy-up for the reports already created, then create the H staged retention dry-run design as the first storage follow-up. Do not implement cleanup or maintenance scripts from this report.

Recommended next operational step:

continue with SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN after reviewer confirms the morning reports are proposal-only
