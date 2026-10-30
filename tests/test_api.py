import base64
import pytest
from fastapi.testclient import TestClient
from unbound.api import create_app
from unbound.settings import Settings
from unbound.worker import process_once
from unbound.providers import MockProvider
from unbound.export import markdown


@pytest.fixture
def app(tmp_path):
    return create_app(
        Settings(
            provider="mock",
            model="mock-v1",
            db=str(tmp_path / "run.db"),
            checkpoint_db=str(tmp_path / "cp.db"),
        )
    )


async def test_api_run_export(app):
    with TestClient(app) as c:
        assert c.get("/health").json()["mock"]
        assert c.get("/").status_code == 200
        assert c.get("/static/app.js").status_code == 200
        r = c.post(
            "/runs",
            json={
                "input": "Explore library sharing",
                "configuration": {"research": "DISABLED"},
            },
        )
        assert r.status_code == 202
        rid = r.json()["run_id"]
        assert not c.get(f"/runs/{rid}/results").json()["complete"]
        await process_once(app.state.store, MockProvider(), app.state.settings)
        run = c.get(f"/runs/{rid}").json()
        assert run["status"] == "COMPLETED", run["error"]
        assert c.get(f"/runs/{rid}/results").json()["complete"]
        assert c.get(f"/runs/{rid}/export.json").json()["id"] == rid
        md = c.get(f"/runs/{rid}/export.md").text
        for title in ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"]:
            assert title in md
        assert md.index("①") < md.index("②") < md.index("⑨")
        assert "OFFLINE MOCK" in md
        assert c.post(f"/runs/{rid}/retry").status_code == 409
        assert len(c.get("/runs").json()) == 1
        assert c.get("/runs/nonexistent").status_code == 404
        assert c.post("/runs", json={"input": "x"}).status_code == 422
        assert (
            c.post(
                "/runs",
                json={"input": "Hello world", "configuration": {"idea_count": 2}},
            ).status_code
            == 422
        )


def test_auth_and_csrf(app):
    app.state.settings.owner_password = "test-owner-password"
    with TestClient(app) as c:
        assert c.get("/").status_code == 401
        assert c.post("/runs", json={"input": "Hello world"}).status_code == 401
        assert c.get("/", auth=("owner", "wrong")).status_code == 401
        assert c.get("/", auth=("owner", "test-owner-password")).status_code == 200
        assert (
            c.post(
                "/runs",
                auth=("owner", "test-owner-password"),
                headers={"Origin": "https://evil.invalid"},
                json={"input": "Hello world"},
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/runs",
                auth=("owner", "test-owner-password"),
                headers={"Origin": "http://testserver"},
                json={"input": "Hello world"},
            ).status_code
            == 202
        )


def test_live_provider_missing_credentials(app, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app.state.settings.provider = "openai"
    with TestClient(app) as c:
        r = c.post("/runs", json={"input": "Hello world"})
        assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_private_network_default(app):
    with TestClient(app, client=("192.0.2.1", 1234)) as c:
        assert c.get("/").status_code == 403
