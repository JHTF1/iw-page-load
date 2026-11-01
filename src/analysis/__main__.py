"""CLI：python -m src.analysis

完整管线：读取 → schema 校验 → 按站点聚合合并 → 统计检验 → 出表 → 出图。
--demo 使用内置假数据跑通管线，用于真实数据到位前验证分析链路。
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Any

from ..common.logging_setup import get_logger
from ..common.paths import INITCWND_CSV, PAGELOAD_CSV, RESULTS_FIGURES, RESULTS_TABLES
from ..common.schema import read_initcwnd_csv, read_pageload_csv
from .merge import merge
from .plots import (
    plot_initcwnd_distribution,
    plot_lab_groups,
    plot_load_vs_bytes,
    plot_ttfb_vs_initcwnd,
)
from .stats import group_compare, partial_spearman, spearman

MERGED_TABLE = "merged_by_site.csv"
STATS_TABLE = "stats_summary.csv"
LAB_TABLE = "lab_group_summary.csv"

MERGED_COLUMNS = (
    "site",
    "group",
    "initcwnd_mss",
    "initcwnd_bytes",
    "mss_bytes",
    "ttfb_ms",
    "load_ms",
    "dns_ms",
    "tcp_ms",
    "tls_ms",
    "dom_content_loaded_ms",
    "request_count",
    "transfer_bytes",
    "runs_total",
    "runs_used",
    "confidence",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.analysis",
        description="合并数据、统计检验并生成图表",
    )
    parser.add_argument("--initcwnd", default=str(INITCWND_CSV), help="initcwnd CSV 路径")
    parser.add_argument("--pageload", default=str(PAGELOAD_CSV), help="pageload CSV 路径")
    parser.add_argument("--figures", default=str(RESULTS_FIGURES), help="图表输出目录")
    parser.add_argument("--tables", default=str(RESULTS_TABLES), help="统计表输出目录")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用内置假数据跑通分析管线（非正式结果，不读取 CSV）",
    )
    return parser


def _round(value: Any, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})
    return path


def _correlation_row(comparison: str, result: dict[str, Any], note: str = "") -> dict[str, Any]:
    return {
        "comparison": comparison,
        "method": result["method"],
        "statistic": _round(result.get("rho")),
        "p_value": _round(result.get("p_value")),
        "p_adjusted": None,
        "effect_size": _round(result.get("effect_size")),
        "n": result.get("n"),
        "note": note,
    }


def _lab_stats_rows(merged: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lab = [row for row in merged if row["group"] == "lab"]
    group_values = {
        row["site"]: row["load_samples"] or [row["load_ms"]]
        for row in lab
        if row.get("load_samples") or row.get("load_ms") is not None
    }
    if not group_values:
        return [], []

    result = group_compare(group_values)
    summary_rows = [
        {
            "site": row["site"],
            "initcwnd_mss": _round(row.get("initcwnd_mss")),
            "n": result["groups"].get(row["site"], {}).get("n", 0),
            "median": _round(result["groups"].get(row["site"], {}).get("median")),
            "q1": _round(result["groups"].get(row["site"], {}).get("q1")),
            "q3": _round(result["groups"].get(row["site"], {}).get("q3")),
            "min": _round(result["groups"].get(row["site"], {}).get("min")),
            "max": _round(result["groups"].get(row["site"], {}).get("max")),
        }
        for row in lab
        if row["site"] in result["groups"]
    ]

    stats_rows: list[dict[str, Any]] = []
    for comparison in result["comparisons"]:
        name_a, name_b = comparison["group_a"], comparison["group_b"]
        median_a = result["groups"][name_a]["median"]
        median_b = result["groups"][name_b]["median"]
        stats_rows.append(
            {
                "comparison": f"受控实验 {name_a} vs {name_b}",
                "method": comparison["method"],
                "statistic": _round(comparison.get("u")),
                "p_value": _round(comparison.get("p_value")),
                "p_adjusted": _round(comparison.get("p_adjusted")),
                "effect_size": _round(comparison.get("effect_size")),
                "n": comparison["n_a"] + comparison["n_b"],
                "note": f"load 中位数 {name_a}={_round(median_a)} ms，{name_b}={_round(median_b)} ms",
            }
        )
    return stats_rows, summary_rows


def _write_tables(merged: list[dict[str, Any]], tables_dir: Path) -> list[Path]:
    merged_rows = [
        {
            key: _round(item.get(key)) if isinstance(item.get(key), float) else item.get(key)
            for key in MERGED_COLUMNS
        }
        for item in merged
    ]
    stats_rows: list[dict[str, Any]] = []
    real = [row for row in merged if row["group"] == "real"]
    if len(real) >= 3:
        ttfb_corr = spearman([row["initcwnd_mss"] for row in real], [row["ttfb_ms"] for row in real])
        load_corr = spearman([row["initcwnd_mss"] for row in real], [row["load_ms"] for row in real])
        partial = partial_spearman(
            [row["initcwnd_mss"] for row in real],
            [row["load_ms"] for row in real],
            [row["transfer_bytes"] for row in real],
        )
        stats_rows.append(_correlation_row("真实站点 TTFB ~ initcwnd", ttfb_corr, "结论仅限相关"))
        stats_rows.append(_correlation_row("真实站点 load ~ initcwnd", load_corr, "结论仅限相关"))
        stats_rows.append(
            _correlation_row(
                "真实站点 load ~ initcwnd（控制 transfer_bytes）",
                partial,
                "偏相关控制页面总字节混杂因素",
            )
        )

    lab_stats_rows, lab_summary_rows = _lab_stats_rows(merged)
    stats_rows.extend(lab_stats_rows)

    paths = [
        _write_rows(tables_dir / MERGED_TABLE, merged_rows),
        _write_rows(tables_dir / STATS_TABLE, stats_rows),
    ]
    if lab_summary_rows:
        paths.append(_write_rows(tables_dir / LAB_TABLE, lab_summary_rows))
    return paths


def _demo_dataset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """内置假数据：真实站点与受控四组，覆盖完整分析管线。"""
    rng = random.Random(20261031)
    timestamp = "2026-10-31T02:00:00Z"
    mss = 1460
    real_sites = [
        ("baidu", "https://www.baidu.com/", 10, "110.242.68.66"),
        ("taobao", "https://www.taobao.com/", 8, "106.11.66.99"),
        ("bilibili", "https://www.bilibili.com/", 12, "47.103.24.44"),
        ("zhihu", "https://www.zhihu.com/", 4, "118.25.6.39"),
        ("github", "https://github.com/", 16, "140.82.112.3"),
        ("wikipedia", "https://www.wikipedia.org/", 20, "208.80.154.224"),
        ("amazon", "https://www.amazon.com/", 6, "205.251.242.103"),
        ("mit", "https://www.mit.edu/", 3, "18.9.22.69"),
    ]
    lab_sites = [("lab-2", 2), ("lab-4", 4), ("lab-10", 10), ("lab-20", 20)]

    initcwnd_rows: list[dict[str, Any]] = []
    pageload_rows: list[dict[str, Any]] = []
    for site, url, cwnd, ip in real_sites:
        initcwnd_rows.append(
            {
                "site": site,
                "url": url,
                "server_ip": ip,
                "ip_version": "4",
                "timestamp_utc": timestamp,
                "initcwnd_bytes": cwnd * mss,
                "mss_bytes": mss,
                "initcwnd_mss": float(cwnd),
                "segment_count": cwnd,
                "retrans_count": 0,
                "method": "passive",
                "confidence": "high",
                "notes": "",
            }
        )
        for run_id in range(1, 6):
            transfer_bytes = rng.randint(900_000, 2_000_000)
            ttfb = 60 + 420 / cwnd + rng.uniform(-8, 8)
            load = 900 + 1600 / cwnd + transfer_bytes / 1800 + rng.uniform(-80, 80)
            dcl = load * rng.uniform(0.6, 0.8)
            pageload_rows.append(
                {
                    "site": site,
                    "url": url,
                    "run_id": run_id,
                    "timestamp_utc": timestamp,
                    "dns_ms": round(rng.uniform(4, 25), 1),
                    "tcp_ms": round(rng.uniform(10, 40), 1),
                    "tls_ms": round(rng.uniform(20, 90), 1),
                    "ttfb_ms": round(ttfb, 1),
                    "dom_content_loaded_ms": round(dcl, 1),
                    "load_ms": round(load, 1),
                    "request_count": rng.randint(30, 90),
                    "transfer_bytes": transfer_bytes,
                    "quic_disabled": True,
                    "cache_mode": "cold",
                    "network_env": "演示假数据 · 本机 · 2026-10-31",
                    "notes": "",
                }
            )

    for site, cwnd in lab_sites:
        url = "http://127.0.0.1:8080/"
        initcwnd_rows.append(
            {
                "site": site,
                "url": url,
                "server_ip": "127.0.0.1",
                "ip_version": "4",
                "timestamp_utc": timestamp,
                "initcwnd_bytes": cwnd * mss,
                "mss_bytes": mss,
                "initcwnd_mss": float(cwnd),
                "segment_count": cwnd,
                "retrans_count": 0,
                "method": "lab",
                "confidence": "high",
                "notes": "",
            }
        )
        for run_id in range(1, 6):
            ttfb = 25 + 300 / cwnd + rng.uniform(-4, 4)
            load = 350 + 2200 / cwnd + rng.uniform(-40, 40)
            pageload_rows.append(
                {
                    "site": site,
                    "url": url,
                    "run_id": run_id,
                    "timestamp_utc": timestamp,
                    "dns_ms": 0.0,
                    "tcp_ms": round(rng.uniform(30, 31), 1),
                    "tls_ms": 0.0,
                    "ttfb_ms": round(ttfb, 1),
                    "dom_content_loaded_ms": round(load * 0.65, 1),
                    "load_ms": round(load, 1),
                    "request_count": 20,
                    "transfer_bytes": 1_200_000,
                    "quic_disabled": True,
                    "cache_mode": "cold",
                    "network_env": "演示假数据 · WSL nginx · RTT 60 ms",
                    "notes": "",
                }
            )
    return initcwnd_rows, pageload_rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = get_logger("analysis")

    if args.demo:
        logger.warning("演示模式：使用内置假数据，输出不是正式实验结果")
        initcwnd_rows, pageload_rows = _demo_dataset()
    else:
        try:
            initcwnd_rows = read_initcwnd_csv(Path(args.initcwnd))
            pageload_rows = read_pageload_csv(Path(args.pageload))
        except FileNotFoundError as error:
            logger.error("数据文件不存在：%s", error)
            return 1

    try:
        merged = merge(initcwnd_rows, pageload_rows)
    except ValueError as error:
        logger.error("%s", error)
        return 1

    if not merged:
        logger.error(
            "合并后没有可用站点：initcwnd=%s 行，pageload=%s 行，请检查 site 是否一致",
            len(initcwnd_rows),
            len(pageload_rows),
        )
        return 1

    tables = _write_tables(merged, Path(args.tables))
    figures = [
        *plot_initcwnd_distribution(merged, Path(args.figures)),
        *plot_ttfb_vs_initcwnd(merged, Path(args.figures)),
        *plot_load_vs_bytes(merged, Path(args.figures)),
        *plot_lab_groups(merged, Path(args.figures)),
    ]

    logger.info(
        "合并完成：initcwnd=%s 行，pageload=%s 行，合并后=%s 个站点（real=%s，lab=%s）",
        len(initcwnd_rows),
        len(pageload_rows),
        len(merged),
        sum(1 for row in merged if row["group"] == "real"),
        sum(1 for row in merged if row["group"] == "lab"),
    )
    logger.info("统计表 %s 个：%s", len(tables), "，".join(str(path) for path in tables))
    logger.info("图表 %s 个文件：%s", len(figures), "，".join(str(path) for path in figures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
