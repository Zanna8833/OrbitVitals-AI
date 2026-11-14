"""Personal Baseline Engine.

Builds the `PersonalBaseline` contract: descriptive statistics of one metric of one crew
member within one mission phase. A baseline is personal and phase-aware: it is computed
from the crew member's own measurements taken during that phase, never from population
values and never across phases.

How a baseline is built:

1. Every measurement is assessed by the Data Quality Engine. Only measurements whose
   quality status is admitted (by default `acceptable` alone) enter the baseline.
2. A measurement belongs to the mission phase that contains its `measured_at`. Phase
   periods include their start and exclude their end. Measurements taken at or after
   `computed_at` are never used.
3. Potential statistical outliers are identified with the modified z-score. By default
   they are counted and kept: an unusual value is not evidence of an error, and the
   median and the median absolute deviation are robust to it. They can be excluded by
   configuration.
4. The statistics are the mean, the sample standard deviation, the median, the median
   absolute deviation, the minimum and the maximum of the values used.
5. The status says how far the baseline can be relied upon:
   - `insufficient_data`: fewer values than `minimum_samples`. No statistic is reported.
   - `established`: the configured criteria are met. None is configured by default,
     because no sourced criterion exists in this repository.
   - `provisional`: every other case, including a baseline whose values are all
     identical, which says nothing about variability.

A baseline is a statistical description. It is not a reference range, and a deviation
from it is not a diagnosis. Reasons and counts are reported in `data_quality.notes`.

Every function is pure and deterministic: `computed_at` is an argument, the result does
not depend on the order of the input, and `baseline_id` is derived from the content.
"""

import math
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise

from app.algorithms.data_quality import (
    DataQualityConfig,
    Period,
    as_utc,
    assess_measurements,
    format_duration,
    summarize_series,
)
from app.algorithms.robust_statistics import (
    POTENTIAL_OUTLIER_CUTOFF,
    describe,
    modified_z_scores,
)
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    BaselineStatistics,
    BaselineStatus,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityStatus,
)

ALGORITHM = AlgorithmInfo(name="personal_baseline", version="0.1.0")

# Namespace of the identifiers derived from the content of a baseline.
_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "orbitvitals:personal_baseline")

# The sample standard deviation divides by n - 1, so it needs two values. This is an
# arithmetic requirement, not a validated sample size.
_ARITHMETIC_MINIMUM_SAMPLES = 2

_ADMISSIBLE_QUALITY = frozenset({QualityStatus.ACCEPTABLE, QualityStatus.DEGRADED})


class OutlierHandling(StrEnum):
    """What to do with values labelled potential statistical outliers."""

    REPORT = "report"  # Keep them in the statistics and report how many there are.
    EXCLUDE = "exclude"  # Leave them out of the statistics and report how many there were.


