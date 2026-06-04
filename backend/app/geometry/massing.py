from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from shapely import MultiPolygon

from app.geometry import reasons
from app.geometry.config import MassingConfig
from app.geometry.reasons import Reason
from app.geometry.shapes import (
    AREA_EPS,
    COORD_NDIGITS,
    largest_polygon,
    remove_thin_parts,
    shrink_to_area,
    to_geojson,
    to_geometry,
)
from app.v1.verification import VerificationStatus


@dataclass(frozen=True, slots=True)
class MassingResult:
    status: VerificationStatus
    reasons: tuple[Reason, ...] = ()
    footprint: dict[str, Any] | None = None
    footprint_area: float | None = None
    floor_count: int | None = None
    gfa: float | None = None
    height_m: float | None = None

    @property
    def is_feasible(self) -> bool:
        return self.status is VerificationStatus.FEASIBLE


def _infeasible(reason: Reason) -> MassingResult:
    return MassingResult(status=VerificationStatus.INFEASIBLE, reasons=(reason,))


def _num(constraints: Mapping[str, Any], key: str) -> float | None:
    value = constraints.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _floor_count(constraints: Mapping[str, Any]) -> tuple[int | None, Reason | None]:
    """Derive the floor count from the height / floor-count limits.

    Takes the binding (minimum) of whichever limits are supplied:
    ``floor(max_height_m / floor_to_floor_m)`` and ``max_floors``. Returns
    ``(None, reason)`` when no limit pins the stack or it admits zero floors,
    else ``(count, None)``.
    """
    max_height_m = _num(constraints, "max_height_m")
    floor_to_floor_m = _num(constraints, "floor_to_floor_m")
    max_floors = _num(constraints, "max_floors")

    limits: list[int] = []
    if max_height_m is not None and floor_to_floor_m:
        limits.append(math.floor(max_height_m / floor_to_floor_m))
    if max_floors is not None:
        limits.append(int(max_floors))

    if not limits:
        return None, reasons.NO_FLOOR_OR_HEIGHT_LIMIT
    count = min(limits)
    if count < 1:
        return None, reasons.HEIGHT_ADMITS_ZERO_FLOORS
    return count, None


def generate_massing(
    site_polygon: Any, constraints: Mapping[str, Any] | None, config: MassingConfig | None = None
) -> MassingResult:
    """Generate a massing for buildable base + target GFA + constraint set."""
    constraints = constraints or {}
    config = config or MassingConfig()

    site = largest_polygon(to_geometry(site_polygon))
    if site is None:
        return _infeasible(reasons.NO_SITE_POLYGON)
    if not site.is_valid:
        # Self-intersecting / degenerate input — reported, not silently repaired.
        # (Site-level repair happens once at save time; see app.geometry.site.)
        return _infeasible(reasons.INVALID_POLYGON)
    if site.area <= AREA_EPS:
        return _infeasible(reasons.ZERO_AREA_SITE)

    # Floor stacking is independent of the footprint shape; check it first so a
    # contradictory height/floor set is reported even on a trivial site.
    floor_count, floor_problem = _floor_count(constraints)
    if floor_count is None:
        assert floor_problem is not None
        return _infeasible(floor_problem)

    # --- Setback inset ---------------------------------------------------
    setback_m = _num(constraints, "setback_m")
    notes: list[Reason] = []
    if setback_m and setback_m > 0:
        inset = site.buffer(-setback_m, join_style="mitre")
    else:
        inset = site

    footprint = largest_polygon(inset)
    if footprint is None or footprint.area <= AREA_EPS:
        return _infeasible(reasons.SETBACK_COLLAPSES_FOOTPRINT)
    if isinstance(inset, MultiPolygon) and len([p for p in inset.geoms if p.area > AREA_EPS]) > 1:
        # A deep setback split the plot (e.g. notched.json). We mass the largest
        # piece and flag it; modelling multiple buildings per site is roadmap.
        notes.append(reasons.SETBACK_SPLIT_USED_LARGEST)

    # --- Drop corridors too thin to actually build in --------------------
    buildable = largest_polygon(remove_thin_parts(footprint, config.min_corridor_width))
    if buildable is None or buildable.area <= AREA_EPS:
        return _infeasible(reasons.FOOTPRINT_TOO_THIN)
    if buildable.area + AREA_EPS < footprint.area:
        notes.append(reasons.TRIMMED_THIN_PARTS)
    footprint = buildable

    # --- Coverage cap: the most footprint the rules allow ----------------
    geometric_area = footprint.area
    max_area = geometric_area
    coverage_ratio = _num(constraints, "site_coverage_ratio")
    if coverage_ratio is not None:
        max_area = min(max_area, coverage_ratio * site.area)
    max_gfa = max_area * floor_count

    # --- Fit the mass to the GFA target ----------------------------------
    # No target: build the most the rules allow. With a target, aim for it by
    # scaling *down* — drop floors first (the coarse lever), then trim the
    # footprint to fine-tune. If the target exceeds capacity the constraints win:
    # build the maximum feasible mass and flag the target as unmet.
    target_gfa = _num(constraints, "target_gfa")
    if target_gfa is None or max_area <= AREA_EPS:
        floors, footprint_area = floor_count, max_area
    elif target_gfa > max_gfa + AREA_EPS:
        floors, footprint_area = floor_count, max_area
        notes.append(reasons.GFA_TARGET_UNMET)
    else:
        floors = min(floor_count, max(1, math.ceil(target_gfa / max_area)))
        footprint_area = min(max_area, target_gfa / floors)
        if floors < floor_count or footprint_area + AREA_EPS < max_area:
            notes.append(reasons.REDUCED_TO_GFA_TARGET)

    # Erode the drawn footprint inward to the area used (coverage cap / GFA
    # target), staying inside the buildable base and following its outline. The
    # erosion can carve out new sub-minimum corridors, so re-trim them — and if
    # that removes anything, the realistic buildable area is whatever survives.
    if footprint_area + AREA_EPS < geometric_area:
        eroded = largest_polygon(shrink_to_area(footprint, footprint_area))
        if eroded is not None and eroded.area > AREA_EPS:
            footprint = eroded
            cleaned = largest_polygon(remove_thin_parts(eroded, config.min_corridor_width))
            if cleaned is not None and cleaned.area + AREA_EPS < eroded.area:
                footprint = cleaned
                footprint_area = cleaned.area

    gfa = footprint_area * floors
    floor_to_floor_m = _num(constraints, "floor_to_floor_m")
    height_m = floors * floor_to_floor_m if floor_to_floor_m else None

    return MassingResult(
        status=VerificationStatus.FEASIBLE,
        reasons=tuple(notes),
        footprint=to_geojson(footprint),
        footprint_area=round(footprint_area, COORD_NDIGITS),
        floor_count=floors,
        gfa=round(gfa, COORD_NDIGITS),
        height_m=round(height_m, COORD_NDIGITS) if height_m is not None else None,
    )
