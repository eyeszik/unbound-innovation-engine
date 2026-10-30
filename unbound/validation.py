from .models import PHASES, LENSES, GENERAL_WEIGHTS, VENTURE_WEIGHTS
from .engine import duplicate_ids


def validate_run(run):
    o = run["outputs"]
    cfg = run["configuration"]
    mode = o["INTENT_CLASSIFIED"]["mode"]
    raw = o["IDEAS_GENERATED"]["concepts"]
    hybrids = o["HYBRIDS_GENERATED"]["concepts"]
    meta = o["META_HYBRIDS_GENERATED"]["concepts"]
    all_c = raw + hybrids + meta
    ids = {c["id"] for c in all_c}
    w = o["WILDCARDS_IDENTIFIED"]["wildcards"]
    evaluation = o["CANDIDATES_SCORED"]
    short = evaluation["shortlist"]
    blueprint = o["EXPERIMENT_DEFINED"]
    gates = {
        "intent_classified": mode in ("GENERAL", "VENTURE", "HYBRID"),
        "minimum_distinct_ideas": len(raw) >= cfg["idea_count"]
        and not duplicate_ids(raw),
        "all_twelve_lenses": {c["primary_technique"] for c in raw} == set(LENSES),
        "five_wildcards": len(w) == 5
        and len({x["idea_id"] for x in w}) == 5
        and {x["idea_id"] for x in w} <= {c["id"] for c in raw},
        "hybrid_count": len(hybrids) == cfg["hybrids"],
        "meta_count": len(meta) == cfg["meta_hybrids"],
        "unique_ids": len(ids) == len(all_c),
        "lineage": all(
            3 <= len(set(c["parents"])) <= 4
            and set(c["parents"]) <= {x["id"] for x in raw}
            for c in hybrids
        )
        and all(
            2 <= len(set(c["parents"])) <= 3
            and set(c["parents"]) <= {x["id"] for x in hybrids}
            for c in meta
        ),
        "no_premature_scores": all(
            not any(
                k in c for k in ("scores", "composite", "confidence", "feasibility")
            )
            for c in all_c
        ),
        "mode_commercial_fields": all(not c["commercial"] for c in all_c)
        if mode == "GENERAL"
        else all(c["commercial"] for c in all_c)
        if mode == "VENTURE"
        else True,
        "five_ranked": len(short) == 5
        and len({a["concept_id"] for a in short}) == 5
        and {a["concept_id"] for a in short} <= ids,
        "all_candidates_evaluated": len(evaluation["assessments"]) == len(ids)
        and {a["concept_id"] for a in evaluation["assessments"]} == ids,
        "blueprint_complete": blueprint["concept_id"] == short[0]["concept_id"]
        and all(
            blueprint[k]
            for k in (
                "minimum_testable_version",
                "required_components",
                "implementation_sequence",
                "validation_question",
                "success_metrics",
                "stop_conditions",
                "automation_design",
                "next_action",
            )
        ),
        "phase_order": list(o) == PHASES[1:-1],
        "research_status": o["EVIDENCE_REVIEWED"]["status"]
        in ("DISABLED", "UNAVAILABLE", "RETRIEVED"),
        "confidence_qualified": all(
            a["confidence"] == "UNVALIDATED"
            or (
                a["evidence_ids"]
                and a["predicted_outcome"]
                and a["time_horizon"]
                and a["assumptions"]
                and a["uncertainty"]
            )
            for a in evaluation["assessments"]
        ),
    }
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "raw_count": len(raw),
        "hybrid_count": len(hybrids),
        "meta_count": len(meta),
        "technique_coverage": sorted({c["primary_technique"] for c in raw}),
        "duplicate_exclusions": o["IDEAS_GENERATED"]["exclusions"],
        "research_status": o["EVIDENCE_REVIEWED"]["status"],
        "unverified_assumptions": o["INTENT_CLASSIFIED"]["assumptions"]
        + o["EVIDENCE_REVIEWED"].get("questions", []),
        "limitations": [
            "Structural validation does not establish real-world novelty, feasibility, safety or demand.",
            "Semantic distinctness and category filtering use model review plus conservative text similarity; owner review remains necessary.",
        ],
        "provider": run["provider"],
        "mock_only": run["provider"] == "mock",
    }
