from __future__ import annotations

from pathlib import Path

import pytest

from src.common.schema import (
    read_initcwnd_csv,
    read_pageload_csv,
    validate_initcwnd,
    validate_pageload,
    write_initcwnd_csv,
    write_pageload_csv,
)


def make_initcwnd(**overrides):
    data = {
        "site": "baidu",
        "url": "https://www.baidu.com/",
        "server_ip": "110.242.68.66",
        "ip_version": "4",
        "timestamp_utc": "2026-11-04T02:15:30Z",
        "initcwnd_bytes": 14600,
        "mss_bytes": 1460,
        "initcwnd_mss": 10.0,
        "segment_count": 10,
        "retrans_count": 0,
        "method": "passive",
        "confidence": "high",
        "notes": "",
    }
    data.update(overrides)
    return data


def make_pageload(**overrides):
    data = {
        "site": "baidu",
        "url": "https://www.baidu.com/",
        "run_id": 1,
        "timestamp_utc": "2026-11-04T02:16:00Z",
        "dns_ms": 12.5,
        "tcp_ms": 20.0,
        "tls_ms": 35.2,
        "ttfb_ms": 120.4,
        "dom_content_loaded_ms": 450.0,
        "load_ms": 700.5,
        "request_count": 42,
        "transfer_bytes": 1200000,
        "quic_disabled": True,
        "cache_mode": "cold",
        "network_env": "有线 · 中国移动 · 2026-11-04 10:00",
        "notes": "",
    }
    data.update(overrides)
    return data


def test_initcwnd_record_is_valid():
    assert validate_initcwnd(make_initcwnd()) == []


def test_initcwnd_missing_required_field():
    record = make_initcwnd()
    del record["server_ip"]
    errors = validate_initcwnd(record)
    assert any("server_ip" in error for error in errors)


def test_initcwnd_mss_must_match_bytes():
    record = make_initcwnd(initcwnd_mss=12.0)
    errors = validate_initcwnd(record)
    assert any("initcwnd_mss" in error for error in errors)


def test_lab_site_requires_lab_method():
    record = make_initcwnd(site="lab-10", method="passive", notes="")
    errors = validate_initcwnd(record)
    assert any("lab 方法" in error for error in errors)


def test_lab_site_with_lab_method_is_valid():
    record = make_initcwnd(site="lab-10", method="lab")
    assert validate_initcwnd(record) == []


def test_pageload_record_is_valid():
    assert validate_pageload(make_pageload()) == []


def test_pageload_requires_quic_disabled_in_strict_mode():
    errors = validate_pageload(make_pageload(quic_disabled=False))
    assert any("quic_disabled" in error for error in errors)
    assert validate_pageload(make_pageload(quic_disabled=False), strict=False) == []


def test_pageload_requires_cold_cache_in_strict_mode():
    errors = validate_pageload(make_pageload(cache_mode="warm"))
    assert any("cache_mode" in error for error in errors)


def test_initcwnd_csv_roundtrip(tmp_path: Path):
    path = tmp_path / "initcwnd.csv"
    write_initcwnd_csv(path, [make_initcwnd()])

    rows = read_initcwnd_csv(path)

    assert len(rows) == 1
    assert rows[0]["site"] == "baidu"
    assert rows[0]["initcwnd_bytes"] == 14600
    assert isinstance(rows[0]["initcwnd_mss"], float)
    assert rows[0]["notes"] is None
    assert validate_initcwnd(rows[0]) == []


def test_pageload_csv_roundtrip(tmp_path: Path):
    path = tmp_path / "pageload.csv"
    write_pageload_csv(path, [make_pageload()])

    rows = read_pageload_csv(path)

    assert len(rows) == 1
    assert rows[0]["quic_disabled"] is True
    assert isinstance(rows[0]["ttfb_ms"], float)
    assert validate_pageload(rows[0]) == []
