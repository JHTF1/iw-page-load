"""按 site 合并 initcwnd 与 pageload 两份数据。"""

from __future__ import annotations

from typing import Any


def merge(
    initcwnd_rows: list[dict[str, Any]],
    pageload_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """以 site 为键合并，受控实验通过 lab- 前缀识别。

    TODO(C): 合并前两侧都必须通过 schema 校验；不通过的数据不得进入分析。
    """
    raise NotImplementedError("TODO(C): 合并两份数据")
