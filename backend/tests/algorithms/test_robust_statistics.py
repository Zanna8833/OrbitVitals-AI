"""Descriptive and robust statistics. All inputs are synthetic numbers."""

import math

import pytest

from app.algorithms.robust_statistics import (
    MODIFIED_Z_SCORE_FACTOR,
    POTENTIAL_OUTLIER_CUTOFF,
    describe,
    median_absolute_deviation,
    modified_z_scores,
)
from app.models import BaselineStatistics


def test_published_constants_are_not_altered() -> None:
    # Iglewicz and Hoaglin (1993), as cited next to the constants.
    assert MODIFIED_Z_SCORE_FACTOR == 0.6745
    assert POTENTIAL_OUTLIER_CUTOFF == 3.5


def test_median_absolute_deviation_is_the_median_distance_from_the_median() -> None:
    # Median 3; distances 2, 1, 0, 1, 97; their median is 1.
    assert median_absolute_deviation([1, 2, 3, 4, 100]) == 1


def test_median_absolute_deviation_is_not_rescaled() -> None:
    # Distances from the median 0 are all 10: a rescaled MAD would be 14.826.
    assert median_absolute_deviation([-10, 10]) == 10


def test_median_absolute_deviation_needs_a_value() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        median_absolute_deviation([])


def test_modified_z_scores_follow_the_published_formula() -> None:
    scores = modified_z_scores([1, 2, 3, 4, 100])

    assert scores == pytest.approx([-1.349, -0.6745, 0.0, 0.6745, 65.4265])


def test_modified_z_scores_keep_the_order_of_the_input() -> None:
    assert modified_z_scores([100, 3, 1, 4, 2]) == pytest.approx(
        [65.4265, 0.0, -1.349, 0.6745, -0.6745]
    )


@pytest.mark.parametrize(
    "values",
    [
        [],
        [5.0],
        [5.0, 5.0, 5.0],
        # More than half of the values are identical: the MAD is zero although they vary.
        [5.0, 5.0, 5.0, 5.0, 9.0],
    ],
)
def test_modified_z_scores_are_undefined_without_spread(values: list[float]) -> None:
    assert modified_z_scores(values) is None


def test_describe_reports_every_statistic() -> None:
    statistics = describe([2, 4, 4, 4, 5, 5, 7, 9])

    assert statistics.mean == 5
    assert statistics.standard_deviation == pytest.approx(math.sqrt(32 / 7))  # n - 1 denominator
    assert statistics.median == 4.5
    assert statistics.median_absolute_deviation == 0.5
    assert statistics.minimum == 2
    assert statistics.maximum == 9


def test_describe_does_not_depend_on_the_order_of_the_values() -> None:
    values = [61.5, 58.0, 59.25, 63.0, 57.75, 60.0]

    assert describe(values) == describe(sorted(values)) == describe(values[::-1])


def test_describe_of_a_single_value_has_no_standard_deviation() -> None:
    statistics = describe([58.0])

    assert statistics.standard_deviation is None
    assert statistics.mean == statistics.median == statistics.minimum == statistics.maximum == 58.0
    assert statistics.median_absolute_deviation == 0


def test_describe_of_identical_values_reports_zero_dispersion() -> None:
    statistics = describe([0.1, 0.1, 0.1])

    assert statistics.standard_deviation == 0
    assert statistics.median_absolute_deviation == 0
    assert statistics.mean == 0.1


def test_describe_of_nothing_reports_nothing() -> None:
    assert describe([]) == BaselineStatistics()
    assert all(value is None for value in describe([]).model_dump().values())
