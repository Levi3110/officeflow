from __future__ import annotations

import re

from .models import Primitive as P


class ApplicationAdapters:
    def __init__(self, settings):
        self.settings = settings
        self.mod = "command"

    def plan(self, action, current_application=None):
        kind, data = action.kind, action.payload
        if kind == "navigate":
            launch = (
                []
                if current_application == self.settings.browser_app
                else [
                    P(kind="launch", value=[self.settings.browser_app]),
                    P(kind="pause", value="switch"),
                ]
            )
            return launch + [
                P(kind="hotkey", value=[self.mod, "l"]),
                P(kind="text", value=action.target),
                P(kind="key", value="enter"),
            ]
        if kind == "follow_link":
            # Find the visible link, then activate it using browser keyboard focus.
            return [
                P(kind="hotkey", value=[self.mod, "f"]),
                P(kind="text", value=data["link_text"]),
                P(kind="key", value="escape"),
            ]
        if kind == "read_page":
            # Runtime verification performs one fresh GUI copy and validates the captured text.
            return []
        if kind == "scroll":
            return [P(kind="scroll", value=data.get("amount", -4)), P(kind="pause", value="read")]
        if kind == "open_file":
            result = [P(kind="launch", value=[self.settings.office_app, action.target])]
            if current_application != self.settings.office_app:
                result.append(P(kind="pause", value="switch"))
            return result
        if kind in ("set_cell", "set_cells"):
            cells = {data["cell"]: data["value"]} if kind == "set_cell" else data["cells"]
            if not cells:
                raise ValueError("empty cell edit")
            coordinates = [re.fullmatch(r"([A-H])([1-9]\d?)", address) for address in cells]
            if any(match is None for match in coordinates):
                raise ValueError("MVP supports A1:H99")
            addresses = sorted(cells, key=lambda address: (int(address[1:]), address[0]))
            match = re.fullmatch(r"([A-H])([1-9]\d?)", addresses[0])
            if not match:
                raise ValueError("MVP supports A1:H99")
            col, row = ord(match[1]) - 65, int(match[2]) - 1
            if any(address != f"{chr(65 + col + index)}{row + 1}" for index, address in enumerate(addresses)):
                raise ValueError("set_cells requires contiguous cells in one row")
            # Go from A1 each time: replay overwrites the cell instead of appending.
            steps = [P(kind="key", value="escape"), P(kind="hotkey", value=[self.mod, "home"])]
            steps += [P(kind="key", value="right")] * col + [P(kind="key", value="down")] * row
            for index, address in enumerate(addresses):
                steps += [
                    P(kind="text", value=str(cells[address])),
                    P(kind="key", value="enter" if index == len(addresses) - 1 else "tab"),
                ]
            steps.append(P(kind="hotkey", value=[self.mod, "s"]))
            return steps
        if kind == "write_document":
            return [
                P(kind="hotkey", value=[self.mod, "a"]),
                P(kind="text", value=data["text"], allow_typo=True),
                P(kind="hotkey", value=[self.mod, "s"]),
            ]
        raise ValueError(f"unsupported action: {kind}")

    def expected_app(self, action):
        if action.kind in ("navigate", "follow_link", "read_page", "scroll"):
            return self.settings.browser_app
        return self.settings.office_app
