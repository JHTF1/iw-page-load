"""四张结果图，统一走 src.common.style。

TODO(C): 图题置于图下方，PNG 与 SVG 双份，编号与报告一致。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def plot_initcwnd_distribution(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 1：真实站点 initcwnd 分布。TODO(C)。"""
    raise NotImplementedError("TODO(C): initcwnd 分布图")


def plot_ttfb_vs_initcwnd(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 2：TTFB 与 initcwnd 散点图。TODO(C)。"""
    raise NotImplementedError("TODO(C): TTFB-initcwnd 散点图")


def plot_load_vs_bytes(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 3：加载时间与页面总字节散点图。TODO(C)。"""
    raise NotImplementedError("TODO(C): 加载时间-总字节散点图")


def plot_lab_groups(rows: list[dict[str, Any]], out_dir: Path | None = None) -> list[Path]:
    """图 4：受控实验四组箱线图。TODO(C)。"""
    raise NotImplementedError("TODO(C): 受控四组箱线图")
