async def test_create_then_read_round_trip(client):
    coords = [[0, 0], [10, 0], [10, 5], [0, 5]]
    created = await client.post(
        "/api/v1/polygons",
        json={"title": "Site A", "site_polygon": {"coordinates": coords}},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Site A"
    assert body["site_polygon"]["coordinates"] == coords
    assert body["is_deleted"] is False

    fetched = await client.get(f"/api/v1/polygons/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


async def test_get_missing_polygon_returns_404(client):
    assert (await client.get("/api/v1/polygons/999999")).status_code == 404
