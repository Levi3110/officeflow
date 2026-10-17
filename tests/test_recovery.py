from synthetic_human.fixture import Catalog
from synthetic_human.models import Action
from synthetic_human.workflow import Workflow


async def test_restart_replans_idempotent_open_but_never_replays_unknown_input(rig):
    action = Action(owner="supervisor", epoch=0, kind="open_file", target="example.ods", goal="open")
    rig.store.start_action(action)
    await rig.reconcile()
    assert rig.store.action(action.id)["status"] == "retryable"
    assert rig.backend.inputs == 0


async def test_supervisor_can_resume_office_after_read_only_failure(rig):
    with Catalog() as catalog:
        workflow = Workflow(rig, catalog.url)
        original = rig.backend.effect

        async def opening_failed(action):
            if action.kind == "open_file":
                raise RuntimeError("temporary first-launch dialog")
            await original(action)

        rig.backend.effect = opening_failed
        assert (await workflow.run())["status"] == "failed"
        assert rig.store.get("continuation") == "supervisor_review"
        browser_actions = rig.store.db.execute(
            "SELECT COUNT(*) FROM actions WHERE json_extract(body,'$.owner')='browser'"
        ).fetchone()[0]
        rig.backend.effect = original
        assert (await workflow.run())["status"] == "completed"
        assert rig.store.get("recoveries") == 1
        assert (
            rig.store.db.execute(
                "SELECT COUNT(*) FROM actions WHERE json_extract(body,'$.owner')='browser'"
            ).fetchone()[0]
            == browser_actions
        )
        assert not rig.store.uncertain()


async def test_supervisor_recovery_budget_is_bounded(rig):
    rig.store.put("continuation", "supervisor_review")
    rig.store.put("recoveries", rig.settings.max_recoveries)
    with Catalog() as catalog:
        result = await Workflow(rig, catalog.url).run()
    assert result["status"] == "failed"
    assert "budget" in result["error"]
