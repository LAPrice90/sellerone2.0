from __future__ import annotations

import contextlib
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd


def safe_to_csv(df: pd.DataFrame, path: Path | str, **to_csv_kwargs: Any) -> None:
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if to_csv_kwargs.get("mode") not in (None, "w"):
        df.to_csv(csv_path, **to_csv_kwargs)
        return

    to_csv_kwargs.pop("mode", None)
    last_error: OSError | None = None
    for attempt in range(1, 4):
        tmp_name = ""
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{csv_path.name}.",
                suffix=f".{os.getpid()}.tmp",
                dir=str(csv_path.parent),
            )
            os.close(fd)
            df.to_csv(tmp_name, **to_csv_kwargs)
            os.replace(tmp_name, csv_path)
            return
        except OSError as exc:
            last_error = exc
            with contextlib.suppress(Exception):
                if tmp_name:
                    Path(tmp_name).unlink()
            if attempt == 3:
                raise
            time.sleep(0.25 * attempt)
    if last_error is not None:
        raise last_error
