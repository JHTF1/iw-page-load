"""统计检验。

方法选择（见 docs/项目总体设计.md 第 11.4 节）：
- 网络延迟通常非正态，相关性用 Spearman 秩相关；
- 页面总字节是混杂因素，用偏相关控制；
- 分组比较用 Mann-Whitney U 检验，并报告 p 值与效应量（秩双列相关）。
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Callable, Sequence


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean(values: Sequence[Any]) -> list[float]:
    return [number for value in values if (number := _to_float(value)) is not None]


def _paired(x: Sequence[Any], y: Sequence[Any]) -> tuple[list[float], list[float]]:
    pairs = [(_to_float(a), _to_float(b)) for a, b in zip(x, y)]
    return ([a for a, b in pairs if a is not None and b is not None],
            [b for a, b in pairs if a is not None and b is not None])


def quantile(values: Sequence[float], q: float) -> float:
    """线性插值分位数，与 numpy 默认口径一致。"""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("空序列没有分位数")
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def describe(values: Sequence[float]) -> dict[str, float | int | None]:
    cleaned = _clean(values)
    if not cleaned:
        return {"n": 0, "median": None, "q1": None, "q3": None, "min": None, "max": None}
    return {
        "n": len(cleaned),
        "median": quantile(cleaned, 0.5),
        "q1": quantile(cleaned, 0.25),
        "q3": quantile(cleaned, 0.75),
        "min": float(min(cleaned)),
        "max": float(max(cleaned)),
    }


def iqr_bounds(values: Sequence[float]) -> tuple[float, float] | None:
    """四分位距上下界：Q1 - 1.5×IQR 到 Q3 + 1.5×IQR。"""
    cleaned = _clean(values)
    if len(cleaned) < 4:
        return None
    q1 = quantile(cleaned, 0.25)
    q3 = quantile(cleaned, 0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def filter_outliers(
    items: Sequence[Any],
    key: Callable[[Any], Any],
) -> tuple[list[Any], list[Any]]:
    """按 key 提取数值并按 IQR 规则剔除异常项，返回 (保留, 剔除)。"""
    values = [key(item) for item in items]
    bounds = iqr_bounds([value for value in values if _to_float(value) is not None])
    if bounds is None:
        return list(items), []
    low, high = bounds
    kept: list[Any] = []
    removed: list[Any] = []
    for item, value in zip(items, values):
        number = _to_float(value)
        if number is None or low <= number <= high:
            kept.append(item)
        else:
            removed.append(item)
    return kept, removed


def _rank(values: Sequence[float]) -> list[float]:
    """平均秩，处理并列值。"""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index
        while end + 1 < len(order) and values[order[end + 1]] == values[order[index]]:
            end += 1
        average = (index + 1 + end + 1) / 2.0
        for offset in range(index, end + 1):
            ranks[order[offset]] = average
        index = end + 1
    return ranks


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = len(x)
    if n < 2:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    sxx = sum((value - mean_x) ** 2 for value in x)
    syy = sum((value - mean_y) ** 2 for value in y)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    return sxy / math.sqrt(sxx * syy)


def _betacf(a: float, b: float, x: float) -> float:
    """正则化不完全贝塔函数的连分式部分（Numerical Recipes）。"""
    max_iter = 200
    epsilon = 3.0e-12
    tiny = 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """正则化不完全贝塔函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - log_beta) / a
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x)
    front = math.exp(b * math.log(1.0 - x) + a * math.log(x) - log_beta) / b
    return 1.0 - front * _betacf(b, a, 1.0 - x)


def _t_p_value(rho: float | None, df: float) -> float | None:
    """相关系数的双尾 p 值：t = r√(df/(1-r²))，p = I_{df/(df+t²)}(df/2, 1/2)。"""
    if rho is None or df <= 0:
        return None
    if abs(rho) >= 1.0:
        return 0.0
    t_squared = df * rho * rho / (1.0 - rho * rho)
    p_value = _betainc(df / 2.0, 0.5, df / (df + t_squared))
    return min(1.0, max(0.0, p_value))


def spearman(x: Sequence[Any], y: Sequence[Any]) -> dict[str, Any]:
    """Spearman 秩相关，返回 rho、p 值与样本量；效应量即 rho。"""
    x_values, y_values = _paired(x, y)
    n = len(x_values)
    if n < 3:
        return {"method": "spearman", "rho": None, "p_value": None, "n": n, "effect_size": None}
    rho = _pearson(_rank(x_values), _rank(y_values))
    return {
        "method": "spearman",
        "rho": rho,
        "p_value": _t_p_value(rho, n - 2),
        "n": n,
        "df": n - 2,
        "effect_size": rho,
    }


