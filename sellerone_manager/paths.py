from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ManagerPaths:
    root: Path
    manifest_dir: Path
    output_dir: Path
    f_live_dir: Path
    f_test_mode_dir: Path


def get_manager_paths(root: Path | str | None = None) -> ManagerPaths:
    base = Path(root).resolve() if root is not None else ROOT
    return ManagerPaths(
        root=base,
        manifest_dir=base / "config" / "manager" / "modules",
        output_dir=base / "out" / "systems" / "M",
        f_live_dir=base / "out" / "systems" / "F" / "price_list_manager" / "live",
        f_test_mode_dir=base / "out" / "systems" / "F" / "price_list_manager" / "test_mode",
    )


def resolve_repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path
