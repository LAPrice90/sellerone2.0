from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


SKU_PREFIX = "NP"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _hash_text(*parts: object, length: int = 8) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length].upper()


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    return f"{prefix}_{_hash_text(*parts, length=length).lower()}"


def _supplier_code(supplier_id: object) -> str:
    clean = re.sub(r"[^A-Za-z0-9]", "", _normalize_text(supplier_id)).upper()
    return (clean[:3] or "SUP").ljust(3, "X")


def generate_expected_seller_sku(
    *,
    supplier_id: object,
    active_run_id: object,
    candidate_id: object,
    asin: object,
    marketplace_id: object,
) -> str:
    supplier = _supplier_code(supplier_id)
    suffix = _hash_text(supplier_id, active_run_id, candidate_id, asin, marketplace_id)
    return f"{SKU_PREFIX}-{supplier}-{suffix}"


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _existing_product_db_skus(root: Path) -> set[str]:
    path = root / "out" / "product_db_preview.csv"
    frame = _read_csv_safe(path)
    if frame.empty or "seller_sku" not in frame.columns:
        return set()
    return {_normalize_key(value) for value in frame["seller_sku"].tolist() if _normalize_key(value) != ""}


def _existing_listing_snapshot_skus(root: Path) -> set[str]:
    skus: set[str] = set()
    for rel_path in (
        "out/listing_offer_snapshot_latest.csv",
        "out/listing_offer_seller_snapshot_latest.csv",
        "out/active_listings.csv",
    ):
        frame = _read_csv_safe(root / rel_path)
        if frame.empty:
            continue
        for column in ("sku", "seller_sku", "SellerSKU", "seller-sku"):
            if column in frame.columns:
                skus.update({_normalize_key(value) for value in frame[column].tolist() if _normalize_key(value) != ""})
    return skus


def _reservation_identity(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        _normalize_text(row.get("supplier_id", "")),
        _normalize_text(row.get("active_run_id", "")),
        _normalize_text(row.get("candidate_id", "")),
        _normalize_key(row.get("asin", "")),
        _normalize_text(row.get("marketplace_id", "")),
    )


def _existing_reservation_map(reservations_df: pd.DataFrame) -> dict[tuple[str, str, str, str, str], str]:
    if reservations_df.empty:
        return {}
    out: dict[tuple[str, str, str, str, str], str] = {}
    for record in reservations_df.to_dict("records"):
        row = {key: _normalize_text(value) for key, value in record.items()}
        key = _reservation_identity(row)
        sku = _normalize_text(row.get("expected_seller_sku", ""))
        if all(part != "" for part in key) and sku != "" and key not in out:
            out[key] = sku
    return out


def _hold_row(
    *,
    observed_utc: str,
    supplier_id: str,
    active_run_id: str,
    candidate_id: str,
    asin: str,
    expected_seller_sku: str,
    reason: str,
    note: str,
    intake_id: str,
    marketplace_id: str,
) -> dict[str, str]:
    return {
        "hold_utc": observed_utc,
        "hold_id": _hash_id("hold", "sku_reservation", supplier_id, active_run_id, candidate_id, asin, expected_seller_sku, reason),
        "hold_stage": "sku_reservation",
        "supplier_id": supplier_id,
        "active_run_id": active_run_id,
        "candidate_id": candidate_id,
        "asin": asin,
        "expected_seller_sku": expected_seller_sku,
        "hold_reason": reason,
        "hold_note": note,
        "source_reference": "amazon_listing_intake_live",
        "intake_id": intake_id,
        "draft_id": "",
        "marketplace_id": marketplace_id,
    }


