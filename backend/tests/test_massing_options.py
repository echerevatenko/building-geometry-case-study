async def test_create_with_unknown_polygon_is_400_not_500(client):
    resp = await client.post("/api/v1/massing-options", json={"polygon_id": 999999})
    assert resp.status_code == 400, resp.text
    assert "detail" in resp.json()


async def test_create_with_unknown_parent_is_400(client):
    polygon = (await client.post("/api/v1/polygons", json={"title": "P"})).json()
    resp = await client.post(
        "/api/v1/massing-options",
        json={"polygon_id": polygon["id"], "parent_id": 999999},
    )
    assert resp.status_code == 400, resp.text
