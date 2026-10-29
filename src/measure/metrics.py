"""指标采集与多轮统计。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def collect_site(url: str, repeats: int = 5) -> list[dict[str, Any]]:
    """对单个站点重复测量 repeats 轮，返回原始记录列表。

    TODO(B): 调用 cdp.ChromeSession，每轮冷缓存，字段与 schema.PAGELOAD_COLUMNS 对齐。
    """
    raise NotImplementedError(f"TODO(B): 测量 {url}")


def collect_all(
    sites_csv: Path,
    repeats: int = 5,
    only: str | None = None,
) -> list[dict[str, Any]]:
    """遍历站点清单逐个测量，返回全部原始记录。

    TODO(B): 读 config/sites.csv，跳过不可达站点并记录原因；only 非空时只测该站点。
    """
    raise NotImplementedError(f"TODO(B): 批量测量 {sites_csv}")


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """多轮汇总：中位数加四分位距剔除异常。

    TODO(B): 剔除规则与剔除数量必须保留，供实验记录和报告引用。
    """
    raise NotImplementedError("TODO(B): 多轮统计")
