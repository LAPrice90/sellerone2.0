from __future__ import annotations

import argparse
import atexit
import csv
import json
import math
import os
import signal
import sys
import threading
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1 import phase1_main_loop, phase1_phase_engine, phase1_storage  # noqa: E402
from scripts.phase1 import phase1_sku_scope  # noqa: E402
from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing  # noqa: E402
from scripts.api.get_listing_item_price import fetch_our_offer_prices, run_own_offer_price_lookup  # noqa: E402
from scripts.h.h_floor_policy import load_h_floor_vat_policy  # noqa: E402
from scripts.h.h_floor_truth import (  # noqa: E402
    HFloorContext,
    append_h_floor_trace_rows,
    build_h_floor_trace_row,
    compute_h_floor_for_sku,
    has_blocking_reason_codes,
    load_h_floor_context,
)
from scripts.phase1.phase1_write_verify import patch_listings_item_price  # noqa: E402

SOURCE = "H110_run_phase1_h_pilot"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
MARKETPLACE_CODE_TO_ID = {"UK": "A1F83G8C2ARO7P"}
SKU_SCAN_STATE_PATH = OUT / "phase1_sku_scan_state.json"
MANUAL_CAPS_PATH = ROOT / "config" / "phase1_manual_max_caps.csv"
PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
TOKEN_COGS_LEDGER_PATH = OUT / "token_cogs_ledger.csv"
TOKEN_LEDGER_PATH = OUT / "token_ledger_live.csv"
TEMP_FLOOR_SNAPSHOT_PATH = OUT / "sku_temp_floor_snapshot.csv"
OFFER_SNAPSHOT_FACTS_PATH = ROOT / "data" / "offer_snapshot_facts.csv"
MIN_REFERRAL_FEE_GBP = 0.25
# Terminology: "commission" in this repricer equals Amazon referral fee.
H_FLOOR_VAT_POLICY = load_h_floor_vat_policy()
PHASE1_PROGRESS_PATH = Path(os.environ.get("H_PHASE1_PROGRESS_PATH", "").strip()) if os.environ.get("H_PHASE1_PROGRESS_PATH", "").strip() else None
PHASE1_RESULT_PATH = Path(os.environ.get("H_PHASE1_RESULT_PATH", "").strip()) if os.environ.get("H_PHASE1_RESULT_PATH", "").strip() else None
PHASE1_COMPLETION_MARKER_PATH = (
    Path(os.environ.get("H_PHASE1_COMPLETION_MARKER_PATH", "").strip())
    if os.environ.get("H_PHASE1_COMPLETION_MARKER_PATH", "").strip()
    else None
)
H110_SKU_DECISION_LOG_PATH = OUT / "systems" / "H" / "live" / "h110_sku_decision_log.csv"
H110_SKU_LIFECYCLE_LOG_PATH = OUT / "systems" / "H" / "live" / "h110_sku_lifecycle_log.csv"
H_LIVE_DIR = OUT / "systems" / "H" / "live"
H_REENTRY_STATE_PATH = H_LIVE_DIR / "h_reentry_price_state.json"
H_INBOUND_ACTIVATION_STATE_PATH = H_LIVE_DIR / "h_inbound_activation_state.json"
CANONICAL_UNIVERSE_PATH = OUT / "phase1_sku_scope.csv"
STOCKED_EXCLUDED_REPORT_PATH = OUT / "REPORT_live_but_excluded.csv"
H_INCLUDE_STOCKED_EXCLUDED_ENV = "H_INCLUDE_STOCKED_EXCLUDED"
DEFAULT_STOCK_SNAPSHOT_PATH = OUT / "parking" / "stock_snapshot_latest.csv"
INVENTORY_SNAPSHOT_GLOB = "inventory_snapshot_*.csv"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
STOCK_SNAPSHOT_PATH_ENV = "H_STOCK_SNAPSHOT_PATH"
STOCK_SNAPSHOT_GLOB_ENV = "H_STOCK_SNAPSHOT_GLOB"
STOCK_SNAPSHOT_SKU_COL_ENV = "H_STOCK_SNAPSHOT_SKU_COL"
STOCK_SNAPSHOT_QTY_COL_ENV = "H_STOCK_SNAPSHOT_QTY_COL"
STOCK_SNAPSHOT_MAX_AGE_HOURS_ENV = "H_STOCK_SNAPSHOT_MAX_AGE_HOURS"
STOCK_SNAPSHOT_REQUIRE_TODAY_ENV = "H_STOCK_SNAPSHOT_REQUIRE_TODAY"
DEFAULT_STOCK_SNAPSHOT_GLOB = "out/parking/stock_snapshot_*.csv"
DEFAULT_STOCK_SNAPSHOT_MAX_AGE_HOURS = 48.0
STOCK_SKU_COL_CANDIDATES = ["sku", "SKU", "Sku", "seller_sku", "SellerSKU"]
STOCK_QTY_COL_CANDIDATES = [
    "total_qty",
    "stock",
    "Stock",
    "qty",
    "Qty",
    "available",
    "Available",
    "on_hand",
    "OnHand",
    "available_qty",
    "quantity",
    "total_quantity",
]
INBOUND_UNITS_COL_CANDIDATES = [
    "inbound_total",
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
]
INBOUND_COMPONENT_COLS = [
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
]
REQUIRED_UNIVERSE_COLUMNS = {
    "sku",
    "merchant_status",
    "manually_disabled",
    "repricing_enabled",
    "observe_enabled",
    "write_enabled",
    "observe_effective",
    "write_effective",
    "reason_code",
    "asof",
}

_ACTIVE_COMPLETION_RUN_ID = ""
_SUCCESS_MARKER_WRITTEN = False
_TERMINAL_MARKER_ATTEMPTED = False
_MARKER_GUARD_LOCK = threading.Lock()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp_path, path)


def _progress(step: str, **fields: object) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [f"{k}={_norm(v)}" for k, v in fields.items() if _norm(v) != ""]
    line = f"{ts} {step}"
    if parts:
        line = f"{line} {' '.join(parts)}"
    if PHASE1_PROGRESS_PATH is not None:
        try:
            PHASE1_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with PHASE1_PROGRESS_PATH.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")
                fh.flush()
        except Exception:
            pass
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass


def _write_result_payload(payload: dict[str, object]) -> None:
    if PHASE1_RESULT_PATH is None:
        return
    payload_text = json.dumps(payload, ensure_ascii=True) + "\n"
    _progress(
        "h110 result_payload_write_start",
        path=str(PHASE1_RESULT_PATH),
        bytes=len(payload_text.encode("utf-8")),
    )
    try:
        _atomic_write_text(PHASE1_RESULT_PATH, payload_text)
        _progress(
            "h110 result_payload_write_done",
            status="ok",
            path=str(PHASE1_RESULT_PATH),
            bytes=len(payload_text.encode("utf-8")),
        )
    except Exception as exc:
        try:
            _progress(
                "h110 result_payload_write_done",
                status="fail",
                path=str(PHASE1_RESULT_PATH),
                error=f"{type(exc).__name__}:{exc}",
            )
        except Exception:
            pass
        raise


def _emit_success_payload(payload: dict[str, object]) -> None:
    payload_text = json.dumps(payload, ensure_ascii=True)
    result_ok = False
    stdout_ok = False
    result_error = ""
    stdout_error = ""
    if PHASE1_RESULT_PATH is not None:
        try:
            _write_result_payload(payload)
            result_ok = PHASE1_RESULT_PATH.exists() and PHASE1_RESULT_PATH.stat().st_size > 0
            if not result_ok:
                result_error = "result_file_missing_after_write"
        except Exception as exc:
            result_error = f"{type(exc).__name__}:{exc}"
    else:
        result_error = "result_path_missing"
    try:
        sys.stdout.write(payload_text + "\n")
        sys.stdout.flush()
        stdout_ok = True
    except Exception as exc:
        stdout_error = f"{type(exc).__name__}:{exc}"
    _progress(
        "h110 success_payload_emit",
        stdout_ok="1" if stdout_ok else "0",
        result_ok="1" if result_ok else "0",
        result_path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
        result_error=result_error,
        stdout_error=stdout_error,
    )
    if not stdout_ok and not result_ok:
        raise RuntimeError(
            "phase1 pilot success payload unavailable "
            f"(stdout_ok=0 result_ok=0 result_path={PHASE1_RESULT_PATH} "
            f"result_error={result_error} stdout_error={stdout_error})"
        )


def _write_completion_marker(
    *,
    status: str,
    run_id: str,
    reason: str = "",
    payload_result_ok: bool = False,
    fail_closed: bool = False,
) -> bool:
    if PHASE1_COMPLETION_MARKER_PATH is None:
        if fail_closed:
            raise RuntimeError("h110 completion marker path missing")
        return False
    payload = {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": _norm(status).lower() or "unknown",
        "run_id": _norm(run_id),
        "reason": _norm(reason),
        "result_path": str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
        "result_ok": "1" if payload_result_ok else "0",
    }
    text = json.dumps(payload, ensure_ascii=True) + "\n"
    try:
        _atomic_write_text(PHASE1_COMPLETION_MARKER_PATH, text)
        marker_exists = PHASE1_COMPLETION_MARKER_PATH.exists()
        marker_size = int(PHASE1_COMPLETION_MARKER_PATH.stat().st_size) if marker_exists else 0
        marker_ok = marker_exists and marker_size > 0
        _progress(
            "h110 completion_marker_write",
            status="ok" if marker_ok else "fail",
            marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
            marker_size=str(marker_size),
            marker_status=payload.get("status", ""),
            marker_run_id=payload.get("run_id", ""),
            fail_closed="1" if fail_closed else "0",
        )
        if payload.get("status", "") == "success":
            _progress(
                "h110 completion_marker_success_write",
                status="ok" if marker_ok else "fail",
                marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
                marker_run_id=payload.get("run_id", ""),
            )
        elif payload.get("status", "") == "failed":
            _progress(
                "h110 completion_marker_failed_write",
                status="ok" if marker_ok else "fail",
                marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
                marker_run_id=payload.get("run_id", ""),
                reason=payload.get("reason", ""),
            )
        if not marker_ok and fail_closed:
            raise RuntimeError(
                "h110 completion contract failed: completion marker missing after write "
                f"(completion_marker_path={PHASE1_COMPLETION_MARKER_PATH})"
            )
        return marker_ok
    except Exception as exc:
        _progress(
            "h110 completion_marker_write",
            status="fail",
            marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
            error=f"{type(exc).__name__}:{exc}",
            marker_status=payload.get("status", ""),
            marker_run_id=payload.get("run_id", ""),
            fail_closed="1" if fail_closed else "0",
        )
        if fail_closed:
            raise RuntimeError(
                "h110 completion contract failed: completion marker write error "
                f"(completion_marker_path={PHASE1_COMPLETION_MARKER_PATH} error={type(exc).__name__}:{exc})"
            ) from exc
        return False


def _set_active_completion_run_id(run_id: str) -> None:
    global _ACTIVE_COMPLETION_RUN_ID
    _ACTIVE_COMPLETION_RUN_ID = _norm(run_id)


def _mark_completion_success_written() -> None:
    global _SUCCESS_MARKER_WRITTEN
    _SUCCESS_MARKER_WRITTEN = True


def _ensure_terminal_completion_marker(*, reason: str) -> None:
    global _TERMINAL_MARKER_ATTEMPTED
    with _MARKER_GUARD_LOCK:
        if _TERMINAL_MARKER_ATTEMPTED or _SUCCESS_MARKER_WRITTEN:
            return
        run_id = _norm(_ACTIVE_COMPLETION_RUN_ID or os.environ.get("H_RUN_ID", ""))
        if not run_id:
            return
        _TERMINAL_MARKER_ATTEMPTED = True
    try:
        _write_completion_marker(
            status="failed",
            run_id=run_id,
            reason=_norm(reason) or "terminal_exit_without_success_marker",
            payload_result_ok=False,
        )
    except Exception:
        pass


