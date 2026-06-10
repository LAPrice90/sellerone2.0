from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
BRIDGE = OUT / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv"
OUT_REVIEW = OUT / "systems" / "B" / "refunds" / "b_return_cogs_residual_review.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_return_cogs_residual_review_summary.csv"

REVIEW_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "token_return_state",
    "recovered_cogs_allowed_exvat",
    "blocked_return_cogs_exvat",
    "blocked_return_cogs_source",
    "residual_review_state",
    "manager_expectation",
    "mot_proof_check",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _num_text(value: object) -> str:
    number = _num(value)
    if abs(number) < 0.0000005:
        return "0"
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _review_state(disposition: str, allowed_cogs: float, blocked_cogs: float) -> str:
    if disposition and disposition != "SELLABLE" and allowed_cogs > 0:
        return "unsafe_non_sellable_cogs_recovery"
    if blocked_cogs > 0 and allowed_cogs <= 0:
        return "blocked_from_roi_and_stock_recovery"
    return "no_residual_cogs_recovery"


def build_return_cogs_residual_review(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    bridge = _read_csv(root_path / BRIDGE)
    rows: list[dict[str, str]] = []
    missing_schema: list[str] = []
    required = {
        "order_id",
        "sku",
        "amazon_return_disposition",
        "token_return_state",
        "return_cogs_recovered_exvat",
        "blocked_return_cogs_exvat",
        "blocked_return_cogs_source",
    }
    if (root_path / BRIDGE).exists():
        missing_schema = sorted(required - set(bridge.columns))
    if not bridge.empty and not missing_schema:
        for _, source in bridge.iterrows():
            disposition = _text(source.get("amazon_return_disposition", "")).upper()
            allowed_cogs = _num(source.get("return_cogs_recovered_exvat", ""))
            blocked_cogs = _num(source.get("blocked_return_cogs_exvat", ""))
            if not (blocked_cogs > 0 or (disposition and disposition != "SELLABLE" and allowed_cogs > 0)):
                continue
            state = _review_state(disposition, allowed_cogs, blocked_cogs)
            rows.append(
                {
                    "order_id": _text(source.get("order_id", "")),
                    "sku": _text(source.get("sku", "")).upper(),
                    "amazon_return_disposition": disposition,
                    "token_return_state": _text(source.get("token_return_state", "")),
                    "recovered_cogs_allowed_exvat": _num_text(allowed_cogs),
                    "blocked_return_cogs_exvat": _num_text(blocked_cogs),
                    "blocked_return_cogs_source": _text(source.get("blocked_return_cogs_source", "")),
                    "residual_review_state": state,
                    "manager_expectation": (
                        "Non-sellable returned stock may stay visible as history, but it must not count as recovered stock money."
                    ),
                    "mot_proof_check": (
                        "B064 and B MOT must show recovered COGS allowed is zero for non-sellable returns."
                    ),
                    "bounded_worker_task": (
                        "Keep residual return COGS blocked from ROI/restocking; do not edit the token return ledger from this review."
                    ),
                    "retest_rule": "Rerun B037, B038, B040, B041, B051, B064, and B MOT after any proof change.",
                    "preview_live_write_allowed": "0",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "protected_before_apply": "0",
                }
            )

    review = pd.DataFrame(rows, columns=REVIEW_COLUMNS).fillna("")
    unsafe_rows = review[review["residual_review_state"] == "unsafe_non_sellable_cogs_recovery"] if not review.empty else review
    status = "ok"
    if not (root_path / BRIDGE).exists():
        status = "not_checked"
    elif missing_schema:
        status = "fail"
    elif len(unsafe_rows) > 0:
        status = "fail"
    summary = pd.DataFrame(
        [
            {"metric": "status", "value": status},
            {"metric": "observed_utc", "value": observed},
            {"metric": "review_rows", "value": str(len(review))},
            {"metric": "blocked_rows", "value": str(int((review["blocked_return_cogs_exvat"].map(_num) > 0).sum()) if not review.empty else 0)},
            {"metric": "unsafe_rows", "value": str(len(unsafe_rows))},
            {
                "metric": "blocked_return_cogs_total",
                "value": _num_text(review["blocked_return_cogs_exvat"].map(_num).sum()) if not review.empty else "0",
            },
            {"metric": "missing_schema", "value": ";".join(missing_schema)},
        ],
        columns=SUMMARY_COLUMNS,
    )
    return {"review": review, "summary": summary}


def write_return_cogs_residual_review_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    review_path = root_path / OUT_REVIEW
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["review"], review_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"review": review_path, "summary": summary_path}


def main() -> None:
    result = build_return_cogs_residual_review()
    paths = write_return_cogs_residual_review_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "review_rows": summary.get("review_rows", "0"),
            "blocked_rows": summary.get("blocked_rows", "0"),
            "unsafe_rows": summary.get("unsafe_rows", "0"),
            "review": str(paths["review"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
