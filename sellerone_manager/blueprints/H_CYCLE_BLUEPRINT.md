# H Cycle Manager Blueprint

Last updated: 2026-05-27

## Plain-English Purpose

H is the live repricing runtime.

In simple terms, H is the pricing control room. It gathers the current product, stock, cost, ROI, and market picture, decides what price action is safe for the scoped SKUs, and leaves evidence showing what it decided, what it published, and whether the run ended cleanly.

The manager's job is not to repair repricing logic or run H freely. The manager's job is to make H independently inspectable from the outside before any repair work is allowed.

## Current Manager-Read State

H is parked as high-risk.

The old H checklist shows failure evidence, but that is only a smoke alarm. It is not final proof of the root cause, and it is not enough to justify random H repair.

Quiet Autonomy parks H repair until the independent H manager/MOT layer exists. The safe work now is planning and building the outside inspection layer only.

## What H Should Produce

H should produce:

- Repricing scope proof: which SKUs were considered and why.
- Market and offer proof: current offer snapshots, seller observations, and market context used by the repricer.
- Floor and ceiling proof: the safety rails H used before considering a price.
- Decision proof: what H decided for each SKU and why.
- Execution proof: whether a price write was needed, skipped, blocked, or applied.
- Publish proof: whether the H publish/finalizer step completed cleanly.
- Terminal proof: the latest run ended in a clear final state, not an ambiguous half-state.
- Runtime ownership proof: H has one owner, fresh heartbeat evidence, and no duplicate/stale owner conflict.
- Boundary proof: H to A016 and related finalizer handoffs are recorded without ambiguity.
- Health proof: H health output is present, readable, and consistent with the newer runtime evidence.
- Storage proof: staged H rollback/snapshot folders are capped and cleanup is only done at a safe H boundary.

## What Outside Proof Shows H Worked

H is manager-proven only when outside evidence shows:

- The latest H manifest exists and has a clear final state.
- Terminal evidence agrees with the manifest.
- Publish evidence exists when publishing is expected and says the publish step completed cleanly.
- Decision and execution outputs contain rows for the expected H scope.
- Required pricing safety fields are present and not blank.
- Market context rows are present enough to explain repricing decisions.
- Write-status values are explicit, such as applied, no write needed, read-only no write, or blocked.
- Lock and heartbeat proof show one active owner or a clean inactive boundary.
- No stale lock, duplicate owner, or ownership/finalization contradiction is visible.
- Boundary evidence explains whether H safely handed off or parked the next step.
- Health output matches the latest runtime truth instead of relying on older stale checklist evidence.

Think of this like checking a delivery lorry from the outside: the manager does not drive the lorry, but it can inspect the delivery note, the seal, the odometer, and the arrival time.

## What The Independent MOT Should Check Without Running H

The H MOT must be read-only. It should not run H, pause H, publish anything, change prices, edit queues, write Sheets, align DB data, delete outputs, or restart workers.

The first H MOT layer should check:

1. `h_latest_manifest_state`
   - Read the latest H manifest.
   - PASS when the latest run has a clear final state and run metadata is readable.
   - WARN when the manifest is stale but readable.
   - FAIL when missing, unreadable, or finalized state is contradictory.

2. `h_terminal_publish_truth`
   - Compare terminal proof and publish proof.
   - PASS when terminal and publish evidence agree.
   - FAIL when terminal says success but publish proof is missing, failed, or ambiguous.

3. `h_decision_execution_rows`
   - Check decision and execution outputs for rows and expected status labels.
   - PASS when rows exist and write-status values are explicit.
   - FAIL when rows are missing, blank, or contain unclear write-status values.

4. `h_market_context_proof`
   - Check market and offer evidence needed to explain repricing decisions.
   - PASS when current market context is present for the scoped run.
   - WARN when the proof is thin but not blocking.
   - FAIL when market context is missing for rows H attempted to price.

5. `h_floor_ceiling_safety_fields`
   - Check floor, ceiling, and safety rail fields.
   - PASS when required fields are present and populated.
   - FAIL when required safety fields are blank or malformed.

6. `h_lock_and_heartbeat_state`
   - Check H owner lock and heartbeat proof only.
   - PASS when one owner is fresh or no owner is present at a clean boundary.
   - WARN when the owner appears old but not yet contradictory.
   - FAIL when lock evidence is stale, duplicate, dead, or contradictory.

7. `h_boundary_finalizer_truth`
   - Check boundary/finalizer artifacts.
   - PASS when H clearly finalized or clearly parked the boundary.
   - FAIL when the boundary state is unresolved, mismatched, or hidden behind a generic failure.

8. `h_health_snapshot_as_clue`
   - Read the old H health/checklist output only as supporting evidence.
   - PASS only when it agrees with newer runtime proof.
   - WARN when old checklist evidence is stale.
   - FAIL only when the manager can tie the old alert to current outside proof.

9. `h_storage_cleanup_safety`
   - Check staged rollback/snapshot counts and cleanup proof.
   - PASS when the newest rollback snapshots are preserved and cleanup is registry-backed.
   - FAIL when cleanup proof is missing, unsafe, or would risk live/current data.

10. `h_manager_readiness`
   - Summarize whether H is inspectable enough for controlled repair.
   - PASS when the manager can explain H status from outside proof.
   - PARKED when proof exists but H is still waiting for controlled proof setup.
   - FAIL when the manager cannot tell whether H is safe.

11. `h_reliability_window`
   - Read recent H manifests without running H.
   - PASS when the last 10 comparable H run receipts have no failed or ambiguous run and at least 8 are clean.
   - WARN when fewer than 10 comparable runs exist or the window is warning-heavy but not failed.
   - FAIL when any run in the window has failed or ambiguous terminal proof.

## What Failure Creates A Bounded Worker Task

Create a bounded worker task only when the MOT finds a specific, repairable H gap.

Examples:

- Latest H manifest is missing, stale, unreadable, or has a vague final state.
- Terminal and publish evidence disagree.
- H claims a run ended cleanly but the publish marker is missing or failed.
- Decision or execution rows are missing, blank, or use unclear write-status labels.
- Required floor, ceiling, or safety fields are blank.
- Market context proof is missing for rows H attempted to price.
- Lock or heartbeat evidence suggests stale ownership, duplicate ownership, or a dead owner.
- Boundary/finalizer evidence does not explain whether H safely finished or parked.
- Last-10-run reliability evidence contains a failed or ambiguous H run.
- Health output conflicts with newer runtime evidence.
- Storage cleanup evidence is missing or would not protect rollback snapshots.

Each worker task must name the earliest source of the problem. It must not "pretty up" a downstream report to hide bad H data.

## What Needs Luke

Stop for Luke if the next step would involve:

- Changing prices.
- Editing queues.
- Writing Google Sheets.
- Pausing, resuming, or changing scheduler ownership.
- Aligning local DB data to make two sources match.
- Deleting outputs.
- Restarting workers.
- Running a live H cycle without an approved proof window.
- Expanding H scope beyond the approved manager/MOT planning task.
- Making a business decision from H evidence instead of only inspecting it.

## What Codex Can Do Without Asking Luke

Codex can safely:

- Maintain this H blueprint.
- Add H to the independent MOT as read-only checks.
- Map H expectations to outside proof categories.
- Create manager-approved worker task packets when read-only MOT evidence identifies a bounded repair.
- Improve manager wording so H status stays clear without dumping raw logs.

Codex cannot treat that as approval to repair H itself.

## Next Safe Setup Step

Add H read-only checks to the independent MOT, then let the manager classify H from those checks before any repair packet is considered.

First we build the H manager/MOT layer, then repairs become controlled.
