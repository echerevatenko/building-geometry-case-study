from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection, sql
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from app.models.massing_option import MassingOption
from app.repositories._base import UNSET, _Unset

_COLUMNS = (
    "id, polygon_id, parent_id, name, position, footprint, constraints, "
    "floor_count, footprint_area, gfa, verification_result, is_deleted, created_at, updated_at"
)


class MassingOptionRepository:
    """CRUD-ish access to ``massing_option`` rows over a single connection."""

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def add(
        self,
        *,
        polygon_id: int,
        parent_id: int | None = None,
        name: str | None = None,
        position: int = 0,
        footprint: dict[str, Any] | None = None,
        constraints: dict[str, Any] | None = None,
        floor_count: int | None = None,
        footprint_area: float | None = None,
        gfa: float | None = None,
    ) -> MassingOption:
        """Insert a new massing option (root if ``parent_id`` is ``None``) and return it.

        The ``jsonb`` columns default to SQL ``NULL`` when omitted; ``dict``
        values are wrapped in ``Jsonb`` so psycopg adapts them to ``jsonb``.
        """
        async with self._conn.cursor(row_factory=class_row(MassingOption)) as cur:
            await cur.execute(
                f"""
                INSERT INTO massing_option (
                    polygon_id, parent_id, name, position, footprint, constraints,
                    floor_count, footprint_area, gfa
                )
                VALUES (
                    %(polygon_id)s, %(parent_id)s, %(name)s, %(position)s, %(footprint)s, %(constraints)s,
                    %(floor_count)s, %(footprint_area)s, %(gfa)s
                )
                RETURNING {_COLUMNS}
                """,
                {
                    "polygon_id": polygon_id,
                    "parent_id": parent_id,
                    "name": name,
                    "position": position,
                    "footprint": Jsonb(footprint) if footprint is not None else None,
                    "constraints": Jsonb(constraints) if constraints is not None else None,
                    "floor_count": floor_count,
                    "footprint_area": footprint_area,
                    "gfa": gfa,
                },
            )
            row = await cur.fetchone()
            assert row is not None  # RETURNING on a successful INSERT always yields a row
            return row

    async def get(self, massing_option_id: int) -> MassingOption | None:
        """Return a live (not soft-deleted) massing option, or ``None``."""
        async with self._conn.cursor(row_factory=class_row(MassingOption)) as cur:
            await cur.execute(
                f"SELECT {_COLUMNS} FROM massing_option WHERE id = %s AND is_deleted = false",
                (massing_option_id,),
            )
            return await cur.fetchone()

    async def list_for_polygon(self, polygon_id: int) -> list[MassingOption]:
        """Return all live massing options for a polygon, ordered for stable tree builds.

        Roots first (``parent_id`` NULL), then by ``parent_id``/``position``/``id``
        so a client can rebuild the massing option tree deterministically.
        """
        async with self._conn.cursor(row_factory=class_row(MassingOption)) as cur:
            await cur.execute(
                f"""
                SELECT {_COLUMNS} FROM massing_option
                WHERE polygon_id = %s AND is_deleted = false
                ORDER BY parent_id NULLS FIRST, position, id
                """,
                (polygon_id,),
            )
            return await cur.fetchall()

    async def update(
        self,
        massing_option_id: int,
        *,
        parent_id: int | None | _Unset = UNSET,
        name: str | None | _Unset = UNSET,
        position: int | _Unset = UNSET,
        footprint: dict[str, Any] | None | _Unset = UNSET,
        constraints: dict[str, Any] | None | _Unset = UNSET,
        floor_count: int | None | _Unset = UNSET,
        footprint_area: float | None | _Unset = UNSET,
        gfa: float | None | _Unset = UNSET,
        verification_result: str | None | _Unset = UNSET,
    ) -> MassingOption | None:
        """Partially update a live massing option.

        Only the arguments you pass are written; omit one to leave that column
        untouched. ``parent_id=None`` is meaningful — it re-roots the massing option;
        passing ``None`` for a ``jsonb`` column clears it.
        Returns the updated row, or ``None`` if no live massing option matched.
        """
        assignments: list[sql.Composable] = []
        params: dict[str, object] = {"id": massing_option_id}

        if not isinstance(parent_id, _Unset):
            assignments.append(sql.SQL("parent_id = %(parent_id)s"))
            params["parent_id"] = parent_id
        if not isinstance(name, _Unset):
            assignments.append(sql.SQL("name = %(name)s"))
            params["name"] = name
        for column, value in (
            ("position", position),
            ("floor_count", floor_count),
            ("footprint_area", footprint_area),
            ("gfa", gfa),
            ("verification_result", verification_result),
        ):
            if not isinstance(value, _Unset):
                assignments.append(sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
                params[column] = value
        for column, value in (("footprint", footprint), ("constraints", constraints)):
            if not isinstance(value, _Unset):
                assignments.append(sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(column)))
                params[column] = Jsonb(value) if value is not None else None

        if not assignments:
            # Nothing to change; return the current row so callers get a stable shape.
            return await self.get(massing_option_id)

        assignments.append(sql.SQL("updated_at = now()"))
        query = sql.SQL(
            "UPDATE massing_option SET {assignments} WHERE id = %(id)s AND is_deleted = false RETURNING {columns}"
        ).format(
            assignments=sql.SQL(", ").join(assignments),
            columns=sql.SQL(_COLUMNS),
        )
        async with self._conn.cursor(row_factory=class_row(MassingOption)) as cur:
            await cur.execute(query, params)
            return await cur.fetchone()

    async def delete(self, massing_option_id: int) -> int:
        """Soft-delete a massing option and its entire live subtree.

        Returns the number of massing options soft-deleted (0 if the massing option was absent
        or already deleted). A recursive CTE walks down ``parent_id`` so a
        deleted node never leaves live descendants dangling.
        """
        async with self._conn.cursor() as cur:
            await cur.execute(
                """
                WITH RECURSIVE subtree AS (
                    SELECT id FROM massing_option WHERE id = %s AND is_deleted = false
                    UNION ALL
                    SELECT child.id
                    FROM massing_option AS child
                    JOIN subtree ON child.parent_id = subtree.id
                    WHERE child.is_deleted = false
                )
                UPDATE massing_option
                SET is_deleted = true,
                    updated_at = now()
                WHERE id IN (SELECT id FROM subtree)
                """,
                (massing_option_id,),
            )
            return cur.rowcount
