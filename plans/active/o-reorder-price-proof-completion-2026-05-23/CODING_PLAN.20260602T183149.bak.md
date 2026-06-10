# O Reorder Price-Proof Completion Plan

Created UTC: 2026-05-23T13:10:13Z
Owner flow: O with read-only H market-proof dependency
Status: H maintenance controller built; automation install blocked by Windows elevation policy

## Plain-English Goal

Finish the Reorder proof layer so each row can answer three operator questions before a PO draft is made:

- What is the current supplier list cost?
- What do we usually pay?
- What is the highest safe cost before the profit check says stop?

The next proof step is a read-only listing-offer scan for the 59 queued restock candidates. That scan must not run while the H pricing cycle is actively refreshing the same market files.

## Phase Status

| Phase | Goal | Status | Proof |
|---|---|---|---|
| 1 | Add price-proof fields, paid-cost profiles, UI chips, hover details, and over-max guards | completed | targeted tests passed |
| 2 | Add O market-refresh candidate bridge | completed | 59 candidates written; ABGee 8 ready; proof folder written |
| 3 | Add candidate-only API listing-offer scan mode | completed | targeted tests passed |
| 4 | Pause H, run candidate-only read-only listing-offer scan, rebuild E/O | blocked | Luke approved proof window 2026-05-27T14:46:33Z; pause still requires elevated PowerShell |

## Completed Evidence

- `restock_market_refresh_candidates_live.csv` has 59 ready candidates.
- ABGee has 8 candidates ready for market refresh.
- `12-749B-9EB5` is queued with ASIN `B084HZRR8G`.
- Tests passed:
  - `python -m pytest tests/test_run_api_collection_restock_candidates.py tests/test_phase1_sku_scope.py tests/test_o021_restock_profit_checks.py -q`
  - result: 11 passed

## Current Blocker

H is active and owns the listing-offer/market snapshot files. Luke approved the controlled pause/proof window on 2026-05-27.

Latest isolation status at 2026-05-23T13:09:48Z:

- H run: `20260523T130747Z`
- H mode: `RUNNING`
- H stage: `phase1_pilot`
- Admin status: `false`

Attempted command:

```powershell
.\run_H_isolation_pause.bat
```

Result:

```text
pause requires elevation. Re-run from elevated PowerShell or cmd (Run as administrator).
```

## 2026-05-27 Controlled Proof Window Update

- Approved by Luke at 2026-05-27T14:46:33Z.
- Forced proof planner result: H proof window status is `pause_required`.
- Current H owner evidence at approval: H lock run `20260527T144229Z`, pid `25300`, heartbeat `2026-05-27T14:46:34Z`.
- O market queue evidence at approval: 59 ready restock candidates.
- Codex-owned sequence:
  1. Request H isolation pause with `run_H_isolation_pause.bat`.
  2. If pause succeeds, create timestamped backups of listing-offer files and O/E proof outputs.
  3. Run candidate-only read-only listing-offer collection for 59 O restock candidates.
  4. Rebuild only the local E/O proof chain needed for restock price proof.
  5. Verify candidate coverage, including `12-749B-9EB5`.
  6. Resume H ownership and confirm ownership restoration.
  7. Write proof under `out/systems/O/history/`.
- Stop condition: if Windows elevation blocks the pause, stop and require Luke to run the pause from an elevated PowerShell. Do not run the scan while H owns market files.

## 2026-05-27 Pause Attempt After Approval

- Codex checked H isolation status at 2026-05-27T14:47:13Z.
- H was still active: run `20260527T144229Z`, stage `phase1_pilot`, runtime mode `RUNNING`.
- Codex attempted `run_H_isolation_pause.bat`.
- Result: blocked because the pause requires elevated PowerShell/admin rights.
- Current status: approved proof window remains parked until Luke runs the elevated pause.
- Resume trigger: Luke runs `run_H_isolation_pause.bat` as Administrator and returns with `H is paused`.
- Success condition before Codex continues: H controlled mode is active and the normal H owner is paused before the 59-row read-only market scan starts.

## 2026-05-27 H Maintenance Controller Build Plan

Luke asked how maintenance can be automated if Codex cannot directly run elevated pause actions. The approved build response is an admin-gated maintenance controller:

