"""records 的单元测试：记录组装与 initcwnd.csv 的 upsert。"""

from __future__ import annotations

import importlib
import re

import pytest

from src.common.schema import read_initcwnd_csv


def _records():
    return importlib.import_module("src.capture.records")


def sample_result(**overrides):
    data = {
        "server_ip": "93.184.216.34",
        "ip_version": "4",
        "initcwnd_bytes": 14600,
        "mss_bytes": 1460,
        "initcwnd_mss": 10.0,
        "segment_count": 10,
        "retrans_count": 0,
        "confidence": "high",
        "notes": "",
    }
    data.update(overrides)
    return data


def test_build_record_maps_measurement_fields():
    record = _records().build_record(
        sample_result(),
        "baidu",
        "https://www.baidu.com/",
        "2026-11-02T01:00:00Z",
    )

    assert record["site"] == "baidu"
    assert record["url"] == "https://www.baidu.com/"
    assert record["server_ip"] == "93.184.216.34"
    assert record["ip_version"] == "4"
    assert record["timestamp_utc"] == "2026-11-02T01:00:00Z"
    assert record["initcwnd_bytes"] == 14600
    assert record["mss_bytes"] == 1460
    assert record["initcwnd_mss"] == 10.0
    assert record["segment_count"] == 10
    assert record["retrans_count"] == 0
    assert record["method"] == "passive"
    assert record["confidence"] == "high"


def test_build_record_marks_lab_site():
    record = _records().build_record(
        sample_result(),
        "lab-10",
        "http://127.0.0.1:8080/",
        "2026-11-03T01:00:00Z",
    )

    assert record["method"] == "lab"


def test_build_record_defaults_missing_notes():
    record = _records().build_record(
        sample_result(notes=None),
        "baidu",
        "https://www.baidu.com/",
        "2026-11-02T01:00:00Z",
    )

    assert record["notes"] == ""


def test_utc_now_iso_matches_contract():
    timestamp = _records().utc_now_iso()

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp)


def test_upsert_appends_new_site(tmp_path):
    records = _records()
    path = tmp_path / "initcwnd.csv"
    record = records.build_record(
        sample_result(), "baidu", "https://www.baidu.com/", "2026-11-02T01:00:00Z"
    )

    written = records.upsert_record(record, path)

    assert written == path
    rows = read_initcwnd_csv(path)
    assert len(rows) == 1
    assert rows[0]["site"] == "baidu"
    assert rows[0]["initcwnd_bytes"] == 14600


def test_upsert_replaces_same_site_and_preserves_others(tmp_path):
    records = _records()
    path = tmp_path / "initcwnd.csv"
    first = records.build_record(
        sample_result(initcwnd_bytes=1460, initcwnd_mss=1.0, segment_count=1),
        "a",
        "https://a.example/",
        "2026-11-02T01:00:00Z",
    )
    other = records.build_record(
        sample_result(initcwnd_bytes=2920, initcwnd_mss=2.0, segment_count=2),
        "b",
        "https://b.example/",
        "2026-11-02T01:01:00Z",
    )
    replacement = records.build_record(
        sample_result(initcwnd_bytes=4380, initcwnd_mss=3.0, segment_count=3),
        "a",
        "https://a.example/",
        "2026-11-02T01:02:00Z",
    )

    records.upsert_record(first, path)
    records.upsert_record(other, path)
    records.upsert_record(replacement, path)

    rows = read_initcwnd_csv(path)
    assert [row["site"] for row in rows] == ["a", "b"]
    assert rows[0]["initcwnd_bytes"] == 4380
    assert rows[1]["initcwnd_bytes"] == 2920


def test_upsert_rejects_invalid_record_without_writing(tmp_path):
    records = _records()
    path = tmp_path / "initcwnd.csv"
    record = records.build_record(
        sample_result(mss_bytes=0, initcwnd_mss=0.0),
        "baidu",
        "https://www.baidu.com/",
        "2026-11-02T01:00:00Z",
    )

    with pytest.raises(ValueError, match="schema"):
        records.upsert_record(record, path)

    assert not path.exists()


def test_cli_single_site_writes_csv(tmp_path, monkeypatch):
    cli = importlib.import_module("src.capture.__main__")
    pcap_path = tmp_path / "baidu.pcap"
    csv_path = tmp_path / "initcwnd.csv"

    monkeypatch.setattr(cli, "capture_url", lambda *args, **kwargs: pcap_path)
    monkeypatch.setattr(cli, "measure_initcwnd", lambda path: sample_result())

    exit_code = cli.main(
        [
            "--site", "baidu",
            "--url", "https://www.baidu.com/",
            "--out", str(pcap_path),
            "--csv", str(csv_path),
        ]
    )

    assert exit_code == 0
    rows = read_initcwnd_csv(csv_path)
    assert len(rows) == 1
    assert rows[0]["site"] == "baidu"
    assert rows[0]["url"] == "https://www.baidu.com/"
    assert rows[0]["method"] == "passive"
