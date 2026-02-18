# Task Cards v1 (E + H + F0)

These are small, separable tasks. Do not combine them.
Tasks marked FUTURE ONLY are not active unless explicitly approved.

---

## Task 1 - Add value metrics to E outputs (no decision behaviour change) [FUTURE ONLY]

Goal:
- Add profit_per_unit_gbp and value_velocity_gbp_per_day to E outputs and logs.

Inputs:
- out/order_master.csv
- out/sku_sales_velocity.csv

Outputs:
- out/sku_performance_summary.csv gains:
  - profit_per_unit_gbp_30d
  - value_velocity_gbp_per_day (based on current velocity_used)
- out/e_decision_log.csv gains matching columns.

Acceptance:
- Existing row counts remain stable.
- New columns are present and numeric where expected.
- No restock logic changes.

---

## Task 2 - Create training set config (5-10 SKUs)

Goal:
- Create config/f_training_set.csv and a helper loader.

Outputs:
- config/f_training_set.csv (schema validated)
- A helper function that returns the enabled training SKUs.

Acceptance:
- If file missing -> WARN and continue.
- If file present -> list of enabled SKUs is correct.

---

## Task 3 - H001 daily offer snapshot (training set only)

Goal:
- Create scripts/H001_capture_offer_snapshot.py that:
  - loads the training set
  - pulls current offer context via SP-API (training set only)
  - writes out/listing_offer_snapshot_YYYY-MM-DD.csv
  - upserts into out/listing_offer_history.csv
  - validates schema

Notes:
- Default is SP-API only. Manual CSV input is emergency one-off only and must never run in daily loops.
- If SP-API is not available, STOP and ask for explicit approval before using any manual export path.

Acceptance:
- Script runs end-to-end locally (even if using a sample input).
- Output schema matches H0 spec.

---

## Task 4 - H002 BuyBotPro backfill importer (optional)

Goal:
- Create scripts/H002_import_bbp_history.py that:
  - reads imports/bbp_history/*.csv
  - maps to H history schema
  - writes rows with source=BBP and notes=BACKFILL
  - never overwrites SPAPI rows

Acceptance:
- Import works for at least one sample file.
- Source tagging is correct.

---

## Task 5 - F0 decision log scaffolding

Goal:
- Create out/f0_decision_log.csv and/or a script that ensures it exists with correct headers.
- Provide a schema check so daily workflow is consistent.

Acceptance:
- Running the script creates the file if missing.
- Headers match F0_decision_log_template.csv.

---

## Task 6 - Weekly review helper (optional)

Goal:
- Build a small report that summarizes:
  - top reason codes
  - which states were used most
  - outcome counts

Acceptance:
- Produces a simple CSV report from the logs.

End.
