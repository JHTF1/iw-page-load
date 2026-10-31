from __future__ import annotations

import csv
from pathlib import Path

from src.analysis.__main__ import main


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_demo_pipeline_outputs_tables_and_figures(tmp_path: Path):
    figures = tmp_path / "figures"
    tables = tmp_path / "tables"

    exit_code = main([
        "--demo",
        "--figures",
        str(figures),
        "--tables",
        str(tables),
    ])

    assert exit_code == 0

    figure_files = sorted(figures.iterdir())
    assert len(figure_files) == 8
    assert {suffix for suffix in (path.suffix for path in figure_files)} == {".png", ".svg"}
    assert all(path.stat().st_size > 0 for path in figure_files)

    merged_rows = read_rows(tables / "merged_by_site.csv")
    assert len(merged_rows) == 12
    assert {row["group"] for row in merged_rows} == {"real", "lab"}

    stats_rows = read_rows(tables / "stats_summary.csv")
    assert any(row["method"] == "spearman" for row in stats_rows)
    assert any(row["method"] == "partial_spearman" for row in stats_rows)
    assert any(row["method"] == "mann-whitney-u" for row in stats_rows)
    assert all(row["p_value"] != "" for row in stats_rows)
    assert all(row["effect_size"] != "" for row in stats_rows)

    lab_rows = read_rows(tables / "lab_group_summary.csv")
    assert len(lab_rows) == 4


def test_missing_csv_returns_error(tmp_path: Path):
    exit_code = main([
        "--initcwnd",
        str(tmp_path / "missing_initcwnd.csv"),
        "--pageload",
        str(tmp_path / "missing_pageload.csv"),
        "--figures",
        str(tmp_path / "figures"),
        "--tables",
        str(tmp_path / "tables"),
    ])

    assert exit_code == 1
