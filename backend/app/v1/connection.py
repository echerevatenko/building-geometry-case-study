from collections.abc import AsyncGenerator

from fastapi import Request
from psycopg import AsyncConnection

from app.db import get_connection as acquire_connection


async def get_connection(request: Request) -> AsyncGenerator[AsyncConnection, None]:
    """FastAPI dependency: borrow a pooled connection for this request.

    Adapts ``db.get_connection`` (which takes a pool) to FastAPI by reading the
    pool off ``request.app.state`` (created in ``create_app``, opened/closed by
    the ``lifespan`` in ``app.server``). Routes declare
    ``conn: AsyncConnection = Depends(get_connection)`` and pass ``conn`` to a
    repository. The pool uses ``autocommit=True``, so writes persist without an
    explicit transaction.
    """
    async for conn in acquire_connection(request.app.state.db_pool):
        yield conn
