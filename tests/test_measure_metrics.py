from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.common.schema import PAGELOAD_COLUMNS, validate_pageload
from src.measure import metrics
from src.measure.cdp import ChromeError


def _timing(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "dns_ms": 12.34,
        "tcp_ms": 30.25,
        "tls_ms": 25.0,
        "ttfb_ms": 60.66,
        "dom_content_loaded_ms": 900.0,
        "load_ms": 1500.0,
        "request_count": 30,
        "transfer_bytes": 500_000,
        "protocol": "h2",
        "timestamp_utc": "2026-11-04T02:15:30Z",
    }
    base.update(overrides)
    return base


def _record(run_id: int, load_ms: float, ttfb_ms: float = 60.0) -> dict[str, Any]:
    return {
        "site": "demo",
        "url": "https://example.com/",
        "run_id": run_id,
        "timestamp_utc": "2026-11-04T02:15:30Z",
        "dns_ms": 10.0,
        "tcp_ms": 20.0,
        "tls_ms": 15.0,
        "ttfb_ms": ttfb_ms,
        "dom_content_loaded_ms": load_ms / 2,
        "load_ms": load_ms,
        "request_count": 21,
        "transfer_bytes": 400_000,
        "quic_disabled": True,
        "cache_mode": "cold",
        "network_env": metrics.DEFAULT_NETWORK_ENV,
        "notes": "",
    }


# ---- build_record ----


def test_build_record_matches_pageload_contract():
    record = metrics.build_record("demo", "https://example.com/", 1, _timing())

    assert [column.name for column in PAGELOAD_COLUMNS] == list(record)
    assert validate_pageload(record) == []
    assert record["site"] == "demo"
    assert record["run_id"] == 1
    assert record["timestamp_utc"] == "2026-11-04T02:15:30Z"
    assert record["quic_disabled"] is True
    assert record["cache_mode"] == "cold"
    assert record["dns_ms"] == 12.3
    assert record["ttfb_ms"] == 60.7


def test_build_record_flags_http3_and_fails_strict_validation():
    record = metrics.build_record("demo", "https://example.com/", 1, _timing(protocol="h3"))

    assert record["quic_disabled"] is False
    assert "HTTP/3" in record["notes"]
    errors = validate_pageload(record)
    assert any("quic_disabled" in error for error in errors)


def test_build_record_notes_http_site_and_cached_dns():
    record = metrics.build_record(
        "lab-10",
        "http://192.168.1.2:8080/",
        1,
        _timing(tls_ms=0, dns_ms=0, protocol="http/1.1"),
    )

    assert "无 TLS 握手" in record["notes"]
    assert "DNS 命中缓存" in record["notes"]
    assert record["tls_ms"] == 0.0


# ---- collect_site ----


def _patch_sessions(monkeypatch: pytest.MonkeyPatch, timings: list[Any]) -> None:
    class FakeSession:
        def __init__(self, binary: str | None = None, port: int = 9222) -> None:
            self._timings = timings

        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def navigate(self, url: str, timeout_ms: int = 30000) -> dict[str, Any]:
            item = self._timings.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(metrics, "ChromeSession", FakeSession)


def test_collect_site_skips_failed_rounds(monkeypatch: pytest.MonkeyPatch):
    timings: list[Any] = [
        _timing(),
        ChromeError("导航超时"),
        {"error": "net::ERR_NAME_NOT_RESOLVED"},
        _timing(load_ms=1600.0),
    ]
    _patch_sessions(monkeypatch, timings)

    records = metrics.collect_site("demo", "https://example.com/", repeats=4)

    assert len(records) == 2
    assert [record["run_id"] for record in records] == [1, 4]
    assert all(validate_pageload(record) == [] for record in records)


def test_collect_site_drops_record_that_breaks_contract(monkeypatch: pytest.MonkeyPatch):
    timings: list[Any] = [_timing(), _timing(protocol="h3")]
    _patch_sessions(monkeypatch, timings)

    records = metrics.collect_site("demo", "https://example.com/", repeats=2)

    assert len(records) == 1
    assert records[0]["run_id"] == 1


# ---- collect_all ----


def _write_sites(path: Path) -> None:
    path.write_text(
        "site,url,region,category,notes\n"
        "demo,https://example.com/,国内,测试,\n"
        "other,https://example.org/,国内,测试,\n",
        encoding="utf-8",
    )


def test_collect_all_reads_sites_and_filters_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    sites_csv: Path = tmp_path / "sites.csv"
    _write_sites(sites_csv)

    seen: list[str] = []

    def fake_collect_site(site: str, url: str, repeats: int = 5, **kwargs: Any) -> list[dict[str, Any]]:
        seen.append(site)
        return [{**_record(1, 100.0), "site": site}]

    monkeypatch.setattr(metrics, "collect_site", fake_collect_site)

    all_runs = metrics.collect_all(sites_csv, repeats=2)
    assert seen == ["demo", "other"]
    assert {run["site"] for run in all_runs} == {"demo", "other"}

    seen.clear()
    only_runs = metrics.collect_all(sites_csv, repeats=2, only="demo")
    assert seen == ["demo"]
    assert all(run["site"] == "demo" for run in only_runs)


def test_collect_all_rejects_unknown_site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    sites_csv: Path = tmp_path / "sites.csv"
    _write_sites(sites_csv)

    with pytest.raises(ValueError, match="not-found"):
        metrics.collect_all(sites_csv, only="not-found")


# ---- summarize ----


def test_summarize_removes_iqr_outlier_and_reports_counts():
    runs = [
        _record(1, 100.0, ttfb_ms=50.0),
        _record(2, 101.0, ttfb_ms=51.0),
        _record(3, 99.0, ttfb_ms=49.0),
        _record(4, 102.0, ttfb_ms=52.0),
        _record(5, 5000.0, ttfb_ms=4000.0),
    ]

    summary = metrics.summarize(runs)["demo"]

    assert summary["n_raw"] == 5
    assert summary["n_kept"] == 4
    assert summary["n_outliers"] == 1
    assert summary["outlier_run_ids"] == [5]
    assert summary["load_ms"] == 100.5
    assert summary["ttfb_ms"] == 50.5
    assert summary["request_count"] == 21


def test_summarize_keeps_small_samples_without_outlier_removal():
    runs = [_record(1, 100.0), _record(2, 500.0), _record(3, 900.0)]

    summary = metrics.summarize(runs)["demo"]

    assert summary["n_raw"] == 3
    assert summary["n_kept"] == 3
    assert summary["n_outliers"] == 0
    assert summary["outlier_run_ids"] == []
    assert summary["load_ms"] == 500.0


def test_summarize_groups_by_site():
    runs = [_record(1, 100.0), {**_record(1, 200.0), "site": "lab-10"}]

    summary = metrics.summarize(runs)

    assert set(summary) == {"demo", "lab-10"}
    assert summary["demo"]["load_ms"] == 100.0
    assert summary["lab-10"]["load_ms"] == 200.0
