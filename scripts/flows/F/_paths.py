from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FPathContract:
    root: Path
    system_root: Path
    live_dir: Path
    history_dir: Path
    inbox_dir: Path


def get_f_path_contract(root: Path | None = None) -> FPathContract:
    base_root = root or ROOT
    system_root = base_root / "out" / "systems" / "F"
    return FPathContract(
        root=base_root,
        system_root=system_root,
        live_dir=system_root / "live",
        history_dir=system_root / "history",
        inbox_dir=system_root / "inbox",
    )


def ensure_f_directories(root: Path | None = None) -> FPathContract:
    contract = get_f_path_contract(root=root)
    contract.live_dir.mkdir(parents=True, exist_ok=True)
    contract.history_dir.mkdir(parents=True, exist_ok=True)
    contract.inbox_dir.mkdir(parents=True, exist_ok=True)
    return contract
