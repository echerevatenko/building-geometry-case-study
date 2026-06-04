import pytest

RECTANGLE = [[0, 0], [40, 0], [40, 25], [0, 25]]


async def test_create_with_unknown_polygon_is_404(client):
    resp = await client.post("/api/v1/massing-options", json={"polygon_id": 999999})
    assert resp.status_code == 404, resp.text
    assert "detail" in resp.json()


async def test_create_with_unknown_parent_is_400(client):
    polygon = (
        await client.post("/api/v1/polygons", json={"title": "P", "site_polygon": {"polygon": RECTANGLE}})
    ).json()
    resp = await client.post(
        "/api/v1/massing-options",
        json={"polygon_id": polygon["id"], "parent_id": 999999},
    )
    assert resp.status_code == 400, resp.text


async def test_create_on_invalid_site_is_409(client):
    # A degenerate (zero-area) site saves but is invalid -> no buildable base.
    polygon = (
        await client.post(
            "/api/v1/polygons",
            json={"title": "Bad", "site_polygon": {"polygon": [[0, 0], [40, 0], [20, 0]]}},
        )
    ).json()
    assert polygon["geometry_status"] == "invalid"
    # The reason carries both a stable name and a human message for the UI.
    assert polygon["geometry_reason"]["name"] == "degenerate_or_zero_area"
    assert polygon["geometry_reason"]["message"]
    resp = await client.post("/api/v1/massing-options", json={"polygon_id": polygon["id"]})
    assert resp.status_code == 409, resp.text


async def _make_option(client, *, site_polygon, constraints):
    polygon = (await client.post("/api/v1/polygons", json={"title": "Site", "site_polygon": site_polygon})).json()
    option = (
        await client.post(
            "/api/v1/massing-options",
            json={"polygon_id": polygon["id"], "constraints": constraints},
        )
    ).json()
    return option


async def test_generate_unknown_option_is_404(client):
    resp = await client.post("/api/v1/massing-options/999999/generate")
    assert resp.status_code == 404, resp.text


async def test_generate_computes_feasible_mass_from_saved_constraints(client):
    option = await _make_option(
        client,
        site_polygon={"polygon": RECTANGLE},
        constraints={
            "setback_m": 3,
            "floor_to_floor_m": 3.5,
            "max_height_m": 24,
            "max_floors": 6,
            "site_coverage_ratio": 0.6,
        },
    )

    # No body -> falls back to the option's saved constraints.
    resp = await client.post(f"/api/v1/massing-options/{option['id']}/generate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verification_result"] == "feasible"
    assert body["floor_count"] == 6
    assert body["footprint_area"] == pytest.approx(600.0)
    assert body["gfa"] == pytest.approx(3600.0)
    assert body["footprint"]["type"] == "Polygon"
    assert body["reasons"] == []  # plainly feasible -> nothing to explain


async def test_update_persists_metrics_and_verification(client):
    option = await _make_option(
        client, site_polygon={"polygon": RECTANGLE}, constraints={"setback_m": 3, "max_floors": 4}
    )
    resp = await client.patch(
        f"/api/v1/massing-options/{option['id']}",
        json={"floor_count": 4, "footprint_area": 600.0, "gfa": 2400.0, "verification_result": "feasible"},
    )
    assert resp.status_code == 200, resp.text

    fetched = (await client.get(f"/api/v1/polygons/{option['polygon_id']}/massing-options")).json()[0]
    assert fetched["floor_count"] == 4
    assert fetched["footprint_area"] == pytest.approx(600.0)
    assert fetched["gfa"] == pytest.approx(2400.0)
    assert fetched["verification_result"] == "feasible"
