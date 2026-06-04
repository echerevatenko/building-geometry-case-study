from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shapely import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

# Areas below this (m²) are treated as no area at all — guards against float
# slivers from repair/buffer ops masquerading as real polygons.
AREA_EPS = 1.0
# Coordinate output precision (millimetre is finer than massing needs).
COORD_NDIGITS = 2


def _coerce_ring(value: Any) -> list[tuple[float, float]] | None:
    """Normalise a coordinate blob into a flat exterior ring of ``(x, y)`` pairs.

    Accepts a bare ring ``[[x, y], ...]`` (the sample-data shape) or a nested
    GeoJSON-style ``[ring, *holes]`` (takes the exterior). Returns ``None`` for
    anything it can't read as a ring.
    """
    if not isinstance(value, (list, tuple)) or not value:
        return None
    first = value[0]
    if isinstance(first, (list, tuple)) and len(first) == 2 and all(isinstance(c, (int, float)) for c in first):
        return [(float(x), float(y)) for x, y in value]
    if isinstance(first, (list, tuple)):  # nested rings — take the exterior
        return _coerce_ring(first)
    return None


def _polygon_from_ring(value: Any) -> Polygon | None:
    ring = _coerce_ring(value)
    if ring is None or len(ring) < 3:
        return None
    return Polygon(ring)


def to_geometry(raw: Any) -> BaseGeometry | None:
    """Parse stored site geometry into a Shapely geometry, or ``None``.

    Handles a bare ring, a ``{"polygon": [...]}`` / ``{"coordinates": [...]}``
    blob (sample-data shapes), and a GeoJSON ``Polygon`` / ``MultiPolygon``.
    Does **not** judge validity — that's the caller's job.
    """
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return _polygon_from_ring(raw)
    if isinstance(raw, Mapping):
        if raw.get("type") in {"Polygon", "MultiPolygon"} and "coordinates" in raw:
            try:
                return shape(dict(raw))
            except Exception:  # noqa: BLE001 - malformed GeoJSON -> no geometry
                return None
        for key in ("polygon", "coordinates", "exterior", "ring", "points"):
            if key in raw:
                return _polygon_from_ring(raw[key])
    return None


def polygon_parts(geom: BaseGeometry | None) -> list[Polygon]:
    """Flatten a geometry into its non-empty polygonal parts (recursing collections)."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        return [p for g in geom.geoms for p in polygon_parts(g)]
    return []


def largest_polygon(geom: BaseGeometry | None) -> Polygon | None:
    """Return the single largest-area polygonal part of a geometry, or ``None``."""
    parts = polygon_parts(geom)
    return max(parts, key=lambda p: p.area) if parts else None


def to_geojson(poly: Polygon) -> dict[str, Any]:
    """A GeoJSON Polygon (exterior only) with rounded coordinates."""
    coords = [[round(x, COORD_NDIGITS), round(y, COORD_NDIGITS)] for x, y in poly.exterior.coords]
    return {"type": "Polygon", "coordinates": [coords]}


def remove_thin_parts(poly: Polygon, min_width: float) -> BaseGeometry:
    """Morphological opening: drop necks/parts narrower than ``min_width``.

    Erode by half the width then dilate back, so anything that can't contain a
    disk of that radius (a corridor thinner than ``min_width``) vanishes while
    thick areas survive. Mitre joins keep square corners intact. The result may
    be empty (the whole footprint was too thin) or split into several pieces (a
    thin neck was severed).
    """
    if min_width <= 0:
        return poly
    r = min_width / 2
    return poly.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")


def shrink_to_area(poly: Polygon, target_area: float) -> BaseGeometry:
    """Erode the polygon inward (uniform inset) until its area ≈ ``target_area``.

    Unlike scaling about the centroid, this keeps the footprint *inside* the
    original outline and following its shape — the natural "we built on less of
    the plot" representation. Area decreases monotonically with the inset
    distance, so a binary search finds it. Returns the original if it's already
    at or below the target.
    """
    if target_area >= poly.area:
        return poly
    lo, hi = 0.0, 1.0
    for _ in range(60):  # grow `hi` until the inset undershoots the target
        if poly.buffer(-hi, join_style="mitre").area <= target_area:
            break
        lo, hi = hi, hi * 2
    for _ in range(40):  # binary-search the inset distance
        mid = (lo + hi) / 2
        if poly.buffer(-mid, join_style="mitre").area > target_area:
            lo = mid
        else:
            hi = mid
    return poly.buffer(-hi, join_style="mitre")
