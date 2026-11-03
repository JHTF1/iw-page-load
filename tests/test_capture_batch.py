"""batch 的单元测试：站点清单、代表轮选择、失败跳过与 CLI 批量模式。"""

from __future__ import annotations

import csv
import importlib

import pytest

from src.common.schema import read_initcwnd_csv


def _batch():
    return importlib.import_module("src.capture.batch")


def sample_result(initcwnd_bytes=1460, confidence="high", retrans_count=0, segment_count=1):
    return {
        "server_ip": "93.184.216.34",
        "ip_version": "4",
        "initcwnd_bytes": initcwnd_bytes,
        "mss_bytes": 1460,
        "initcwnd_mss": round(initcwnd_bytes / 1460, 2),
        "segment_count": segment_count,
        "retrans_count": retrans_count,
        "confidence": confidence,
        "notes": "",
    }


def run_record(initcwnd_bytes, confidence="high", retrans_count=0):
    return {
        "initcwnd_bytes": initcwnd_bytes,
        "confidence": confidence,
        "retrans_count": retrans_count,
        "notes": "",
    }


def write_sites(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["site", "url", "category"])
        for row in rows:
            writer.writerow(row)


def test_read_sites_filters_blank_rows(tmp_path):
    sites_csv = tmp_path / "sites.csv"
    write_sites(
        sites_csv,
        [
            ["a", "https://a.example/", "news"],
            ["", "https://bad.example/", "x"],
            ["b", "https://b.example/", ""],
        ],
    )

    sites = _batch().read_sites(sites_csv)

    assert sites == [
        {"site": "a", "url": "https://a.example/"},
        {"site": "b", "url": "https://b.example/"},
    ]


def test_select_representative_prefers_high_confidence():
    batch = _batch()
    runs = [run_record(1000, "high"), run_record(2000, "medium", retrans_count=1)]

    assert batch.select_representative(runs)["initcwnd_bytes"] == 1000


def test_select_representative_tie_breaks_by_median_then_retrans():
    batch = _batch()

    odd = [run_record(1000), run_record(3000), run_record(2000)]
    assert batch.select_representative(odd)["initcwnd_bytes"] == 2000

    even = [run_record(1000, retrans_count=1), run_record(3000, retrans_count=0)]
    assert batch.select_representative(even)["initcwnd_bytes"] == 3000


def test_capture_sites_writes_one_row_per_site(tmp_path, monkeypatch):
    batch = _batch()
    sites_csv = tmp_path / "sites.csv"
    csv_path = tmp_path / "initcwnd.csv"
    write_sites(
        sites_csv,
        [
            ["a", "https://a.example/", ""],
            ["b", "https://b.example/", ""],
        ],
    )
    results = [
        sample_result(1460, "high", 0),
        sample_result(4380, "medium", 1, segment_count=3),
        sample_result(2920, "high", 0, segment_count=2),
        sample_result(2920, "high", 0, segment_count=2),
    ]
    calls = []
    index = {"value": 0}

    def fake_capture(url, out_pcap, duration_s=None, iface=None):
        calls.append((url, out_pcap))
        return out_pcap

    def fake_measure(pcap_path):
        result = results[index["value"]]
        index["value"] += 1
        return result

    monkeypatch.setattr(batch, "capture_url", fake_capture)
    monkeypatch.setattr(batch, "measure_initcwnd", fake_measure)
    monkeypatch.setattr(batch, "load_settings", lambda: {"capture": {"duration_s": 8, "repeats": 2}})

    written = batch.capture_sites(sites_csv=sites_csv, repeats=2, csv_path=csv_path)

    assert len(calls) == 4
    assert len(written) == 2
    assert written[0]["site"] == "a"
    assert written[0]["initcwnd_bytes"] == 1460
    assert "2 轮首飞字节: 1460/4380" in written[0]["notes"]
    assert written[1]["initcwnd_bytes"] == 2920

    rows = read_initcwnd_csv(csv_path)
    assert [row["site"] for row in rows] == ["a", "b"]
    assert rows[0]["confidence"] == "high"
    assert "2 轮首飞字节" in rows[0]["notes"]


def test_capture_sites_skips_failed_site_and_continues(tmp_path, monkeypatch):
    batch = _batch()
    sites_csv = tmp_path / "sites.csv"
    csv_path = tmp_path / "initcwnd.csv"
    write_sites(
        sites_csv,
        [
            ["a", "https://a.example/", ""],
            ["b", "https://b.example/", ""],
        ],
    )

    def fake_capture(url, out_pcap, duration_s=None, iface=None):
        if "a.example" in url:
            raise RuntimeError("connection refused")
        return out_pcap

    monkeypatch.setattr(batch, "capture_url", fake_capture)
    monkeypatch.setattr(batch, "measure_initcwnd", lambda path: sample_result(2920, segment_count=2))
    monkeypatch.setattr(batch, "load_settings", lambda: {"capture": {"duration_s": 8, "repeats": 2}})

    written = batch.capture_sites(sites_csv=sites_csv, repeats=2, csv_path=csv_path)

    assert [record["site"] for record in written] == ["b"]
    assert [row["site"] for row in read_initcwnd_csv(csv_path)] == ["b"]


def test_capture_sites_only_filters_sites(tmp_path, monkeypatch):
    batch = _batch()
    sites_csv = tmp_path / "sites.csv"
    csv_path = tmp_path / "initcwnd.csv"
    write_sites(
        sites_csv,
        [
            ["a", "https://a.example/", ""],
            ["b", "https://b.example/", ""],
        ],
    )
    calls = []

    def fake_capture(url, out_pcap, duration_s=None, iface=None):
        calls.append(url)
        return out_pcap

    monkeypatch.setattr(batch, "capture_url", fake_capture)
    monkeypatch.setattr(batch, "measure_initcwnd", lambda path: sample_result(2920, segment_count=2))
    monkeypatch.setattr(batch, "load_settings", lambda: {"capture": {"duration_s": 8, "repeats": 2}})

    written = batch.capture_sites(sites_csv=sites_csv, repeats=1, only="b", csv_path=csv_path)

    assert calls == ["https://b.example/"]
    assert [record["site"] for record in written] == ["b"]


def test_capture_sites_rejects_unknown_only(tmp_path, monkeypatch):
    batch = _batch()
    sites_csv = tmp_path / "sites.csv"
    write_sites(sites_csv, [["a", "https://a.example/", ""]])

    monkeypatch.setattr(batch, "load_settings", lambda: {"capture": {"duration_s": 8, "repeats": 2}})

    with pytest.raises(ValueError, match="missing"):
        batch.capture_sites(sites_csv=sites_csv, only="missing", csv_path=tmp_path / "initcwnd.csv")


def test_cli_batch_mode_calls_capture_sites(tmp_path, monkeypatch):
    cli = importlib.import_module("src.capture.__main__")
    calls = []

    def fake_capture_sites(sites_csv, **kwargs):
        calls.append((sites_csv, kwargs))
        return []

    monkeypatch.setattr(cli, "capture_sites", fake_capture_sites)

    exit_code = cli.main(
        [
            "--sites", str(tmp_path / "sites.csv"),
            "--only", "a",
            "--repeats", "1",
            "--csv", str(tmp_path / "initcwnd.csv"),
        ]
    )

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0][1]["only"] == "a"
    assert calls[0][1]["repeats"] == 1
