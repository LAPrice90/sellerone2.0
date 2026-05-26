from __future__ import annotations

import csv
from pathlib import Path

from scripts.one_off import P006_build_csv_dependency_map as p006


def _write_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset_id",
                "dataset_name",
                "dataset_family",
                "owner_cycle",
                "canonical_path",
                "allowed_mirror_paths",
                "writer_scripts",
                "consumer_scripts",
                "dataset_type",
                "update_frequency",
                "decision_importance_0_10",
                "freshness_score_0_10",
                "reliability_score_0_10",
                "completeness_score_0_10",
                "overall_data_performance_score_0_10",
                "status",
                "schema_ref",
                "notes",
                "last_scored_utc",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "dataset_id": "B.TOKEN_COGS_LEDGER",
                "owner_cycle": "B",
                "canonical_path": "out/token_cogs_ledger.csv",
            }
        )


def test_p006_maps_registry_csv_read_and_write(tmp_path, monkeypatch):
    registry = tmp_path / "registry.csv"
    script_dir = tmp_path / "scripts"
    script = script_dir / "flow.py"
    _write_registry(registry)
    script_dir.mkdir()
    script.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import pandas as pd",
                "OUT = Path('out')",
                "TOKEN_COGS = OUT / 'token_cogs_ledger.csv'",
                "df = pd.read_csv(TOKEN_COGS)",
                "df.to_csv(TOKEN_COGS, index=False)",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(p006, "ROOT", tmp_path)

    rows = p006.build_rows([script_dir], registry_path=registry)

    assert len(rows) == 2
    assert {row["operation"] for row in rows} == {"read_csv", "to_csv"}
    assert {row["dataset_id"] for row in rows} == {"B.TOKEN_COGS_LEDGER"}
    assert {row["migration_status"] for row in rows} == {"sql_primary_pilot_proven"}


def test_p006_maps_allowed_mirror_wildcard_paths(tmp_path, monkeypatch):
    registry = tmp_path / "registry.csv"
    script_dir = tmp_path / "scripts"
    script = script_dir / "flow.py"
    _write_registry(registry)
    rows = list(csv.DictReader(registry.open("r", encoding="utf-8", newline="")))
    rows.append(
        {
            "dataset_id": "F.NEW_PRODUCT_REVIEW_PASS_PACK",
            "owner_cycle": "F",
            "canonical_path": "out/analysis_reports/f_live_price_file_pass_review_latest.csv",
            "allowed_mirror_paths": "out/analysis_reports/f_live_price_file_pass_review_*.csv",
        }
    )
    with registry.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "dataset_id",
            "dataset_name",
            "dataset_family",
            "owner_cycle",
            "canonical_path",
            "allowed_mirror_paths",
            "writer_scripts",
            "consumer_scripts",
            "dataset_type",
            "update_frequency",
            "decision_importance_0_10",
            "freshness_score_0_10",
            "reliability_score_0_10",
            "completeness_score_0_10",
            "overall_data_performance_score_0_10",
            "status",
            "schema_ref",
            "notes",
            "last_scored_utc",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    script_dir.mkdir()
    script.write_text(
        "import pandas as pd\npd.read_csv('out/analysis_reports/f_live_price_file_pass_review_20260429T150000Z.csv')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(p006, "ROOT", tmp_path)

    built_rows = p006.build_rows([script_dir], registry_path=registry)

    assert len(built_rows) == 1
    assert built_rows[0]["dataset_id"] == "F.NEW_PRODUCT_REVIEW_PASS_PACK"
    assert built_rows[0]["migration_status"] == "sql_primary_pilot_proven"


def test_p006_maps_declared_csv_path_inside_dict(tmp_path, monkeypatch):
    registry = tmp_path / "registry.csv"
    script_dir = tmp_path / "scripts"
    script = script_dir / "flow.py"
    _write_registry(registry)
    rows = list(csv.DictReader(registry.open("r", encoding="utf-8", newline="")))
    rows.append(
        {
            "dataset_id": "F.NEW_PRODUCT_REVIEW_PASS_PACK",
            "owner_cycle": "F",
            "canonical_path": "out/analysis_reports/f_live_price_file_pass_review_latest.csv",
        }
    )
    with registry.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "dataset_id",
            "dataset_name",
            "dataset_family",
            "owner_cycle",
            "canonical_path",
            "allowed_mirror_paths",
            "writer_scripts",
            "consumer_scripts",
            "dataset_type",
            "update_frequency",
            "decision_importance_0_10",
            "freshness_score_0_10",
            "reliability_score_0_10",
            "completeness_score_0_10",
            "overall_data_performance_score_0_10",
            "status",
            "schema_ref",
            "notes",
            "last_scored_utc",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    script_dir.mkdir()
    script.write_text(
        "PACKS = {'passes': 'out/analysis_reports/f_live_price_file_pass_review_latest.csv'}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(p006, "ROOT", tmp_path)

    built_rows = p006.build_rows([script_dir], registry_path=registry)

    assert len(built_rows) == 1
    assert built_rows[0]["operation"] == "declared_csv_path"
    assert built_rows[0]["dataset_id"] == "F.NEW_PRODUCT_REVIEW_PASS_PACK"


def test_p006_maps_o_f_schema_contract_paths_without_registry_rows(tmp_path, monkeypatch):
    registry = tmp_path / "registry.csv"
    script_dir = tmp_path / "scripts"
    script = script_dir / "flow.py"
    _write_registry(registry)
    script_dir.mkdir()
    script.write_text(
        "import pandas as pd\npd.read_csv('out/systems/O/live/product_db_operator_view.csv')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(p006, "ROOT", tmp_path)

    built_rows = p006.build_rows([script_dir], registry_path=registry)

    assert len(built_rows) == 1
    assert built_rows[0]["dataset_id"] == "O.PRODUCT_DB_OPERATOR_VIEW"
    assert built_rows[0]["migration_status"] == "sql_primary_pilot_proven"


def test_p006_writes_valid_report_and_summary(tmp_path, monkeypatch):
    registry = tmp_path / "registry.csv"
    script_dir = tmp_path / "scripts"
    script = script_dir / "flow.py"
    output_dir = tmp_path / "out"
    _write_registry(registry)
    script_dir.mkdir()
    script.write_text(
        "import pandas as pd\npd.read_csv('out/unknown.csv')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(p006, "ROOT", tmp_path)

    rows = p006.build_rows([script_dir], registry_path=registry)
    report_path, summary_path, summary = p006.write_outputs(rows, output_dir)

    assert report_path.exists()
    assert summary_path.exists()
    assert summary["row_count"] == 1
    assert summary["unregistered_csv_count"] == 1
    with report_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == p006.OUTPUT_COLUMNS
