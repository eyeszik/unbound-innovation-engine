import json


def markdown(run):
    o = run["outputs"]
    c = {
        x["id"]: x
        for p in ("IDEAS_GENERATED", "HYBRIDS_GENERATED", "META_HYBRIDS_GENERATED")
        for x in o.get(p, {}).get("concepts", [])
    }
    lines = [
        "# UNBOUND INNOVATION ENGINE v3.0",
        f"Run: {run['id']} | Status: {run['status']} | Provider: {run['provider']} / {run['model']}",
        f"Contract: {run['contract_version']}",
    ]
    if run["provider"] == "mock":
        lines.append("**OFFLINE MOCK — not live inference or market validation.**")

    def section(title, content):
        lines.extend(["", f"## {title}", content])

    def pretty(value):
        return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"

    def concepts(phase):
        result = []
        for item in o.get(phase, {}).get("concepts", []):
            result.extend(
                [
                    f"### {item['id']} [{item['primary_technique']}] {item['name']}",
                    f"Mechanism: {item['mechanism']}",
                    f"Differentiation: {item['differentiation']}",
                    f"Technique: {item['technique_detail']}",
                ]
            )
            if item["parents"]:
                result.append("Parents: " + " + ".join(item["parents"]))
            if item["category_shift"]:
                result.append("Category shift: " + item["category_shift"])
            if item["transformative_potential"]:
                result.append(
                    "Transformative potential: " + item["transformative_potential"]
                )
            if item["speculative"]:
                result.append("**Speculative mechanism — unvalidated.**")
            if item["commercial"]:
                result.append(pretty(item["commercial"]))
        return "\n\n".join(result) or "Pending"

    section(
        "① INPUT INTERPRETATION",
        pretty({"original_input": run["input"], **o.get("INTENT_CLASSIFIED", {})}),
    )
    section("② RAW IDEA UNIVERSE", concepts("IDEAS_GENERATED"))
    section("③ FIVE WILDCARDS", pretty(o.get("WILDCARDS_IDENTIFIED", {})))
    section("④ FIRST-ORDER HYBRIDS", concepts("HYBRIDS_GENERATED"))
    section("⑤ SECOND-ORDER META-HYBRIDS", concepts("META_HYBRIDS_GENERATED"))
    shortlist = o.get("CANDIDATES_SCORED", {}).get("shortlist", [])
    ranked = []

    def lineage(cid):
        item = c[cid]
        return {"id": cid, "parents": [lineage(p) for p in item["parents"]]}

    for rank, a in enumerate(shortlist, 1):
        ranked.append(
            {
                "rank": rank,
                "concept": c[a["concept_id"]],
                "lineage": lineage(a["concept_id"]),
                **a,
            }
        )
    section(
        "⑥ FINAL SHORTLIST",
        pretty(
            {
                "ranked": ranked,
                "weighting": o.get("CANDIDATES_SCORED", {}).get(
                    "weighting_explanation"
                ),
                "rubrics": o.get("CANDIDATES_SCORED", {}).get("rubrics"),
                "unconventional_retention": o.get("CANDIDATES_SCORED", {}).get(
                    "unconventional_justification"
                ),
            }
        ),
    )
    section(
        "⑦ RECOMMENDED INNOVATION",
        pretty(
            {
                "candidate": ranked[0] if ranked else None,
                "advantages": o.get("EXPERIMENT_DEFINED", {}).get("advantages", []),
                "uncertainties": o.get("EXPERIMENT_DEFINED", {}).get(
                    "uncertainties", []
                ),
            }
        ),
    )
    section("⑧ EXECUTION BLUEPRINT", pretty(o.get("EXPERIMENT_DEFINED", {})))
    section(
        "⑨ VALIDATION SUMMARY",
        pretty(
            {
                "validation": o.get(
                    "OUTPUT_VALIDATED", {"passed": False, "status": "PENDING"}
                ),
                "research": o.get("EVIDENCE_REVIEWED", {}),
                "error": run["error"],
            }
        ),
    )
    return "\n\n".join(lines) + "\n"
