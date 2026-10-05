from __future__ import annotations

import copy

from workflow.scene_diff import MAX_LINES, summarize_changes


def base_scene() -> dict:
    return {
        "version": "2.0",
        "units": "metric",
        "floors": 1,
        "site": {"width": 12, "depth": 20},
        "floorData": [{"id": "f1", "level": 0}],
        "metadata": {"createdAt": "a", "updatedAt": "a"},
        "rooms": [
            {"id": "bed2", "name": "Bedroom 2", "position": {"x": 0, "y": 0}, "dimensions": {"width": 3, "height": 4}, "area": 12},
            {"id": "kit", "name": "Kitchen", "position": {"x": 3, "y": 0}, "dimensions": {"width": 4, "height": 4}, "area": 16},
            {"id": "great", "name": "Great Room", "position": {"x": 0, "y": 4}, "dimensions": {"width": 7, "height": 5}, "area": 35},
        ],
        "walls": [
            {"id": "w-great", "start": {"x": 0, "y": 6.5}, "end": {"x": 7, "y": 6.5}, "thickness": 0.15},
        ],
        "openings": [
            {"id": "d1", "type": "door", "wallId": "w1", "position": {"x": 1.5, "y": 0}, "width": 0.9, "height": 2.1},
        ],
        "furniture": [
            {"id": "f-bed", "kind": "bed", "roomId": "bed2", "position": {"x": 1, "y": 1}, "rotation": 0},
        ],
    }


def test_no_meaningful_change_reports_details_updated():
    assert summarize_changes(base_scene(), base_scene()) == ["Design details updated"]


def test_initial_version():
    assert summarize_changes(None, base_scene()) == ["Initial version submitted"]


def test_room_area_rename_add_remove():
    nxt = base_scene()
    nxt["rooms"][0]["area"] = 13.2
    nxt["rooms"][1]["name"] = "Kitchenette"
    nxt["rooms"].append({"id": "study", "name": "Study", "position": {"x": 8, "y": 0}, "dimensions": {"width": 2, "height": 2}})
    nxt["rooms"] = [r for r in nxt["rooms"] if r["id"] != "great"]
    lines = summarize_changes(base_scene(), nxt)
    assert "Bedroom 2 area increased by 1.2 m²" in lines
    assert "Kitchen renamed to Kitchenette" in lines
    assert "Study added" in lines
    assert "Great Room removed" in lines


def test_wall_moved_and_thickness():
    nxt = base_scene()
    nxt["walls"][0]["start"]["y"] = 6.8
    nxt["walls"][0]["end"]["y"] = 6.8
    nxt["walls"][0]["thickness"] = 0.25
    lines = summarize_changes(base_scene(), nxt)
    assert "Great Room wall moved" in lines
    assert "Great Room wall thickness changed" in lines


def test_openings_moved_added_removed_and_legacy_shape():
    nxt = base_scene()
    nxt["openings"][0]["position"]["x"] = 2.1
    nxt["openings"].append({"id": "win1", "type": "window", "position": {"x": 5, "y": 0}, "width": 1.2, "height": 1.2})
    lines = summarize_changes(base_scene(), nxt)
    assert "Bedroom 2 door position changed" in lines
    assert "Kitchen window added" in lines

    prev_legacy = {"rooms": base_scene()["rooms"], "openings": {"doors": [{"id": "d1", "x": 1.5, "y": 0, "width": 0.9}], "windows": []}}
    next_legacy = copy.deepcopy(prev_legacy)
    next_legacy["openings"]["doors"] = []
    assert "Bedroom 2 door removed" in summarize_changes(prev_legacy, next_legacy)


def test_furniture_and_site():
    nxt = base_scene()
    nxt["furniture"][0]["position"]["x"] = 2
    nxt["furniture"].append({"id": "f-sofa", "kind": "sofa", "roomId": "great", "position": {"x": 2, "y": 5}, "rotation": 0})
    nxt["site"]["width"] = 14
    lines = summarize_changes(base_scene(), nxt)
    assert "Bedroom 2 bed moved" in lines
    assert "Great Room sofa added" in lines
    assert "Site details changed" in lines


def test_floor_membership_lists_are_not_floor_setting_changes():
    prev = base_scene()
    prev["floorData"][0].update({"height": 3, "wallIds": ["w-great"], "roomIds": [], "openingIds": [], "stairIds": []})
    nxt = copy.deepcopy(prev)
    nxt["walls"].append({"id": "w-new", "start": {"x": 20, "y": 0}, "end": {"x": 22, "y": 0}, "thickness": 0.15})
    nxt["floorData"][0]["wallIds"].append("w-new")
    lines = summarize_changes(prev, nxt)
    assert "Wall added" in lines
    assert "Floor settings changed" not in lines
    nxt["floorData"][0]["height"] = 3.2
    assert "Floor settings changed" in summarize_changes(prev, nxt)


def test_long_summaries_are_capped():
    nxt = base_scene()
    nxt["rooms"] += [
        {"id": f"r{i}", "name": f"Room {i}", "position": {"x": 20 + i, "y": 0}, "dimensions": {"width": 1, "height": 1}}
        for i in range(20)
    ]
    lines = summarize_changes(base_scene(), nxt)
    assert len(lines) == MAX_LINES
    assert lines[-1].startswith("and ") and lines[-1].endswith("more changes")
