from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class MassingOption:
    id: int
    polygon_id: int
    parent_id: int | None
    name: str | None
    position: int
    footprint: dict[str, Any] | None
    constraints: dict[str, Any] | None
    floor_count: int | None
    footprint_area: float | None
    gfa: float | None
    verification_result: str | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
