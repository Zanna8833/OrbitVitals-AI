"""Reviewed topic routing and authored context for exactly two existing pipelines.

Manifest pins bind these interpretations to the reviewed source snapshots. Updating
an upstream file or metadata manifest requires an explicit new scientific review.
No participant records, physiological values, or copied NASA documentation occur here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.nasa_data import actigraphy
from app.nasa_data import source as actigraphy_source
from app.nasa_evidence.models import DatasetId, EvidenceTopic, EvidenceVariable
from app.nasa_mr001g import analysis as mr001g
from app.nasa_mr001g import source as mr001g_source


@dataclass(frozen=True)
class DatasetProfile:
    dataset_id: DatasetId
    source_identity: str
    manifest_path: str
    manifest_sha256: str
    load_manifest: Callable[[], tuple[dict[str, Any], bytes]]
    import_dataset: Callable[[Path], dict[str, Any]]
    pipeline: str
    documentation_path: str
    metadata_url: str
    topics: tuple[EvidenceTopic, ...]
    variables: tuple[EvidenceVariable, ...]
    context: tuple[str, ...]
    limitations: tuple[str, ...]
    synthetic_fixture: bool = False


COMMON_LIMITATIONS = (
    "Human terrestrial bed-rest volunteers are not synthetic crew members or astronauts in flight.",
    "Descriptive evidence establishes no causation, clinical norms, thresholds or NASA validation.",
    "Calendar dates do not supply aware measurement instants or observation boundaries.",
    "Missing observations do not establish sensor failure, nonadherence or physiological decline.",
    "Source records, participant IDs, notes, dates and individual results remain private.",
    "Redistribution rights remain unconfirmed. Public access is not a blanket reuse license.",
    "Physiological statistics are withheld; structural counts describe data validation only.",
)


def reviewed_profiles() -> tuple[DatasetProfile, ...]:
    """Return the closed production catalog; no runtime dataset registration exists."""
    return (
        DatasetProfile(
            dataset_id=DatasetId.ACTIGRAPHY,
            source_identity=actigraphy_source.DATASET_ID,
            manifest_path="data/nasa/utmb_campaign_1_actigraphy/manifest.json",
            manifest_sha256="991b7f6292f1321c7fab6102b76a5c8285fbf6a626c4d08b55e8321646da1be9",
            load_manifest=actigraphy_source.load_manifest,
            import_dataset=actigraphy.import_dataset,
            pipeline="app.nasa_data.actigraphy.import_dataset",
            documentation_path="docs/nasa-data-proof-public.md",
            metadata_url=(
                "https://nlsp.nasa.gov/api/v1/data/datasets/"
                "e26501eb-7d7a-5012-8c8e-c5bdb3eecaf6/full"
            ),
            topics=(EvidenceTopic.SLEEP, EvidenceTopic.ACTIGRAPHY, EvidenceTopic.DATA_QUALITY),
            variables=(
                EvidenceVariable(
                    source_column="Sleep Duration (hours)",
                    description="Processed sleep duration, using documented duration syntax.",
                    source_representation="ReadMe HH:mm; inspected cells also contain :ss",
                    unit_verification="reviewed_source_dictionary",
                    canonical_unit="min",
                    transformation="Existing importer: 60 * hours + minutes + seconds / 60.",
                ),
                EvidenceVariable(
                    source_column="Sleep Efficiency (%)",
                    description="Processed sleep efficiency reported as a percentage.",
                    source_representation="percent",
                    unit_verification="reviewed_source_dictionary",
                    canonical_unit="%",
                    transformation="Identity; no physiological values are exposed by this adapter.",
                ),
            ),
            context=(
                "The processed export provides sleep-duration and sleep-efficiency context.",
                "Duration interpretation uses both the source dictionary and the column heading.",
                "The pipeline verifies the query export without appending it to the primary table.",
                "Structural counts cover the two selected metric columns, rather than every field.",
            ),
            limitations=COMMON_LIMITATIONS
            + (
                "Processed actigraphy is not polysomnography or a raw movement-epoch stream.",
                "Sleep latency has no supported canonical metric mapping.",
                "Source notes and device quality are not independently validated by the importer.",
            ),
        ),
        DatasetProfile(
            dataset_id=DatasetId.MR001G,
            source_identity=mr001g_source.DATASET_ID,
            manifest_path="data/nasa/utmb_campaign_3_mr001g_tilt/manifest.json",
            manifest_sha256="bb924b5cda10f1e25264cc2692bd5c62a9510db47fd05cb6675c938b21065499",
            load_manifest=mr001g_source.load_manifest,
            import_dataset=mr001g.import_dataset,
            pipeline="app.nasa_mr001g.analysis.import_dataset",
            documentation_path="docs/nasa-mr001g-cardiovascular.md",
            metadata_url=mr001g_source.METADATA_URLS["dataset_metadata"],
            topics=(
                EvidenceTopic.HEART_RATE,
                EvidenceTopic.BLOOD_PRESSURE,
                EvidenceTopic.CARDIOVASCULAR_ADAPTATION,
                EvidenceTopic.DATA_QUALITY,
            ),
            variables=tuple(
                EvidenceVariable(
                    source_column=column,
                    description=description,
                    source_representation="Original numerical scale; source unit is not verified.",
                    unit_verification="unresolved",
                    canonical_unit=None,
                    transformation="None; no normalization or quantitative clinical comparison.",
                )
                for column, description in (
                    ("SBP", "Source-label systolic pressure candidate."),
                    ("DBP", "Source-label diastolic pressure candidate."),
                    ("HR", "Reported heart-rate candidate; acquisition method unspecified."),
                    ("HR (Dinamap)", "Source-labeled Dinamap heart-rate channel."),
                    (
                        "AVE HR",
                        "Averaged heart-rate candidate; window and channel are unspecified.",
                    ),
                )
            ),
            context=(
                "The Tilt export describes supine and tilt testing in terrestrial bed rest.",
                (
                    "Heart-rate channels remain separate; equivalent acquisition and averaging "
                    "are not established."
                ),
                "The importer annotates questionable pressure pairs and keeps both source values.",
                (
                    "Protocol context does not establish a direction or magnitude of "
                    "cardiovascular adaptation."
                ),
                "Counts cover present HR/BP columns; absent columns create no cells.",
            ),
            limitations=COMMON_LIMITATIONS
            + (
                "Source-unit verification is unresolved for every selected MR001G channel.",
                (
                    "Do not normalize to bpm/mmHg or make quantitative clinical comparisons "
                    "until units and protocol are established."
                ),
                "Dates, relative steps, missing context and catalog discrepancies require review.",
                "Broader campaign enrollment and demographics do not establish export membership.",
                "The selected Tilt dataset excludes the experiment's separate hormonal exports.",
            ),
        ),
    )
