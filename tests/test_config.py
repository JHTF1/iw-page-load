from __future__ import annotations

import csv

from src.common.paths import SITES_CSV, ensure_dirs
from src.common.settings import load_settings


def test_ensure_dirs_creates_directories():
    dirs = ensure_dirs()
    assert dirs
    assert all(directory.is_dir() for directory in dirs)


def test_settings_has_expected_sections():
    settings = load_settings()
    for section in ("project", "sites", "capture", "measure", "lab", "analysis"):
        assert section in settings

    assert settings["lab"]["initcwnd_values"] == [2, 4, 10, 20]
    assert settings["measure"]["disable_quic"] is True
    assert settings["measure"]["cache_mode"] == "cold"


def test_sites_csv_is_well_formed():
    with SITES_CSV.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) >= 20
    for row in rows:
        assert row["site"]
        assert row["url"].startswith("http")
        assert row["region"]
        assert row["category"]

    sites = [row["site"] for row in rows]
    assert len(sites) == len(set(sites)), "site 列不能重复"
