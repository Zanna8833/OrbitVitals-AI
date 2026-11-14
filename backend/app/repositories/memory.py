"""An isolated, lock-protected in-memory store; all data is lost on process restart."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from app.models import EvaluationResult, PersonalBaseline, PhysiologicalMeasurement


@dataclass(frozen=True)
class StoredBaseline:
    value: PersonalBaseline
    basis: str


class InMemoryRepository:
    """One instance per FastAPI app; callers receive independent model copies."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._measurements: dict[str, PhysiologicalMeasurement] = {}
        self._baselines: dict[str, StoredBaseline] = {}
        self._evaluations: dict[str, EvaluationResult] = {}

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def measurement(self, identifier: str) -> PhysiologicalMeasurement | None:
        with self._lock:
            value = self._measurements.get(identifier)
            return value.model_copy(deep=True) if value else None

    def measurements(self, crew_member_id: str) -> list[PhysiologicalMeasurement]:
        with self._lock:
            return sorted(
                (
                    value.model_copy(deep=True)
                    for value in self._measurements.values()
                    if value.crew_member_id == crew_member_id
                ),
                key=lambda value: (value.measured_at, value.measurement_id),
            )

    def save_measurements(self, values: Sequence[PhysiologicalMeasurement]) -> None:
        with self._lock:
            self._measurements.update(
                (value.measurement_id, value.model_copy(deep=True)) for value in values
            )

    def save_baseline(self, value: PersonalBaseline, basis: str) -> None:
        with self._lock:
            self._baselines[value.baseline_id] = StoredBaseline(value.model_copy(deep=True), basis)

    def baseline(self, identifier: str, crew_member_id: str) -> StoredBaseline | None:
        with self._lock:
            stored = self._baselines.get(identifier)
            if stored is None or stored.value.crew_member_id != crew_member_id:
                return None
            return StoredBaseline(stored.value.model_copy(deep=True), stored.basis)

    def baselines(self, crew_member_id: str) -> list[PersonalBaseline]:
        with self._lock:
            return sorted(
                (
                    stored.value.model_copy(deep=True)
                    for stored in self._baselines.values()
                    if stored.value.crew_member_id == crew_member_id
                ),
                key=lambda value: (value.window_end, value.computed_at, value.baseline_id),
                reverse=True,
            )

    def save_evaluation(self, value: EvaluationResult) -> None:
        with self._lock:
            self._evaluations[value.evaluation_id] = value.model_copy(deep=True)

    def evaluations(self, crew_member_id: str) -> list[EvaluationResult]:
        with self._lock:
            return sorted(
                (
                    value.model_copy(deep=True)
                    for value in self._evaluations.values()
                    if value.crew_member_id == crew_member_id
                ),
                key=lambda value: (value.window_end, value.evaluated_at, value.evaluation_id),
                reverse=True,
            )

    def invalidate(self, changes: Sequence[PhysiologicalMeasurement]) -> None:
        """Discard derived snapshots affected by backfill or a changed quality assessment."""

        def overlaps(crew: str, start: datetime, end: datetime) -> bool:
            return any(
                item.crew_member_id == crew
                and item.measured_at < end
                and (
                    item.interval_end > start
                    if item.interval_end is not None and item.interval_end > item.measured_at
                    else item.measured_at >= start
                )
                for item in changes
            )

        with self._lock:
            stale = {
                identifier
                for identifier, stored in self._baselines.items()
                if overlaps(
                    stored.value.crew_member_id, stored.value.window_start, stored.value.window_end
                )
            }
            self._baselines = {
                identifier: value
                for identifier, value in self._baselines.items()
                if identifier not in stale
            }
            self._evaluations = {
                identifier: value
                for identifier, value in self._evaluations.items()
                if not overlaps(value.crew_member_id, value.window_start, value.window_end)
                and not any(finding.baseline_id in stale for finding in value.findings)
            }
