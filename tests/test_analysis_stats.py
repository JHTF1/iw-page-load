from __future__ import annotations

import pytest

from src.analysis.stats import (
    filter_outliers,
    group_compare,
    iqr_bounds,
    mann_whitney_u,
    partial_spearman,
    spearman,
)


def test_spearman_perfect_monotonic():
    result = spearman([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])

    assert result["rho"] == pytest.approx(1.0)
    assert result["p_value"] == pytest.approx(0.0, abs=1e-9)
    assert result["n"] == 5
    assert result["effect_size"] == pytest.approx(1.0)


def test_spearman_reverse_monotonic():
    result = spearman([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])

    assert result["rho"] == pytest.approx(-1.0)
    assert result["p_value"] == pytest.approx(0.0, abs=1e-9)


def test_spearman_requires_three_pairs():
    result = spearman([1, 2], [2, 4])

    assert result["rho"] is None
    assert result["n"] == 2


def test_spearman_constant_series_returns_none():
    result = spearman([1, 1, 1, 1], [1, 2, 3, 4])

    assert result["rho"] is None
    assert result["p_value"] is None


def test_partial_spearman_removes_common_control_variable():
    x = [3, 1, 6, 2, 5, 4]
    control = [1, 2, 3, 4, 5, 6]
    y = [1.2, 2.8, 3.0, 2.5, 5.0, 6.1]

    result = partial_spearman(x, y, control)

    assert result["method"] == "partial_spearman"
    assert result["rho"] is not None
    assert abs(result["rho"]) < 0.6
    assert result["p_value"] > 0.05
    assert result["df"] == len(x) - 3


def test_mann_whitney_separated_groups():
    result = mann_whitney_u([1, 2, 3], [4, 5, 6])

    assert result["u"] == pytest.approx(0.0)
    assert result["p_value"] < 0.1
    assert result["effect_size"] == pytest.approx(-1.0)


def test_group_compare_pairs_and_bonferroni():
    result = group_compare(
        {
            "lab-2": [1400, 1450, 1500],
            "lab-4": [850, 900, 950],
            "lab-10": [550, 600, 650],
            "lab-20": [420, 450, 480],
        }
    )

    assert len(result["comparisons"]) == 6
    assert all(item["p_adjusted"] >= item["p_value"] for item in result["comparisons"])
    assert result["groups"]["lab-2"]["n"] == 3
    assert result["groups"]["lab-2"]["median"] == pytest.approx(1450.0)


def test_filter_outliers_removes_extreme_value():
    kept, removed = filter_outliers([100.0, 101.0, 102.0, 103.0, 10_000.0], key=lambda value: value)

    assert removed == [10_000.0]
    assert kept == [100.0, 101.0, 102.0, 103.0]


def test_iqr_bounds_needs_enough_samples():
    assert iqr_bounds([1.0, 2.0, 3.0]) is None
    low, high = iqr_bounds([1.0, 2.0, 3.0, 4.0])
    assert low < 1.0
    assert high > 4.0
