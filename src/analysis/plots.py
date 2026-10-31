"""四张结果图，统一走 src.common.style。

图题置于图下方，PNG 与 SVG 双份，编号与 docs/报告框架.md 第 5 章一致（图 3~图 6）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

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


def plot_initcwnd_distribution(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
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
    ax.set_xlabel("初始拥塞窗口 initcwnd / MSS")
    ax.set_ylabel("站点")
    ax.set_title("真实站点初始拥塞窗口分布")
    for index, value in enumerate(values):
        ax.text(value + 0.3, index, f"{value:.1f}", va="center", fontsize=9, color=PALETTE[7])
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    return save_figure(
        fig,
        FIGURE_NAMES[3],
        caption="图 3 真实站点 initcwnd 分布（数据来源：data/processed/initcwnd.csv）",
        out_dir=out_dir,
    )


def plot_ttfb_vs_initcwnd(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 4：TTFB 与 initcwnd 散点图，标注 Spearman 秩相关结果。"""
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

    fig = new_figure(6.4, 4.8)
    ax = fig.add_subplot(111)
    ax.scatter(x_values, y_values, s=46, color=PALETTE[0], edgecolor="white", linewidth=0.6, zorder=3)
    for site, x, y in pairs:
        ax.annotate(site, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=8, color=PALETTE[7])

    if len(set(x_values)) >= 2:
        slope, intercept = np.polyfit(x_values, y_values, 1)
        line_x = np.linspace(min(x_values), max(x_values), 100)
        ax.plot(line_x, slope * line_x + intercept, color=PALETTE[5], linewidth=1.2, label="最小二乘拟合线")
        ax.legend(loc="best")

    rho = result["rho"]
    annotation = "Spearman ρ 无法计算" if rho is None else (
        f"Spearman ρ = {rho:.3f}，{_p_text(result['p_value'])}，n = {result['n']}"
    )
    ax.text(
        0.03,
        0.03,
        annotation,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9.5,
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": PALETTE[4]},
    )
    ax.set_xlabel("初始拥塞窗口 initcwnd / MSS")
    ax.set_ylabel("首字节时间 TTFB / ms")
    ax.set_title("真实站点 TTFB 与 initcwnd")
    return save_figure(
        fig,
        FIGURE_NAMES[4],
        caption="图 4 真实站点 TTFB 与 initcwnd 散点图（结论仅为相关）",
        out_dir=out_dir,
    )


def plot_load_vs_bytes(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 5：加载时间与页面总字节散点图，展示需要控制的混杂变量。"""
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

    sizes = [size / 1_000_000.0 for _, size, _, _ in triples]
    loads = [load for _, _, load, _ in triples]
    partial = partial_spearman(
        [initcwnd for _, _, _, initcwnd in triples],
        [load for _, _, load, _ in triples],
        [size for _, size, _, _ in triples],
    )

    fig = new_figure(6.4, 4.8)
    ax = fig.add_subplot(111)
    ax.scatter(sizes, loads, s=46, color=PALETTE[2], edgecolor="white", linewidth=0.6, zorder=3)
    for site, size, load, _ in triples:
        ax.annotate(
            site,
            (size / 1_000_000.0, load),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
            color=PALETTE[7],
        )

    if len(set(sizes)) >= 2:
        slope, intercept = np.polyfit(sizes, loads, 1)
        line_x = np.linspace(min(sizes), max(sizes), 100)
        ax.plot(line_x, slope * line_x + intercept, color=PALETTE[5], linewidth=1.2, label="最小二乘拟合线")
        ax.legend(loc="best")

    rho = partial["rho"]
    annotation = "偏相关无法计算" if rho is None else (
        f"控制页面总字节后偏 Spearman ρ = {rho:.3f}，{_p_text(partial['p_value'])}"
    )
    ax.text(
        0.03,
        0.03,
        annotation,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9.5,
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": PALETTE[4]},
    )
    ax.set_xlabel("页面总传输字节 / MB")
    ax.set_ylabel("页面加载时间 load / ms")
    ax.set_title("真实站点加载时间与页面总字节")
    return save_figure(
        fig,
        FIGURE_NAMES[5],
        caption="图 5 真实站点加载时间与页面总字节散点图（页面总字节是混杂因素）",
        out_dir=out_dir,
    )


def plot_lab_groups(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 6：受控实验四组箱线图（每组用全部保留轮次，不只画中位数）。"""
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
        labels.append(f"{row['site']}\n({_number(row, 'initcwnd_mss'):.0f} MSS)")

    fig = new_figure(6.4, 4.8)
    ax = fig.add_subplot(111)
    boxplot = ax.boxplot(
        groups,
        tick_labels=labels,
        patch_artist=True,
        medianprops={"color": PALETTE[5], "linewidth": 1.6},
        whiskerprops={"color": PALETTE[7]},
        capprops={"color": PALETTE[7]},
        flierprops={"marker": "o", "markersize": 4, "markerfacecolor": PALETTE[5], "markeredgecolor": PALETTE[5]},
    )
    for index, patch in enumerate(boxplot["boxes"]):
        patch.set_facecolor(PALETTE[index % len(PALETTE)])
        patch.set_alpha(0.75)
    ax.set_xlabel("受控实验分组（initcwnd 设定值）")
    ax.set_ylabel("页面加载时间 load / ms")
    ax.set_title("受控实验四组加载时间对比")
    return save_figure(
        fig,
        FIGURE_NAMES[6],
        caption="图 6 受控实验四组加载时间箱线图（固定 RTT 60 ms，每组 5 轮）",
        out_dir=out_dir,
    )
