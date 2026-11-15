"""Checks a crew member's daily intake of energy, protein, fluid, vitamins and minerals against
NASA's spaceflight requirements.

Requirements come from NASA JSC-67378 Rev 1 (2020), Nutritional Requirements for Exploration
Missions up to 365 days: NASA uses the US Dietary Reference Intakes, with vitamin D raised for the
lack of sunlight (OCHMO-TB-013). Intake is logged either as a food of the station menu with a number
of servings, or directly as values (fresh food, water drunk). The standard menu has about 200 items
and makes up about 75% of the food on board (ISS Food System Overview, 2025); NASA's ISS FIT tablet
app logs food the same way. The result supports decisions made by people: it is not a diagnosis.

Limits: the extra 200 kcal per hour of spacewalk (JSC-67378) is not included, and a day logged only
in part (a forgotten dinner) lowers the mean.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import AwareDatetime, Field, NonNegativeFloat, model_validator

from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    ContractModel,
    DataQuality,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MetricFinding,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    QualityStatus,
)
from app.models.common import Identifier

ALGORITHM = AlgorithmInfo(name="nutrition_intake", version="0.1.0")
FOOD_CATALOG_PATH = Path(__file__).parent / "iss_food_catalog.json"

# Activity factor for crews with exercise equipment on par with the station's (JSC-67378)
ACTIVITY_FACTOR = 1.25
# NASA requires 100% of the estimated energy requirement; the 2% margin is a team choice
ENERGY_MARGIN = 0.02
PROTEIN_MIN_G_PER_KG = 1.2
PROTEIN_MAX_G_PER_KG = 1.8
FLUID_ML_PER_KG = 32
# Phosphorus shall not exceed 1.5 times the calcium intake (JSC-67378)
PHOSPHORUS_TO_CALCIUM_MAX = 1.5
# Women under 50 who do not suppress menstruation need at least 18 mg/d of iron (JSC-67378)
IRON_MENSTRUATION_MIN_MG = 18
IRON_MENSTRUATION_AGE_LIMIT = 50


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"


FLUID_MIN_ML = {Sex.MALE: 2500, Sex.FEMALE: 2100}

# Daily (minimum, maximum) from JSC-67378, by sex; None means no limit
FIXED_REQUIREMENTS = {
    MetricType.VITAMIN_A_INTAKE: {Sex.MALE: (900, None), Sex.FEMALE: (700, None)},
    MetricType.VITAMIN_C_INTAKE: {Sex.MALE: (125, None), Sex.FEMALE: (110, None)},
    MetricType.VITAMIN_D_INTAKE: {Sex.MALE: (25, None), Sex.FEMALE: (25, None)},
    MetricType.VITAMIN_K_INTAKE: {Sex.MALE: (120, None), Sex.FEMALE: (90, None)},
    MetricType.VITAMIN_B12_INTAKE: {Sex.MALE: (2.4, None), Sex.FEMALE: (2.4, None)},
    MetricType.FOLATE_INTAKE: {Sex.MALE: (400, None), Sex.FEMALE: (400, None)},
    MetricType.CALCIUM_INTAKE: {Sex.MALE: (1000, 2500), Sex.FEMALE: (1000, 2500)},
    MetricType.PHOSPHORUS_INTAKE: {Sex.MALE: (700, None), Sex.FEMALE: (700, None)},
    MetricType.SODIUM_INTAKE: {Sex.MALE: (1500, 2300), Sex.FEMALE: (1500, 2300)},
    MetricType.POTASSIUM_INTAKE: {Sex.MALE: (3400, None), Sex.FEMALE: (2600, None)},
    # Iron is limited to avoid iron overload, since spaceflight raises iron stores
    MetricType.IRON_INTAKE: {Sex.MALE: (None, 8), Sex.FEMALE: (None, 8)},
    MetricType.MAGNESIUM_INTAKE: {Sex.MALE: (420, None), Sex.FEMALE: (320, None)},
    MetricType.ZINC_INTAKE: {Sex.MALE: (11, None), Sex.FEMALE: (8, None)},
}

# Calcium comes before phosphorus: the phosphorus maximum depends on the calcium intake
EVALUATED_METRICS = [
    MetricType.ENERGY_INTAKE,
    MetricType.PROTEIN_INTAKE,
    MetricType.FLUID_INTAKE,
    MetricType.VITAMIN_A_INTAKE,
    MetricType.VITAMIN_C_INTAKE,
    MetricType.VITAMIN_D_INTAKE,
    MetricType.VITAMIN_K_INTAKE,
    MetricType.VITAMIN_B12_INTAKE,
    MetricType.FOLATE_INTAKE,
    MetricType.CALCIUM_INTAKE,
    MetricType.PHOSPHORUS_INTAKE,
    MetricType.SODIUM_INTAKE,
    MetricType.POTASSIUM_INTAKE,
    MetricType.IRON_INTAKE,
    MetricType.MAGNESIUM_INTAKE,
    MetricType.ZINC_INTAKE,
]


class CrewProfile(ContractModel):
    """Data the requirements depend on."""

    sex: Sex
    # The energy equations are for adults of 19 years and older
    age_years: int = Field(ge=19)
    height_m: float = Field(gt=0)
    body_mass_kg: float = Field(gt=0, description="Current mass, e.g. the latest body_mass.")
    menstruating: bool = False


class IntakeEntry(ContractModel):
    """One logged intake: a food of the catalog with its servings, or values entered directly.

    Direct values are in the catalog units (metric_catalog.json); a nutrient left out counts as
    zero, so water drunk is logged as {"fluid_intake": 500}.
    """

    entry_id: Identifier
    crew_member_id: Identifier
    eaten_at: AwareDatetime
    food_id: Identifier | None = None
    servings: float = Field(default=1, gt=0)
    values: dict[MetricType, NonNegativeFloat] = {}

    @model_validator(mode="after")
    def _check_food_or_values(self) -> Self:
        has_values = len(self.values) > 0
        if (self.food_id is None) == (not has_values):
            raise ValueError("Log either a food_id or direct values, not both")
        for metric in self.values:
            if metric not in EVALUATED_METRICS:
                raise ValueError("Not a nutrition intake metric: " + metric.value)
        return self


@dataclass
class DayIntake:
    """Totals of one UTC day, and for each nutrient the foods whose value is not known."""

    day: date
    totals: dict[MetricType, float]
    unknown_foods: dict[MetricType, list[str]]


def load_food_catalog(path: Path) -> dict[str, dict[MetricType, float | None]]:
    """Food id -> values per serving. None means the value is not known yet."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    catalog = {}
    for food_id, food in data["foods"].items():
        values = {}
        for name, value in food["values"].items():
            values[MetricType(name)] = value
        catalog[food_id] = values
    return catalog


