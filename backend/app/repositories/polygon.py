from __future__ import annotations

import logging
from typing import Any

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from app.models.polygon import Polygon
from app.repositories._base import UNSET, _Unset

logger = logging.getLogger(__name__)

# Column list kept in one place so SELECT/RETURNING stay in sync with Polygon.
_COLUMNS = (
    "id, title, site_polygon, buildable_base, geometry_status, geometry_reason, is_deleted, created_at, updated_at"
)


class PolygonRepository:
    """CRUD-ish access to ``polygon`` rows over a single connection.

    Soft delete only: rows are never removed, ``is_deleted`` is flipped instead.
    Read/update/delete operations ignore already-soft-deleted rows.
    """

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def add(
        self,
        *,
        title: str,
        site_polygon: dict[str, Any] | None = None,
        buildable_base: dict[str, Any] | None = None,
        geometry_status: str | None = None,
        geometry_reason: str | None = None,
    ) -> Polygon:
        """Insert a new polygon (with its derived geometry) and return the row.

        The ``jsonb`` columns default to SQL ``NULL`` when omitted; ``dict``
        values are wrapped in ``Jsonb`` so psycopg adapts them to ``jsonb``. The
        derived geometry fields are computed by the caller via ``parse_site``.
        """
        async with self._conn.cursor(row_factory=class_row(Polygon)) as cur:
            await cur.execute(
                f"""
                INSERT INTO polygon (title, site_polygon, buildable_base, geometry_status, geometry_reason)
                VALUES (
                    %(title)s, %(site_polygon)s, %(buildable_base)s, %(geometry_status)s, %(geometry_reason)s
                )
                RETURNING {_COLUMNS}
                """,
                {
                    "title": title,
                    "site_polygon": Jsonb(site_polygon) if site_polygon is not None else None,
                    "buildable_base": Jsonb(buildable_base) if buildable_base is not None else None,
                    "geometry_status": geometry_status,
                    "geometry_reason": geometry_reason,
                },
            )
            row = await cur.fetchone()
            assert row is not None  # RETURNING on a successful INSERT always yields a row
            return row

    async def get(self, polygon_id: int) -> Polygon | None:
        """Return a live (not soft-deleted) polygon, or ``None``."""
        async with self._conn.cursor(row_factory=class_row(Polygon)) as cur:
            await cur.execute(
                f"SELECT {_COLUMNS} FROM polygon WHERE id = %s AND is_deleted = false",
                (polygon_id,),
            )
            return await cur.fetchone()

    async def list(self) -> list[Polygon]:
        """Return all live (not soft-deleted) polygons, oldest first."""
        async with self._conn.cursor(row_factory=class_row(Polygon)) as cur:
            await cur.execute(f"SELECT {_COLUMNS} FROM polygon WHERE is_deleted = false ORDER BY created_at, id")
            return await cur.fetchall()

    async def update(
        self,
        polygon_id: int,
        *,
        title: str | _Unset = UNSET,
        site_polygon: dict[str, Any] | None | _Unset = UNSET,
        buildable_base: dict[str, Any] | None | _Unset = UNSET,
        geometry_status: str | None | _Unset = UNSET,
        geometry_reason: str | None | _Unset = UNSET,
    ) -> Polygon | None:
        """Partially update a live polygon.

        Only the arguments you pass are written; omit one to leave that column
        untouched. Passing ``None`` for a ``jsonb`` column clears it. The derived
        geometry columns (``buildable_base`` / ``geometry_status`` /
        ``geometry_reason``) are computed by the caller via ``parse_site`` and
        written here whenever ``site_polygon`` changes. Returns the updated row,
        or ``None`` if no live polygon matched.
        """
        assignments: list[sql.Composable] = []
        params: dict[str, object] = {"id": polygon_id}

        if not isinstance(title, _Unset):
            assignments.append(sql.SQL("title = %(title)s"))
            params["title"] = title
        for column, value in (("geometry_status", geometry_status), ("geometry_reason", geometry_reason)):
            if not isinstance(value, _Unset):
                assignments.append(sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
                params[column] = value
        for column, value in (("site_polygon", site_polygon), ("buildable_base", buildable_base)):
            if not isinstance(value, _Unset):
                assignments.append(sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
                params[column] = Jsonb(value) if value is not None else None

        if not assignments:
            # Nothing to change; return the current row so callers get a stable shape.
            return await self.get(polygon_id)

        assignments.append(sql.SQL("updated_at = now()"))
        query = sql.SQL(
            "UPDATE polygon SET {assignments} WHERE id = %(id)s AND is_deleted = false RETURNING {columns}"
        ).format(
            assignments=sql.SQL(", ").join(assignments),
            columns=sql.SQL(_COLUMNS),
        )
        async with self._conn.cursor(row_factory=class_row(Polygon)) as cur:
            await cur.execute(query, params)
            return await cur.fetchone()

    async def delete(self, polygon_id: int) -> bool:
        """Soft-delete a polygon and all of its massing options. Returns ``True`` if a
        live polygon was deleted.

        ``massing_option.polygon_id`` has ``ON DELETE CASCADE``, but that only fires on a
        hard delete, so the cascade is done here: every live massing option sharing this
        ``polygon_id`` is soft-deleted too (one statement covers the whole massing option
        tree since they all carry the polygon id). Run inside a transaction so
        the polygon and its massing options flip together.
        """
        async with self._conn.transaction():
            async with self._conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE polygon
                    SET is_deleted = true,
                        updated_at = now()
                    WHERE id = %s AND is_deleted = false
                    """,
                    (polygon_id,),
                )

                if cur.rowcount == 0:
                    return False

                await cur.execute(
                    """
                    UPDATE massing_option
                    SET is_deleted = true,
                        updated_at = now()
                    WHERE polygon_id = %s AND is_deleted = false
                    """,
                    (polygon_id,),
                )

        return True
