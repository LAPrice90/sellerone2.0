import os
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
REPORT_DIR = OUT_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

LEDGER_PATH = Path(os.environ.get("TOKEN_LEDGER_PATH", OUT_DIR / "token_ledger_live.csv"))

if not LEDGER_PATH.exists():
    raise SystemExit(f"Missing token ledger: {LEDGER_PATH}")

ledger = pd.read_csv(LEDGER_PATH, dtype=str).fillna("")

if "source_batch_id" not in ledger.columns:
    ledger["source_batch_id"] = ""
if "status" not in ledger.columns:
    ledger["status"] = ""

# Normalize batch id
ledger["batch_id"] = ledger["source_batch_id"].astype(str).str.strip()
ledger.loc[ledger["batch_id"] == "", "batch_id"] = "(blank)"

# Helper flags
ledger["is_allocated"] = ledger["status"] == "allocated"
ledger["is_available"] = ledger["status"] == "available"
ledger["is_research_pending"] = ledger["status"] == "research_pending"
ledger["is_unsellable"] = ledger["status"] == "unsellable"
ledger["is_returned_pending"] = ledger["status"] == "returned_pending"
ledger["is_warehouse"] = ledger["status"] == "warehouse"

ledger["has_return"] = ledger[["return_order_id", "return_date", "last_return_order_id", "last_return_date"]].astype(str).apply(lambda r: any(x.strip() for x in r), axis=1)
ledger["has_disposed"] = ledger[["disposed_event_id", "disposed_date", "disposed_reason"]].astype(str).apply(lambda r: any(x.strip() for x in r), axis=1)

# Build per-batch summary
rows = []
for batch_id, grp in ledger.groupby("batch_id"):
    rows.append({
        "batch_id": batch_id,
        "tokens_total": len(grp),
        "allocated_tokens": int(grp["is_allocated"].sum()),
        "available_tokens": int(grp["is_available"].sum()),
        "research_pending": int(grp["is_research_pending"].sum()),
        "unsellable": int(grp["is_unsellable"].sum()),
        "returned_pending": int(grp["is_returned_pending"].sum()),
        "warehouse": int(grp["is_warehouse"].sum()),
        "returned_events": int(grp["has_return"].sum()),
        "disposed_events": int(grp["has_disposed"].sum()),
        "unique_orders": int(grp["allocated_order_id"].replace("", pd.NA).dropna().nunique()),
    })

report = pd.DataFrame(rows).sort_values("tokens_total", ascending=False)

# Write daily report
stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
report_path = REPORT_DIR / f"token_batch_daily_report_{stamp}.csv"
report.to_csv(report_path, index=False)

# Append weekly log
weekly_path = REPORT_DIR / "token_batch_weekly_log.csv"
report["report_date"] = stamp
if weekly_path.exists():
    weekly = pd.read_csv(weekly_path, dtype=str).fillna("")
    weekly = pd.concat([weekly, report], ignore_index=True)
    weekly.to_csv(weekly_path, index=False)
else:
    report.to_csv(weekly_path, index=False)

print({
    "status": "success",
    "batches": int(report["batch_id"].nunique()),
    "rows": int(len(report)),
    "daily_report": str(report_path),
    "weekly_log": str(weekly_path),
})