- Codex may write a bounded H maintenance request file.
- A one-time Administrator install creates a Windows scheduled task that runs the controller with highest privileges.
- The controller may only call the existing H isolation script for `status`, `pause`, or `resume`.
- The controller must write proof JSON after each request.
- The controller must not write Google Sheets, prices, queues, purchase orders, receiving events, Amazon handoffs, or local DB facts.

Allowed files for this controller phase:

- `scripts/tools/h_maintenance_controller.ps1`
- `scripts/tools/install_h_maintenance_controller.ps1`
- `scripts/one_off/H200_request_h_maintenance.py`
- optional small `.bat` wrappers at repo root
- focused tests for request-file validation
- this coding plan

Proof for this phase:

- Python request helper compiles.
- Request-helper tests pass.
- PowerShell controller parses in dry-run/status mode without touching live H controls.
- No pause, resume, market scan, PO, receiving, Amazon handoff, Sheet write, price change, queue edit, DB alignment, or output deletion is performed by this build step.

## 2026-05-27 H Maintenance Controller Build Result

Built files:

- `scripts/tools/h_maintenance_controller.ps1`
- `scripts/tools/install_h_maintenance_controller.ps1`
- `scripts/one_off/H200_request_h_maintenance.py`
- `run_H_maintenance_controller_install.bat`
- `tests/test_h_maintenance_request_helper.py`
- O MOT controller gate in `sellerone_manager/hourly_mot.py`

Verification:

- `python -m py_compile scripts\one_off\H200_request_h_maintenance.py` passed.
- `python -m py_compile sellerone_manager\hourly_mot.py scripts\one_off\H200_request_h_maintenance.py` passed.
- `python -m pytest tests\test_h_maintenance_request_helper.py tests\manager\test_hourly_mot.py -q` passed: 53 tests.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tools\h_maintenance_controller.ps1 -Root . -StatusOnly -DryRun` passed and wrote status proof without pausing or resuming H.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tools\install_h_maintenance_controller.ps1 -Root .` refused from non-admin with `administrator_required`, proving the installer is admin-gated.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O` passed with 0 fails. O now reports `o_h_maintenance_controller_gate=decision_needed` because the one-time Administrator install has not happened yet, and `o_h_market_proof_gate=warn` because Luke already approved the controlled proof packet but H still owns the market files.

Current boundary:

- The controller is not installed yet.
- H has not been paused.
- The 59-row O market-proof scan has not run.
- Next proof trigger: a Codex-owned automation retries/monitors controller setup and only proceeds when a safe elevated controller exists.

## 2026-05-27 Automation Install Attempt

Luke clarified this should be automation-owned, not a manual task.

Codex changed the installer so it attempts scheduled-task registration instead of refusing immediately when the shell is not elevated.

Result:

- First automated install attempt found a PowerShell compatibility issue in the task settings call.
- Codex fixed the settings call and retried.
- Second automated install attempt reached the real platform boundary: Windows returned `Access is denied` while registering the `Highest` privilege scheduled task from the non-elevated Codex session.
- O MOT now reports `warn`, not `decision_needed`, for this controller gate. This is treated as an automation-platform blocker, not a Luke business decision.

Automation-owned next step:

- A recurring Codex automation should run the O MOT, retry or inspect controller setup, and keep the blocker visible without asking Luke to run commands.
- It must not pause H, run market proof, write Sheets, change prices, edit queues, align DB facts, create POs, receive stock, send to Amazon, or delete outputs unless the elevated controller becomes proven and the approved proof packet still applies.

Automation created:

- App automation id: `o-h-maintenance-automation`
- Schedule: hourly
- Scope: O MOT, H controller install/status proof, coding-plan update
- Hard stop: no H pause/resume or market scan until the elevated controller is proven installed and a bounded proof packet explicitly allows the next step.

## 2026-05-27 User-Working Readiness Gate

Added the O MOT gate `o_user_working_readiness`.

This gate answers today's practical question: can O be worked on with Luke as a user-facing mid-build system without opening real buying actions?

The gate is allowed to pass with non-user warnings such as H controller automation or H market-file ownership. It fails if any built safety or UI proof is missing, if O claims completion, or if buy/PO/receiving/send guardrails are unsafe.

Next safe packet:

- `plans/active/o-reorder-price-proof-completion-2026-05-23/O_USER_WORKING_PACKET_20260527.md`

Verification:

- `python -m py_compile sellerone_manager\hourly_mot.py` passed.
- `python -m pytest tests\manager\test_hourly_mot.py tests\test_o_ui_operator_view.py tests\test_o410_product_database_ui.py tests\test_o420_product_database_edit_ui.py -q` passed: 146 tests.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O` passed with 0 fails and 2 warnings.
- Live O readiness result: `o_user_working_readiness=ok`.
- Live proof detail: 659 Product DB operator rows, 0 buy-ready rows, and 2 tolerated non-user warnings for H controller automation and H market-proof ownership.

