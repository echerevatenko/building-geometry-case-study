from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Reason:
    name: str
    message: str


# --- Site validation (computed when a polygon is saved) ----------------------
REPAIRED_SELF_INTERSECTION = Reason(
    "repaired_self_intersection",
    "The site outline was self-intersecting and has been repaired.",
)
KEPT_LARGEST_PIECE = Reason(
    "kept_largest_piece",
    "The site resolved into several pieces; the largest was kept to build on.",
)
NO_COORDINATES = Reason("no_coordinates", "The site has no usable coordinates.")
DEGENERATE_SITE = Reason("degenerate_or_zero_area", "The site outline is degenerate and encloses no area.")
BELOW_MIN_SITE_AREA = Reason("below_min_site_area", "The site is smaller than the minimum buildable area.")

# --- Massing generation (computed per option) --------------------------------
NO_SITE_POLYGON = Reason("no_site_polygon", "The site has no buildable base to mass.")
INVALID_POLYGON = Reason("invalid_polygon", "The buildable base is not a valid polygon.")
ZERO_AREA_SITE = Reason("zero_area_site", "The buildable base encloses no area.")
NO_FLOOR_OR_HEIGHT_LIMIT = Reason(
    "no_floor_or_height_limit",
    "No height or floor-count limit was given, so floors can't be stacked.",
)
HEIGHT_ADMITS_ZERO_FLOORS = Reason("height_admits_zero_floors", "The height limit is too low to fit a single floor.")
SETBACK_COLLAPSES_FOOTPRINT = Reason("setback_collapses_footprint", "The setback leaves no buildable footprint.")
SETBACK_SPLIT_USED_LARGEST = Reason(
    "setback_split_used_largest_piece",
    "The setback split the site into pieces; the largest was massed.",
)
FOOTPRINT_TOO_THIN = Reason("footprint_too_thin", "The buildable footprint is everywhere too narrow to build in.")
TRIMMED_THIN_PARTS = Reason(
    "trimmed_thin_parts",
    "Corridors too narrow to build in were trimmed from the footprint.",
)
GFA_TARGET_UNMET = Reason("gfa_target_unmet", "The GFA target can't be reached within the height/floor limits.")
REDUCED_TO_GFA_TARGET = Reason(
    "reduced_to_gfa_target",
    "The mass was scaled below the site's capacity to meet the GFA target.",
)

# Reverse lookup so a stored ``name`` can be rehydrated into a full Reason on read.
BY_NAME: dict[str, Reason] = {
    r.name: r
    for r in (
        REPAIRED_SELF_INTERSECTION,
        KEPT_LARGEST_PIECE,
        NO_COORDINATES,
        DEGENERATE_SITE,
        BELOW_MIN_SITE_AREA,
        NO_SITE_POLYGON,
        INVALID_POLYGON,
        ZERO_AREA_SITE,
        NO_FLOOR_OR_HEIGHT_LIMIT,
        HEIGHT_ADMITS_ZERO_FLOORS,
        SETBACK_COLLAPSES_FOOTPRINT,
        SETBACK_SPLIT_USED_LARGEST,
        FOOTPRINT_TOO_THIN,
        TRIMMED_THIN_PARTS,
        GFA_TARGET_UNMET,
        REDUCED_TO_GFA_TARGET,
    )
}
