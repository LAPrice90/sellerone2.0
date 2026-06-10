from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from scripts.core.safe_file_writes import safe_to_csv

OUT_ROOT = Path("out")
SYSTEMS_ROOT = OUT_ROOT / "systems"

# Legacy out/<file> -> system owner for Phase 2 live-writer migration.
LIVE_WRITER_COMPAT_MAP: Dict[str, str] = {
    "api_run_log.csv": "shared",
    "inventory_history.csv": "shared",
    "inbound_history.csv": "shared",
    "refund_adjustment_history.csv": "shared",
    "listing_offer_history.csv": "H",
    "listing_offer_seller_observation_history.csv": "H",
    "h_worker_probe_event_log.csv": "H",
    "h_worker_probe_response_log.csv": "H",
    "token_ledger_live.csv": "B",
    "token_allocations_live.csv": "B",
    "token_shortages_by_sku.csv": "B",
}


def _normalize_legacy_rel(path_or_rel: str | Path) -> str:
    rel = str(path_or_rel).replace("\\", "/").strip()
    if rel.startswith("./"):
        rel = rel[2:]
    if rel.startswith("out/"):
        rel = rel[4:]
    return rel


@dataclass(frozen=True)
class CompatPath:
    legacy_rel: str
    system: str
    live_path: Path
    legacy_path: Path


def resolve_compat_path(path_or_rel: str | Path, default_system: str = "shared") -> CompatPath:
    rel = _normalize_legacy_rel(path_or_rel)
    system = LIVE_WRITER_COMPAT_MAP.get(rel, default_system)
    rel_path = Path(rel)
    return CompatPath(
        legacy_rel=rel,
        system=system,
        live_path=SYSTEMS_ROOT / system / "live" / rel_path,
        legacy_path=OUT_ROOT / rel_path,
    )


def write_csv_with_compat(
    df: pd.DataFrame,
    *,
    path_or_rel: str | Path,
    default_system: str = "shared",
    index: bool = False,
    mirror_legacy: bool = True,
) -> CompatPath:
    resolved = resolve_compat_path(path_or_rel, default_system=default_system)
    resolved.live_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(df, resolved.live_path, index=index)
    if mirror_legacy:
        resolved.legacy_path.parent.mkdir(parents=True, exist_ok=True)
        safe_to_csv(df, resolved.legacy_path, index=index)
    return resolved


def compat_map_rows() -> List[dict]:
    rows: List[dict] = []
    for legacy_rel in sorted(LIVE_WRITER_COMPAT_MAP):
        resolved = resolve_compat_path(legacy_rel)
        rows.append(
            {
                "legacy_rel": f"out/{legacy_rel}",
                "system": resolved.system,
                "live_rel": str(resolved.live_path).replace("\\", "/"),
                "legacy_rel_resolved": str(resolved.legacy_path).replace("\\", "/"),
            }
        )
    return rows


def compatibility_targets(path_or_rel: str | Path, default_system: str = "shared") -> Iterable[Path]:
    resolved = resolve_compat_path(path_or_rel, default_system=default_system)
    yield resolved.live_path
    yield resolved.legacy_path

