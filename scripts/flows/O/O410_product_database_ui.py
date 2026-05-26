from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O030_build_product_db_operator_view import build_product_db_operator_view
from scripts.flows.O._contract_io import read_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract

_FRESHNESS_MAX_AGE_HOURS = {
    "source_product_db_asof": 48,
    "source_queue_asof": 48,
    "source_ordered_asof": 48,
    "source_velocity_asof": 48,
    "source_performance_asof": 48,
}
_OPTIONAL_FRESHNESS_SOURCES = {"source_queue_asof", "source_ordered_asof"}


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_view_df(root: Path) -> pd.DataFrame:
    return read_o_contract_df(root, "product_db_operator_view")


def load_product_db_operator_view(root: Path | None = None, *, force_refresh: bool = False) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    view_df = _read_view_df(root_path)
    if force_refresh or view_df.empty:
        view_df = build_product_db_operator_view(root=root_path)
    return view_df


def _money_text(value: object) -> str:
    text = _normalize_text(value)
    if text == "":
        return "-"
    return f"\u00A3{text}"


def _pack_label(row: pd.Series) -> str:
    explicit = _normalize_text(row.get("pack_profile_label", ""))
    if explicit != "":
        return explicit
    mode = _normalize_text(row.get("order_qty_mode", "")).lower()
    sell_pack = _normalize_text(row.get("sell_pack_qty", ""))
    case_qty = _normalize_text(row.get("supplier_case_qty", ""))
    if mode == "bundles":
        label = f"Bundle {sell_pack or '1'}"
    elif mode == "sell_packs":
        label = f"Pack {sell_pack or '1'}"
    elif case_qty not in {"", "1"}:
        label = f"Case {case_qty}"
    else:
        label = "Unit"
    step = _normalize_text(row.get("valid_order_step", ""))
    if step not in {"", "1"}:
        label = f"{label} | Step {step}"
    return label


def _source_key_label(source_column: str) -> str:
    return source_column.replace("source_", "").replace("_asof", "")


def _parse_timestamp(value: object) -> datetime | None:
    text = _normalize_text(value)
    if text == "":
        return None
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.to_pydatetime()
    return None


def _freshness_flags_series(view_df: pd.DataFrame, *, now_utc: datetime | None = None) -> pd.Series:
    if view_df.empty:
        return pd.Series(dtype=str, index=view_df.index)
    now = now_utc or datetime.now(timezone.utc)
    flags: list[str] = []
    for _, row in view_df.iterrows():
        stale_sources: list[str] = []
        for source_col, max_age_hours in _FRESHNESS_MAX_AGE_HOURS.items():
            source_raw = _normalize_text(row.get(source_col, ""))
            source_ts = _parse_timestamp(source_raw)
            if source_ts is None:
                if source_raw == "" and source_col in _OPTIONAL_FRESHNESS_SOURCES:
                    continue
                stale_sources.append(_source_key_label(source_col))
                continue
            if source_ts > now:
                continue
            if now - source_ts > timedelta(hours=max_age_hours):
                stale_sources.append(_source_key_label(source_col))
        flags.append("|".join(stale_sources) if stale_sources else "ok")
    return pd.Series(flags, index=view_df.index, dtype=str)


def product_db_status_counts(view_df: pd.DataFrame) -> dict[str, int]:
    if view_df.empty:
        return {
            "live": 0,
            "snoozed": 0,
            "discontinued": 0,
            "dropped": 0,
            "with_issues": 0,
            "rows": 0,
        }
    status = view_df.get("operational_status", "").map(lambda v: _normalize_text(v).lower())
    with_issues = view_df.get("data_issue_flags", "").map(lambda v: _normalize_text(v) != "")
    return {
        "live": int(status.eq("live").sum()),
        "snoozed": int(status.eq("snoozed").sum()),
        "discontinued": int(status.eq("discontinued").sum()),
        "dropped": int(status.eq("dropped").sum()),
        "with_issues": int(with_issues.sum()),
        "rows": int(len(view_df.index)),
    }