def _residual(values: Sequence[float], control: Sequence[float]) -> list[float] | None:
    mean_v = sum(values) / len(values)
    mean_c = sum(control) / len(control)
    var_c = sum((c - mean_c) ** 2 for c in control)
    if var_c <= 0:
        return None
    cov = sum((v - mean_v) * (c - mean_c) for v, c in zip(values, control))
    slope = cov / var_c
    return [(v - mean_v) - slope * (c - mean_c) for v, c in zip(values, control)]


def partial_spearman(
    x: Sequence[Any],
    y: Sequence[Any],
    control: Sequence[Any],
) -> dict[str, Any]:
    """控制 control 变量后的偏 Spearman 相关（对秩做线性残差化）。"""
    triples = [
        (_to_float(a), _to_float(b), _to_float(c)) for a, b, c in zip(x, y, control)
    ]
    usable = [triple for triple in triples if None not in triple]
    n = len(usable)
    if n < 4:
        return {"method": "partial_spearman", "rho": None, "p_value": None, "n": n, "effect_size": None}
    x_values = _rank([triple[0] for triple in usable])  # type: ignore[arg-type]
    y_values = _rank([triple[1] for triple in usable])  # type: ignore[arg-type]
    control_values = _rank([triple[2] for triple in usable])  # type: ignore[arg-type]
    residual_x = _residual(x_values, control_values)
    residual_y = _residual(y_values, control_values)
    rho = None if residual_x is None or residual_y is None else _pearson(residual_x, residual_y)
    return {
        "method": "partial_spearman",
        "rho": rho,
        "p_value": _t_p_value(rho, n - 3),
        "n": n,
        "df": n - 3,
        "effect_size": rho,
    }


def mann_whitney_u(group_a: Sequence[Any], group_b: Sequence[Any]) -> dict[str, Any]:
    """Mann-Whitney U 检验（正态近似 + 并列校正 + 连续性校正）。"""
    a = _clean(group_a)
    b = _clean(group_b)
    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        return {
            "method": "mann-whitney-u",
            "u": None,
            "p_value": None,
            "effect_size": None,
            "n_a": n_a,
            "n_b": n_b,
        }

    u_a = sum(
        1.0 if value_b < value_a else 0.5 if value_b == value_a else 0.0
        for value_a in a
        for value_b in b
    )
    n = n_a + n_b
    ties = 0.0
    for value in set(a + b):
        count = a.count(value) + b.count(value)
        ties += count**3 - count
    variance = n_a * n_b / 12.0 * ((n + 1) - ties / (n * (n - 1)))
    mean = n_a * n_b / 2.0
    if variance <= 0:
        p_value = 1.0 if u_a == mean else 0.0
    else:
        correction = 0.5 if u_a > mean else -0.5 if u_a < mean else 0.0
        z_value = (u_a - mean - correction) / math.sqrt(variance)
        p_value = min(1.0, max(0.0, math.erfc(abs(z_value) / math.sqrt(2.0))))
    effect_size = 2.0 * u_a / (n_a * n_b) - 1.0
    return {
        "method": "mann-whitney-u",
        "u": u_a,
        "p_value": p_value,
        "effect_size": effect_size,
        "n_a": n_a,
        "n_b": n_b,
    }


def group_compare(groups: dict[str, Sequence[Any]]) -> dict[str, Any]:
    """分组比较：两组用 Mann-Whitney U，多组做两两比较并给出 Bonferroni 校正 p 值。"""
    cleaned = {name: _clean(values) for name, values in groups.items()}
    nonempty = {name: values for name, values in cleaned.items() if values}
    summary = {name: describe(values) for name, values in cleaned.items()}
    comparisons: list[dict[str, Any]] = []
    for name_a, name_b in combinations(nonempty, 2):
        result = mann_whitney_u(nonempty[name_a], nonempty[name_b])
        result.update({"group_a": name_a, "group_b": name_b})
        comparisons.append(result)

    pairs = len(comparisons)
    for result in comparisons:
        p_value = result["p_value"]
        result["p_adjusted"] = None if p_value is None else min(1.0, p_value * pairs)

    return {
        "method": "mann-whitney-u" if pairs <= 1 else "mann-whitney-u（两两比较）",
        "groups": summary,
        "comparisons": comparisons,
    }
