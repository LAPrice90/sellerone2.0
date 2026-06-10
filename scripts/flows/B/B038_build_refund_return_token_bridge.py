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
REFUND_BRIDGE_REL = Path("out/systems/B/refunds/b_refund_pnl_bridge.csv")
AMAZON_RETURN_REPORT_RELS = [
    Path("out/systems/B/refunds/b_fba_customer_returns.csv"),
    Path("out/systems/M/b_refund_return_api_probe/b_fba_customer_returns_probe.csv"),
    Path("out/fba_customer_returns.csv"),
]
TOKEN_LEDGER_REL = Path("out/token_ledger_live.csv")
TOKEN_RETURN_LEDGER_REL = Path("out/token_return_ledger.csv")
OUT_BRIDGE_REL = Path("out/systems/B/refunds/b_refund_return_token_bridge.csv")
OUT_SUMMARY_REL = Path("out/systems/B/refunds/b_refund_return_token_summary.csv")

BRIDGE_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "api_refund_proof_state",
    "refund_money_state",
    "refund_units",
    "refund_price_total",
    "amazon_return_proof_state",
    "amazon_return_date",
    "amazon_return_quantity",
    "amazon_return_disposition",
    "amazon_return_status",
    "amazon_return_reason",
    "token_return_state",
    "returned_pending_tokens",
    "returned_complete_tokens",
    "reusable_return_tokens",
    "available_return_tokens",
    "allocated_reusable_return_tokens",
    "research_pending_tokens",
    "unsellable_tokens",
    "unsafe_original_return_tokens",
    "unsafe_original_token_ids",
    "return_cogs_recovered_exvat",
    "return_cogs_source",
    "blocked_return_cogs_exvat",
    "blocked_return_cogs_source",
    "sellerboard_match_state",
    "proof_label",
    "roi_stock_recovery_state",
    "mismatch_state",
    "manager_action",
    "notes",
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


def _first_present(df: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in df.columns:
            return df[name].astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype=str)


def _first_non_blank(values: pd.Series) -> str:
    for value in values.tolist():
        text = _text(value)
        if text:
            return text
    return ""


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_amazon_return_report(root: Path) -> Path | None:
    for rel_path in AMAZON_RETURN_REPORT_RELS:
        path = root / rel_path
        if path.exists():
            return path
    return None


def _choose_disposition(dispositions: list[str]) -> str:
    cleaned = [_text(value).upper() for value in dispositions if _text(value)]
    if not cleaned:
        return ""
    if "SELLABLE" in cleaned:
        return "SELLABLE"
    if "RESEARCHING" in cleaned:
        return "RESEARCHING"
    return cleaned[0]


