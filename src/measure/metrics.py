"""指标采集与多轮统计。

对每个站点每轮启动一次独立的 Chrome 会话（独立临时 profile），保证冷缓存；
原始记录严格对齐 ``schema.PAGELOAD_COLUMNS``，写入前必须通过 ``validate_pageload``。
"""

from __future__ import annotations

import csv
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..common.logging_setup import get_logger
from ..common.schema import validate_pageload
from ..common.settings import load_settings
from .cdp import ChromeError, ChromeSession

logger = get_logger("measure.metrics")

FLOAT_FIELDS = (
    "dns_ms",
    "tcp_ms",
    "tls_ms",
    "ttfb_ms",
    "dom_content_loaded_ms",
    "load_ms",
)

DEFAULT_NETWORK_ENV = "Windows · 本机 Chrome · 冷缓存 · 禁用 QUIC"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(
    site: str,
    url: str,
    run_id: int,
    timing: dict[str, Any],
    *,
    network_env: str = DEFAULT_NETWORK_ENV,
) -> dict[str, Any]:
    """把 CDP 原始指标转成 pageload 契约记录。

    ``quic_disabled`` 不盲信启动参数：一旦协议是 h3 就记 false，
    让 schema 的严格校验把该轮挡在分析之外。
    """
    protocol = str(timing.get("protocol") or "")
    dns_ms = float(timing.get("dns_ms") or 0)
    tls_ms = float(timing.get("tls_ms") or 0)

    notes: list[str] = []
    if protocol == "h3":
        notes.append("检测到 HTTP/3，QUIC 未禁用")
    if tls_ms <= 0:
        notes.append("无 TLS 握手（HTTP 站点）")
    if dns_ms <= 0:
        notes.append("DNS 命中缓存")

    record: dict[str, Any] = {
        "site": site,
        "url": url,
        "run_id": int(run_id),
        "timestamp_utc": str(timing.get("timestamp_utc") or _utc_now()),
        "dns_ms": round(dns_ms, 1),
        "tcp_ms": round(float(timing.get("tcp_ms") or 0), 1),
        "tls_ms": round(tls_ms, 1),
        "ttfb_ms": round(float(timing.get("ttfb_ms") or 0), 1),
        "dom_content_loaded_ms": round(float(timing.get("dom_content_loaded_ms") or 0), 1),
        "load_ms": round(float(timing.get("load_ms") or 0), 1),
        "request_count": int(timing.get("request_count") or 0),
        "transfer_bytes": int(timing.get("transfer_bytes") or 0),
        "quic_disabled": protocol != "h3",
        "cache_mode": "cold",
        "network_env": network_env,
        "notes": "; ".join(notes),
    }
    return record


def collect_site(
    site: str,
    url: str,
    repeats: int = 5,
    *,
    chrome_binary: str | None = None,
    port: int = 9222,
    timeout_ms: int = 30000,
    network_env: str = DEFAULT_NETWORK_ENV,
) -> list[dict[str, Any]]:
    """对单个站点重复测量，每轮一个新 Chrome 会话（冷缓存）。

    单轮失败或数据不合规时跳过该轮并记日志，不中断整个站点。
    """
    records: list[dict[str, Any]] = []
    for run_id in range(1, repeats + 1):
        try:
            with ChromeSession(binary=chrome_binary, port=port) as session:
                timing = session.navigate(url, timeout_ms=timeout_ms)
        except (ChromeError, FileNotFoundError, OSError) as exc:
            logger.warning("%s 第 %d 轮失败: %s", site, run_id, exc)
            continue

        if timing.get("error"):
            logger.warning("%s 第 %d 轮导航失败: %s", site, run_id, timing["error"])
            continue

        record = build_record(site, url, run_id, timing, network_env=network_env)
        errors = validate_pageload(record)
        if errors:
            logger.warning("%s 第 %d 轮数据不合规，已丢弃: %s", site, run_id, "; ".join(errors))
            continue
        records.append(record)
    return records


def collect_all(
    sites_csv: Path,
    repeats: int = 5,
    only: str | None = None,
    *,
    network_env: str | None = None,
) -> list[dict[str, Any]]:
    """遍历站点清单逐个测量，返回全部原始记录。

    不可达站点只记日志、不中断流程；``only`` 非空时只测该站点。
    """
    settings = load_settings()
    measure = settings.get("measure", {})
    chrome_binary = measure.get("chrome_binary", "auto")
    port = int(measure.get("remote_debug_port", 9222))
    timeout_ms = int(measure.get("navigation_timeout_ms", 30000))
    env = network_env or DEFAULT_NETWORK_ENV

    sites = _read_sites(Path(sites_csv))
    if only:
        sites = [row for row in sites if row["site"] == only]
        if not sites:
            raise ValueError(f"站点清单里没有 {only!r}")

    all_runs: list[dict[str, Any]] = []
    for row in sites:
        site, url = row["site"], row["url"]
        logger.info("开始测量 %s: %s", site, url)
        runs = collect_site(
            site,
            url,
            repeats=repeats,
            chrome_binary=chrome_binary,
            port=port,
            timeout_ms=timeout_ms,
            network_env=env,
        )
        if len(runs) < repeats:
            logger.warning("%s 有效轮次 %d/%d", site, len(runs), repeats)
        if not runs:
            logger.error("%s 全部轮次失败，该站点从数据集中剔除", site)
        all_runs.extend(runs)

    logger.info("共采集 %d 条记录，覆盖 %d 个站点", len(all_runs), len({r["site"] for r in all_runs}))
    return all_runs


def summarize(runs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """多轮汇总：按 load_ms 用 IQR 剔除异常轮，其余指标取中位数。

    剔除结果（条数与轮次编号）保留在返回值里，供实验记录和报告引用。
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        grouped.setdefault(str(run["site"]), []).append(run)

    summary: dict[str, Any] = {}
    for site, items in grouped.items():
        kept, outliers = _drop_outliers(items)
        summary[site] = {
            "n_raw": len(items),
            "n_kept": len(kept),
            "n_outliers": len(outliers),
            "outlier_run_ids": [item["run_id"] for item in outliers],
            **{
                field: round(statistics.median(float(item[field]) for item in kept), 1)
                for field in FLOAT_FIELDS
            },
            "request_count": int(statistics.median(int(item["request_count"]) for item in kept)),
            "transfer_bytes": int(statistics.median(int(item["transfer_bytes"]) for item in kept)),
        }
    return summary


def _read_sites(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    sites = [
        {"site": (row.get("site") or "").strip(), "url": (row.get("url") or "").strip()}
        for row in rows
    ]
    return [row for row in sites if row["site"] and row["url"]]


def _quantile(sorted_values: list[float], q: float) -> float:
    """线性插值分位数，避免依赖 numpy。"""
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight


def _drop_outliers(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """以 load_ms 为基准判定异常轮。

    样本少于 4 条时 IQR 不可靠，不做剔除。
    """
    if len(items) < 4:
        return items, []

    values = sorted(float(item["load_ms"]) for item in items)
    q1 = _quantile(values, 0.25)
    q3 = _quantile(values, 0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    kept = [item for item in items if lower_bound <= float(item["load_ms"]) <= upper_bound]
    outliers = [item for item in items if item not in kept]
    return kept, outliers
