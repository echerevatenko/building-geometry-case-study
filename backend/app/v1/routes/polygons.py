from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection
from pydantic import BaseModel, ConfigDict, Field

from app.geometry import reasons
from app.geometry.config import MassingConfig
from app.geometry.reasons import Reason
from app.geometry.site import ParsedSite, SiteStatus, parse_site
from app.models.polygon import Polygon
from app.repositories.massing_option import MassingOptionRepository
from app.repositories.polygon import PolygonRepository
from app.v1.connection import get_connection
from app.v1.routes.massing_options import MassingOptionOut

router = APIRouter(prefix="/polygons", tags=["polygons"])

_MASSING = MassingConfig()


class PolygonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    site_polygon: dict[str, Any]


class PolygonUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    site_polygon: dict[str, Any] | None = None


class PolygonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    site_polygon: dict[str, Any] | None
    buildable_base: dict[str, Any] | None
    geometry_status: str | None
    # None when the site is plainly valid; otherwise a {name, message} for the user.
    geometry_reason: Reason | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


def _to_out(polygon: Polygon) -> PolygonOut:
    reason = reasons.BY_NAME.get(polygon.geometry_reason) if polygon.geometry_reason else None
    return PolygonOut(
        id=polygon.id,
        title=polygon.title,
        site_polygon=polygon.site_polygon,
        buildable_base=polygon.buildable_base,
        geometry_status=polygon.geometry_status,
        geometry_reason=reason,
        is_deleted=polygon.is_deleted,
        created_at=polygon.created_at,
        updated_at=polygon.updated_at,
    )


def _validate_site(site_polygon: Any) -> ParsedSite:
    """Parse + classify a site polygon, rejecting unusable coordinates with 422."""
    parsed = parse_site(site_polygon, _MASSING)
    if parsed.status is SiteStatus.EMPTY:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Site polygon has no usable coordinates.")
    return parsed


@router.get("", response_model=list[PolygonOut])
async def list_polygons(conn: AsyncConnection = Depends(get_connection)) -> list[PolygonOut]:
    polygons = await PolygonRepository(conn).list()
    return [_to_out(p) for p in polygons]


@router.get("/{polygon_id}", response_model=PolygonOut)
async def get_polygon(polygon_id: int, conn: AsyncConnection = Depends(get_connection)) -> PolygonOut:
    polygon = await PolygonRepository(conn).get(polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
    return _to_out(polygon)


@router.get("/{polygon_id}/massing-options", response_model=list[MassingOptionOut])
async def list_polygon_massing_options(
    polygon_id: int, conn: AsyncConnection = Depends(get_connection)
) -> list[MassingOptionOut]:
    if await PolygonRepository(conn).get(polygon_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
    massing_options = await MassingOptionRepository(conn).list_for_polygon(polygon_id)
    return [MassingOptionOut.model_validate(o) for o in massing_options]


@router.post("", response_model=PolygonOut, status_code=status.HTTP_201_CREATED)
async def create_polygon(body: PolygonCreate, conn: AsyncConnection = Depends(get_connection)) -> PolygonOut:
    parsed = _validate_site(body.site_polygon)
    polygon = await PolygonRepository(conn).add(
        title=body.title,
        site_polygon=body.site_polygon,
        buildable_base=parsed.base,
        geometry_status=parsed.status.value,
        geometry_reason=parsed.reason.name if parsed.reason else None,
    )
    return _to_out(polygon)


@router.patch("/{polygon_id}", response_model=PolygonOut)
async def update_polygon(
    polygon_id: int, body: PolygonUpdate, conn: AsyncConnection = Depends(get_connection)
) -> PolygonOut:
    changes = body.model_dump(exclude_unset=True)
    # When the geometry changes, recompute the derived fields so they never drift.
    if "site_polygon" in changes:
        parsed = _validate_site(changes["site_polygon"])
        changes["buildable_base"] = parsed.base
        changes["geometry_status"] = parsed.status.value
        changes["geometry_reason"] = parsed.reason.name if parsed.reason else None
    polygon = await PolygonRepository(conn).update(polygon_id, **changes)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
    return _to_out(polygon)


@router.delete("/{polygon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_polygon(polygon_id: int, conn: AsyncConnection = Depends(get_connection)) -> None:
    # Soft-deletes the polygon and all of its massing options (see PolygonRepository.delete).
    deleted = await PolygonRepository(conn).delete(polygon_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
