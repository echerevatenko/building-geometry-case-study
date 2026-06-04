from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from shapely import make_valid

from app.geometry import reasons
from app.geometry.config import MassingConfig
from app.geometry.reasons import Reason
from app.geometry.shapes import AREA_EPS, polygon_parts, to_geojson, to_geometry


class SiteStatus(StrEnum):
    VALID = "valid"  # one good polygon
    SEMI_VALID = "semi_valid"  # repaired / multi-part; largest piece kept
    INVALID = "invalid"  # degenerate or too small to build on
    EMPTY = "empty"  # no usable coordinates (rejected at the API)


@dataclass(frozen=True, slots=True)
class ParsedSite:
    """Result of validating a site polygon at save time.

    ``base`` is the canonical buildable polygon as GeoJSON (``None`` unless the
    status is ``valid`` / ``semi_valid``). ``reason`` explains a non-plain
    outcome and is ``None`` when the site is plainly ``valid``.
    """

    base: dict[str, Any] | None
    status: SiteStatus
    reason: Reason | None

    @property
    def has_base(self) -> bool:
        return self.base is not None


def parse_site(raw: Any, config: MassingConfig) -> ParsedSite:
    """Classify a raw site polygon and derive its canonical buildable base.

    Self-intersecting input is **repaired** (``make_valid``) rather than refused;
    if repair yields several pieces we keep the largest and flag it ``semi_valid``.
    A site whose largest piece is below ``config.min_site_area`` (or which has no
    real area at all) is ``invalid`` — saved, but no options can be built on it.
    """
    geom = to_geometry(raw)
    if geom is None or geom.is_empty:
        return ParsedSite(None, SiteStatus.EMPTY, reasons.NO_COORDINATES)

    repaired = not geom.is_valid
    if repaired:
        geom = make_valid(geom)

    parts = [p for p in polygon_parts(geom) if p.area > AREA_EPS]
    if not parts:
        return ParsedSite(None, SiteStatus.INVALID, reasons.DEGENERATE_SITE)

    base = max(parts, key=lambda p: p.area)
    if base.area < config.min_site_area:
        return ParsedSite(None, SiteStatus.INVALID, reasons.BELOW_MIN_SITE_AREA)

    if len(parts) >= 2:
        return ParsedSite(to_geojson(base), SiteStatus.SEMI_VALID, reasons.KEPT_LARGEST_PIECE)
    if repaired:
        return ParsedSite(to_geojson(base), SiteStatus.SEMI_VALID, reasons.REPAIRED_SELF_INTERSECTION)
    return ParsedSite(to_geojson(base), SiteStatus.VALID, None)