def default_food_catalog() -> dict[str, dict[MetricType, float | None]]:
    """Foods named by NASA as part of the station's food system (iss_food_catalog.json)."""
    return load_food_catalog(FOOD_CATALOG_PATH)


def entry_values(
    entry: IntakeEntry, catalog: dict[str, dict[MetricType, float | None]]
) -> dict[MetricType, float | None]:
    if entry.food_id is None:
        values = {}
        for metric in EVALUATED_METRICS:
            values[metric] = entry.values.get(metric, 0.0)
        return values
    if entry.food_id not in catalog:
        raise ValueError("Food not in the catalog: " + entry.food_id)
    values = {}
    for metric in EVALUATED_METRICS:
        per_serving = catalog[entry.food_id].get(metric)
        if per_serving is None:
            values[metric] = None
        else:
            values[metric] = per_serving * entry.servings
    return values


def daily_intakes(
    entries: list[IntakeEntry], catalog: dict[str, dict[MetricType, float | None]]
) -> list[DayIntake]:
    """One DayIntake for each UTC day with at least one entry, in date order."""
    days = {}
    for entry in entries:
        day = entry.eaten_at.astimezone(UTC).date()
        if day not in days:
            totals = {}
            unknown_foods = {}
            for metric in EVALUATED_METRICS:
                totals[metric] = 0.0
                unknown_foods[metric] = []
            days[day] = DayIntake(day=day, totals=totals, unknown_foods=unknown_foods)
        intake = days[day]
        values = entry_values(entry, catalog)
        for metric in EVALUATED_METRICS:
            if values[metric] is None:
                intake.unknown_foods[metric].append(entry.food_id)
            else:
                intake.totals[metric] += values[metric]
    result = []
    for day in sorted(days):
        result.append(days[day])
    return result


