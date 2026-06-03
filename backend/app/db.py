"""Database plumbing — async psycopg with a connection pool.

This wires up an async connection pool and a FastAPI dependency that hands you a
connection. There is **no ORM and no schema** on purpose: define your own model
types (plain dataclasses / pydantic) and write **pure SQL** with psycopg.

Example usage in a route:

    from psycopg import AsyncConnection
    from psycopg.rows import dict_row

    async def list_options(conn: AsyncConnection = Depends(get_connection)):
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT id, parent_id, name FROM options")
            return await cur.fetchall()

Wire the dependency to the app's pool however you prefer (e.g. a small provider
that reads `request.app.state.db_pool`).
"""

from collections.abc import AsyncGenerator

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.config import Config


def create_pool(config: Config) -> AsyncConnectionPool:
    # open=False: the pool is opened in the app lifespan, not at import time.
    return AsyncConnectionPool(config.database_url, open=False, kwargs={"autocommit": True})


async def get_connection(pool: AsyncConnectionPool) -> AsyncGenerator[AsyncConnection, None]:
    async with pool.connection() as conn:
        yield conn
