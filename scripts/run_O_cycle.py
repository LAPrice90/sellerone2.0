from __future__ import annotations

import sys

from cycles import run_O_cycle as _impl


if __name__ != "__main__":
    sys.modules[__name__] = _impl
else:
    raise SystemExit(_impl.main())
