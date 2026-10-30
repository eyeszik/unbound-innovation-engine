import pytest
from unbound.research import research, compute
from unbound.models import *
from unbound.engine import score_assessments, EngineError
from unbound.providers import MockProvider


async def test_optional_tools_without_credentials(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("WOLFRAM_APP_ID", raising=False)
    r = await research("Library coordination", "GENERAL", "AUTO")
    assert r["status"] == "UNAVAILABLE" and r["evidence"] == [] and r["questions"]
    assert (await research("Library", "GENERAL", "DISABLED"))["status"] == "DISABLED"
    assert (await compute("2+2"))["status"] == "UNAVAILABLE"


async def test_score_arithmetic_and_evidence_guards():
    p = MockProvider()
    batch = await p.generate("", {"count": 5, "stage": "raw"}, ConceptBatch)
    concepts = [
        {**c.model_dump(), "id": f"I{i + 1:02}"} for i, c in enumerate(batch.concepts)
    ]
    e = await p.generate("", {"concepts": concepts}, Evaluation)
    r = score_assessments(e, concepts, [])
    a = r["assessments"][0]
    assert a["composite"] == 6.0
    e.assessments[0].confidence = "EVIDENCE_AVAILABLE"
    with pytest.raises(EngineError, match="confidence"):
        score_assessments(e, concepts, [])
    e.assessments[0].confidence = "UNVALIDATED"
    e.assessments[0].scores["novelty"] = 11
    with pytest.raises(EngineError, match="1–10"):
        score_assessments(e, concepts, [])


async def test_research_retrieval_and_failure_are_honest(monkeypatch):
    import httpx
    import unbound.research as module

    original = httpx.AsyncClient
    monkeypatch.setenv("EXA_API_KEY", "fixture-only")

    def handler(request):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/paper",
                        "title": "Published analogue",
                        "text": "An analogous mechanism.",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    r = await research("Library", "GENERAL", "ENABLED")
    assert r["status"] == "RETRIEVED"
    assert all(e["status"] == "RETRIEVED" and e["retrieved_at"] for e in r["evidence"])

    def failure(request):
        return httpx.Response(
            401, json={"error": "fixture-only secret must not escape"}
        )

    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(failure), **kw),
    )
    r = await research("Library", "GENERAL", "ENABLED")
    assert r["status"] == "UNAVAILABLE"
    assert "fixture-only" not in str(r)
