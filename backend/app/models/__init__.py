"""Shared data contracts. These models are the single source of truth.

The JSON Schema files in `/schemas` are generated from them by
`backend/scripts/export_schemas.py` and must never be edited by hand.
"""

from app.models.baseline import BaselineStatistics, BaselineStatus, PersonalBaseline
from app.models.common import AlgorithmInfo, ContractModel, HealthDomain
from app.models.data_quality import DataQuality, QualityFlag, QualityStatus
from app.models.evaluation import EvaluationResult, EvaluationStatus, MetricFinding
from app.models.measurement import MeasurementSource, PhysiologicalMeasurement
from app.models.metrics import METRIC_CATALOG, MetricDefinition, MetricType
from app.models.mission import MissionPhase, MissionPhaseType

# Contracts published as JSON Schema, keyed by the base name of the generated file.
CONTRACT_MODELS: dict[str, type[ContractModel]] = {
    "physiological_measurement": PhysiologicalMeasurement,
    "data_quality": DataQuality,
    "personal_baseline": PersonalBaseline,
    "mission_phase": MissionPhase,
    "evaluation_result": EvaluationResult,
}

__all__ = [
    "CONTRACT_MODELS",
    "METRIC_CATALOG",
    "AlgorithmInfo",
    "BaselineStatistics",
    "BaselineStatus",
    "ContractModel",
    "DataQuality",
    "EvaluationResult",
    "EvaluationStatus",
    "HealthDomain",
    "MeasurementSource",
    "MetricDefinition",
    "MetricFinding",
    "MetricType",
    "MissionPhase",
    "MissionPhaseType",
    "PersonalBaseline",
    "PhysiologicalMeasurement",
    "QualityFlag",
    "QualityStatus",
]
