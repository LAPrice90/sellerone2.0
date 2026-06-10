# Response

## Status
- Running.

## Results
- Queue reset applied at `2026-04-23T15:17:26Z`.
- Queue order: `remaining-first`.
- Supplier: `stocklist_supplier`.
- Canonical rows: `42663`.
- Final queued rows: `37201`.
- Unprocessed rows placed first: `32872`.
- Already-scraped priority rows placed after unprocessed rows: `4329`.
- Processed rows excluded from queue remainder: `5462`.
- Archive directory: `out/systems/F/history/webscrape_resets/20260423T151726Z`.
- Reset report: `out/analysis_reports/f_webscrape_reset_plan_latest.csv`.

## Launch Proof
- Scanner wrapper started from `run_F_supplier_full_legacy_scan.bat stocklist_supplier`.
- Wrapper PID at startup: `27632`.
- F061 Python PID at startup: `11672`.
- Runtime log: `out/systems/F/live/f061_hometime.log`.
- Component log: `out/systems/F/live/f061_hometime_components.log`.
- First observed terminal checkpoints completed.
- Pending rows after startup proof: `37186`.
- Rows completed after startup proof: `15`.
- Latest run state: `running`.

## Guardrails
- No Google Sheets writes.
- No local DB alignment changes.
- No A scripts run.
- No B scripts run manually.
- No WORK_LOG update.
