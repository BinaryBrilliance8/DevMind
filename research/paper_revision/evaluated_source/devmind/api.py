"""Authenticated control API and same-origin browser console."""

import hmac
import json
import shutil
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from devmind.config import Config
from devmind.contracts import Review, RunRequest
from devmind.database import Rejected, Repository
from devmind.readiness import inspect


class RequestBounds:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > 32768:
                await JSONResponse({"detail": "Body exceeds 32 KiB"}, 413)(
                    scope, receive, send
                )
                return
            body.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return body.pop(0) if body else await receive()

        await self.app(scope, replay, send)


def create_app(config: Config, repository: Repository) -> FastAPI:
    config.validate()
    app = FastAPI(title="DevMind", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(RequestBounds)
    requests = defaultdict(deque)
    lock = Lock()

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def authenticate(
        request: Request, authorization: Annotated[str | None, Header()] = None
    ):
        address = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with lock:
            if address not in requests and len(requests) > 10000:
                requests.clear()
            recent = requests[address]
            while recent and recent[0] < now - 60:
                recent.popleft()
            if len(recent) >= 240:
                raise HTTPException(429, "Request rate exceeded")
            recent.append(now)
        if not hmac.compare_digest(
            (authorization or "").encode(), ("Bearer " + config.api_token).encode()
        ):
            raise HTTPException(401, "Enter a valid operator token")

    secure = [Depends(authenticate)]

    def required(identifier: str) -> dict:
        item = repository.get(identifier)
        if not item:
            raise HTTPException(404, "Run not found")
        return item

    def public(item: dict) -> dict:
        return {
            key: value
            for key, value in item.items()
            if key not in {"owner", "lease", "fingerprint", "request_key"}
        }

    @app.get("/health")
    def health():
        return {"service": "DevMind", "status": "online"}

    @app.get("/ready")
    def ready():
        report = inspect(config, repository, execution=False)
        return JSONResponse({"ready": report["ready"]}, 200 if report["ready"] else 503)

    @app.get("/api/readiness", dependencies=secure)
    def dependencies():
        report = inspect(config, repository)
        return JSONResponse(report, 200 if report["ready"] else 503)

    @app.get("/api/system", dependencies=secure)
    def system():
        return {
            "model": config.model or None,
            "database": repository.engine.dialect.name,
            "docker_cli": shutil.which("docker") is not None,
            "project_count": len(config.projects),
            "limits": {
                "steps": config.steps,
                "seconds": config.seconds,
                "tokens": config.token_limit,
            },
            "note": "Docker CLI presence does not prove daemon or model availability",
        }

    @app.get("/api/projects", dependencies=secure)
    def projects():
        return [
            {
                "key": p.key,
                "name": p.name,
                "image": p.image,
                "verify": p.verify,
                "protected": p.protected,
            }
            for p in config.projects
        ]

    @app.get("/api/runs", dependencies=secure)
    def listing(limit: int = Query(100, ge=1, le=500)):
        return [public(item) for item in repository.listing(limit)]

    @app.post("/api/runs", dependencies=secure)
    def submit(
        body: RunRequest,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
    ):
        try:
            config.project(body.project)
            identifier, created = repository.submit(
                body, idempotency_key, config.capacity
            )
        except Rejected as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return JSONResponse(
            {"id": identifier, "created": created}, 201 if created else 200
        )

    @app.get("/api/runs/{identifier}", dependencies=secure)
    def detail(identifier: str):
        return public(required(identifier))

    @app.get("/api/runs/{identifier}/events", dependencies=secure)
    def timeline(identifier: str, cursor: int = Query(0, ge=0)):
        required(identifier)
        return repository.timeline(identifier, cursor)

    @app.post("/api/runs/{identifier}/cancel", dependencies=secure)
    def cancel(identifier: str):
        required(identifier)
        return {"cancelled": repository.cancel(identifier)}

    @app.post("/api/runs/{identifier}/review", dependencies=secure)
    def review(identifier: str, body: Review):
        required(identifier)
        if not repository.review(identifier, body.decision, body.note):
            raise HTTPException(
                409, "Only verified runs awaiting review can be reviewed"
            )
        return {"decision": body.decision, "merged": False}

    @app.get("/api/runs/{identifier}/patch", dependencies=secure)
    def patch(identifier: str):
        required(identifier)
        artifact = repository.artifact(identifier, "patch")
        if not artifact:
            raise HTTPException(409, "Patch is not yet available")
        return PlainTextResponse(
            artifact["content"], headers={"ETag": '"' + artifact["sha256"] + '"'}
        )

    @app.get("/api/runs/{identifier}/prediction", dependencies=secure)
    def prediction(identifier: str):
        item = required(identifier)
        if (
            item["status"] in {"active", "queued"}
            or not item["request"]["benchmark_id"]
        ):
            raise HTTPException(409, "A terminal run with a benchmark ID is required")
        artifact = repository.artifact(identifier, "patch")
        payload = {
            "instance_id": item["request"]["benchmark_id"],
            "model_name_or_path": (item["result"] or {}).get("model", config.model),
            "model_patch": artifact["content"] if artifact else "",
        }
        return Response(json.dumps(payload) + "\n", media_type="application/x-ndjson")

    @app.get("/api/runs/{identifier}/trajectory", dependencies=secure)
    def trajectory(identifier: str, consent: bool = False):
        if not consent:
            raise HTTPException(
                422, "Explicit consent is required to export source-bearing traces"
            )
        item = required(identifier)
        if item["status"] != "approved":
            raise HTTPException(409, "Training candidates require a human-approved run")
        history = []
        cursor = 0
        while page := repository.timeline(identifier, cursor):
            history.extend(page)
            cursor = page[-1]["sequence"]
        payload = {
            "schema": 1,
            "quality": "human-approved; not official benchmark verification",
            "run": public(item),
            "events": history,
        }
        return Response(json.dumps(payload) + "\n", media_type="application/x-ndjson")

    @app.get("/")
    def index():
        return FileResponse(config.web / "index.html")

    app.mount("/assets", StaticFiles(directory=config.web), name="assets")
    return app
