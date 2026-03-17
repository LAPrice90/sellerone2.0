# Governance Audit

## GOVERNANCE FILE INVENTORY

| file path | current practical role | active / passive / ambiguous | overlap with project_control | recommendation |
| --- | --- | --- | --- | --- |
| `AGENTS.md` | Primary live instruction file for Codex behavior in this repo. Defines work rules, testing policy, work-log rules, ticket rotation, maintenance safety, and verification behavior. | Active | Yes | Keep as canonical for agent-operating rules unless and until its rules are deliberately migrated into `project_control/OPERATING_SYSTEM.md`. |
| `WORK_LOG.md` | Canonical append-only audit trail and state ledger for approved changes. Also carries carryover/next-task guidance. | Active | Yes | Keep as canonical for approved historical state and audit trail. Do not replace with `CURRENT_STATE.md`; instead keep `CURRENT_STATE.md` as summarized current snapshot later. |
| `NOTES.md` | Legacy backlog, future-job list, testing ideas, and partial checklist. Functions as an old task queue plus idea dump. | Ambiguous | Yes | Demote to reference-only, then later merge any still-valid actionable items into `project_control/TASK_QUEUE.md`. |
| `APP_PLAN.txt` | Legacy architecture/product/process manifesto. Contains system principles, module grouping, cadence, checklist, and user-interaction rules. | Ambiguous | Yes | Treat as reference-only source material for populating `PROJECT_BRIEF.md`, `ARCHITECTURE.md`, and `GUARDRAILS.md`. Do not keep it as a parallel active authority. |
| `cycle_recovery_plan_v1.md` | Specific operational recovery and hardening plan for B cycle. Functions like a scoped incident/recovery runbook. | Ambiguous | Partial | Keep as reference-only operational recovery plan unless promoted into a process guidebook or summarized in `CURRENT_STATE.md` / `DECISIONS.md`. |
| `README.md` | Minimal project label only. Does not currently govern behavior. | Passive | No | Leave passive or expand later as newcomer orientation only, not control authority. |
| `project_control/OPERATING_SYSTEM.md` | Intended new central operating model file, but currently empty heading only. | Ambiguous | N/A | Populate later and aim for it to become the narrative system-control file. For now it is not authoritative. |
| `project_control/PROJECT_BRIEF.md` | Intended repo-level purpose/scope file, currently empty heading only. | Ambiguous | N/A | Populate later; currently non-operative. |
| `project_control/ARCHITECTURE.md` | Intended architecture authority file, currently empty heading only. | Ambiguous | N/A | Populate later; currently not authoritative despite name. |
| `project_control/CURRENT_STATE.md` | Intended current-state summary file, currently empty heading only. | Ambiguous | N/A | Populate later as a summary layer, not as a replacement for `WORK_LOG.md`. |
| `project_control/TASK_QUEUE.md` | Intended canonical task queue, currently empty heading only. | Ambiguous | N/A | Populate later and use it to replace active task-planning use of `NOTES.md`. |
| `project_control/DECISIONS.md` | Intended architecture/operating decision register, currently empty heading only. | Ambiguous | N/A | Populate later with approved durable decisions currently trapped in chat or legacy plans. |
| `project_control/GUARDRAILS.md` | Intended explicit rules file, currently empty heading only. | Ambiguous | N/A | Populate later; likely best place for persistent repo rules that are broader than agent-only behavior. |
| `project_control/HANDOVER_TEMPLATE.md` | Intended handoff template, currently empty heading only. | Passive | N/A | Keep as support artifact only. |
| `project_control/PROMPT_WORKFLOW.md` | New workflow map for idea -> control files -> Codex task -> validation -> control-doc updates. | Active | N/A | Keep as active process guidance inside `project_control`, but subordinate to `AGENTS.md` until operating files are populated. |
| `project_control/DATA_LINEAGE_REPORT.md` | Investigative control artifact mapping data sources and dependencies. | Active | N/A | Keep as canonical reference for data-lineage analysis. |
| `project_control/SOURCE_AUTHORITY_REPORT.md` | Investigative control artifact classifying source-of-truth roles and duplicate truth layers. | Active | N/A | Keep as canonical reference for source authority decisions. |
| `project_control/CANONICAL_ENFORCEMENT_PLAN.md` | Phased cleanup plan for canonical path enforcement. | Active | N/A | Keep as canonical implementation planning reference for canonical-source cleanup work. |
| `scripts/cycles/H_PHASE1_INLINE_MODE_RUNBOOK.md` | Narrow process runbook for H inline mode operations and rollback. | Active | Partial | Keep as process-specific runbook, not repo-wide governance. Link from architecture/current-state later if needed. |
| `scripts/SCRIPTS.md` | Legacy script index and usage guide. Helps users locate runners and understand outputs. | Passive | Partial | Keep as reference-only script catalog. |
| `scripts/ONE_OFF_SCRIPTS.md` | Mapping/index for one-off scripts. | Passive | No | Keep as reference-only catalog. |
| `docs/REPORT_*.md` incident files | Point-in-time investigation reports about specific failures or warnings. | Passive | Partial | Keep as incident history/reference only. Not governance authority. |

