from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Mode(StrEnum):
    AUTO = "AUTO"
    GENERAL = "GENERAL"
    VENTURE = "VENTURE"
    HYBRID = "HYBRID"


LENSES = [
    "SCAMPER",
    "BLUE_OCEAN",
    "TRIZ",
    "BIOMIMICRY",
    "GAME_DESIGN",
    "HOSPITALITY_LOYALTY",
    "JTBD",
    "RANDOM_MECHANICAL",
    "COUNTERFACTUAL",
    "SYSTEMS_NETWORKS",
    "AI_NATIVE",
    "CONSTRAINT_REMOVAL",
]
PHASES = [
    "INPUT_RECEIVED",
    "INTENT_CLASSIFIED",
    "IDEAS_GENERATED",
    "WILDCARDS_IDENTIFIED",
    "HYBRIDS_GENERATED",
    "META_HYBRIDS_GENERATED",
    "EVIDENCE_REVIEWED",
    "CANDIDATES_SCORED",
    "EXPERIMENT_DEFINED",
    "OUTPUT_VALIDATED",
]
GENERAL_WEIGHTS = dict(
    novelty=0.30, impact=0.25, coherence=0.20, adaptability=0.15, readiness=0.10
)
VENTURE_WEIGHTS = dict(
    novelty=0.25,
    profit=0.25,
    automation=0.15,
    defensibility=0.15,
    market=0.10,
    readiness=0.10,
)


class Configuration(Strict):
    mode: Mode = Mode.AUTO
    idea_count: int = Field(35, ge=35, le=100)
    wildcards: Literal[5] = 5
    hybrids: int = Field(5, ge=4, le=5)
    meta_hybrids: int = Field(3, ge=2, le=3)
    shortlist: Literal[5] = 5
    novelty_target: str = "HIGH"
    automation_priority: str = "CONTEXTUAL"
    research: Literal["AUTO", "ENABLED", "DISABLED"] = "AUTO"
    risk_tolerance: str = "SPECULATIVE_EXPLORATION"
    output_detail: Literal["COMPACT", "STANDARD", "EXTENDED"] = "STANDARD"
    time_horizon: str = "CONTEXTUAL"
    budget: str = "UNSPECIFIED"
    technology_stack: str = "CONTEXTUAL"
    target_market: str = "CONTEXTUAL"
    computation_queries: list[str] = Field(default_factory=list, max_length=3)


class RunInput(Strict):
    input: str = Field(min_length=3, max_length=20000)
    configuration: Configuration = Field(default_factory=Configuration)


class Interpretation(Strict):
    mode: Literal["GENERAL", "VENTURE", "HYBRID"]
    objective: str
    assumptions: list[str]
    constraints: list[str]
    rationale: str


class Commercial(Strict):
    buyer: str
    purchased_outcome: str
    price_model: str
    value_defense: str
    automation_opportunity: str
    revenue_assumptions: list[str]


class Concept(Strict):
    id: str = ""
    name: str
    mechanism: str
    primary_technique: Literal[
        "SCAMPER",
        "BLUE_OCEAN",
        "TRIZ",
        "BIOMIMICRY",
        "GAME_DESIGN",
        "HOSPITALITY_LOYALTY",
        "JTBD",
        "RANDOM_MECHANICAL",
        "COUNTERFACTUAL",
        "SYSTEMS_NETWORKS",
        "AI_NATIVE",
        "CONSTRAINT_REMOVAL",
    ]
    technique_detail: str
    parents: list[str] = Field(default_factory=list)
    speculative: bool
    differentiation: str
    commercial: Commercial | None = None
    category_shift: str | None = None
    transformative_potential: str | None = None


class ConceptBatch(Strict):
    concepts: list[Concept]


class Wildcard(Strict):
    idea_id: str
    broken_assumption: str
    unexpected_mechanism: str
    useful_insight: str


class Wildcards(Strict):
    wildcards: list[Wildcard]


class NoveltyReview(Strict):
    duplicate_ids: list[str]
    generic_ids: list[str]
    differentiation: dict[str, str]
    notes: list[str]


class Evidence(Strict):
    id: str
    claim: str
    url: str | None = None
    retrieved_at: str | None = None
    status: Literal["RETRIEVED", "UNVERIFIED", "CONTRADICTED"]
    excerpt: str
    limitations: str


class Assessment(Strict):
    concept_id: str
    rubric: Literal["GENERAL", "VENTURE"]
    scores: dict[str, float]
    rationale: str
    primary_risk: str
    experiment: str
    evidence_ids: list[str]
    confidence: Literal["UNVALIDATED", "EVIDENCE_AVAILABLE"]
    predicted_outcome: str | None = None
    time_horizon: str | None = None
    assumptions: list[str]
    uncertainty: str
    composite: float = 0


class Evaluation(Strict):
    assessments: list[Assessment]
    unconventional_candidate_id: str
    unconventional_justification: str


class Task(Strict):
    description: str
    classification: Literal[
        "Human judgment",
        "AI-assisted",
        "Tool-executed",
        "Scheduled automation",
        "Human approval required",
    ]


class Blueprint(Strict):
    concept_id: str
    minimum_testable_version: str
    required_components: list[str]
    implementation_sequence: list[str]
    validation_question: str
    success_metrics: list[str]
    stop_conditions: list[str]
    automation_design: list[Task]
    next_action: str
    advantages: list[str]
    uncertainties: list[str]
