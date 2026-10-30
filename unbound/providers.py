import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from .models import *


class ProviderConfigurationError(ValueError):
    pass


def check_provider(settings):
    load_dotenv()
    names = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    if settings.provider == "mock":
        return
    if settings.provider == "compatible":
        if not settings.api_key or not settings.base_url:
            raise ProviderConfigurationError(
                "Set UNBOUND_API_KEY and UNBOUND_BASE_URL for compatible provider"
            )
    elif settings.provider not in names:
        raise ProviderConfigurationError(
            "Unknown provider; choose openai, anthropic, compatible or explicit mock"
        )
    elif not os.getenv(names[settings.provider]):
        raise ProviderConfigurationError(
            f"Missing {names[settings.provider]} for selected live provider"
        )


class LiveProvider:
    def __init__(self, settings):
        check_provider(settings)
        self.settings = settings

    async def generate(self, task, context, schema):
        if self.settings.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            model = ChatAnthropic(
                model=self.settings.model, max_tokens=16000, max_retries=0
            )
        else:
            from langchain_openai import ChatOpenAI

            kwargs = {}
            if self.settings.provider == "compatible":
                kwargs.update(
                    api_key=self.settings.api_key, base_url=self.settings.base_url
                )
            model = ChatOpenAI(model=self.settings.model, max_retries=0, **kwargs)
        from .rules import RULES

        # JSON schema in prompt also works with compatible models lacking tool support.
        response = await model.ainvoke(
            [
                (
                    "system",
                    RULES
                    + "\nReturn only JSON matching this schema: "
                    + json.dumps(schema.model_json_schema()),
                ),
                (
                    "human",
                    json.dumps({"task": task, "context": context}, ensure_ascii=False),
                ),
            ]
        )
        content = response.content
        if not isinstance(content, str):
            content = "".join(x.get("text", "") for x in content if isinstance(x, dict))
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return schema.model_validate_json(content)


