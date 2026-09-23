from solver.adapter import layout_to_floorplan
from solver.models import Envelope, FurnitureFootprint, Layout, PlacedRoom


def test_layout_to_floorplan_exports_furniture():
    living = PlacedRoom("liv", "living_room", "Living", 0, 0, 16, 14, "public")
    layout = Layout(
        rooms=[living],
        furniture=[FurnitureFootprint("sofa-1", "liv", "sofa", 2, 2, 7, 3)],
        envelope=Envelope(20, 20),
    )
    payload = layout_to_floorplan(layout)
    assert len(payload["furniture"]) == 1
    item = payload["furniture"][0]
    assert item["id"] == "sofa-1"
    assert item["roomId"] == "liv"
    assert item["kind"] == "sofa"
    assert item["width"] == 7
    assert item["depth"] == 3
