import os
import time
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "out"
REPORT_DIR = OUT_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

LEDGER_PATH = Path(os.environ.get("TOKEN_LEDGER_PATH", OUT_DIR / "token_ledger_live.csv"))

TOKEN_LEDGER_REQUIRED_COLUMNS = [
    "return_order_id",
    "return_date",
    "last_return_order_id",
    "last_return_date",
    "disposed_event_id",
    "disposed_date",
    "disposed_reason",
    "allocated_order_id",
]


def _safe_to_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    last_error: OSError | None = None
    for attempt in range(1, 4):
        try:
            df.to_csv(tmp_path, index=False)
            os.replace(tmp_path, path)
            return
        except OSError as exc:
            last_error = exc
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt == 3:
                raise
            time.sleep(0.25 * attempt)
    if last_error is not None:
        raise last_error


def build_token_batch_report(
    ledger_path: Path = LEDGER_PATH,
    report_dir: Path = REPORT_DIR,
    stamp: str | None = None,
) -> dict[str, object]:
    if not ledger_path.exists():
        raise SystemExit(f"Missing token ledger: {ledger_path}")

    ledger = pd.read_csv(ledger_path, dtype=str).fillna("")

    if "source_batch_id" not in ledger.columns:
        ledger["source_batch_id"] = ""
    if "status" not in ledger.columns:
        ledger["status"] = ""
    for column in TOKEN_LEDGER_REQUIRED_COLUMNS:
        if column not in ledger.columns:
            ledger[column] = ""

    ledger["batch_id"] = ledger["source_batch_id"].astype(str).str.strip()
    ledger.loc[ledger["batch_id"] == "", "batch_id"] = "(blank)"

    ledger["is_allocated"] = ledger["status"] == "allocated"
    ledger["is_available"] = ledger["status"] == "available"
    ledger["is_research_pending"] = ledger["status"] == "research_pending"
    ledger["is_unsellable"] = ledger["status"] == "unsellable"
    ledger["is_returned_pending"] = ledger["status"] == "returned_pending"
    ledger["is_warehouse"] = ledger["status"] == "warehouse"

    ledger["has_return"] = ledger[
        ["return_order_id", "return_date", "last_return_order_id", "last_return_date"]
    ].astype(str).apply(lambda r: any(x.strip() for x in r), axis=1)
    ledger["has_disposed"] = ledger[
        ["disposed_event_id", "disposed_date", "disposed_reason"]
    ].astype(str).apply(lambda r: any(x.strip() for x in r), axis=1)

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

    stamp = stamp or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = report_dir / f"token_batch_daily_report_{stamp}.csv"
    _safe_to_csv(report, report_path)

    weekly_path = report_dir / "token_batch_weekly_log.csv"
    report["report_date"] = stamp
    if weekly_path.exists():
        weekly = pd.read_csv(weekly_path, dtype=str).fillna("")
        weekly = pd.concat([weekly, report], ignore_index=True)
        _safe_to_csv(weekly, weekly_path)
    else:
        _safe_to_csv(report, weekly_path)

    return {
        "status": "success",
        "batches": int(report["batch_id"].nunique()),
        "rows": int(len(report)),
        "daily_report": str(report_path),
        "weekly_log": str(weekly_path),
    }


def main() -> int:
    print(build_token_batch_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