@dataclass(frozen=True)
class BaselineConfig:
    """Settings of the Personal Baseline Engine. Nothing here is a clinical threshold.

    - `quality`: settings of the Data Quality Engine applied to the reference data.
    - `admitted_quality`: quality statuses a measurement may have to enter a baseline.
      `acceptable` alone by default; `degraded` can be added.
    - `minimum_samples`: values needed to report statistics. The default, 2, is the
      smallest count for which a standard deviation exists.
    - `established_min_samples`, `established_min_span`: criteria for the `established`
      status, as a number of values and as the time between the first and the last value
      used. Both are unset by default: this repository holds no sourced criterion, so
      the engine never labels a baseline `established` until the team configures one and
      documents where it comes from.
    - `outlier_cutoff`: absolute modified z-score above which a value is a potential
      outlier. The default is the value recommended by Iglewicz and Hoaglin (1993); see
      `app.algorithms.robust_statistics`. `None` disables the screening.
    - `outlier_handling`: keep and report potential outliers (default), or exclude them.
    """

    quality: DataQualityConfig = field(default_factory=DataQualityConfig)
    admitted_quality: frozenset[QualityStatus] = frozenset({QualityStatus.ACCEPTABLE})
    minimum_samples: int = _ARITHMETIC_MINIMUM_SAMPLES
    established_min_samples: int | None = None
    established_min_span: timedelta | None = None
    outlier_cutoff: float | None = POTENTIAL_OUTLIER_CUTOFF
    outlier_handling: OutlierHandling = OutlierHandling.REPORT

    def __post_init__(self) -> None:
        # Accept plain strings and any collection, so that a setting read from a file
        # cannot be silently ignored by an identity comparison.
        object.__setattr__(self, "outlier_handling", OutlierHandling(self.outlier_handling))
        object.__setattr__(
            self,
            "admitted_quality",
            frozenset(QualityStatus(status) for status in self.admitted_quality),
        )
        if not self.admitted_quality or not self.admitted_quality <= _ADMISSIBLE_QUALITY:
            raise ValueError("admitted_quality must be a non-empty subset of acceptable, degraded")
        if self.minimum_samples < _ARITHMETIC_MINIMUM_SAMPLES:
            raise ValueError(f"minimum_samples must be at least {_ARITHMETIC_MINIMUM_SAMPLES}")
        if (
            self.established_min_samples is not None
            and self.established_min_samples < self.minimum_samples
        ):
            raise ValueError("established_min_samples must not be lower than minimum_samples")
        if self.established_min_span is not None and self.established_min_span <= timedelta(0):
            raise ValueError("established_min_span must be positive")
        if self.outlier_cutoff is not None and not (
            math.isfinite(self.outlier_cutoff) and self.outlier_cutoff > 0
        ):
            raise ValueError("outlier_cutoff must be a positive number")


def build_baseline(
    measurements: Sequence[PhysiologicalMeasurement],
    mission_phases: Sequence[MissionPhase],
    *,
    crew_member_id: str,
    metric: MetricType,
    mission_phase: MissionPhaseType,
    computed_at: datetime,
    config: BaselineConfig | None = None,
    reference_start: datetime | None = None,
    reference_end: datetime | None = None,
) -> PersonalBaseline | None:
    """Build the baseline of one metric of one crew member for one mission phase.

    `measurements` is the whole batch available: the records of the series are selected
    here, after every record has been assessed in its context. `mission_phases` is the
    timeline of one mission.

    The reference window is the part of the phase that lies before `computed_at`. It
    can be narrowed to `[reference_start, reference_end)`.

    Return `None` when the timeline has no entry of that phase inside the reference
    window: without a window, no baseline can be described. A phase without usable
    measurements still returns a baseline, with the status `insufficient_data`.
    """
    config = config or BaselineConfig()
    computed_at = as_utc(computed_at, "computed_at")
    periods = _reference_periods(mission_phases, computed_at, reference_start, reference_end)
    if mission_phase not in periods:
        return None

    assessed = assess_measurements(measurements, assessed_at=computed_at, config=config.quality)
    candidates = [m for m in assessed if m.crew_member_id == crew_member_id and m.metric == metric]
    return _build(
        candidates,
        periods[mission_phase],
        crew_member_id,
        metric,
        mission_phase,
        computed_at,
        config,
    )


def build_baselines(
    measurements: Sequence[PhysiologicalMeasurement],
    mission_phases: Sequence[MissionPhase],
    *,
    computed_at: datetime,
    config: BaselineConfig | None = None,
    crew_member_ids: Sequence[str] | None = None,
    metrics: Sequence[MetricType] | None = None,
    reference_start: datetime | None = None,
    reference_end: datetime | None = None,
) -> list[PersonalBaseline]:
    """Build one baseline per crew member, metric and mission phase.

    Covers every phase of the timeline that has a reference window, in chronological
    order, for:

    - `crew_member_ids`, or the crew members found in `measurements` when omitted;
    - `metrics`, or the metrics found in the measurements of each crew member when
      omitted.

    A combination without usable measurements is not skipped: it yields a baseline with
    the status `insufficient_data`, so that missing observations stay visible.

    The result is ordered by crew member, then by metric in catalog order, then by phase.
    """
    config = config or BaselineConfig()
    computed_at = as_utc(computed_at, "computed_at")
    periods = _reference_periods(mission_phases, computed_at, reference_start, reference_end)
    assessed = assess_measurements(measurements, assessed_at=computed_at, config=config.quality)

    by_series: dict[tuple[str, MetricType], list[PhysiologicalMeasurement]] = defaultdict(list)
    for measurement in assessed:
        by_series[(measurement.crew_member_id, measurement.metric)].append(measurement)

    if crew_member_ids is None:
        crew_member_ids = {crew_member_id for crew_member_id, _ in by_series}

    baselines = []
    for crew_member_id in sorted(set(crew_member_ids)):
        wanted = {m for c, m in by_series if c == crew_member_id} if metrics is None else metrics
        for metric in MetricType:
            if metric not in wanted:
                continue
            for mission_phase, phase_periods in periods.items():
                baselines.append(
                    _build(
                        by_series.get((crew_member_id, metric), []),
                        phase_periods,
                        crew_member_id,
                        metric,
                        mission_phase,
                        computed_at,
                        config,
                    )
                )
    return baselines


