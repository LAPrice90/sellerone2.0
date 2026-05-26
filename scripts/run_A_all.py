from __future__ import annotations

import os
import sys

os.environ.setdefault("A_SKIP_LEGACY_SHEET_OUTPUT_STEPS", "1")
os.environ.setdefault("A_ENABLE_STOCK_RECEIPTS_SHEET", "1")
os.environ.setdefault("A_MAINT_POLL_S", "5")
os.environ.setdefault("A_MAINT_WAIT_READY_MAX_S", "300")
os.environ.setdefault("A_MAINT_WAIT_LOG_EVERY_S", "10")
os.environ.setdefault("A_MAINT_B_NOT_RUNNING_STABLE_S", "30")
os.environ.setdefault("A_ENSURE_B_AFTER_A", "0")
os.environ.setdefault("A_B_RECOVERY_WAIT_S", "60")
os.environ.setdefault("A_B_RECOVERY_POLL_S", "5")
os.environ.setdefault("A_B_RECOVERY_USE_SCHEDULER", "1")
os.environ.setdefault("A_B_SCHEDULER_TASK_NAME", "AMZ Orders")

try:
    from scripts.cycles import run_A_all as _impl
except ModuleNotFoundError:
    from cycles import run_A_all as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})

if __name__ != "__main__":
    sys.modules[__name__] = _impl


if __name__ == "__main__":
    raise SystemExit(main())
