from __future__ import annotations

import hashlib
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .artifacts import write_odf
from .desktop import matches
from .model import ModelGateway
from .models import Action, Handoff, Product
from .workers import DocumentWorker, ParserWorker, SpreadsheetWorker, Verifier


class GraphState(TypedDict, total=False):
    route: str
    status: str
    error: str
    verification: dict


class Workflow:
    """Expertise handoff changes authority; worker calls just return a plan/data."""

    def __init__(self, runtime, base_url):
        self.runtime = runtime
        self.store, self.authority = runtime.store, runtime.authority
        self.directory = runtime.directory
        self.base_url = base_url
        self.parser = ParserWorker()
        self.model = ModelGateway(runtime.settings, self.store)
        graph = StateGraph(GraphState)
        for name in ("dispatch", "supervisor", "browser", "office", "verifier"):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "dispatch")
        for node in ("dispatch", "supervisor", "browser", "office"):
            graph.add_conditional_edges(
                node,
                lambda state: state["route"],
                {
                    "supervisor": "supervisor",
                    "browser": "browser",
                    "office": "office",
                    "verifier": "verifier",
                    "done": END,
                },
            )
        graph.add_edge("verifier", END)
        self.graph = graph.compile()

    def products(self):
        return [Product.model_validate(p) for p in self.store.get("products", [])]

    def save_products(self, products):
        with self.store.transaction():
            self.store.put("products", [p.model_dump() for p in products])
            self.store.put("data_version", self.store.get("data_version", 0) + 1)
            self.store.put("progress", sum(1 + (p.warranty_months is not None) for p in products))

    async def act(self, role, kind, target, payload=None, expected=None, stable=False):
        payload = payload or {}
        identity = hashlib.sha256(json.dumps([kind, target, payload], sort_keys=True).encode()).hexdigest()
        # An already-verified mutation is only skipped after comparing persisted file state again.
        if stable and (old := self.store.action(identity)):
            prior = Action.model_validate_json(old["body"])
            if old["status"] == "done":
                observation = await self.runtime.observe()
                if not matches(prior, observation, self.runtime.backend):
                    raise RuntimeError(
                        "completed artifact changed since checkpoint; supervisor review needed"
                    )
                return json.loads(old["result"])
            raise RuntimeError("unresolved mutation; run restart reconciliation before continuing")
        row = self.authority.current()
        action = Action(
            owner=role,
            epoch=row["epoch"],
            kind=kind,
            target=target,
            payload=payload,
            expected=expected or {},
            goal=f"{role}: {kind}",
            **({"id": identity} if stable else {}),
        )
        return await self.runtime.perform(action)

    async def transfer(self, sender, receiver, reason, next_task, resume_at, completion):
        decision = await self.model.decide(
            sender,
            {
                "reason": reason,
                "data_version": self.store.get("data_version", 0),
                "completion": completion,
                "next_task": next_task,
            },
            [receiver],
            receiver,
        )
        checkpoint = self.store.checkpoint(
            {
                "products": self.store.get("products", []),
                "data_version": self.store.get("data_version", 0),
                "files": self.store.artifacts(),
                "resume_at": resume_at,
            }
        )
        await self.runtime.observe(checkpoint=True)
        packet = Handoff(
            sender=sender,
            receiver=decision.next_role,
            reason=reason,
            next_task=next_task,
            data_version=self.store.get("data_version", 0),
            completion=completion,
            checkpoint_id=checkpoint,
            resume_at=resume_at,
            authority_epoch=self.authority.current()["epoch"],
        )

        async def accept(p):
            products = self.products()
            if p.receiver == "office":
                return len(products) == 3 and (
                    p.resume_at == "office_assess" or all(x.warranty_months is not None for x in products)
                )
            if p.receiver == "browser":
                return p.resume_at == "browser_collect" or bool(products)
            return True

        # Sender captured a checkpoint screenshot; receiver still re-observes AX/focus after commit.
        await self.authority.handoff(packet, accept, self.runtime.observe)

    async def dispatch(self, _):
        if self.store.get("completed", False):
            return {"route": "verifier"}
        return {"route": self.authority.current()["owner"]}

    async def supervisor(self, _):
        if self.store.get("continuation") == "supervisor_verify":
            return {"route": "verifier"}
        if self.store.get("continuation") == "supervisor_review":
            recoveries = self.store.get("recoveries", 0)
            if recoveries >= self.runtime.settings.max_recoveries:
                raise RuntimeError("supervisor recovery budget exhausted")
            allowed = {
                "browser_collect": "browser",
                "browser_details": "browser",
                "office_assess": "office",
                "office_create": "office",
            }
            continuation = None
            for row in self.store.db.execute(
                "SELECT body FROM handoffs WHERE status='committed' ORDER BY updated DESC"
            ):
                packet = Handoff.model_validate_json(row[0])
                if packet.resume_at in allowed and packet.receiver == allowed[packet.resume_at]:
                    continuation = packet.resume_at
                    break
            if not continuation:
                raise RuntimeError("no safe specialist checkpoint exists for supervisor recovery")
            receiver = allowed[continuation]
            self.store.put("recoveries", recoveries + 1)
            await self.transfer(
                "supervisor",
                receiver,
                "reconciled checkpoint; bounded specialist recovery",
                "continue from verified checkpoint without repeating uncertain mutations",
                continuation,
                ["prior mutations reconciled", "complete remaining mission"],
            )
            return {"route": receiver}
        self.store.put(
            "mission",
            {
                "goal": "Compare three demo products and create a spreadsheet and report",
                "criteria": [
                    "three sourced products",
                    "warranty complete",
                    "8% tax formulas",
                    "consistent saved report",
                ],
                "scope": "local fixture + LibreOffice via GUI",
            },
        )
        await self.transfer(
            "supervisor",
            "browser",
            "web research requires browser expertise",
            "collect three product summaries",
            "browser_collect",
            ["three sourced product prices"],
        )
        return {"route": "browser"}

    async def browser(self, _):
        if self.store.get("continuation") == "browser_details":
            products = self.products()
            for index, product in enumerate(products):
                if product.warranty_months is not None:
                    continue
                await self.act(
                    "browser", "navigate", self.base_url, expected={"contains": "Demo Product Catalog"}
                )
                result = await self.act(
                    "browser",
                    "follow_link",
                    f"{self.base_url}/{product.name.lower()}",
                    {"link_text": f"Details {product.name}"},
                    {"contains": f"Product details: {product.name}"},
                )
                await self.act("browser", "scroll", "page", {"amount": -5})
                result = await self.act(
                    "browser",
                    "read_page",
                    product.source_url,
                    expected={"contains": f"Product details: {product.name}"},
                )
                products[index] = self.parser.details(result["text"], product, result["evidence_id"])
                self.save_products(products)
            await self.transfer(
                "browser",
                "office",
                "requested warranty evidence is complete",
                "resume spreadsheet and report creation",
                "office_create",
                ["all warranty values sourced", "return to office_create"],
            )
        else:
            result = await self.act(
                "browser", "navigate", self.base_url, expected={"contains": "Demo Product Catalog"}
            )
            await self.act("browser", "scroll", "page", {"amount": -4})
            result = await self.act(
                "browser", "read_page", self.base_url, expected={"contains": "Demo Product Catalog"}
            )
            self.save_products(self.parser.catalog(result["text"], self.base_url, result["evidence_id"]))
            await self.transfer(
                "browser",
                "office",
                "summaries ready for comparison",
                "assess completeness and prepare artifacts",
                "office_assess",
                ["three products with price and source"],
            )
        return {"route": "office"}

    async def office(self, _):
        products = self.products()
        missing = [p.name for p in products if p.warranty_months is None]
        if missing:
            await self.transfer(
                "office",
                "browser",
                "warranty is absent from catalog summaries",
                f"retrieve warranty months for {', '.join(missing)} from their detail links",
                "browser_details",
                ["warranty for each missing product", "resume office_create"],
            )
            return {"route": "browser"}
        sheet, document = self.directory / "comparison.ods", self.directory / "report.odt"
        files = {"spreadsheet": str(sheet), "document": str(document)}
        self.store.put("files", files)
        for path in (sheet, document):
            if not path.exists():
                write_odf(path)  # Empty only: no product data is written outside GUI in live mode.
        await self.act("office", "open_file", str(sheet))
        rows = {}
        for cell, value in SpreadsheetWorker().plan(products):
            rows.setdefault(int(cell[1:]), {})[cell] = value
        for cells in rows.values():
            await self.act("office", "set_cells", str(sheet), {"cells": cells}, stable=True)
        await self.runtime.observe(checkpoint=True)
        await self.act("office", "open_file", str(document))
        report = DocumentWorker().plan(products)
        await self.act("office", "write_document", str(document), {"text": report}, stable=True)
        self.store.put("progress", 8)
        await self.transfer(
            "office",
            "supervisor",
            "office artifacts saved; final independent verification required",
            "verify artifacts against observed sources",
            "supervisor_verify",
            ["spreadsheet and report saved", "all values consistent"],
        )
        return {"route": "verifier"}

    async def verifier(self, _):
        result = Verifier().check(self.directory, self.products(), DocumentWorker().plan(self.products()))
        self.store.event("verification.final", result)
        self.store.put("verification", result)
        self.store.put("completed", result["passed"])
        if not result["passed"]:
            raise RuntimeError(f"final verification failed: {result['errors']}")
        return {"route": "done", "status": "completed", "verification": result}

    async def run(self):
        try:
            await self.runtime.reconcile()
            return await self.graph.ainvoke({}, {"recursion_limit": 32})
        except Exception as exc:
            self.store.event("workflow.failed", {"error": str(exc)})
            await self.authority.escalate(str(exc), lambda: self.runtime.observe(checkpoint=True))
            return {"status": "failed", "error": str(exc)}
