from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off.HF000_prep_freeze_learning_inputs import freeze_manifest


def _write_csv(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_freeze_manifest_updates_status_and_table(tmp_path: Path) -> None:
    repo_root = tmp_path
    source_rel = "out/sample.csv"
    source_path = repo_root / source_rel
    _write_csv(
        source_path,
        [
            "c1,c2",
            "a,1",
            "b,2",
        ],
    )

    manifest_path = repo_root / "FROZEN_INPUT_MANIFEST.md"
    manifest_path.write_text(
        "\n".join(
            [
                "# Frozen Input Manifest",
                "",
                "## Status",
                "- Freeze state:",
                "  - pending prep gate",
                "- Freeze owner:",
                "  - pending",
                "- Freeze timestamp UTC:",
                "  - pending",
                "",
                "## Planned source list",
                "",
                "| Path | Role | Freeze row count | Freeze last write UTC | Freeze hash | Notes |",
                "|---|---|---:|---|---|---|",
                f"| `{source_rel}` | sample role | pending | pending | pending | sample note |",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    fixed_ts = "2026-04-17T18:00:00Z"
    records = freeze_manifest(
        manifest_path=manifest_path,
        repo_root=repo_root,
        rel_paths=[source_rel],
        owner="codex",
        timestamp_utc=fixed_ts,
    )

    manifest_text = manifest_path.read_text(encoding="utf-8")
    expected_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert records[source_rel].row_count == 2
    assert "  - locked" in manifest_text
    assert "  - codex" in manifest_text
    assert f"  - {fixed_ts}" in manifest_text
    assert f"| `{source_rel}` | sample role | 2 | " in manifest_text
    assert f"`{expected_hash}`" in manifest_text


def test_freeze_manifest_fails_for_missing_source(tmp_path: Path) -> None:
    repo_root = tmp_path
    manifest_path = repo_root / "FROZEN_INPUT_MANIFEST.md"
    manifest_path.write_text(
        "\n".join(
            [
                "# Frozen Input Manifest",
                "",
                "## Status",
                "- Freeze state:",
                "  - pending prep gate",
                "- Freeze owner:",
                "  - pending",
                "- Freeze timestamp UTC:",
                "  - pending",
                "",
                "## Planned source list",
                "",
                "| Path | Role | Freeze row count | Freeze last write UTC | Freeze hash | Notes |",
                "|---|---|---:|---|---|---|",
                "| `out/missing.csv` | sample role | pending | pending | pending | sample note |",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        freeze_manifest(
            manifest_path=manifest_path,
            repo_root=repo_root,
            rel_paths=["out/missing.csv"],
            owner="codex",
            timestamp_utc="2026-04-17T18:00:00Z",
        )
    except FileNotFoundError as exc:
        assert "required freeze source missing" in str(exc)
        return
    raise AssertionError("expected FileNotFoundError for missing source path")
