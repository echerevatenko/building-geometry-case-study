from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Polygon:
    id: int
    title: str
    site_polygon: dict[str, Any] | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
