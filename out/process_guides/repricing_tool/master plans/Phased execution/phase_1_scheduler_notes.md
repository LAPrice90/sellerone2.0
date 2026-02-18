# Phase 1 Scheduler Notes (H Pilot)

Use `scripts/bat/run_phase1_pilot_h_once.bat` for Task Scheduler.

## Recommended trigger
- Trigger type: Daily
- Advanced settings: Repeat task every `15 minutes`
- For a duration of: `Indefinitely` (or `1 day` with daily trigger)

## Required task settings
- Do not use overlapping runs:
- In Settings, set "If the task is already running" to `Do not start a new instance`.
- Disable "Stop the task if it runs longer than" (this often kills valid runs).
- Enable restart on failure:
- Restart every `1 minute`
- Attempt to restart up to `3 times`

## Program/action
- Program/script: full path to `scripts/bat/run_phase1_pilot_h_once.bat`
- Start in: repo root folder
- Run whether user is logged on or not
- Run with highest privileges if your environment needs protected network/env access

## Mode guidance
- Default safe startup:
- Add `--read-only` to the BAT command first day to validate without writes.
- Enable live writes only when config has `enabled_live_writes: true` and writer mode is `CODEX_H`.

## CPT and parked policy
- CPT calls are A-cycle only (`A016_refresh_phase1_daily_intel.py`).
- H-cycle must not call CPT endpoints directly.
- `out/phase1_sku_scope.csv` is the target source for H-cycle.
- SKUs with `parked_flag=1` are excluded from H targets and must remain no-write.

## Whole DB rollout sequence
1) Stage A - read-only soak:
- Set all SKUs to `READ_ONLY` in `config/phase1_writer_modes.csv`.
- Run normal A/B/H schedule.
- Require 10 consecutive runs with 0 FAIL before write enablement.

2) Stage B - controlled writes:
- Move a small approved batch to `CODEX_H`.
- Keep all other SKUs `READ_ONLY`.
- Expand only after each batch clears health checks.

3) Stage C - steady state:
- Keep dropped/discontinued and out-of-stock SKUs parked automatically.
- Keep H writes limited to non-parked, in-stock, `CODEX_H` SKUs.

## Recovery when intel coverage drops
- Check `out/phase1_sku_scope.csv` generation timestamp.
- Run A016 dry-run to confirm non-parked coverage counts.
- Review A015 checks:
- `a_daily_intel_coverage_non_parked`
- `a_daily_intel_compliance_nonempty_non_parked`
- `h_scope_non_parked_matches_targets`

## Lock behavior
- H runner uses `out/H_pricing_cycle.lock`.
- If lock exists and process is active, new launch exits (prevents double-run conflicts).

## Split health isolation (B vs H)
- H split mode env:
- `H_SPLIT_HEALTH_MODE=legacy|shadow|split` (default rollout `shadow`)
- `H_SPLIT_CHECKLIST_PATH=out/cycle_alerts/checklist_H_split.csv`
- `H_HEALTH_INTERVAL_SECONDS=900` (default)
- `H_HEALTH_FAIL_CLOSED=1` (default)
- B split mode env:
- `B_SPLIT_HEALTH_MODE=legacy|shadow|split` (default rollout `shadow`)
- `B_SPLIT_CHECKLIST_PATH=out/cycle_alerts/checklist_B_split.csv`
- Shared shadow tracking files:
- `out/cycle_alerts/split_shadow_compare.csv`
- `out/cycle_alerts/split_shadow_state.json`
- Cutover rule:
- when `split_shadow_state.json` has `ready_for_cutover=true`, both loops auto-switch effective mode from `shadow` to `split`.

## Locked H floor VAT policy
- Source of truth: `config/h_floor_vat_policy.json`.
- Current locked mode:
- `vat_registered=true`
- `recover_input_vat_on_cogs=true`
- `recover_input_vat_on_fees=true`
- Floor math rule:
- Remove output VAT from sale first.
- Compute floor on ex-VAT COGS and ex-VAT fees.
- Re-gross final required sale price at market VAT rate.
- Data source rule for H floor:
- Do not use `order_master.csv` for floor cost inputs.
- COGS source is token-first:
- `out/token_ledger_live.csv` next available token `cost_per_unit` (primary)
- `out/token_cogs_ledger.csv` median `cogs_exvat` (fallback)
- Fee inputs come from Product DB fee fields (`last_*` first, then standard fee fields).
- Health guardrails:
- `h_floor_vat_policy_config`
- `h_floor_phase1_cogs_basis_drift`

## Referral terminology and band lock
- In repricer language, `commission` means Amazon referral fee. They are the same charge.
- H floor referral source must stay in-band:
- Use `last_commission_pct_10` then `referral_fee_10` when candidate price `<= 10`.
- Use `last_commission_pct_100` then `referral_fee_100` when candidate price `> 10`.
- Never cross bands and never use `last_commission_pct` in H floor decisions.
- `h_floor_legacy_cogs_basis_drift`

## Terminology lock
- In this repricer context, `commission` and `referral fee` mean the same Amazon percentage fee.
- They are aliases, not separate charges.
- If user or logs say `commission`, interpret as `referral fee`.