def _reference_periods(
    mission_phases: Sequence[MissionPhase],
    computed_at: datetime,
    reference_start: datetime | None,
    reference_end: datetime | None,
) -> dict[MissionPhaseType, list[Period]]:
    """Return the reference periods of every phase, phases in chronological order.

    Entries of the same phase are pooled. A period never extends past `computed_at` or
    outside the reference bounds; phases left without a period are omitted.
    """
    _check_timeline(mission_phases)
    lower = None if reference_start is None else as_utc(reference_start, "reference_start")
    upper = computed_at
    if reference_end is not None:
        upper = min(upper, as_utc(reference_end, "reference_end"))

    periods: dict[MissionPhaseType, list[Period]] = defaultdict(list)
    for entry in sorted(mission_phases, key=lambda entry: (entry.start_time, entry.phase_id)):
        start = entry.start_time if lower is None else max(entry.start_time, lower)
        end = upper if entry.end_time is None else min(entry.end_time, upper)
        if start < end:
            periods[entry.phase].append((as_utc(start, "start_time"), as_utc(end, "end_time")))
    return dict(periods)


def _check_timeline(mission_phases: Sequence[MissionPhase]) -> None:
    """Refuse a timeline on which the phase of a measurement would be ambiguous."""
    if len({entry.mission_id for entry in mission_phases}) > 1:
        raise ValueError("mission_phases must describe a single mission")
    ordered = sorted(mission_phases, key=lambda entry: (entry.start_time, entry.phase_id))
    for earlier, later in pairwise(ordered):
        if earlier.end_time is None or earlier.end_time > later.start_time:
            raise ValueError(
                f"mission phases '{earlier.phase_id}' and '{later.phase_id}' overlap, so the "
                "phase of a measurement would be ambiguous"
            )


def _build(
    candidates: Sequence[PhysiologicalMeasurement],
    periods: Sequence[Period],
    crew_member_id: str,
    metric: MetricType,
    mission_phase: MissionPhaseType,
    computed_at: datetime,
    config: BaselineConfig,
) -> PersonalBaseline:
    """Build one baseline from the assessed measurements of one crew member and metric."""
    series = [m for m in candidates if any(start <= m.measured_at < end for start, end in periods)]
    admitted = [m for m in series if m.data_quality.status in config.admitted_quality]

    scores = None
    if config.outlier_cutoff is not None:
        scores = modified_z_scores([m.value for m in admitted])
    is_outlier = (
        [False] * len(admitted)
        if scores is None
        else [abs(score) > config.outlier_cutoff for score in scores]
    )
    exclude = config.outlier_handling is OutlierHandling.EXCLUDE
    used = [m for m, flagged in zip(admitted, is_outlier, strict=True) if not (exclude and flagged)]

    remarks = []
    if len(admitted) < len(series):
        admitted_names = ", ".join(sorted(status.value for status in config.admitted_quality))
        remarks.append(
            f"Records not admitted to the baseline: {len(series) - len(admitted)} of "
            f"{len(series)} (admitted data quality: {admitted_names})."
        )
    remarks.extend(_outlier_remarks(admitted, scores, sum(is_outlier), config))

    if len(used) < config.minimum_samples:
        status = BaselineStatus.INSUFFICIENT_DATA
        statistics = BaselineStatistics()
        remarks.append("No baseline statistic is reported.")
    else:
        statistics = describe([m.value for m in used])
        status, status_remarks = _status(used, statistics, config)
        remarks.extend(status_remarks)

    draft = PersonalBaseline(
        baseline_id="pending",
        crew_member_id=crew_member_id,
        metric=metric,
        unit=METRIC_CATALOG[metric].unit,
        mission_phase=mission_phase,
        status=status,
        window_start=min(start for start, _ in periods),
        window_end=max(end for _, end in periods),
        sample_count=len(used),
        statistics=statistics,
        data_quality=summarize_series(
            series,
            metric=metric,
            periods=periods,
            assessed_at=computed_at,
            config=config.quality,
            analysed_count=len(used),
            minimum_samples=config.minimum_samples,
            remarks=remarks,
        ),
        algorithm=ALGORITHM,
        computed_at=computed_at,
    )
    # The identifier is derived from the content: computing the same baseline again
    # yields the same identifier, and any difference in the result yields another one.
    identifier = uuid.uuid5(_ID_NAMESPACE, draft.model_dump_json(exclude={"baseline_id"}))
    return draft.model_copy(update={"baseline_id": str(identifier)})


