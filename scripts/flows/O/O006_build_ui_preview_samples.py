from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


PREFERRED_SUPPLIERS: tuple[str, ...] = ("DHB", "Stax", "TD Synnex")
TARGET_COUNTS_BY_SUPPLIER: tuple[int, ...] = (4, 3, 3)
QTY_PATTERN: tuple[int, ...] = (12, 24, 6, 18, 30, 8, 15, 20, 10, 36)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _num(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _num_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _read_contract_df(root_path: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root_path, contract_name)


def _select_preview_rows(source_df: pd.DataFrame) -> pd.DataFrame:
    work = source_df.copy()
    work = work[
        work["supplier_name"].astype(str).str.strip().ne("")
        & work["seller_sku"].astype(str).str.strip().ne("")
        & work["title"].astype(str).str.strip().ne("")
        & work["main_image"].astype(str).str.strip().ne("")
    ].copy()
    if work.empty:
        return work

    selected_parts: list[pd.DataFrame] = []
    used_skus: set[str] = set()

    for supplier_name, target_count in zip(PREFERRED_SUPPLIERS, TARGET_COUNTS_BY_SUPPLIER):
        supplier_rows = work[work["supplier_name"] == supplier_name].copy()
        if supplier_rows.empty:
            continue
        supplier_rows = supplier_rows[~supplier_rows["seller_sku"].isin(used_skus)].head(target_count)
        if supplier_rows.empty:
            continue
        selected_parts.append(supplier_rows)
        used_skus.update(supplier_rows["seller_sku"].tolist())

    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else pd.DataFrame(columns=work.columns)
    if len(selected.index) < 10:
        remaining = work[~work["seller_sku"].isin(used_skus)].head(10 - len(selected.index))
        if not remaining.empty:
            selected = pd.concat([selected, remaining], ignore_index=True)

    return selected.head(10).reset_index(drop=True)


def _derive_cost(row: pd.Series) -> float:
    direct_cost = _num(row.get("current_supplier_buy_cost_gbp", ""))
    if direct_cost is not None and direct_cost > 0:
        return round(direct_cost, 2)

    market_price = _num(row.get("market_price_gbp", ""))
    if market_price is not None and market_price > 0:
        return round(max(0.5, market_price * 0.68), 2)

    return 2.49


def _derive_market_price(row: pd.Series, cost: float, index: int) -> float:
    direct_market = _num(row.get("market_price_gbp", ""))
    if direct_market is not None and direct_market > 0:
        return round(direct_market, 2)

    multiplier = 1.32 if index % 2 == 0 else 1.18
    return round(cost * multiplier, 2)


def build_ui_preview_samples(root: Path | None = None, *, preview_utc: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    asof_utc = preview_utc or _utc_now_iso()

    source_df = _read_contract_df(root_path, "restock_source_view")
    if source_df.empty:
        raise FileNotFoundError("restock_source_view.csv is required to build preview samples")

    selected = _select_preview_rows(source_df)
    if len(selected.index) < 10:
        raise ValueError("not enough source rows with supplier, title, image, and sku to build 10 preview samples")

    rec_contract = get_o_output_contract("restock_recommendations_live")
    queue_contract = get_o_output_contract("restock_review_queue")

    rec_rows: list[dict[str, str]] = []
    queue_rows: list[dict[str, str]] = []

    for idx, (_, row) in enumerate(selected.iterrows()):
        status = "full_restock" if idx < 6 else "test_restock"
        target_days = "30" if status == "full_restock" else "10"
        qty = QTY_PATTERN[idx]
        cost = _derive_cost(row)
        market_price = _derive_market_price(row, cost, idx)
        forward_profit = round(market_price - cost, 2)
        forward_roi = round((forward_profit / cost) * 100.0, 2) if cost > 0 else 0.0
        days_cover_available = _normalize_text(row.get("days_cover_available_only", "0")) or "0"
        days_cover_total = _normalize_text(row.get("days_cover_total_pipeline", days_cover_available)) or days_cover_available
        reasons = "UI_PREVIEW_SAMPLE"
        if status == "test_restock":
            reasons = "UI_PREVIEW_SAMPLE,TEST_SPEND_CAP_APPLIED"

        rec_row = {
            "asof_utc": asof_utc,
            "seller_sku": _normalize_text(row.get("seller_sku", "")),
            "asin": _normalize_text(row.get("asin", "")),
            "supplier_code": _normalize_text(row.get("supplier_code", "")),
            "supplier_name": _normalize_text(row.get("supplier_name", "")),
            "recommendation_status": status,
            "reason_codes": reasons,
            "recommended_qty_raw": str(qty),
            "recommended_qty_rounded": str(qty),
            "target_days_cover": target_days,
            "days_cover_available_only": days_cover_available,
            "days_cover_total_pipeline": days_cover_total,
            "current_supplier_buy_cost_gbp": _num_text(cost),
            "current_supplier_cost_source": "ui_preview_sample",
            "market_price_gbp": _num_text(market_price),
            "market_price_basis_used": "UI_PREVIEW_SAMPLE",
            "forward_roi_pct": _num_text(forward_roi),
            "forward_profit_per_unit_gbp": _num_text(forward_profit),
            "title": _normalize_text(row.get("title", "")),
            "main_image": _normalize_text(row.get("main_image", "")),
            "confidence_score": "80",
            "policy_version": "o_ui_preview_v1",
            "cost_mode": "test",
            "recommendation_basis": "ui_preview_sample",
        }
        rec_rows.append(rec_row)

        supplier_code = _normalize_text(row.get("supplier_code", ""))
        supplier_name = _normalize_text(row.get("supplier_name", ""))
        queue_row = {
            "queue_utc": asof_utc,
            "seller_sku": rec_row["seller_sku"],
            "asin": rec_row["asin"],
            "supplier_code": supplier_code,
            "supplier_name": supplier_name,
            "recommendation_status": status,
            "suggested_qty": str(qty),
            "suggested_unit_cost_gbp": _num_text(cost),
            "suggested_market_price_gbp": _num_text(market_price),
            "expected_forward_roi_pct": _num_text(forward_roi),
            "expected_forward_profit_per_unit_gbp": _num_text(forward_profit),
            "days_cover_available_only": days_cover_available,
            "days_cover_total_pipeline": days_cover_total,
            "reason_codes": reasons,
            "queue_status": "needs_review",
            "title": rec_row["title"],
            "main_image": rec_row["main_image"],
            "supplier_group_key": f"{supplier_code}|{supplier_name}".strip("|"),
            "snooze_until_utc": "",
            "queue_notes": "ui_preview_sample",
            "cost_mode": "test",
            "recommendation_basis": "ui_preview_sample",
        }
        queue_rows.append(queue_row)

    rec_df = pd.DataFrame(rec_rows)
    queue_df = pd.DataFrame(queue_rows)

    rec_ordered = [*rec_contract.required_columns, *rec_contract.optional_columns]
    queue_ordered = [*queue_contract.required_columns, *queue_contract.optional_columns]
    for col in rec_ordered:
        if col not in rec_df.columns:
            rec_df[col] = ""
    for col in queue_ordered:
        if col not in queue_df.columns:
            queue_df[col] = ""

    rec_df = rec_df[rec_ordered]
    queue_df = queue_df[queue_ordered]

    rec_path = root_path / rec_contract.rel_path
    queue_path = root_path / queue_contract.rel_path
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "restock_recommendations_live", rec_df)
    write_o_contract_df(root_path, "restock_review_queue", queue_df)

    supplier_counts = queue_df.groupby("supplier_name").size().to_dict()
    print(
        {
            "status": "success",
            "rows": len(queue_df),
            "suppliers": supplier_counts,
            "recommendations": str(rec_path),
            "queue": str(queue_path),
        }
    )
    return rec_df, queue_df


def main() -> None:
    build_ui_preview_samples()


if __name__ == "__main__":
    main()
