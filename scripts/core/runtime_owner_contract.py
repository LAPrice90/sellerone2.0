from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = ROOT / "config" / "runtime_owner_contract.json"
REQUIRED_FLOWS = ("A", "B", "E", "H")


class RuntimeOwnerContractError(RuntimeError):
    pass


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_rel(value: Any) -> str:
    text = _norm_text(value).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _to_repo_rel(path_or_text: Any) -> str:
    if isinstance(path_or_text, Path):
        candidate = path_or_text
    else:
        candidate = Path(_norm_text(path_or_text))
    try:
        if candidate.is_absolute():
            rel = candidate.resolve().relative_to(ROOT.resolve())
            return _norm_rel(rel.as_posix())
    except Exception:
        pass
    return _norm_rel(candidate.as_posix())


def is_truthy(value: Any) -> bool:
    return _norm_text(value).lower() in {"1", "true", "yes", "on"}


def load_runtime_owner_contract(contract_path: Path | None = None) -> dict[str, Any]:
    path = Path(contract_path or DEFAULT_CONTRACT_PATH)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except FileNotFoundError as exc:
        raise RuntimeOwnerContractError(f"runtime owner contract missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeOwnerContractError(f"runtime owner contract invalid json: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeOwnerContractError(f"runtime owner contract root must be object: {path}")
    return raw


def validate_runtime_owner_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    flows = contract.get("flows", {})
    if not isinstance(flows, dict):
        return ["flows must be an object"]

    owners_seen: dict[str, str] = {}
    for flow in REQUIRED_FLOWS:
        payload = flows.get(flow)
        if not isinstance(payload, dict):
            errors.append(f"missing flow entry: {flow}")
            continue
        launcher = _norm_rel(payload.get("launcher_entrypoint"))
        runtime_owner = _norm_rel(payload.get("runtime_owner"))
        worker = _norm_rel(payload.get("worker_entrypoint"))
        owner_chain = payload.get("owner_chain", [])
        if not launcher:
            errors.append(f"{flow}: launcher_entrypoint missing")
        if not runtime_owner:
            errors.append(f"{flow}: runtime_owner missing")
        if not worker:
            errors.append(f"{flow}: worker_entrypoint missing")
        if not isinstance(owner_chain, list) or not owner_chain:
            errors.append(f"{flow}: owner_chain missing")
        else:
            chain = [_norm_rel(item) for item in owner_chain if _norm_rel(item)]
            if not chain:
                errors.append(f"{flow}: owner_chain empty")
            else:
                if launcher and chain[0] != launcher:
                    errors.append(f"{flow}: owner_chain first must match launcher_entrypoint")
                if worker and chain[-1] != worker:
                    errors.append(f"{flow}: owner_chain last must match worker_entrypoint")
        if runtime_owner:
            if flow in owners_seen:
                errors.append(f"{flow}: duplicate owner mapping")
            owners_seen[flow] = runtime_owner
    return errors


def load_and_validate_runtime_owner_contract(contract_path: Path | None = None) -> dict[str, Any]:
    contract = load_runtime_owner_contract(contract_path=contract_path)
    errors = validate_runtime_owner_contract(contract)
    if errors:
        raise RuntimeOwnerContractError("runtime owner contract invalid: " + "; ".join(errors))
    return contract


def get_flow_contract(flow: str, contract_path: Path | None = None) -> dict[str, Any]:
    flow_key = _norm_text(flow).upper()
    contract = load_and_validate_runtime_owner_contract(contract_path=contract_path)
    flows = contract.get("flows", {})
    payload = flows.get(flow_key)
    if not isinstance(payload, dict):
        raise RuntimeOwnerContractError(f"flow {flow_key} missing from runtime owner contract")
    return payload


def assert_flow_owner_mapping(
    flow: str,
    *,
    runtime_owner: Path | str | None = None,
    worker_entry: Path | str | None = None,
    launcher_entrypoint: Path | str | None = None,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    payload = get_flow_contract(flow, contract_path=contract_path)
    flow_key = _norm_text(flow).upper()
    if runtime_owner is not None:
        expected = _norm_rel(payload.get("runtime_owner"))
        actual = _to_repo_rel(runtime_owner)
        if expected != actual:
            raise RuntimeOwnerContractError(
                f"{flow_key} runtime_owner mismatch expected={expected} actual={actual}"
            )
    if worker_entry is not None:
        expected = _norm_rel(payload.get("worker_entrypoint"))
        actual = _to_repo_rel(worker_entry)
        if expected != actual:
            raise RuntimeOwnerContractError(
                f"{flow_key} worker_entrypoint mismatch expected={expected} actual={actual}"
            )
    if launcher_entrypoint is not None:
        expected = _norm_rel(payload.get("launcher_entrypoint"))
        actual = _to_repo_rel(launcher_entrypoint)
        if expected != actual:
            raise RuntimeOwnerContractError(
                f"{flow_key} launcher_entrypoint mismatch expected={expected} actual={actual}"
            )
    return payload
