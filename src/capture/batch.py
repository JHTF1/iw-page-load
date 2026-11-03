"""批量抓取站点清单并写入 initcwnd.csv。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..common.logging_setup import get_logger
from ..common.paths import DATA_RAW, SITES_CSV
from ..common.schema import validate_initcwnd
from ..common.settings import load_settings
from .initcwnd import measure_initcwnd
from .records import build_record, upsert_record, utc_now_iso
from .sniffer import capture_url

logger = get_logger("capture.batch")

CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}


def read_sites(sites_csv: Path) -> list[dict[str, str]]:
    with Path(sites_csv).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    sites = [
        {"site": (row.get("site") or "").strip(), "url": (row.get("url") or "").strip()}
        for row in rows
    ]
    return [row for row in sites if row["site"] and row["url"]]


def select_representative(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """按置信度、与中位数的距离、重传数依次选一轮代表站点。"""
    if not runs:
        raise ValueError("没有可用的测量轮次")

    values = sorted(int(run["initcwnd_bytes"]) for run in runs)
    middle = len(values) // 2
    median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2

    def rank(run: dict[str, Any]) -> tuple[int, float, int]:
        return (
            CONFIDENCE_RANK.get(str(run["confidence"]), 3),
            abs(int(run["initcwnd_bytes"]) - median),
            int(run["retrans_count"]),
        )

    return min(runs, key=rank)


def _annotate(runs: list[dict[str, Any]], chosen: dict[str, Any]) -> str:
    values = "/".join(str(int(run["initcwnd_bytes"])) for run in runs)
    note = f"{len(runs)} 轮首飞字节: {values}；取代表轮"
    existing = str(chosen.get("notes") or "").strip()
    return f"{existing}；{note}" if existing else note


def capture_sites(
    sites_csv: Path = SITES_CSV,
    *,
    repeats: int | None = None,
    only: str | None = None,
    csv_path: Path | None = None,
    duration_s: float | None = None,
    iface: str | None = None,
) -> list[dict[str, Any]]:
    settings = load_settings()
    capture_settings = settings.get("capture", {})
    rounds = int(repeats if repeats is not None else capture_settings.get("repeats", 2))
    if rounds <= 0:
        raise ValueError("repeats 必须大于 0")
    duration = float(duration_s if duration_s is not None else capture_settings.get("duration_s", 8.0))

    sites = read_sites(Path(sites_csv))
    if only is not None:
        sites = [row for row in sites if row["site"] == only]
        if not sites:
            raise ValueError(f"站点清单里没有 {only!r}")

    written: list[dict[str, Any]] = []
    failed_sites: set[str] = set()
    for row in sites:
        site, url = row["site"], row["url"]
        runs: list[dict[str, Any]] = []
        for run_id in range(1, rounds + 1):
            try:
                timestamp = utc_now_iso()
                pcap_path = capture_url(
                    url,
                    DATA_RAW / f"{site}-r{run_id}.pcap",
                    duration_s=duration,
                    iface=iface,
                )
                result = measure_initcwnd(pcap_path)
                record = build_record(result, site, url, timestamp)
                errors = validate_initcwnd(record)
                if errors:
                    raise ValueError("; ".join(errors))
                runs.append(record)
            except Exception as exc:
                logger.warning("%s 第 %d 轮失败: %s", site, run_id, exc)

        if not runs:
            logger.error("%s 全部轮次失败，已跳过", site)
            failed_sites.add(site)
            continue

        representative = dict(select_representative(runs))
        representative["notes"] = _annotate(runs, representative)
        try:
            path = upsert_record(representative, csv_path)
        except ValueError as exc:
            logger.error("%s 记录未通过校验，已跳过: %s", site, exc)
            failed_sites.add(site)
            continue
        written.append(representative)
        logger.info(
            "%s 写入 %s（%d/%d 轮有效，代表轮 %s bytes）",
            site,
            path,
            len(runs),
            rounds,
            representative["initcwnd_bytes"],
        )

    logger.info("批量结束：%d 个站点写入，%d 个站点失败", len(written), len(failed_sites))
    return written
