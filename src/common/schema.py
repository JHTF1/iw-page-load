"""两份 CSV 的字段契约与校验。

字段变更属于公共契约变更：必须走 PR，三人确认后同步更新 docs/数据字典.md。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Iterable, Sequence

INITCWND_CSV_NAME = "initcwnd.csv"
PAGELOAD_CSV_NAME = "pageload.csv"

LAB_SITE_PREFIX = "lab-"
METHOD_PASSIVE = "passive"
METHOD_LAB = "lab"
METHODS = (METHOD_PASSIVE, METHOD_LAB)
CONFIDENCE_LEVELS = ("high", "medium", "low")
IP_VERSIONS = ("4", "6")
CACHE_MODES = ("cold", "warm")

MSS_TOLERANCE = 0.1


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str
    unit: str
    description: str
    required: bool = True


INITCWND_COLUMNS: tuple[Column, ...] = (
    Column("site", "str", "", "站点标识，与 pageload.csv 一致；受控实验写 lab-<initcwnd>"),
    Column("url", "str", "", "被测 URL"),
    Column("server_ip", "str", "", "服务器 IP"),
    Column("ip_version", "str", "", "IP 版本：4 或 6"),
    Column("timestamp_utc", "str", "", "采集时间，ISO 8601，UTC"),
    Column("initcwnd_bytes", "int", "byte", "首窗口字节数"),
    Column("mss_bytes", "int", "byte", "MSS 字节数"),
    Column("initcwnd_mss", "float", "MSS", "initcwnd 的 MSS 倍数"),
    Column("segment_count", "int", "segment", "首窗口内报文段数量，仅供参考"),
    Column("retrans_count", "int", "segment", "首窗口内重传数量"),
    Column("method", "str", "", "passive（真实站点）或 lab（受控实验）"),
    Column("confidence", "str", "", "high / medium / low"),
    Column("notes", "str", "", "备注", required=False),
)

PAGELOAD_COLUMNS: tuple[Column, ...] = (
    Column("site", "str", "", "站点标识，与 initcwnd.csv 一致"),
    Column("url", "str", "", "被测 URL"),
    Column("run_id", "int", "", "同一站点的测量轮次编号"),
    Column("timestamp_utc", "str", "", "采集时间，ISO 8601，UTC"),
    Column("dns_ms", "float", "ms", "DNS 解析耗时"),
    Column("tcp_ms", "float", "ms", "TCP 连接耗时"),
    Column("tls_ms", "float", "ms", "TLS 握手耗时"),
    Column("ttfb_ms", "float", "ms", "首字节时间"),
    Column("dom_content_loaded_ms", "float", "ms", "DOMContentLoaded 耗时"),
    Column("load_ms", "float", "ms", "load 事件耗时"),
    Column("request_count", "int", "request", "资源请求数"),
    Column("transfer_bytes", "int", "byte", "页面总传输字节"),
    Column("quic_disabled", "bool", "", "是否禁用 QUIC，正式数据必须为 true"),
    Column("cache_mode", "str", "", "cold 或 warm，正式数据必须为 cold"),
    Column("network_env", "str", "", "网络环境描述"),
    Column("notes", "str", "", "备注", required=False),
)


@dataclass
class InitcwndRecord:
    site: str
    url: str
    server_ip: str
    ip_version: str
    timestamp_utc: str
    initcwnd_bytes: int
    mss_bytes: int
    initcwnd_mss: float
    segment_count: int
    retrans_count: int
    method: str
    confidence: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def validate(self) -> list[str]:
        return validate_initcwnd(self.as_dict())


@dataclass
class PageloadRecord:
    site: str
    url: str
    run_id: int
    timestamp_utc: str
    dns_ms: float
    tcp_ms: float
    tls_ms: float
    ttfb_ms: float
    dom_content_loaded_ms: float
    load_ms: float
    request_count: int
    transfer_bytes: int
    quic_disabled: bool
    cache_mode: str
    network_env: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def validate(self, strict: bool = True) -> list[str]:
        return validate_pageload(self.as_dict(), strict=strict)


def _type_ok(value: Any, dtype: str) -> bool:
    if dtype == "str":
        return isinstance(value, str)
    if dtype == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if dtype == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if dtype == "bool":
        return isinstance(value, bool)
    raise ValueError(f"未知 dtype: {dtype}")


def validate_record(record: dict[str, Any], columns: Sequence[Column]) -> list[str]:
    errors: list[str] = []
    for col in columns:
        value = record.get(col.name)
        if value is None or value == "":
            if col.required:
                errors.append(f"{col.name}: 必填字段为空")
            continue
        if not _type_ok(value, col.dtype):
            errors.append(f"{col.name}: 期望 {col.dtype}，实际 {type(value).__name__}")
    return errors


def validate_initcwnd(record: dict[str, Any]) -> list[str]:
    errors = validate_record(record, INITCWND_COLUMNS)
    if errors:
        return errors

    if record["ip_version"] not in IP_VERSIONS:
        errors.append(f"ip_version: 必须是 {IP_VERSIONS} 之一")
    if record["method"] not in METHODS:
        errors.append(f"method: 必须是 {METHODS} 之一")
    if record["confidence"] not in CONFIDENCE_LEVELS:
        errors.append(f"confidence: 必须是 {CONFIDENCE_LEVELS} 之一")
    if record["initcwnd_bytes"] <= 0:
        errors.append("initcwnd_bytes: 必须大于 0")
    if record["mss_bytes"] <= 0:
        errors.append("mss_bytes: 必须大于 0")
    if record["initcwnd_mss"] <= 0:
        errors.append("initcwnd_mss: 必须大于 0")

    if record["initcwnd_bytes"] > 0 and record["mss_bytes"] > 0:
        expected = record["initcwnd_bytes"] / record["mss_bytes"]
        if abs(record["initcwnd_mss"] - expected) > MSS_TOLERANCE:
            errors.append(
                "initcwnd_mss: 与 initcwnd_bytes/mss_bytes 不一致"
                f"（记录 {record['initcwnd_mss']:.2f}，应为 {expected:.2f}）"
            )

    is_lab = record["site"].startswith(LAB_SITE_PREFIX)
    if is_lab and record["method"] != METHOD_LAB:
        errors.append("method: lab- 前缀的站点必须使用 lab 方法")
    if not is_lab and record["method"] != METHOD_PASSIVE:
        errors.append("method: 真实站点必须使用 passive 方法")
    return errors


def validate_pageload(record: dict[str, Any], strict: bool = True) -> list[str]:
    errors = validate_record(record, PAGELOAD_COLUMNS)
    if errors:
        return errors

    if record["cache_mode"] not in CACHE_MODES:
        errors.append(f"cache_mode: 必须是 {CACHE_MODES} 之一")
    numeric_fields = (
        "dns_ms",
        "tcp_ms",
        "tls_ms",
        "ttfb_ms",
        "dom_content_loaded_ms",
        "load_ms",
        "transfer_bytes",
        "request_count",
    )
    for name in numeric_fields:
        if record[name] < 0:
            errors.append(f"{name}: 不能为负数")
    if strict and not record["quic_disabled"]:
        errors.append("quic_disabled: 正式数据必须禁用 QUIC")
    if strict and record["cache_mode"] != "cold":
        errors.append("cache_mode: 正式数据必须是 cold")
    return errors


_TRUE_VALUES = {"true", "1", "yes", "y"}
_FALSE_VALUES = {"false", "0", "no", "n"}


def _coerce(value: Any, dtype: str) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if dtype == "str":
        return str(value)
    if dtype == "int":
        return int(float(value))
    if dtype == "float":
        return float(value)
    if dtype == "bool":
        if isinstance(value, bool):
            return value
        lowered = str(value).lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
        raise ValueError(f"无法解析为布尔值: {value!r}")
    raise ValueError(f"未知 dtype: {dtype}")


def normalize_record(record: dict[str, Any], columns: Sequence[Column]) -> dict[str, Any]:
    return {col.name: _coerce(record.get(col.name), col.dtype) for col in columns}


def read_csv(path: Path, columns: Sequence[Column]) -> list[dict[str, Any]]:
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [normalize_record(row, columns) for row in rows]


def write_csv(
    path: Path,
    records: Iterable[dict[str, Any]],
    columns: Sequence[Column],
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[col.name for col in columns])
        writer.writeheader()
        for record in records:
            row: dict[str, Any] = {}
            for col in columns:
                value = record.get(col.name)
                if value is None:
                    value = ""
                elif isinstance(value, bool):
                    value = "true" if value else "false"
                row[col.name] = value
            writer.writerow(row)
    return path


def read_initcwnd_csv(path: Path) -> list[dict[str, Any]]:
    return read_csv(path, INITCWND_COLUMNS)


def read_pageload_csv(path: Path) -> list[dict[str, Any]]:
    return read_csv(path, PAGELOAD_COLUMNS)


def write_initcwnd_csv(path: Path, records: Iterable[dict[str, Any]]) -> Path:
    return write_csv(path, records, INITCWND_COLUMNS)


def write_pageload_csv(path: Path, records: Iterable[dict[str, Any]]) -> Path:
    return write_csv(path, records, PAGELOAD_COLUMNS)
