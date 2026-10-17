import pytest

from synthetic_human.artifacts import read_document, write_odf
from synthetic_human.authority import AuthorityError
from synthetic_human.models import Action
from synthetic_human.runtime import UncertainAction


def document_action(rig):
    path = rig.directory / "test.odt"
    write_odf(path)
    return Action(
        owner="supervisor",
        epoch=0,
        kind="write_document",
        target=str(path),
        payload={"text": "Correct final content."},
        goal="write a report",
    )


async def test_duplicate_id_does_not_duplicate_edit(rig):
    action = document_action(rig)
    await rig.perform(action)
    first_effects = rig.backend.effects
    await rig.perform(action)
    assert rig.backend.effects == first_effects
    assert read_document(action.target) == action.payload["text"]


async def test_ambiguous_success_is_observed_before_retry(rig):
    action = document_action(rig)
    original = rig.backend.effect

    async def saved_then_lost_ack(action):
        await original(action)
        raise TimeoutError("lost acknowledgment after successful save")

    rig.backend.effect = saved_then_lost_ack
    with pytest.raises(TimeoutError):
        await rig.perform(action)
    assert rig.store.action(action.id)["status"] == "uncertain"
    effects = rig.backend.effects
    result = await rig.perform(action)
    assert result["reconciled"]
    assert rig.backend.effects == effects


async def test_restart_reconciles_saved_file_without_retyping(rig):
    action = document_action(rig)
    rig.store.start_action(action)
    write_odf(rig.directory / "test.odt", text=action.payload["text"])
    await rig.reconcile()
    assert rig.store.action(action.id)["status"] == "done"
    assert rig.backend.inputs == 0


async def test_restart_blocks_unresolved_mutation(rig):
    action = document_action(rig)
    rig.store.start_action(action)
    with pytest.raises(UncertainAction, match="unresolved"):
        await rig.reconcile()
    assert rig.backend.inputs == 0
    with pytest.raises(UncertainAction, match="ambiguous"):
        await rig.perform(action)
    assert rig.backend.inputs == 0


async def test_stop_file_prevents_inputs(rig):
    action = document_action(rig)
    (rig.directory / "STOP").touch()
    with pytest.raises(RuntimeError, match="emergency"):
        await rig.perform(action)
    assert rig.backend.inputs == 0
    assert rig.authority.current()["lease"] is None


async def test_reusing_id_with_different_payload_is_rejected(rig):
    action = document_action(rig)
    await rig.perform(action)
    changed = action.model_copy(update={"payload": {"text": "other"}})
    with pytest.raises(ValueError, match="different content"):
        await rig.perform(changed)


async def test_epoch_is_checked_between_individual_input_events(rig):
    action = document_action(rig)
    original = rig.backend.emit

    async def revoke_after_first_input(primitive):
        await original(primitive)
        rig.store.db.execute("UPDATE authority SET epoch=epoch+1")

    rig.backend.emit = revoke_after_first_input
    with pytest.raises(AuthorityError, match="stale"):
        await rig.perform(action)
    assert rig.backend.inputs == 1
    assert rig.backend.effects == 0


async def test_wrong_focused_document_blocks_mutation(rig):
    action = document_action(rig)
    rig.backend.mode = "macos"
    rig.backend.application = "LibreOffice"
    rig.backend.url = "Some other document.odt"
    with pytest.raises(RuntimeError, match="wrong document"):
        await rig.perform(action)
    assert rig.backend.inputs == 0
