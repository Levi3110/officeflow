import json

import pytest

from synthetic_human.artifacts import read_sheet
from synthetic_human.fixture import Catalog
from synthetic_human.workers import DocumentWorker, Verifier
from synthetic_human.workflow import Workflow


async def test_end_to_end_including_missing_information_handoff(rig):
    with Catalog() as catalog:
        workflow = Workflow(rig, catalog.url)
        result = await workflow.run()
        assert result["status"] == "completed", result
        transfers = [
            json.loads(row[0])["packet"]
            for row in rig.store.db.execute(
                "SELECT body FROM events WHERE kind='handoff.committed' ORDER BY seq"
            )
        ]
        assert [(p["sender"], p["receiver"]) for p in transfers] == [
            ("supervisor", "browser"),
            ("browser", "office"),
            ("office", "browser"),
            ("browser", "office"),
            ("office", "supervisor"),
        ]
        assert transfers[2]["resume_at"] == "browser_details"
        assert transfers[3]["resume_at"] == "office_create"
        cells = read_sheet(rig.directory / "comparison.ods")
        assert float(cells["D2"]["value"]) == pytest.approx(129.6)
        assert [p.warranty_months for p in workflow.products()] == [24, 12, 36]
        effects = rig.backend.effects
        again = await workflow.run()
        assert again["status"] == "completed"
        assert rig.backend.effects == effects


async def test_verifier_detects_changed_source_evidence(rig):
    with Catalog() as catalog:
        workflow = Workflow(rig, catalog.url)
        assert (await workflow.run())["status"] == "completed"
        product = workflow.products()[0]
        path = rig.directory / "evidence" / f"{product.evidence_id}.txt"
        path.write_text(path.read_text().replace("24 months", "48 months"))
        result = Verifier().check(
            rig.directory, workflow.products(), DocumentWorker().plan(workflow.products())
        )
        assert not result["passed"]
        assert any("digest" in error for error in result["errors"])


async def test_completed_file_drift_is_detected_on_resume(rig):
    with Catalog() as catalog:
        workflow = Workflow(rig, catalog.url)
        assert (await workflow.run())["status"] == "completed"
        (rig.directory / "report.odt").unlink()
        result = await workflow.run()
        assert result["status"] == "failed"


@pytest.mark.parametrize(
    "products",
    [
        [("Vega", 800.10, 0), ("Orion", 12.25, 60), ("Lyra", 99.90, 18)],
        [("Lyra", 70, 36), ("Vega", 68, 12), ("Orion", 68, 24)],
        [("Orion", 0.50, 120), ("Vega", 99999.99, 0), ("Lyra", 12.75, 1)],
    ],
)
async def test_workflow_uses_observed_prices_order_and_warranties(rig, products):
    with Catalog(products=products) as catalog:
        workflow = Workflow(rig, catalog.url)
        result = await workflow.run()
        assert result["status"] == "completed", result
        observed = workflow.products()
        assert [(p.name, p.price, p.warranty_months) for p in observed] == products
        sheet = read_sheet(rig.directory / "comparison.ods")
        for row, (_, price, _) in enumerate(products, 2):
            assert float(sheet[f"D{row}"]["value"]) == pytest.approx(price * 1.08)
