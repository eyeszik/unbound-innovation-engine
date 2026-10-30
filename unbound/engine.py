import asyncio
import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .models import *
from .research import research, compute
from .rules import VERSION


class EngineError(RuntimeError):
    pass


class GraphState(TypedDict):
    run_id: str
    phase: str


def duplicate_ids(concepts):
    seen = []
    duplicates = []
    for c in concepts:
        normalized = re.sub(r"\W+", " ", c["mechanism"].lower()).strip()
        if any(
            normalized == s or SequenceMatcher(None, normalized, s).ratio() > 0.94
            for s in seen
        ):
            duplicates.append(c["id"])
        else:
            seen.append(normalized)
    return duplicates


def score_assessments(evaluation, concepts, evidence):
    candidates = {c["id"]: c for c in concepts}
    assessments = evaluation.model_dump()["assessments"]
    if len(assessments) != len(candidates) or {
        a["concept_id"] for a in assessments
    } != set(candidates):
        raise EngineError("Evaluator must assess every eligible concept exactly once")
    evidence_ids = {e["id"] for e in evidence if e["status"] == "RETRIEVED"}
    for a in assessments:
        expected = "VENTURE" if candidates[a["concept_id"]]["commercial"] else "GENERAL"
        weights = VENTURE_WEIGHTS if expected == "VENTURE" else GENERAL_WEIGHTS
        if a["rubric"] != expected or set(a["scores"]) != set(weights):
            raise EngineError("Scoring rubric does not match concept mode")
        if any(not 1 <= v <= 10 for v in a["scores"].values()):
            raise EngineError("Scores must be within 1–10")
        if not set(a["evidence_ids"]) <= evidence_ids:
            raise EngineError("Unknown or unavailable evidence cited")
        if a["confidence"] == "EVIDENCE_AVAILABLE" and not (
            a["evidence_ids"]
            and a["predicted_outcome"]
            and a["time_horizon"]
            and a["uncertainty"]
            and a["assumptions"]
        ):
            raise EngineError(
                "Evidence-qualified confidence requires outcome, horizon, assumptions and cited evidence"
            )
        a["composite"] = round(sum(a["scores"][k] * w for k, w in weights.items()), 3)
    ranked = sorted(assessments, key=lambda a: (-a["composite"], a["concept_id"]))
    chosen = ranked[:5]
    special = evaluation.unconventional_candidate_id
    if special not in candidates or not evaluation.unconventional_justification.strip():
        raise EngineError("Unconventional candidate and justification required")
    if special not in {a["concept_id"] for a in chosen}:
        chosen = chosen[:4] + [next(a for a in ranked if a["concept_id"] == special)]
    return {
        "assessments": assessments,
        "shortlist": chosen,
        "rubrics": {"GENERAL": GENERAL_WEIGHTS, "VENTURE": VENTURE_WEIGHTS},
        "weighting_explanation": "Creative concepts use GENERAL; explicitly commercial concepts use VENTURE. HYBRID compares normalized 1–10 composites; unconventional retention may override pure score order.",
        "unconventional_candidate_id": special,
        "unconventional_justification": evaluation.unconventional_justification,
    }


