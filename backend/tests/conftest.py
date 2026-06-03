import pathlib
import time

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Config
from app.server import create_app

MIGRATIONS_DIR = str(pathlib.Path(__file__).resolve().parent.parent / "migrations")


def _yoyo_uri(libpq_url: str) -> str:
    # yoyo's plain postgresql:// backend wants psycopg2; we run psycopg 3.
    for scheme in ("postgresql://", "postgres://"):
        if libpq_url.startswith(scheme):
            return "postgresql+psycopg://" + libpq_url[len(scheme) :]
    return libpq_url


def _apply_migrations(libpq_url: str) -> None:
    from yoyo import get_backend, read_migrations

    backend = get_backend(_yoyo_uri(libpq_url))
    migrations = read_migrations(MIGRATIONS_DIR)
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))


def _wait_ready(url: str, attempts: int = 40) -> None:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            with psycopg.connect(url, connect_timeout=2) as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # noqa: BLE001 - retry until the container accepts connections
            last = exc
            time.sleep(0.5)
    raise RuntimeError(f"Postgres did not become ready: {last}")


@pytest.fixture(scope="session")
def pg_url():
    """A migrated, throwaway Postgres; yields its libpq URL. Skips without Docker."""
    try:
        from testcontainers.core.container import DockerContainer
    except ModuleNotFoundError:
        pytest.skip("testcontainers not installed; skipping DB-backed tests")

    container = (
        DockerContainer("postgres:16-alpine")
        .with_env("POSTGRES_USER", "test")
        .with_env("POSTGRES_PASSWORD", "test")
        .with_env("POSTGRES_DB", "test")
        .with_exposed_ports(5432)
    )
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001 - Docker unavailable, image pull failed, etc.
        pytest.skip(f"could not start Postgres test container: {exc}")

    try:
        url = f"postgresql://test:test@{container.get_container_host_ip()}:{container.get_exposed_port(5432)}/test"
        _wait_ready(url)
        _apply_migrations(url)
        yield url
    finally:
        container.stop()


@pytest.fixture
def clean_db(pg_url):
    """Truncate every table so each test starts from an empty, id-reset schema."""
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute("TRUNCATE polygon, massing_option RESTART IDENTITY CASCADE")
    yield


@pytest.fixture
async def client(pg_url, clean_db):
    """An httpx client bound to the app, with the pool opened (lifespan isn't run by ASGITransport)."""
    app = create_app(Config(database_url=pg_url, allowed_origins="*"))
    await app.state.db_pool.open()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
            yield http_client
    finally:
        await app.state.db_pool.close()


@pytest.fixture
async def conn(pg_url, clean_db):
    """A raw autocommit connection for exercising repositories directly."""
    connection = await psycopg.AsyncConnection.connect(pg_url, autocommit=True)
    try:
        yield connection
    finally:
        await connection.close()
