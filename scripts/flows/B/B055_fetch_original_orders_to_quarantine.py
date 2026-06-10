from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Protocol

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv
from sellerone_manager.b_order_recovery import EXPECTED_QUARANTINE_REL_PATH, QUARANTINE_REQUIRED_COLUMNS
from sellerone_manager.b_order_recovery_scanner import (
    SpApiOrderRecoveryClient,
    _merge_quarantine_row,
    _quarantine_row,
)


OUT = Path("out")
SOURCE_PROOF = OUT / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv"
ORDERS_ALL = OUT / "orders_all.csv"
RESULTS = OUT / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_results.csv"
SUMMARY = OUT / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_summary.csv"
MANIFEST = OUT / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_manifest.json"

TARGET_STATE = "needs_api_original_order_fetch_to_quarantine"

RESULT_COLUMNS = [
    "observed_utc",
    "order_id",
    "sku",
    "source_state",
    "action_state",
    "proof_label",
    "marketplace_id",
    "purchase_utc",
    "order_status",
    "order_item_ids",
    "required_field_gaps",
    "duplicate_state",
    "ready_for_live_merge",
    "notes",
    "live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
]

SUMMARY_COLUMNS = ["metric", "value"]

REQUIRED_FIELDS = ["purchase_utc", "marketplace_id", "sku", "asin", "order_item_ids", "currency", "order_status"]