## 2026-06-01 Expected Restock Profit Research

Read-only research was run against order, refund, fee, transaction, inbound-cost, SKU performance, and O proof files.

Research artifact:

- `plans/active/o-reorder-price-proof-completion-2026-05-23/O_EXPECTED_RESTOCK_PROFIT_RESEARCH_20260601.md`

Plain-English conclusion:

- O should not trust expected profit until refund drag and inbound/FBA-send cost are modelled as explicit proof fields.
- Current O refund fields exist but are zero for all rows, while refund transaction evidence exists.
- Current inbound cost events exist, but no SKU allocation exists yet.
- Next safe build is a read-only expected-profit input model, not PO, receiving, send-to-Amazon, market-scan, Sheet, price, queue, or DB work.

## Automatic Next Step After Controller Exists

After the elevated H controller is proven installed, Codex should:

1. Create a timestamped backup of the listing-offer files and O/E proof outputs.
2. Run candidate-only read-only listing-offer collection:

```powershell
$env:API_COLLECTION_DATASETS='listing_offer'
$env:API_COLLECTION_LISTING_BASE_MODE='restock_candidates'
$env:API_COLLECTION_RESTOCK_CANDIDATE_LIMIT='59'
python run_api_collection.py
```

3. Verify the collection covers the queued candidate SKUs, including `12-749B-9EB5`.
4. Rebuild the safe local E/O proof chain only.
5. Verify Reorder now has native Max pay / market proof where data is available.
6. Resume H with:

```powershell
.\run_H_isolation_resume.bat
```

7. Record a proof file under `out/systems/O/history/`.

## Guardrails

- Do not write to Google Sheets.
- Do not run O010 or O100 as part of this price-proof rebuild.
- Do not send anything to Amazon.
- Do not mark receiving.
- Do not overlap a manual listing-offer scan with active H ownership.
- If a row remains missing native market proof after the scan, keep it visible as `check price`, not a clean buy.

## Success Criteria

- H is paused before the read-only scan starts.
- Listing-offer scan runs only against the 59 O restock candidates.
- `12-749B-9EB5` either receives native market proof and Max pay, or stays blocked with a plain missing-data reason.
- Reorder shows price proof in compact chips and hover details, not long robot notes.
- H ownership is resumed after the proof.

## 2026-05-27 O/H Maintenance Automation Run

Automation ID: `o-h-maintenance-automation`
Observed UTC: 2026-05-27T16:17:54Z

What happened:

- O MOT was run before the install retry and reported 0 fails and 0 warnings.
- The H maintenance controller install proof still said `installed=false`, `success=false`, and `failure_reason=scheduled_task_registration_failed`.
- The automation made the one allowed installer attempt with `scripts\tools\install_h_maintenance_controller.ps1 -Root .`.
- Windows again blocked highest-privilege scheduled task registration from the non-admin Codex session with `Access denied`.
- O MOT was rerun after the install attempt and again reported 0 fails and 0 warnings.

Current result:

- H maintenance controller is not installed.
- The O/H market-proof lane remains parked under Quiet Autonomy.
- No H pause or resume was requested.
- No market proof scan was run.
- No Google Sheets, price, queue, local DB, PO, receiving, Amazon handoff, or output-deletion action was performed.

Next trigger:

- Continue hourly automation inspection of the same controller proof and O MOT artifacts.
- If a future run proves the controller installed cleanly, use only the bounded `status` probe first, then rerun O MOT before any further proof-window step.

## 2026-05-27 O/H Maintenance Automation Run 2

Automation ID: `o-h-maintenance-automation`
Observed UTC: 2026-05-27T17:19:27Z

What happened:

- O MOT was run before the install retry and reported 0 fails and 0 warnings.
- The H maintenance controller install proof still said `installed=false`, `success=false`, and `failure_reason=scheduled_task_registration_failed`.
- The automation made the one allowed installer attempt with `scripts\tools\install_h_maintenance_controller.ps1 -Root .`.
- Windows again blocked highest-privilege scheduled task registration from the non-admin Codex session with `Access denied`.
- O MOT was rerun after the install attempt and again reported 0 fails and 0 warnings.