class MockProvider:
    """Deterministic contract fixture. NOT evidence of live creative performance."""

    async def generate(self, task, context, schema):
        await asyncio.sleep(
            0.02
        )  # Enables observable parallelism in offline demonstrations.
        if schema is Interpretation:
            text = context["input"].lower()
            business = any(
                w in text
                for w in (
                    "revenue",
                    "profit",
                    "business",
                    "commercial",
                    "startup",
                    "sell ",
                )
            )
            creative = any(
                w in text for w in ("creative", "art ", "story", "exploration")
            )
            return Interpretation(
                mode="HYBRID"
                if business and creative
                else "VENTURE"
                if business
                else "GENERAL",
                objective=context["input"],
                assumptions=["Offline mock fixture: outputs are not live ideation."],
                constraints=[],
                rationale="Explicit keyword fixture; live routing uses the configured model.",
            )
        if schema is NoveltyReview:
            return NoveltyReview(
                duplicate_ids=[],
                generic_ids=[],
                differentiation={
                    c["id"]: c["differentiation"] for c in context["concepts"]
                },
                notes=["Mock semantic review; not independent novelty evidence."],
            )
        if schema is ConceptBatch:
            stage = context.get("stage", "raw")
            count = context["count"]
            worker = context.get("worker", 0)
            lenses = context.get("lenses", LENSES)
            concepts = []
            # Forty distinct mechanism fixtures, as opposed to repeated renamed concepts.
            actions = [
                "partition resources by time windows",
                "route requests through rotating stewards",
                "pool idle capacity using reciprocal credits",
                "trigger regeneration after measured depletion",
                "sense local changes through distributed probes",
                "migrate work toward available capacity",
                "allocate scarce resources with sealed preference ballots",
                "unlock capabilities through cooperative milestones",
                "replace ownership with reversible access rights",
                "delay allocation until demand is observed",
                "compress handoffs into verifiable receipts",
                "exchange surplus across complementary participants",
                "split complex tasks into dependency trees",
                "combine low-resolution signals into consensus",
                "substitute waste streams for virgin inputs",
                "reverse the order of service and payment",
                "eliminate redundant approvals with scoped trust",
                "adapt fault isolation from cellular membranes",
                "modify interfaces using contextual constraints",
                "reuse completed artifacts as validation fixtures",
                "reduce commitments to expiring options",
                "raise transparency through signed provenance",
                "create opt-in mutual assistance pools",
                "resolve privacy utility tension through local aggregation",
                "coordinate without a central inventory using local signals",
                "rebuild failed components from redundant templates",
                "simulate alternative allocations before commitment",
                "make learning transferable through skill passports",
                "anticipate needs through consent-based schedules",
                "replace a product with an outcome verification ritual",
                "transfer ratchet mechanics into incremental commitment",
                "transfer capillary transport into demand-driven routing",
                "invert expertise by letting novices choose constraints",
                "make scarcity mandatory to expose substitution paths",
                "create a feedback loop rewarding shared maintenance",
                "compose agents with independent verification gates",
                "remove distance constraints then map back to asynchronous exchange",
                "impose zero storage to derive immediate reuse",
                "eliminate waiting through pre-authorized bounded decisions",
                "reallocate authority according to measured uncertainty",
            ]
            available = context.get("parents", [])
            for i in range(count):
                n = (worker * 10 + i) % len(actions)
                parents = (
                    []
                    if stage == "raw"
                    else [
                        p["id"]
                        for p in available[i % max(1, len(available)) :][
                            : 3 if stage == "hybrid" else 2
                        ]
                    ]
                )
                if stage != "raw" and len(parents) < (3 if stage == "hybrid" else 2):
                    parents = [
                        p["id"] for p in available[: 3 if stage == "hybrid" else 2]
                    ]
                commercial = None
                if context.get("mode") in ("VENTURE", "HYBRID"):
                    commercial = Commercial(
                        buyer="Participating operator (hypothesis)",
                        purchased_outcome="Reduced coordination delay",
                        price_model="Subscription hypothesis; amount unvalidated",
                        value_defense="Consent-based operational integration hypothesis",
                        automation_opportunity="Automate receipt validation with human exceptions",
                        revenue_assumptions=["Willingness to pay requires interviews"],
                    )
                mechanism = (
                    actions[n]
                    if stage == "raw"
                    else f"Recombine {', '.join(parents)} by {actions[(i + 20) % 40]} with a new conditional coordination layer {i + 1}"
                )
                concepts.append(
                    Concept(
                        name=f"Offline {stage} mechanism {worker * 10 + i + 1}",
                        mechanism=mechanism,
                        primary_technique=lenses[i % len(lenses)],
                        technique_detail="Fixture transfer of an operating property; multiple SCAMPER operations represented.",
                        parents=parents,
                        speculative=True,
                        differentiation=mechanism,
                        commercial=commercial,
                        category_shift="Coordination protocol replacing a service"
                        if stage == "meta"
                        else None,
                        transformative_potential="Unvalidated shared coordination hypothesis"
                        if stage == "meta"
                        else None,
                    )
                )
            return ConceptBatch(concepts=concepts)
        if schema is Wildcards:
            return Wildcards(
                wildcards=[
                    Wildcard(
                        idea_id=c["id"],
                        broken_assumption="Central coordination is necessary",
                        unexpected_mechanism=c["mechanism"],
                        useful_insight="Test whether local signals can coordinate safely",
                    )
                    for c in context["concepts"][:5]
                ]
            )
        if schema is Evaluation:
            out = []
            for i, c in enumerate(context["concepts"]):
                rubric = "VENTURE" if c.get("commercial") else "GENERAL"
                weights = VENTURE_WEIGHTS if rubric == "VENTURE" else GENERAL_WEIGHTS
                out.append(
                    Assessment(
                        concept_id=c["id"],
                        rubric=rubric,
                        scores={k: float(6 + i % 4) for k in weights},
                        rationale="Offline scoring fixture, not market evidence",
                        primary_risk="Coordination mechanism untested",
                        experiment="Compare coordination delay against baseline",
                        evidence_ids=[],
                        confidence="UNVALIDATED",
                        assumptions=["All outcomes require validation"],
                        uncertainty="No field observations",
                    )
                )
            return Evaluation(
                assessments=out,
                unconventional_candidate_id=context["concepts"][0]["id"],
                unconventional_justification="Keep an inverted coordination mechanism as a speculative test candidate",
            )
        if schema is Blueprint:
            return Blueprint(
                concept_id=context["best"]["id"],
                minimum_testable_version="Manual simulation with five consenting participants and explicit receipts",
                required_components=["Consent form", "Timer", "Receipt ledger"],
                implementation_sequence=[
                    "Define baseline",
                    "Recruit consenting participants",
                    "Run baseline and intervention",
                    "Compare measurements",
                ],
                validation_question="Does the defining mechanism reduce handoff delay?",
                success_metrics=[
                    "Median handoff delay at least 20% below measured baseline (experimental target)"
                ],
                stop_conditions=[
                    "Any consent withdrawal",
                    "No improvement after three trials",
                ],
                automation_design=[
                    Task(
                        description="Review participant consent",
                        classification="Human approval required",
                    ),
                    Task(
                        description="Aggregate timings", classification="Tool-executed"
                    ),
                ],
                next_action="Draft a reversible paper simulation",
                advantages=["Test mechanism before building infrastructure"],
                uncertainties=["Participant adoption unmeasured"],
            )
        raise ValueError("Unsupported fixture schema")


def make_provider(settings):
    check_provider(settings)
    return MockProvider() if settings.provider == "mock" else LiveProvider(settings)
