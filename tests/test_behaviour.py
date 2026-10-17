from synthetic_human.behaviour import HumanBehaviourEngine
from synthetic_human.models import Persona


async def test_typos_are_corrected_and_commands_are_not_perturbed():
    events, output = [], []
    engine = HumanBehaviourEngine(
        Persona(seed=7, typo_probability=0.1), lambda kind, body: events.append((kind, body)), realtime=False
    )

    async def emit(p):
        if p.kind == "text":
            output.extend(p.value)
        elif p.kind == "key":
            assert p.value == "backspace"
            output.pop()

    text = "This is a sufficiently long paragraph to exercise natural typing corrections. " * 4
    await engine.type(text, emit, allow_typo=True)
    assert "".join(output) == text
    assert any(e[1]["category"] == "behaviour.typo_notice" for e in events)
    intervals = [e[1]["requested_seconds"] for e in events if e[1]["category"] == "behaviour.typing"]
    assert max(intervals) > min(intervals) * 2
    events.clear()
    await engine.type("=B2*1.08", emit, allow_typo=False)
    assert not any(e[1]["category"] == "behaviour.typo_notice" for e in events)


async def test_realtime_engine_actually_waits_for_context_pauses():
    # Engine-only test with actual clock waits; this is not a desktop or human telemetry recording.
    events = []
    engine = HumanBehaviourEngine(
        Persona(seed=17, pause_scale=0.05), lambda kind, body: events.append(body), realtime=True
    )
    for context in ("read", "switch", "plan"):
        await engine.context_pause(context, characters=100)
    assert all(not event["simulated_timing"] for event in events)
    assert all(event["elapsed_seconds"] >= event["requested_seconds"] * 0.9 for event in events)
    assert len({round(event["requested_seconds"], 3) for event in events}) == 3
    assert engine.elapsed > 0.05
