from app.repositories.massing_option import MassingOptionRepository
from app.repositories.polygon import PolygonRepository


async def test_delete_cascades_to_whole_subtree_and_spares_siblings(conn):
    polygons = PolygonRepository(conn)
    options = MassingOptionRepository(conn)

    polygon = await polygons.add(title="P")
    root = await options.add(polygon_id=polygon.id, name="root")
    child = await options.add(polygon_id=polygon.id, parent_id=root.id, name="child")
    await options.add(polygon_id=polygon.id, parent_id=child.id, name="grandchild")
    await options.add(polygon_id=polygon.id, name="sibling")

    # Deleting the root walks parent_id down and soft-deletes root + child + grandchild.
    deleted = await options.delete(root.id)
    assert deleted == 3

    remaining = await options.list_for_polygon(polygon.id)
    assert [o.name for o in remaining] == ["sibling"]

    # Already-deleted nodes are not deleted again.
    assert await options.delete(root.id) == 0


async def test_partial_update_leaves_unspecified_columns_untouched(conn):
    polygons = PolygonRepository(conn)
    options = MassingOptionRepository(conn)

    polygon = await polygons.add(title="P")
    opt = await options.add(polygon_id=polygon.id, name="orig", constraints={"setback_m": 2}, floor_count=3)

    # Updating only the name must not disturb the jsonb / scalar columns.
    updated = await options.update(opt.id, name="renamed")
    assert updated is not None
    assert updated.name == "renamed"
    assert updated.constraints == {"setback_m": 2}
    assert updated.floor_count == 3


async def test_update_distinguishes_unset_from_explicit_none(conn):
    polygons = PolygonRepository(conn)
    options = MassingOptionRepository(conn)

    polygon = await polygons.add(title="P")
    opt = await options.add(polygon_id=polygon.id, name="keep", constraints={"setback_m": 2})

    # Explicit None clears a nullable jsonb column; the omitted name is left alone.
    cleared = await options.update(opt.id, constraints=None)
    assert cleared is not None
    assert cleared.constraints is None
    assert cleared.name == "keep"

    # parent_id=None is meaningful: it re-roots a child option.
    child = await options.add(polygon_id=polygon.id, parent_id=opt.id, name="child")
    rerooted = await options.update(child.id, parent_id=None)
    assert rerooted is not None
    assert rerooted.parent_id is None
