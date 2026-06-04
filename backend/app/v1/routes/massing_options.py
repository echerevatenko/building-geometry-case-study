import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection
from pydantic import BaseModel, ConfigDict, Field

from app.geometry.config import MassingConfig
from app.geometry.massing import generate_massing
from app.geometry.reasons import Reason
from app.repositories.massing_option import MassingOptionRepository
from app.repositories.polygon import PolygonRepository
from app.v1.connection import get_connection
from app.v1.verification import VerificationStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/massing-options", tags=["massing_options"])

# Algorithm settings live with the algorithm; the route just uses the defaults.
_MASSING = MassingConfig()


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
    # A branched child is pre-filled by the client with the parent's state.
    floor_count: int | None = Field(None, ge=0)
    footprint_area: float | None = Field(None, ge=0)
    gfa: float | None = Field(None, ge=0)
    verification_result: VerificationStatus | None = None


class MassingOptionUpdate(BaseModel):
    parent_id: int | None = None
    name: str | None = Field(None, max_length=200)
    position: int | None = Field(None, ge=0)
    footprint: dict[str, Any] | None = None
    constraints: MassingConstraints | None = None
    floor_count: int | None = Field(None, ge=0)
    footprint_area: float | None = Field(None, ge=0)
    gfa: float | None = Field(None, ge=0)
    verification_result: VerificationStatus | None = None


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


class GenerationRequest(BaseModel):
    constraints: MassingConstraints | None = None


class GenerationResult(BaseModel):
    footprint: dict[str, Any] | None
    floor_count: int | None
    footprint_area: float | None
    gfa: float | None
    verification_result: VerificationStatus
    # Empty when the massing is plainly feasible; otherwise the reason it's
    # infeasible, or advisory notes (split site, GFA target unmet).
    reasons: list[Reason]


@router.post("/{massing_option_id}/generate", response_model=GenerationResult)
async def generate_massing_option(
    massing_option_id: int,
    body: GenerationRequest | None = None,
    conn: AsyncConnection = Depends(get_connection),
) -> GenerationResult:
    """Preview a massing for the given constraints. This is a pure what-if: it
    computes against the site's buildable base and returns the result **without
    persisting**, so the user can try constraints without saving them first."""
    option = await MassingOptionRepository(conn).get(massing_option_id)
    if option is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Massing option not found")

    polygon = await PolygonRepository(conn).get(option.polygon_id)
    buildable_base = polygon.buildable_base if polygon is not None else None

    constraints = (
        body.constraints.model_dump() if body is not None and body.constraints is not None else option.constraints
    )

    result = generate_massing(buildable_base, constraints, _MASSING)
    logger.info(
        "Previewed massing for option %s: %s (%s)",
        massing_option_id,
        result.status.value,
        ", ".join(r.name for r in result.reasons) or "ok",
    )
    return GenerationResult(
        footprint=result.footprint,
        floor_count=result.floor_count,
        footprint_area=result.footprint_area,
        gfa=result.gfa,
        verification_result=result.status,
        reasons=list(result.reasons),
    )


@router.post("", response_model=MassingOptionOut, status_code=status.HTTP_201_CREATED)
async def create_massing_option(
    body: MassingOptionCreate, conn: AsyncConnection = Depends(get_connection)
) -> MassingOptionOut:
    # Options are built on the site's buildable base; refuse if the site has none
    # (invalid / too-small geometry), so broken sites don't accrete options.
    polygon = await PolygonRepository(conn).get(body.polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Polygon not found")
    if polygon.buildable_base is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Site has no buildable base; cannot add massing options.",
        )

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
        verification_result=body.verification_result.value if body.verification_result is not None else None,
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