class OriginalOrderApi(Protocol):
    def fetch_order(self, order_id: str) -> dict[str, Any]:
        ...

    def list_order_items(self, order_id: str) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class B055Result:
    rows: pd.DataFrame
    summary: pd.DataFrame
    quarantine_rows: list[dict[str, str]]
    manifest: dict[str, Any]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return _read_csv(path).fillna("").to_dict("records")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _target_rows(source: pd.DataFrame) -> pd.DataFrame:
    if source.empty:
        return pd.DataFrame()
    work = source.copy()
    for column in ["order_id", "sku", "original_order_recovery_state"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work[
        (work["original_order_recovery_state"].astype(str).str.strip() == TARGET_STATE)
        & (work["order_id_norm"] != "")
        & (work["sku_norm"] != "")
    ].drop_duplicates(subset=["order_id_norm", "sku_norm"])


def _local_order_ids(path: Path) -> set[str]:
    orders = _read_csv(path)
    if orders.empty:
        return set()
    column = "amazon_order_id" if "amazon_order_id" in orders.columns else "order_id" if "order_id" in orders.columns else ""
    if not column:
        return set()
    return {_text(value) for value in orders[column].tolist() if _text(value)}


def _quarantine_by_order(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        order_id = _text(row.get("amazon_order_id") or row.get("order_id"))
        if order_id:
            out.setdefault(order_id, []).append(row)
    return out


def _required_gaps(row: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not _text(row.get(field, ""))]


def _looks_api_proved(row: dict[str, str]) -> bool:
    return _text(row.get("proof_label")) == "API proved" and not _required_gaps(row)


def _result_row(
    *,
    observed: str,
    order_id: str,
    sku: str,
    source_state: str,
    action_state: str,
    proof_label: str,
    quarantine_row: dict[str, str] | None = None,
    notes: str = "",
) -> dict[str, str]:
    row = quarantine_row or {}
    gaps = _required_gaps(row) if row else []
    return {
        "observed_utc": observed,
        "order_id": order_id,
        "sku": sku,
        "source_state": source_state,
        "action_state": action_state,
        "proof_label": proof_label,
        "marketplace_id": _text(row.get("marketplace_id", "")),
        "purchase_utc": _text(row.get("purchase_utc", "")),
        "order_status": _text(row.get("order_status", "")),
        "order_item_ids": _text(row.get("order_item_ids", "")),
        "required_field_gaps": "|".join(gaps),
        "duplicate_state": _text(row.get("duplicate_state", "")),
        "ready_for_live_merge": _text(row.get("ready_for_live_merge", "0")) or "0",
        "notes": notes,
        "live_write_allowed": "0",
        "roi_or_restock_use_allowed": "0",
        "sellerboard_final_truth_allowed": "0",
        "protected_before_apply": "1",
    }


def build_original_order_fetch_to_quarantine(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    apply_fetch: bool = False,
    api_client: OriginalOrderApi | None = None,
) -> B055Result:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    source = _target_rows(_read_csv(root_path / SOURCE_PROOF))
    local_ids = _local_order_ids(root_path / ORDERS_ALL)
    quarantine_path = root_path / EXPECTED_QUARANTINE_REL_PATH
    quarantine_rows = _read_rows(quarantine_path)
    quarantine_by_order = _quarantine_by_order(quarantine_rows)
    client = api_client if apply_fetch else None
    if apply_fetch and client is None:
        client = SpApiOrderRecoveryClient()

    result_rows: list[dict[str, str]] = []
    for _, source_row in source.iterrows():
        order_id = _text(source_row.get("order_id_norm", ""))
        sku = _norm_sku(source_row.get("sku_norm", ""))
        source_state = _text(source_row.get("original_order_recovery_state", ""))
        existing_rows = quarantine_by_order.get(order_id, [])
        api_existing = next((row for row in existing_rows if _looks_api_proved(row)), None)
        if order_id in local_ids:
            result_rows.append(
                _result_row(
                    observed=observed,
                    order_id=order_id,
                    sku=sku,
                    source_state=source_state,
                    action_state="blocked_already_in_live_orders",
                    proof_label="API proved",
                    notes="Order already exists in live local order proof; do not fetch or duplicate.",
                )
            )
            continue
        if api_existing:
            result_rows.append(
                _result_row(
                    observed=observed,
                    order_id=order_id,
                    sku=sku,
                    source_state=source_state,
                    action_state="already_api_proved_in_quarantine",
                    proof_label="API proved",
                    quarantine_row=api_existing,
                    notes="Existing quarantine row is already API-proved.",
                )
            )
            continue
        if len(existing_rows) > 1:
            result_rows.append(
                _result_row(
                    observed=observed,
                    order_id=order_id,
                    sku=sku,
                    source_state=source_state,
                    action_state="blocked_duplicate_quarantine_rows",
                    proof_label="not yet proven",
                    notes="Multiple quarantine rows exist before this fetch; duplicate risk must be resolved first.",
                )
            )
            continue
        if not apply_fetch:
            result_rows.append(
                _result_row(
                    observed=observed,
                    order_id=order_id,
                    sku=sku,
                    source_state=source_state,
                    action_state="planned_api_fetch_to_quarantine",
                    proof_label="not yet proven",
                    notes="Preview only. No Amazon call was made and no quarantine row was written.",
                )
            )
            continue
        try:
            assert client is not None
            order = client.fetch_order(order_id)
            items = client.list_order_items(order_id)
            new_row = _quarantine_row(
                order=order,
                items=items,
                sellerboard_row={"amazon_order_id": order_id, "mapped_sku": sku},
                marketplace_id=_text(order.get("MarketplaceId")),
                proof_label="API proved",
                source="api_original_refund_order_recovery",
            )
            gaps = _required_gaps(new_row)
            if gaps:
                new_row["proof_label"] = "not yet proven"
                action_state = "fetched_but_incomplete_quarantine_proof"
                proof_label = "not yet proven"
                notes = "Amazon fetch returned, but required order fields are missing."
            else:
                action_state = "fetched_api_proved_to_quarantine"
                proof_label = "API proved"
                notes = "Order and item proof fetched into quarantine only."
            new_row["ready_for_live_merge"] = "0"
            quarantine_rows = _merge_quarantine_row(quarantine_rows, new_row)
            quarantine_by_order = _quarantine_by_order(quarantine_rows)
            result_rows.append(
                _result_row(
                    observed=observed,
                    order_id=order_id,
                    sku=sku,
                    source_state=source_state,
                    action_state=action_state,
                    proof_label=proof_label,
                    quarantine_row=new_row,
                    notes=notes,
                )
            )
        except Exception as exc:
            result_rows.append(
                _result_row(
                    observed=observed,
                    order_id=order_id,
                    sku=sku,
                    source_state=source_state,
                    action_state="api_fetch_failed",
                    proof_label="not yet proven",
                    notes=exc.__class__.__name__,
                )
            )

    rows = pd.DataFrame(result_rows, columns=RESULT_COLUMNS).fillna("")
    unsafe_rows = 0
    if not rows.empty:
        unsafe_rows = int(
            (rows["live_write_allowed"].astype(str).str.strip() != "0").sum()
            + (rows["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()
            + (rows["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()
        )
    api_failed = int((rows["action_state"] == "api_fetch_failed").sum()) if not rows.empty else 0
    duplicate_blocked = int((rows["action_state"] == "blocked_duplicate_quarantine_rows").sum()) if not rows.empty else 0
    fetched = int((rows["action_state"] == "fetched_api_proved_to_quarantine").sum()) if not rows.empty else 0
    planned = int((rows["action_state"] == "planned_api_fetch_to_quarantine").sum()) if not rows.empty else 0
    incomplete = int((rows["action_state"] == "fetched_but_incomplete_quarantine_proof").sum()) if not rows.empty else 0
    status = "ok"
    source_path = root_path / SOURCE_PROOF
    if source.empty and not source_path.exists():
        status = "not_checked"
    elif unsafe_rows or api_failed or duplicate_blocked or incomplete:
        status = "fail"
    summary_values = {
        "status": status,
        "observed_utc": observed,
        "apply_fetch": "1" if apply_fetch else "0",
        "source_rows": str(len(source)),
        "result_rows": str(len(rows)),
        "planned_api_fetch_rows": str(planned),
        "fetched_api_proved_rows": str(fetched),
        "fetched_incomplete_rows": str(incomplete),
        "already_api_proved_rows": str(int((rows["action_state"] == "already_api_proved_in_quarantine").sum()) if not rows.empty else 0),
        "already_live_order_rows": str(int((rows["action_state"] == "blocked_already_in_live_orders").sum()) if not rows.empty else 0),
        "duplicate_blocked_rows": str(duplicate_blocked),
        "api_fetch_failed_rows": str(api_failed),
        "unsafe_rows": str(unsafe_rows),
        "quarantine_rows_after": str(len(quarantine_rows) if apply_fetch else len(_read_rows(quarantine_path))),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    manifest = {
        "observed_utc": observed,
        "status": status,
        "apply_fetch": apply_fetch,
        "source_path": str(root_path / SOURCE_PROOF),
        "quarantine_path": str(quarantine_path),
        "result_rows": len(rows),
        "safety": {
            "b_run_started": False,
            "business_outputs_changed": False,
            "local_db_changed": False,
            "sheets_written": False,
            "live_merge": False,
            "output_deleted": False,
            "roi_or_restock_changed": False,
        },
    }
    return B055Result(rows=rows, summary=summary, quarantine_rows=quarantine_rows, manifest=manifest)


def write_original_order_fetch_outputs(
    result: B055Result,
    *,
    root: Path | str | None = None,
    write_quarantine: bool = False,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    result_path = root_path / RESULTS
    summary_path = root_path / SUMMARY
    manifest_path = root_path / MANIFEST
    safe_to_csv(result.rows, result_path, index=False)
    safe_to_csv(result.summary, summary_path, index=False)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(result.manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths = {"results": result_path, "summary": summary_path, "manifest": manifest_path}
    if write_quarantine:
        quarantine_path = root_path / EXPECTED_QUARANTINE_REL_PATH
        safe_to_csv(pd.DataFrame(result.quarantine_rows, columns=QUARANTINE_REQUIRED_COLUMNS).fillna(""), quarantine_path, index=False)
        paths["quarantine"] = quarantine_path
    return paths


def main() -> None:
    result = build_original_order_fetch_to_quarantine(apply_fetch=False)
    paths = write_original_order_fetch_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result.summary.iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "source_rows": summary.get("source_rows", "0"),
            "planned_api_fetch_rows": summary.get("planned_api_fetch_rows", "0"),
            "fetched_api_proved_rows": summary.get("fetched_api_proved_rows", "0"),
            "results": str(paths["results"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