def _outlier_remarks(
    admitted: Sequence[PhysiologicalMeasurement],
    scores: Sequence[float] | None,
    outlier_count: int,
    config: BaselineConfig,
) -> list[str]:
    if config.outlier_cutoff is None:
        return ["Potential outliers were not screened: the screening is disabled."]
    if scores is None:
        # Nothing to say for a handful of values, or when all of them are identical:
        # the status remarks cover those cases.
        if len(admitted) < config.minimum_samples or len({m.value for m in admitted}) < 2:
            return []
        return [
            "Potential outliers were not screened: the median absolute deviation of the "
            "admitted values is zero, which leaves the modified z-score undefined."
        ]
    if not outlier_count:
        return []
    outcome = "excluded from" if config.outlier_handling is OutlierHandling.EXCLUDE else "kept in"
    return [
        f"Potential statistical outliers among the {len(admitted)} admitted values: "
        f"{outlier_count} (absolute modified z-score above {config.outlier_cutoff:g}; "
        f"Iglewicz and Hoaglin, 1993), {outcome} the statistics. The label is statistical: "
        "it indicates neither a measurement error nor a health condition."
    ]


def _status(
    used: Sequence[PhysiologicalMeasurement], statistics: BaselineStatistics, config: BaselineConfig
) -> tuple[BaselineStatus, list[str]]:
    """Status of a baseline that has enough values, with the sentences that explain it."""
    if statistics.minimum == statistics.maximum:
        return BaselineStatus.PROVISIONAL, [
            "All the values used are identical: the baseline says nothing about "
            "variability, deviations cannot be standardised against it, and it stays "
            "provisional."
        ]

    remarks = []
    if statistics.median_absolute_deviation == 0:
        remarks.append(
            "The median absolute deviation of the values used is zero, so deviations cannot "
            "be standardised with it; the standard deviation is still defined."
        )

    times = [m.measured_at for m in used]
    span = max(times) - min(times)
    requirements = []
    unmet = False
    if config.established_min_samples is not None:
        requirements.append(f"at least {config.established_min_samples} values")
        unmet = unmet or len(used) < config.established_min_samples
    if config.established_min_span is not None:
        requirements.append(
            f"values spanning at least {format_duration(config.established_min_span)}"
        )
        unmet = unmet or span < config.established_min_span

    if not requirements:
        remarks.append(
            "No criterion for an established baseline is configured, so the baseline is "
            "provisional."
        )
        return BaselineStatus.PROVISIONAL, remarks

    criteria = " and ".join(requirements)
    found = f"{len(used)} values spanning {format_duration(span)} were used"
    if unmet:
        remarks.append(
            f"The baseline is provisional: the configured criteria are {criteria}; {found}."
        )
        return BaselineStatus.PROVISIONAL, remarks
    remarks.append(
        f"The configured criteria for an established baseline are met ({criteria}); {found}."
    )
    return BaselineStatus.ESTABLISHED, remarks
