from __future__ import annotations

import csv
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from scripts.core.out_paths import compat_map_rows, resolve_compat_path

OUT_REVIEWS = Path("out") / "reviews"
VERIFY_CSV = OUT_REVIEWS / "live_writer_verification.csv"
COMPAT_MANIFEST_CSV = OUT_REVIEWS / "live_writer_path_compat_manifest.csv"
ROLLBACK_MANIFEST_CSV = OUT_REVIEWS / "live_writer_rollback_manifest.csv"
ROLLBACK_PS1 = OUT_REVIEWS / "live_writer_rollback.ps1"
BOOTSTRAP_MANIFEST_CSV = OUT_REVIEWS / "live_writer_bootstrap_manifest.csv"


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _file_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except Exception:
        return 0


def build_verification_rows() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    checked_utc = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    for entry in compat_map_rows():
        legacy_rel = str(entry["legacy_rel"]).replace("\\", "/")
        rel = legacy_rel[4:] if legacy_rel.startswith("out/") else legacy_rel
        resolved = resolve_compat_path(rel)
        live_exists = resolved.live_path.exists()
        legacy_exists = resolved.legacy_path.exists()
        live_hash = _sha256(resolved.live_path) if live_exists else ""
        legacy_hash = _sha256(resolved.legacy_path) if legacy_exists else ""
        match = live_exists and legacy_exists and (live_hash == legacy_hash)
        status = "ok" if match else "warn"
        if not live_exists:
            status = "warn"
        rows.append(
            {
                "checked_utc": checked_utc,
                "legacy_rel": legacy_rel,
                "live_path": str(resolved.live_path).replace("\\", "/"),
                "legacy_path": str(resolved.legacy_path).replace("\\", "/"),
                "system": resolved.system,
                "live_exists": "1" if live_exists else "0",
                "legacy_exists": "1" if legacy_exists else "0",
                "live_bytes": str(_file_size(resolved.live_path)),
                "legacy_bytes": str(_file_size(resolved.legacy_path)),
                "live_sha256": live_hash,
                "legacy_sha256": legacy_hash,
                "status": status,
            }
        )
    return rows


def bootstrap_live_from_legacy() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    copied_utc = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    for entry in compat_map_rows():
        legacy_rel = str(entry["legacy_rel"]).replace("\\", "/")
        rel = legacy_rel[4:] if legacy_rel.startswith("out/") else legacy_rel
        resolved = resolve_compat_path(rel)
        did_copy = "0"
        reason = "noop"
        if not resolved.live_path.exists() and resolved.legacy_path.exists():
            resolved.live_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved.legacy_path, resolved.live_path)
            did_copy = "1"
            reason = "copied_legacy_to_live"
        elif resolved.live_path.exists():
            reason = "live_exists"
        elif not resolved.legacy_path.exists():
            reason = "missing_legacy"
        rows.append(
            {
                "copied_utc": copied_utc,
                "legacy_rel": legacy_rel,
                "live_path": str(resolved.live_path).replace("\\", "/"),
                "legacy_path": str(resolved.legacy_path).replace("\\", "/"),
                "copied": did_copy,
                "reason": reason,
            }
        )
    return rows


def _write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as fh:
        if not fieldnames:
            fh.write("")
            return
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_compat_manifest() -> None:
    rows = compat_map_rows()
    _write_csv(COMPAT_MANIFEST_CSV, rows)


def _write_rollback_manifest() -> None:
    rows: List[Dict[str, str]] = []
    for entry in compat_map_rows():
        legacy_rel = str(entry["legacy_rel"]).replace("\\", "/")
        rel = legacy_rel[4:] if legacy_rel.startswith("out/") else legacy_rel
        resolved = resolve_compat_path(rel)
        rows.append(
            {
                "source_live": str(resolved.live_path).replace("\\", "/"),
                "destination_legacy": str(resolved.legacy_path).replace("\\", "/"),
                "live_exists": "1" if resolved.live_path.exists() else "0",
                "legacy_exists": "1" if resolved.legacy_path.exists() else "0",
                "live_bytes": str(_file_size(resolved.live_path)),
            }
        )
    _write_csv(ROLLBACK_MANIFEST_CSV, rows)

    lines = [
        '$manifest = Import-Csv -Path "out\\reviews\\live_writer_rollback_manifest.csv"',
        "foreach($row in $manifest){",
        '  if(Test-Path $row.source_live){',
        "    $destDir = Split-Path -Parent $row.destination_legacy",
        "    if(-not (Test-Path $destDir)){ New-Item -ItemType Directory -Path $destDir -Force | Out-Null }",
        "    Copy-Item -Path $row.source_live -Destination $row.destination_legacy -Force",
        "  }",
        "}",
        "",
    ]
    ROLLBACK_PS1.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    should_bootstrap = os.environ.get("LIVE_WRITER_BOOTSTRAP", "1").strip() == "1"
    if should_bootstrap:
        bootstrap_rows = bootstrap_live_from_legacy()
        _write_csv(BOOTSTRAP_MANIFEST_CSV, bootstrap_rows)
        copied = sum(1 for r in bootstrap_rows if r.get("copied") == "1")
        print(f"[verify_live_writer_paths] wrote {BOOTSTRAP_MANIFEST_CSV} copied={copied}")
    _write_compat_manifest()
    _write_rollback_manifest()
    rows = build_verification_rows()
    _write_csv(VERIFY_CSV, rows)
    ok_count = sum(1 for r in rows if r.get("status") == "ok")
    warn_count = sum(1 for r in rows if r.get("status") == "warn")
    print(f"[verify_live_writer_paths] wrote {VERIFY_CSV} rows={len(rows)} ok={ok_count} warn={warn_count}")
    print(f"[verify_live_writer_paths] wrote {COMPAT_MANIFEST_CSV}")
    print(f"[verify_live_writer_paths] wrote {ROLLBACK_MANIFEST_CSV}")
    print(f"[verify_live_writer_paths] wrote {ROLLBACK_PS1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

