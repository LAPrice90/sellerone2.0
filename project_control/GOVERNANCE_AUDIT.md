# Governance Audit

Audit timestamp: 2026-05-01T14:22Z

Update timestamp: 2026-05-01T22:09Z

Post-audit update:

- Product DB target authority is now SQL, edited through the UI.
- Local SQL Product DB proof has 659 rows and 659 unique `seller_sku`; O Product DB operator view has 659 rows.
- Legacy `out/product_db_preview.csv` is currently stale at 608 rows and is classified by P018 as `mirror_stale_not_authority`.
- Current H runtime proof has 0 blank and 0 invalid `execution_write_status` rows on terminal run `20260501T215343Z`. Stale `out/pricing_output.csv` still contains historical blank rows and is audit-only until refreshed or retired through an approved export path.
- Repricer tracker UI parity proof P017 is `ready_with_stale_audit_warning`, with 0 missing critical fields; the Sheet remains temporary fallback until explicit operator cutover.
- SQL Product DB / repricer tracker UI authority Phase 2 is locally complete with P021 status `complete_locally_pending_explicit_cutover_approvals`, `fail_count=0`, and `warn_count=0`.

## Summary

This audit found real proof for F scanner, Product DB snapshots, E ROI analytics, H pricing runtime, B ownership, and O Product DB operator view. It also found schema and health gaps that should not be hidden.

## Systems With No Clear Current Output Proof

| System / area | Evidence | Status |
|---|---|---|
| External Google Sheets writes | Sheet-writing scripts exist in A, B, E publish, H publish, and tools, but no audit-run Sheet write was performed | NOT VERIFIED |
| H scheduler task export | Runtime docs and tools reference `AMZ H Cycle`; no XML export found in `config/scheduler/` | NOT VERIFIED |
| B scheduler task export | Runtime docs and tools reference `AMZ Orders`; no XML export found in `config/scheduler/` | NOT VERIFIED |
| A latest owner run | A scripts and health outputs exist, but no A-owned run was executed during this audit | NOT VERIFIED |
| C/D older flows | Scripts exist under `scripts/flows/C` and `scripts/flows/D`; they are not in `config/runtime_owner_contract.json` | NOT VERIFIED |
| External BBP/web scrape availability | F scanner evidence exists, but no separate external availability smoke test was run | NOT VERIFIED |

## Scripts With No Clear Owner Role

- `run_api_collection.py` exists at repo root but is not in `config/runtime_owner_contract.json`.
- `scripts/flows/C/*` and `scripts/flows/D/*` contain runnable scripts but have no current runtime owner contract entry.
- `scripts/one_off/` contains 101 source-inventory entries; these must stay one-off and out of daily loops.
- Legacy F scanner modules under `scripts/flows/F/legacy_scanner_2_1/` are still active through F061, but should not become separate owner entrypoints.
- Root batch files for H isolation, owner audit, home-time monitor, and supplier test scans are operational helpers, not core daily owners.

## Broken Or Risky Pipelines

| Pipeline | Evidence | Risk |
|---|---|---|
| Product DB schema | `out/db_snapshot.csv` has duplicate header `last_updated_A003` inherited from source | CSV readers can fail or silently mangle columns |
| Product DB ASIN uniqueness | duplicate ASINs `0786964502`, `B07RRQX71T`, `B09NQ9ZHDQ` | ASIN-based linking can map one product to multiple rows |
| Scanner identity uniqueness | duplicate scanner ASIN `B0DPMGDZLZ` | new-product review may double count one product |
| Scanner to DB link | `out/link_check.csv` shows 50 scanner ASINs and all 50 are `New` | Could be correct new-product flow or missing DB linkage; needs operator decision |
| B token health | `out/cycle_alerts/checklist_B.csv` has FAIL `token_shortages_by_sku=6` | B is running but not clean |
| Aggregate health freshness | `out/system_health_checklist.csv` is from 2026-05-01T05:10:08Z and shows H freshness FAIL rows that are stale relative to later H terminal evidence at 2026-05-01T14:20:11Z | Health output is truthful but not the newest runtime truth |
| Pricing output completeness | `out/pricing_output.csv` has 20 rows with blank `execution_write_status` | Pricing proof is real, but not fully normalized |

## Duplicate Or Conflicting Logic

- Product DB authority is split across Google Sheet `Product_DB`, `out/product_db_preview.csv`, SQLite table `sys_product_db_preview`, and O Product DB operator outputs.
- H has both legacy root outputs and `out/systems/H/live/` outputs. Current architecture should prefer systems-live owner artifacts for runtime truth.
- F has a modern price-list manager plus legacy scanner modules. The legacy modules are still used by F061 and should stay inside that owner chain.
- A/B/E/H health and output proof are partly split between aggregate health files and flow-scoped checklists.
- Wrapper scripts exist both at root and under `scripts/` for some cycles. The owner contract should define which path is approved.

## Missing Validation Points

- Product DB schema validation must detect duplicate headers before downstream readers load the file.
- Product DB linking needs a no-write insert/update test path.
- Scanner needs an ASIN duplicate and supplier SKU duplicate gate.
- H pricing proof needs a compact status summary with write status counts and blank-status detection.
- Scheduler ownership should have exported evidence for all active Windows tasks, not just `AMZ Price List Manager`.
- External integrations need read-only smoke tests that cannot write Sheets or submit Amazon changes.

## Output Visibility Created

| Output | Rows | Source |
|---|---:|---|
| `out/scanner_latest.csv` | 51 | `out/systems/F/live/feeder_legacy_first_checks_live.csv` |
| `out/db_snapshot.csv` | 608 | SQLite table `sys_product_db_preview` |
| `out/link_check.csv` | 50 | scanner ASINs compared to Product DB ASINs |
| `out/pricing_output.csv` | 89 | `out/phase1_runtime_floor_snapshot_latest.csv` merged with ROI snapshot |
| `project_control/SCRIPT_INVENTORY.csv` | 675 | root entrypoints, `scripts/`, `tests/`, scheduler config |

## Governance Recommendation

Keep the control layer as evidence-first:

- Use owner locks and terminal markers for live runtime truth.
- Use flow-scoped health for flow decisions.
- Treat aggregate health older than newer runtime proof as stale context, not current confirmation.
- Do not patch downstream exports to hide source schema problems.
- Do not use one-off scripts inside daily loops.
