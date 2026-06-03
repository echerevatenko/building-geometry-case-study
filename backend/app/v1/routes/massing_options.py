from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection
from pydantic import BaseModel, ConfigDict, Field

from app.repositories.massing_option import MassingOptionRepository
from app.v1.connection import get_connection
from app.v1.verification import VerificationStatus

router = APIRouter(prefix="/massing-options", tags=["massing_options"])


class MassingConstraints(BaseModel):
    """Per-option building constraints, stored in the ``constraints`` jsonb column."""

    setback_m: float | None = Field(None, ge=0)
    floor_to_floor_m: float | None = Field(None, ge=0)
    max_height_m: float | None = Field(None, ge=0)
    max_floors: int | None = Field(None, ge=0)
    site_coverage_ratio: float | None = Field(None, ge=0, le=1)
    target_gfa: float | None = Field(None, ge=0)


class MassingOptionCreate(BaseModel):
    polygon_id: int
    parent_id: int | None = None
    name: str | None = Field(None, max_length=200)
    position: int = Field(0, ge=0)
    footprint: dict[str, Any] | None = None
    constraints: MassingConstraints | None = None
    floor_count: int | None = Field(None, ge=0)
    footprint_area: float | None = Field(None, ge=0)
    gfa: float | None = Field(None, ge=0)


class MassingOptionUpdate(BaseModel):
    # Only fields the client actually sends are applied (see model_fields_set
    # via exclude_unset below). parent_id=null is meaningful — it re-roots.
    parent_id: int | None = None
    name: str | None = Field(None, max_length=200)
    position: int | None = Field(None, ge=0)
    footprint: dict[str, Any] | None = None
    constraints: MassingConstraints | None = None
    floor_count: int | None = Field(None, ge=0)
    footprint_area: float | None = Field(None, ge=0)
    gfa: float | None = Field(None, ge=0)


class MassingOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    polygon_id: int
    parent_id: int | None
    name: str | None
    position: int
    footprint: dict[str, Any] | None
    constraints: MassingConstraints | None
    floor_count: int | None
    footprint_area: float | None
    gfa: float | None
    verification_result: VerificationStatus | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class GenerationResult(BaseModel):
    footprint: dict[str, Any] | None
    floor_count: int | None
    footprint_area: float | None
    gfa: float | None
    verification_result: VerificationStatus


@router.post("/{massing_option_id}/generate", response_model=GenerationResult)
async def generate_massing_option(
    massing_option_id: int, conn: AsyncConnection = Depends(get_connection)
) -> GenerationResult:
    repo = MassingOptionRepository(conn)
    if await repo.get(massing_option_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Massing option not found")
    # Stub: real massing generation (produce footprint, floor count, GFA, …) goes here later.
    verification_result = VerificationStatus.FEASIBLE
    massing_option = await repo.update(massing_option_id, verification_result=verification_result.value)
    assert massing_option is not None  # the row existed a statement ago and we hold the connection
    return GenerationResult(
        footprint=massing_option.footprint,
        floor_count=massing_option.floor_count,
        footprint_area=massing_option.footprint_area,
        gfa=massing_option.gfa,
        verification_result=verification_result,
    )


@router.post("", response_model=MassingOptionOut, status_code=status.HTTP_201_CREATED)
async def create_massing_option(
    body: MassingOptionCreate, conn: AsyncConnection = Depends(get_connection)
) -> MassingOptionOut:
    massing_option = await MassingOptionRepository(conn).add(
        polygon_id=body.polygon_id,
        parent_id=body.parent_id,
        name=body.name,
        position=body.position,
        footprint=body.footprint,
        constraints=body.constraints.model_dump() if body.constraints is not None else None,
        floor_count=body.floor_count,
        footprint_area=body.footprint_area,
        gfa=body.gfa,
    )
    return MassingOptionOut.model_validate(massing_option)


@router.patch("/{massing_option_id}", response_model=MassingOptionOut)
async def update_massing_option(
    massing_option_id: int, body: MassingOptionUpdate, conn: AsyncConnection = Depends(get_connection)
) -> MassingOptionOut:
    changes = body.model_dump(exclude_unset=True)
    massing_option = await MassingOptionRepository(conn).update(massing_option_id, **changes)
    if massing_option is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Massing option not found")
    return MassingOptionOut.model_validate(massing_option)


@router.delete("/{massing_option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_massing_option(massing_option_id: int, conn: AsyncConnection = Depends(get_connection)) -> None:
    # Soft-deletes the massing option and its whole subtree (see MassingOptionRepository.delete).
    deleted = await MassingOptionRepository(conn).delete(massing_option_id)
    if deleted == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Massing option not found")
