from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O050_build_repricing_tracker_view import (
    build_repricing_tracker_glance_df,
    build_repricing_tracker_view,
    filter_repricing_tracker_view,
    load_repricing_tracker_view,
    repricer_tracker_counts,
)
from scripts.flows.O._contract_io import read_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def load_repricer_tracker_health(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    return read_o_contract_df(root_path, "repricer_tracker_health")


def render_repricing_tracker_ui(root: Path | None = None) -> None:
    import streamlit as st

    root_path = Path(root) if root is not None else get_o_path_contract().root
    view_df = load_repricing_tracker_view(root=root_path)
    if view_df.empty:
        view_df = build_repricing_tracker_view(root=root_path)
    health_df = load_repricer_tracker_health(root=root_path)

    st.subheader("Repricer Tracker")
    st.caption("Read-only tracker from H pricing outputs. The Sheet remains temporary until this view is proven.")

    counts = repricer_tracker_counts(view_df)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Rows", str(counts["rows"]))
    c2.metric("Latest Run", str(counts["latest_run_rows"]))
    c3.metric("Eligible", str(counts["eligible_to_write"]))
    c4.metric("Attempted", str(counts["write_attempted"]))
    c5.metric("Applied", str(counts["write_applied"]))
    c6.metric("Missing Status", str(counts["missing_write_status"]))

    if not health_df.empty:
        fail_count = int(health_df.get("status", "").map(lambda v: _normalize_text(v).lower() == "fail").sum())
        warn_count = int(health_df.get("status", "").map(lambda v: _normalize_text(v).lower() == "warn").sum())
        if fail_count or warn_count:
            st.warning(f"Tracker health: {fail_count} fail, {warn_count} warn.")
        with st.expander("Tracker health"):
            st.dataframe(health_df, use_container_width=True, hide_index=True)

    if view_df.empty:
        st.info("No repricer tracker rows available.")
        return

    statuses = ["All statuses", *sorted({_normalize_text(v) for v in view_df.get("tracker_status", "").tolist() if _normalize_text(v)})]
    controls_a, controls_b, controls_c, controls_d = st.columns([2, 2, 1, 1])
    search_text = controls_a.text_input("Search SKU / ASIN / State", value="", key="o_repricer_tracker_search")
    status_filter = controls_b.selectbox("Status", options=statuses, key="o_repricer_tracker_status")
    current_run_only = controls_c.checkbox("Latest Run", value=True, key="o_repricer_tracker_current_run_only")
    issues_only = controls_d.checkbox("Issues", value=False, key="o_repricer_tracker_issues_only")
    writes_only = st.checkbox("Writes only", value=False, key="o_repricer_tracker_writes_only")

    filtered = filter_repricing_tracker_view(
        view_df,
        search_text=search_text,
        status_filter=status_filter,
        current_run_only=current_run_only,
        issues_only=issues_only,
        writes_only=writes_only,
    )
    st.caption(f"Showing {len(filtered.index)} rows.")
    if filtered.empty:
        st.info("No rows match current filters.")
        return

    st.dataframe(build_repricing_tracker_glance_df(filtered), use_container_width=True, hide_index=True)

    sku_options = filtered.get("sku", pd.Series(dtype=str)).astype(str).tolist()
    selected_sku = st.selectbox("View Details", options=["", *sku_options], key="o_repricer_tracker_detail_sku")
    if _normalize_text(selected_sku) == "":
        return

    selected_rows = filtered[filtered["sku"].astype(str) == selected_sku].copy()
    if selected_rows.empty:
        return
    row = selected_rows.iloc[0].to_dict()
    with st.expander(f"{selected_sku} pricing detail", expanded=True):
        st.markdown("**Decision Chain**")
        st.markdown(f"Eligible to write: {_normalize_text(row.get('eligible_to_write_flag', '0'))}")
        st.markdown(f"Decision to change price: {_normalize_text(row.get('decision_to_change_price_flag', '0'))}")
        st.markdown(f"Write attempted: {_normalize_text(row.get('write_attempted_flag', '0'))}")
        st.markdown(f"Write applied: {_normalize_text(row.get('write_applied_flag', '0'))}")

        st.markdown("**Price Context**")
        st.markdown(f"Old price: {_normalize_text(row.get('old_price_gbp', '')) or '-'}")
        st.markdown(f"New price: {_normalize_text(row.get('new_price_gbp', '')) or '-'}")
        st.markdown(f"Hard floor: {_normalize_text(row.get('hard_floor_gbp', '')) or '-'}")
        st.markdown(f"Ceiling: {_normalize_text(row.get('ceiling_gbp', '')) or '-'}")
        st.markdown(f"True binding ceiling: {_normalize_text(row.get('true_binding_ceiling_gbp', '')) or '-'}")

        st.markdown("**Runtime Truth**")
        st.markdown(f"Tracker status: {_normalize_text(row.get('tracker_status', '')) or '-'}")
        st.markdown(f"Execution state: {_normalize_text(row.get('execution_state', '')) or '-'}")
        st.markdown(f"Write result: {_normalize_text(row.get('raw_execution_write_status', '')) or '-'}")
        st.markdown(f"Write issue: {_normalize_text(row.get('write_status_issue', '')) or 'none'}")
        st.markdown(f"Write error: {_normalize_text(row.get('execution_write_error', '')) or '-'}")
        st.markdown(f"Run: {_normalize_text(row.get('source_run_id', '')) or '-'}")
        st.markdown(f"Latest terminal run: {_normalize_text(row.get('latest_terminal_run_id', '')) or '-'}")
        st.markdown(f"Latest-run row: {'1' if _truthy(row.get('is_latest_terminal_run', '')) else '0'}")


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Repricer Tracker", layout="wide")
    st.title("Repricer Tracker")
    render_repricing_tracker_ui()


if __name__ == "__main__":
    main()
