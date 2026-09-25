"""Tests for the poster edit list."""

import pytest
from shapely.geometry import box

import map2plotter.edits as pe

VALID = {
    "version": 1,
    "erase": [[[10, 10], [50, 10], [50, 40]]],
    "text": {"city": {"dy": -5}},
    "hidden_layers": ["parks"],
}


def test_valid_edit_list():
    edits = pe.parse_edits(VALID)
    assert edits.erase == [[(10, 10), (50, 10), (50, 40)]]
    assert edits.text_edit("city").dy == -5
    assert edits.text_edit("coords") == pe.TextEdit()
    assert edits.layer_hidden("parks") and not edits.layer_hidden("water")


def test_empty_object_changes_nothing():
    edits = pe.parse_edits({})
    assert edits.is_empty()
    assert edits.erase_area(300, 400).is_empty


@pytest.mark.parametrize(
    "data, fragment",
    [
        ({"hidden_layers": ["buildings"]}, "buildings"),
        ({"erase": [[[0, 0], [1, 1]]]}, "erase[0]"),
        ({"erase": [[[0, 0], [1, "a"], [2, 2]]]}, "erase[0][1]"),
        ({"erase": [[[0, 0], [1, True], [2, 2]]]}, "erase[0][1]"),
        ({"text": {"title": {}}}, "title"),
        ({"text": {"city": {"rotate": 3}}}, "rotate"),
        ({"text": {"city": {"hidden": "yes"}}}, "hidden"),
        ({"version": 2}, "version"),
        ({"layers": []}, "layers"),
        ([], "object"),
    ],
)
def test_invalid_edit_lists(data, fragment):
    with pytest.raises(pe.EditsError, match=None) as err:
        pe.parse_edits(data)
    assert fragment in str(err.value)


def test_bad_json_file(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(pe.EditsError, match="not valid JSON"):
        pe.load_edits(path)


def test_missing_file(tmp_path):
    with pytest.raises(pe.EditsError, match="Cannot read"):
        pe.load_edits(tmp_path / "missing.json")


def test_erase_area_clipped_to_page():
    edits = pe.parse_edits({"erase": [[[-10, -10], [20, -10], [20, 20], [-10, 20]]]})
    area = edits.erase_area(100, 100)
    assert area.equals(box(0, 0, 20, 20))


def test_self_intersecting_polygon_is_repaired():
    edits = pe.parse_edits({"erase": [[[0, 0], [10, 10], [10, 0], [0, 10]]]})
    area = edits.erase_area(100, 100)
    assert area.is_valid and area.area > 0


def test_round_trip():
    edits = pe.parse_edits(VALID)
    assert pe.parse_edits(edits.to_dict()) == edits
