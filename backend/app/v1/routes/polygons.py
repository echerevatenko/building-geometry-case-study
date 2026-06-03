from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection
from pydantic import BaseModel, ConfigDict, Field

from app.repositories.massing_option import MassingOptionRepository
from app.repositories.polygon import PolygonRepository
from app.v1.connection import get_connection
from app.v1.routes.massing_options import MassingOptionOut

router = APIRouter(prefix="/polygons", tags=["polygons"])


class PolygonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    site_polygon: dict[str, Any] | None = None


class PolygonUpdate(BaseModel):
    # Only fields the client actually sends are applied (see exclude_unset below).
    title: str | None = Field(None, min_length=1, max_length=200)
    site_polygon: dict[str, Any] | None = None


class PolygonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    site_polygon: dict[str, Any] | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[PolygonOut])
async def list_polygons(conn: AsyncConnection = Depends(get_connection)) -> list[PolygonOut]:
    polygons = await PolygonRepository(conn).list()
    return [PolygonOut.model_validate(p) for p in polygons]


@router.get("/{polygon_id}", response_model=PolygonOut)
async def get_polygon(polygon_id: int, conn: AsyncConnection = Depends(get_connection)) -> PolygonOut:
    polygon = await PolygonRepository(conn).get(polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
    return PolygonOut.model_validate(polygon)


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
    polygon = await PolygonRepository(conn).add(
        title=body.title,
        site_polygon=body.site_polygon,
    )
    return PolygonOut.model_validate(polygon)


@router.patch("/{polygon_id}", response_model=PolygonOut)
async def update_polygon(
    polygon_id: int, body: PolygonUpdate, conn: AsyncConnection = Depends(get_connection)
) -> PolygonOut:
    changes = body.model_dump(exclude_unset=True)
    polygon = await PolygonRepository(conn).update(polygon_id, **changes)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
    return PolygonOut.model_validate(polygon)


@router.delete("/{polygon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_polygon(polygon_id: int, conn: AsyncConnection = Depends(get_connection)) -> None:
    # Soft-deletes the polygon and all of its massing options (see PolygonRepository.delete).
    deleted = await PolygonRepository(conn).delete(polygon_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
