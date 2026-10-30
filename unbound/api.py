import secrets
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from .models import RunInput
from .settings import Settings
from .store import Store
from .providers import check_provider, ProviderConfigurationError
from .export import markdown


def create_app(settings=None):
    settings = settings or Settings()
    settings.prepare()
    store = Store(settings.db)
    app = FastAPI(
        title="UNBOUND INNOVATION ENGINE",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    app.state.settings = settings
    basic = HTTPBasic(auto_error=False)

    async def owner(
        request: Request, credentials: HTTPBasicCredentials | None = Depends(basic)
    ):
        host = request.client.host if request.client else ""
        if settings.owner_password:
            if not credentials or not (
                secrets.compare_digest(credentials.username.encode(), b"owner")
                and secrets.compare_digest(
                    credentials.password.encode(), settings.owner_password.encode()
                )
            ):
                raise HTTPException(
                    401,
                    "Owner authentication required",
                    headers={"WWW-Authenticate": 'Basic realm="UNBOUND"'},
                )
        elif host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(
                403, "Network access requires UNBOUND_OWNER_PASSWORD and HTTPS gateway"
            )
        # Reject cross-site browser mutations, including cached Basic auth requests.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            expected = (
                settings.public_origin
                or f"{request.url.scheme}://{request.headers.get('host', '')}"
            )
            if (origin and origin != expected) or request.headers.get(
                "sec-fetch-site"
            ) == "cross-site":
                raise HTTPException(403, "Cross-origin mutation rejected")

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "provider": settings.provider,
            "model": settings.model,
            "mock": settings.provider == "mock",
        }

    @app.get("/", response_class=HTMLResponse, dependencies=[Depends(owner)])
    def dashboard():
        return (Path(__file__).parent / "static/index.html").read_text()

    @app.post("/runs", status_code=202, dependencies=[Depends(owner)])
    def start(request: RunInput):
        try:
            check_provider(settings)
        except ProviderConfigurationError as exc:
            raise HTTPException(503, str(exc)) from None
        rid = store.create(request, settings.provider, settings.model)
        return {"run_id": rid, "status": "QUEUED", "status_url": f"/runs/{rid}"}

    @app.get("/runs", dependencies=[Depends(owner)])
    def history():
        return store.history()

    def get(rid):
        run = store.get(rid)
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/runs/{run_id}", dependencies=[Depends(owner)])
    def status(run_id: str):
        return get(run_id)

    @app.post("/runs/{run_id}/retry", status_code=202, dependencies=[Depends(owner)])
    def retry(run_id: str):
        get(run_id)
        if not store.retry(run_id):
            raise HTTPException(409, "Only a failed run can be retried")
        return {"run_id": run_id, "status": "QUEUED"}

    @app.get("/runs/{run_id}/results", dependencies=[Depends(owner)])
    def results(run_id: str):
        run = get(run_id)
        return {
            "complete": run["status"] == "COMPLETED",
            "run": run,
            "markdown": markdown(run),
        }

    @app.get("/runs/{run_id}/export.json", dependencies=[Depends(owner)])
    def export_json(run_id: str):
        import json

        return Response(
            json.dumps(get(run_id), ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="innovation-report.json"'
            },
        )

    @app.get("/runs/{run_id}/export.md", dependencies=[Depends(owner)])
    def export_md(run_id: str):
        return Response(
            markdown(get(run_id)),
            media_type="text/markdown",
            headers={
                "Content-Disposition": 'attachment; filename="innovation-report.md"'
            },
        )

    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).parent / "static"),
        name="static",
    )
    return app


app = create_app()
