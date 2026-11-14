"""Fabricated JSON requests for integration tests, never mission exercise/sleep policies."""

from datetime import UTC, datetime, timedelta

from app.models import METRIC_CATALOG, MetricType

PREFIX = "/api/v1"
START = datetime(2026, 11, 2, tzinfo=UTC)


def simulated_measurement(
    identifier: str = "sim-m1",
    metric: str = "exercise_duration",
    value: float = 30,
    instant: datetime = START,
    crew: str = "sim-crew",
    **overrides,
) -> dict:
    return {
        "measurement_id": identifier,
        "crew_member_id": crew,
        "metric": metric,
        "unit": METRIC_CATALOG[MetricType(metric)].unit,
        "value": value,
        "measured_at": instant.isoformat(),
        "source": "simulated",
        "device_id": "sim-device",
        **overrides,
    }


def simulated_sleep_policy() -> dict:
    # Explicit synthetic test settings, never imported by the application as defaults.
    return {
        "policy_id": "simulated-api-test-policy",
        "duration": {
            "minimum_slope_per_day": 5,
            "minimum_total_change": 15,
            "minimum_observation_deviation": 30,
        },
        "efficiency": {
            "minimum_slope_per_day": 0.5,
            "minimum_total_change": 2,
            "minimum_observation_deviation": 5,
        },
        "minimum_nights": 3,
        "minimum_coverage": 1,
        "minimum_span_days": 2,
        "maximum_consecutive_missing_nights": 0,
        "minimum_decreasing_fraction": 1,
        "night_start_hour_utc": 12,
    }


def sleep_records(
    values: list[float], *, start: datetime = START, crew: str = "sim-crew"
) -> list[dict]:
    records = []
    for day, value in enumerate(values):
        instant = start + timedelta(days=day, hours=22)
        for metric, reading in [("sleep_duration", value), ("sleep_efficiency", 90)]:
            records.append(
                simulated_measurement(
                    f"sim-{crew}-{instant.date()}-{metric}",
                    metric,
                    reading,
                    instant,
                    crew,
                    interval_end=(instant + timedelta(hours=12)).isoformat(),
                )
            )
    return records


def sleep_command(days: int = 4, *, start: datetime = START) -> dict:
    return {
        "domain": "sleep",
        "window_start": (start + timedelta(hours=12)).isoformat(),
        "window_end": (start + timedelta(days=days, hours=12)).isoformat(),
        "mission_phase": "in_flight",
        "sleep_config": simulated_sleep_policy(),
    }


def activity_records(
    values: list[float], *, start: datetime = START, crew: str = "sim-crew"
) -> list[dict]:
    return [
        simulated_measurement(
            f"sim-{crew}-{(start + timedelta(days=day)).date()}-{metric}",
            metric,
            reading,
            start + timedelta(days=day, hours=9),
            crew,
            interval_end=(start + timedelta(days=day, hours=10)).isoformat(),
        )
        for day, value in enumerate(values)
        for metric, reading in [("exercise_duration", value), ("active_energy_expenditure", 200)]
    ]


def activity_options(days: int = 3, *, start: datetime = START) -> dict:
    return {
        "coverage": [
            {
                "day": (start + timedelta(days=day)).date().isoformat(),
                "metric": metric,
                "complete": True,
            }
            for day in range(days)
            for metric in ("exercise_duration", "active_energy_expenditure")
        ],
        "policies": [
            {"metric": "exercise_duration", "daily_target": 20},
            {"metric": "active_energy_expenditure", "daily_target": 100},
        ],
    }


def activity_command(days: int = 3, *, start: datetime = START) -> dict:
    return {
        "domain": "physical_activity",
        "window_start": start.isoformat(),
        "window_end": (start + timedelta(days=days)).isoformat(),
        "mission_phase": "in_flight",
        "activity": activity_options(days, start=start),
    }


def baseline_command(
    metric: str = "sleep_duration", *, start: datetime = START, days: int = 3
) -> dict:
    return {
        "metric": metric,
        "mission_phase": "in_flight",
        "mission_phases": [
            {
                "phase_id": "sim-phase",
                "mission_id": "sim-mission",
                "phase": "in_flight",
                "start_time": "2026-10-01T00:00:00Z",
            }
        ],
        "reference_start": start.isoformat(),
        "reference_end": (start + timedelta(days=days)).isoformat(),
    }
