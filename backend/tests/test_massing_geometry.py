"""Unit tests for the massing algorithm (pure geometry — no DB, no app)."""

import json
import pathlib

import pytest
from shapely.geometry import shape

from app.geometry.config import MassingConfig
from app.geometry.massing import MassingResult, generate_massing
from app.geometry.shapes import remove_thin_parts
from app.v1.verification import VerificationStatus

# Two 20x20 squares joined by a 2m-wide neck (y 9..11) — a corridor too thin to build.
DUMBBELL = [
    [0, 0],
    [20, 0],
    [20, 9],
    [30, 9],
    [30, 0],
    [50, 0],
    [50, 20],
    [30, 20],
    [30, 11],
    [20, 11],
    [20, 20],
    [0, 20],
]

SITES_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "sites"


def _names(result: MassingResult) -> list[str]:
    return [r.name for r in result.reasons]


def _site(name: str) -> dict:
    return json.loads((SITES_DIR / f"{name}.json").read_text())


RECTANGLE = _site("rectangle")["polygon"]  # 40 x 25, area 1000
L_SHAPED = _site("l-shaped")["polygon"]  # concave, area 900
NOTCHED = _site("notched")["polygon"]


# --- Golden path ---------------------------------------------------------


def test_rectangle_pure_inset_area():
    # 3m setback on 40x25 -> 34x19 footprint, no coverage cap binding.
    result = generate_massing(RECTANGLE, {"setback_m": 3, "floor_to_floor_m": 3.5, "max_floors": 6})
    assert result.is_feasible
    assert result.footprint_area == pytest.approx(34 * 19)
    assert result.floor_count == 6
    assert result.gfa == pytest.approx(34 * 19 * 6)
    assert result.footprint["type"] == "Polygon"


def test_rectangle_modest_coverage_binds_area():
    # modest set from constraints.example.json: coverage 0.6 caps the 646 m² inset
    # to 600 m², which then flows through to GFA.
    result = generate_massing(
        RECTANGLE,
        {"setback_m": 3, "floor_to_floor_m": 3.5, "max_height_m": 24, "max_floors": 6, "site_coverage_ratio": 0.6},
    )
    assert result.is_feasible
    assert result.footprint_area == pytest.approx(600.0)  # min(646, 0.6 * 1000)
    assert result.floor_count == 6  # min(floor(24/3.5)=6, 6)
    assert result.gfa == pytest.approx(3600.0)


def test_coverage_cap_erodes_footprint_inside_the_buildable_base():
    # On a concave plot, the area-reducing footprint must erode *inward* and stay
    # within the full inset — a centroid scale would push edges outside the shape.
    full = generate_massing(L_SHAPED, {"setback_m": 2, "max_floors": 3})
    capped = generate_massing(L_SHAPED, {"setback_m": 2, "max_floors": 3, "site_coverage_ratio": 0.4})
    assert capped.is_feasible
    assert capped.footprint_area == pytest.approx(0.4 * 900)  # 0.4 × site area
    assert capped.footprint_area < full.footprint_area
    # The capped footprint is contained in the un-capped one (follows the outline).
    assert shape(full.footprint).buffer(1e-6).contains(shape(capped.footprint))


def test_coverage_reduction_trims_corridors_below_min_width():
    # 30x30 square with a 4m arm. A 0.9 coverage cap erodes the arm below the 3m
    # min corridor width — it must be trimmed, not left as an unbuildable sliver.
    site = [[0, 0], [30, 0], [30, 13], [52, 13], [52, 17], [30, 17], [30, 30], [0, 30]]  # area 988
    cfg = MassingConfig(min_corridor_width=3.0)
    result = generate_massing(site, {"setback_m": 0, "max_floors": 1, "site_coverage_ratio": 0.9}, cfg)
    assert result.is_feasible
    foot = shape(result.footprint)
    # Nothing thinner than the min width survives: opening by it leaves area unchanged.
    assert remove_thin_parts(foot, 3.0).area == pytest.approx(foot.area, rel=0.01)
    # The trimmed arm means the real buildable area is below the raw coverage cap.
    assert result.footprint_area < 0.9 * 988