def estimated_energy_requirement(profile: CrewProfile) -> float:
    """kcal/day, Dietary Reference Intake equations for adults (as in JSC-67378 and OCHMO-TB-013).
    JSC-67378 prints 622 for men: the original equation and OCHMO-TB-013 use 662."""
    mass = profile.body_mass_kg
    height = profile.height_m
    if profile.sex == Sex.MALE:
        return 662 - 9.53 * profile.age_years + ACTIVITY_FACTOR * (15.9 * mass + 539.6 * height)
    return 354 - 6.91 * profile.age_years + ACTIVITY_FACTOR * (9.36 * mass + 726 * height)


def requirement_range(
    metric: MetricType, profile: CrewProfile, calcium_mean: float | None
) -> tuple[float | None, float | None]:
    """Daily (minimum, maximum) for this crew member; None means no limit."""
    mass = profile.body_mass_kg
    if metric == MetricType.ENERGY_INTAKE:
        return estimated_energy_requirement(profile) * (1 - ENERGY_MARGIN), None
    if metric == MetricType.PROTEIN_INTAKE:
        return PROTEIN_MIN_G_PER_KG * mass, PROTEIN_MAX_G_PER_KG * mass
    if metric == MetricType.FLUID_INTAKE:
        return max(FLUID_ML_PER_KG * mass, FLUID_MIN_ML[profile.sex]), None
    needs_more_iron = (
        profile.sex == Sex.FEMALE
        and profile.menstruating
        and profile.age_years < IRON_MENSTRUATION_AGE_LIMIT
    )
    if metric == MetricType.IRON_INTAKE and needs_more_iron:
        return IRON_MENSTRUATION_MIN_MG, None
    minimum, maximum = FIXED_REQUIREMENTS[metric][profile.sex]
    if metric == MetricType.PHOSPHORUS_INTAKE and calcium_mean is not None:
        maximum = PHOSPHORUS_TO_CALCIUM_MAX * calcium_mean
    return minimum, maximum


def range_text(minimum: float | None, maximum: float | None, unit: str) -> str:
    if minimum is not None and maximum is not None:
        return f"{minimum:.4g}-{maximum:.4g} {unit}"
    if minimum is not None:
        return f"at least {minimum:.4g} {unit}"
    return f"at most {maximum:.4g} {unit}"


def window_day_count(window_start: datetime, window_end: datetime) -> int:
    """UTC calendar days touched by [window_start, window_end)."""
    first = window_start.astimezone(UTC).date()
    last = (window_end - timedelta(microseconds=1)).astimezone(UTC).date()
    return (last - first).days + 1


def evaluate_nutrient(
    metric: MetricType,
    intakes: list[DayIntake],
    day_count: int,
    minimum: float | None,
    maximum: float | None,
    note: str,
) -> MetricFinding:
    """Mean daily intake over the logged days against the NASA range. A day where a food has no
    value for this nutrient is left out, because its total is not known."""
    unit = METRIC_CATALOG[metric].unit
    usable = []
    excluded = []
    for intake in intakes:
        foods = intake.unknown_foods[metric]
        if len(foods) > 0:
            excluded.append(f"{intake.day.isoformat()} ({', '.join(sorted(set(foods)))})")
        else:
            usable.append(intake.totals[metric])
    explanation = f"Logged {len(intakes)} of {day_count} days."
    if len(excluded) > 0:
        explanation = f"{explanation} Left out, foods without a value: {'; '.join(excluded)}."
    if len(usable) == 0:
        return MetricFinding(
            metric=metric,
            unit=unit,
            status=EvaluationStatus.INSUFFICIENT_DATA,
            explanation=f"{explanation} No day with a complete total.",
        )

    mean = sum(usable) / len(usable)
    nasa_range = range_text(minimum, maximum, unit)
    # The reference is the limit that was crossed, or the minimum when the mean is in range
    reference = minimum
    if reference is None:
        reference = maximum
    if minimum is not None and mean < minimum:
        status = EvaluationStatus.ATTENTION
        position = "below"
    elif maximum is not None and mean > maximum:
        status = EvaluationStatus.ATTENTION
        position = "above"
        reference = maximum
    else:
        status = EvaluationStatus.NOMINAL
        position = "within"
    explanation = (
        f"{explanation} Mean daily intake {mean:.4g} {unit} is {position} the NASA range "
        f"({nasa_range}{note})."
    )
    absolute_deviation = mean - reference
    relative_deviation = None
    if reference != 0:
        relative_deviation = round(absolute_deviation / reference, 4)
    return MetricFinding(
        metric=metric,
        unit=unit,
        status=status,
        observed_value=round(mean, 2),
        baseline_value=round(reference, 2),
        absolute_deviation=round(absolute_deviation, 2),
        relative_deviation=relative_deviation,
        explanation=explanation,
    )


