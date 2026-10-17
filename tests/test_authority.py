import asyncio

import pytest

from synthetic_human.artifacts import write_odf
from synthetic_human.authority import AuthorityError
from synthetic_human.models import Action, Handoff


def packet(rig, receiver="browser"):
    return Handoff(
        sender=rig.authority.current()["owner"],
        receiver=receiver,
        reason="expertise",
        next_task="research",
        data_version=0,
        completion=["sources found"],
        resume_at="browser_collect",
        checkpoint_id=rig.store.checkpoint({"data_version": 0}),
        authority_epoch=rig.authority.current()["epoch"],
    )


async def accepted(_):
    return True


async def test_handoff_changes_owner_and_reobserves(rig):
    seen = []

    async def observe():
        seen.append(rig.authority.current()["owner"])
        return await rig.observe()

    await rig.authority.handoff(packet(rig), accepted, observe)
    assert rig.authority.current()["owner"] == "browser"
    assert rig.authority.current()["epoch"] == 1
    assert seen == ["browser"]
    assert rig.store.get("continuation") == "browser_collect"


async def test_stale_command_never_emits_input(rig):
    await rig.authority.handoff(packet(rig), accepted, rig.observe)
    old = Action(owner="supervisor", epoch=0, kind="scroll", target="page", goal="old queued command")
    with pytest.raises(AuthorityError, match="stale"):
        await rig.perform(old)
    assert rig.backend.inputs == 0


async def test_receiver_rejection_preserves_owner(rig):
    async def reject(_):
        return False

    with pytest.raises(AuthorityError, match="rejected"):
        await rig.authority.handoff(packet(rig), reject, rig.observe)
    assert rig.authority.current()["epoch"] == 0


async def test_handoff_drains_existing_executor(rig):
    acceptance = asyncio.Event()

    async def accept(_):
        acceptance.set()
        return True

    async with rig.authority.gate:
        transfer = asyncio.create_task(rig.authority.handoff(packet(rig), accept, rig.observe))
        await acceptance.wait()
        assert rig.authority.current()["owner"] == "supervisor"
        assert not transfer.done()
    await transfer
    assert rig.authority.current()["owner"] == "browser"


def test_exclusive_lease_and_fenced_primitives(rig):
    token = rig.authority.acquire("supervisor", 0)
    with pytest.raises(AuthorityError, match="busy"):
        rig.authority.acquire("supervisor", 0)
    with pytest.raises(AuthorityError, match="missing"):
        rig.authority.validate("supervisor", 0, "wrong-token")
    rig.authority.release(token)
    with pytest.raises(AuthorityError):
        rig.authority.validate("supervisor", 0, token)


async def test_expired_lease_is_quarantined(rig):
    rig.authority.acquire("supervisor", 0)
    rig.store.db.execute("UPDATE authority SET lease_until=0")
    with pytest.raises(AuthorityError, match="busy"):
        rig.authority.acquire("supervisor", 0)
    with pytest.raises(AuthorityError, match="outstanding"):
        await rig.authority.handoff(packet(rig), accepted, rig.observe)


async def test_handoff_rechecks_version_after_acceptance(rig):
    async def mutate(_):
        rig.store.put("data_version", 1)
        return True

    with pytest.raises(AuthorityError, match="changed"):
        await rig.authority.handoff(packet(rig), mutate, rig.observe)
    assert rig.authority.current()["owner"] == "supervisor"


async def test_no_progress_handoffs_are_bounded_and_escalate(rig):
    rig.authority.settings.max_no_progress = 2
    await rig.authority.handoff(packet(rig), accepted, rig.observe)
    with pytest.raises(AuthorityError, match="budget"):
        await rig.authority.handoff(packet(rig, "office"), accepted, rig.observe)
    await rig.authority.escalate("no progress", rig.observe)
    assert rig.authority.current()["owner"] == "supervisor"


async def test_handoff_rejects_artifacts_changed_during_acceptance(rig):
    path = rig.directory / "checkpoint.odt"
    write_odf(path, text="first")
    rig.store.record_artifact(str(path))
    transfer = packet(rig)
    transfer.checkpoint_id = rig.store.checkpoint({"data_version": 0, "files": rig.store.artifacts()})

    async def accept_with_concurrent_save(_):
        write_odf(path, text="second")
        rig.store.record_artifact(str(path))
        return True

    with pytest.raises(AuthorityError, match="artifact versions changed"):
        await rig.authority.handoff(transfer, accept_with_concurrent_save, rig.observe)
    assert rig.authority.current()["owner"] == "supervisor"