def _replace_stage_holds(root: Path, *, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_holds_live")
    if existing.empty:
        retained = existing
    else:
        retained = existing[existing["hold_stage"].map(_normalize_text) != "sku_reservation"].copy()
    out_df = pd.concat([retained, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_holds_live", out_df)


def _write_health(
    root: Path,
    *,
    observed_utc: str,
    reserved_rows: int,
    hold_rows: int,
) -> None:
    check_name = "amazon_listing_sku_reservation"
    status = "ok" if hold_rows == 0 else "warn"
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    health = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(reserved_rows),
                "notes": f"reserved_rows={reserved_rows};hold_rows={hold_rows}",
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "amazon_listing_intake_live.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, health], ignore_index=True))


def reserve_amazon_listing_skus(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()

    intake_df = read_f_contract_df(root_path, "amazon_listing_intake_live")
    existing_reservations = read_f_contract_df(root_path, "amazon_listing_sku_reservations_live")
    reservation_map = _existing_reservation_map(existing_reservations)
    product_db_skus = _existing_product_db_skus(root_path)
    listing_skus = _existing_listing_snapshot_skus(root_path)

    reservation_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for record in intake_df.to_dict("records"):
        row = {key: _normalize_text(value) for key, value in record.items()}
        supplier_id, active_run_id, candidate_id, asin_key, marketplace_id = _reservation_identity(row)
        intake_id = _normalize_text(row.get("intake_id", ""))
        source_status = _normalize_text(row.get("intake_status", ""))
        missing = [
            name
            for name, value in (
                ("supplier_id", supplier_id),
                ("active_run_id", active_run_id),
                ("candidate_id", candidate_id),
                ("asin", asin_key),
                ("marketplace_id", marketplace_id),
            )
            if value == ""
        ]

        expected_sku = ""
        status = "reserved"
        reason = "reserved"
        if missing:
            status = "held"
            reason = "missing_identity:" + ",".join(missing)
        else:
            identity = (supplier_id, active_run_id, candidate_id, asin_key, marketplace_id)
            expected_sku = reservation_map.get(identity) or generate_expected_seller_sku(
                supplier_id=supplier_id,
                active_run_id=active_run_id,
                candidate_id=candidate_id,
                asin=asin_key,
                marketplace_id=marketplace_id,
            )
            collision_reasons: list[str] = []
            if _normalize_key(expected_sku) in product_db_skus:
                collision_reasons.append("sku_collision_product_db")
            if _normalize_key(expected_sku) in listing_skus:
                collision_reasons.append("sku_collision_listing_snapshot")
            if collision_reasons:
                status = "held"
                reason = "|".join(collision_reasons)

        reservation_id = _hash_id("sku_res", supplier_id, active_run_id, candidate_id, asin_key, marketplace_id)
        reservation_rows.append(
            {
                "observed_utc": observed,
                "reservation_id": reservation_id,
                "intake_id": intake_id,
                "supplier_id": supplier_id,
                "active_run_id": active_run_id,
                "candidate_id": candidate_id,
                "asin": asin_key,
                "marketplace_id": marketplace_id,
                "expected_seller_sku": expected_sku,
                "sku_reservation_status": status,
                "sku_reservation_reason": reason,
                "source_intake_status": source_status,
                "updated_at_utc": observed,
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "amazon_title": _normalize_text(row.get("amazon_title", "")),
                "source_reference": intake_id,
            }
        )
        if status != "reserved":
            hold_rows.append(
                _hold_row(
                    observed_utc=observed,
                    supplier_id=supplier_id,
                    active_run_id=active_run_id,
                    candidate_id=candidate_id,
                    asin=asin_key,
                    expected_seller_sku=expected_sku,
                    reason=reason,
                    note="SKU reservation blocked before Amazon draft creation",
                    intake_id=intake_id,
                    marketplace_id=marketplace_id,
                )
            )

    out_df = pd.DataFrame(reservation_rows)
    if not out_df.empty:
        out_df = out_df.drop_duplicates(
            subset=["supplier_id", "active_run_id", "candidate_id", "asin", "marketplace_id"],
            keep="last",
        )
        out_df = out_df.sort_values(
            by=["supplier_id", "active_run_id", "candidate_id", "asin"],
            ascending=[True, True, True, True],
            kind="stable",
        )

    finalized = write_f_contract_df(root_path, "amazon_listing_sku_reservations_live", out_df)
    _replace_stage_holds(root_path, rows=hold_rows)
    reserved_count = int((finalized.get("sku_reservation_status", pd.Series(dtype=str)) == "reserved").sum())
    _write_health(root_path, observed_utc=observed, reserved_rows=reserved_count, hold_rows=len(hold_rows))
    print(
        {
            "status": "success",
            "reservation_rows": int(len(finalized.index)),
            "reserved_rows": reserved_count,
            "hold_rows": len(hold_rows),
        }
    )
    return finalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reserve stable seller SKUs for Amazon listing intake rows.")
    parser.add_argument("--root", default="")
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    reserve_amazon_listing_skus(root=root, observed_utc=observed)


if __name__ == "__main__":
    main()
