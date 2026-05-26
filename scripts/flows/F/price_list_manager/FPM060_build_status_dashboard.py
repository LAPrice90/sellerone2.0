from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_HANDOFF_PREVIEW_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    QUEUE_CONTROL_COLUMNS,
    SOURCE_ACQUISITION_COLUMNS,
    STATUS_DASHBOARD_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_row(df: pd.DataFrame, sort_column: str) -> pd.Series | None:
    if df.empty or sort_column not in df.columns:
        return None
    work = df.copy()
    work["_sort"] = work[sort_column].map(normalize_text)
    work = work.sort_values("_sort", ascending=False, kind="stable")
    return work.iloc[0] if not work.empty else None


def _latest_appended_row(df: pd.DataFrame) -> pd.Series | None:
    if df.empty:
        return None
    work = df.copy()
    work = work[work.apply(lambda row: any(normalize_text(value) for value in row.values), axis=1)]
    return work.iloc[-1] if not work.empty else None


def _handoff_summary(preview: pd.DataFrame) -> dict[str, str]:
    row = _latest_row(preview, "built_at_utc")
    if row is None:
        return {
            "state": "Preview not built",
            "supplier": "",
            "rows": "0",
            "reason": "Run the handoff preview after building the next-action decision.",
            "built_at": "",
        }
    allowed = normalize_text(row.get("live_apply_allowed", "")) == "1"
    technical_ready = normalize_text(row.get("technical_ready_flag", "")) == "1"
    approval_state = normalize_text(row.get("approval_state", ""))
    idle_status = normalize_text(row.get("f061_idle_status", ""))
    block_reason = normalize_text(row.get("block_reason", ""))
    if allowed:
        state = "Ready - approved handoff"
        reason = "F061 is idle, required fields are present, and approval matches this supplier batch. Live apply is still disabled until the approved apply phase."
    elif technical_ready and approval_state != "approved":
        state = "Ready - approval required"
        reason = block_reason or "F061 is idle and staged rows are ready, but explicit handoff approval is still required."
    elif idle_status == "busy":
        state = "Blocked - F061 busy"
        reason = block_reason or "F061 is currently busy."
    else:
        state = "Blocked"
        reason = block_reason or "Handoff guard has not allowed live apply."
    return {
        "state": state,
        "supplier": normalize_text(row.get("supplier_name", "")) or normalize_text(row.get("supplier_id", "")),
        "rows": normalize_text(row.get("staged_rows", "")) or "0",
        "reason": reason,
        "built_at": normalize_text(row.get("built_at_utc", "")),
    }


def _parse_utc(value: object) -> datetime | None:
    raw = normalize_text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _is_monthly_manual_supplier(supplier: pd.Series) -> bool:
    source_type = normalize_text(supplier.get("source_type", ""))
    priority = normalize_text(supplier.get("priority_band", "")).lower()
    refresh_days = normalize_text(supplier.get("normal_refresh_days", ""))
    if source_type != "manual_request":
        return False
    if priority == "monthly_manual":
        return True
    try:
        return int(float(refresh_days)) >= 28
    except ValueError:
        return False


def _latest_batch_month_due(
    *,
    supplier: pd.Series,
    latest_batch: pd.Series | None,
    acquisition_row: pd.Series | None,
) -> bool:
    if latest_batch is None or not _is_monthly_manual_supplier(supplier):
        return False
    batch_dt = _parse_utc(latest_batch.get("source_received_at_utc", ""))
    checked_dt = _parse_utc(acquisition_row.get("checked_at_utc", "")) if acquisition_row is not None else None
    if batch_dt is None or checked_dt is None:
        return False
    return (batch_dt.year, batch_dt.month) < (checked_dt.year, checked_dt.month)


def _status_label(batch_status: str, decision_action: str) -> str:
    status = normalize_text(batch_status).lower()
    action = normalize_text(decision_action).lower()
    if status in {"test_scan_running", "active_in_f061"}:
        return "In Progress"
    if action == "run_test_scan":
        return "Test Ready"
    if action == "recommend_test_scan":
        return "Next Scan"
    if status == "imported_from_source":
        return "Done"
    if status in {"completed", "test_scan_complete"}:
        return "Complete"
    if status in {"blocked"}:
        return "Blocked"
    return "Next"


