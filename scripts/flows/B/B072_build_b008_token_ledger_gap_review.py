from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv"
ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
B057_APPLIED = OUT / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_applied.csv"
B062_APPLIED = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_swap_applied.csv"
OUT_REVIEW = OUT / "systems" / "B" / "refunds" / "b_b008_token_ledger_gap_review.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_b008_token_ledger_gap_review_summary.csv"

REVIEW_COLUMNS = [
    "order_id",
    "sku",
    "allocation_token_id",
    "allocation_row_seen",
    "ledger_token_seen",
    "b057_applied_seen",
    "b062_replacement_seen",
    "gap_label",
    "manager_state",
    "protected_before_apply",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _split(value: object) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in _text(value).split("|"):
        text = part.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _prepare(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy()
    for column in columns:
        if column not in work.columns:
            work[column] = ""
    return work


def _token_seen(df: pd.DataFrame, column: str, token_id: str) -> bool:
    return not df.empty and column in df.columns and bool((df[column].astype(str) == token_id).any())


def _allocation_row_seen(allocations: pd.DataFrame, order_id: str, sku: str, token_id: str) -> bool:
    if allocations.empty:
        return False
    rows = allocations[
        (allocations["order_id"].astype(str) == order_id)
        & (allocations["seller_sku"].map(_norm_sku) == sku)
        & (allocations["token_id"].astype(str) == token_id)
    ]
    return not rows.empty


def _classify(*, token_id: str, ledger_seen: bool, b057_seen: bool, b062_seen: bool) -> tuple[str, str, str, str, str]:
    if ledger_seen:
        return (
            "stale_preview_token_now_visible",
            "retest_b042",
            "The token is now visible in the ledger, so the B042 preview may be stale.",
            "Rerun B042, B041, B038, B051, and B MOT.",
            "Rerun B042/B041/B038/B051/B MOT; row should leave token-ledger-gap if the token is still valid.",
        )
    if b057_seen:
        return (
            "b057_allocation_token_missing_from_ledger",
            "protected_ledger_alignment_needed",
            "B057 says it created the sale-allocation token, but the current token ledger cannot see it.",
            "Prepare a protected ledger-alignment preview. Do not create a substitute token or edit the ledger here.",
            "After any protected ledger repair, rerun B042/B041/B038/B051 and B MOT.",
        )
    if b062_seen:
        return (
            "b062_replacement_token_missing_from_ledger",
            "protected_ledger_alignment_needed",
            "B062 used this token as replacement stock, but the current token ledger cannot see it.",
            "Prepare a protected ledger-alignment preview. Do not create a substitute token or edit the ledger here.",
            "After any protected ledger repair, rerun B042/B041/B038/B051 and B MOT.",
        )
    if "-RB009-" in token_id:
        return (
            "rb009_reusable_return_token_missing_from_ledger",
            "protected_return_token_ledger_alignment_needed",
            "The allocation points to a returned-stock reusable token, but the current token ledger cannot see it.",
            "Trace the original B009 event or protected apply manifest before any ledger correction.",
            "After proof or protected correction, rerun B042/B041/B038/B051 and B MOT.",
        )
    return (
        "token_id_missing_from_ledger_not_yet_proven",
        "not_yet_proven",
        "The allocation token is not visible in the current token ledger and no known manager repair manifest explains it.",
        "Inspect allocation and token-ledger history; do not create a substitute token.",
        "Rerun this review after the earliest missing proof source is found.",
    )


def build_b008_token_ledger_gap_review(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    preview = _prepare(_read_csv(root_path / PREVIEW), ["order_id", "sku", "allocation_token_ids", "reproof_lane"])
    allocations = _prepare(_read_csv(root_path / ALLOCATIONS), ["order_id", "seller_sku", "token_id"])
    ledger = _prepare(_read_csv(root_path / TOKEN_LEDGER), ["token_id"])
    b057 = _prepare(_read_csv(root_path / B057_APPLIED), ["new_token_id"])
    b062 = _prepare(_read_csv(root_path / B062_APPLIED), ["replacement_token_id"])

    rows: list[dict[str, str]] = []
    gaps = preview[preview["reproof_lane"].astype(str).str.strip() == "token_ledger_gap"].copy()
    for _, row in gaps.iterrows():
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        for token_id in _split(row.get("allocation_token_ids", "")):
            ledger_seen = _token_seen(ledger, "token_id", token_id)
            b057_seen = _token_seen(b057, "new_token_id", token_id)
            b062_seen = _token_seen(b062, "replacement_token_id", token_id)
            label, state, expectation, task, retest = _classify(
                token_id=token_id,
                ledger_seen=ledger_seen,
                b057_seen=b057_seen,
                b062_seen=b062_seen,
            )
            rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "allocation_token_id": token_id,
                    "allocation_row_seen": "1" if _allocation_row_seen(allocations, order_id, sku, token_id) else "0",
                    "ledger_token_seen": "1" if ledger_seen else "0",
                    "b057_applied_seen": "1" if b057_seen else "0",
                    "b062_replacement_seen": "1" if b062_seen else "0",
                    "gap_label": label,
                    "manager_state": state,
                    "protected_before_apply": "1" if state not in {"retest_b042"} else "0",
                    "preview_live_write_allowed": "0",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "manager_expectation": expectation,
                    "bounded_worker_task": task,
                    "retest_rule": retest,
                }
            )

    review = pd.DataFrame(rows, columns=REVIEW_COLUMNS).fillna("")
    unsafe = review[
        (review["preview_live_write_allowed"].astype(str) != "0")
        | (review["roi_or_restock_use_allowed"].astype(str) != "0")
        | (review["sellerboard_final_truth_allowed"].astype(str) != "0")
    ]
    unclassified = review[(review["gap_label"].astype(str).str.strip() == "") | (review["manager_state"].astype(str).str.strip() == "")]
    summary_values = {
        "status": "fail" if len(unsafe) or len(unclassified) else "ok",
        "review_rows": str(len(review)),
        "stale_preview_rows": str(int((review["manager_state"] == "retest_b042").sum()) if not review.empty else 0),
        "protected_ledger_alignment_rows": str(
            int(review["manager_state"].astype(str).str.contains("ledger_alignment", na=False).sum()) if not review.empty else 0
        ),
        "not_yet_proven_rows": str(int((review["manager_state"] == "not_yet_proven").sum()) if not review.empty else 0),
        "unclassified_rows": str(len(unclassified)),
        "unsafe_rows": str(len(unsafe)),
        "live_write_allowed_rows": str(
            int((review["preview_live_write_allowed"] != "0").sum()) if not review.empty else 0
        ),
        "roi_or_restock_allowed_rows": str(
            int((review["roi_or_restock_use_allowed"] != "0").sum()) if not review.empty else 0
        ),
        "sellerboard_final_truth_allowed_rows": str(
            int((review["sellerboard_final_truth_allowed"] != "0").sum()) if not review.empty else 0
        ),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "review": review,
        "summary": summary,
        "review_path": root_path / OUT_REVIEW,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_b008_token_ledger_gap_review_outputs(result: dict[str, object], *, root: Path | str | None = None) -> dict[str, Path]:
    review_path = Path(result["review_path"])
    summary_path = Path(result["summary_path"])
    review_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["review"], review_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"review": review_path, "summary": summary_path}


def main() -> None:
    result = build_b008_token_ledger_gap_review()
    paths = write_b008_token_ledger_gap_review_outputs(result)
    summary = result["summary"]
    values = {row["metric"]: row["value"] for _, row in summary.iterrows()} if not summary.empty else {}
    print(
        {
            "status": values.get("status", ""),
            "review_rows": values.get("review_rows", "0"),
            "protected_ledger_alignment_rows": values.get("protected_ledger_alignment_rows", "0"),
            "not_yet_proven_rows": values.get("not_yet_proven_rows", "0"),
            "review": str(paths["review"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
