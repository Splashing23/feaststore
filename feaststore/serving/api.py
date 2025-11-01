"""FastAPI application exposing online feature retrieval.

Design notes:
- The `FeatureStore` is constructed once at startup and shared; Redis and the
  SQLAlchemy engine are both connection-pooled and thread-safe for our use.
- Domain exceptions are translated to HTTP status codes by exception handlers so
  route bodies stay free of try/except noise.
- `/metrics` exposes a tiny Prometheus text exposition when metrics are enabled.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from feaststore import __version__
from feaststore.config import get_settings
from feaststore.exceptions import FeatureStoreError, FeatureViewNotFoundError
from feaststore.serving.metrics import Metrics
from feaststore.serving.schemas import (
    FeatureViewSummary,
    HealthResponse,
    OnlineFeaturesRequest,
    OnlineFeaturesResponse,
)
from feaststore.store import FeatureStore

logger = logging.getLogger("feaststore.serving")

metrics = Metrics()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    app.state.store = FeatureStore(settings)
    logger.info("feaststore serving %s ready (project=%s)", __version__, settings.project)
    try:
        yield
    finally:
        app.state.store.close()


app = FastAPI(
    title="feaststore",
    version=__version__,
    summary="Online feature serving API",
    lifespan=lifespan,
)


def get_store(request: Request) -> FeatureStore:
    return request.app.state.store


@app.exception_handler(FeatureViewNotFoundError)
async def _fv_not_found(request: Request, exc: FeatureViewNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(FeatureStoreError)
async def _fs_error(request: Request, exc: FeatureStoreError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", response_model=HealthResponse)
def health(store: FeatureStore = Depends(get_store)) -> HealthResponse:
    try:
        online_ok = store.online.ping()
    except Exception:  # noqa: BLE001 - health must never raise
        online_ok = False
    return HealthResponse(
        status="ok" if online_ok else "degraded",
        online_store="up" if online_ok else "down",
        version=__version__,
    )


@app.get("/feature-views", response_model=list[FeatureViewSummary])
def list_feature_views(store: FeatureStore = Depends(get_store)) -> list[FeatureViewSummary]:
    summaries = []
    for v in store.list_feature_views():
        summaries.append(
            FeatureViewSummary(
                name=v.name,
                entities=[e.name for e in v.entities],
                features=v.feature_names(),
                source_table=v.source_table,
                ttl_seconds=int(v.ttl.total_seconds()) if v.ttl else None,
            )
        )
    return summaries


@app.post("/get-online-features", response_model=OnlineFeaturesResponse)
def get_online_features(
    req: OnlineFeaturesRequest,
    store: FeatureStore = Depends(get_store),
) -> OnlineFeaturesResponse:
    start = time.perf_counter()
    results = store.get_online_features(features=req.features, entity_rows=req.entities)
    elapsed_ms = (time.perf_counter() - start) * 1000
    metrics.observe_request(n_entities=len(req.entities), latency_ms=elapsed_ms)
    return OnlineFeaturesResponse(
        metadata={"n_entities": len(req.entities), "latency_ms": round(elapsed_ms, 3)},
        results=results,
    )


@app.get("/metrics")
def prometheus_metrics() -> PlainTextResponse:
    if not get_settings().enable_metrics:
        return PlainTextResponse("metrics disabled\n", status_code=404)
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")
