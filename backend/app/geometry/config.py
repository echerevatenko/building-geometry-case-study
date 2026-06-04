from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MassingConfig:
    """Tunable rules for the massing/site algorithm."""

    # Smallest buildable-base area (m²) a saved site may have; below this the
    # polygon is stored but marked `invalid`, so no options can be built on it.
    min_site_area: float = 2.0
    # Narrowest part (m) of a footprint worth building in; corridors thinner than
    # this are trimmed (morphological opening) before metrics are computed.
    min_corridor_width: float = 1.0
