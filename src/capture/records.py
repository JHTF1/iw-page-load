"""把单站 initcwnd 测量结果组装成契约记录并写入 CSV。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.paths import INITCWND_CSV
from ..common.schema import (
    LAB_SITE_PREFIX,
    METHOD_LAB,
    METHOD_PASSIVE,
    read_initcwnd_csv,
    validate_initcwnd,
    write_initcwnd_csv,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(
    result: dict[str, Any],
    site: str,
    url: str,
    timestamp_utc: str,
) -> dict[str, Any]:
    method = METHOD_LAB if site.startswith(LAB_SITE_PREFIX) else METHOD_PASSIVE
    return {
        "site": site,
        "url": url,
        "server_ip": result["server_ip"],
        "ip_version": result["ip_version"],
        "timestamp_utc": timestamp_utc,
        "initcwnd_bytes": int(result["initcwnd_bytes"]),
        "mss_bytes": int(result["mss_bytes"]),
        "initcwnd_mss": round(float(result["initcwnd_mss"]), 2),
        "segment_count": int(result["segment_count"]),
        "retrans_count": int(result["retrans_count"]),
        "method": method,
        "confidence": result["confidence"],
        "notes": result.get("notes") or "",
    }


def upsert_record(record: dict[str, Any], csv_path: Path | None = None) -> Path:
    """按 site 写入或更新一行；校验不通过时拒绝写入。"""
    path = Path(csv_path) if csv_path is not None else INITCWND_CSV
    errors = validate_initcwnd(record)
    if errors:
        raise ValueError("initcwnd 记录未通过 schema 校验: " + "; ".join(errors))

    rows: dict[str, dict[str, Any]] = {}
    if path.exists():
        for row in read_initcwnd_csv(path):
            rows[str(row["site"])] = row
    rows[str(record["site"])] = record
    return write_initcwnd_csv(path, [rows[key] for key in sorted(rows)])