def filter_product_db_view(
    view_df: pd.DataFrame,
    *,
    search_text: str = "",
    supplier_filter: str = "All suppliers",
    status_filter: tuple[str, ...] = ("live", "snoozed", "discontinued", "dropped"),
    pack_mode_filter: str = "All modes",
    issues_only: bool = False,
    low_stock_only: bool = False,
    stale_only: bool = False,
) -> pd.DataFrame:
    if view_df.empty:
        return view_df.copy()
    out = view_df.copy()
    out["_status_norm"] = out.get("operational_status", "").map(lambda v: _normalize_text(v).lower())
    out["_supplier_label"] = out.get("supplier_name", "").map(lambda v: _normalize_text(v) or "(Unknown supplier)")
    out["_mode_norm"] = out.get("order_qty_mode", "").map(lambda v: _normalize_text(v).lower())
    out["_freshness_flags"] = _freshness_flags_series(out)

    status_set = {_normalize_text(v).lower() for v in status_filter if _normalize_text(v) != ""}
    if status_set:
        out = out[out["_status_norm"].isin(status_set)].copy()

    supplier_token = _normalize_text(supplier_filter)
    if supplier_token not in {"", "All suppliers"}:
        out = out[out["_supplier_label"] == supplier_token].copy()

    mode_token = _normalize_text(pack_mode_filter).lower()
    if mode_token not in {"", "all modes"}:
        out = out[out["_mode_norm"] == mode_token].copy()

    query = _normalize_text(search_text).lower()
    if query:
        search_cols = ("seller_sku", "asin", "title", "supplier_sku", "barcode", "supplier_name")
        mask = pd.Series(False, index=out.index)
        for col in search_cols:
            if col in out.columns:
                mask = mask | out[col].astype(str).str.lower().str.contains(query, na=False)
        out = out[mask].copy()

    if issues_only:
        out = out[out.get("data_issue_flags", "").map(lambda v: _normalize_text(v) != "")].copy()

    if low_stock_only:
        stock = pd.to_numeric(out.get("stock_available", ""), errors="coerce").fillna(0)
        out = out[stock <= 0].copy()

    if stale_only:
        out = out[out["_freshness_flags"] != "ok"].copy()

    out = out.sort_values(by=["_supplier_label", "_status_norm", "seller_sku"], ascending=[True, True, True], kind="stable")
    return out.drop(columns=["_status_norm", "_supplier_label", "_mode_norm", "_freshness_flags"], errors="ignore")


def build_product_db_glance_df(view_df: pd.DataFrame) -> pd.DataFrame:
    if view_df.empty:
        return pd.DataFrame(
            columns=[
                "Status",
                "Supplier",
                "SKU",
                "ASIN",
                "Name",
                "Packs",
                "Stock",
                "Ordered",
                "Cost",
                "VAT",
                "ROI",
                "V30",
                "Days",
                "Freshness",
                "Issues",
            ]
        )
    freshness_flags = _freshness_flags_series(view_df)
    out = pd.DataFrame(
        {
            "Status": view_df.get("operational_status", "").map(lambda v: _normalize_text(v).title()),
            "Supplier": view_df.get("supplier_name", "").map(lambda v: _normalize_text(v) or "(Unknown supplier)"),
            "SKU": view_df.get("seller_sku", ""),
            "ASIN": view_df.get("asin", ""),
            "Name": view_df.get("title", ""),
            "Packs": view_df.apply(_pack_label, axis=1),
            "Stock": view_df.get("stock_available", "").map(lambda v: _normalize_text(v) or "0"),
            "Ordered": view_df.get("ordered_open_qty", "").map(lambda v: _normalize_text(v) or "0"),
            "Cost": view_df.get("supplier_catalog_price", "").map(_money_text),
            "VAT": view_df.get("vat_rate", "").map(lambda v: f"{_normalize_text(v)}%" if _normalize_text(v) else "-"),
            "ROI": view_df.get("roi_snapshot_pct", "").map(lambda v: f"{_normalize_text(v)}%" if _normalize_text(v) else "-"),
            "V30": view_df.get("velocity_30d", "").map(lambda v: _normalize_text(v) or "0"),
            "Days": view_df.get("days_cover", "").map(lambda v: _normalize_text(v) or "-"),
            "Freshness": freshness_flags.map(lambda v: _normalize_text(v) or "ok"),
            "Issues": view_df.get("data_issue_flags", "").map(lambda v: _normalize_text(v) or "-"),
        }
    )
    return out