class Engine:
    def __init__(self, store, provider, settings, owner):
        self.store = store
        self.provider = provider
        self.settings = settings
        self.owner = owner

    async def ask(self, rid, key, task, context, schema, validator=None):
        cached = self.store.cache(rid, key)
        if cached is not None:
            return schema.model_validate(cached)
        for attempt in range(self.settings.attempts):
            self.store.event(rid, key, key, "RUNNING", f"Attempt {attempt + 1}")
            try:
                result = await asyncio.wait_for(
                    self.provider.generate(task, context, schema),
                    timeout=self.settings.call_timeout,
                )
                result = schema.model_validate(result)
                if validator:
                    validator(result)
                self.store.cache(rid, key, result.model_dump(mode="json"))
                self.store.event(
                    rid, key, key, "COMPLETED", "Structured output accepted"
                )
                return result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Never persist exception text: SDK errors can include credentials or prompts.
                self.store.event(
                    rid,
                    key,
                    key,
                    "RETRY" if attempt + 1 < self.settings.attempts else "FAILED",
                    f"{type(exc).__name__}: response rejected or provider unavailable; inspect configuration and retry",
                )
                if attempt + 1 == self.settings.attempts:
                    raise EngineError(
                        f"{key} failed after {self.settings.attempts} attempts ({type(exc).__name__}); check credentials, model availability, connectivity and output contract"
                    ) from None
                context = {
                    **context,
                    "repair_instruction": "Previous attempt failed structural or phase contract validation. Recheck exact count, lineage, commercial fields, lens assignment and requested schema; do not add scoring to creative phases.",
                }
                await asyncio.sleep(min(2**attempt, 8))
        raise EngineError("Unreachable retry state")

    async def execute_phase(self, rid, phase):
        run = self.store.get(rid)
        out = run["outputs"]
        cfg = run["configuration"]
        base = {"input": run["input"], "configuration": cfg}
        interpretation = out.get("INTENT_CLASSIFIED", {})
        mode = interpretation.get("mode", cfg["mode"])
        base.update(mode=mode, interpretation=interpretation)
        if phase == "INTENT_CLASSIFIED":
            result = await self.ask(
                rid,
                "intent",
                "Classify intent; ambiguous AUTO must be GENERAL. Honor an explicit selected mode. Explain objective, assumptions and constraints.",
                base,
                Interpretation,
            )
            value = result.model_dump()
            if cfg["mode"] != "AUTO":
                value["mode"] = cfg["mode"]
                value["rationale"] = "Explicit user mode. " + value["rationale"]
            return value
        if phase == "IDEAS_GENERATED":

            async def generate(worker, count, lenses, key, avoid=None):
                def valid(batch):
                    if len(batch.concepts) < count:
                        raise ValueError("Insufficient worker candidates")
                    for c in batch.concepts:
                        if c.primary_technique not in lenses or c.parents:
                            raise ValueError("Invalid raw lens or lineage")
                        if mode == "GENERAL" and c.commercial:
                            raise ValueError("Unsolicited monetization")
                        if mode == "VENTURE" and not c.commercial:
                            raise ValueError("Missing commercial fields")

                ctx = {
                    **base,
                    "stage": "raw",
                    "worker": worker,
                    "count": count,
                    "lenses": lenses,
                    "existing_mechanisms_to_avoid": avoid or [],
                }
                return await self.ask(
                    rid,
                    key,
                    "Generate independent distinct mechanisms using assigned primary lenses. Use multiple SCAMPER operations. No evaluation or feasibility ranking. No scores. Every commercial idea needs commercial fields. Treat speculation honestly.",
                    ctx,
                    ConceptBatch,
                    valid,
                )

            count = max(10, (cfg["idea_count"] + 3) // 4)
            batches = await asyncio.gather(
                *(
                    generate(i, count, LENSES[i * 3 : i * 3 + 3], f"creative-{i}")
                    for i in range(4)
                )
            )
            candidates = []
            exclusions = []

            def append(batch):
                for concept in batch.concepts:
                    c = concept.model_dump()
                    c["id"] = f"I{len(candidates) + 1:02}"
                    candidates.append(c)

            for batch in batches:
                append(batch)
            for repair in range(self.settings.attempts):

                def review_valid(r):
                    ids = {c["id"] for c in candidates}
                    if not set(r.duplicate_ids + r.generic_ids) <= ids:
                        raise ValueError("Unknown excluded ID")

                review = await self.ask(
                    rid,
                    f"novelty-{repair}",
                    "Identify duplicate mechanisms and domain-generic or banned concepts. Return diversity matrix explanations; do not score or evaluate feasibility.",
                    {**base, "concepts": candidates},
                    NoveltyReview,
                    review_valid,
                )
                rejected = set(
                    duplicate_ids(candidates)
                    + review.duplicate_ids
                    + review.generic_ids
                )
                valid = [c for c in candidates if c["id"] not in rejected]
                exclusions.extend(
                    {
                        "id": c["id"],
                        "reason": "Mechanism overlap or generic/category banlist",
                    }
                    for c in candidates
                    if c["id"] in rejected
                )
                # Coverage-first retention, then original generation order.
                selected = []
                for lens in LENSES:
                    match = next(
                        (c for c in valid if c["primary_technique"] == lens), None
                    )
                    if match and match not in selected:
                        selected.append(match)
                for c in valid:
                    if len(selected) >= cfg["idea_count"]:
                        break
                    if c not in selected:
                        selected.append(c)
                missing = [
                    l
                    for l in LENSES
                    if l not in {c["primary_technique"] for c in selected}
                ]
                if len(selected) >= cfg["idea_count"] and not missing:
                    return {
                        "concepts": selected,
                        "coverage": {
                            l: [
                                c["id"] for c in selected if c["primary_technique"] == l
                            ]
                            for l in LENSES
                        },
                        "exclusions": exclusions,
                        "diversity_matrix": review.differentiation,
                        "novelty_notes": review.notes,
                        "semantic_review": "MOCK_ONLY"
                        if run["provider"] == "mock"
                        else "MODEL_REVIEW_NOT_GLOBAL_NOVELTY_PROOF",
                    }
                if repair + 1 < self.settings.attempts:
                    extra = await generate(
                        4 + repair,
                        max(4, cfg["idea_count"] - len(selected) + len(missing)),
                        missing or LENSES,
                        f"creative-repair-{repair}",
                        [c["mechanism"] for c in candidates],
                    )
                    append(extra)
            raise EngineError(
                "Distinct count or lens coverage failed after bounded repairs"
            )
        raw = out["IDEAS_GENERATED"]["concepts"]
        if phase == "WILDCARDS_IDENTIFIED":

            def valid(w):
                ids = [x.idea_id for x in w.wildcards]
                if (
                    len(ids) != 5
                    or len(set(ids)) != 5
                    or not set(ids) <= {c["id"] for c in raw}
                ):
                    raise ValueError("Five unique raw wildcards required")

            return (
                await self.ask(
                    rid,
                    "wildcards",
                    "Extract five unconventional seeds; no feasibility rejection. Describe broken assumption, unexpected mechanism and useful insight.",
                    {**base, "concepts": raw},
                    Wildcards,
                    valid,
                )
            ).model_dump()
        if phase in ("HYBRIDS_GENERATED", "META_HYBRIDS_GENERATED"):
            meta = phase == "META_HYBRIDS_GENERATED"
            parents = out["HYBRIDS_GENERATED"]["concepts"] if meta else raw
            n = cfg["meta_hybrids" if meta else "hybrids"]
            prefix = "M" if meta else "H"

            def valid(batch):
                if len(batch.concepts) != n:
                    raise ValueError("Incorrect synthesis count")
                for c in batch.concepts:
                    if (
                        not (2 if meta else 3)
                        <= len(set(c.parents))
                        <= (3 if meta else 4)
                        or len(set(c.parents)) != len(c.parents)
                        or not set(c.parents) <= {p["id"] for p in parents}
                    ):
                        raise ValueError("Invalid lineage")
                    if mode == "GENERAL" and c.commercial:
                        raise ValueError("Unsolicited commercialization")
                    if mode == "VENTURE" and not c.commercial:
                        raise ValueError("Missing commercial fields")
                    if meta and not (c.category_shift and c.transformative_potential):
                        raise ValueError("Meta category shift missing")

            batch = await self.ask(
                rid,
                prefix + "-synthesis",
                "Create genuinely emergent mechanisms, not feature bundles. No scoring. Preserve parent IDs. Meta concepts require changed category/architecture and transformative potential.",
                {
                    **base,
                    "stage": "meta" if meta else "hybrid",
                    "count": n,
                    "parents": parents,
                },
                ConceptBatch,
                valid,
            )
            concepts = [
                {**c.model_dump(), "id": f"{prefix}{i + 1:02}"}
                for i, c in enumerate(batch.concepts)
            ]
            return {"concepts": concepts}
        if phase == "EVIDENCE_REVIEWED":
            result = await research(run["input"], mode, cfg["research"])
            result["computations"] = []
            if cfg["research"] != "DISABLED":
                for query in cfg.get("computation_queries", []):
                    result["computations"].append(
                        {"query": query, **await compute(query)}
                    )
            return result
        all_concepts = (
            raw
            + out["HYBRIDS_GENERATED"]["concepts"]
            + out["META_HYBRIDS_GENERATED"]["concepts"]
        )
        if phase == "CANDIDATES_SCORED":
            evidence = out["EVIDENCE_REVIEWED"]

            def valid(e):
                score_assessments(e, all_concepts, evidence["evidence"])

            evaluation = await self.ask(
                rid,
                "evaluation",
                "Evaluate ALL eligible concepts exactly once, only now. Use GENERAL rubric for noncommercial concepts, VENTURE for commercial. Scores 1–10 with exact rubric keys. Separate quality from evidence and outcomes; numeric success probabilities forbidden. Identify one unconventional high-upside candidate and justify retention. Do not invent economic evidence.",
                {
                    **base,
                    "concepts": all_concepts,
                    "evidence": evidence,
                    "rubrics": {"GENERAL": GENERAL_WEIGHTS, "VENTURE": VENTURE_WEIGHTS},
                },
                Evaluation,
                valid,
            )
            return score_assessments(evaluation, all_concepts, evidence["evidence"])
        if phase == "EXPERIMENT_DEFINED":
            best_id = out["CANDIDATES_SCORED"]["shortlist"][0]["concept_id"]
            best = next(c for c in all_concepts if c["id"] == best_id)

            def valid(b):
                if b.concept_id != best_id or not all(
                    [
                        b.required_components,
                        b.implementation_sequence,
                        b.success_metrics,
                        b.stop_conditions,
                        b.automation_design,
                        b.next_action,
                    ]
                ):
                    raise ValueError("Incomplete blueprint")

            return (
                await self.ask(
                    rid,
                    "blueprint",
                    "Produce minimum authentic mechanism test, dependencies, dependency-aware sequence, decisive question, measurable success thresholds (targets, not predictions), stop conditions, task automation classification and immediate reversible next action. Do not claim experiment execution.",
                    {
                        **base,
                        "best": best,
                        "assessment": out["CANDIDATES_SCORED"]["shortlist"][0],
                    },
                    Blueprint,
                    valid,
                )
            ).model_dump()
        if phase == "OUTPUT_VALIDATED":
            from .validation import validate_run

            value = validate_run(run)
            self.store.cache(rid, "validation-results", value)
            if not value["passed"]:
                raise EngineError(
                    "Final validation failed: "
                    + ", ".join(k for k, v in value["gates"].items() if not v)
                )
            return value
        raise EngineError("Unknown phase")

    def graph(self, checkpointer=None):
        graph = StateGraph(GraphState)
        previous = START
        for phase in PHASES[1:]:

            def node_factory(p):
                async def node(state):
                    run = self.store.get(state["run_id"])
                    if p not in run["outputs"]:
                        result = await self.execute_phase(state["run_id"], p)
                        self.store.commit_phase(state["run_id"], p, result, self.owner)
                    return {"phase": p}

                return node

            graph.add_node(phase, node_factory(phase))
            graph.add_edge(previous, phase)
            previous = phase
        graph.add_edge(previous, END)
        return graph.compile(checkpointer=checkpointer)
