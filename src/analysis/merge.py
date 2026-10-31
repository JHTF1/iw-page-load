"""按 site 合并 initcwnd 与 pageload 两份数据。

规则（见 docs/数据字典.md 第四节）：
- 合并前两侧数据都必须通过 schema 校验，不通过的数据不得进入分析；
- 同一站点多轮 pageload 先剔除 IQR 异常轮次，再按站点取中位数；
- 合并键是 site，受控实验通过 lab- 前缀识别，与真实站点分开统计。
"""

from __future__ import annotations

from statistics import median
from typing import Any

from ..common.schema import LAB_SITE_PREFIX, validate_initcwnd, validate_pageload
from .stats import filter_outliers

GROUP_REAL = "real"
GROUP_LAB = "lab"

PAGELOAD_METRICS: tuple[str, ...] = (
    "dns_ms",
    "tcp_ms",
    "tls_ms",
    "ttfb_ms",
    "dom_content_loaded_ms",
    "load_ms",
    "request_count",
    "transfer_bytes",
)


def site_group(site: str) -> str:
    """lab- 前缀为受控实验，其余为真实站点。"""
    return GROUP_LAB if site.startswith(LAB_SITE_PREFIX) else GROUP_REAL


def aggregate_pageload(
    pageload_rows: list[dict[str, Any]],
    drop_outliers: bool = True,
) -> list[dict[str, Any]]:
    """把同一站点的多轮数据聚合为一行（各指标取中位数）。

    IQR 剔除以 load_ms 为判据，只剔除整个异常轮次，保留的轮次用于中位数与箱线图样本。
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in pageload_rows:
        grouped.setdefault(row["site"], []).append(row)

    aggregated: list[dict[str, Any]] = []
    for site, runs in grouped.items():
        runs_total = len(runs)
        kept = runs
        if drop_outliers and runs_total >= 4:
            kept_runs, _ = filter_outliers(
                runs,
                key=lambda run: run.get("load_ms"),
            )
            if kept_runs:
                kept = kept_runs

        record: dict[str, Any] = {
            "site": site,
            "group": site_group(site),
            "url": kept[0].get("url") or runs[0].get("url") or "",
            "runs_total": runs_total,
            "runs_used": len(kept),
        }
        for metric in PAGELOAD_METRICS:
            values = [float(run[metric]) for run in kept if run.get(metric) is not None]
            record[metric] = float(median(values)) if values else None
        record["ttfb_samples"] = [
            float(run["ttfb_ms"]) for run in kept if run.get("ttfb_ms") is not None
        ]
        record["load_samples"] = [
            float(run["load_ms"]) for run in kept if run.get("load_ms") is not None
        ]
        aggregated.append(record)
    return aggregated


def merge(
    initcwnd_rows: list[dict[str, Any]],
    pageload_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """以 site 为键合并，返回按站点排序的合并结果。

    两侧数据先逐行校验，任一行不通过即抛出 ValueError，不允许带病进入分析。
    """
    errors = [
        f"initcwnd[{index}] {error}"
        for index, row in enumerate(initcwnd_rows)
        for error in validate_initcwnd(row)
    ]
    errors += [
        f"pageload[{index}] {error}"
        for index, row in enumerate(pageload_rows)
        for error in validate_pageload(row)
    ]
    if errors:
        raise ValueError("数据校验未通过：\n" + "\n".join(errors))

    init_by_site: dict[str, dict[str, Any]] = {}
    for row in initcwnd_rows:
        init_by_site.setdefault(row["site"], row)

    merged: list[dict[str, Any]] = []
    for page in aggregate_pageload(pageload_rows):
        init = init_by_site.get(page["site"])
        if init is None:
            continue
        record = {
            "site": page["site"],
            "group": page["group"],
            "url": page["url"] or init["url"],
            "initcwnd_mss": float(init["initcwnd_mss"]),
            "initcwnd_bytes": int(init["initcwnd_bytes"]),
            "mss_bytes": int(init["mss_bytes"]),
            "method": init["method"],
            "confidence": init["confidence"],
            "runs_total": page["runs_total"],
            "runs_used": page["runs_used"],
            "ttfb_samples": page["ttfb_samples"],
            "load_samples": page["load_samples"],
        }
        for metric in PAGELOAD_METRICS:
            record[metric] = page[metric]
        merged.append(record)
    merged.sort(key=lambda item: item["site"])
    return merged
