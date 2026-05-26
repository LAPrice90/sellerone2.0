from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class PriceListManagerPaths:
    root: Path
    config_dir: Path
    system_dir: Path
    test_mode_dir: Path


def get_manager_paths(root: Path | None = None) -> PriceListManagerPaths:
    base_root = Path(root) if root is not None else ROOT
    system_dir = base_root / "out" / "systems" / "F" / "price_list_manager"
    return PriceListManagerPaths(
        root=base_root,
        config_dir=base_root / "config" / "feeder" / "price_list_manager",
        system_dir=system_dir,
        test_mode_dir=system_dir / "test_mode",
    )


def ensure_manager_test_mode_dir(root: Path | None = None) -> PriceListManagerPaths:
    paths = get_manager_paths(root=root)
    paths.test_mode_dir.mkdir(parents=True, exist_ok=True)
    return paths

