import asyncio
import json
from types import SimpleNamespace

import pytest

from synthetic_human.adapters import ApplicationAdapters
from synthetic_human.artifacts import read_sheet, write_odf
from synthetic_human.behaviour import HumanBehaviourEngine
from synthetic_human.models import Action, Persona
from synthetic_human.native_keyboard import NativeKeyboard


async def test_row_edit_lost_ack_reconciles_all_cells_without_retyping(rig):
    path = rig.directory / "row.ods"
    write_odf(path)
    action = Action(
        owner="supervisor",
        epoch=0,
        kind="set_cells",
        target=str(path),
        payload={"cells": {"A2": "Orion", "B2": "120", "C2": "24", "D2": "=B2*1.08"}},
        goal="one verified row checkpoint",
    )
    original = rig.backend.effect

    async def save_then_timeout(action):
        await original(action)
        raise TimeoutError("saved but acknowledgement lost")

    rig.backend.effect = save_then_timeout
    with pytest.raises(TimeoutError):
        await rig.perform(action)
    dispatches = rig.backend.inputs
    result = await rig.perform(action)
    assert result["reconciled"]
    assert rig.backend.inputs == dispatches
    assert read_sheet(path)["C2"]["value"] == "24"


def test_noncontiguous_row_is_rejected_before_input(rig):
    action = Action(
        owner="supervisor",
        epoch=0,
        kind="set_cells",
        target="sheet.ods",
        payload={"cells": {"A1": "a", "A2": "b"}},
        goal="invalid row",
    )
    with pytest.raises(ValueError, match="contiguous"):
        ApplicationAdapters(rig.settings).plan(action)


async def test_persona_restarts_from_same_rng_state():
    persona = Persona(seed=19)
    first = HumanBehaviourEngine(persona, lambda *_: None, realtime=False)

    async def discard(_):
        pass

    await first.type("A paragraph before checkpoint. ", discard, allow_typo=True)
    restored = HumanBehaviourEngine(persona, lambda *_: None, realtime=False)
    restored.restore(json.loads(json.dumps(first.snapshot())))
    left, right = [], []

    async def collect_left(primitive):
        left.append(primitive.model_dump())

    async def collect_right(primitive):
        right.append(primitive.model_dump())

    await first.type("Continue after the handoff.", collect_left, allow_typo=True)
    await restored.type("Continue after the handoff.", collect_right, allow_typo=True)
    assert left == right
    assert all(p["hold_seconds"] > 0 for p in left if p["kind"] == "text")


async def test_protected_urls_and_emails_never_get_typos():
    events = []
    engine = HumanBehaviourEngine(Persona(seed=4, typo_probability=0.1), lambda *_: None, realtime=False)

    async def collect(primitive):
        events.append(primitive)

    text = "https://example.test/abcdefghijklmnopqrstuvwxyz someone@example.test"
    await engine.type(text, collect, allow_typo=True)
    assert all(p.kind != "key" for p in events)
    assert "".join(p.value for p in events) == text


@pytest.mark.parametrize("character", ["a", "A", "á"])
async def test_cancelled_native_key_hold_always_releases_key(character):
    # Native API stub: this test sends no real OS input.
    sent = []
    quartz = SimpleNamespace(
        CGEventSourceCreate=lambda _: "private-source",
        kCGEventSourceStatePrivate=-1,
        kCGEventFlagMaskCommand=1,
        kCGEventFlagMaskShift=2,
        kCGEventFlagMaskControl=4,
        kCGEventFlagMaskAlternate=8,
        CGEventCreateKeyboardEvent=lambda source, code, down: {"code": code, "down": down, "source": source},
        CGEventSetFlags=lambda event, flags: event.update(flags=flags),
        CGEventKeyboardSetUnicodeString=lambda event, length, text: event.update(text=text),
        CGEventPost=lambda _tap, event: sent.append(event),
        kCGHIDEventTap=0,
    )
    keyboard = NativeKeyboard(quartz, {"a": 0, "shift": 56})
    task = asyncio.create_task(keyboard.text(character, 0.5))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    actual_keys = [event for event in sent if event["code"] == 0]
    assert [event["down"] for event in actual_keys] == [True, False]
    assert all(event["text"] == character for event in actual_keys)
    assert all(event["flags"] == (2 if character == "A" else 0) for event in actual_keys)
    assert all(event["source"] == "private-source" for event in sent)
    assert sent[-1]["down"] is False
    if character == "A":
        assert sent[0]["code"] == sent[-1]["code"] == 56
        assert sent[-1]["flags"] == 0


def test_trace_batch_flush_preserves_order_at_action_boundary(rig):
    rig.store.event("input.dispatched", {"kind": "text", "backend": "simulation", "seconds": 0})
    rig.store.event(
        "timing", {"category": "behaviour.typing", "elapsed_seconds": 0, "requested_seconds": 0.1}
    )
    rig.store.event("test.boundary", {"completed": True})
    events = [row[0] for row in rig.store.db.execute("SELECT kind FROM events ORDER BY seq")]
    assert events == ["input.dispatched", "timing", "test.boundary"]