Current result:

- H maintenance controller is not installed.
- The O/H market-proof lane remains parked under Quiet Autonomy.
- No H pause or resume was requested.
- No market proof scan was run.
- No Google Sheets, price, queue, local DB, PO, receiving, Amazon handoff, or output-deletion action was performed.

Next trigger:

- Continue hourly automation inspection of the same controller proof and O MOT artifacts.
- If a future run proves the controller installed cleanly, use only the bounded `status` probe first, then rerun O MOT before any further proof-window step.

## 2026-05-27 O/H Maintenance Automation Run 3

Automation ID: `o-h-maintenance-automation`
Observed UTC: 2026-05-27T18:20:34Z

What happened:

- O MOT was run before the install retry and reported 0 fails and 0 warnings.
- The H maintenance controller install proof still said `installed=false`, `success=false`, and `failure_reason=scheduled_task_registration_failed`.
- The automation made the one allowed installer attempt with `scripts\tools\install_h_maintenance_controller.ps1 -Root .`.
- Windows again blocked highest-privilege scheduled task registration from the non-admin Codex session with `Access denied`.
- O MOT was rerun after the install attempt and again reported 0 fails and 0 warnings.

Current result:

- H maintenance controller is not installed.
- The O/H market-proof lane remains parked under Quiet Autonomy as an automation-platform blocker.
- No H pause or resume was requested.
- No market proof scan was run.
- No Google Sheets, price, queue, local DB, PO, receiving, Amazon handoff, or output-deletion action was performed.

Next trigger:

- Continue hourly automation inspection of the same controller proof and O MOT artifacts.
- If a future run proves the controller installed cleanly, use only the bounded `status` probe first, then rerun O MOT before any further proof-window step.

## 2026-05-27 O/H Maintenance Automation Run 4

Automation ID: `o-h-maintenance-automation`
Observed UTC: 2026-05-27T19:22:03Z

What happened:

- O MOT was run before the install retry and reported 0 fails and 0 warnings.
- The H maintenance controller install proof still said `installed=false`, `success=false`, and `failure_reason=scheduled_task_registration_failed`.
- The automation made the one allowed installer attempt with `scripts\tools\install_h_maintenance_controller.ps1 -Root .`.
- Windows again blocked highest-privilege scheduled task registration from the non-admin Codex session with `Access denied`.
- O MOT was rerun after the install attempt and again reported 0 fails and 0 warnings.

Current result:

- H maintenance controller is not installed.
- The O/H market-proof lane remains parked under Quiet Autonomy as an automation-platform blocker.
- No H pause or resume was requested.
- No market proof scan was run.
- No Google Sheets, price, queue, local DB, PO, receiving, Amazon handoff, or output-deletion action was performed.

Next trigger:

- Continue hourly automation inspection of the same controller proof and O MOT artifacts.
- If a future run proves the controller installed cleanly, use only the bounded `status` probe first, then rerun O MOT before any further proof-window step.

## 2026-05-27 O/H Maintenance Automation Run 5

Automation ID: `o-h-maintenance-automation`
Observed UTC: 2026-05-27T20:22:20Z

What happened:

- O MOT was run before the install retry and reported 0 fails and 0 warnings.
- The H maintenance controller install proof still said `installed=false`, `success=false`, and `failure_reason=scheduled_task_registration_failed`.
- The automation made the one allowed installer attempt with `scripts\tools\install_h_maintenance_controller.ps1 -Root .`.
- Windows again blocked highest-privilege scheduled task registration from the non-admin Codex session with `Access denied`.
- O MOT was rerun after the install attempt and again reported 0 fails and 0 warnings.

Current result:

- H maintenance controller is not installed.
- The O/H market-proof lane remains parked under Quiet Autonomy as an automation-platform blocker.
- No H pause or resume was requested.
- No market proof scan was run.
- No Google Sheets, price, queue, local DB, PO, receiving, Amazon handoff, or output-deletion action was performed.

Next trigger:

- Continue hourly automation inspection of the same controller proof and O MOT artifacts.
- If a future run proves the controller installed cleanly, use only the bounded `status` probe first, then rerun O MOT before any further proof-window step.
