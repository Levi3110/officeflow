import asyncio
from types import SimpleNamespace

import pytest

from synthetic_human.native_keyboard import NativeKeyboard


def keyboard_stub():
    events = []
    quartz = SimpleNamespace(
        CGEventSourceCreate=lambda _: object(),
        kCGEventSourceStatePrivate=-1,
        kCGEventFlagMaskCommand=1,
        kCGEventFlagMaskShift=2,
        kCGEventFlagMaskControl=4,
        kCGEventFlagMaskAlternate=8,
        CGEventCreateKeyboardEvent=lambda source, code, down: {"code": code, "down": down},
        CGEventSetFlags=lambda event, flags: event.update(flags=flags),
        CGEventPost=lambda _, event: events.append(event),
        kCGHIDEventTap=0,
    )
    return NativeKeyboard(quartz, {"command": 55, "s": 1}), events


async def test_hotkey_cancellation_releases_every_pressed_modifier():
    keyboard, events = keyboard_stub()
    task = asyncio.create_task(keyboard.hotkey(["command", "s"]))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == [
        {"code": 55, "down": True, "flags": 1},
        {"code": 55, "down": False, "flags": 0},
    ]


async def test_invalid_hotkey_releases_modifier_before_propagating_error():
    keyboard, events = keyboard_stub()
    with pytest.raises(ValueError, match="unsupported native key"):
        await keyboard.hotkey(["command", "unsupported"])
    assert events[-1] == {"code": 55, "down": False, "flags": 0}