## OVERLAP AND CONFLICT AREAS

### 1) Agent behavior authority split

- files involved: `AGENTS.md`, `project_control/OPERATING_SYSTEM.md`, `project_control/GUARDRAILS.md`, `project_control/PROMPT_WORKFLOW.md`
- type of conflict: active-vs-intended authority split
- risk: Codex currently receives concrete operating rules from `AGENTS.md`, while `project_control` contains the intended replacement structure but mostly empty files. This can cause false assumptions that governance has already moved when it has not.

### 2) State and history split

- files involved: `WORK_LOG.md`, `project_control/CURRENT_STATE.md`
- type of conflict: state ledger vs intended current-state summary
- risk: if `CURRENT_STATE.md` is later populated without a clear rule, users may treat it as the canonical state source and bypass the append-only audit in `WORK_LOG.md`.

### 3) Task selection overlap

- files involved: `NOTES.md`, `WORK_LOG.md` (`Next` / `Carryover`), `project_control/TASK_QUEUE.md`
- type of conflict: multiple task queues/backlogs
- risk: Codex or the user could select work from the wrong backlog. `AGENTS.md` already gives `WORK_LOG.md` carryover behavior, while `NOTES.md` acts like an older to-do list and `TASK_QUEUE.md` is the intended future queue.

### 4) Architecture and planning overlap

- files involved: `APP_PLAN.txt`, `project_control/PROJECT_BRIEF.md`, `project_control/ARCHITECTURE.md`, `project_control/GUARDRAILS.md`
- type of conflict: legacy architecture manifesto vs new structured control docs
- risk: `APP_PLAN.txt` still contains real principles and module planning, but the new control files that should replace it are mostly empty. That makes the legacy file still practically influential.

### 5) Operational recovery rule split

- files involved: `cycle_recovery_plan_v1.md`, `AGENTS.md`, `scripts/cycles/H_PHASE1_INLINE_MODE_RUNBOOK.md`, future `project_control/CURRENT_STATE.md` / `DECISIONS.md`
- type of conflict: operational runbook and recovery guidance spread across multiple files
- risk: incident handling may follow stale or partial instructions because the recovery rules are not gathered in one lane.

### 6) Process workflow overlap

- files involved: `project_control/PROMPT_WORKFLOW.md`, `AGENTS.md`
- type of conflict: workflow guidance vs binding agent rules
- risk: `PROMPT_WORKFLOW.md` suggests control-doc update flow, but `AGENTS.md` still controls what Codex must do in the repo. If they diverge later, Codex could follow the wrong procedural source.

### 7) Audit trail vs planning notes confusion

- files involved: `WORK_LOG.md`, `NOTES.md`, `APP_PLAN.txt`
- type of conflict: historical record mixed with future intent files
- risk: older plans or notes may be mistaken for current committed state, especially where `WORK_LOG.md` says it is the source of truth for system state.

### 8) Ambiguous practical status of new control system

- files involved: most of `project_control/` vs active legacy files
- type of conflict: structure exists, authority not yet migrated
- risk: the repo appears to have one coherent new control system, but in practice authority is still split across root files and new reports. This is the highest structural ambiguity right now.

