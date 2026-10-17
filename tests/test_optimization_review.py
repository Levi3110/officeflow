"""Target real regressions: stale focus, duplicate clipboard reads, and hold clipping."""

import asyncio
import json
import sys
import time
from types import SimpleNamespace

import pytest

from synthetic_human.behaviour import HumanBehaviourEngine
from synthetic_human.desktop import MacDesktop
from synthetic_human.models import Action, Observation, Persona
from synthetic_human.telemetry import TelemetryCollector


async def test_independent_holds_are_not_clipped_by_short_onsets_and_prose_stays_correct():
    persona = Persona(
        seed=9,
        characters_per_second=20,
        independent_key_hold=True,
        key_hold_median_seconds=0.09,
        key_hold_log_sigma=0.35,
    )
    engine = HumanBehaviourEngine(persona, lambda *_: None, realtime=False)
    output = []

    async def emit(primitive):
        output.append(primitive)

    await engine.type("Typing with independent holds. " * 20, emit)
    holds = [p.hold_seconds for p in output]
    assert "".join(p.value for p in output) == "Typing with independent holds. " * 20
    assert sum(value > 0.07 for value in holds) > len(holds) / 2
    assert all(p.onset_interval_seconds >= p.hold_seconds + 0.0119 for p in output)
    assert all(0 < value <= 0.45 for value in holds)


async def test_legacy_persona_checkpoint_restores_with_default_new_fields():
    engine = HumanBehaviourEngine(Persona(seed=19), lambda *_: None, realtime=False)
    state = json.loads(json.dumps(engine.snapshot()))
    for key in ("typing_log_sigma", "key_hold_median_seconds", "key_hold_log_sigma", "independent_key_hold"):
        state["persona"].pop(key)
    restored = HumanBehaviourEngine(Persona(seed=19), lambda *_: None, realtime=False)
    restored.restore(state)
    assert restored.snapshot() == engine.snapshot()
    with pytest.raises(ValueError, match="persona differs"):
        HumanBehaviourEngine(Persona(seed=19, independent_key_hold=True), lambda *_: None).restore(state)


async def test_brief_focus_reads_document_identity_without_editor_contents():
    backend = object.__new__(MacDesktop)
    backend._front_application = lambda: SimpleNamespace(
        processIdentifier=lambda: 12, localizedName=lambda: "LibreOffice"
    )
    backend.AX = SimpleNamespace(AXUIElementCreateApplication=lambda _: "app")
    looked_up = []

    def attribute(element, name):
        looked_up.append(name)
        return {
            "AXFocusedWindow": "window",
            "AXTitle": "comparison.ods",
            "AXDocument": "file:///test/comparison.ods",
        }.get(name)

    backend._attribute = attribute
    observation = await backend.observe_focus()
    assert observation.document_uri == "file:///test/comparison.ods"
    assert observation.application == "LibreOffice"
    assert "AXFocusedUIElement" not in looked_up
    assert "AXValue" not in looked_up


async def test_frequent_focus_fence_still_rejects_wrong_document(rig):
    rig.backend.mode = "macos"

    async def focused():
        return Observation(
            timestamp=time.time(),
            application=rig.settings.office_app,
            document_uri="file:///wrong/comparison.ods",
        )

    rig.backend.observe_focus = focused
    action = Action(
        owner="supervisor",
        epoch=0,
        kind="set_cells",
        target=str(rig.directory / "comparison.ods"),
        payload={"cells": {"A1": "safe"}},
        goal="verify identity before typing",
    )
    with pytest.raises(RuntimeError, match="wrong document"):
        await rig._focus(action)
    assert rig.backend.inputs == 0


async def test_verifier_uses_one_clipboard_snapshot_for_match_and_saved_evidence(rig):
    reads = []

    def clipboard():
        reads.append(1)
        return "Expected page" if len(reads) == 1 else "Unrelated later clipboard"

    rig.backend.read_clipboard = clipboard
    action = Action(
        owner="supervisor",
        epoch=0,
        kind="read_page",
        target="http://fixture.test",
        expected={"contains": "Expected"},
        goal="capture the same observed page",
    )
    result = await rig._verify(action, "test-token")
    assert len(reads) == 1
    assert result["text"] == "Expected page"
    assert (rig.directory / "evidence" / f"{action.id}.txt").read_text() == result["text"]


