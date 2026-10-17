from synthetic_human.assessment import assess
from synthetic_human.fixture import Catalog
from synthetic_human.workflow import Workflow


async def test_activity_checklist_does_not_promote_simulation_to_gui(rig):
    rig.store.put("settings", rig.settings.model_dump())
    with Catalog() as catalog:
        assert (await Workflow(rig, catalog.url).run())["status"] == "completed"
    result = assess(rig.directory)
    assert result["policy_checks_passed"] == 7
    assert result["desktop_checks_passed"] == 0
    assert result["authenticity_score"] is None
    click = next(row for row in result["criteria"] if row["criterion"] == "clicking_links")
    assert click["evidence"]["mouse_link_activations"] == 3


async def test_checklist_rechecks_artifacts_and_accepts_no_placeholder_pause_evidence(rig):
    rig.store.put("settings", rig.settings.model_dump())
    with Catalog() as catalog:
        assert (await Workflow(rig, catalog.url).run())["status"] == "completed"
    (rig.directory / "report.odt").unlink()
    rig.store.db.execute("DELETE FROM events WHERE kind='timing'")
    result = assess(rig.directory)
    rows = {row["criterion"]: row for row in result["criteria"]}
    assert rows["interacting_with_applications"]["policy_check"] == "not_demonstrated"
    assert rows["contextual_pauses"]["policy_check"] == "not_demonstrated"
    assert rows["occasional_corrected_typos"]["policy_check"] == "not_demonstrated"
