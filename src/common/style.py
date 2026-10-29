"""图表统一风格：中文字体、字号、配色、导出格式按报告规范统一。

图题在图下方（GB/T 7713.1），由 save_figure 的 caption 参数自动放置；
导出固定为 300 dpi PNG 加矢量 SVG 双份。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.figure import Figure

from .paths import RESULTS_FIGURES

PREFERRED_CJK_FONTS = (
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
)

# Okabe-Ito 色盲友好配色
PALETTE = (
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#D55E00",
    "#F0E442",
    "#000000",
)

_APPLIED = False


def pick_cjk_font() -> str:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in PREFERRED_CJK_FONTS:
        if name in available:
            return name
    return "DejaVu Sans"


def apply_style() -> None:
    global _APPLIED
    font = pick_cjk_font()
    plt.rcParams.update(
        {
            "font.sans-serif": [font, "DejaVu Sans"],
            "font.family": "sans-serif",
            "axes.unicode_minus": False,
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "font.size": 10.5,
            "axes.titlesize": 12,
            "axes.labelsize": 10.5,
            "axes.prop_cycle": plt.cycler(color=list(PALETTE)),
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linestyle": "--",
            "legend.frameon": False,
        }
    )
    _APPLIED = True


def new_figure(width_in: float = 6.4, height_in: float = 4.8) -> Figure:
    if not _APPLIED:
        apply_style()
    return plt.figure(figsize=(width_in, height_in))


def save_figure(
    fig: Figure,
    name: str,
    caption: str | None = None,
    out_dir: Path | None = None,
) -> list[Path]:
    if not _APPLIED:
        apply_style()
    target_dir = Path(out_dir) if out_dir else RESULTS_FIGURES
    target_dir.mkdir(parents=True, exist_ok=True)

    if caption:
        fig.text(0.5, 0.01, caption, ha="center", va="bottom", fontsize=10.5)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
    else:
        fig.tight_layout()

    png_path = target_dir / f"{name}.png"
    svg_path = target_dir / f"{name}.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    return [png_path, svg_path]
