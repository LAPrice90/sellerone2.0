# E Manager Proof Coverage Package

## 1. Package Status

- Manager task packet: `sellerone_manager/tasks/approved/MGR_E_proof_gap_project_control_EXPECTAT.md`
- Task type: manager task packaging only
- Luke decision needed: no
- Protected boundary hit: no
- Worker run performed: no
- Code edited: no
- Sheets, pricing, queues, local DB alignment, publish enablement, and output deletion: not touched

This package is only a proof map. It is like a checklist for the inspector: it says which parts of E already have manager-readable proof, which parts are still missing proof, and exactly where a future verifier should look.

## 2. Evidence Read

- `project_control/EXPECTATIONS/E_cycle_expectations.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `out/systems/M/flow_expectation_reconciliation.csv`
- `out/systems/M/flow_maintenance_state.csv`
- `out/systems/M/manager_task_candidates.csv`
- `out/systems/M/approved_task_packets.csv`
- `out/systems/E/live/e_run_log.jsonl`
- `out/cycle_alerts/checklist_E.csv`
- `out/cycle_alerts/checklist_E_split.csv`
- `out/sku_sales_velocity.csv`
- `out/sku_roi_snapshot.csv`
- `out/sku_restock_signals.csv`
- `out/sku_performance_summary.csv`
- `out/e_study_report.csv`

Latest manager reconciliation observation read:

- Observed UTC: `2026-05-27T07:07:35Z`
- Flow: E
- Manager state: `ok`
- Classification: `calm`
- Active FAIL count: `0`
- Active WARN count: `0`
- Stale evidence count: `0`
- Covered expectations: `7`
- Total expectations: `9`
- Not verified count: `2`
- Proof rule: use E-owned run logs and E-scoped health; keep E proof separate from global health.

Latest E runtime evidence read:

- Last E run id: `20260527T052628458951Z`
- Last E run finished UTC: `2026-05-27T05:27:03.422440+00:00`
- Last E run status: `success`
- Last 10 completed E runs in the run log: `10`
- Last 10 completed E runs with status success: `10`
- Last run task list: `E001_build_sales_velocity.py;E002_build_roi_snapshot.py;E003_build_restock_signals.py;E004_build_performance_summary.py;E005_build_study_report.py;E006_build_sales_truth_reconciliation.py;E007_build_sku_daily_sales_truth.py;A015_build_system_health_check.py:profile=e`
- Last expected input as-of: `2026-05-27`
- Last output as-of: `2026-05-27`
- Last as-of rerun trigger: `1`

Latest E scoped checklist evidence read:

- `out/cycle_alerts/checklist_E.csv`: 23 rows, 23 ok, 0 fail, 0 warn
- `out/cycle_alerts/checklist_E_split.csv`: 23 rows, 23 ok, 0 fail, 0 warn
- Note: the split checklist text showed an E lock path in the notes, but the status was still `ok`, and the later E checklist was also `ok`. This package does not inspect or alter locks.

Latest core E output files read:

| Output | Rows | Last write UTC |
|---|---:|---|
| `out/sku_sales_velocity.csv` | 483 | `2026-05-27T05:26:29.4639641Z` |
| `out/sku_roi_snapshot.csv` | 44 | `2026-05-27T05:26:31.4656916Z` |
| `out/sku_restock_signals.csv` | 161 | `2026-05-27T05:26:32.1423110Z` |
| `out/sku_performance_summary.csv` | 161 | `2026-05-27T05:26:34.7146196Z` |
| `out/e_study_report.csv` | 161 | `2026-05-27T05:26:35.3901255Z` |

## 3. Covered E Expectations

These expectations are already covered by manager-readable evidence. In plain English, the manager can already point to a file or health check for these.

| E expectation | Manager status | Evidence currently mapped |
|---|---|---|
| E cycle runner | covered | `e_cycle_stale_lock` in E scoped health |
| Sales velocity output | covered | `e_schema_sales_velocity` |
| ROI snapshot output | covered | `e_schema_roi_snapshot`, country split ROI schema checks, and ROI truth checks |
| Restock signal output | covered | `e_schema_restock_signals` |
| Performance summary output | covered | `e_schema_performance_summary`, ROI alignment, and study report alignment checks |
| Study report output | covered | `e_schema_study_report`, freshness versus summary, and truth alignment checks |
| Health profile evidence | covered | E scoped health profile evidence, recorded as `A015_build_system_health_check.py:profile=e` in the E-owned run log |

The current evidence says the main E factory line is producing its normal tables, and the manager can read those proofs without using global health as a shortcut.

## 4. Not Verified E Expectations

These expectations remain `not_verified` because the manager does not yet have a specific proof hook mapped to them.

| E expectation | Current status | Why it is not verified |
|---|---|---|
| Cadence control | not_verified | The expectations file says the orchestrator has cadence skip/run behavior, and the run log contains fields that appear useful for this, such as `expected_input_asof`, `output_asof`, and `asof_rerun_trigger`. However, the manager reconciliation does not yet map a named manager check to cadence behavior. |
| Optional publishing path | not_verified | The expectations file says `E010` exists with gated sheet writes, but no manager-readable evidence is mapped for the publish gate, disabled state, or safe publish behavior. Because publish enablement is forbidden in this task, this package only records the proof gap. |

These are proof-coverage gaps, not active runtime failures. The current manager state shows 0 active E FAIL, 0 active E WARN, and 0 stale E evidence.

## 5. Exact Future Proof Path For E

Do not run E now for this package. The future proof path should use the next normal E-owned run, or a separately approved E-owned proof window.

The proof path is:

1. Wait for the next E-owned completed run, or use a separately approved E-owned proof window.
2. Read `out/systems/E/live/e_run_log.jsonl`.
3. Find the newest completed row after the proof start time.
4. Confirm the newest row has:
   - `status` = `success`
   - a nonblank `finished_utc`
   - `tasks_run` includes E001 through E007
   - `tasks_run` includes E scoped health, not only global health
5. Confirm the core E outputs are refreshed by that run:
   - `out/sku_sales_velocity.csv`
   - `out/sku_roi_snapshot.csv`
   - `out/sku_restock_signals.csv`
   - `out/sku_performance_summary.csv`
   - `out/e_study_report.csv`
6. Read the E scoped checklist only after the run has finished:
   - `out/cycle_alerts/checklist_E.csv`
   - `out/cycle_alerts/checklist_E_split.csv`
7. Confirm E scoped health has:
   - 0 FAIL
   - 0 WARN, unless a named non-blocking exception is recorded elsewhere
   - no stale-output condition
8. For cadence control proof, manager evidence should confirm the cadence decision in plain terms:
   - run was needed and E ran, or
   - run was not needed and E skipped safely
   - the reason is visible from E-owned evidence, such as as-of fields or a dedicated cadence check
9. For optional publishing proof, manager evidence should confirm the publish gate in plain terms:
   - publish disabled and no Sheet write attempted, or
   - publish enabled only under separate approval and staged safely
   - no legacy Sheet write happens by default

The success condition for this package's future retest is simple:

- E manager reconciliation changes from 7 of 9 covered to 9 of 9 covered, or
- the two remaining items stay `not_verified` with named follow-up tasks that explain exactly what manager-readable evidence is missing.

## 6. Safe Future Task Candidates

No worker repair task is needed right now. The current evidence points to missing manager proof mapping, not broken E output behavior.

Safe future task candidates, only if a later manager retest still cannot verify the two open expectations:

| Candidate | Scope | Protected boundary |
|---|---|---|
| Add E cadence proof mapping | Add or confirm a manager-readable check that maps E cadence skip/run behavior to the `Cadence control` expectation. Prefer existing E-owned run log fields before changing worker code. | No worker run, no publish enablement, no Sheets. |
| Add E publish gate proof mapping | Add or confirm a manager-readable check that proves E optional publishing is gated, disabled by default, and never using legacy Sheet write unless explicitly approved. | No publish enablement, no Sheet write, no E010 execution unless separately approved. |

Only create a true worker repair task if the future proof shows the E runner cannot write the required cadence or publish-gate evidence from its own normal path.

## 7. Stop Conditions

Stop immediately if any of these occur:

- The task requires running E now.
- The task requires editing worker code.
- The task requires enabling publish.
- The task requires any Sheet write.
- The task requires changing pricing.
- The task requires editing queues.
- The task requires local DB alignment.
- The task requires deleting outputs.
- The task requires editing `out/systems/M/approved_task_packets.csv`.
- The task requires changing manager task status.
- The root cause changes from proof mapping to active E runtime failure.
- E scoped health shows a new FAIL or WARN that blocks the package conclusion.

## 8. Forbidden Actions

The following actions are forbidden for this package:

- Do not run E scripts.
- Do not run worker cycles.
- Do not run publish enablement.
- Do not run A015.
- Do not write to Google Sheets.
- Do not change pricing.
- Do not change queues.
- Do not align local DB to another source.
- Do not delete outputs.
- Do not edit code.
- Do not edit `approved_task_packets.csv`.
- Do not edit manager task status.
- Do not use global health as the proof for E when E scoped proof is available.

## 9. Manager Conclusion

Luke does not need to make a decision for this package.

E currently has manager-readable proof for 7 of 9 expectations. The two remaining gaps are cadence control and optional publishing path, and both are missing proof mapping rather than showing an active E failure. The next safe move is to let a future approved manager retest map those two expectations to E-owned evidence without crossing protected boundaries.
