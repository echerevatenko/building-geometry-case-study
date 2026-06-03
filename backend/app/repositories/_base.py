from __future__ import annotations

from typing import Final


class _Unset:
    """Sentinel for "argument not provided" in partial updates.

    Distinguishes "leave this column alone" from an explicit ``None`` (which is
    a meaningful value for nullable columns such as ``massing_option.parent_id``).
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNSET"


UNSET: Final = _Unset()