def _load_amazon_returns(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if path is None:
        return {}
    rows = _read_csv(path)
    if rows.empty:
        return {}
    work = rows.copy()
    work["order_id_norm"] = _first_present(work, ["order-id", "order_id", "amazon_order_id"]).map(_text)
    work["sku_norm"] = _first_present(work, ["sku", "seller-sku", "seller_sku", "SKU"]).map(_norm_sku)
    work["return_date_norm"] = _first_present(work, ["return-date", "return_date", "returnDate"]).map(_text)
    work["quantity_num"] = pd.to_numeric(_first_present(work, ["quantity", "qty", "Quantity"]), errors="coerce").fillna(0.0).abs()
    work.loc[work["quantity_num"] <= 0, "quantity_num"] = 1.0
    work["disposition_norm"] = _first_present(work, ["detailed-disposition", "detailed_disposition", "disposition"]).map(
        lambda value: _text(value).upper()
    )
    work["status_norm"] = _first_present(work, ["status", "return_status"]).map(_text)
    work["reason_norm"] = _first_present(work, ["reason", "return_reason"]).map(_text)
    work = work[(work["order_id_norm"] != "") & (work["sku_norm"] != "")]
    out: dict[tuple[str, str], dict[str, str]] = {}
    for (order_id, sku), group in work.groupby(["order_id_norm", "sku_norm"], dropna=False):
        dates = sorted([_text(value) for value in group["return_date_norm"].tolist() if _text(value)])
        dispositions = sorted({_text(value).upper() for value in group["disposition_norm"].tolist() if _text(value)})
        out[(order_id, sku)] = {
            "return_date": dates[-1] if dates else "",
            "quantity": _num_text(float(group["quantity_num"].sum())),
            "disposition": _choose_disposition(dispositions),
            "status": _first_non_blank(group["status_norm"]),
            "reason": _first_non_blank(group["reason_norm"]),
        }
    return out


def _empty_token_state() -> dict[str, object]:
    return {
        "returned_pending_tokens": 0,
        "returned_complete_tokens": 0,
        "reusable_return_tokens": 0,
        "available_return_tokens": 0,
        "allocated_reusable_return_tokens": 0,
        "research_pending_tokens": 0,
        "unsellable_tokens": 0,
        "unsafe_original_return_tokens": 0,
        "available_token_ids": [],
        "reusable_token_ids": [],
        "unsafe_original_token_ids": [],
        "return_event_ids": [],
    }


def _load_token_states(path: Path) -> dict[tuple[str, str], dict[str, object]]:
    ledger = _read_csv(path)
    if ledger.empty or "seller_sku" not in ledger.columns:
        return {}
    work = ledger.copy()
    for column in ["token_id", "status", "return_order_id", "last_return_order_id", "notes"]:
        if column not in work.columns:
            work[column] = ""
    states: dict[tuple[str, str], dict[str, object]] = {}
    seen: set[tuple[tuple[str, str], str, str]] = set()
    for _, row in work.iterrows():
        sku = _norm_sku(row.get("seller_sku", ""))
        if not sku:
            continue
        order_ids = {
            _text(row.get("return_order_id", "")),
            _text(row.get("last_return_order_id", "")),
        }
        order_ids.discard("")
        if not order_ids:
            continue
        token_id = _text(row.get("token_id", ""))
        status = _text(row.get("status", "")).lower()
        for order_id in order_ids:
            key = (order_id, sku)
            seen_key = (key, token_id, status)
            if seen_key in seen:
                continue
            seen.add(seen_key)
            state = states.setdefault(key, _empty_token_state())
            notes = _text(row.get("notes", "")).lower()
            note_text = _text(row.get("notes", ""))
            is_reusable_return_token = (
                "return_sellable_dup" in notes
                and _text(row.get("last_return_order_id", "")) == order_id
                and status in {"available", "allocated", "warehouse"}
            )
            is_original_return_lifecycle_token = any(
                marker in notes
                for marker in [
                    "return_closed",
                    "return_unsellable",
                    "return_researching",
                    "researching_negative",
                ]
            )
            has_live_status = status in {"available", "allocated", "warehouse"}
            if is_reusable_return_token:
                state["reusable_return_tokens"] = int(state["reusable_return_tokens"]) + 1
                state["reusable_token_ids"] = [*state["reusable_token_ids"], token_id]
                if status == "available":
                    state["available_return_tokens"] = int(state["available_return_tokens"]) + 1
                    state["available_token_ids"] = [*state["available_token_ids"], token_id]
                if status == "allocated":
                    state["allocated_reusable_return_tokens"] = int(state["allocated_reusable_return_tokens"]) + 1
            elif is_original_return_lifecycle_token and has_live_status:
                state["unsafe_original_return_tokens"] = int(state["unsafe_original_return_tokens"]) + 1
                state["unsafe_original_token_ids"] = [*state["unsafe_original_token_ids"], token_id]
            if status == "returned_pending":
                state["returned_pending_tokens"] = int(state["returned_pending_tokens"]) + 1
            elif status == "returned_complete":
                state["returned_complete_tokens"] = int(state["returned_complete_tokens"]) + 1
            elif status == "research_pending":
                state["research_pending_tokens"] = int(state["research_pending_tokens"]) + 1
            elif status == "unsellable":
                state["unsellable_tokens"] = int(state["unsellable_tokens"]) + 1
            event_ids = list(state.get("return_event_ids", []))
            if _text(row.get("return_order_id", "")) == order_id:
                event_ids.append(_text(row.get("return_event_id", "")))
            if _text(row.get("last_return_order_id", "")) == order_id:
                event_ids.append(_text(row.get("last_return_event_id", "")))
            if _text(row.get("last_return_order_id", "")) == order_id:
                if "return_closed:" in note_text:
                    event_ids.append(note_text.split("return_closed:", 1)[1].split(";", 1)[0].strip())
                if status in {"available", "allocated", "warehouse"} and "return_sellable_dup:" in note_text:
                    event_ids.append(note_text.split("return_sellable_dup:", 1)[1].split(";", 1)[0].strip())
            state["return_event_ids"] = [event_id for event_id in dict.fromkeys(event_ids) if event_id]
    return states


def _load_return_cogs_by_token(path: Path) -> dict[str, float]:
    rows = _read_csv(path)
    if rows.empty or "token_id" not in rows.columns:
        return {}
    rows = rows.copy()
    cost_col = "token_cost" if "token_cost" in rows.columns else "cost_per_unit"
    if cost_col not in rows.columns:
        return {}
    rows["cost_num"] = pd.to_numeric(rows[cost_col], errors="coerce").fillna(0.0)
    out: dict[str, float] = {}
    for token_id, group in rows.groupby(rows["token_id"].map(_text), dropna=False):
        if token_id:
            out[token_id] = float(group["cost_num"].sum())
    return out


def _load_return_cogs_by_event(path: Path) -> dict[str, list[tuple[str, float]]]:
    rows = _read_csv(path)
    if rows.empty or "return_event_id" not in rows.columns:
        return {}
    work = rows.copy()
    for column in ["return_event_id", "token_id", "token_cost", "cost_per_unit"]:
        if column not in work.columns:
            work[column] = ""
    cost_col = "token_cost" if "token_cost" in work.columns else "cost_per_unit"
    work["cost_num"] = pd.to_numeric(work[cost_col], errors="coerce").fillna(0.0)
    out: dict[str, list[tuple[str, float]]] = {}
    for _, row in work.iterrows():
        event_id = _text(row.get("return_event_id", ""))
        token_id = _text(row.get("token_id", ""))
        if not event_id or not token_id:
            continue
        out.setdefault(event_id, []).append((token_id, float(row.get("cost_num", 0.0))))
    return out


def _load_refund_rows(path: Path) -> pd.DataFrame:
    rows = _read_csv(path)
    if rows.empty:
        return pd.DataFrame(columns=["order_id", "sku", "api_refund_proof_state"])
    rows = rows.copy()
    for column in [
        "order_id",
        "sku",
        "refund_posted_date",
        "api_refund_proof_state",
        "refund_units",
        "refund_price_total",
        "return_cogs_recovered_exvat",
        "sellerboard_match_state",
    ]:
        if column not in rows.columns:
            rows[column] = ""
    rows["order_id"] = rows["order_id"].map(_text)
    rows["sku"] = rows["sku"].map(_norm_sku)
    return rows[(rows["order_id"] != "") & (rows["sku"] != "")].copy()


def _token_return_state(token_state: dict[str, object]) -> str:
    if int(token_state.get("reusable_return_tokens", 0)) > 0:
        return "reusable_return_token_seen"
    if int(token_state.get("available_return_tokens", 0)) > 0:
        return "available_return_token_seen"
    if int(token_state.get("returned_complete_tokens", 0)) > 0:
        return "returned_complete_no_available_token_seen"
    if int(token_state.get("returned_pending_tokens", 0)) > 0:
        return "returned_pending"
    if int(token_state.get("research_pending_tokens", 0)) > 0:
        return "research_pending"
    if int(token_state.get("unsellable_tokens", 0)) > 0:
        return "unsellable"
    if int(token_state.get("unsafe_original_return_tokens", 0)) > 0:
        return "original_return_token_live_status_conflict"
    return "no_token_return_state"


def _classify(
    *,
    api_refund_state: str,
    amazon_return: dict[str, str] | None,
    token_state: dict[str, object],
    return_cogs: float,
) -> tuple[str, str, str, str, str]:
    reusable = int(token_state.get("reusable_return_tokens", 0))
    unsafe_original = int(token_state.get("unsafe_original_return_tokens", 0))
    unsafe_reuse = reusable > 0 or unsafe_original > 0
    disposition = _text((amazon_return or {}).get("disposition", "")).upper()
    has_amazon_return = amazon_return is not None

    if api_refund_state == "sellerboard_bridge_only":
        return (
            "sellerboard_witness_only",
            "not_safe_sellerboard_only",
            "warning",
            "Wait for API refund proof. Sellerboard is only a witness.",
            "sellerboard return row has no API refund money proof",
        )
    if not has_amazon_return:
        if reusable > 0 or return_cogs > 0:
            return (
                "token_reuse_without_amazon_return_proof",
                "not_safe_token_reuse_unproved",
                "warning",
                "Create a bounded B repair task to prove the Amazon return event before trusting stock recovery.",
                "token reuse exists but Amazon return proof is missing",
            )
        if unsafe_original > 0:
            return (
                "token_reuse_without_amazon_return_proof",
                "not_safe_original_return_token_status_conflict",
                "warning",
                "Create a bounded B repair task to prove why the original returned token has a live stock status.",
                "original returned token has live status but Amazon return proof is missing",
            )
        return (
            "refund_without_return_proof",
            "refund_money_only_no_stock_recovery",
            "ok",
            "No token action. Treat this as refund money without stock recovery proof.",
            "API refund exists but no Amazon return report row was matched",
        )
    if disposition == "SELLABLE":
        if reusable > 0:
            if return_cogs > 0:
                return (
                    "returned_sellable_token_reused",
                    "stock_recovery_api_and_token_proved",
                    "ok",
                    "No repair needed. Sellable return and token reuse agree.",
                    "",
                )
            return (
                "returned_sellable_token_reused",
                "stock_recovery_token_proved_cogs_not_yet_proven",
                "warning",
                "Create a bounded B repair task to prove the return COGS ledger caught the reusable token.",
                "sellable token reuse exists but return COGS proof is missing",
            )
        if int(token_state.get("unsellable_tokens", 0)) > 0 or int(token_state.get("research_pending_tokens", 0)) > 0:
            return (
                "returned_sellable_later_unsellable_no_reuse",
                "stock_recovery_blocked_by_token_disposal",
                "ok",
                "No reusable stock recovery. Token evidence says the returned item is no longer sellable.",
                "",
            )
        return (
            "returned_sellable_token_missing",
            "stock_recovery_missing_token_reuse",
            "warning",
            "Create a bounded B repair task for the normal B009 token-return route. Do not create tokens from this bridge.",
            "Amazon says sellable but reusable token proof is missing",
        )
    if disposition == "RESEARCHING":
        return (
            "return_research_pending",
            "not_safe_researching",
            "warning" if unsafe_reuse else "ok",
            "Keep out of reusable stock until Amazon or the token system proves sellable.",
            "researching return has reusable token evidence" if unsafe_reuse else "",
        )
    return (
        "returned_unsellable_no_reuse",
        "not_safe_unsellable",
        "warning" if unsafe_reuse or return_cogs > 0 else "ok",
        "Keep out of reusable stock. Investigate if any reusable token or return COGS recovery evidence exists.",
        (
            "non-sellable return has reusable token evidence"
            if unsafe_reuse
            else ("non-sellable return has return COGS recovery evidence" if return_cogs > 0 else "")
        ),
    )


def build_refund_return_token_bridge(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, object]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    refund_rows = _load_refund_rows(root_path / REFUND_BRIDGE_REL)
    amazon_report_path = _find_amazon_return_report(root_path)
    amazon_returns = _load_amazon_returns(amazon_report_path)
    token_states = _load_token_states(root_path / TOKEN_LEDGER_REL)
    cogs_by_token = _load_return_cogs_by_token(root_path / TOKEN_RETURN_LEDGER_REL)
    cogs_by_event = _load_return_cogs_by_event(root_path / TOKEN_RETURN_LEDGER_REL)

    refund_keys = {(row["order_id"], row["sku"]) for _, row in refund_rows.iterrows()}
    reuse_without_refund_keys = {
        key
        for key, state in token_states.items()
        if key not in refund_keys and int(state.get("reusable_return_tokens", 0)) > 0
    }

    rows: list[dict[str, object]] = []
    for _, refund in refund_rows.iterrows():
        order_id = _text(refund.get("order_id", ""))
        sku = _norm_sku(refund.get("sku", ""))
        key = (order_id, sku)
        token_state = token_states.get(key, _empty_token_state())
        token_ids = [token_id for token_id in token_state.get("reusable_token_ids", []) if token_id]
        event_token_costs: list[tuple[str, float]] = []
        for event_id in token_state.get("return_event_ids", []):
            event_token_costs.extend(cogs_by_event.get(event_id, []))
        event_token_ids = [token_id for token_id, _ in event_token_costs if token_id]
        for token_id in event_token_ids:
            if token_id not in token_ids:
                token_ids.append(token_id)
        cogs_from_return_ledger = sum(cogs_by_token.get(token_id, 0.0) for token_id in token_ids)
        if cogs_from_return_ledger <= 0 and event_token_costs:
            cogs_from_return_ledger = sum(cost for _, cost in event_token_costs)
        bridge_cogs = _num(refund.get("return_cogs_recovered_exvat", ""))
        amazon_return = amazon_returns.get(key)
        disposition = _text((amazon_return or {}).get("disposition", "")).upper()
        raw_return_cogs = cogs_from_return_ledger if cogs_from_return_ledger > 0 else bridge_cogs
        raw_return_cogs_source = "token_return_ledger" if cogs_from_return_ledger > 0 else ("refund_bridge" if bridge_cogs > 0 else "")
        blocked_return_cogs = 0.0
        blocked_return_cogs_source = ""
        return_cogs = raw_return_cogs
        return_cogs_source = raw_return_cogs_source
        classification_return_cogs = raw_return_cogs
        if raw_return_cogs > 0 and (amazon_return is None or disposition != "SELLABLE"):
            blocked_return_cogs = raw_return_cogs
            blocked_return_cogs_source = raw_return_cogs_source
            return_cogs = 0.0
            return_cogs_source = ""
            classification_return_cogs = raw_return_cogs if amazon_return is None else 0.0
        if event_token_ids and _text((amazon_return or {}).get("disposition", "")).upper() == "SELLABLE":
            token_state["reusable_return_tokens"] = max(
                int(token_state.get("reusable_return_tokens", 0)),
                len(set(event_token_ids)),
            )
        api_refund_state = _text(refund.get("api_refund_proof_state", ""))
        refund_money_state = "api_proved" if api_refund_state == "api_proved" else api_refund_state or "not_yet_proven"
        proof_label, roi_state, mismatch_state, manager_action, notes = _classify(
            api_refund_state=api_refund_state,
            amazon_return=amazon_return,
            token_state=token_state,
            return_cogs=classification_return_cogs,
        )
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "refund_posted_date": _text(refund.get("refund_posted_date", "")),
                "api_refund_proof_state": api_refund_state,
                "refund_money_state": refund_money_state,
                "refund_units": _num_text(refund.get("refund_units", "")),
                "refund_price_total": _num_text(refund.get("refund_price_total", "")),
                "amazon_return_proof_state": "api_return_report_pulled" if amazon_return else "not_yet_proven",
                "amazon_return_date": _text((amazon_return or {}).get("return_date", "")),
                "amazon_return_quantity": _num_text((amazon_return or {}).get("quantity", "")),
                "amazon_return_disposition": _text((amazon_return or {}).get("disposition", "")),
                "amazon_return_status": _text((amazon_return or {}).get("status", "")),
                "amazon_return_reason": _text((amazon_return or {}).get("reason", "")),
                "token_return_state": _token_return_state(token_state),
                "returned_pending_tokens": str(token_state.get("returned_pending_tokens", 0)),
                "returned_complete_tokens": str(token_state.get("returned_complete_tokens", 0)),
                "reusable_return_tokens": str(token_state.get("reusable_return_tokens", 0)),
                "available_return_tokens": str(token_state.get("available_return_tokens", 0)),
                "allocated_reusable_return_tokens": str(token_state.get("allocated_reusable_return_tokens", 0)),
                "research_pending_tokens": str(token_state.get("research_pending_tokens", 0)),
                "unsellable_tokens": str(token_state.get("unsellable_tokens", 0)),
                "unsafe_original_return_tokens": str(token_state.get("unsafe_original_return_tokens", 0)),
                "unsafe_original_token_ids": "|".join(
                    [token_id for token_id in token_state.get("unsafe_original_token_ids", []) if token_id]
                ),
                "return_cogs_recovered_exvat": _num_text(return_cogs),
                "return_cogs_source": return_cogs_source,
                "blocked_return_cogs_exvat": _num_text(blocked_return_cogs),
                "blocked_return_cogs_source": blocked_return_cogs_source,
                "sellerboard_match_state": _text(refund.get("sellerboard_match_state", "")),
                "proof_label": proof_label,
                "roi_stock_recovery_state": roi_state,
                "mismatch_state": mismatch_state,
                "manager_action": manager_action,
                "notes": notes,
            }
        )

    for order_id, sku in sorted(reuse_without_refund_keys):
        token_state = token_states[(order_id, sku)]
        token_ids = [token_id for token_id in token_state.get("reusable_token_ids", []) if token_id]
        cogs_from_return_ledger = sum(cogs_by_token.get(token_id, 0.0) for token_id in token_ids)
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "refund_posted_date": "",
                "api_refund_proof_state": "not_yet_proven",
                "refund_money_state": "not_yet_proven",
                "refund_units": "0",
                "refund_price_total": "0",
                "amazon_return_proof_state": "not_yet_proven",
                "amazon_return_date": "",
                "amazon_return_quantity": "0",
                "amazon_return_disposition": "",
                "amazon_return_status": "",
                "amazon_return_reason": "",
                "token_return_state": _token_return_state(token_state),
                "returned_pending_tokens": str(token_state.get("returned_pending_tokens", 0)),
                "returned_complete_tokens": str(token_state.get("returned_complete_tokens", 0)),
                "reusable_return_tokens": str(token_state.get("reusable_return_tokens", 0)),
                "available_return_tokens": str(token_state.get("available_return_tokens", 0)),
                "allocated_reusable_return_tokens": str(token_state.get("allocated_reusable_return_tokens", 0)),
                "research_pending_tokens": str(token_state.get("research_pending_tokens", 0)),
                "unsellable_tokens": str(token_state.get("unsellable_tokens", 0)),
                "unsafe_original_return_tokens": str(token_state.get("unsafe_original_return_tokens", 0)),
                "unsafe_original_token_ids": "|".join(
                    [token_id for token_id in token_state.get("unsafe_original_token_ids", []) if token_id]
                ),
                "return_cogs_recovered_exvat": "0",
                "return_cogs_source": "",
                "blocked_return_cogs_exvat": _num_text(cogs_from_return_ledger),
                "blocked_return_cogs_source": "token_return_ledger" if cogs_from_return_ledger > 0 else "",
                "sellerboard_match_state": "",
                "proof_label": "token_reuse_without_amazon_return_proof",
                "roi_stock_recovery_state": "not_safe_token_reuse_unproved",
                "mismatch_state": "warning",
                "manager_action": "Create a bounded B repair task to prove the refund and Amazon return before trusting stock recovery.",
                "notes": "reusable returned token exists without matching refund bridge row",
            }
        )

    bridge = pd.DataFrame(rows, columns=BRIDGE_COLUMNS).fillna("")
    summary_values = {
        "observed_utc": observed,
        "refund_bridge_rows": str(len(refund_rows)),
        "amazon_return_rows": str(len(amazon_returns)),
        "bridge_rows": str(len(bridge)),
        "api_refund_rows": str((bridge["api_refund_proof_state"] == "api_proved").sum()) if not bridge.empty else "0",
        "sellerboard_witness_only_rows": str((bridge["proof_label"] == "sellerboard_witness_only").sum()) if not bridge.empty else "0",
        "refund_without_return_proof_rows": str((bridge["proof_label"] == "refund_without_return_proof").sum()) if not bridge.empty else "0",
        "returned_sellable_token_reused_rows": str((bridge["proof_label"] == "returned_sellable_token_reused").sum()) if not bridge.empty else "0",
        "returned_sellable_token_missing_rows": str((bridge["proof_label"] == "returned_sellable_token_missing").sum()) if not bridge.empty else "0",
        "token_reuse_without_amazon_return_proof_rows": str((bridge["proof_label"] == "token_reuse_without_amazon_return_proof").sum()) if not bridge.empty else "0",
        "blocked_return_cogs_rows": str((bridge["blocked_return_cogs_exvat"].map(_num) > 0).sum()) if not bridge.empty else "0",
        "blocked_return_cogs_total": _num_text(bridge["blocked_return_cogs_exvat"].map(_num).sum()) if not bridge.empty else "0",
        "warning_rows": str((bridge["mismatch_state"] == "warning").sum()) if not bridge.empty else "0",
        "amazon_return_report_path": str(amazon_report_path or ""),
    }
    summary = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in summary_values.items()],
        columns=SUMMARY_COLUMNS,
    )
    return {
        "bridge": bridge,
        "summary": summary,
        "output_bridge": root_path / OUT_BRIDGE_REL,
        "output_summary": root_path / OUT_SUMMARY_REL,
    }


def write_refund_return_token_bridge_outputs(result: dict[str, object]) -> dict[str, Path]:
    bridge_path = Path(result["output_bridge"])
    summary_path = Path(result["output_summary"])
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["bridge"], bridge_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"bridge": bridge_path, "summary": summary_path}


def main() -> None:
    result = build_refund_return_token_bridge()
    paths = write_refund_return_token_bridge_outputs(result)
    bridge = result["bridge"]
    summary = result["summary"]
    warning_rows = "0"
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        rows = summary.loc[summary["metric"] == "warning_rows", "value"].tolist()
        warning_rows = rows[0] if rows else "0"
    print(
        {
            "status": "success",
            "bridge_rows": int(len(bridge)),
            "warning_rows": int(float(warning_rows or 0)),
            "snapshot": str(paths["bridge"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