def phase_at(moment: datetime, mission_phases: list[MissionPhase]) -> MissionPhaseType | None:
    for phase in mission_phases:
        if phase.start_time <= moment and (phase.end_time is None or moment < phase.end_time):
            return phase.phase
    return None


def evaluate_nutrition(
    crew_member_id: str,
    entries: list[IntakeEntry],
    catalog: dict[str, dict[MetricType, float | None]],
    profile: CrewProfile,
    mission_phases: list[MissionPhase],
    window_start: datetime,
    window_end: datetime,
    evaluated_at: datetime,
    evaluation_id: str,
) -> EvaluationResult:
    """Evaluates the intake of one crew member logged in [window_start, window_end).

    Entries of other crew members are ignored; a food missing from the catalog raises ValueError.
    """
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    if window_end > evaluated_at:
        raise ValueError("window_end cannot be after evaluated_at")

    own_entries = []
    for entry in entries:
        if entry.crew_member_id != crew_member_id:
            continue
        if window_start <= entry.eaten_at < window_end:
            own_entries.append(entry)
    intakes = daily_intakes(own_entries, catalog)
    day_count = window_day_count(window_start, window_end)

    eer = estimated_energy_requirement(profile)
    mass = profile.body_mass_kg
    notes = {
        MetricType.ENERGY_INTAKE: (
            f", {100 - ENERGY_MARGIN * 100:g}% of the estimated requirement of {eer:.0f} kcal"
        ),
        MetricType.PROTEIN_INTAKE: (
            f", {PROTEIN_MIN_G_PER_KG}-{PROTEIN_MAX_G_PER_KG} g per kg of body mass ({mass:g} kg)"
        ),
        MetricType.FLUID_INTAKE: f", {FLUID_ML_PER_KG} mL per kg of body mass, food water included",
        MetricType.PHOSPHORUS_INTAKE: ", at most 1.5 times the calcium intake",
    }
    findings = []
    calcium_mean = None
    for metric in EVALUATED_METRICS:
        minimum, maximum = requirement_range(metric, profile, calcium_mean)
        note = notes.get(metric, "")
        finding = evaluate_nutrient(metric, intakes, day_count, minimum, maximum, note)
        if metric == MetricType.CALCIUM_INTAKE:
            calcium_mean = finding.observed_value
        findings.append(finding)

    attention = []
    evaluated = 0
    for finding in findings:
        if finding.status == EvaluationStatus.ATTENTION:
            attention.append(finding.metric.value)
        if finding.status != EvaluationStatus.INSUFFICIENT_DATA:
            evaluated += 1
    if len(attention) > 0:
        status = EvaluationStatus.ATTENTION
        summary = "Outside the NASA intake requirements: " + ", ".join(attention) + "."
    elif evaluated > 0:
        status = EvaluationStatus.NOMINAL
        summary = "The logged intake meets the NASA requirements that could be evaluated."
    else:
        status = EvaluationStatus.INSUFFICIENT_DATA
        summary = "Not enough logged intake to evaluate nutrition."

    return EvaluationResult(
        evaluation_id=evaluation_id,
        crew_member_id=crew_member_id,
        domain=HealthDomain.NUTRITION,
        mission_phase=phase_at(window_start, mission_phases),
        window_start=window_start,
        window_end=window_end,
        status=status,
        summary=summary,
        findings=findings,
        # Logged by hand: no quality algorithm has assessed these values
        data_quality=DataQuality(status=QualityStatus.NOT_ASSESSED),
        algorithm=ALGORITHM,
        evaluated_at=evaluated_at,
    )