def _install_completion_exit_guards(run_id: str) -> None:
    _set_active_completion_run_id(run_id)

    def _atexit_guard() -> None:
        _ensure_terminal_completion_marker(reason="atexit_without_success_marker")

    atexit.register(_atexit_guard)

    def _signal_guard(signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        sig_name = "SIGTERM"
        for candidate in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig_obj = getattr(signal, candidate, None)
            if sig_obj is not None and int(sig_obj) == int(signum):
                sig_name = candidate
                break
        _ensure_terminal_completion_marker(reason=f"signal_{sig_name.lower()}_before_success_marker")
        raise SystemExit(128 + int(signum))

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig_obj = getattr(signal, sig_name, None)
        if sig_obj is None:
            continue
        try:
            signal.signal(sig_obj, _signal_guard)
        except Exception:
            continue


def _completion_marker_success_for_run(run_id: str) -> tuple[bool, str]:
    marker_path = PHASE1_COMPLETION_MARKER_PATH
    if marker_path is None:
        return False, "completion_marker_path_missing"
    if not marker_path.exists():
        return False, "completion_marker_missing"
    try:
        raw = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"completion_marker_invalid_json:{type(exc).__name__}:{exc}"
    if not isinstance(raw, dict):
        return False, "completion_marker_not_object"
    status = _norm(raw.get("status", "")).lower()
    marker_run_id = _norm(raw.get("run_id", ""))
    result_ok = _norm(raw.get("result_ok", ""))
    if status != "success":
        return False, f"completion_marker_status_{status or 'missing'}"
    if run_id and marker_run_id and marker_run_id != run_id:
        return False, f"completion_marker_run_mismatch:{marker_run_id}"
    if result_ok not in {"1", "true"}:
        return False, f"completion_marker_result_not_ok:{result_ok or 'missing'}"
    return True, "ok"


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _to_float(value: object) -> float | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        out = float(raw)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _resolve_vat_rate(row: pd.Series, fee_row: dict[str, str]) -> float:
    # Repricer VAT must be based on product/market VAT rates, not settlement withheld flags.
    vat_raw = _to_float(fee_row.get("last_vat_rate_pct", ""))
    if vat_raw is None:
        vat_raw = _to_float(fee_row.get("vat_rate", ""))
    if vat_raw is not None:
        if vat_raw > 1:
            vat_raw = vat_raw / 100.0
        if vat_raw < 0:
            vat_raw = 0.0
        return vat_raw

    price_ex = _to_float(row.get("Price_ExVAT_num", ""))
    price_vat = _to_float(row.get("Price_VAT_num", ""))
    if price_ex is not None and price_ex > 0 and price_vat is not None:
        candidate = abs(price_vat) / abs(price_ex)
        if candidate >= 0:
            return candidate
    return 0.2


def _to_int(value: object) -> int | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        return int(float(raw))
    except Exception:
        return None


def _round_half_up(value: float, ndigits: int = 2) -> float:
    q = Decimal("1").scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def _csv_cell(value: object) -> str:
    text = _norm(value)
    if any(ch in text for ch in [",", "\"", "\n", "\r"]):
        text = "\"" + text.replace("\"", "\"\"") + "\""
    return text


def _append_csv_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        if fh.tell() == 0:
            fh.write(",".join(headers) + "\n")
        for row in rows:
            fh.write(",".join(_csv_cell(row.get(col, "")) for col in headers) + "\n")


def _append_temp_floor_snapshot(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "asof_utc",
        "sku",
        "order_id",
        "order_date_utc",
        "candidate_price_gbp",
        "vat_rate_market",
        "cogs_total_gbp",
        "fba_total_gbp",
        "commission_total_gbp",
        "digital_fee_total_gbp",
        "fixed_total_gbp",
        "break_even_total_gbp",
        "temp_floor_10roi_gbp",
        "source_script",
    ]
    _append_csv_rows(
        TEMP_FLOOR_SNAPSHOT_PATH,
        headers,
        [{k: _norm(row.get(k, "")) for k in headers} for row in rows],
    )


def _to_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    try:
        raw = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_scalar(text: str) -> object:
    raw = str(text).strip()
    if raw == "":
        return ""
    low = raw.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except Exception:
        return raw.strip("\"'")


def _simple_yaml_load(path: Path) -> dict:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = line.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_scalar(value)
    return root


def _cfg_get(cfg: dict, *keys: str, default: object = "") -> object:
    cur: object = cfg
    for key in keys:
        if not isinstance(cur, dict):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def _to_num_text(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _env_float(name: str, default: float) -> float:
    raw = _norm(os.environ.get(name, ""))
    if not raw:
        return default
    parsed = _to_float(raw)
    if parsed is None:
        return default
    return parsed


def _env_int(name: str, default: int) -> int:
    raw = _norm(os.environ.get(name, ""))
    if not raw:
        return default
    parsed = _to_int(raw)
    if parsed is None:
        return default
    return parsed


def _is_truthy_text(value: object) -> bool:
    text = _norm(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


def _is_in_stock_listing_row(row: dict[str, str]) -> bool:
    # Use the same listing snapshot signal the repricer already relies on.
    # If our offer is present (or we have a positive current price), treat as in stock.
    if _is_truthy_text(row.get("we_present_flag", "")):
        return True
    our_price = _to_float(row.get("our_price", ""))
    return our_price is not None and our_price > 0


def _has_active_offer_price(row: dict[str, str]) -> bool:
    for col in ("our_price", "buy_box_price", "lowest_fba_price", "lowest_fbm_price"):
        price = _to_float(row.get(col, ""))
        if price is not None and price > 0:
            return True
    return False


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return payload if isinstance(payload, dict) else default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _fmt_stock_qty(value: float | None) -> str:
    if value is None:
        return ""
    return f"{_round_half_up(float(value), 2):.2f}"


def _latest_listing_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No listing snapshot found in out/")
    return files[-1]


def _latest_seller_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_seller_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No seller snapshot found in out/")
    return files[-1]


def _load_listing_row_map(path: Path | None = None) -> dict[str, dict[str, str]]:
    target = path or _latest_listing_snapshot()
    df = pd.read_csv(target, dtype=str).fillna("")
    if "sku" not in df.columns:
        raise RuntimeError(f"listing snapshot missing required column sku: {target.name}")
    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec = {str(k): _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get("sku", "")).upper()
        if not sku or sku in out:
            continue
        out[sku] = rec
    return out


def _resolve_stock_source_path() -> Path:
    raw = _norm(os.environ.get(STOCK_SNAPSHOT_PATH_ENV, ""))
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        return path
    return DEFAULT_STOCK_SNAPSHOT_PATH


def _resolve_stock_glob_pattern() -> str:
    raw = _norm(os.environ.get(STOCK_SNAPSHOT_GLOB_ENV, ""))
    return raw or DEFAULT_STOCK_SNAPSHOT_GLOB


def _resolve_stock_max_age_hours() -> float:
    parsed = _to_float(os.environ.get(STOCK_SNAPSHOT_MAX_AGE_HOURS_ENV, DEFAULT_STOCK_SNAPSHOT_MAX_AGE_HOURS))
    if parsed is None:
        return DEFAULT_STOCK_SNAPSHOT_MAX_AGE_HOURS
    return max(float(parsed), 0.0)


def _resolve_stock_require_today() -> bool:
    return _to_bool(os.environ.get(STOCK_SNAPSHOT_REQUIRE_TODAY_ENV, "0"), default=False)


def _resolve_glob_paths(pattern: str) -> list[Path]:
    candidate = Path(pattern)
    if candidate.is_absolute():
        base = candidate.parent
        glob_pat = candidate.name
    else:
        base = ROOT
        glob_pat = pattern
    try:
        return sorted(base.glob(glob_pat))
    except Exception:
        return []


def _collect_stock_snapshot_candidates() -> list[Path]:
    paths: list[Path] = []

    # 1) Canonical stock truth for runtime decisions: latest dated inventory snapshot.
    inv_snapshots = sorted(OUT.glob(INVENTORY_SNAPSHOT_GLOB))
    if inv_snapshots:
        paths.append(inv_snapshots[-1])

    # 2) inventory_summaries.csv is compatibility fallback when snapshot is missing.
    if INVENTORY_SUMMARIES_PATH.exists():
        paths.append(INVENTORY_SUMMARIES_PATH)

    # 3) Parking stock snapshots are last resort.
    explicit = _resolve_stock_source_path()
    if explicit.exists():
        paths.append(explicit)

    for path in _resolve_glob_paths(_resolve_stock_glob_pattern()):
        if path.is_file():
            paths.append(path)

    parent = explicit.parent if explicit.parent.exists() else OUT / "parking"
    if parent.exists():
        for path in sorted(parent.glob("stock_snapshot*.csv"), reverse=True):
            if path.is_file():
                paths.append(path)

    dedup: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(path)
    return dedup


def _resolve_stock_column(
    df: pd.DataFrame,
    *,
    env_col: str,
    candidates: list[str],
    label: str,
) -> str:
    explicit = _norm(os.environ.get(env_col, ""))
    if explicit:
        if explicit in df.columns:
            return explicit
        raise RuntimeError(f"[H110] stock snapshot missing configured {label} column '{explicit}'")
    for col in candidates:
        if col in df.columns:
            return col
    raise RuntimeError(f"[H110] stock snapshot missing {label} column; tried {','.join(candidates)}")


def _parse_stock_qty(value: object) -> float | None:
    raw = _norm(value)
    if not raw:
        return None
    parsed = _to_float(raw)
    if parsed is None:
        return None
    return parsed


def _resolve_optional_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    return ""


def _parse_inbound_total_from_row(row: pd.Series, available_cols: set[str]) -> float | None:
    present_component_cols = [col for col in INBOUND_COMPONENT_COLS if col in available_cols]
    if present_component_cols:
        total = 0.0
        for col in present_component_cols:
            val = _parse_stock_qty(row.get(col, ""))
            if val is not None and val > 0:
                total += float(val)
        return total
    inbound_col = ""
    for col in INBOUND_UNITS_COL_CANDIDATES:
        if col in available_cols:
            inbound_col = col
            break
    if not inbound_col:
        return None
    return _parse_stock_qty(row.get(inbound_col, ""))


def _parse_snapshot_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            day = datetime.fromisoformat(f"{text}T00:00:00+00:00")
            return day.astimezone(timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _infer_snapshot_datetime(df: pd.DataFrame, path: Path) -> tuple[datetime, str]:
    file_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    for col in ("asof_utc", "asof_date", "date_utc", "timestamp_utc"):
        if col not in df.columns:
            continue
        parsed_values = [_parse_snapshot_dt(v) for v in df[col].astype(str).tolist()]
        parsed_values = [v for v in parsed_values if v is not None]
        if parsed_values:
            parsed_max = max(parsed_values)
            if file_dt - parsed_max > timedelta(hours=48):
                return file_dt, f"{col}_stale_fallback_file_mtime"
            return parsed_max, col
    return file_dt, "file_mtime"


def _write_excluded_stock_file(
    *,
    today_utc: str,
    stock_source_path: str,
    excluded_rows: list[dict[str, str]],
) -> Path:
    out_path = H_LIVE_DIR / f"h_excluded_stock_{today_utc}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sku", "stock_qty", "reason", "today_utc", "stock_source_path"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in excluded_rows:
            writer.writerow(
                {
                    "sku": _norm(row.get("sku", "")),
                    "stock_qty": _norm(row.get("stock_qty", "")) or ("0" if _norm(row.get("reason", "")) == "OUT_OF_STOCK" else ""),
                    "reason": _norm(row.get("reason", "")),
                    "today_utc": today_utc,
                    "stock_source_path": stock_source_path,
                }
            )
    return out_path


def _write_excluded_scope_file(
    *,
    today_utc: str,
    scope_source: str,
    excluded_rows: list[dict[str, str]],
) -> Path:
    out_path = H_LIVE_DIR / f"h_excluded_scope_{today_utc}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sku", "sale_status", "parked_flag", "reason", "today_utc", "scope_source"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in excluded_rows:
            writer.writerow(
                {
                    "sku": _norm(row.get("sku", "")),
                    "sale_status": _norm(row.get("sale_status", "")),
                    "parked_flag": _norm(row.get("parked_flag", "")),
                    "reason": _norm(row.get("reason", "")),
                    "today_utc": today_utc,
                    "scope_source": scope_source,
                }
            )
    return out_path


def _write_exception_included_file(
    *,
    today_utc: str,
    rows: list[dict[str, str]],
) -> Path:
    out_path = H_LIVE_DIR / f"h_exception_included_{today_utc}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sku", "total_qty", "reason", "sale_status", "parked_flag", "include_reason"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sku": _norm(row.get("sku", "")).upper(),
                    "total_qty": _norm(row.get("total_qty", "")),
                    "reason": _norm(row.get("reason", "")),
                    "sale_status": _norm(row.get("sale_status", "")),
                    "parked_flag": _norm(row.get("parked_flag", "")),
                    "include_reason": "STOCKED_BUT_EXCLUDED",
                }
            )
    return out_path


def _load_stocked_excluded_rows(today_utc: str) -> list[dict[str, str]]:
    if not STOCKED_EXCLUDED_REPORT_PATH.exists():
        return []
    try:
        df = pd.read_csv(STOCKED_EXCLUDED_REPORT_PATH, dtype=str).fillna("")
    except Exception:
        return []
    if df.empty or "sku" not in df.columns:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, rec in df.iterrows():
        sku = _norm(rec.get("sku", "")).upper()
        if not sku or sku in seen:
            continue
        qty = _to_float(rec.get("total_qty", ""))
        if qty is None or qty <= 0:
            continue
        seen.add(sku)
        rows.append(
            {
                "sku": sku,
                "total_qty": f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}",
                "reason": _norm(rec.get("reason", "")),
                "sale_status": _norm(rec.get("sale_status", "")),
                "parked_flag": _norm(rec.get("parked_flag", "")),
                "today_utc": today_utc,
            }
        )
    return rows


def _apply_scope_universe_filter(
    *,
    universe_rows: list[dict[str, str]],
    today_utc: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    excluded_rows: list[dict[str, str]] = []
    included_rows: list[dict[str, str]] = []
    excluded_dropped = 0
    excluded_parked = 0

    for row in universe_rows:
        parked_flag = _as_bool_text(row.get("parked_flag", ""), "0")
        is_parked = parked_flag == "1"

        if is_parked:
            if is_parked:
                excluded_parked += 1
            excluded_rows.append(
                {
                    "sku": _norm(row.get("sku", "")).upper(),
                    "sale_status": _norm(row.get("sale_status", "")),
                    "parked_flag": parked_flag,
                    "reason": "PARKED",
                }
            )
            continue
        included_rows.append(row)

    excluded_path = _write_excluded_scope_file(
        today_utc=today_utc,
        scope_source=str(CANONICAL_UNIVERSE_PATH),
        excluded_rows=excluded_rows,
    )
    summary = {
        "scope_total": str(len(universe_rows)),
        "excluded_dropped": str(excluded_dropped),
        "excluded_parked": str(excluded_parked),
        "remaining": str(len(included_rows)),
        "excluded_path": str(excluded_path),
        "scope_source": str(CANONICAL_UNIVERSE_PATH),
    }
    _progress(
        "h_universe_scope_filter",
        today_utc=today_utc,
        scope_total=summary["scope_total"],
        excluded_dropped=summary["excluded_dropped"],
        excluded_parked=summary["excluded_parked"],
        remaining=summary["remaining"],
    )
    return included_rows, summary


def _write_stock_snapshot_status(
    *,
    today_utc: str,
    chosen_path: str,
    chosen_date: str,
    age_hours: float,
    is_fallback: bool,
    status: str,
) -> Path:
    out_path = H_LIVE_DIR / "h_stock_snapshot_status.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["today_utc", "chosen_path", "chosen_date", "age_hours", "is_fallback", "status"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerow(
            {
                "today_utc": today_utc,
                "chosen_path": chosen_path,
                "chosen_date": chosen_date,
                "age_hours": f"{_round_half_up(age_hours, 2):.2f}",
                "is_fallback": "1" if is_fallback else "0",
                "status": status,
            }
        )
    return out_path


def _apply_stock_universe_filter(
    *,
    due_rows: list[dict[str, str]],
    now_utc: datetime,
    today_utc: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    candidates = _collect_stock_snapshot_candidates()
    if not candidates:
        raise RuntimeError("[H110] stock snapshot missing: no candidate files found")

    parsed_candidates: list[dict[str, object]] = []
    parse_errors: list[str] = []
    for path in candidates:
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
            if df.empty:
                continue
            sku_col = _resolve_stock_column(
                df,
                env_col=STOCK_SNAPSHOT_SKU_COL_ENV,
                candidates=STOCK_SKU_COL_CANDIDATES,
                label="sku",
            )
            qty_col = _resolve_stock_column(
                df,
                env_col=STOCK_SNAPSHOT_QTY_COL_ENV,
                candidates=STOCK_QTY_COL_CANDIDATES,
                label="qty",
            )
            snapshot_dt, snapshot_basis = _infer_snapshot_datetime(df, path)
            parsed_candidates.append(
                {
                    "path": path,
                    "df": df,
                    "sku_col": sku_col,
                    "qty_col": qty_col,
                    "snapshot_dt": snapshot_dt,
                    "snapshot_date": snapshot_dt.date().isoformat(),
                    "snapshot_basis": snapshot_basis,
                }
            )
        except Exception as exc:
            parse_errors.append(f"{path}: {exc}")

    if not parsed_candidates:
        details = " | ".join(parse_errors[:5])
        raise RuntimeError(f"[H110] no readable stock snapshots ({details})")

    inv_snapshot_candidates = sorted(
        [rec for rec in parsed_candidates if _norm(Path(str(rec["path"])).name).lower().startswith("inventory_snapshot_")],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )
    inventory_summaries_candidates = sorted(
        [rec for rec in parsed_candidates if Path(str(rec["path"])).resolve() == INVENTORY_SUMMARIES_PATH.resolve()],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )
    parking_stock_candidates = sorted(
        [
            rec
            for rec in parsed_candidates
            if _norm(Path(str(rec["path"])).name).lower().startswith("stock_snapshot")
            and "parking" in {part.lower() for part in Path(str(rec["path"])).parts}
        ],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )
    other_candidates = sorted(
        [
            rec
            for rec in parsed_candidates
            if rec not in inv_snapshot_candidates
            and rec not in inventory_summaries_candidates
            and rec not in parking_stock_candidates
        ],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )

    source_priority: dict[str, int] = {}
    for rec in inv_snapshot_candidates:
        source_priority[str(rec["path"])] = 0
    for rec in inventory_summaries_candidates:
        source_priority[str(rec["path"])] = 1
    for rec in parking_stock_candidates:
        source_priority[str(rec["path"])] = 2
    for rec in other_candidates:
        source_priority[str(rec["path"])] = 3

    ordered_candidates = sorted(
        parsed_candidates,
        key=lambda rec: (
            source_priority.get(str(rec["path"]), 99),
            -float(rec["snapshot_dt"].timestamp()),
            str(rec["path"]),
        ),
    )

    require_today = _resolve_stock_require_today()
    max_age_hours = _resolve_stock_max_age_hours()
    chosen = ordered_candidates[0]
    is_fallback = chosen["snapshot_date"] != today_utc
    chosen_dt = chosen["snapshot_dt"]
    age_hours = max((now_utc - chosen_dt).total_seconds() / 3600.0, 0.0)
    action = "ok"
    status = "OK"
    if is_fallback:
        action = "warn"
        status = "WARN"
    if require_today and is_fallback:
        action = "abort"
        status = "ABORT"
    if age_hours > max_age_hours:
        action = "abort"
        status = "ABORT"

    status_path = _write_stock_snapshot_status(
        today_utc=today_utc,
        chosen_path=str(chosen["path"]),
        chosen_date=str(chosen["snapshot_date"]),
        age_hours=age_hours,
        is_fallback=bool(is_fallback),
        status=status,
    )
    _progress(
        "h_stock_snapshot_decision",
        today_utc=today_utc,
        chosen_path=str(chosen["path"]),
        chosen_date=str(chosen["snapshot_date"]),
        age_hours=f"{_round_half_up(age_hours, 2):.2f}",
        is_fallback="1" if is_fallback else "0",
        action=action,
    )
    if action == "abort":
        if require_today and is_fallback:
            raise RuntimeError(
                f"[H110] stock snapshot require-today violation: today={today_utc} "
                f"chosen_date={chosen['snapshot_date']} source={chosen['path']}"
            )
        raise RuntimeError(
            f"[H110] stock snapshot too old: age_hours={_round_half_up(age_hours, 2):.2f} "
            f"max_age_hours={_round_half_up(max_age_hours, 2):.2f} source={chosen['path']}"
        )

    stock_source_path = chosen["path"]
    stock_df = chosen["df"]
    sku_col = str(chosen["sku_col"])
    qty_col = str(chosen["qty_col"])

    stock_by_sku_by_source: list[tuple[str, dict[str, float | None]]] = []
    inbound_by_sku_by_source: list[tuple[str, dict[str, float | None]]] = []
    for rec in ordered_candidates:
        source_path = str(rec["path"])
        source_sku_col = str(rec["sku_col"])
        source_qty_col = str(rec["qty_col"])
        source_df = rec["df"]
        source_cols = set(source_df.columns)
        source_map: dict[str, float | None] = {}
        source_inbound_map: dict[str, float | None] = {}
        for _, row in source_df.iterrows():
            sku_key = _norm(row.get(source_sku_col, "")).upper()
            if not sku_key:
                continue
            qty_val = _parse_stock_qty(row.get(source_qty_col, ""))
            inbound_val = _parse_inbound_total_from_row(row, source_cols)
            prev = source_map.get(sku_key)
            prev_inbound = source_inbound_map.get(sku_key)
            if qty_val is None:
                if prev is None:
                    source_map[sku_key] = None
            elif prev is None:
                source_map[sku_key] = qty_val
            else:
                source_map[sku_key] = float(max(float(prev), float(qty_val)))
            if inbound_val is None:
                if prev_inbound is None:
                    source_inbound_map[sku_key] = None
                continue
            if prev_inbound is None:
                source_inbound_map[sku_key] = inbound_val
            else:
                source_inbound_map[sku_key] = float(max(float(prev_inbound), float(inbound_val)))
        stock_by_sku_by_source.append((source_path, source_map))
        inbound_by_sku_by_source.append((source_path, source_inbound_map))

    eligible_rows: list[dict[str, str]] = []
    available_stock_by_sku: dict[str, str] = {}
    inbound_units_by_sku: dict[str, str] = {}
    excluded_rows: list[dict[str, str]] = []
    excluded_oos = 0
    excluded_unknown = 0
    for row in due_rows:
        sku = _norm(row.get("sku", "")).upper()
        qty: float | None = None
        for _, source_map in stock_by_sku_by_source:
            if sku not in source_map:
                continue
            candidate_qty = source_map.get(sku)
            # If the source has SKU but blank qty, continue to next source.
            if candidate_qty is None:
                continue
            if qty is None:
                qty = float(candidate_qty)
            else:
                qty = float(max(float(qty), float(candidate_qty)))
        inbound_qty: float | None = None
        for _, source_map in inbound_by_sku_by_source:
            if sku not in source_map:
                continue
            candidate_inbound = source_map.get(sku)
            if candidate_inbound is None:
                continue
            if inbound_qty is None:
                inbound_qty = float(candidate_inbound)
            else:
                inbound_qty = float(max(float(inbound_qty), float(candidate_inbound)))
        if qty is None:
            if inbound_qty is not None and float(inbound_qty) > 0:
                available_stock_by_sku[sku] = "0.00"
                inbound_units_by_sku[sku] = _fmt_stock_qty(float(inbound_qty))
                eligible_rows.append(row)
                continue
            excluded_unknown += 1
            excluded_rows.append({"sku": sku, "stock_qty": "", "reason": "STOCK_UNKNOWN"})
            continue
        if float(qty) <= 0:
            if inbound_qty is not None and float(inbound_qty) > 0:
                available_stock_by_sku[sku] = _fmt_stock_qty(float(qty))
                inbound_units_by_sku[sku] = _fmt_stock_qty(float(inbound_qty))
                eligible_rows.append(row)
                continue
            excluded_oos += 1
            excluded_rows.append({"sku": sku, "stock_qty": _norm(_round_half_up(float(qty), 2)), "reason": "OUT_OF_STOCK"})
            continue
        available_stock_by_sku[sku] = _fmt_stock_qty(float(qty))
        inbound_units_by_sku[sku] = _fmt_stock_qty(float(inbound_qty)) if inbound_qty is not None else ""
        eligible_rows.append(row)

    excluded_path = _write_excluded_stock_file(
        today_utc=today_utc,
        stock_source_path=str(stock_source_path),
        excluded_rows=excluded_rows,
    )

    summary = {
        "scope_total": str(len(due_rows)),
        "eligible": str(len(eligible_rows)),
        "excluded_oos": str(excluded_oos),
        "excluded_unknown": str(excluded_unknown),
        "stock_source": str(stock_source_path),
        "stock_sku_col": sku_col,
        "stock_qty_col": qty_col,
        "stock_snapshot_date": str(chosen["snapshot_date"]),
        "stock_snapshot_age_hours": f"{_round_half_up(age_hours, 2):.2f}",
        "stock_snapshot_is_fallback": "1" if is_fallback else "0",
        "stock_snapshot_status": status,
        "stock_snapshot_action": action,
        "stock_snapshot_status_path": str(status_path),
        "excluded_path": str(excluded_path),
        "available_stock_by_sku": available_stock_by_sku,
        "inbound_units_by_sku": inbound_units_by_sku,
    }
    _progress(
        "h_universe_stock_decision",
        today_utc=today_utc,
        scope_total=summary["scope_total"],
        eligible=summary["eligible"],
        excluded_oos=summary["excluded_oos"],
        excluded_unknown=summary["excluded_unknown"],
        stock_source=summary["stock_source"],
        stock_col=summary["stock_qty_col"],
        sku_col=summary["stock_sku_col"],
    )
    return eligible_rows, summary


def _daily_intel_today_stats(*, today_utc_date: str, skus: set[str] | None = None) -> dict[str, int | str]:
    path = phase1_storage.phase1_table_path("sku_daily_intel")
    out: dict[str, int | str] = {
        "path": str(path),
        "rows_today": 0,
        "unique_skus_today": 0,
        "matched_skus_today": 0,
    }
    if not path.exists():
        return out
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return out
    if df.empty or "date_utc" not in df.columns or "sku" not in df.columns:
        return out
    today_df = df.loc[df["date_utc"].astype(str).str.strip().eq(today_utc_date)].copy()
    today_skus = {
        _norm(v).upper()
        for v in today_df.get("sku", "").astype(str).tolist()
        if _norm(v)
    }
    out["rows_today"] = int(len(today_df.index))
    out["unique_skus_today"] = int(len(today_skus))
    if skus:
        out["matched_skus_today"] = int(len({s for s in skus if _norm(s)} & today_skus))
    return out


def _as_bool_text(value: object, default: str = "0") -> str:
    text = _norm(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    return default


def _append_sku_decision_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "decision_ts_utc",
        "run_id",
        "sku",
        "repricing_enabled",
        "observe_effective",
        "write_effective",
        "market_data_present",
        "decision",
        "reason_code",
    ]
    _append_csv_rows(
        H110_SKU_DECISION_LOG_PATH,
        headers,
        [{k: _norm(row.get(k, "")) for k in headers} for row in rows],
    )


def _append_sku_lifecycle_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "event_ts_utc",
        "run_id",
        "sku",
        "event",
        "elapsed_ms",
        "decision",
        "write_status",
        "reason_codes_csv",
        "error",
    ]
    _append_csv_rows(
        H110_SKU_LIFECYCLE_LOG_PATH,
        headers,
        [{k: _norm(row.get(k, "")) for k in headers} for row in rows],
    )


def _load_canonical_universe(now_utc: datetime) -> list[dict[str, str]]:
    phase1_sku_scope.build_and_write_scope(asof_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
    if not CANONICAL_UNIVERSE_PATH.exists():
        raise RuntimeError(f"[H110] universe missing: {CANONICAL_UNIVERSE_PATH}")
    try:
        scope_df = pd.read_csv(CANONICAL_UNIVERSE_PATH, dtype=str).fillna("")
    except Exception as exc:
        raise RuntimeError(f"[H110] universe unreadable: {exc}")
    if scope_df.empty:
        raise RuntimeError("[H110] universe empty")
    missing_cols = sorted([c for c in REQUIRED_UNIVERSE_COLUMNS if c not in scope_df.columns])
    if missing_cols:
        raise RuntimeError(f"[H110] universe schema missing columns: {','.join(missing_cols)}")

    sku_key = scope_df["sku"].astype(str).str.strip().str.upper()
    dupes = sku_key[sku_key.ne("") & sku_key.duplicated()].tolist()
    if dupes:
        raise RuntimeError(f"[H110] universe duplicate sku rows: {','.join(sorted(set(dupes))[:10])}")

    rows: list[dict[str, str]] = []
    for _, rec in scope_df.iterrows():
        row = {str(k): _norm(v) for k, v in rec.to_dict().items()}
        sku = _norm(row.get("sku", "")).upper()
        if not sku:
            continue
        row["sku"] = sku
        row["repricing_enabled"] = _as_bool_text(row.get("repricing_enabled", ""), "0")
        row["observe_effective"] = _as_bool_text(row.get("observe_effective", ""), "1")
        row["write_effective"] = _as_bool_text(row.get("write_effective", ""), "0")
        row["reason_code"] = _norm(row.get("reason_code", "")) or "unknown"
        rows.append(row)
    if not rows:
        raise RuntimeError("[H110] universe has no valid sku rows")
    return rows


def _load_manual_caps() -> tuple[dict[str, str], dict[str, str]]:
    by_sku: dict[str, str] = {}
    by_asin: dict[str, str] = {}
    if not MANUAL_CAPS_PATH.exists():
        return by_sku, by_asin
    try:
        df = pd.read_csv(MANUAL_CAPS_PATH, dtype=str).fillna("")
    except Exception:
        return by_sku, by_asin
    for _, row in df.iterrows():
        cap_raw = _norm(row.get("manual_max_price_gbp", ""))
        cap_val = _to_float(cap_raw)
        if cap_val is None or cap_val <= 0:
            continue
        cap_text = f"{cap_val:.2f}"
        sku_key = _norm(row.get("sku", "")).upper()
        asin_key = _norm(row.get("asin", "")).upper()
        if sku_key and sku_key not in by_sku:
            by_sku[sku_key] = cap_text
        if asin_key and asin_key not in by_asin:
            by_asin[asin_key] = cap_text
    return by_sku, by_asin


def _load_temp_floor_by_sku(allowed_skus: set[str] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    floor_by_sku: dict[str, str] = {}
    blocked_by_sku: dict[str, str] = {}
    snapshot_rows: list[dict[str, str]] = []
    trace_rows: list[dict[str, str]] = []
    asof_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        context = load_h_floor_context(
            product_db_path=PRODUCT_DB_PATH,
            token_ledger_path=TOKEN_LEDGER_PATH,
            token_cogs_path=TOKEN_COGS_LEDGER_PATH,
        )
    except Exception:
        context = HFloorContext(product_db_rows={}, token_cogs_by_sku={}, vat_policy=load_h_floor_vat_policy())

    sku_filter = {s.strip().upper() for s in (allowed_skus or set()) if s and s.strip()}
    for sku_key, row in context.product_db_rows.items():
        if not sku_key:
            continue
        if sku_filter and sku_key.upper() not in sku_filter:
            continue
        candidate_price = _to_float(row.get("live_listing_price", ""))
        if candidate_price is None or candidate_price <= 0:
            candidate_price = _to_float(row.get("last_sold_price", ""))
        if candidate_price is None:
            candidate_price = 0.0

        inputs, result = compute_h_floor_for_sku(sku_key, candidate_price, context=context)
        blocking = has_blocking_reason_codes(inputs.reason_codes)
        floor_total = _round_half_up(result.floor_total_gbp, 2)
        if (not blocking) and floor_total > 0:
            floor_by_sku[sku_key] = f"{floor_total:.2f}"
        elif blocking:
            blocked_by_sku[sku_key] = ",".join(inputs.reason_codes)

        snapshot_rows.append(
            {
                "asof_utc": asof_utc,
                "sku": sku_key,
                "order_id": "",
                "order_date_utc": "",
                "candidate_price_gbp": f"{_round_half_up(inputs.candidate_price_gbp, 2):.2f}",
                "vat_rate_market": f"{inputs.vat_rate:.6f}",
                "cogs_total_gbp": f"{_round_half_up(inputs.cogs_exvat_gbp, 2):.2f}",
                "fba_total_gbp": f"{_round_half_up(inputs.fba_exvat_gbp, 2):.2f}",
                "commission_total_gbp": f"{_round_half_up(inputs.referral_amount_gbp, 2):.2f}",
                "digital_fee_total_gbp": f"{_round_half_up(inputs.digital_fee_exvat_gbp, 2):.2f}",
                "fixed_total_gbp": "0.00",
                "break_even_total_gbp": f"{_round_half_up(result.break_even_total_gbp, 2):.2f}",
                "temp_floor_10roi_gbp": f"{floor_total:.2f}" if (not blocking and floor_total > 0) else "",
                "source_script": SOURCE,
            }
        )
        trace_rows.append(
            build_h_floor_trace_row(
                inputs=inputs,
                result=result,
                source_script=SOURCE,
                asof_utc=asof_utc,
            )
        )

    _append_temp_floor_snapshot(snapshot_rows)
    append_h_floor_trace_rows(trace_rows)
    return floor_by_sku, blocked_by_sku


def _resolve_marketplace_id(listing_row: dict[str, str], cfg_marketplace_id: str) -> str:
    explicit = _norm(cfg_marketplace_id) or _norm(listing_row.get("marketplace_id", ""))
    if explicit:
        return explicit
    code = _norm(listing_row.get("marketplace", "")).upper()
    mapped = MARKETPLACE_CODE_TO_ID.get(code, "")
    if mapped:
        return mapped
    return os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")


def _phase1_market_payload_from_snapshots(
    *,
    sku: str,
    asin: str,
    marketplace_id: str,
    our_seller_id: str,
    listing_row: dict[str, str],
) -> tuple[dict[str, object], str]:
    def _fallback_rival_offers_from_recent_snapshot() -> list[dict[str, object]]:
        if not OFFER_SNAPSHOT_FACTS_PATH.exists():
            return []
        try:
            df = pd.read_csv(OFFER_SNAPSHOT_FACTS_PATH, dtype=str).fillna("")
        except Exception:
            return []
        if df.empty or "sku" not in df.columns:
            return []
        scoped = df.loc[df.get("sku", "").astype(str).str.strip().str.upper().eq(sku.upper())].copy()
        if scoped.empty:
            return []
        if "snapshot_ts_utc" in scoped.columns:
            scoped = scoped.sort_values("snapshot_ts_utc", ascending=False)
            latest_ts = str(scoped.iloc[0].get("snapshot_ts_utc", "")).strip()
            if latest_ts:
                scoped = scoped.loc[scoped.get("snapshot_ts_utc", "").astype(str).str.strip().eq(latest_ts)].copy()
        rival_rows: list[dict[str, object]] = []
        for _, rec in scoped.iterrows():
            seller = _norm(rec.get("seller_id_canonical", ""))
            if not seller or seller.upper() == our_seller_id.upper():
                continue
            listing_price = _to_float(rec.get("listing_price_gbp", ""))
            shipping_price = _to_float(rec.get("shipping_gbp", ""))
            landed_price = _to_float(rec.get("landed_price_gbp", ""))
            if listing_price is None and landed_price is not None and shipping_price is not None:
                listing_price = landed_price - shipping_price
            listing_price = listing_price if listing_price is not None else 0.0
            shipping_price = shipping_price if shipping_price is not None else 0.0
            min_days = _to_int(rec.get("min_delivery_days", ""))
            max_days = _to_int(rec.get("max_delivery_days", ""))
            fulf = _norm(rec.get("fulfilment_channel", "")).upper()
            rival_rows.append(
                {
                    "SellerId": seller,
                    "ListingPrice": {"Amount": listing_price},
                    "Shipping": {"Amount": shipping_price},
                    "ShippingTime": {"minimumDays": min_days or 0, "maximumDays": max_days or (min_days or 0)},
                    "IsFulfilledByAmazon": fulf in {"FBA", "AFN", "AMAZON"},
                    "IsPrime": _to_bool(rec.get("is_prime", "")),
                    "IsFeaturedOfferWinner": str(rec.get("is_featured_offer_winner", "")).strip() == "1",
                }
            )
        return rival_rows

    if not listing_row:
        return {"asin": asin, "marketplaceId": marketplace_id, "offers": []}, ""
    try:
        seller_path = _latest_seller_snapshot()
        df = pd.read_csv(seller_path, dtype=str).fillna("")
    except Exception:
        df = pd.DataFrame()
    if "sku" in df.columns:
        scoped = df.loc[df.get("sku", "").astype(str).str.strip().str.upper().eq(sku.upper())].copy()
    else:
        scoped = df.head(0).copy()
    offers: list[dict[str, object]] = []
    for _, rec in scoped.iterrows():
        seller_id = _norm(rec.get("seller_id", ""))
        if not seller_id:
            continue
        listing_price = _to_float(rec.get("offer_price_gbp", ""))
        shipping_price = _to_float(rec.get("offer_shipping_price_gbp", ""))
        landed_price = _to_float(rec.get("offer_landed_price_gbp", ""))
        if listing_price is None and landed_price is not None and shipping_price is not None:
            listing_price = landed_price - shipping_price
        listing_price = listing_price if listing_price is not None else 0.0
        shipping_price = shipping_price if shipping_price is not None else 0.0
        min_days = _to_int(rec.get("min_delivery_days", ""))
        max_days = _to_int(rec.get("max_delivery_days", ""))
        fulf = _norm(rec.get("fulfilment_channel", "")).upper()
        offers.append(
            {
                "SellerId": seller_id,
                "ListingPrice": {"Amount": listing_price},
                "Shipping": {"Amount": shipping_price},
                "ShippingTime": {"minimumDays": min_days or 0, "maximumDays": max_days or (min_days or 0)},
                "IsFulfilledByAmazon": fulf in {"FBA", "AFN", "AMAZON"},
                "IsPrime": _to_bool(rec.get("is_prime", "")),
                "IsFeaturedOfferWinner": False,
            }
        )

    our_price = _to_float(listing_row.get("our_price", ""))
    if our_price is not None and not any(_norm(o.get("SellerId", "")).upper() == our_seller_id.upper() for o in offers):
        offers.append(
            {
                "SellerId": our_seller_id,
                "ListingPrice": {"Amount": our_price},
                "Shipping": {"Amount": 0.0},
                "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                "IsFulfilledByAmazon": True,
                "IsPrime": True,
                "IsFeaturedOfferWinner": False,
            }
        )
    # If current seller snapshot only has our offer, reuse the latest known rival snapshot rows.
    has_rival = any(_norm(o.get("SellerId", "")).upper() != our_seller_id.upper() for o in offers)
    if not has_rival:
        offers.extend(_fallback_rival_offers_from_recent_snapshot())

    buy_box_price = _to_float(listing_row.get("buy_box_price", ""))
    if buy_box_price is not None and offers:
        winner_idx = None
        winner_gap = 999999.0
        for idx, offer in enumerate(offers):
            listing_amt = _to_float((offer.get("ListingPrice", {}) or {}).get("Amount"))
            shipping_amt = _to_float((offer.get("Shipping", {}) or {}).get("Amount"))
            landed = (listing_amt or 0.0) + (shipping_amt or 0.0)
            gap = abs(landed - buy_box_price)
            if gap < winner_gap:
                winner_gap = gap
                winner_idx = idx
        if winner_idx is not None and winner_gap <= 0.02:
            offers[winner_idx]["IsFeaturedOfferWinner"] = True

    payload = {"asin": asin, "marketplaceId": marketplace_id, "offers": offers}
    listings_observed_price = _to_num_text(listing_row.get("our_price", ""), "")
    return payload, listings_observed_price


def _seller_id_from_env() -> str:
    return (
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    ).strip()


def _phase1_write_submitter(*, sku: str, marketplace_id: str, run_id: str):
    def _submit(target_price_gbp: str) -> dict[str, str]:
        try:
            load_dotenv_if_missing()
            access_token = get_lwa_access_token()
            seller_id = _seller_id_from_env()
            if not seller_id:
                raise RuntimeError("SELLER_ID missing from environment")
            result = patch_listings_item_price(
                access_token=access_token,
                seller_id=seller_id,
                sku=sku,
                marketplace_id=marketplace_id,
                product_type=os.environ.get("H_DEFAULT_PRODUCT_TYPE", "PRODUCT"),
                target_price_gbp=target_price_gbp,
                run_id=run_id,
                source_script=SOURCE,
                spapi_base_url=SPAPI_BASE_URL,
            )
            return {
                "ok": _norm(result.get("ok", "0")),
                "http_status": _norm(result.get("http_status", "")),
                "submission_id": _norm(result.get("submission_id", "")),
                "response_text": _norm(result.get("response_text", "")),
            }
        except Exception as exc:
            return {"ok": "0", "http_status": "", "submission_id": "", "response_text": str(exc)}

    return _submit


def _phase1_post_write_price_lookup(*, sku: str, marketplace_id: str, run_id: str):
    def _lookup() -> str:
        try:
            load_dotenv_if_missing()
            access_token = get_lwa_access_token()
            seller_id = _seller_id_from_env()
            if not seller_id:
                return ""
            payload = fetch_our_offer_prices(
                [sku],
                marketplace_id=marketplace_id,
                access_token=access_token,
                seller_id=seller_id,
                run_id=run_id,
                script_name=SOURCE,
                sleep_sec=0.0,
                timeout=8,
            )
        except Exception:
            return ""
        row = payload.get(sku, {}) if isinstance(payload, dict) else {}
        return _norm(row.get("price", ""))

    return _lookup


def _run_one_sku(
    *,
    cfg: dict,
    sku: str,
    read_only: bool,
    run_id: str,
    now_utc: datetime,
    manual_cap_by_sku: dict[str, str],
    manual_cap_by_asin: dict[str, str],
    temp_floor_by_sku: dict[str, str],
    temp_floor_blockers_by_sku: dict[str, str],
    daily_boundary_lock_by_sku: dict[str, dict[str, str]],
    boundary_lock_date_utc: str,
    universe_row: dict[str, str],
    listing_map: dict[str, dict[str, str]],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
    reentry_price_discovery_active: bool = False,
    reentry_event: bool = False,
    inbound_price_discovery_active: bool = False,
) -> dict[str, str]:
    sku = _norm(sku).upper()
    if not sku:
        raise RuntimeError("[H110] empty sku in run_one_sku")
    started_at = datetime.now(timezone.utc)
    _append_sku_lifecycle_rows(
        [
            {
                "event_ts_utc": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_id": run_id,
                "sku": sku,
                "event": "start",
            }
        ]
    )

    def _finalize_lifecycle(
        *,
        event: str,
        decision: str = "",
        write_status: str = "",
        reason_codes_csv: str = "",
        error: str = "",
    ) -> None:
        now = datetime.now(timezone.utc)
        elapsed_ms = max(int((now - started_at).total_seconds() * 1000), 0)
        _append_sku_lifecycle_rows(
            [
                {
                    "event_ts_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "run_id": run_id,
                    "sku": sku,
                    "event": event,
                    "elapsed_ms": str(elapsed_ms),
                    "decision": decision,
                    "write_status": write_status,
                    "reason_codes_csv": reason_codes_csv,
                    "error": error,
                }
            ]
        )

    def _marker_reason(prefix: str, exc: BaseException | None = None) -> str:
        parts = [prefix, sku]
        if exc is not None:
            parts.append(type(exc).__name__)
            msg = _norm(str(exc))[:180]
            if msg:
                parts.append(msg)
        return ":".join([p for p in parts if _norm(p)])

    def _return_out_row(out_row: dict[str, str]) -> dict[str, str]:
        _progress(
            "h110 sku_exec_exit_normal",
            sku=sku,
            run_id=run_id,
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
        )
        return out_row

    _progress("h110 run_one_sku start", sku=sku, run_id=run_id)
    _progress("h110 sku_exec_enter", sku=sku, run_id=run_id)

    listing_row = listing_map.get(sku, {})
    market_data_present = "1" if listing_row else "0"
    write_effective = _as_bool_text(universe_row.get("write_effective", ""), "0") == "1"
    repricing_enabled = _as_bool_text(universe_row.get("repricing_enabled", ""), "0") == "1"
    asin_override = _norm(_cfg_get(cfg, "asin", default="")).upper()
    asin = _norm(universe_row.get("asin", "")) or _norm(listing_row.get("asin", ""))
    if asin_override and _norm(_cfg_get(cfg, "sku", default="")).upper() == sku:
        asin = asin_override
    marketplace_id = _resolve_marketplace_id(listing_row, _norm(_cfg_get(cfg, "marketplace_id", default="")))
    seller_id = _norm(_cfg_get(cfg, "seller_id", default="")) or _seller_id_from_env()
    if not seller_id:
        raise SystemExit("[H110] phase1 pilot config missing seller_id and no seller id found in environment")

    writer_mode = "CODEX_H" if write_effective else "READ_ONLY"
    cohort_file = str(os.environ.get("H_PHASE_ENGINE_COHORT_FILE", "config/phase_engine_cohort.csv") or "").strip() or "config/phase_engine_cohort.csv"
    exclude_file = str(os.environ.get("H_PHASE_ENGINE_EXCLUDE_FILE", "config/phase_engine_exclusions.csv") or "").strip() or "config/phase_engine_exclusions.csv"
    in_cohort = phase1_phase_engine.sku_in_csv(cohort_file, sku)
    excluded = phase1_phase_engine.sku_in_csv(exclude_file, sku)
    if in_cohort and not excluded:
        writer_mode = "CODEX_H"
    if not listing_row:
        _progress(
            "h110 market_data_decision",
            sku=sku,
            today_utc=now_utc.strftime("%Y-%m-%d"),
            listing_snapshot_path=listing_snapshot_path,
            seller_snapshot_path=seller_snapshot_path,
            listing_row_exists="0",
            reason="SKIP_NO_MARKET_DATA",
        )
        out_row = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": "0",
            "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": "",
            "executioner_probe_type": "SKIP_NO_MARKET_DATA",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "SKIP_NO_MARKET_DATA",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": "",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "SKIP_NO_MARKET_DATA",
            "phase1_boundary_lock_mode": "set_pending",
            "phase1_boundary_lock_date": boundary_lock_date_utc,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
            "market_data_present": market_data_present,
            "write_effective": "1" if write_effective else "0",
            "repricing_enabled": "1" if repricing_enabled else "0",
            "universe_reason_code": _norm(universe_row.get("reason_code", "")),
            "decision": "skip_no_market_data",
        }
        _finalize_lifecycle(
            event="finish",
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
            reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
        )
        return _return_out_row(out_row)
    if not _has_active_offer_price(listing_row):
        _progress(
            "h110 market_data_decision",
            sku=sku,
            today_utc=now_utc.strftime("%Y-%m-%d"),
            listing_snapshot_path=listing_snapshot_path,
            seller_snapshot_path=seller_snapshot_path,
            listing_row_exists="1",
            active_price_exists="0",
            reason="SKIP_NO_ACTIVE_OFFER",
        )
        out_row = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": "0",
            "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": "",
            "executioner_probe_type": "SKIP_NO_ACTIVE_OFFER",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "SKIP_NO_ACTIVE_OFFER",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": "",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "SKIP_NO_ACTIVE_OFFER",
            "phase1_boundary_lock_mode": "set_pending",
            "phase1_boundary_lock_date": boundary_lock_date_utc,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
            "market_data_present": market_data_present,
            "write_effective": "1" if write_effective else "0",
            "repricing_enabled": "1" if repricing_enabled else "0",
            "universe_reason_code": _norm(universe_row.get("reason_code", "")),
            "decision": "skip_no_active_offer",
        }
        _finalize_lifecycle(
            event="finish",
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
            reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
        )
        return _return_out_row(out_row)

    default_hard_floor = _to_num_text(_cfg_get(cfg, "boundaries", "hard_floor_gbp", default="0.00"), "0.00")
    manual_cap_candidate = manual_cap_by_sku.get(sku) or manual_cap_by_asin.get(asin) or ""
    temp_floor_resolved = temp_floor_by_sku.get(sku, "")
    floor_blockers_csv = _norm(temp_floor_blockers_by_sku.get(sku, ""))
    if temp_floor_resolved:
        temp_floor_num = _to_float(temp_floor_resolved) or 0.0
        hard_floor_candidate = f"{temp_floor_num:.2f}"
    else:
        hard_floor_candidate = default_hard_floor

    lock_entry = daily_boundary_lock_by_sku.get(sku)
    lock_hard_floor = _norm((lock_entry or {}).get("hard_floor_gbp", ""))
    lock_manual_cap = _norm((lock_entry or {}).get("manual_cap_gbp", ""))
    using_daily_lock = bool(lock_hard_floor and lock_manual_cap)
    # Root-cause guard: if today's lock no longer matches fresh floor inputs, do not pin stale floor.
    if using_daily_lock and hard_floor_candidate:
        lock_floor_num = _to_float(lock_hard_floor)
        fresh_floor_num = _to_float(hard_floor_candidate)
        if lock_floor_num is not None and fresh_floor_num is not None:
            if abs(lock_floor_num - fresh_floor_num) >= 0.01:
                using_daily_lock = False
    if using_daily_lock:
        hard_floor_resolved = lock_hard_floor
        manual_cap_resolved = lock_manual_cap
    else:
        hard_floor_resolved = hard_floor_candidate
        manual_cap_resolved = manual_cap_candidate

    today = now_utc.strftime("%Y-%m-%d")
    if floor_blockers_csv:
        latest_daily_after = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
        daily_missing = "1" if _norm(latest_daily_after.get("date_utc", "")) != today else "0"
        out_row = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": daily_missing,
            "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_probe_type": "hold",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "FLOOR_INPUT_MISSING_HOLD",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": manual_cap_resolved,
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": ",".join([floor_blockers_csv, "H_FLOOR_INPUT_BLOCKED_NO_WRITE"]).strip(","),
            "phase1_boundary_lock_mode": "reused" if using_daily_lock else "set_pending",
            "phase1_boundary_lock_date": boundary_lock_date_utc,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
            "market_data_present": market_data_present,
            "write_effective": "1" if write_effective else "0",
            "repricing_enabled": "1" if repricing_enabled else "0",
            "universe_reason_code": _norm(universe_row.get("reason_code", "")),
            "decision": "skip_floor_input_missing",
        }
        _finalize_lifecycle(
            event="finish",
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
            reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
        )
        return _return_out_row(out_row)

    def _refresh_daily_intel_once() -> None:
        now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        phase1_main_loop.run_a_cycle(
            sku=sku,
            now_utc=now_iso,
            compliance_anchor_gbp=_cfg_get(
                cfg,
                "daily_intel",
                "compliance_anchor_gbp",
                default=_cfg_get(cfg, "boundaries", "manual_cap_gbp", default=listing_row.get("our_price", "0.00")),
            ),
            policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
            manual_cap_gbp=manual_cap_resolved,
            foep_price_gbp=_cfg_get(cfg, "daily_intel", "foep_price_gbp", default=listing_row.get("buy_box_price", "")),
            foep_status=_cfg_get(cfg, "daily_intel", "foep_status", default="MISSING"),
            foep_last_refresh_utc=_cfg_get(cfg, "daily_intel", "foep_last_refresh_utc", default=now_iso),
            cpt_gbp=_cfg_get(cfg, "daily_intel", "cpt_gbp", default=""),
            cpt_last_refresh_utc=_cfg_get(cfg, "daily_intel", "cpt_last_refresh_utc", default=now_iso),
            cpt_status=_cfg_get(cfg, "daily_intel", "cpt_status", default="MISSING"),
            last_known_safe_gbp=_cfg_get(cfg, "daily_intel", "last_known_safe_gbp", default=listing_row.get("our_price", "")),
            foep_stale_hours=int(float(_cfg_get(cfg, "eligibility", "foep_stale_hours", default=48))),
            foep_sanity_min_mult=_cfg_get(cfg, "eligibility", "foep_sanity_min_mult", default="0.50"),
            foep_sanity_max_mult=_cfg_get(cfg, "eligibility", "foep_sanity_max_mult", default="2.00"),
            market_reference_price_gbp=_cfg_get(cfg, "daily_intel", "market_reference_price_gbp", default=listing_row.get("buy_box_price", "")),
        )

    allow_intraday_intel_refresh = _to_bool(
        _cfg_get(cfg, "allow_h_intraday_intel_refresh", default=False),
        default=False,
    )

    payload, listings_observed_price = _phase1_market_payload_from_snapshots(
        sku=sku,
        asin=asin,
        marketplace_id=marketplace_id,
        our_seller_id=seller_id,
        listing_row=listing_row,
    )
    _progress("h110 run_one_sku market_payload_ready", sku=sku, offers=len(payload.get("offers", [])))
    cfg_live = _to_bool(_cfg_get(cfg, "enabled_live_writes", default=False), default=False)
    effective_live = bool(
        writer_mode == "CODEX_H"
        and not read_only
        and cfg_live
    )
    submitter = _phase1_write_submitter(sku=sku, marketplace_id=marketplace_id, run_id=run_id) if effective_live else None
    post_write_lookup = _phase1_post_write_price_lookup(sku=sku, marketplace_id=marketplace_id, run_id=run_id) if effective_live else None
    _progress(
        "h110 run_one_sku h_cycle_start",
        sku=sku,
        writer_mode=writer_mode,
        effective_live="1" if effective_live else "0",
    )
    _progress(
        "h110 sku_exec_pre_write",
        sku=sku,
        run_id=run_id,
        writer_mode=writer_mode,
        effective_live="1" if effective_live else "0",
    )
    try:
        h_out = phase1_main_loop.run_h_cycle(
            sku=sku,
            asin=asin,
            marketplace_id=marketplace_id,
            our_seller_id=seller_id,
            pricing_writer_mode=writer_mode,
            enabled_live_writes=effective_live,
            current_price_gbp=_to_num_text(listing_row.get("our_price", ""), "0.00"),
            hard_floor_gbp=hard_floor_resolved,
            manual_cap_gbp=manual_cap_resolved,
            max_step_down_gbp=_cfg_get(cfg, "guardrails", "max_step_down_gbp", default="0.20"),
            max_step_up_gbp=_cfg_get(cfg, "guardrails", "max_step_up_gbp", default="0.20"),
            max_daily_drop_gbp=_cfg_get(cfg, "guardrails", "max_daily_drop_gbp", default="0.60"),
            daily_drop_used_gbp=_cfg_get(cfg, "guardrails", "daily_drop_used_gbp", default="0.00"),
            delta_tolerance_gbp=_cfg_get(cfg, "learning", "delta_tolerance_gbp", default="0.02"),
            stable_buffer_gbp=_cfg_get(cfg, "learning", "stable_buffer_gbp", default="0.02"),
            min_clean_tests_for_confidence=int(float(_cfg_get(cfg, "learning", "min_clean_tests_for_confidence", default=5))),
            price_apply_tolerance_gbp=_cfg_get(cfg, "guardrails", "price_apply_tolerance_gbp", default="0.01"),
            policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
            market_payload=payload,
            listings_observed_price_gbp=listings_observed_price,
            write_submitter=submitter,
            post_write_observed_price_lookup=post_write_lookup,
            now_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            daily_intel_refresher=_refresh_daily_intel_once if allow_intraday_intel_refresh else None,
            reentry_price_discovery_active=reentry_price_discovery_active,
            reentry_event=reentry_event,
            inbound_price_discovery_active=inbound_price_discovery_active,
        )
    except BaseException as exc:
        _progress(
            "h110 sku_exec_abnormal_exit",
            sku=sku,
            run_id=run_id,
            error_type=type(exc).__name__,
            error=_norm(str(exc))[:240],
        )
        _finalize_lifecycle(event="error", error=_norm(str(exc))[:500])
        _ensure_terminal_completion_marker(reason=_marker_reason("sku_exec_abnormal_exit", exc))
        raise
    _progress(
        "h110 sku_exec_post_write",
        sku=sku,
        run_id=run_id,
        state=_norm(h_out.state),
        write_status=_norm(h_out.write_status),
    )
    _progress("h110 run_one_sku h_cycle_done", sku=sku, state=_norm(h_out.state), write_status=_norm(h_out.write_status))
    if not using_daily_lock:
        daily_boundary_lock_by_sku[sku] = {
            "hard_floor_gbp": hard_floor_resolved,
            "manual_cap_gbp": manual_cap_resolved,
            "final_ceiling_landed_gbp": _norm(h_out.final_ceiling_landed_gbp),
            "locked_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    latest_daily_after = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
    daily_missing = "1" if _norm(latest_daily_after.get("date_utc", "")) != today else "0"

    out_row = {
        "phase1_pilot": "1",
        "phase1_sku": sku,
        "phase1_asin": asin,
        "daily_intel_missing_for_today": daily_missing,
        "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executioner_probe_type": _norm(h_out.state),
        "executioner_live_write_attempted": "1" if effective_live else "0",
        "executioner_live_write_success": "1" if _norm(h_out.write_status) == "APPLIED" else "0",
        "write_status": _norm(h_out.write_status),
        "writer_mode": writer_mode,
        "hard_floor_applied_gbp": hard_floor_resolved,
        "manual_cap_applied_gbp": manual_cap_resolved,
        "final_ceiling_landed_gbp": _norm(h_out.final_ceiling_landed_gbp),
        "reason_codes_csv": ",".join(h_out.reason_codes),
        "phase1_boundary_lock_mode": "reused" if using_daily_lock else "set",
        "phase1_boundary_lock_date": boundary_lock_date_utc,
        "phase1_boundary_lock_final_ceiling_gbp": _norm((daily_boundary_lock_by_sku.get(sku) or {}).get("final_ceiling_landed_gbp", "")),
        "blocked_due_to_missing_intel": _norm(h_out.blocked_due_to_missing_intel),
        "blocked_due_to_stale_intel": _norm(h_out.blocked_due_to_stale_intel),
        "refresh_attempted_count": _norm(h_out.refresh_attempted_count),
        "refresh_throttled_count": _norm(h_out.refresh_throttled_count),
        "market_data_present": market_data_present,
        "write_effective": "1" if write_effective else "0",
        "repricing_enabled": "1" if repricing_enabled else "0",
        "universe_reason_code": _norm(universe_row.get("reason_code", "")),
        "decision": "execute",
    }
    _finalize_lifecycle(
        event="finish",
        decision=_norm(out_row.get("decision", "")),
        write_status=_norm(out_row.get("write_status", "")),
        reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
    )
    return _return_out_row(out_row)


def _run_once(*, cfg: dict, read_only: bool, run_id: str, now_utc: datetime) -> dict[str, str]:
    cfg = dict(cfg or {})
    _progress("h110 run_once start", run_id=run_id, read_only="1" if read_only else "0")
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_utc = now_utc.strftime("%Y-%m-%d")
    universe_rows_raw = _load_canonical_universe(now_utc)
    universe_raw_by_sku = {
        _norm(r.get("sku", "")).upper(): r for r in universe_rows_raw if _norm(r.get("sku", ""))
    }
    universe_rows, scope_summary = _apply_scope_universe_filter(
        universe_rows=universe_rows_raw,
        today_utc=today_utc,
    )
    universe_by_sku = {r["sku"]: r for r in universe_rows}
    observe_rows = [r for r in universe_rows if _as_bool_text(r.get("observe_effective", ""), "1") == "1"]
    if not observe_rows:
        _append_sku_decision_rows(
            [
                {
                    "decision_ts_utc": now_iso,
                    "run_id": run_id,
                    "sku": "",
                    "repricing_enabled": "0",
                    "observe_effective": "0",
                    "write_effective": "0",
                    "market_data_present": "",
                    "decision": "skip_observe_disabled_all",
                    "reason_code": "observe_disabled_all",
                }
            ]
        )
        return {
            "phase1_pilot": "1",
            "phase1_sku": "",
            "phase1_skus_processed_csv": "",
            "phase1_skus_processed_count": "0",
            "phase1_skus_skipped_cooldown_count": "0",
            "phase1_skus_skipped_parked_count": str(
                sum(1 for r in universe_rows if _as_bool_text(r.get("repricing_enabled", ""), "0") == "0")
            ),
            "phase1_skus_skipped_out_of_stock_count": str(
                sum(1 for r in universe_rows if "out_of_stock" in _norm(r.get("reason_code", "")).lower())
            ),
            "phase1_scan_cooldown_minutes": "0",
            "phase1_next_due_sleep_seconds": "0",
            "phase1_next_due_sku": "",
            "phase1_target_universe_mode": "canonical_scope",
            "phase1_target_universe_source": str(CANONICAL_UNIVERSE_PATH),
            "phase1_target_universe_mode_source": "phase1_sku_scope",
            "phase1_target_universe_candidate_count": str(len(universe_rows)),
            "phase1_target_universe_resolved_count": str(len(observe_rows)),
            "phase1_target_universe_skipped_no_listing_count": "0",
            "phase1_target_universe_skipped_out_of_stock_count": str(
                sum(1 for r in universe_rows if "out_of_stock" in _norm(r.get("reason_code", "")).lower())
            ),
            "phase1_target_universe_notes_csv": "OBSERVE_DISABLED_ALL",
            "phase1_scope_total": scope_summary["scope_total"],
            "phase1_scope_excluded_dropped_count": scope_summary["excluded_dropped"],
            "phase1_scope_excluded_parked_count": scope_summary["excluded_parked"],
            "phase1_scope_remaining_count": scope_summary["remaining"],
            "phase1_scope_excluded_path": scope_summary["excluded_path"],
            "phase1_scope_source_path": scope_summary["scope_source"],
            "phase1_boundary_lock_date": now_utc.strftime("%Y-%m-%d"),
            "phase1_boundary_lock_sku_count": "0",
            "phase1_boundary_lock_mode": "",
            "phase1_boundary_lock_final_ceiling_gbp": "",
            "daily_intel_missing_for_today": "0",
            "daily_intel_normal_processed_count": "0",
            "daily_intel_normal_missing_count": "0",
            "daily_intel_exception_processed_count": "0",
            "daily_intel_exception_missing_count": "0",
            "daily_intel_gate_policy": "STRICT_ALL",
            "last_executioner_utc": now_iso,
            "executioner_ran_utc": "",
            "executioner_probe_type": "NO_SKU_OBSERVE_ENABLED",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "NO_SKU_OBSERVE_ENABLED",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "NO_SKU_OBSERVE_ENABLED",
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
        }
    try:
        listing_snapshot_path_obj = _latest_listing_snapshot()
        listing_map = _load_listing_row_map(listing_snapshot_path_obj)
        listing_snapshot_path = str(listing_snapshot_path_obj)
        try:
            seller_snapshot_path = str(_latest_seller_snapshot())
        except Exception:
            seller_snapshot_path = ""
    except Exception as exc:
        raise RuntimeError(f"[H110] snapshot unreadable/corrupt: {exc}")

    scan_state = _read_json(SKU_SCAN_STATE_PATH, default={"last_scan_utc": {}, "daily_boundary_lock": {}})
    last_scan_utc = scan_state.get("last_scan_utc", {})
    if not isinstance(last_scan_utc, dict):
        last_scan_utc = {}
    boundary_lock = scan_state.get("daily_boundary_lock", {})
    if not isinstance(boundary_lock, dict):
        boundary_lock = {}
    if _norm(boundary_lock.get("date_utc", "")) != today_utc:
        boundary_lock = {"date_utc": today_utc, "by_sku": {}}
    boundary_lock_by_sku = boundary_lock.get("by_sku", {})
    if not isinstance(boundary_lock_by_sku, dict):
        boundary_lock_by_sku = {}

    cooldown_minutes = max(int(float(_cfg_get(cfg, "scan_cooldown_minutes", default=15))), 0)
    # Run-once should process the full current universe deterministically.
    if _to_bool(os.environ.get("H_RUN_ONCE", "0"), default=False):
        cooldown_minutes = 0
    spacing_seconds = max(float(_cfg_get(cfg, "sku_call_spacing_seconds", default=2.0)), 0.0)
    spacing_seconds = max(_env_float("H110_SKU_CALL_SPACING_SECONDS_OVERRIDE", spacing_seconds), 0.0)
    max_skus_raw = float(_cfg_get(cfg, "max_skus_per_run", default=0) or 0)
    # max_skus_per_run <= 0 means "no cap": process all due in-stock SKUs.
    max_skus_per_run = int(max_skus_raw) if max_skus_raw > 0 else 0
    max_skus_override = _env_int("H110_MAX_SKUS_PER_RUN_OVERRIDE", max_skus_per_run)
    if max_skus_override > 0:
        max_skus_per_run = max_skus_override
    manual_cap_by_sku, manual_cap_by_asin = _load_manual_caps()
    _progress("h110 run_once manual_caps_loaded", sku_caps=len(manual_cap_by_sku), asin_caps=len(manual_cap_by_asin))
    universe_skus = {r.get("sku", "").strip().upper() for r in universe_rows if _norm(r.get("sku", ""))}
    temp_floor_by_sku, temp_floor_blockers_by_sku = _load_temp_floor_by_sku(universe_skus)
    _progress(
        "h110 run_once temp_floor_loaded",
        floor_count=len(temp_floor_by_sku),
        blocker_count=len(temp_floor_blockers_by_sku),
    )

    due_rows: list[dict[str, str]] = []
    skipped_cooldown: list[str] = []
    cooldown_wait_candidates: list[tuple[int, str]] = []
    decision_rows: list[dict[str, str]] = []
    skipped_out_of_stock = [
        r["sku"] for r in universe_rows if "out_of_stock" in _norm(r.get("reason_code", "")).lower()
    ]
    skipped_parked_count = sum(1 for r in universe_rows if _as_bool_text(r.get("repricing_enabled", ""), "0") == "0")
    for sku, urow in sorted(universe_by_sku.items()):
        if _as_bool_text(urow.get("observe_effective", ""), "1") == "1":
            continue
        decision_rows.append(
            {
                "decision_ts_utc": now_iso,
                "run_id": run_id,
                "sku": sku,
                "repricing_enabled": _as_bool_text(urow.get("repricing_enabled", ""), "0"),
                "observe_effective": "0",
                "write_effective": _as_bool_text(urow.get("write_effective", ""), "0"),
                "market_data_present": "1" if sku in listing_map else "0",
                "decision": "skip_observe_disabled",
                "reason_code": _norm(urow.get("reason_code", "")) or "observe_disabled",
            }
        )
    for urow in sorted(
        observe_rows,
        key=lambda r: (
            0 if _as_bool_text(r.get("write_effective", ""), "0") == "1" else 1,
            r.get("sku", ""),
        ),
    ):
        sku = _norm(urow.get("sku", "")).upper()
        if not sku:
            continue
        last_dt = _to_dt(last_scan_utc.get(sku, ""))
        if last_dt is None:
            due_rows.append(urow)
            continue
        elapsed_seconds = max((now_utc - last_dt).total_seconds(), 0.0)
        if elapsed_seconds >= float(cooldown_minutes) * 60.0:
            due_rows.append(urow)
        else:
            skipped_cooldown.append(sku)
            remaining_seconds = max(int(math.ceil(float(cooldown_minutes) * 60.0 - elapsed_seconds)), 1)
            cooldown_wait_candidates.append((remaining_seconds, sku))
            decision_rows.append(
                {
                    "decision_ts_utc": now_iso,
                    "run_id": run_id,
                    "sku": sku,
                    "repricing_enabled": _as_bool_text(urow.get("repricing_enabled", ""), "0"),
                    "observe_effective": "1",
                    "write_effective": _as_bool_text(urow.get("write_effective", ""), "0"),
                    "market_data_present": "1" if sku in listing_map else "0",
                    "decision": "skip_cooldown",
                    "reason_code": "cooldown",
                }
            )

    due_rows, stock_summary = _apply_stock_universe_filter(
        due_rows=due_rows,
        now_utc=now_utc,
        today_utc=today_utc,
    )
    # Apply cap after stock filtering so in-stock candidates are not starved
    # by out-of-stock rows that happened to appear earlier in the due list.
    if max_skus_per_run > 0:
        due_rows = due_rows[:max_skus_per_run]
    normal_count = len(due_rows)
    include_stocked_excluded = _to_bool(os.environ.get(H_INCLUDE_STOCKED_EXCLUDED_ENV, "0"), default=False)
    exception_rows = _load_stocked_excluded_rows(today_utc) if include_stocked_excluded else []
    exception_included_rows: list[dict[str, str]] = []
    exception_by_sku = {r.get("sku", "").upper(): r for r in exception_rows if _norm(r.get("sku", ""))}
    exception_count = 0
    overlap_count = 0
    if include_stocked_excluded and exception_by_sku:
        due_by_sku = {_norm(r.get("sku", "")).upper(): r for r in due_rows if _norm(r.get("sku", ""))}
        exception_candidates: list[tuple[str, dict[str, str]]] = []
        for sku, exc_row in sorted(exception_by_sku.items()):
            raw_row = universe_raw_by_sku.get(sku)
            if raw_row is None:
                continue
            exception_candidates.append((sku, exc_row))
        exception_count = len(exception_candidates)
        overlap_count = sum(1 for sku, _ in exception_candidates if sku in due_by_sku)
        for sku, exc_row in exception_candidates:
            if sku in due_by_sku:
                continue
            raw_row = universe_raw_by_sku[sku]
            due_rows.append(raw_row)
            due_by_sku[sku] = raw_row
            exception_included_rows.append(exc_row)
    exception_path = ""
    if include_stocked_excluded:
        exception_path = str(_write_exception_included_file(today_utc=today_utc, rows=exception_included_rows))
    _progress(
        "h_universe_exception_decision",
        today_utc=today_utc,
        enabled="1" if include_stocked_excluded else "0",
        normal_count=normal_count,
        exception_count=exception_count,
        overlap_count=overlap_count,
        final_process_count=len(due_rows),
    )
    _progress(
        "h110 run_once due_scan_complete",
        due_count=len(due_rows),
        skipped_cooldown_count=len(skipped_cooldown),
        skipped_out_of_stock_count=len(skipped_out_of_stock),
        excluded_stock_oos=stock_summary["excluded_oos"],
        excluded_stock_unknown=stock_summary["excluded_unknown"],
    )
    stock_qty_by_sku_raw = stock_summary.get("available_stock_by_sku", {})
    stock_qty_by_sku = stock_qty_by_sku_raw if isinstance(stock_qty_by_sku_raw, dict) else {}
    inbound_units_by_sku_raw = stock_summary.get("inbound_units_by_sku", {})
    inbound_units_by_sku = inbound_units_by_sku_raw if isinstance(inbound_units_by_sku_raw, dict) else {}
    reentry_state = _read_json(H_REENTRY_STATE_PATH, default={"skus": {}})
    reentry_state_by_sku = reentry_state.get("skus", {}) if isinstance(reentry_state, dict) else {}
    if not isinstance(reentry_state_by_sku, dict):
        reentry_state_by_sku = {}
    inbound_state = _read_json(H_INBOUND_ACTIVATION_STATE_PATH, default={"skus": {}})
    inbound_state_by_sku = inbound_state.get("skus", {}) if isinstance(inbound_state, dict) else {}
    if not isinstance(inbound_state_by_sku, dict):
        inbound_state_by_sku = {}

    run_rows: list[dict[str, str]] = []
    for idx, urow in enumerate(due_rows):
        sku = _norm(urow.get("sku", "")).upper()
        current_stock_qty = _to_float(stock_qty_by_sku.get(sku, ""))
        current_inbound_units = _to_float(inbound_units_by_sku.get(sku, ""))
        state_row = reentry_state_by_sku.get(sku, {})
        if not isinstance(state_row, dict):
            state_row = {}
        previous_stock_qty = _to_float(state_row.get("previous_available_stock", ""))
        reentry_started_utc = _norm(state_row.get("reentry_started_utc", ""))
        reentry_started_dt = _to_dt(reentry_started_utc)
        reentry_start_stock_qty = _to_float(state_row.get("reentry_start_stock", ""))
        reentry_active = _as_bool_text(state_row.get("reentry_active", "0"), "0") == "1"
        reentry_event = bool(
            previous_stock_qty is not None
            and previous_stock_qty <= 0.0
            and current_stock_qty is not None
            and current_stock_qty > 0.0
        )

        if reentry_event:
            reentry_active = True
            reentry_started_utc = now_iso
            reentry_start_stock_qty = current_stock_qty
            _progress(
                "h_reentry_event",
                sku=sku,
                previous_available_stock=_fmt_stock_qty(previous_stock_qty),
                current_available_stock=_fmt_stock_qty(current_stock_qty),
                marker="REENTRY_PRICE_DISCOVERY",
            )
        elif reentry_active:
            first_sale_detected = bool(
                reentry_start_stock_qty is not None
                and current_stock_qty is not None
                and current_stock_qty < reentry_start_stock_qty
            )
            elapsed_seconds = (
                (now_utc - reentry_started_dt).total_seconds()
                if reentry_started_dt is not None
                else 0.0
            )
            if first_sale_detected or elapsed_seconds >= 86400.0:
                reentry_active = False
                reentry_started_utc = ""
                reentry_start_stock_qty = None
                _progress(
                    "h_reentry_mode_exit",
                    sku=sku,
                    reason="first_sale" if first_sale_detected else "24h_elapsed",
                    current_available_stock=_fmt_stock_qty(current_stock_qty),
                )
        inbound_state_row = inbound_state_by_sku.get(sku, {})
        if not isinstance(inbound_state_row, dict):
            inbound_state_row = {}
        previous_inbound_units = _to_float(inbound_state_row.get("previous_inbound_units", "0"))
        previous_available_units = _to_float(inbound_state_row.get("previous_available_units", ""))
        inbound_activation_event = bool(
            previous_inbound_units is not None
            and previous_inbound_units <= 0.0
            and current_inbound_units is not None
            and current_inbound_units > 0.0
            and current_stock_qty is not None
            and current_stock_qty <= 0.0
        )
        inbound_discovery_active = bool(
            current_stock_qty is not None
            and current_stock_qty <= 0.0
            and current_inbound_units is not None
            and current_inbound_units > 0.0
        )
        if inbound_activation_event:
            _progress(
                "h_inbound_activation_event",
                sku=sku,
                previous_inbound_units=_fmt_stock_qty(previous_inbound_units),
                current_inbound_units=_fmt_stock_qty(current_inbound_units),
                previous_available_units=_fmt_stock_qty(previous_available_units),
                current_available_units=_fmt_stock_qty(current_stock_qty),
                marker="INBOUND_PRICE_DISCOVERY",
            )

        try:
            row = _run_one_sku(
                cfg=cfg,
                sku=sku,
                read_only=read_only,
                run_id=f"{run_id}_{idx+1:02d}",
                now_utc=now_utc,
                manual_cap_by_sku=manual_cap_by_sku,
                manual_cap_by_asin=manual_cap_by_asin,
                temp_floor_by_sku=temp_floor_by_sku,
                temp_floor_blockers_by_sku=temp_floor_blockers_by_sku,
                daily_boundary_lock_by_sku=boundary_lock_by_sku,
                boundary_lock_date_utc=today_utc,
                universe_row=urow,
                listing_map=listing_map,
                listing_snapshot_path=listing_snapshot_path,
                seller_snapshot_path=seller_snapshot_path,
                reentry_price_discovery_active=reentry_active,
                reentry_event=reentry_event,
                inbound_price_discovery_active=inbound_discovery_active,
            )
        except BaseException as exc:
            _progress(
                "h110 sku_exec_abnormal_exit",
                sku=sku,
                run_id=run_id,
                stage="run_once_boundary",
                error_type=type(exc).__name__,
                error=_norm(str(exc))[:240],
            )
            _ensure_terminal_completion_marker(
                reason="run_once_sku_exec_abnormal_exit:"
                f"{sku}:{type(exc).__name__}:{_norm(str(exc))[:180]}"
            )
            raise
        row["reentry_event"] = "1" if reentry_event else "0"
        row["reentry_price_discovery_active"] = "1" if reentry_active else "0"
        row["current_available_stock"] = _fmt_stock_qty(current_stock_qty)
        row["current_inbound_units"] = _fmt_stock_qty(current_inbound_units)
        row["inbound_activation_event"] = "1" if inbound_activation_event else "0"
        row["inbound_discovery_active"] = "1" if inbound_discovery_active else "0"
        run_rows.append(row)
        reentry_state_by_sku[sku] = {
            "previous_available_stock": _fmt_stock_qty(current_stock_qty),
            "reentry_active": "1" if reentry_active else "0",
            "reentry_started_utc": reentry_started_utc if reentry_active else "",
            "reentry_start_stock": _fmt_stock_qty(reentry_start_stock_qty) if reentry_active else "",
            "updated_utc": now_iso,
        }
        inbound_state_by_sku[sku] = {
            "previous_available_units": _fmt_stock_qty(current_stock_qty),
            "previous_inbound_units": _fmt_stock_qty(current_inbound_units),
            "updated_utc": now_iso,
        }
        last_scan_utc[sku] = now_iso
        decision_rows.append(
            {
                "decision_ts_utc": now_iso,
                "run_id": run_id,
                "sku": sku,
                "repricing_enabled": _norm(row.get("repricing_enabled", "")),
                "observe_effective": "1",
                "write_effective": _norm(row.get("write_effective", "")),
                "market_data_present": _norm(row.get("market_data_present", "0")),
                "decision": _norm(row.get("decision", "")) or "execute",
                "reason_code": _norm(row.get("universe_reason_code", "")) or _norm(row.get("reason_codes_csv", "")),
            }
        )
        _progress("h110 run_once sku_done", sku=sku, idx=f"{idx+1}/{len(due_rows)}", write_status=_norm(row.get("write_status", "")))
        if idx < len(due_rows) - 1 and spacing_seconds > 0:
            time.sleep(spacing_seconds)
    _append_sku_decision_rows(decision_rows)

    latest_scan_state = _read_json(SKU_SCAN_STATE_PATH, default={"last_scan_utc": {}, "daily_boundary_lock": {}})
    latest_last_scan_utc = latest_scan_state.get("last_scan_utc", {})
    if not isinstance(latest_last_scan_utc, dict):
        latest_last_scan_utc = {}
    merged_last_scan_utc = dict(latest_last_scan_utc)
    for sku_key, ts_value in last_scan_utc.items():
        incoming_ts = _to_dt(ts_value)
        existing_ts = _to_dt(merged_last_scan_utc.get(sku_key, ""))
        if incoming_ts is None:
            continue
        if existing_ts is None or incoming_ts >= existing_ts:
            merged_last_scan_utc[sku_key] = ts_value

    scan_state["last_scan_utc"] = merged_last_scan_utc
    scan_state["daily_boundary_lock"] = {
        "date_utc": today_utc,
        "by_sku": boundary_lock_by_sku,
    }
    _write_json(SKU_SCAN_STATE_PATH, scan_state)
    _write_json(H_REENTRY_STATE_PATH, {"skus": reentry_state_by_sku})
    _write_json(H_INBOUND_ACTIVATION_STATE_PATH, {"skus": inbound_state_by_sku})

    next_due_sleep_seconds = 0
    next_due_sku = ""
    if cooldown_wait_candidates:
        next_due_sleep_seconds, next_due_sku = min(cooldown_wait_candidates, key=lambda pair: pair[0])

    if not run_rows:
        no_due_reason = "NO_SKU_DUE_COOLDOWN"
        if int(stock_summary["scope_total"]) > 0 and int(stock_summary["eligible"]) == 0:
            no_due_reason = "NO_SKU_DUE_STOCK_FILTER"
        _progress("h110 run_once done", processed_count=0, reason=no_due_reason)
        return {
            "phase1_pilot": "1",
            "phase1_sku": "",
            "phase1_skus_processed_csv": "",
            "phase1_skus_processed_count": "0",
            "phase1_skus_skipped_cooldown_count": str(len(skipped_cooldown)),
            "phase1_skus_skipped_parked_count": str(skipped_parked_count),
            "phase1_skus_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
            "phase1_scan_cooldown_minutes": str(cooldown_minutes),
            "phase1_next_due_sleep_seconds": str(next_due_sleep_seconds),
            "phase1_next_due_sku": next_due_sku,
            "phase1_target_universe_mode": "canonical_scope",
            "phase1_target_universe_source": str(CANONICAL_UNIVERSE_PATH),
            "phase1_target_universe_mode_source": "phase1_sku_scope",
            "phase1_target_universe_candidate_count": str(len(universe_rows)),
            "phase1_target_universe_resolved_count": str(len(observe_rows)),
            "phase1_target_universe_skipped_no_listing_count": str(sum(1 for r in observe_rows if r["sku"] not in listing_map)),
            "phase1_target_universe_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
            "phase1_target_universe_notes_csv": "canonical_universe",
            "phase1_scope_total": scope_summary["scope_total"],
            "phase1_scope_excluded_dropped_count": scope_summary["excluded_dropped"],
            "phase1_scope_excluded_parked_count": scope_summary["excluded_parked"],
            "phase1_scope_remaining_count": scope_summary["remaining"],
            "phase1_scope_excluded_path": scope_summary["excluded_path"],
            "phase1_scope_source_path": scope_summary["scope_source"],
            "phase1_exception_enabled": "1" if include_stocked_excluded else "0",
            "phase1_exception_count": str(exception_count),
            "phase1_exception_overlap_count": str(overlap_count),
            "phase1_exception_normal_count": str(normal_count),
            "phase1_exception_final_process_count": str(len(due_rows)),
            "phase1_exception_path": exception_path,
            "phase1_stock_scope_total": stock_summary["scope_total"],
            "phase1_stock_eligible_count": stock_summary["eligible"],
            "phase1_stock_excluded_oos_count": stock_summary["excluded_oos"],
            "phase1_stock_excluded_unknown_count": stock_summary["excluded_unknown"],
            "phase1_stock_source_path": stock_summary["stock_source"],
            "phase1_stock_sku_col": stock_summary["stock_sku_col"],
            "phase1_stock_qty_col": stock_summary["stock_qty_col"],
            "phase1_stock_snapshot_date": stock_summary["stock_snapshot_date"],
            "phase1_stock_snapshot_age_hours": stock_summary["stock_snapshot_age_hours"],
            "phase1_stock_snapshot_is_fallback": stock_summary["stock_snapshot_is_fallback"],
            "phase1_stock_snapshot_status": stock_summary["stock_snapshot_status"],
            "phase1_stock_snapshot_action": stock_summary["stock_snapshot_action"],
            "phase1_stock_snapshot_status_path": stock_summary["stock_snapshot_status_path"],
            "phase1_stock_excluded_path": stock_summary["excluded_path"],
            "phase1_boundary_lock_date": today_utc,
            "phase1_boundary_lock_sku_count": str(len(boundary_lock_by_sku)),
            "phase1_boundary_lock_mode": "",
            "phase1_boundary_lock_final_ceiling_gbp": "",
            "daily_intel_missing_for_today": "0",
            "daily_intel_normal_processed_count": "0",
            "daily_intel_normal_missing_count": "0",
            "daily_intel_exception_processed_count": "0",
            "daily_intel_exception_missing_count": "0",
            "daily_intel_gate_policy": "STRICT_ALL",
            "last_executioner_utc": now_iso,
            "executioner_ran_utc": "",
            "executioner_probe_type": "NO_SKU_DUE",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": no_due_reason,
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": no_due_reason,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
        }

    exception_only_skus = {
        _norm(r.get("sku", "")).upper() for r in exception_included_rows if _norm(r.get("sku", ""))
    }
    normal_processed_count = 0
    normal_missing_count = 0
    exception_processed_count = 0
    exception_missing_count = 0
    for row in run_rows:
        sku = _norm(row.get("phase1_sku", "")).upper()
        is_missing = row.get("daily_intel_missing_for_today", "0") == "1"
        if sku and sku in exception_only_skus:
            exception_processed_count += 1
            if is_missing:
                exception_missing_count += 1
        else:
            normal_processed_count += 1
            if is_missing:
                normal_missing_count += 1
    gate_policy = "EXEMPT_EXCEPTION" if include_stocked_excluded else "STRICT_ALL"
    gate_missing_count = normal_missing_count
    blocked_missing_count = sum(1 for row in run_rows if row.get("blocked_due_to_missing_intel", "0") == "1")
    blocked_stale_count = sum(1 for row in run_rows if row.get("blocked_due_to_stale_intel", "0") == "1")
    refresh_attempted_count = sum(int(_norm(row.get("refresh_attempted_count", "0")) or "0") for row in run_rows)
    refresh_throttled_count = sum(int(_norm(row.get("refresh_throttled_count", "0")) or "0") for row in run_rows)
    processed_skus = {_norm(row.get("phase1_sku", "")).upper() for row in run_rows if _norm(row.get("phase1_sku", ""))}
    intel_stats = _daily_intel_today_stats(today_utc_date=today_utc, skus=processed_skus)
    market_missing_count = sum(1 for row in run_rows if _norm(row.get("market_data_present", "0")) != "1")
    skip_no_market_count = sum(1 for row in run_rows if _norm(row.get("write_status", "")) == "SKIP_NO_MARKET_DATA")
    _progress(
        "h110 daily_intel_market_decision",
        today_utc=today_utc,
        daily_intel_path=str(intel_stats.get("path", "")),
        rows_today=str(intel_stats.get("rows_today", 0)),
        unique_skus_today=str(intel_stats.get("unique_skus_today", 0)),
        processed_skus=str(len(processed_skus)),
        processed_with_today_intel=str(intel_stats.get("matched_skus_today", 0)),
        processed_missing_today_intel=str(max(len(processed_skus) - int(intel_stats.get("matched_skus_today", 0)), 0)),
        market_data_missing_count=str(market_missing_count),
        skip_no_market_data_count=str(skip_no_market_count),
    )
    _progress(
        "h_daily_intel_gate_decision",
        today_utc=today_utc,
        normal_processed=normal_processed_count,
        normal_missing=normal_missing_count,
        exception_processed=exception_processed_count,
        exception_missing=exception_missing_count,
        policy=gate_policy,
    )
    last = run_rows[-1]
    _progress("h110 run_once done", processed_count=len(run_rows), last_sku=_norm(last.get("phase1_sku", "")))
    return {
        "phase1_pilot": "1",
        "phase1_sku": _norm(last.get("phase1_sku", "")),
        "phase1_skus_processed_csv": ",".join([_norm(r.get("phase1_sku", "")) for r in run_rows]),
        "phase1_skus_processed_count": str(len(run_rows)),
        "phase1_skus_skipped_cooldown_count": str(len(skipped_cooldown)),
        "phase1_skus_skipped_parked_count": str(skipped_parked_count),
        "phase1_skus_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
        "phase1_scan_cooldown_minutes": str(cooldown_minutes),
        "phase1_next_due_sleep_seconds": str(next_due_sleep_seconds),
        "phase1_next_due_sku": next_due_sku,
        "phase1_target_universe_mode": "canonical_scope",
        "phase1_target_universe_source": str(CANONICAL_UNIVERSE_PATH),
        "phase1_target_universe_mode_source": "phase1_sku_scope",
        "phase1_target_universe_candidate_count": str(len(universe_rows)),
        "phase1_target_universe_resolved_count": str(len(observe_rows)),
        "phase1_target_universe_skipped_no_listing_count": str(sum(1 for r in observe_rows if r["sku"] not in listing_map)),
        "phase1_target_universe_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
        "phase1_target_universe_notes_csv": "canonical_universe",
        "phase1_scope_total": scope_summary["scope_total"],
        "phase1_scope_excluded_dropped_count": scope_summary["excluded_dropped"],
        "phase1_scope_excluded_parked_count": scope_summary["excluded_parked"],
        "phase1_scope_remaining_count": scope_summary["remaining"],
        "phase1_scope_excluded_path": scope_summary["excluded_path"],
        "phase1_scope_source_path": scope_summary["scope_source"],
        "phase1_exception_enabled": "1" if include_stocked_excluded else "0",
        "phase1_exception_count": str(exception_count),
        "phase1_exception_overlap_count": str(overlap_count),
        "phase1_exception_normal_count": str(normal_count),
        "phase1_exception_final_process_count": str(len(due_rows)),
        "phase1_exception_path": exception_path,
        "phase1_stock_scope_total": stock_summary["scope_total"],
        "phase1_stock_eligible_count": stock_summary["eligible"],
        "phase1_stock_excluded_oos_count": stock_summary["excluded_oos"],
        "phase1_stock_excluded_unknown_count": stock_summary["excluded_unknown"],
        "phase1_stock_source_path": stock_summary["stock_source"],
        "phase1_stock_sku_col": stock_summary["stock_sku_col"],
        "phase1_stock_qty_col": stock_summary["stock_qty_col"],
        "phase1_stock_snapshot_date": stock_summary["stock_snapshot_date"],
        "phase1_stock_snapshot_age_hours": stock_summary["stock_snapshot_age_hours"],
        "phase1_stock_snapshot_is_fallback": stock_summary["stock_snapshot_is_fallback"],
        "phase1_stock_snapshot_status": stock_summary["stock_snapshot_status"],
        "phase1_stock_snapshot_action": stock_summary["stock_snapshot_action"],
        "phase1_stock_snapshot_status_path": stock_summary["stock_snapshot_status_path"],
        "phase1_stock_excluded_path": stock_summary["excluded_path"],
        "phase1_boundary_lock_date": today_utc,
        "phase1_boundary_lock_sku_count": str(len(boundary_lock_by_sku)),
        "phase1_boundary_lock_mode": _norm(last.get("phase1_boundary_lock_mode", "")),
        "phase1_boundary_lock_final_ceiling_gbp": _norm(last.get("phase1_boundary_lock_final_ceiling_gbp", "")),
        "daily_intel_missing_for_today": "1" if gate_missing_count > 0 else "0",
        "daily_intel_missing_count": str(gate_missing_count),
        "daily_intel_normal_processed_count": str(normal_processed_count),
        "daily_intel_normal_missing_count": str(normal_missing_count),
        "daily_intel_exception_processed_count": str(exception_processed_count),
        "daily_intel_exception_missing_count": str(exception_missing_count),
        "daily_intel_gate_policy": gate_policy,
        "last_executioner_utc": now_iso,
        "executioner_ran_utc": _norm(last.get("executioner_ran_utc", "")),
        "executioner_probe_type": _norm(last.get("executioner_probe_type", "")),
        "executioner_live_write_attempted": _norm(last.get("executioner_live_write_attempted", "0")),
        "executioner_live_write_success": _norm(last.get("executioner_live_write_success", "0")),
        "write_status": _norm(last.get("write_status", "")),
        "final_ceiling_landed_gbp": _norm(last.get("final_ceiling_landed_gbp", "")),
        "reason_codes_csv": _norm(last.get("reason_codes_csv", "")),
        "blocked_due_to_missing_intel": str(blocked_missing_count),
        "blocked_due_to_stale_intel": str(blocked_stale_count),
        "refresh_attempted_count": str(refresh_attempted_count),
        "refresh_throttled_count": str(refresh_throttled_count),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="H110 - Run one Phase 1 H pilot step")
    parser.add_argument("--phase1-config", required=True, help="Path to Phase 1 pilot YAML config")
    parser.add_argument("--read-only", action="store_true", help="Force read-only mode")
    parser.add_argument("--run-id", default="", help="Optional run id from orchestrator")
    parser.add_argument("--now-utc", default="", help="Optional fixed UTC timestamp, ISO")
    args = parser.parse_args()

    cfg_path = Path(args.phase1_config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        raise SystemExit(f"[H110] phase1 config not found: {cfg_path}")
    cfg = _simple_yaml_load(cfg_path)
    run_id = _norm(args.run_id)
    if not run_id:
        raise SystemExit("[H110] --run-id is required (provided by H cycle run context)")
    if PHASE1_RESULT_PATH is None:
        raise RuntimeError("h110 completion contract requires H_PHASE1_RESULT_PATH")
    if PHASE1_COMPLETION_MARKER_PATH is None:
        raise RuntimeError("h110 completion contract requires H_PHASE1_COMPLETION_MARKER_PATH")
    _install_completion_exit_guards(run_id)
    _write_completion_marker(
        status="started",
        run_id=run_id,
        reason="run_started",
        payload_result_ok=False,
    )

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    if _norm(args.now_utc):
        try:
            raw = _norm(args.now_utc).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(raw)
            now_utc = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    state = _run_once(cfg=cfg, read_only=bool(args.read_only), run_id=run_id, now_utc=now_utc)
    _progress("h110 finalization_enter", run_id=run_id)
    try:
        _emit_success_payload(state)
        result_ok = False
        try:
            result_ok = PHASE1_RESULT_PATH.exists() and PHASE1_RESULT_PATH.stat().st_size > 0
        except Exception:
            result_ok = False
        if not result_ok:
            _progress(
                "h110 finalization_abnormal_exit",
                run_id=run_id,
                stage="result_payload_contract",
                reason="result_payload_missing_after_emit",
                result_path=str(PHASE1_RESULT_PATH),
            )
            _write_completion_marker(
                status="failed",
                run_id=run_id,
                reason="result_payload_missing_after_emit",
                payload_result_ok=False,
                fail_closed=True,
            )
            raise RuntimeError(
                "h110 completion contract failed: result payload missing after emit "
                f"(result_path={PHASE1_RESULT_PATH})"
            )
        _write_completion_marker(
            status="success",
            run_id=run_id,
            reason="payload_emitted",
            payload_result_ok=result_ok,
            fail_closed=True,
        )
        _mark_completion_success_written()
        return 0
    except BaseException as exc:
        _progress(
            "h110 finalization_abnormal_exit",
            run_id=run_id,
            stage="finalization",
            error_type=type(exc).__name__,
            error=_norm(str(exc))[:240],
        )
        try:
            _write_completion_marker(
                status="failed",
                run_id=run_id,
                reason=_marker_reason("finalization_abnormal_exit", exc),
                payload_result_ok=False,
                fail_closed=True,
            )
        except Exception as marker_exc:
            _progress(
                "h110 completion_marker_failed_write",
                status="fail",
                run_id=run_id,
                marker_path=str(PHASE1_COMPLETION_MARKER_PATH) if PHASE1_COMPLETION_MARKER_PATH else "",
                error=f"{type(marker_exc).__name__}:{marker_exc}",
            )
        raise


if __name__ == "__main__":
    try:
        exit_code = int(main())
    except BaseException as exc:
        run_id = _norm(os.environ.get("H_RUN_ID", ""))
        if isinstance(exc, SystemExit):
            code_obj = exc.code
            try:
                code_int = int(code_obj) if code_obj is not None else 0
            except Exception:
                code_int = 1
            if code_int == 0:
                marker_ok, marker_reason = _completion_marker_success_for_run(run_id)
                if not marker_ok:
                    _write_completion_marker(
                        status="failed",
                        run_id=run_id,
                        reason=f"system_exit_0_without_success_marker:{marker_reason}",
                        payload_result_ok=False,
                    )
                    raise RuntimeError(
                        "h110 completion contract failed: system exit 0 without success marker "
                        f"(run_id={run_id} reason={marker_reason} marker_path={PHASE1_COMPLETION_MARKER_PATH})"
                    ) from exc
            raise
        reason = f"{type(exc).__name__}:{_norm(str(exc))[:240]}"
        _write_completion_marker(
            status="failed",
            run_id=run_id,
            reason=reason,
            payload_result_ok=False,
        )
        raise
    raise SystemExit(exit_code)


