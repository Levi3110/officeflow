from synthetic_human.viewport import displacement


def test_scroll_evidence_requires_same_page_and_matching_content():
    before = {"page": "Products", "bounds": [0, 100, 800, 600], "anchors": {"AXHeading:Products": 50}}
    assert displacement(before, {**before, "anchors": {"AXHeading:Products": -30}}) == -80
    assert displacement(before, {**before, "page": "Other", "anchors": {"AXHeading:Products": -30}}) is None
    assert displacement(before, {**before, "anchors": {"AXHeading:Other": -30}}) is None
    assert displacement(before, {**before, "bounds": [100, 400, 800, 600]}) is None
    assert displacement(before, {**before, "anchors": {"AXHeading:Products": 49}}) is None
