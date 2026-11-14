"""Descriptive and robust statistics shared by the cross-domain algorithms.

Pure functions over finite numbers. They describe data and do not judge it: nothing in
this module is a clinical threshold or a reference range.
"""

import statistics
from collections.abc import Sequence

from app.models import BaselineStatistics

# Modified z-score: M_i = 0.6745 * (x_i - median) / MAD, where MAD is the median absolute
# deviation. The factor 0.6745 is the 0.75 quantile of the standard normal distribution;
# it puts M_i on the scale of a standard deviation when the data are normally distributed.
# Source: Iglewicz B, Hoaglin DC. How to Detect and Handle Outliers. ASQC Basic References
# in Quality Control, vol. 16. ASQC Quality Press, 1993. Quoted in the NIST/SEMATECH
# e-Handbook of Statistical Methods, section 1.3.5.17, "Detection of Outliers".
MODIFIED_Z_SCORE_FACTOR = 0.6745

# Absolute modified z-score above which the same source labels a value a *potential*
# outlier. It is a statistical convention, not a clinical threshold.
POTENTIAL_OUTLIER_CUTOFF = 3.5


def median_absolute_deviation(values: Sequence[float]) -> float:
    """Return the median of the absolute deviations from the median.

    The value is not rescaled: it is the plain MAD, in the unit of `values`.
    """
    if not values:
        raise ValueError("median_absolute_deviation needs at least one value")
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def modified_z_scores(values: Sequence[float]) -> list[float] | None:
    """Return the modified z-score of every value, in the order of `values`.

    Return `None` when the score is undefined: there is no value, or the median
    absolute deviation is zero. The caller must then treat the values as not screened
    instead of dividing by zero.
    """
    if not values:
        return None
    center = statistics.median(values)
    spread = statistics.median(abs(value - center) for value in values)
    if spread == 0:
        return None
    return [MODIFIED_Z_SCORE_FACTOR * (value - center) / spread for value in values]


def describe(values: Sequence[float]) -> BaselineStatistics:
    """Return the descriptive statistics of `values`.

    - `standard_deviation` is the sample standard deviation (n - 1 denominator). It is
      null for fewer than two values, where it is undefined.
    - `median_absolute_deviation` is not rescaled.
    - Every statistic is null when there is no value.

    The result does not depend on the order of `values`.
    """
    if not values:
        return BaselineStatistics()
    ordered = sorted(values)
    return BaselineStatistics(
        # `statistics.mean` and `statistics.stdev` use exact rational arithmetic: the mean
        # of identical values is that value, and their standard deviation is exactly zero.
        mean=statistics.mean(ordered),
        standard_deviation=statistics.stdev(ordered) if len(ordered) > 1 else None,
        median=statistics.median(ordered),
        median_absolute_deviation=median_absolute_deviation(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
    )
