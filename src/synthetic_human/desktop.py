from __future__ import annotations

import asyncio
import html
import platform
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from .artifacts import read_document, read_sheet, write_odf
from .models import Observation


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.hidden += 1
        if tag in ("p", "h1", "h2", "div", "br", "a"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


class SimulationDesktop:
    """Test double, never presented as actual desktop/input telemetry."""

    mode = "simulation"

    def __init__(self, settings):
        self.settings = settings
        self.application = "Simulation"
        self.url = ""
        self.clipboard = ""
        self.effects = 0
        self.inputs = 0
        self.position = (0, 0)

    async def emit(self, primitive):
        self.inputs += 1
        if primitive.kind == "launch":
            self.application = primitive.value[0]
        elif primitive.kind == "move":
            self.position = primitive.value

    def cursor(self):
        return self.position

    def locate_link(self, text):
        return (300, 300)

    async def observe(self, screenshot=None):
        return Observation(
            timestamp=time.time(),
            application=self.application,
            title=self.url,
            focus="simulated",
            accessibility="simulation; no real accessibility evidence",
        )

    async def effect(self, action):
        self.effects += 1
        if action.kind in ("navigate", "follow_link"):
            self.url = action.target
            with urlopen(self.url, timeout=5) as response:
                parser = TextExtractor()
                parser.feed(response.read().decode())
                self.clipboard = html.unescape("".join(parser.parts))
        elif action.kind in ("set_cell", "set_cells"):
            path = Path(action.target)
            cells = {
                k: v["formula"][3:].replace("[.", "").replace("]", "") if v["formula"] else v["value"]
                for k, v in read_sheet(path).items()
            }
            updates = (
                {action.payload["cell"]: action.payload["value"]}
                if action.kind == "set_cell"
                else action.payload["cells"]
            )
            cells.update(updates)
            write_odf(path, cells=cells)
        elif action.kind == "write_document":
            write_odf(Path(action.target), text=action.payload["text"])

    def read_clipboard(self):
        return self.clipboard


class MacDesktop:
    """Only emit() sends input. Observation uses AX and optional screenshots, never invokes controls."""

    mode = "macos"

    def __init__(self, settings):
        if platform.system() != "Darwin":
            raise RuntimeError("macos backend requires macOS")
        import AppKit
        import ApplicationServices as AX
        import CoreFoundation
        import pyautogui
        import Quartz

        self.AX, self.AppKit, self.pg, self.Quartz = AX, AppKit, pyautogui, Quartz
        self.CF = CoreFoundation
        from .native_keyboard import NativeKeyboard

        self.keyboard = NativeKeyboard(Quartz, pyautogui._pyautogui_osx.keyboardMapping)
        self.settings = settings
        self.pg.PAUSE = 0
        self.pg.FAILSAFE = True
        if not AX.AXIsProcessTrusted():
            raise RuntimeError("Accessibility permission is missing; see README. No input has been sent.")

    async def emit(self, primitive):
        self.pg.failSafeCheck()
        kind, value = primitive.kind, primitive.value
        if kind == "hotkey":
            await self.keyboard.hotkey(value)
        elif kind == "key":
            await self.keyboard.key(value)
        elif kind == "text":
            return await self.keyboard.text(value, primitive.hold_seconds)
        elif kind == "scroll":
            self.pg.scroll(int(value))
        elif kind == "click":
            self.pg.click(*value)
        elif kind == "move":
            self.pg.moveTo(*value)
        elif kind == "launch":
            # Native launcher opens the app/document; editing still occurs exclusively by GUI input.
            process = await asyncio.create_subprocess_exec(
                "open", "-a", value[0], *value[1:], stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            if process.returncode:
                raise RuntimeError(stderr.decode())
            # LaunchServices can open an app without bringing its window forward (e.g. another Space).
            # Activate explicitly here; Runtime still verifies focus before any following input.
            deadline = time.monotonic() + 5
            while True:
                applications = self.AppKit.NSWorkspace.sharedWorkspace().runningApplications()
                target = next((app for app in applications if str(app.localizedName()) == value[0]), None)
                if target is not None:
                    if not target.activateWithOptions_(self.AppKit.NSApplicationActivateAllWindows):
                        raise RuntimeError(f"application activation rejected: {value[0]}")
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"application did not launch: {value[0]}")
                await asyncio.sleep(0.2)

    async def effect(self, action):
        pass  # Live execution has no synthetic side effects.

    def read_clipboard(self):
        return subprocess.check_output(["pbpaste"], timeout=5).decode("utf-8")

    def browser_viewport(self):
        from .viewport import capture

        return capture(self)

    def _attribute(self, element, name):
        err, value = self.AX.AXUIElementCopyAttributeValue(element, name, None)
        return value if err == 0 else None

    def cursor(self):
        return tuple(self.pg.position())

    def _front_application(self):
        # AppKit caches time-varying app properties until its run loop advances. asyncio alone
        # does not drive that loop, so otherwise focus can remain frozen at the initial app.
        self.CF.CFRunLoopRunInMode(self.CF.kCFRunLoopDefaultMode, 0.002, False)
        return self.AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()

    def locate_link(self, text):
        app = self._front_application()
        root = self.AX.AXUIElementCreateApplication(app.processIdentifier())
        pending = [root]
        visited = 0
        deadline = time.monotonic() + 1.5
        while pending and visited < 1200 and time.monotonic() < deadline:
            element = pending.pop()
            visited += 1
            role = self._attribute(element, "AXRole")
            label = " ".join(
                str(self._attribute(element, key) or "") for key in ("AXTitle", "AXDescription", "AXValue")
            )
            if role == "AXLink" and text in label:
                position = self._attribute(element, "AXPosition")
                size = self._attribute(element, "AXSize")
                if position and size:
                    ok_p, point = self.AX.AXValueGetValue(position, self.AX.kAXValueCGPointType, None)
                    ok_s, extent = self.AX.AXValueGetValue(size, self.AX.kAXValueCGSizeType, None)
                    if ok_p and ok_s and extent.width > 0 and extent.height > 0:
                        return (point.x + extent.width / 2, point.y + extent.height / 2)
            pending.extend(self._attribute(element, "AXChildren") or [])
        return None

    async def observe(self, screenshot=None):
        app = self._front_application()
        ax_app = self.AX.AXUIElementCreateApplication(app.processIdentifier())
        window = self._attribute(ax_app, "AXFocusedWindow")
        focus = self._attribute(ax_app, "AXFocusedUIElement")
        title = str(self._attribute(window, "AXTitle") or "") if window else ""
        document_uri = str(self._attribute(window, "AXDocument") or "") if window else ""
        focus_text = ""
        if focus:
            focus_text = " ".join(
                str(self._attribute(focus, key) or "")
                for key in ("AXRole", "AXTitle", "AXDescription", "AXValue")
            )[:4000]
        screenshot_path = None
        error = None
        if screenshot:
            if self.Quartz.CGPreflightScreenCaptureAccess():
                try:
                    self.pg.screenshot().save(screenshot)
                    screenshot_path = str(screenshot)
                except Exception as exc:
                    error = str(exc)
            else:
                error = "Screen Recording permission missing; screenshot unavailable"
        return Observation(
            timestamp=time.time(),
            application=str(app.localizedName()),
            title=title,
            document_uri=document_uri,
            focus=focus_text,
            accessibility=focus_text,
            screenshot=screenshot_path,
            error=error,
        )


def document_matches(target, observation):
    uri = urlparse(observation.document_uri)
    return uri.scheme == "file" and Path(unquote(uri.path)).resolve() == Path(target).resolve()


def matches(action, observation, desktop):
    """Read independently persisted document state; never trust command success alone."""
    if action.kind in ("set_cell", "set_cells"):
        try:
            sheet = read_sheet(Path(action.target))
            updates = (
                {action.payload["cell"]: action.payload["value"]}
                if action.kind == "set_cell"
                else action.payload["cells"]
            )
            for address, expected_value in updates.items():
                cell = sheet.get(address, {})
                expected = str(expected_value)
                if expected.startswith("="):
                    actual = (cell.get("formula") or "").replace("[.", "").replace("]", "")
                    if actual.removeprefix("of:") != expected:
                        return False
                else:
                    value = cell.get("value", "")
                    try:
                        equal = float(value) == float(expected)
                    except ValueError:
                        equal = value == expected
                    if not equal:
                        return False
            return True
        except (OSError, ValueError, KeyError, BadZipFile, ParseError):
            return False
    if action.kind == "write_document":
        try:
            return read_document(Path(action.target)) == action.payload["text"]
        except (OSError, ValueError, BadZipFile, ParseError):
            return False
    if action.kind == "open_file":
        return desktop.mode == "simulation" or document_matches(action.target, observation)
    if action.kind in ("navigate", "follow_link", "read_page"):
        return action.expected.get("contains", "") in desktop.read_clipboard()
    return True
