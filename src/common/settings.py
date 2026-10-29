"""读取 config/settings.yaml。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import SETTINGS_YAML


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = Path(path) if path else SETTINGS_YAML
    with settings_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"配置文件顶层必须是映射: {settings_path}")
    return data
