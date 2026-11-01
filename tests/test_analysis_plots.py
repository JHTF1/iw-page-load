from __future__ import annotations

from pathlib import Path

import pytest

from src.analysis.plots import (
    plot_initcwnd_distribution,
    plot_lab_groups,
    plot_load_vs_bytes,
    plot_ttfb_vs_initcwnd,
)


def merged_row(
    site: str,
    group: str,
    initcwnd_mss: float,
    ttfb_ms: float,
    load_ms: float,
    transfer_bytes: int,
    load_samples: list[float] | None = None,
) -> dict:
    return {
        "site": site,
        "group": group,
        "initcwnd_mss": initcwnd_mss,
        "initcwnd_bytes": initcwnd_mss * 1460,
        "mss_bytes": 1460,
        "ttfb_ms": ttfb_ms,
        "load_ms": load_ms,
        "transfer_bytes": transfer_bytes,
        "dns_ms": 10.0,
        "tcp_ms": 20.0,
        "tls_ms": 30.0,
        "dom_content_loaded_ms": load_ms * 0.7,
        "request_count": 40,
        "runs_total": 5,
        "runs_used": 5,
        "load_samples": load_samples or [load_ms],
        "ttfb_samples": [ttfb_ms],
        "confidence": "high",
    }


@pytest.fixture
def merged_rows() -> list[dict]:
    real = [
        merged_row("baidu", "real", 10.0, 100.0, 1500.0, 1_200_000),
        merged_row("taobao", "real", 8.0, 110.0, 1600.0, 1_300_000),
        merged_row("bilibili", "real", 12.0, 90.0, 1450.0, 1_500_000),
        merged_row("zhihu", "real", 4.0, 180.0, 1900.0, 1_000_000),
        merged_row("github", "real", 16.0, 80.0, 1400.0, 1_600_000),
        merged_row("wikipedia", "real", 20.0, 70.0, 1350.0, 1_700_000),
    ]
    lab = [
        merged_row("lab-2", "lab", 2.0, 180.0, 1500.0, 1_200_000, [1480.0, 1490.0, 1500.0, 1510.0, 1520.0]),
        merged_row("lab-4", "lab", 4.0, 95.0, 900.0, 1_200_000, [880.0, 890.0, 900.0, 910.0, 920.0]),
        merged_row("lab-10", "lab", 10.0, 50.0, 600.0, 1_200_000, [580.0, 590.0, 600.0, 610.0, 620.0]),
        merged_row("lab-20", "lab", 20.0, 38.0, 450.0, 1_200_000, [430.0, 440.0, 450.0, 460.0, 470.0]),
    ]
    return real + lab


def test_four_figures_export_png_and_svg(tmp_path: Path, merged_rows: list[dict]):
    outputs = [
        *plot_initcwnd_distribution(merged_rows, tmp_path),
        *plot_ttfb_vs_initcwnd(merged_rows, tmp_path),
        *plot_load_vs_bytes(merged_rows, tmp_path),
        *plot_lab_groups(merged_rows, tmp_path),
    ]

    assert len(outputs) == 8
    assert [path.suffix for path in outputs] == [".png", ".svg"] * 4
    assert all(path.exists() and path.stat().st_size > 0 for path in outputs)
    names = {path.name for path in outputs}
    assert {
        "fig3_initcwnd_distribution.png",
        "fig4_ttfb_vs_initcwnd.svg",
        "fig5_load_vs_bytes.png",
        "fig6_lab_groups.svg",
    } <= names


def test_plot_initcwnd_distribution_without_real_rows(tmp_path: Path):
    lab_only = [merged_row("lab-2", "lab", 2.0, 180.0, 1500.0, 1_200_000)]

    assert plot_initcwnd_distribution(lab_only, tmp_path) == []


def test_plot_lab_groups_uses_all_runs(tmp_path: Path, merged_rows: list[dict]):
    paths = plot_lab_groups(merged_rows, tmp_path)

    assert paths
    assert paths[0].exists()