def test_tower_hits_gfa_target_exactly():
    result = generate_massing(
        RECTANGLE,
        {
            "setback_m": 5,
            "floor_to_floor_m": 4,
            "max_height_m": 80,
            "max_floors": 20,
            "site_coverage_ratio": 0.45,
            "target_gfa": 9000,
        },
    )
    assert result.is_feasible
    assert result.gfa == pytest.approx(9000.0)  # 450 m² * 20 floors
    assert "gfa_target_unmet" not in _names(result)


def test_zero_setback_returns_the_site_itself():
    result = generate_massing(RECTANGLE, {"setback_m": 0, "max_floors": 1})
    assert result.is_feasible
    assert result.footprint_area == pytest.approx(1000.0)
    assert result.floor_count == 1


# --- Concave / degenerate insets (the README edge cases) -----------------


def test_l_shaped_reflex_corner_stays_connected():
    result = generate_massing(L_SHAPED, {"setback_m": 3, "max_floors": 4})
    assert result.is_feasible
    # Inset of a concave plot loses area but stays a single (non-split) footprint.
    assert 0 < result.footprint_area < 900
    assert result.footprint["type"] == "Polygon"
    assert result.reasons == ()  # not split


def test_notched_large_setback_collapses():
    # A 12m setback eats both 20m-wide arms of the notched plot.
    result = generate_massing(NOTCHED, {"setback_m": 12, "floor_to_floor_m": 3.5, "max_floors": 3})
    assert result.status is VerificationStatus.INFEASIBLE
    assert _names(result) == ["setback_collapses_footprint"]
    assert result.footprint is None


def test_notched_moderate_setback_splits_uses_largest_piece():
    # A setback wide enough to sever the notch but not collapse the arms: the
    # inset becomes two pieces and we mass the largest, flagging the split.
    result = generate_massing(NOTCHED, {"setback_m": 6, "max_floors": 2})
    assert result.is_feasible
    assert _names(result) == ["setback_split_used_largest_piece"]
    assert result.footprint["type"] == "Polygon"


# --- Thin corridors (too narrow to build in) -----------------------------


def test_thin_corridor_is_trimmed_to_largest_buildable_piece():
    # The 2m neck is below a 3m min width: it's trimmed, severing the dumbbell,
    # and the largest remaining square (20x20) is massed.
    result = generate_massing(DUMBBELL, {"setback_m": 0, "max_floors": 1}, MassingConfig(min_corridor_width=3.0))
    assert result.is_feasible
    assert "trimmed_thin_parts" in _names(result)
    assert result.footprint_area == pytest.approx(400.0, abs=2)


def test_corridor_kept_when_min_width_is_lower():
    # Drop the threshold below the neck width: nothing is trimmed, the whole
    # dumbbell stays connected.
    result = generate_massing(DUMBBELL, {"setback_m": 0, "max_floors": 1}, MassingConfig(min_corridor_width=1.0))
    assert result.is_feasible
    assert "trimmed_thin_parts" not in _names(result)
    assert result.footprint_area > 800  # both squares + neck


def test_entirely_thin_footprint_is_infeasible():
    strip = [[0, 0], [40, 0], [40, 2], [0, 2]]  # 2m wide everywhere
    result = generate_massing(strip, {"setback_m": 0, "max_floors": 1}, MassingConfig(min_corridor_width=3.0))
    assert result.status is VerificationStatus.INFEASIBLE
    assert _names(result) == ["footprint_too_thin"]
    assert result.footprint is None


# --- Infeasible constraint sets ------------------------------------------


def test_no_floor_or_height_limit_is_infeasible():
    result = generate_massing(RECTANGLE, {"setback_m": 3})
    assert result.status is VerificationStatus.INFEASIBLE
    assert _names(result) == ["no_floor_or_height_limit"]


