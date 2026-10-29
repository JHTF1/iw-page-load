from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from src.common.style import PALETTE, apply_style, new_figure, pick_cjk_font, save_figure


def test_pick_cjk_font_returns_name():
    assert isinstance(pick_cjk_font(), str)
    assert pick_cjk_font()


def test_apply_style_sets_font_family():
    apply_style()
    assert plt.rcParams["font.family"] == ["sans-serif"]
    assert plt.rcParams["savefig.dpi"] == 300
    assert len(PALETTE) >= 4


def test_save_figure_exports_png_and_svg(tmp_path: Path):
    fig = new_figure()
    ax = fig.add_subplot(111)
    ax.plot([1, 2, 3], [1, 4, 9], label="示例")
    ax.set_xlabel("initcwnd / MSS")
    ax.set_ylabel("TTFB / ms")
    ax.legend()

    paths = save_figure(fig, "demo", caption="图 0 测试用图", out_dir=tmp_path)

    assert [path.suffix for path in paths] == [".png", ".svg"]
    assert all(path.exists() and path.stat().st_size > 0 for path in paths)
