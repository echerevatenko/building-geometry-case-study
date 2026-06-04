import json
import pathlib

from app.geometry.config import MassingConfig
from app.geometry.site import SiteStatus, parse_site

SITES_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "sites"
CONFIG = MassingConfig(min_site_area=10.0)


def _site(name: str) -> list:
    return json.loads((SITES_DIR / f"{name}.json").read_text())["polygon"]


RECTANGLE = _site("rectangle")  # 40 x 25, area 1000
L_SHAPED = _site("l-shaped")  # concave, area 900
NOTCHED = _site("notched")


def test_plain_rectangle_is_valid():
    parsed = parse_site({"polygon": RECTANGLE}, CONFIG)
    assert parsed.status is SiteStatus.VALID
    assert parsed.reason is None  # nothing to explain when valid
    assert parsed.base is not None and parsed.base["type"] == "Polygon"


def test_concave_l_shape_is_valid_single_piece():
    parsed = parse_site({"polygon": L_SHAPED}, CONFIG)
    assert parsed.status is SiteStatus.VALID
    assert parsed.has_base


def test_notched_is_valid_until_a_setback_splits_it():
    # The notched plot is one simple polygon at save time; splitting only happens
    # per-option when a setback is applied, so the site itself is valid.
    parsed = parse_site({"polygon": NOTCHED}, CONFIG)
    assert parsed.status is SiteStatus.VALID


def test_self_intersection_is_repaired_to_semi_valid():
    bowtie = [[0, 0], [10, 10], [10, 0], [0, 10]]
    parsed = parse_site({"polygon": bowtie}, CONFIG)
    assert parsed.status is SiteStatus.SEMI_VALID
    assert parsed.has_base  # largest repaired piece kept
    assert parsed.reason is not None
    assert parsed.reason.name in {"kept_largest_piece", "repaired_self_intersection"}


def test_geojson_multipolygon_keeps_largest_piece():
    small = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
    big = [[100, 100], [140, 100], [140, 125], [100, 125], [100, 100]]
    parsed = parse_site({"type": "MultiPolygon", "coordinates": [[small], [big]]}, CONFIG)
    assert parsed.status is SiteStatus.SEMI_VALID
    assert parsed.reason is not None and parsed.reason.name == "kept_largest_piece"


def test_below_min_site_area_is_invalid():
    tiny = [[0, 0], [2, 0], [2, 2], [0, 2]]  # 4 m² < 10
    parsed = parse_site({"polygon": tiny}, CONFIG)
    assert parsed.status is SiteStatus.INVALID
    assert parsed.reason is not None and parsed.reason.name == "below_min_site_area"
    assert parsed.base is None


def test_degenerate_collinear_is_invalid():
    line = [[0, 0], [10, 0], [20, 0]]  # zero area
    parsed = parse_site({"polygon": line}, CONFIG)
    assert parsed.status is SiteStatus.INVALID
    assert parsed.base is None


def test_no_coordinates_is_empty():
    assert parse_site(None, CONFIG).status is SiteStatus.EMPTY
    assert parse_site({"polygon": [[0, 0], [1, 1]]}, CONFIG).status is SiteStatus.EMPTY  # <3 points
    assert parse_site({}, CONFIG).status is SiteStatus.EMPTY


def test_min_site_area_is_configurable():
    site = {"polygon": [[0, 0], [5, 0], [5, 5], [0, 5]]}  # 25 m²
    assert parse_site(site, MassingConfig(min_site_area=10.0)).status is SiteStatus.VALID
    assert parse_site(site, MassingConfig(min_site_area=50.0)).status is SiteStatus.INVALID
