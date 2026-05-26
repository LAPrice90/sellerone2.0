from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, SOURCE_ACQUISITION_COLUMNS


FetchFunc = Callable[..., dict[str, object]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1_bytes(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _api_filename(supplier_id: str, fetched_at_utc: str) -> str:
    stamp = fetched_at_utc.replace("-", "").replace(":", "")
    return f"{supplier_id}_{stamp}.csv"


def _load_secret_config(root: Path, supplier_id: str) -> dict[str, str]:
    config_path = root / "secrets" / "price_list_manager" / f"{supplier_id}_api.json"
    config: dict[str, str] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
        if isinstance(raw, dict):
            config.update({normalize_text(key): normalize_text(value) for key, value in raw.items()})

    upper = supplier_id.upper()
    for key in ["username", "password", "base_url", "auth_token"]:
        env_value = os.environ.get(f"{upper}_API_{key.upper()}", "")
        if env_value:
            config[key] = env_value
    return config


def _resolve_fetcher(converter_id: str) -> FetchFunc | None:
    if not converter_id:
        return None
    try:
        module = importlib.import_module(f"scripts.flows.F.suppliers.{converter_id}")
    except ModuleNotFoundError:
        return None
    fetcher = getattr(module, "fetch_api_source", None)
    return fetcher if callable(fetcher) else None


def _eligible_api_sources(acquisition: pd.DataFrame, supplier_id: str = "") -> pd.DataFrame:
    work = acquisition.copy()
    work = work[work["source_type"].map(lambda value: normalize_text(value).lower()) == "api_pull"].copy()
    work = work[work["source_subtype"].map(lambda value: normalize_text(value).lower()) == "api"].copy()
    work = work[work["source_state"].map(lambda value: normalize_text(value).lower()) == "green"].copy()
    if supplier_id:
        key = normalize_text(supplier_id).lower()
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == key].copy()
    return work.sort_values(["supplier_id", "checked_at_utc"], kind="stable").reset_index(drop=True)


def fetch_api_sources(
    root: Path | None = None,
    *,
    supplier_id: str = "",
    fetched_at_utc: str | None = None,
    timeout_seconds: int = 60,
    fetch_func: FetchFunc | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    fetched_at = fetched_at_utc or _utc_now_iso()
    acquisition_path = paths.test_mode_dir / "source_acquisition_status.csv"
    registry_path = paths.test_mode_dir / "supplier_registry.csv"
    health_path = paths.test_mode_dir / "health.csv"
    acquisition = read_csv(acquisition_path, SOURCE_ACQUISITION_COLUMNS)
    registry = read_csv(registry_path, [
        "supplier_id",
        "supplier_name",
        "source_type",
        "source_subtype",
        "source_url",
        "source_folder_path",
        "existing_supplier_config_path",
        "converter_id",
        "normal_refresh_days",
        "minimum_rescan_days",
        "large_file_flag",
        "manual_request_required_flag",
        "priority_band",
        "active_flag",
        "notes",
    ])
    if acquisition.empty:
        raise FileNotFoundError("source_acquisition_status.csv is required before fetching API sources")

    registry_by_supplier = {
        normalize_text(row.get("supplier_id", "")): row.to_dict()
        for _, row in registry.iterrows()
        if normalize_text(row.get("supplier_id", ""))
    }
    api_sources = _eligible_api_sources(acquisition, supplier_id=supplier_id)
    fetched_rows = 0
    failed_rows = 0
    bytes_total = 0
    updated = acquisition.copy()

    for _, source_row in api_sources.iterrows():
        source_supplier_id = normalize_text(source_row.get("supplier_id", ""))
        supplier = registry_by_supplier.get(source_supplier_id, {})
        converter_id = normalize_text(supplier.get("converter_id", source_supplier_id))
        fetcher = fetch_func or _resolve_fetcher(converter_id)
        mask = updated["supplier_id"].map(lambda value: normalize_text(value).lower()) == source_supplier_id.lower()
        if fetcher is None:
            failed_rows += 1
            updated.loc[mask, "source_state"] = "error"
            updated.loc[mask, "status"] = "fail"
            updated.loc[mask, "operator_action"] = "Add API adapter"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = "api_adapter_missing"
            continue

        secret = _load_secret_config(paths.root, source_supplier_id)
        username = normalize_text(secret.get("username", ""))
        password = normalize_text(secret.get("password", ""))
        auth_token = normalize_text(secret.get("auth_token", ""))
        base_url = normalize_text(secret.get("base_url", "")) or normalize_text(supplier.get("source_url", ""))
        if not auth_token and (not username or not password):
            failed_rows += 1
            updated.loc[mask, "source_state"] = "error"
            updated.loc[mask, "status"] = "fail"
            updated.loc[mask, "operator_action"] = "Add API credentials"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = "api_credentials_missing"
            continue

        inbox_dir = paths.test_mode_dir / "downloaded_sources" / source_supplier_id / "Inbox"
        target = inbox_dir / _api_filename(source_supplier_id, fetched_at)
        try:
            kwargs = {
                "username": username,
                "password": password,
                "base_url": base_url,
                "timeout_seconds": timeout_seconds,
                "auth_token": auth_token,
            }
            signature = inspect.signature(fetcher)
            accepts_var_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            accepted_kwargs = kwargs if accepts_var_kwargs else {
                key: value for key, value in kwargs.items() if key in signature.parameters
            }
            result = fetcher(target, **accepted_kwargs)
        except Exception as exc:
            result = {"ok": False, "notes": f"api_fetch_error={type(exc).__name__}", "bytes": 0}

        notes = normalize_text(result.get("notes", ""))
        bytes_written = int(result.get("bytes", 0) or 0)
        bytes_total += bytes_written
        if bool(result.get("ok", False)) and target.exists():
            fetched_rows += 1
            file_count = len([path for path in inbox_dir.iterdir() if path.is_file()])
            source_hash = _sha1_bytes(target)
            updated.loc[mask, "source_state"] = "ready"
            updated.loc[mask, "status"] = "ok"
            updated.loc[mask, "source_location"] = base_url
            updated.loc[mask, "latest_source_path"] = str(target)
            updated.loc[mask, "latest_source_name"] = target.name
            updated.loc[mask, "latest_source_mtime_utc"] = _file_mtime_utc(target)
            updated.loc[mask, "file_count"] = str(file_count)
            updated.loc[mask, "operator_action"] = "Import latest file"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = f"{notes};bytes={bytes_written};sha1={source_hash}"
            continue

        failed_rows += 1
        if target.exists():
            target.unlink()
        updated.loc[mask, "source_state"] = "error"
        updated.loc[mask, "status"] = "fail"
        updated.loc[mask, "latest_source_path"] = ""
        updated.loc[mask, "latest_source_name"] = ""
        updated.loc[mask, "latest_source_mtime_utc"] = ""
        updated.loc[mask, "file_count"] = "0"
        updated.loc[mask, "operator_action"] = "Investigate API pull"
        updated.loc[mask, "checked_at_utc"] = fetched_at
        updated.loc[mask, "notes"] = notes or "api_fetch_failed"

    acquisition = write_csv(acquisition_path, updated, SOURCE_ACQUISITION_COLUMNS)
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "api_source_fetch_reconciliation",
                "status": "ok" if failed_rows == 0 else "fail",
                "value": str(fetched_rows),
                "notes": f"api_sources={len(api_sources.index)};fetched={fetched_rows};failed={failed_rows};bytes={bytes_total}",
                "observed_utc": fetched_at,
                "source_path": str(acquisition_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "api_sources": int(len(api_sources.index)),
        "fetched_sources": int(fetched_rows),
        "failed_sources": int(failed_rows),
        "bytes": int(bytes_total),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "acquisition_path": str(acquisition_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch API-based price-list sources into test-mode inboxes.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--fetched-at-utc", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    fetch_api_sources(
        root=root,
        supplier_id=args.supplier_id,
        fetched_at_utc=args.fetched_at_utc,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    main()