def render_product_database_ui(root: Path | None = None) -> None:
    import streamlit as st

    root_path = Path(root) if root is not None else get_o_path_contract().root
    view_df = load_product_db_operator_view(root=root_path)

    st.subheader("Product Database")
    st.caption("Browse product truth here. Use Product DB Edit for manual changes.")

    counts = product_db_status_counts(view_df)
    freshness_flags = _freshness_flags_series(view_df)
    stale_count = int((freshness_flags != "ok").sum()) if not view_df.empty else 0
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Rows", str(counts["rows"]))
    c2.metric("Live", str(counts["live"]))
    c3.metric("Snoozed", str(counts["snoozed"]))
    c4.metric("Discontinued", str(counts["discontinued"]))
    c5.metric("Dropped", str(counts["dropped"]))
    c6.metric("Issues", str(counts["with_issues"]))
    c7.metric("Stale", str(stale_count))

    if view_df.empty:
        st.info("No product database rows available.")
        return

    supplier_options = ["All suppliers", *sorted({_normalize_text(v) or "(Unknown supplier)" for v in view_df.get("supplier_name", "").tolist()})]
    controls_a, controls_b, controls_c, controls_d, controls_e, controls_f, controls_g = st.columns([2, 2, 2, 2, 1, 1, 1])
    search_text = controls_a.text_input("Search SKU / ASIN / Name / Supply / Barcode", value="", key="o_product_db_search")
    supplier_filter = controls_b.selectbox("Supplier", options=supplier_options, key="o_product_db_supplier")
    status_filter = controls_c.multiselect(
        "Status",
        options=["live", "snoozed", "discontinued", "dropped"],
        default=["live", "snoozed", "discontinued", "dropped"],
        key="o_product_db_status",
    )
    pack_mode_filter = controls_d.selectbox(
        "Pack Mode",
        options=["All modes", "raw_units", "sell_packs", "bundles"],
        key="o_product_db_pack_mode",
    )
    issues_only = controls_e.checkbox("Issues", value=False, key="o_product_db_issues_only")
    low_stock_only = controls_f.checkbox("No Stock", value=False, key="o_product_db_low_stock_only")
    stale_only = controls_g.checkbox("Stale", value=False, key="o_product_db_stale_only")

    filtered = filter_product_db_view(
        view_df,
        search_text=search_text,
        supplier_filter=supplier_filter,
        status_filter=tuple(status_filter),
        pack_mode_filter=pack_mode_filter,
        issues_only=issues_only,
        low_stock_only=low_stock_only,
        stale_only=stale_only,
    )
    st.caption(f"Showing {len(filtered.index)} rows.")

    if filtered.empty:
        st.info("No rows match current filters.")
        return

    st.dataframe(build_product_db_glance_df(filtered), use_container_width=True, hide_index=True)

    sku_options = filtered.get("seller_sku", pd.Series(dtype=str)).astype(str).tolist()
    selected_sku = st.selectbox("View Details", options=["", *sku_options], key="o_product_db_detail_sku")
    if _normalize_text(selected_sku) == "":
        return

    selected_rows = filtered[filtered["seller_sku"].astype(str) == selected_sku].copy()
    row = selected_rows.iloc[0].to_dict()
    row_freshness = _normalize_text(_freshness_flags_series(selected_rows).iloc[0]) or "ok"
    with st.expander(f"{selected_sku} details", expanded=True):
        st.markdown("**Identity**")
        st.markdown(f"SKU: `{_normalize_text(row.get('seller_sku', ''))}`")
        st.markdown(f"ASIN: `{_normalize_text(row.get('asin', '')) or '-'}`")
        st.markdown(f"Name: {_normalize_text(row.get('title', '')) or '-'}")
        st.markdown(f"Status: {_normalize_text(row.get('operational_status', '')).title()}")
        st.markdown(f"Sale Status: {_normalize_text(row.get('sale_status', '')) or '-'}")
        st.markdown(f"Queue Status: {_normalize_text(row.get('queue_status', '')) or '-'}")
        st.markdown(f"Status Reason: {_normalize_text(row.get('status_reason', '')) or '-'}")

        st.markdown("**Supply And Packs**")
        st.markdown(f"Supplier: {_normalize_text(row.get('supplier_name', '')) or '-'} ({_normalize_text(row.get('supplier_code', '')) or '-'})")
        st.markdown(f"Supply SKU: `{_normalize_text(row.get('supplier_sku', '')) or '-'}`")
        st.markdown(f"Barcode: `{_normalize_text(row.get('barcode', '')) or '-'}`")
        st.markdown(f"Pack Profile: {_pack_label(pd.Series(row))}")
        st.markdown(f"Pack Note: {_normalize_text(row.get('pack_conversion_note', '')) or '-'}")

        st.markdown("**Economics And Tax**")
        st.markdown(f"Supplier Cost: {_money_text(row.get('supplier_catalog_price', ''))}")
        st.markdown(f"Last Purchase: {_money_text(row.get('last_purchase_price', ''))}")
        st.markdown(f"VAT: {_normalize_text(row.get('vat_rate', '')) or '-'}")
        st.markdown(f"ROI Snapshot: {_normalize_text(row.get('roi_snapshot_pct', '')) or '-'}")

        st.markdown("**Stock And Demand**")
        st.markdown(f"Stock Available: {_normalize_text(row.get('stock_available', '')) or '0'}")
        st.markdown(f"Stock Total: {_normalize_text(row.get('stock_total', '')) or '0'}")
        st.markdown(f"Ordered Open: {_normalize_text(row.get('ordered_open_qty', '')) or '0'}")
        st.markdown(f"Velocity 30d: {_normalize_text(row.get('velocity_30d', '')) or '0'}")
        st.markdown(f"Days Cover: {_normalize_text(row.get('days_cover', '')) or '-'}")

        st.markdown("**Issues**")
        st.markdown(_normalize_text(row.get("data_issue_flags", "")) or "none")
        st.markdown("**Freshness**")
        st.markdown(f"Flags: {row_freshness}")
        st.markdown(f"Product DB asof: {_normalize_text(row.get('source_product_db_asof', '')) or '-'}")
        st.markdown(f"Queue asof: {_normalize_text(row.get('source_queue_asof', '')) or '-'}")
        st.markdown(f"Ordered asof: {_normalize_text(row.get('source_ordered_asof', '')) or '-'}")
        st.markdown(f"Velocity asof: {_normalize_text(row.get('source_velocity_asof', '')) or '-'}")
        st.markdown(f"Performance asof: {_normalize_text(row.get('source_performance_asof', '')) or '-'}")
        st.caption("Manual updates are submitted in Product DB Edit.")


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Product Database", layout="wide")
    st.title("Product Database")
    render_product_database_ui()


if __name__ == "__main__":
    main()
