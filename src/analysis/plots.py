"""四张结果图，统一走 src.common.style。

PNG 与 SVG 双份，编号与 docs/报告框架.md 第 5 章一致（图 3~图 6）。
``bake_caption=False`` 时不在图片内嵌图题，供报告正文另排标准图题。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.ticker import FixedLocator, FuncFormatter

from ..common.style import PALETTE, new_figure, save_figure
from .stats import partial_spearman, spearman

FIGURE_NAMES = {
    3: "fig3_initcwnd_distribution",
    4: "fig4_ttfb_vs_initcwnd",
    5: "fig5_load_vs_bytes",
    6: "fig6_lab_groups",
}


def _number(record: dict[str, Any], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _p_text(p_value: float | None) -> str:
    if p_value is None:
        return "p 无法计算"
    if p_value < 0.001:
        return "p < 0.001"
    return f"p = {p_value:.3f}"


def _real_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("group") == "real"]


def _lab_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("group") == "lab"]


def _smart_annotate(ax, fig, points: list[tuple[str, float, float]], fontsize: float = 7.8) -> None:
    """在散点旁放置站点名，按候选偏移做简单避让，减少标签互相遮挡。"""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer=renderer)
    placed: list[Any] = []
    offsets = (
        (5, 4),
        (5, -11),
        (-5, 4),
        (-5, -11),
        (8, 13),
        (8, -18),
        (-8, 13),
        (-8, -18),
        (14, 5),
        (14, -12),
        (-14, 5),
        (-14, -12),
        (5, 21),
        (-5, 21),
        (5, -25),
        (-5, -25),
    )
    for site, x_value, y_value in points:
        chosen = None
        for dx, dy in offsets:
            annotation = ax.annotate(
                site,
                (x_value, y_value),
                xytext=(dx, dy),
                textcoords="offset points",
                fontsize=fontsize,
                color=PALETTE[7],
                zorder=4,
            )
            bbox = annotation.get_window_extent(renderer=renderer)
            inside = (
                bbox.x0 >= axes_bbox.x0
                and bbox.x1 <= axes_bbox.x1
                and bbox.y0 >= axes_bbox.y0
                and bbox.y1 <= axes_bbox.y1
            )
            if inside and all(not bbox.overlaps(other) for other in placed):
                chosen = (annotation, bbox)
                break
            annotation.remove()
        if chosen is None:
            annotation = ax.annotate(
                site,
                (x_value, y_value),
                xytext=(5, 4),
                textcoords="offset points",
                fontsize=fontsize,
                color=PALETTE[7],
                zorder=4,
            )
            chosen = (annotation, annotation.get_window_extent(renderer=renderer))
        placed.append(chosen[1])


def _log_ticks(axis, positions: list[float]) -> None:
    axis.set_major_locator(FixedLocator(positions))
    axis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    axis.set_minor_locator(FixedLocator([]))


def plot_initcwnd_distribution(
    rows: list[dict[str, Any]],
    out_dir: Path | None = None,
    *,
    bake_caption: bool = True,
) -> list[Path]:
    """图 3：真实站点 initcwnd 分布（横向条形图，按 initcwnd 降序）。"""
    points = [
        (row["site"], _number(row, "initcwnd_mss"))
        for row in _real_rows(rows)
    ]
    points = [(site, value) for site, value in points if value is not None]
    if not points:
        return []
    points.sort(key=lambda item: item[1])

    height = max(4.8, 0.32 * len(points) + 1.8)
    fig = new_figure(6.4, height)
    ax = fig.add_subplot(111)
    sites = [site for site, _ in points]
    values = [value for _, value in points]
    ax.barh(sites, values, color=PALETTE[0], height=0.6)
    ax.axvline(10.0, color=PALETTE[5], linestyle="--", linewidth=1.2, label="RFC 6928 建议值 10 MSS")
    ax.set_xlim(0, 11.5)
    ax.set_xlabel("初始拥塞窗口 initcwnd / MSS")
    ax.set_ylabel("站点")
    ax.set_title(f"真实站点初始拥塞窗口分布（n = {len(points)}）")
    for index, value in enumerate(values):
        ax.text(value + 0.18, index, f"{value:.2f}", va="center", fontsize=8.5, color=PALETTE[7])
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="none")
    ax.grid(axis="y", visible=False)
    return save_figure(
        fig,
        FIGURE_NAMES[3],
        caption=(
            "图 3 真实站点 initcwnd 分布（数据来源：data/processed/initcwnd.csv）"
            if bake_caption
            else None
        ),
        out_dir=out_dir,
    )


def plot_ttfb_vs_initcwnd(
    rows: list[dict[str, Any]],
    out_dir: Path | None = None,
    *,
    bake_caption: bool = True,
) -> list[Path]:
    """图 4：TTFB 与 initcwnd 散点图（纵轴对数刻度），标注 Spearman 秩相关。"""
    pairs = [
        (row["site"], _number(row, "initcwnd_mss"), _number(row, "ttfb_ms"))
        for row in _real_rows(rows)
    ]
    pairs = [(site, x, y) for site, x, y in pairs if x is not None and y is not None]
    if len(pairs) < 2:
        return []

    x_values = [x for _, x, _ in pairs]
    y_values = [y for _, _, y in pairs]
    result = spearman(x_values, y_values)

    fig = new_figure(6.6, 4.9)
    ax = fig.add_subplot(111)
    ax.scatter(x_values, y_values, s=46, color=PALETTE[0], edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(8, 30_000)
    ax.set_xlim(2.0, 5.5)
    _log_ticks(ax.yaxis, [10, 30, 100, 300, 1000, 3000, 10000])

    rho = result["rho"]
    annotation = "Spearman ρ 无法计算" if rho is None else (
        f"Spearman ρ = {rho:.3f}，{_p_text(result['p_value'])}，n = {result['n']}"
    )
    ax.text(
        0.98,
        0.03,
        annotation,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9.2,
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": PALETTE[4]},
    )
    ax.set_xlabel("初始拥塞窗口 initcwnd / MSS")
    ax.set_ylabel("首字节时间 TTFB / ms（对数刻度）")
    ax.set_title("真实站点 TTFB 与 initcwnd")
    _smart_annotate(ax, fig, pairs)
    return save_figure(
        fig,
        FIGURE_NAMES[4],
        caption=(
            "图 4 真实站点 TTFB 与 initcwnd 散点图（结论仅为相关）"
            if bake_caption
            else None
        ),
        out_dir=out_dir,
    )


def plot_load_vs_bytes(
    rows: list[dict[str, Any]],
    out_dir: Path | None = None,
    *,
    bake_caption: bool = True,
) -> list[Path]:
    """图 5：加载时间与页面总字节散点图（双对数刻度），展示需要控制的混杂变量。"""
    triples = [
        (
            row["site"],
            _number(row, "transfer_bytes"),
            _number(row, "load_ms"),
            _number(row, "initcwnd_mss"),
        )
        for row in _real_rows(rows)
    ]
    triples = [
        (site, size, load, initcwnd)
        for site, size, load, initcwnd in triples
        if size is not None and load is not None and initcwnd is not None
    ]
    if len(triples) < 2:
        return []

    sizes_mb = [size / 1_000_000.0 for _, size, _, _ in triples]
    loads = [load for _, _, load, _ in triples]
    partial = partial_spearman(
        [initcwnd for _, _, _, initcwnd in triples],
        loads,
        [size for _, size, _, _ in triples],
    )

    fig = new_figure(6.6, 4.9)
    ax = fig.add_subplot(111)
    ax.scatter(sizes_mb, loads, s=46, color=PALETTE[2], edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.0012, 10.0)
    ax.set_ylim(200, 50_000)
    _log_ticks(ax.xaxis, [0.001, 0.01, 0.1, 1, 10])
    _log_ticks(ax.yaxis, [300, 1000, 3000, 10000, 30000])

    rho = partial["rho"]
    annotation = "偏相关无法计算" if rho is None else (
        f"控制页面总字节后偏 Spearman ρ = {rho:.3f}，{_p_text(partial['p_value'])}"
    )
    ax.text(
        0.98,
        0.03,
        annotation,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9.0,
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": PALETTE[4]},
    )
    ax.set_xlabel("页面总传输字节 / MB（对数刻度）")
    ax.set_ylabel("页面加载时间 load / ms（对数刻度）")
    ax.set_title("真实站点加载时间与页面总字节")
    _smart_annotate(ax, fig, [(site, size / 1_000_000.0, load) for site, size, load, _ in triples])
    return save_figure(
        fig,
        FIGURE_NAMES[5],
        caption=(
            "图 5 真实站点加载时间与页面总字节散点图（页面总字节是混杂因素）"
            if bake_caption
            else None
        ),
        out_dir=out_dir,
    )


def plot_lab_groups(
    rows: list[dict[str, Any]],
    out_dir: Path | None = None,
    *,
    bake_caption: bool = True,
) -> list[Path]:
    """图 6：受控实验四组箱线图，叠加各保留轮次的实测点。"""
    lab = [row for row in _lab_rows(rows) if _number(row, "initcwnd_mss") is not None]
    if not lab:
        return []
    lab.sort(key=lambda row: _number(row, "initcwnd_mss"))

    groups: list[list[float]] = []
    labels: list[str] = []
    for row in lab:
        samples = [float(value) for value in row.get("load_samples", []) if value is not None]
        if not samples and _number(row, "load_ms") is not None:
            samples = [_number(row, "load_ms")]
        groups.append(samples)
        labels.append(f"{row['site']}\n({_number(row, 'initcwnd_mss'):.0f} MSS, n={len(samples)})")

    fig = new_figure(6.4, 4.9)
    ax = fig.add_subplot(111)
    boxplot = ax.boxplot(
        groups,
        tick_labels=labels,
        widths=0.5,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": PALETTE[5], "linewidth": 1.8},
        whiskerprops={"color": PALETTE[7]},
        capprops={"color": PALETTE[7]},
    )
    for index, patch in enumerate(boxplot["boxes"]):
        patch.set_facecolor(PALETTE[index % len(PALETTE)])
        patch.set_alpha(0.55)

    rng = np.random.default_rng(20261104)
    for index, samples in enumerate(groups, start=1):
        jitter = np.linspace(-0.11, 0.11, len(samples)) if len(samples) > 1 else np.array([0.0])
        if len(samples) > 2:
            rng.shuffle(jitter)
        ax.scatter(
            np.full(len(samples), index) + jitter,
            samples,
            s=24,
            color=PALETTE[7],
            alpha=0.75,
            zorder=3,
        )
        median = float(np.median(samples))
        ax.annotate(
            f"{median:.1f}",
            (index, max(samples)),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
            color=PALETTE[5],
        )

    low = min(min(samples) for samples in groups if samples)
    high = max(max(samples) for samples in groups if samples)
    padding = max(8.0, (high - low) * 0.08)
    ax.set_ylim(low - padding, high + padding * 2.2)
    ax.set_xlabel("受控实验分组（initcwnd 设定值）")
    ax.set_ylabel("页面加载时间 load / ms")
    ax.set_title("受控实验四组加载时间对比")
    return save_figure(
        fig,
        FIGURE_NAMES[6],
        caption=(
            "图 6 受控实验四组加载时间箱线图"
            "（固定 RTT 60 ms，IQR 剔除后保留 3~5 轮，点为各保留轮次）"
            if bake_caption
            else None
        ),
        out_dir=out_dir,
    )
