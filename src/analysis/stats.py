"""统计检验。

方法选择（TODO(C)）：
- 网络延迟通常非正态，相关性用 Spearman 秩相关
- 页面总字节是混杂因素，用偏相关控制
- 分组比较用 Mann-Whitney U 检验，并报告 p 值与效应量
"""

from __future__ import annotations

from typing import Any, Sequence


def spearman(x: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    """返回 rho、p 值与样本量。TODO(C)。"""
    raise NotImplementedError("TODO(C): Spearman 相关")


def partial_spearman(
    x: Sequence[float],
    y: Sequence[float],
    control: Sequence[float],
) -> dict[str, Any]:
    """控制 control 变量后的偏 Spearman 相关。TODO(C)。"""
    raise NotImplementedError("TODO(C): 偏相关")


def group_compare(groups: dict[str, Sequence[float]]) -> dict[str, Any]:
    """多组比较，返回检验方法与各组统计量。TODO(C)。"""
    raise NotImplementedError("TODO(C): 分组检验")