## RECOMMENDED AUTHORITY HIERARCHY

Recommended top-down control order for the repo:

1. `AGENTS.md`
- Use as the binding agent-behavior and execution-rules source until a deliberate migration is completed.

2. `WORK_LOG.md`
- Use as the canonical approved state/audit trail.
- `Next` and `Carryover` remain subordinate to explicit user tickets, as already defined in `AGENTS.md`.

3. `project_control/OPERATING_SYSTEM.md`
- Intended future narrative operating model.
- Should become the main repo control summary once populated, but today it is not yet active enough to outrank `AGENTS.md`.

4. `project_control/PROJECT_BRIEF.md`
- Intended purpose/scope authority for what the system is trying to do.

5. `project_control/ARCHITECTURE.md`
- Intended canonical architecture description.

6. `project_control/DECISIONS.md`
- Intended durable decision register for approved structural choices.

7. `project_control/CURRENT_STATE.md`
- Intended concise current snapshot.
- Should summarize, not replace, `WORK_LOG.md`.

8. `project_control/TASK_QUEUE.md`
- Intended canonical queue for unapproved or upcoming work once populated.

9. `project_control/GUARDRAILS.md`
- Intended durable repo/system rules that are broader than Codex-only instructions.

10. Process-specific runbooks and incident docs
- `cycle_recovery_plan_v1.md`
- `scripts/cycles/H_PHASE1_INLINE_MODE_RUNBOOK.md`
- `docs/REPORT_*.md`
- These should be subordinate operational references, not top-level governance.

11. Legacy planning/reference docs
- `NOTES.md`
- `APP_PLAN.txt`
- `scripts/SCRIPTS.md`
- `scripts/ONE_OFF_SCRIPTS.md`
- These should be treated as reference-only unless their content is intentionally migrated upward.

## CONSOLIDATION RECOMMENDATIONS

### keep as canonical

- `AGENTS.md` for active Codex behavior rules
- `WORK_LOG.md` for approved state history and audit trail
- `project_control/DATA_LINEAGE_REPORT.md` for data-lineage reference
- `project_control/SOURCE_AUTHORITY_REPORT.md` for source authority reference
- `project_control/CANONICAL_ENFORCEMENT_PLAN.md` for canonical-source cleanup planning
- `project_control/PROMPT_WORKFLOW.md` as process guidance inside the new control system

### merge into another file

- Merge still-valid backlog items from `NOTES.md` into `project_control/TASK_QUEUE.md`
- Merge durable architecture/principle content from `APP_PLAN.txt` into `project_control/PROJECT_BRIEF.md`, `project_control/ARCHITECTURE.md`, and `project_control/GUARDRAILS.md`
- Merge durable operational decisions from `cycle_recovery_plan_v1.md` into `project_control/DECISIONS.md` or a future process-guidebook structure if they are still current

### demote to reference-only

- `NOTES.md`
- `APP_PLAN.txt`
- `cycle_recovery_plan_v1.md`
- `scripts/SCRIPTS.md`
- `scripts/ONE_OFF_SCRIPTS.md`
- `docs/REPORT_*.md`
- `scripts/cycles/H_PHASE1_INLINE_MODE_RUNBOOK.md` should remain active only as a flow-specific runbook, not repo-wide governance

### archive/deprecate later

- `NOTES.md` after actionable items are migrated into `project_control/TASK_QUEUE.md`
- `APP_PLAN.txt` after its still-valid principles are migrated into populated `project_control` files
- `cycle_recovery_plan_v1.md` after its active guidance is either superseded or folded into maintained process guidebooks

## High-risk ambiguity summary

- The highest-risk ambiguity is that `project_control/` looks like the new control system, but `AGENTS.md` and `WORK_LOG.md` still carry the only clearly active binding authority.
- `NOTES.md` and `WORK_LOG.md` both influence task selection today, while `TASK_QUEUE.md` exists but is empty.
- `APP_PLAN.txt` still contains live architectural and process principles, but the files that should supersede it are mostly placeholders.
- Without a declared migration rule, Codex can legitimately encounter multiple plausible instruction sources for planning, architecture, and work selection.

## FILES CREATED

- `project_control/GOVERNANCE_AUDIT.md`
