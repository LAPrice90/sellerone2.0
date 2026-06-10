# Plans

## Purpose

This folder is the durable memory for planning and executing repo work.

Use:
- `plans/active/` for live work
- `plans/archive/` for completed or frozen work
- `plans/templates/` for starter files

## Lanes

Use one system with two lanes:

### Build lane

Use for:
- new feature
- new extension
- new output

Start with:
- `PROJECT_BRIEF.md`
- `PLAN.md`
- `CODING_PLAN.md`
- `EXECUTION_BATCH_001.md`

### Debug lane

Use for:
- bug
- stale data
- missing update
- broken join
- wrong output

Start with:
- `INCIDENT_BRIEF.md`
- `CODING_PLAN.md` when the work spans phases or needs live proof
- `DEBUG_BATCH_001.md`

## Standard Flow

1. Create a new plan folder in `plans/active/`
2. Choose build lane or debug lane
3. Fill the brief, `PLAN.md`, and `CODING_PLAN.md` before phase execution
4. Fill the matching batch files
5. Store proof in `EXECUTION_BATCH_###_REPLY.md`
6. Move finished plans to `plans/archive/<year>/`

## Fast Start

Use:

```powershell
python scripts/one_off/P001_create_plan_workspace.py --slug my-plan-slug
```

That creates a ready-to-fill plan folder with both build and debug templates.