def test_height_below_floor_to_floor_admits_zero_floors():
    result = generate_massing(RECTANGLE, {"floor_to_floor_m": 3.5, "max_height_m": 3})
    assert result.status is VerificationStatus.INFEASIBLE
    assert _names(result) == ["height_admits_zero_floors"]


def test_unreachable_gfa_target_keeps_constraints_and_flags_unmet():
    # Capacity is 4 * 1000 = 4000 m²; a 10000 target can't be reached without
    # breaking the floor cap, so the constraints win: build the max, flag unmet.
    result = generate_massing(RECTANGLE, {"max_floors": 4, "floor_to_floor_m": 3, "target_gfa": 10_000})
    assert result.is_feasible
    assert result.floor_count == 4
    assert result.gfa == pytest.approx(4000.0)
    assert "gfa_target_unmet" in _names(result)
    assert "reduced_to_gfa_target" not in _names(result)


def test_gfa_target_met_exactly_at_capacity_has_no_notes():
    result = generate_massing(RECTANGLE, {"max_floors": 4, "floor_to_floor_m": 3, "target_gfa": 4000})
    assert result.is_feasible
    assert result.floor_count == 4
    assert result.gfa == pytest.approx(4000.0)
    assert result.reasons == ()  # met at full capacity — nothing to flag


def test_gfa_target_below_capacity_drops_floors_first():
    # Capacity 4000; target 2000 is reachable by halving the floors at full footprint.
    result = generate_massing(RECTANGLE, {"max_floors": 4, "floor_to_floor_m": 3, "target_gfa": 2000})
    assert result.is_feasible
    assert result.floor_count == 2  # 4 -> 2 floors
    assert result.footprint_area == pytest.approx(1000.0)  # footprint untouched
    assert result.gfa == pytest.approx(2000.0)
    assert result.height_m == pytest.approx(6.0)  # 2 * 3, not 12
    assert "reduced_to_gfa_target" in _names(result)


def test_gfa_target_trims_footprint_when_floors_cannot_hit_it():
    # Target 1500: 2 floors at full footprint would be 2000 (too much), 1 floor
    # only 1000 (too little) — so use 2 floors and trim the footprint to 750.
    result = generate_massing(RECTANGLE, {"max_floors": 4, "floor_to_floor_m": 3, "target_gfa": 1500})
    assert result.is_feasible
    assert result.floor_count == 2
    assert result.footprint_area == pytest.approx(750.0)
    assert result.gfa == pytest.approx(1500.0)
    assert "reduced_to_gfa_target" in _names(result)


# --- Bad input -----------------------------------------------------------


def test_self_intersecting_polygon_is_infeasible():
    bowtie = [[0, 0], [2, 2], [2, 0], [0, 2]]
    result = generate_massing(bowtie, {"max_floors": 1})
    assert result.status is VerificationStatus.INFEASIBLE
    assert _names(result) == ["invalid_polygon"]


def test_missing_site_polygon_is_infeasible():
    assert _names(generate_massing(None, {"max_floors": 1})) == ["no_site_polygon"]
    assert _names(generate_massing([[0, 0], [1, 1]], {"max_floors": 1})) == ["no_site_polygon"]


def test_accepts_geojson_polygon_input():
    geojson = {"type": "Polygon", "coordinates": [RECTANGLE + [RECTANGLE[0]]]}
    result = generate_massing(geojson, {"setback_m": 3, "max_floors": 2})
    assert result.is_feasible
    assert result.footprint_area == pytest.approx(34 * 19)


def test_none_constraints_is_infeasible_not_an_error():
    result = generate_massing(RECTANGLE, None)
    assert result.status is VerificationStatus.INFEASIBLE


# --- Property ------------------------------------------------------------


@pytest.mark.parametrize("setback", [0, 1, 2, 5, 8])
def test_footprint_never_exceeds_site_area(setback):
    result = generate_massing(RECTANGLE, {"setback_m": setback, "max_floors": 1})
    if result.is_feasible:
        assert result.footprint_area <= 1000 + 1e-9