def _source_method(supplier: pd.Series) -> str:
    source_type = normalize_text(supplier.get("source_type", ""))
    source_subtype = normalize_text(supplier.get("source_subtype", ""))
    if source_type == "api_pull" and source_subtype == "csv_link":
        return "CSV link"
    if source_type == "api_pull":
        return "API"
    if source_type == "manual_request":
        return "Email request"
    if source_type == "manual_download":
        return "Website link"
    if source_type == "email_attachment":
        return "Daily email"
    if source_type == "url_download":
        return "URL download"
    return source_type or "Unknown"


def _source_location(supplier: pd.Series, acquisition_row: pd.Series | None = None) -> str:
    if acquisition_row is not None:
        acquisition_location = normalize_text(acquisition_row.get("source_location", ""))
        if acquisition_location:
            return acquisition_location
    folder = normalize_text(supplier.get("source_folder_path", ""))
    if folder:
        return folder
    return normalize_text(supplier.get("source_url", "")) or "Not configured yet"


def _queue_control_lookup(controls: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if controls.empty:
        return out
    work = controls.copy()
    work["_updated"] = work["updated_at_utc"].map(normalize_text)
    work = work.sort_values("_updated", ascending=False, kind="stable")
    for _, row in work.iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        if not supplier_id or supplier_id in out:
            continue
        state = normalize_text(row.get("control_state", "")).lower()
        if state in {"paused", "prioritised"}:
            out[supplier_id] = {
                "control_state": state,
                "priority_rank": normalize_text(row.get("priority_rank", "")),
                "reason": normalize_text(row.get("reason", "")),
            }
    return out


def _control_display(control: dict[str, str]) -> str:
    state = normalize_text(control.get("control_state", "")).lower()
    if state == "paused":
        return "Paused"
    if state == "prioritised":
        rank = normalize_text(control.get("priority_rank", ""))
        return f"Prioritised #{rank}" if rank else "Prioritised"
    return "Normal"


def _file_state(
    *,
    supplier: pd.Series,
    latest_batch: pd.Series | None,
    acquisition_row: pd.Series | None = None,
) -> str:
    source_type = normalize_text(supplier.get("source_type", ""))
    source_subtype = normalize_text(supplier.get("source_subtype", ""))
    source_url = normalize_text(supplier.get("source_url", ""))
    monthly_due = _latest_batch_month_due(
        supplier=supplier,
        latest_batch=latest_batch,
        acquisition_row=acquisition_row,
    )
    acquisition_state = (
        normalize_text(acquisition_row.get("source_state", "")).lower() if acquisition_row is not None else ""
    )
    if latest_batch is not None and not monthly_due:
        status = normalize_text(latest_batch.get("batch_status", ""))
        if status == "blocked":
            return "Error"
        return "Ready"
    if monthly_due and acquisition_state != "ready":
        return "Missing"
    if acquisition_row is not None:
        source_state = acquisition_state
        acquisition_status = normalize_text(acquisition_row.get("status", "")).lower()
        if acquisition_status == "fail" or source_state == "error":
            return "Error"
        if source_state == "config_needed":
            return "Config Needed"
        if source_state == "missing":
            return "Missing"
        if source_state == "waiting":
            return "Waiting"
        if latest_batch is not None and source_state in {"ready", "download_ready", "green"}:
            return "Ready"
        if source_state == "ready":
            return "Ready"
        if source_state in {"download_ready", "green"}:
            return "Green"
    if source_type in {"manual_request", "manual_download"}:
        return "Missing"
    if source_type == "api_pull" and source_subtype == "csv_link" and not source_url:
        return "Config Needed"
    if source_type == "api_pull":
        return "Green"
    return "Waiting"


def _operator_action(
    *,
    supplier: pd.Series,
    file_state: str,
    latest_batch: pd.Series | None,
    acquisition_row: pd.Series | None = None,
) -> str:
    source_type = normalize_text(supplier.get("source_type", ""))
    acquisition_action = (
        normalize_text(acquisition_row.get("operator_action", "")) if acquisition_row is not None else ""
    )
    acquisition_state = (
        normalize_text(acquisition_row.get("source_state", "")).lower() if acquisition_row is not None else ""
    )
    monthly_due = _latest_batch_month_due(
        supplier=supplier,
        latest_batch=latest_batch,
        acquisition_row=acquisition_row,
    )
    if latest_batch is not None and file_state == "Ready" and acquisition_state == "ready" and acquisition_action and monthly_due:
        return acquisition_action
    if latest_batch is not None and file_state == "Ready":
        return "Price file registered"
    if acquisition_action:
        return acquisition_action
    if file_state == "Missing" and source_type == "manual_request":
        return "Request price file"
    if file_state == "Missing" and source_type == "manual_download":
        return "Download from website"
    if file_state == "Config Needed":
        return "Add source details"
    if file_state == "Error":
        return "Investigate file"
    if latest_batch is not None:
        return "Ready for test queue"
    if source_type == "api_pull":
        return "Auto pull when due"
    if source_type == "email_attachment":
        return "Await email file"
    return "Wait"


def _queue_state(*, file_state: str, bot_status: str, decision_action: str) -> str:
    if decision_action == "run_test_scan":
        return "Active"
    if decision_action == "recommend_test_scan":
        return "Recommended"
    if file_state == "Missing":
        return "Needs Manual File"
    if file_state == "Config Needed":
        return "Blocked"
    if file_state == "Error":
        return "Blocked"
    if file_state == "Green":
        return "Ready When Due"
    if bot_status in {"Complete", "Done"}:
        return "Complete"
    return "Queued"


def _acquisition_lookup(acquisition: pd.DataFrame) -> dict[str, pd.Series]:
    if acquisition.empty:
        return {}
    work = acquisition.copy()
    work["_supplier_id"] = work["supplier_id"].map(normalize_text)
    work["_checked_at"] = work["checked_at_utc"].map(normalize_text)
    work = work.sort_values(["_supplier_id", "_checked_at"], ascending=[True, False], kind="stable")
    out: dict[str, pd.Series] = {}
    for _, row in work.iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        if supplier_id and supplier_id not in out:
            out[supplier_id] = row
    return out


def _queue_sort(row: dict[str, str]) -> tuple[int, str]:
    state = normalize_text(row.get("queue_state", ""))
    order = {
        "Active": 0,
        "Recommended": 1,
        "Prioritised": 2,
        "Ready When Due": 3,
        "Queued": 4,
        "Paused": 5,
        "Needs Manual File": 6,
        "Blocked": 7,
        "Complete": 8,
    }
    return (order.get(state, 9), normalize_text(row.get("supplier_name", "")))


def _count_rows(rows: pd.DataFrame, column: str, value: str) -> int:
    if rows.empty or column not in rows.columns:
        return 0
    return int((rows[column].map(lambda raw: normalize_text(raw).lower()) == value.lower()).sum())


def _build_dashboard_rows(
    *,
    registry: pd.DataFrame,
    batches: pd.DataFrame,
    batch_rows: pd.DataFrame,
    decisions: pd.DataFrame,
    scanner_results: pd.DataFrame,
    acquisition: pd.DataFrame,
    controls: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    acquisition_by_supplier = _acquisition_lookup(acquisition)
    controls_by_supplier = _queue_control_lookup(controls)
    latest_global_decision = _latest_appended_row(decisions)
    for _, supplier in registry.iterrows():
        supplier_id = normalize_text(supplier.get("supplier_id", ""))
        supplier_name = normalize_text(supplier.get("supplier_name", ""))
        supplier_batches = batches[batches["supplier_id"].map(normalize_text) == supplier_id].copy()
        supplier_batch_rows = batch_rows[batch_rows["supplier_id"].map(normalize_text) == supplier_id].copy()
        supplier_results = scanner_results[scanner_results["supplier_id"].map(normalize_text) == supplier_id].copy()

        latest_batch = _latest_row(supplier_batches, "source_received_at_utc")
        latest_decision = (
            latest_global_decision
            if latest_global_decision is not None
            and normalize_text(latest_global_decision.get("supplier_id", "")) == supplier_id
            else None
        )
        latest_acquisition = acquisition_by_supplier.get(supplier_id)
        queue_control = controls_by_supplier.get(supplier_id, {})
        control_state = normalize_text(queue_control.get("control_state", "")).lower()
        control_label = _control_display(queue_control)

        batch_id = normalize_text(latest_batch.get("batch_id", "")) if latest_batch is not None else ""
        batch_status = normalize_text(latest_batch.get("batch_status", "")) if latest_batch is not None else ""
        decision_action = (
            normalize_text(latest_decision.get("recommended_action", "")) if latest_decision is not None else ""
        )
        bot_status = _status_label(batch_status, decision_action)
        file_state = _file_state(supplier=supplier, latest_batch=latest_batch, acquisition_row=latest_acquisition)
        if file_state == "Missing" and _latest_batch_month_due(
            supplier=supplier,
            latest_batch=latest_batch,
            acquisition_row=latest_acquisition,
        ):
            bot_status = "Missing"
        queue_state = _queue_state(file_state=file_state, bot_status=bot_status, decision_action=decision_action)
        active_rows = (
            supplier_batch_rows[supplier_batch_rows["batch_id"].map(normalize_text) == batch_id].copy()
            if batch_id
            else supplier_batch_rows
        )
        active_results = (
            supplier_results[supplier_results["batch_id"].map(normalize_text) == batch_id].copy()
            if batch_id
            else supplier_results
        )

        if not active_results.empty:
            web_pass = _count_rows(active_results, "result_status", "PASS")
            web_fail = _count_rows(active_results, "result_status", "FAIL")
            web_rescan = _count_rows(active_results, "result_status", "RESCAN")
            processed_keys = {normalize_text(value) for value in active_results["row_key"].tolist()}
            web_unprocessed = int(
                active_rows[
                    active_rows["scan_eligibility"].map(lambda value: normalize_text(value).lower()) == "scan_now"
                ]["row_key"]
                .map(lambda value: normalize_text(value) not in processed_keys)
                .sum()
            )
        else:
            web_pass = _count_rows(active_rows, "scan_eligibility", "pass")
            web_fail = _count_rows(active_rows, "scan_eligibility", "fail")
            web_rescan = _count_rows(active_rows, "scan_eligibility", "rescan")
            web_unprocessed = _count_rows(active_rows, "scan_eligibility", "scan_now")

        if latest_decision is None and web_unprocessed > 0 and file_state == "Ready":
            bot_status = "Queued"
            queue_state = "Queued"

        if (
            latest_decision is None
            and not active_results.empty
            and web_unprocessed == 0
            and (web_pass + web_fail + web_rescan) > 0
        ):
            bot_status = "Complete"
            queue_state = "Complete"

        if control_state == "paused" and queue_state not in {"Complete", "Blocked", "Needs Manual File"}:
            bot_status = "Paused"
            queue_state = "Paused"
        elif control_state == "prioritised" and queue_state == "Queued":
            bot_status = "Prioritised"
            queue_state = "Prioritised"

        rows.append(
            {
                "queue_position": "0",
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "source_method": _source_method(supplier),
                "source_location": _source_location(supplier, latest_acquisition),
                "file_state": file_state,
                "queue_state": queue_state,
                "operator_action": "Paused by operator"
                if control_state == "paused"
                else (
                    "Recommended next scan"
                    if decision_action == "recommend_test_scan"
                    else _operator_action(
                        supplier=supplier,
                        file_state=file_state,
                        latest_batch=latest_batch,
                        acquisition_row=latest_acquisition,
                    )
                ),
                "control_state": control_label,
                "price_list_date": normalize_text(latest_batch.get("source_received_at_utc", ""))
                if latest_batch is not None
                else "",
                "bot_status": bot_status if file_state != "Missing" else "Missing",
                "web_unprocessed": str(web_unprocessed),
                "web_pass": str(web_pass),
                "web_fail": str(web_fail),
                "web_rescan": str(web_rescan),
                "second_unprocessed": "0",
                "second_pass": "0",
                "second_fail": "0",
            }
        )
    sorted_rows = sorted(rows, key=_queue_sort)
    for index, row in enumerate(sorted_rows, start=1):
        row["queue_position"] = str(index)
    return pd.DataFrame(sorted_rows)


def _td(value: object, *, cls: str = "") -> str:
    class_attr = f' class="{html.escape(cls)}"' if cls else ""
    return f"<td{class_attr}>{html.escape(normalize_text(value))}</td>"


def _render_html(dashboard: pd.DataFrame, *, built_at_utc: str, handoff: dict[str, str] | None = None) -> str:
    queue_cards = []
    for _, row in dashboard.iterrows():
        state = normalize_text(row.get("queue_state", ""))
        state_class = state.lower().replace(" ", "-")
        queue_cards.append(
            f"""
      <article class="queue-card {html.escape(state_class)}">
        <div class="queue-rank">#{html.escape(normalize_text(row.get("queue_position", "")))}</div>
        <div class="queue-main">
          <div class="queue-title">{html.escape(normalize_text(row.get("supplier_name", "")))}</div>
          <div class="queue-sub">{html.escape(normalize_text(row.get("source_method", "")))} | {html.escape(normalize_text(row.get("file_state", "")))} | {html.escape(normalize_text(row.get("control_state", "")))} | {html.escape(normalize_text(row.get("operator_action", "")))}</div>
          <div class="queue-location">{html.escape(normalize_text(row.get("source_location", "")))}</div>
        </div>
        <div class="queue-counts">
          <span>{html.escape(normalize_text(row.get("web_unprocessed", "0")))} scan</span>
          <span>{html.escape(normalize_text(row.get("web_pass", "0")))} pass</span>
          <span>{html.escape(normalize_text(row.get("web_fail", "0")))} fail</span>
        </div>
        <div class="queue-controls">
          <button type="button" disabled>Pause</button>
          <button type="button" disabled>Prioritise</button>
        </div>
      </article>"""
        )

    manual_alerts = []
    manual_df = dashboard[dashboard["queue_state"].map(normalize_text) == "Needs Manual File"].copy()
    for _, row in manual_df.iterrows():
        manual_alerts.append(
            f"""
      <div class="alert-row">
        <strong>{html.escape(normalize_text(row.get("supplier_name", "")))}</strong>
        <span>{html.escape(normalize_text(row.get("source_location", "")))}</span>
        <span>{html.escape(normalize_text(row.get("operator_action", "")))}</span>
      </div>"""
        )

    table_rows = []
    for _, row in dashboard.iterrows():
        table_rows.append(
            "<tr>"
            + _td(row.get("queue_position", ""), cls="metric")
            + _td(row.get("supplier_name", ""), cls="supplier")
            + _td(row.get("source_method", ""))
            + _td(row.get("file_state", ""), cls="status")
            + _td(row.get("control_state", ""), cls="status")
            + _td(row.get("price_list_date", ""))
            + _td(row.get("bot_status", ""), cls="status")
            + '<td class="gap"></td>'
            + _td(row.get("web_unprocessed", ""), cls="metric")
            + _td(row.get("web_pass", ""), cls="metric")
            + _td(row.get("web_fail", ""), cls="metric")
            + _td(row.get("web_rescan", ""), cls="metric")
            + '<td class="gap"></td>'
            + _td(row.get("second_unprocessed", ""), cls="metric")
            + _td(row.get("second_pass", ""), cls="metric")
            + _td(row.get("second_fail", ""), cls="metric")
            + "</tr>"
        )

    queue_html = "\n".join(queue_cards)
    manual_html = "\n".join(manual_alerts) if manual_alerts else "<div class=\"empty-alert\">No manual files needed right now.</div>"
    rows_html = "\n".join(table_rows)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Price List Process Manager</title>
  <style>
    :root {{
      --grid: #d6dde3;
      --bot: #53c8d4;
      --bot-dark: #27a8bc;
      --web: #f4cc45;
      --web-soft: #fff6dc;
      --second: #58c98b;
      --second-soft: #e1f5eb;
      --text: #101820;
      --muted: #52616f;
      --panel: #ffffff;
      --panel-border: #d9e1e8;
      --danger: #b42318;
      --danger-soft: #fff1f0;
      --ready: #067647;
      --ready-soft: #ecfdf3;
    }}
    body {{
      margin: 0;
      background: #f7f9fb;
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
    }}
    main {{
      max-width: 1220px;
      margin: 20px auto;
      padding: 0 16px;
    }}
    h1 {{
      margin: 0 0 4px 0;
      font-size: 20px;
      font-weight: 700;
    }}
    .meta {{
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 12px;
    }}
    .queue-panel, .manual-panel {{
      background: var(--panel);
      border: 1px solid var(--panel-border);
      margin: 0 0 14px 0;
    }}
    .handoff-panel {{
      display: grid;
      grid-template-columns: 220px 1fr 160px;
      gap: 10px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--panel-border);
      margin: 0 0 14px 0;
      padding: 10px 12px;
    }}
    .handoff-panel.blocked {{
      border-left: 4px solid var(--danger);
    }}
    .handoff-panel.ready {{
      border-left: 4px solid var(--ready);
    }}
    .handoff-state {{
      font-weight: 700;
    }}
    .handoff-detail {{
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .handoff-rows {{
      text-align: right;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}
    .panel-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid var(--panel-border);
      font-weight: 700;
    }}
    .panel-title span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
    }}
    .queue-card {{
      display: grid;
      grid-template-columns: 44px minmax(260px, 1fr) 220px 190px;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid var(--panel-border);
    }}
    .queue-card:last-child {{
      border-bottom: 0;
    }}
    .queue-card.active {{
      background: var(--ready-soft);
    }}
    .queue-card.needs-manual-file {{
      background: var(--danger-soft);
    }}
    .queue-rank {{
      font-weight: 700;
      color: var(--muted);
    }}
    .queue-title {{
      font-weight: 700;
    }}
    .queue-sub, .queue-location {{
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .queue-counts {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }}
    .queue-counts span {{
      border: 1px solid var(--panel-border);
      padding: 5px 6px;
      text-align: center;
      background: #fff;
    }}
    .queue-controls {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }}
    button {{
      border: 1px solid #cbd5df;
      background: #f8fafc;
      color: #52616f;
      padding: 6px 8px;
      font: inherit;
    }}
    .alert-row {{
      display: grid;
      grid-template-columns: 180px minmax(260px, 1fr) 160px;
      gap: 10px;
      padding: 9px 12px;
      border-bottom: 1px solid var(--panel-border);
      background: var(--danger-soft);
      color: var(--danger);
    }}
    .alert-row:last-child {{
      border-bottom: 0;
    }}
    .empty-alert {{
      padding: 10px 12px;
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      background: white;
      border: 1px solid var(--grid);
    }}
    th, td {{
      border: 1px solid var(--grid);
      padding: 6px 8px;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    thead tr.group th {{
      font-size: 16px;
      font-weight: 700;
      color: #000;
      padding: 4px 8px;
    }}
    thead tr.columns th {{
      font-size: 13px;
      font-weight: 700;
    }}
    .bot-head {{
      background: var(--bot);
    }}
    .web-head {{
      background: var(--web);
    }}
    .second-head {{
      background: var(--second);
    }}
    .bot-col {{
      background: #d9f4f7;
    }}
    .web-col {{
      background: var(--web-soft);
    }}
    .second-col {{
      background: var(--second-soft);
    }}
    tbody tr:nth-child(even) .bot-col {{
      background: #eefbfc;
    }}
    tbody tr:nth-child(even) .web-col {{
      background: #fffbef;
    }}
    tbody tr:nth-child(even) .second-col {{
      background: #f1fbf6;
    }}
    .supplier {{
      font-weight: 700;
      text-align: left;
    }}
    .status {{
      font-weight: 700;
    }}
    .metric {{
      font-variant-numeric: tabular-nums;
    }}
    .gap {{
      width: 18px;
      background: #edf1f5;
      border-top-color: #edf1f5;
      border-bottom-color: #edf1f5;
    }}
    @media (max-width: 820px) {{
      main {{
        margin: 12px auto;
        padding: 0 8px;
      }}
      table {{
        min-width: 980px;
      }}
      .table-wrap {{
        overflow-x: auto;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Price List Process Manager</h1>
    <div class="meta">Built at {html.escape(built_at_utc)}. Automatic handoff runs when the active scan finishes.</div>
    <section class="queue-panel">
      <div class="panel-title">Queue <span>Pause and prioritise controls are preview-only in test mode.</span></div>
      {queue_html}
    </section>
    <section class="manual-panel">
      <div class="panel-title">Manual File Alerts <span>Missing files move down the queue so API pulls can continue.</span></div>
      {manual_html}
    </section>
    <div class="table-wrap">
      <table>
        <thead>
          <tr class="group">
            <th class="bot-head" colspan="7">Bot Status</th>
            <th class="gap"></th>
            <th class="web-head" colspan="4">Web Scraper</th>
            <th class="gap"></th>
            <th class="second-head" colspan="3">Second Checks</th>
          </tr>
          <tr class="columns">
            <th class="bot-head">Queue</th>
            <th class="bot-head">Price List Imports</th>
            <th class="bot-head">Method</th>
            <th class="bot-head">File</th>
            <th class="bot-head">Control</th>
            <th class="bot-head">Date</th>
            <th class="bot-head">Status</th>
            <th class="gap"></th>
            <th class="web-head">Unprocessed</th>
            <th class="web-head">PASS</th>
            <th class="web-head">FAIL</th>
            <th class="web-head">RE SCAN</th>
            <th class="gap"></th>
            <th class="second-head">Unprocessed</th>
            <th class="second-head">PASS</th>
            <th class="second-head">FAIL</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </main>
</body>
</html>
"""


def build_status_dashboard(root: Path | None = None, *, built_at_utc: str | None = None) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    built_at = built_at_utc or _utc_now_iso()
    test_dir = paths.test_mode_dir

    registry = read_csv(test_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    batches = read_csv(test_dir / "price_list_batches.csv", PRICE_LIST_BATCH_COLUMNS)
    batch_rows = read_csv(test_dir / "batch_rows.csv", BATCH_ROW_COLUMNS)
    decisions = read_csv(test_dir / "manager_decisions.csv", MANAGER_DECISION_COLUMNS)
    scanner_results = read_csv(test_dir / "placeholder_scanner_results.csv", PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    acquisition = read_csv(test_dir / "source_acquisition_status.csv", SOURCE_ACQUISITION_COLUMNS)
    controls = read_csv(test_dir / "queue_controls.csv", QUEUE_CONTROL_COLUMNS)
    handoff_preview = read_csv(test_dir / "f061_handoff_preview.csv", F061_HANDOFF_PREVIEW_COLUMNS)

    if registry.empty:
        raise FileNotFoundError("supplier_registry.csv is required before building the status dashboard")

    dashboard = _build_dashboard_rows(
        registry=registry,
        batches=batches,
        batch_rows=batch_rows,
        decisions=decisions,
        scanner_results=scanner_results,
        acquisition=acquisition,
        controls=controls,
    )
    dashboard = write_csv(test_dir / "status_dashboard.csv", dashboard, STATUS_DASHBOARD_COLUMNS)

    html_path = test_dir / "status_dashboard.html"
    html_path.write_text(
        _render_html(dashboard, built_at_utc=built_at, handoff=_handoff_summary(handoff_preview)),
        encoding="utf-8",
    )

    summary = {
        "status": "success",
        "dashboard_rows": int(len(dashboard)),
        "web_unprocessed_total": int(pd.to_numeric(dashboard["web_unprocessed"], errors="coerce").fillna(0).sum()),
        "html_path": str(html_path),
        "csv_path": str(test_dir / "status_dashboard.csv"),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build price-list manager status dashboard.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--built-at-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_status_dashboard(root=root, built_at_utc=args.built_at_utc)


if __name__ == "__main__":
    main()
