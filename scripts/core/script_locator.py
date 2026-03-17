from __future__ import annotations

import re
from pathlib import Path

_FLOW_RE = re.compile(r"^([A-H])[0-9]{3}_.+\.py$", re.IGNORECASE)


def resolve_script_path(scripts_root: Path, script_name: str) -> Path:
    name = str(script_name).replace('/', '\\').strip()
    rel = Path(name)
    if rel.is_absolute():
        return rel

    direct = scripts_root / rel
    if direct.exists():
        return direct

    if len(rel.parts) == 1:
        m = _FLOW_RE.match(rel.name)
        if m:
            flow = m.group(1).upper()
            candidate = scripts_root / 'flows' / flow / rel.name
            if candidate.exists():
                return candidate
        for folder in ('tools', 'cycles', 'one_off'):
            candidate = scripts_root / folder / rel.name
            if candidate.exists():
                return candidate

    return direct

