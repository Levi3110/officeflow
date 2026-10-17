"""Quartz keyboard delivery with explicit flags and matching text/physical key codes."""

import asyncio
import time


class NativeKeyboard:
    def __init__(self, quartz, mapping):
        self.q, self.mapping = quartz, mapping
        self.source = quartz.CGEventSourceCreate(quartz.kCGEventSourceStatePrivate)
        self.modifiers = {
            "command": quartz.kCGEventFlagMaskCommand,
            "shift": quartz.kCGEventFlagMaskShift,
            "ctrl": quartz.kCGEventFlagMaskControl,
            "alt": quartz.kCGEventFlagMaskAlternate,
        }

    def post(self, key, down, flags=0, text=None):
        code = self.mapping.get(key.lower())
        if code is None:
            if text is None:
                raise ValueError(f"unsupported native key: {key}")
            code = 0  # Unicode fallback for characters outside the documented US layout.
        event = self.q.CGEventCreateKeyboardEvent(self.source, code, down)
        self.q.CGEventSetFlags(event, flags)
        if text is not None:
            self.q.CGEventKeyboardSetUnicodeString(event, len(text.encode("utf-16-le")) // 2, text)
        self.q.CGEventPost(self.q.kCGHIDEventTap, event)

    async def text(self, value, hold_seconds):
        key = {"\n": "enter", "\t": "tab"}.get(value, value)
        text = None if value in ("\n", "\t") else value
        shifted = value.isupper() or value in '~!@#$%^&*()_+{}|:"<>?'
        flags = self.modifiers["shift"] if shifted else 0
        if shifted:
            self.post("shift", True, flags)
        started = time.monotonic()
        try:
            self.post(key, True, flags, text)
            try:
                await asyncio.sleep(hold_seconds)
            finally:
                self.post(key, False, flags, text)
        finally:
            if shifted:
                self.post("shift", False)
        return {"hold_elapsed_seconds": time.monotonic() - started}

    async def hotkey(self, keys):
        held, flags = [], 0
        try:
            for key in keys:
                flags |= self.modifiers.get(key, 0)
                self.post(key, True, flags)
                held.append(key)
                await asyncio.sleep(0.035)
        finally:
            for key in reversed(held):
                flags &= ~self.modifiers.get(key, 0)
                self.post(key, False, flags)

    async def key(self, value):
        self.post(value, True)
        try:
            await asyncio.sleep(0.045)
        finally:
            self.post(value, False)
