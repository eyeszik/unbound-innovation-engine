import asyncio
import json
import time
import pytest
from unbound.engine import Engine, EngineError, duplicate_ids
from unbound.models import *
from unbound.providers import MockProvider, check_provider, ProviderConfigurationError
from unbound.settings import Settings
from unbound.store import Store
from unbound.worker import process_once


@pytest.fixture
def setup(tmp_path):
    s = Settings(
        provider="mock",
        model="mock-v1",
        db=str(tmp_path / "runs.db"),
        checkpoint_db=str(tmp_path / "graph.db"),
        attempts=2,
        call_timeout=5,
    )
    s.prepare()
    return s, Store(s.db)


async def run_fixture(
    setup, mode="AUTO", provider=None, input="Improve a neighborhood library"
):
    s, db = setup
    rid = db.create(
        RunInput(
            input=input, configuration=Configuration(mode=mode, research="DISABLED")
        ),
        s.provider,
        s.model,
    )
    await process_once(db, provider or MockProvider(), s)
    return db.get(rid)


@pytest.mark.parametrize(
    "text,mode",
    [
        ("Explore library access", "GENERAL"),
        ("Build a profitable business", "VENTURE"),
        ("Creative art business", "HYBRID"),
    ],
)
async def test_intent(text, mode):
    r = await MockProvider().generate("intent", {"input": text}, Interpretation)
    assert r.mode == mode


@pytest.mark.parametrize("mode", ["GENERAL", "VENTURE", "HYBRID"])
async def test_full_contract(setup, mode):
    r = await run_fixture(setup, mode)
    assert r["status"] == "COMPLETED", r["error"]
    assert list(r["outputs"]) == PHASES[1:]
    v = r["outputs"]["OUTPUT_VALIDATED"]
    assert (
        v["passed"]
        and v["raw_count"] == 35
        and v["hybrid_count"] == 5
        and v["meta_count"] == 3
    )
    assert set(v["technique_coverage"]) == set(LENSES)
    assert len(r["outputs"]["CANDIDATES_SCORED"]["shortlist"]) == 5
    assert v["mock_only"]


async def test_parallelism_and_evaluation_isolation(setup):
    class Spy(MockProvider):
        active = 0
        peak = 0
        calls = []

        async def generate(self, task, context, schema):
            self.calls.append((task, context, schema))
            if context.get("stage") == "raw":
                assert not any(
                    k in context for k in ("evidence", "assessments", "scores")
                )
                self.active += 1
                self.peak = max(self.peak, self.active)
                await asyncio.sleep(0.02)
                self.active -= 1
            return await super().generate(task, context, schema)

    p = Spy()
    r = await run_fixture(setup, provider=p)
    assert r["status"] == "COMPLETED", r["error"]
    assert p.peak == 4
    schemas = [x[2] for x in p.calls]
    assert schemas.index(Evaluation) > max(
        i for i, s in enumerate(schemas) if s is ConceptBatch
    )


def test_duplicate_detection():
    assert duplicate_ids(
        [
            {"id": "I01", "mechanism": "Share surplus by time slots"},
            {"id": "I02", "mechanism": "Share surplus by time slots!"},
        ]
    ) == ["I02"]


async def test_failure_retry_recovery_without_duplicates(setup):
    class Broken(MockProvider):
        async def generate(self, task, context, schema):
            if schema is Wildcards:
                raise RuntimeError("secret-api-key-must-not-be-logged")
            return await super().generate(task, context, schema)

    s, db = setup
    r = await run_fixture(setup, provider=Broken())
    assert r["status"] == "FAILED"
    before = r["outputs"]["IDEAS_GENERATED"]
    assert "secret-api-key" not in json.dumps(r)
    assert db.retry(r["id"])
    await process_once(db, MockProvider(), s)
    after = db.get(r["id"])
    assert after["status"] == "COMPLETED", after["error"]
    assert before == after["outputs"]["IDEAS_GENERATED"]
    with db.connect() as c:
        assert (
            c.execute(
                "SELECT count(*) FROM outputs WHERE run_id=?", (r["id"],)
            ).fetchone()[0]
            == 9
        )


async def test_schema_repair_and_bounded_retries(setup):
    class Flaky(MockProvider):
        count = 0

        async def generate(self, task, context, schema):
            if schema is Wildcards:
                self.count += 1
                if self.count == 1:
                    return Wildcards(wildcards=[])
            return await super().generate(task, context, schema)

    p = Flaky()
    r = await run_fixture(setup, provider=p)
    assert r["status"] == "COMPLETED", r["error"]
    assert p.count == 2


async def test_timeout(setup):
    s, db = setup
    s.call_timeout = 0.001
    r = await run_fixture(setup)
    assert r["status"] == "FAILED" and "TimeoutError" in r["error"]


def test_phase_order_and_leases(setup):
    s, db = setup
    rid = db.create(RunInput(input="Test concept"), s.provider, s.model)
    assert db.claim("one", s.provider, s.model) == rid
    assert db.claim("two", s.provider, s.model) is None
    with pytest.raises(ValueError, match="ordering"):
        db.commit_phase(rid, "IDEAS_GENERATED", {}, "one")
    with pytest.raises(RuntimeError, match="lease"):
        db.commit_phase(rid, "INTENT_CLASSIFIED", {}, "two")
    with db.connect() as c:
        c.execute("UPDATE runs SET lease_until=0 WHERE id=?", (rid,))
    assert db.claim("two", s.provider, s.model) == rid
    assert not db.heartbeat(rid, "one")


async def test_graph_sqlite_checkpoints(setup):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    s, db = setup
    rid = db.create(
        RunInput(
            input="Durable library access",
            configuration=Configuration(research="DISABLED"),
        ),
        s.provider,
        s.model,
    )
    async with AsyncSqliteSaver.from_conn_string(s.checkpoint_db) as saver:
        await process_once(db, MockProvider(), s, saver)
        checkpoint = await saver.aget_tuple({"configurable": {"thread_id": rid}})
        assert checkpoint is not None
    assert Store(s.db).get(rid)["status"] == "COMPLETED"


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        check_provider(Settings(provider="openai"))


async def test_lineage_repair(setup):
    class BadParents(MockProvider):
        async def generate(self, task, context, schema):
            r = await super().generate(task, context, schema)
            if context.get("stage") == "hybrid":
                r.concepts[0].parents = ["I999"]
            return r

    r = await run_fixture(setup, provider=BadParents())
    assert r["status"] == "FAILED" and r["phase"] == "WILDCARDS_IDENTIFIED"


async def test_coverage_repair_exhaustion(setup):
    class NoCoverage(MockProvider):
        async def generate(self, task, context, schema):
            if schema is NoveltyReview:
                return NoveltyReview(
                    duplicate_ids=[],
                    generic_ids=[c["id"] for c in context["concepts"]],
                    differentiation={},
                    notes=[],
                )
            return await super().generate(task, context, schema)

    r = await run_fixture(setup, provider=NoCoverage())
    assert r["status"] == "FAILED" and "bounded repairs" in r["error"]
