import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import errors as pg_errors

from app.config import Config
from app.db import create_pool
from app.v1.router import router as v1_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup
    await app.state.db_pool.open()
    yield
    # shutdown
    await app.state.db_pool.close()


def create_app(config: Config) -> FastAPI:
    # Configure root logging so app loggers reach stdout (and thus `docker logs`).
    logging.basicConfig(
        level=config.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Building Geometry Case Study",
        version="0.1.0",
        debug=config.debug,
        lifespan=lifespan,
    )

    app.state.config = config
    app.state.db_pool = create_pool(config)

    origins = [o.strip() for o in config.allowed_origins.split(";")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)

    @app.exception_handler(pg_errors.IntegrityError)
    async def _integrity_error(request: Request, exc: pg_errors.IntegrityError) -> JSONResponse:
        # A constraint stopped the write (e.g. a bad polygon_id/parent_id FK, or
        # the id <> parent_id check). Map to a client error instead of a 500, but
        # return a generic message: the raw Postgres diagnostic names internal
        # tables/columns/constraints, so it stays in our logs, not the response.
        logger.warning("DB integrity error on %s %s: %s", request.method, request.url.path, exc.diag.message_primary)
        # 400 for "you referenced/sent something invalid", 409 for true conflicts.
        if isinstance(exc, pg_errors.ForeignKeyViolation):
            detail, code = "References a resource that does not exist.", status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, (pg_errors.CheckViolation, pg_errors.NotNullViolation)):
            detail, code = "A field is missing or out of its allowed range.", status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, pg_errors.UniqueViolation):
            detail, code = "That resource already exists.", status.HTTP_409_CONFLICT
        else:
            detail, code = "The request conflicts with the current state.", status.HTTP_409_CONFLICT
        return JSONResponse(status_code=code, content={"detail": detail})

    @app.get("/")
    async def root() -> dict:
        from app import __version__

        return {"status": "ok", "version": __version__}

    return app


def deploy_factory() -> FastAPI:
    config = Config()
    return create_app(config)


def local_factory() -> FastAPI:
    from dotenv import load_dotenv

    load_dotenv()
    config = Config()
    return create_app(config)
