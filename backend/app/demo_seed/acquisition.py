"""Authored acquisition assumptions for the synthetic dashboard revision only.

Device IDs persist a protocol key through the unchanged measurement contract.
These fictional protocols describe generation intent, not verified device use.
"""

from app.models import MetricType

SEED_REVISION = "dashboard-acquisition-v2"
MISSING_CURRENT_VITAL_DAYS = frozenset({2, 6, 10, 11, 12})
LEGACY_VITAL_METRICS = (
    MetricType.HEART_RATE,
    MetricType.RESPIRATORY_RATE,
    MetricType.BLOOD_OXYGEN_SATURATION,
)
DASHBOARD_METRICS = (
    MetricType.HEART_RATE_VARIABILITY_RMSSD,
    MetricType.SYSTOLIC_BLOOD_PRESSURE,
    MetricType.DIASTOLIC_BLOOD_PRESSURE,
    MetricType.BODY_TEMPERATURE,
    MetricType.BODY_MASS,
)
ACQUISITION_PROTOCOLS = {
    MetricType.HEART_RATE: {
        "device_suffix": "sim-waking-rest-v2",
        "minute_of_day": 7 * 60 + 5,
        "interval_minutes": 0,
        "context": "SIMULATED 07:00 waking followed by five minutes of seated quiet rest.",
        "modality": "Authored optical spot reading; no real sensor or beat data.",
    },
    MetricType.RESPIRATORY_RATE: {
        "device_suffix": "sim-waking-rest-v2",
        "minute_of_day": 7 * 60 + 5,
        "interval_minutes": 0,
        "context": "SIMULATED seated resting spot check after waking, before exercise.",
        "modality": "Authored respiratory spot reading; no measured waveform.",
    },
    MetricType.BLOOD_OXYGEN_SATURATION: {
        "device_suffix": "sim-waking-rest-v2",
        "minute_of_day": 7 * 60 + 5,
        "interval_minutes": 0,
        "context": "SIMULATED seated resting spot check after waking, before exercise.",
        "modality": "Authored optical spot reading, including retained decoder corruption.",
    },
    MetricType.HEART_RATE_VARIABILITY_RMSSD: {
        "device_suffix": "sim-resting-ppg-v2",
        "minute_of_day": 7 * 60,
        "interval_minutes": 5,
        "context": "SIMULATED five-minute seated resting capture immediately after waking.",
        "modality": "Authored PPG RMSSD scalar; not computed from absent beat intervals.",
    },
    MetricType.SYSTOLIC_BLOOD_PRESSURE: {
        "device_suffix": "sim-seated-cuff-v2",
        "minute_of_day": 7 * 60 + 10,
        "interval_minutes": 0,
        "context": "SIMULATED paired seated cuff check after quiet rest, before exercise.",
        "modality": "Authored cuff pair; no device accuracy or calibration claim.",
    },
    MetricType.DIASTOLIC_BLOOD_PRESSURE: {
        "device_suffix": "sim-seated-cuff-v2",
        "minute_of_day": 7 * 60 + 10,
        "interval_minutes": 0,
        "context": "SIMULATED same cuff, instant and context as the systolic channel.",
        "modality": "Authored cuff pair; no device accuracy or calibration claim.",
    },
    MetricType.BODY_TEMPERATURE: {
        "device_suffix": "sim-oral-spot-v2",
        "minute_of_day": 7 * 60 + 10,
        "interval_minutes": 0,
        "context": "SIMULATED oral spot check before exercise; not a core-temperature model.",
        "modality": "Authored oral reading; no real thermometer.",
    },
    MetricType.BODY_MASS: {
        "device_suffix": "sim-mass-check-v2",
        "minute_of_day": 7 * 60 + 15,
        "interval_minutes": 0,
        "context": "SIMULATED daily morning mass check before exercise.",
        "modality": "Authored mass-instrument reading; no spacecraft instrument model.",
    },
}


def acquisition_device_id(crew: str, metric: MetricType) -> str:
    """Resolve the fictional device/protocol identity retained by the HTTP API."""
    return f"{crew}:{ACQUISITION_PROTOCOLS[metric]['device_suffix']}"
