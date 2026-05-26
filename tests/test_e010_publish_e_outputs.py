from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.E import E010_publish_e_outputs as e010


def test_e010_tab_specs_include_truth_outputs() -> None:
    tab_titles = [title for title, _ in e010.TAB_SPECS]
    assert "E_Study_Report" in tab_titles
    assert "E_Sales_Truth_Reconciliation" in tab_titles
    assert "E_Daily_Sales_Truth" in tab_titles


def test_e010_read_csv_returns_empty_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    df = e010._read_csv(missing)
    assert isinstance(df, pd.DataFrame)
    assert df.empty
