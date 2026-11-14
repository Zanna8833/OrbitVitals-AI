"""Transactional orchestration; scientific modules and their public resource models stay intact."""

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta

from app.algorithms.data_quality import assess_measurements, assess_window
from app.algorithms.personal_baseline import build_baseline
from app.core.config import Settings
from app.domains.physical_activity import ActivityRequest, DailyBaselineReference, monitor_activity
from app.domains.physical_activity.models import ACTIVITY_METRICS
from app.domains.sleep import evaluate_sleep_window
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    DataQuality,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MeasurementSource,
    MetricFinding,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from app.repositories.memory import InMemoryRepository
from app.services.commands import ActivityOptions, BaselineCommand, EvaluationCommand

Clock = Callable[[], datetime]
_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "orbitvitals:api-integration:v1")


class IntegrationError(Exception):
    """An expected application error, translated to the documented HTTP error envelope."""

    def __init__(
        self, status_code: int, message: str, location: tuple[str, ...] = ("body",)
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.location = location


def _identifier(kind: str, payload: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{kind}:{payload}"))


def _identity(value: PhysiologicalMeasurement) -> dict:
    return value.model_dump(exclude={"data_quality"})


def _quality_identity(value: PhysiologicalMeasurement) -> dict | None:
    return value.data_quality.model_dump(exclude={"assessed_at"}) if value.data_quality else None


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _combined_quality(qualities: Sequence[DataQuality], at: datetime) -> DataQuality:
    """Combine status/flags without pooling incomparable sample denominators or scores."""
    if all(item.status == QualityStatus.UNUSABLE for item in qualities):
        status = QualityStatus.UNUSABLE
    elif all(item.status == QualityStatus.ACCEPTABLE for item in qualities):
        status = QualityStatus.ACCEPTABLE
    else:
        status = QualityStatus.DEGRADED
    return DataQuality(
        status=status,
        flags=sorted({flag for item in qualities for flag in item.flags}, key=str),
        notes="Per-metric Data Quality Engine assessments are attached to findings. "
        "Mixed unusable/usable metrics yield degraded window quality; only the affected "
        "metric is suppressed. Scores and sample completeness are not pooled.",
        algorithm=AlgorithmInfo(name="api_quality_rollup", version="0.1.0"),
        assessed_at=at,
    )


class IntegrationService:
    """The HTTP layer delegates to this service; no scientific defaults are invented."""

    def __init__(self, repository: InMemoryRepository, settings: Settings, clock: Clock) -> None:
        self.repository = repository
        self.settings = settings
        self.clock = clock

    def _at(self, requested: datetime | None) -> datetime:
        now = _utc(self.clock())
        if requested is not None and _utc(requested) > now:
            raise IntegrationError(422, "The requested computation time cannot be in the future")
        return _utc(requested) if requested is not None else now

    def ingest(
        self, incoming: Sequence[PhysiologicalMeasurement]
    ) -> list[PhysiologicalMeasurement]:
        at = self._at(None)
        with self.repository.transaction():
            unique: dict[str, PhysiologicalMeasurement] = {}
            new: dict[str, PhysiologicalMeasurement] = {}
            for original in incoming:
                value = original.model_copy(
                    update={
                        "measured_at": _utc(original.measured_at),
                        "interval_end": _utc(original.interval_end)
                        if original.interval_end
                        else None,
                        "data_quality": None,
                    }
                )
                previous = unique.get(value.measurement_id) or self.repository.measurement(
                    value.measurement_id
                )
                if previous is not None and _identity(previous) != _identity(value):
                    raise IntegrationError(
                        409, "measurement_id already exists with different content"
                    )
                unique[value.measurement_id] = value
                if self.repository.measurement(value.measurement_id) is None:
                    new[value.measurement_id] = value
            assessed = []
            changes = []
            for crew in sorted({value.crew_member_id for value in new.values()}):
                history = self.repository.measurements(crew)
                before = {value.measurement_id: value for value in history}
                additions = [value for value in new.values() if value.crew_member_id == crew]
                crew_assessed = assess_measurements(
                    [*history, *additions], assessed_at=at, config=self.settings.data_quality
                )
                assessed.extend(crew_assessed)
                changes.extend(
                    value
                    for value in crew_assessed
                    if (
                        value.measurement_id not in before
                        or _quality_identity(value)
                        != _quality_identity(before[value.measurement_id])
                    )
                )
            # Validate every record and compute every assessment before writing anything.
            self.repository.save_measurements(assessed)
            self.repository.invalidate(changes)
            return [self.repository.measurement(identifier) for identifier in unique]

    def _activity_request(
        self,
        crew: str,
        history: Sequence[PhysiologicalMeasurement],
        start: datetime,
        end: datetime,
        at: datetime,
        phase: MissionPhaseType | None,
        options: ActivityOptions,
        identifier: str,
        baselines: Sequence[PersonalBaseline] = (),
    ) -> ActivityRequest:
        return ActivityRequest(
            crew_member_id=crew,
            window_start=start,
            window_end=end,
            evaluated_at=at,
            evaluation_id=identifier,
            mission_phase=phase,
            measurements=tuple(value for value in history if value.metric in ACTIVITY_METRICS),
            sessions=options.sessions,
            coverage=options.coverage,
            day_plans=options.day_plans,
            policies=options.policies,
            reduction_run_length=options.reduction_run_length,
            context_notes=options.context_notes,
            baselines=tuple(
                DailyBaselineReference(
                    baseline=value,
                    comparison_basis="complete_active_day_total",
                    comparable=options.baselines_comparable,
                )
                for value in baselines
            ),
        )

    def _daily_reference(
        self,
        crew: str,
        history: Sequence[PhysiologicalMeasurement],
        command: BaselineCommand,
        at: datetime,
    ) -> tuple[list[PhysiologicalMeasurement], str, int]:
        report = monitor_activity(
            self._activity_request(
                crew,
                history,
                command.reference_start,
                command.reference_end,
                at,
                command.mission_phase,
                command.activity or ActivityOptions(),
                "reference-aggregation",
            )
        )
        by_id = {value.measurement_id: value for value in history}
        index = ACTIVITY_METRICS.index(command.metric)
        values = []
        excluded = 0
        for day in report.days:
            item = day.metrics[index]
            left = datetime.combine(day.day, time.min, UTC)
            right = left + timedelta(days=1)
            contained_in_phase = any(
                phase.phase == command.mission_phase
                and phase.start_time <= left
                and (phase.end_time is None or phase.end_time >= right)
                for phase in command.mission_phases
            )
            if not item.comparison_eligible or not contained_in_phase:
                if not day.planned_rest and day.comparisons_enabled:
                    excluded += 1
                continue
            sources = {by_id[identifier].source for identifier in item.measurement_ids}
            if len(sources) > 1:
                raise IntegrationError(
                    422, "Daily baseline contributions must use one source type per day"
                )
            source = next(iter(sources)) if sources else MeasurementSource.MANUAL_ENTRY
            values.append(
                PhysiologicalMeasurement(
                    measurement_id=_identifier(
                        "daily-total",
                        f"{crew}:{command.metric}:{day.day}:{item.observed_total}:{item.measurement_ids}",
                    ),
                    crew_member_id=crew,
                    metric=command.metric,
                    unit=item.unit,
                    value=item.observed_total,
                    measured_at=left,
                    interval_end=right,
                    source=source,
                    # A derived total is not a new raw device observation. Raw device checks
                    # already ran; individual-device ranges cannot be applied to the sum.
                    device_id=None,
                )
            )
        return (
            values,
            (
                f"Daily reference adapter: {len(values)} complete usable active-day totals; "
                f"{excluded} active dates excluded for incomplete recording, quality "
                "or phase boundaries. "
                "Rest/operational exceptions are excluded. Derived totals are transient and are "
                "not inserted into measurement history."
            ),
            excluded,
        )

    def generate_baseline(self, crew: str, command: BaselineCommand) -> PersonalBaseline:
        at = self._at(command.computed_at)
        if command.reference_end > at:
            raise IntegrationError(422, "reference_end cannot follow the computation time")
        with self.repository.transaction():
            history = assess_measurements(
                self.repository.measurements(crew),
                assessed_at=at,
                config=self.settings.data_quality,
            )
            quality_config = self.settings.data_quality
            notes = f"API aggregation basis: {command.aggregation}. "
            excluded_days = 0
            if command.aggregation == "complete_active_day_total":
                history, daily_notes, excluded_days = self._daily_reference(
                    crew, history, command, at
                )
                notes += daily_notes + " "
                quality_config = replace(quality_config, sensor_ranges={}, expected_intervals={})
            value = build_baseline(
                history,
                command.mission_phases,
                crew_member_id=crew,
                metric=command.metric,
                mission_phase=command.mission_phase,
                computed_at=at,
                reference_start=command.reference_start,
                reference_end=command.reference_end,
                config=command.config.engine_config(quality_config),
            )
            if value is None:
                raise IntegrationError(
                    422, "No requested mission phase overlaps the reference window"
                )
            if command.config.policy_source:
                notes += f"Establishment policy source: {command.config.policy_source}. "
            quality = value.data_quality.model_copy(deep=True)
            if excluded_days:
                if quality.status != QualityStatus.UNUSABLE:
                    quality.status = QualityStatus.DEGRADED
                quality.flags = sorted({*quality.flags, QualityFlag.MISSING_DATA}, key=str)
                quality.completeness = len(history) / (len(history) + excluded_days)
                quality.score = None
                quality.algorithm = AlgorithmInfo(
                    name="api_daily_reference_quality", version="0.1.0"
                )
            quality.notes = (quality.notes or "") + " " + notes
            value = value.model_copy(update={"data_quality": quality})
            value = value.model_copy(
                update={
                    "baseline_id": _identifier(
                        "baseline", value.model_dump_json(exclude={"baseline_id"})
                    )
                }
            )
            self.repository.save_baseline(value, command.aggregation)
            return value

    def _baselines(self, crew: str, command: EvaluationCommand) -> list[PersonalBaseline]:
        selected = []
        seen = set()
        for identifier in command.baseline_ids:
            stored = self.repository.baseline(identifier, crew)
            if stored is None:
                raise IntegrationError(404, "Requested baseline was not found for this crew member")
            value = stored.value
            if METRIC_CATALOG[value.metric].domain != command.domain:
                raise IntegrationError(
                    422, "Selected baseline belongs to a different health domain"
                )
            if value.mission_phase != command.mission_phase:
                raise IntegrationError(422, "Selected baseline must match mission_phase")
            expected_basis = (
                "measurement"
                if command.domain == HealthDomain.SLEEP
                else "complete_active_day_total"
            )
            if stored.basis != expected_basis:
                raise IntegrationError(
                    422, f"Selected baseline requires aggregation={expected_basis}"
                )
            if value.metric in seen:
                raise IntegrationError(422, "Select at most one baseline for each metric")
            seen.add(value.metric)
            selected.append(value)
        return selected

    def generate_evaluation(self, crew: str, command: EvaluationCommand) -> EvaluationResult:
        at = self._at(command.evaluated_at)
        if command.window_end > at:
            raise IntegrationError(422, "window_end cannot follow the evaluation time")
        with self.repository.transaction():
            history = assess_measurements(
                self.repository.measurements(crew),
                assessed_at=at,
                config=self.settings.data_quality,
            )
            selected = self._baselines(crew, command)
            payload = json.dumps(
                {
                    "crew": crew,
                    "at": at.isoformat(),
                    "command": command.model_dump(mode="json"),
                    "measurements": [value.model_dump(mode="json") for value in history],
                },
                sort_keys=True,
            )
            identifier = _identifier("evaluation", payload)
            if command.domain == HealthDomain.PHYSICAL_ACTIVITY:
                options = command.activity or ActivityOptions()
                if selected and not options.baselines_comparable:
                    raise IntegrationError(
                        422, "Confirm activity.baselines_comparable before using a daily baseline"
                    )
                result = monitor_activity(
                    self._activity_request(
                        crew,
                        history,
                        command.window_start,
                        command.window_end,
                        at,
                        command.mission_phase,
                        options,
                        identifier,
                        selected,
                    )
                ).evaluation
            else:
                result = self._sleep_evaluation(crew, command, history, selected, at, identifier)
                if any(
                    value.source == MeasurementSource.SIMULATED
                    and value.metric in (MetricType.SLEEP_DURATION, MetricType.SLEEP_EFFICIENCY)
                    for value in history
                ):
                    if not result.summary.startswith("SIMULATED DATA"):
                        result.summary = "SIMULATED DATA. " + result.summary
                    for finding in result.findings:
                        finding.explanation = "SIMULATED DATA. " + finding.explanation
            self.repository.save_evaluation(result)
            return result

    def _sleep_evaluation(
        self,
        crew: str,
        command: EvaluationCommand,
        history: Sequence[PhysiologicalMeasurement],
        baselines: Sequence[PersonalBaseline],
        at: datetime,
        identifier: str,
    ) -> EvaluationResult:
        metrics = (MetricType.SLEEP_DURATION, MetricType.SLEEP_EFFICIENCY)
        records = [value for value in history if value.metric in metrics]
        qualities = {
            metric: assess_window(
                records,
                crew_member_id=crew,
                metric=metric,
                window_start=_utc(command.window_start),
                window_end=_utc(command.window_end),
                assessed_at=at,
                config=self.settings.data_quality,
            )
            for metric in metrics
        }
        quality = _combined_quality(list(qualities.values()), at)
        config = command.sleep_config or self.settings.sleep_config
        if config is None:
            reason = (
                "Sleep screening policy is not configured. Supply sleep_config or set "
                "ORBITVITALS_SLEEP_CONFIG. No thresholds or physiological findings were assumed."
            )
            return EvaluationResult(
                evaluation_id=identifier,
                crew_member_id=crew,
                domain=HealthDomain.SLEEP,
                mission_phase=command.mission_phase,
                window_start=_utc(command.window_start),
                window_end=_utc(command.window_end),
                evaluated_at=at,
                status=EvaluationStatus.INSUFFICIENT_DATA,
                summary=reason,
                findings=[
                    MetricFinding(
                        metric=metric,
                        unit=METRIC_CATALOG[metric].unit,
                        status=EvaluationStatus.INSUFFICIENT_DATA,
                        explanation=reason,
                        data_quality=qualities[metric],
                    )
                    for metric in metrics
                ],
                data_quality=quality,
                algorithm=AlgorithmInfo(name="api_orchestration", version="0.1.0"),
            )
        admitted = [
            value for value in records if value.data_quality.status == QualityStatus.ACCEPTABLE
        ]
        result = evaluate_sleep_window(
            admitted,
            evaluation_id=identifier,
            crew_member_id=crew,
            window_start=command.window_start,
            window_end=command.window_end,
            evaluated_at=at,
            config=config,
            mission_phase=command.mission_phase,
            baselines={value.metric: value for value in baselines},
            data_quality=quality,
            metric_data_quality=qualities,
        )
        for finding in result.findings:
            excluded = [
                value.measurement_id
                for value in records
                if value.metric == finding.metric
                and value.data_quality.status != QualityStatus.ACCEPTABLE
                and command.window_start <= value.measured_at < command.window_end
            ]
            if excluded:
                finding.explanation += (
                    " API eligibility policy excluded non-acceptable records: "
                    f"{', '.join(excluded)}."
                )
        if any(value.source == MeasurementSource.SIMULATED for value in records):
            result.summary = "SIMULATED DATA. " + result.summary
        return result
