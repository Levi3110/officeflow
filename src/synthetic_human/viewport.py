"""Read-only AX viewport evidence; wheel dispatch alone is not proof of scrolling."""

from collections import deque


def capture(desktop):
    app = desktop._front_application()
    root = desktop.AX.AXUIElementCreateApplication(app.processIdentifier())
    window = desktop._attribute(root, "AXFocusedWindow")
    pending = deque([window] if window else [])
    visited = 0
    area = None
    while pending and visited < 800:
        element = pending.popleft()
        visited += 1
        if desktop._attribute(element, "AXRole") == "AXWebArea":
            title = str(desktop._attribute(element, "AXTitle") or "")
            if title != "Omnibox Popup":
                area = element
                break
        pending.extend(desktop._attribute(element, "AXChildren") or [])
    if area is None:
        return None

    def bounds(element):
        position = desktop._attribute(element, "AXPosition")
        size = desktop._attribute(element, "AXSize")
        if position is None or size is None:
            return None
        ok_p, point = desktop.AX.AXValueGetValue(position, desktop.AX.kAXValueCGPointType, None)
        ok_s, extent = desktop.AX.AXValueGetValue(size, desktop.AX.kAXValueCGSizeType, None)
        if not ok_p or not ok_s or extent.width <= 0 or extent.height <= 0:
            return None
        return [point.x, point.y, extent.width, extent.height]

    rectangle = bounds(area)
    if rectangle is None:
        return None
    anchors = {}
    pending = deque(desktop._attribute(area, "AXChildren") or [])
    while pending and visited < 1200 and len(anchors) < 12:
        element = pending.popleft()
        visited += 1
        role = desktop._attribute(element, "AXRole")
        if role in ("AXHeading", "AXLink", "AXStaticText"):
            label = str(
                desktop._attribute(element, "AXTitle") or desktop._attribute(element, "AXValue") or ""
            )
            location = bounds(element)
            if label and location:
                anchors.setdefault(f"{role}:{label[:180]}", location[1] - rectangle[1])
        pending.extend(desktop._attribute(element, "AXChildren") or [])
    return {
        "source": "macOS AX element positions relative to web area",
        "page": str(desktop._attribute(area, "AXTitle") or ""),
        "bounds": rectangle,
        "anchors": anchors,
    }


def displacement(before, after):
    if not before or not after or before["page"] != after["page"]:
        return None
    # Ignore window moves; compare positions relative to the web viewport.
    changes = [
        after["anchors"][key] - value
        for key, value in before["anchors"].items()
        if key in after["anchors"] and abs(after["anchors"][key] - value) > 2
    ]
    return changes[0] if changes else None
