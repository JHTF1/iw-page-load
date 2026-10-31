from __future__ import annotations

import pytest

from src.analysis.merge import aggregate_pageload, merge, site_group


def make_initcwnd(site: str, mss_count: int) -> dict:
    return {
        "site": site,
        "url": "https://example.com/",
        "server_ip": "127.0.0.1",
        "ip_version": "4",
        "timestamp_utc": "2026-10-31T02:00:00Z",
        "initcwnd_bytes": mss_count * 1460,
        "mss_bytes": 1460,
        "initcwnd_mss": float(mss_count),
        "segment_count": mss_count,
        "retrans_count": 0,
        "method": "lab" if site.startswith("lab-") else "passive",
        "confidence": "high",
        "notes": "",
    }


def make_pageload(site: str, run_id: int, load_ms: float, ttfb_ms: float, transfer_bytes: int = 1_200_000) -> dict:
    return {
        "site": site,
        "url": "https://example.com/",
        "run_id": run_id,
        "timestamp_utc": "2026-10-31T02:00:00Z",
        "dns_ms": 10.0,
        "tcp_ms": 20.0,
        "tls_ms": 30.0,
        "ttfb_ms": ttfb_ms,
        "dom_content_loaded_ms": load_ms * 0.7,
        "load_ms": load_ms,
        "request_count": 40,
        "transfer_bytes": transfer_bytes,
        "quic_disabled": True,
        "cache_mode": "cold",
        "network_env": "有线 · 测试",
        "notes": "",
    }


def test_site_group_uses_lab_prefix():
    assert site_group("lab-10") == "lab"
    assert site_group("baidu") == "real"


def test_aggregate_uses_median_and_drops_iqr_outlier():
    rows = [
        make_pageload("baidu", index + 1, load, load / 5)
        for index, load in enumerate([100.0, 101.0, 102.0, 103.0, 10_000.0])
    ]

    aggregated = aggregate_pageload(rows)

    assert len(aggregated) == 1
    record = aggregated[0]
    assert record["runs_total"] == 5
    assert record["runs_used"] == 4
    assert record["load_ms"] == pytest.approx(101.5)
    assert len(record["load_samples"]) == 4


def test_aggregate_keeps_all_runs_when_fewer_than_four():
    rows = [make_pageload("jd", 1, 100.0, 20.0), make_pageload("jd", 2, 200.0, 30.0)]

    aggregated = aggregate_pageload(rows)

    assert aggregated[0]["runs_used"] == 2
    assert aggregated[0]["load_ms"] == pytest.approx(150.0)


def test_merge_joins_by_site_and_classifies_groups():
    initcwnd_rows = [make_initcwnd("baidu", 10), make_initcwnd("lab-10", 10)]
    pageload_rows = [
        make_pageload("baidu", 1, 900.0, 100.0),
        make_pageload("baidu", 2, 950.0, 110.0),
        make_pageload("lab-10", 1, 500.0, 50.0),
    ]

    merged = merge(initcwnd_rows, pageload_rows)

    assert [row["site"] for row in merged] == ["baidu", "lab-10"]
    assert merged[0]["group"] == "real"
    assert merged[1]["group"] == "lab"
    assert merged[0]["initcwnd_mss"] == 10.0
    assert merged[0]["load_ms"] == pytest.approx(925.0)
    assert merged[0]["runs_used"] == 2
    assert merged[1]["load_samples"] == [500.0]


def test_merge_excludes_sites_without_counterpart():
    initcwnd_rows = [make_initcwnd("baidu", 10), make_initcwnd("github", 16)]
    pageload_rows = [make_pageload("baidu", 1, 900.0, 100.0)]

    merged = merge(initcwnd_rows, pageload_rows)

    assert [row["site"] for row in merged] == ["baidu"]


def test_merge_rejects_invalid_pageload_rows():
    initcwnd_rows = [make_initcwnd("baidu", 10)]
    pageload_rows = [make_pageload("baidu", 1, 900.0, 100.0)]
    pageload_rows[0]["quic_disabled"] = False

    with pytest.raises(ValueError, match="quic_disabled"):
        merge(initcwnd_rows, pageload_rows)