def fake_quartz(monkeypatch):
    quartz = SimpleNamespace(
        CGEventSourceCounterForEventType=lambda *_: 0,
        kCGEventSourceStateCombinedSessionState=0,
        kCGEventKeyDown=1,
        kCGEventLeftMouseDown=2,
        kCGEventScrollWheel=3,
    )
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    monkeypatch.setattr("synthetic_human.telemetry.platform.system", lambda: "Darwin")
    monkeypatch.setattr("synthetic_human.telemetry.psutil.pids", lambda: [])


async def test_passive_focus_monitor_refreshes_on_main_loop_without_any_input(tmp_path, monkeypatch):
    fake_quartz(monkeypatch)
    names = iter(("Chrome", "LibreOffice", "LibreOffice", "LibreOffice"))
    monkeypatch.setattr(
        "synthetic_human.telemetry.read_macos_foreground",
        lambda: {"pid": 1, "name": next(names, "LibreOffice")},
    )
    collector = TelemetryCollector(tmp_path / "sample.jsonl", "macos", interval=0.01)
    collector._refresh_foreground()
    assert collector._sample()["foreground"]["name"] == "Chrome"
    task = asyncio.create_task(collector._monitor_foreground())
    try:
        await asyncio.sleep(0.035)
        sample = collector._sample()
        assert sample["foreground"]["name"] == "LibreOffice"
        assert sample["foreground_status"] == "observed"
        assert sample["foreground_source"] == "NSWorkspace.main_run_loop"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_stale_focus_is_not_reported_as_a_fresh_observation(tmp_path, monkeypatch):
    fake_quartz(monkeypatch)
    collector = TelemetryCollector(tmp_path / "sample.jsonl", "macos")
    collector.foreground_snapshot = (time.monotonic() - 10, {"pid": 1, "name": "Code"}, None)
    sample = collector._sample()
    assert sample["foreground_status"] == "stale"
    assert "foreground" not in sample
    assert sample["input_counters"]["key_down"] == 0


def test_sampler_discovers_new_pids_and_fences_reuse_without_repeated_name_queries(tmp_path, monkeypatch):
    from contextlib import nullcontext

    clock, pids = [1.0], [9001]
    names = {9001: "Other app", 9002: "Google Chrome"}
    created = {9001: 10, 9002: 20}
    lookups = []

    class Process:
        def __init__(self, pid):
            self.pid = pid
            self.created = created[pid]

        def oneshot(self):
            return nullcontext()

        def name(self):
            lookups.append(self.pid)
            return names[self.pid]

        def create_time(self):
            return self.created

        def is_running(self):
            return self.created == created[self.pid]

        def cpu_percent(self):
            return 1

        def memory_info(self):
            return SimpleNamespace(rss=1024)

        def num_threads(self):
            return 2

    monkeypatch.setattr(
        "synthetic_human.telemetry.time", SimpleNamespace(monotonic=lambda: clock[0], time=lambda: clock[0])
    )
    monkeypatch.setattr("synthetic_human.telemetry.psutil.pids", lambda: pids)
    monkeypatch.setattr("synthetic_human.telemetry.psutil.Process", Process)
    collector = TelemetryCollector(tmp_path / "sampler.jsonl", "simulation")
    assert not collector._sample()["processes"]
    clock[0] += 0.5
    pids.append(9002)
    first = collector._sample()["processes"][0]
    assert first["cpu_first_sample"]
    assert lookups == [9001, 9002]
    clock[0] += 0.5
    following = collector._sample()["processes"][0]
    assert not following["cpu_first_sample"]
    assert following["metadata_age_seconds"] == 0.5
    assert lookups == [9001, 9002]
    created[9002] = 30  # Same PID now identifies a different process before the metadata TTL.
    assert collector._sample()["processes"][0]["cpu_first_sample"]
    assert lookups == [9001, 9002, 9002]
    clock[0] += 6
    collector._sample()
    assert lookups.count(9001) == 2
