"""项目路径常量。所有模块统一从这里取路径，禁止手写相对路径。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DATA_RAW = DATA_DIR / "raw"
DATA_PROCESSED = DATA_DIR / "processed"
RESULTS_DIR = ROOT / "results"
RESULTS_FIGURES = RESULTS_DIR / "figures"
RESULTS_TABLES = RESULTS_DIR / "tables"
DOCS_DIR = ROOT / "docs"

SITES_CSV = CONFIG_DIR / "sites.csv"
SETTINGS_YAML = CONFIG_DIR / "settings.yaml"

INITCWND_CSV = DATA_PROCESSED / "initcwnd.csv"
PAGELOAD_CSV = DATA_PROCESSED / "pageload.csv"


def ensure_dirs() -> list[Path]:
    """创建运行期需要的目录，返回已确认存在的目录列表。"""
    dirs = [DATA_RAW, DATA_PROCESSED, RESULTS_FIGURES, RESULTS_TABLES]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
    return dirs
