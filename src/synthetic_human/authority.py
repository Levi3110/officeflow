from __future__ import annotations

import asyncio
import json
import time
from uuid import uuid4

from .models import Handoff


class AuthorityError(RuntimeError):
    pass


class AuthorityManager:
    """SQLite transactions fence all processes; asyncio lock drains local input before handoff."""

    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.gate = asyncio.Lock()

    def current(self):
        return dict(self.store.db.execute("SELECT * FROM authority WHERE singleton=1").fetchone())

    def _check(self, row, owner, epoch):
        if row["owner"] != owner or row["epoch"] != epoch:
            raise AuthorityError("stale authority: owner or epoch does not match")

    def acquire(self, owner, epoch, action=None):
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM authority WHERE singleton=1").fetchone()
            self._check(row, owner, epoch)
            # Expired leases remain quarantined: a hung executor might still hold an input event.
            if row["lease"]:
                raise AuthorityError("desktop lease busy; reconcile/restart the previous executor first")
            token = str(uuid4())
            db.execute(
                "UPDATE authority SET lease=?,lease_until=? WHERE singleton=1",
                (token, time.time() + self.settings.lease_seconds),
            )
            if action is not None:
                # The write-ahead intent and lease become durable together, before the first input.
                self.store.start_action(action)
        return token

    def validate(self, owner, epoch, token):
        row = self.store.db.execute(
            "SELECT owner,epoch,lease,lease_until FROM authority WHERE singleton=1"
        ).fetchone()
        self._check(row, owner, epoch)
        if row["lease"] != token or row["lease_until"] < time.time():
            raise AuthorityError("desktop lease missing or expired")

    def release(self, token):
        self.store.db.execute("UPDATE authority SET lease=NULL,lease_until=0 WHERE lease=?", (token,))

    async def handoff(self, packet: Handoff, accept, observe):
        checkpoint = self.store.db.execute(
            "SELECT state FROM checkpoints WHERE id=?", (packet.checkpoint_id,)
        ).fetchone()
        if not checkpoint:
            raise AuthorityError("checkpoint missing")
        if packet.data_version != self.store.get("data_version", 0):
            raise AuthorityError("handoff data version is stale")
        if packet.data_version != json.loads(checkpoint[0]).get("data_version", 0):
            raise AuthorityError("checkpoint does not match the handoff version")
        if not await accept(packet):
            raise AuthorityError("receiver rejected handoff inputs")
        self.store.db.execute(
            "INSERT INTO handoffs VALUES(?,?,'accepted',?)",
            (packet.id, packet.model_dump_json(), time.time()),
        )
        # Drain old input. Acceptance does not grant access to the desktop.
        async with self.gate:
            with self.store.transaction() as db:
                row = db.execute("SELECT * FROM authority WHERE singleton=1").fetchone()
                self._check(row, packet.sender, packet.authority_epoch)
                if packet.data_version != self.store.get("data_version", 0):
                    raise AuthorityError("data changed while receiver was accepting handoff")
                snapshot = json.loads(checkpoint[0])
                if "files" in snapshot and snapshot["files"] != self.store.artifacts():
                    raise AuthorityError("artifact versions changed while handoff was being prepared")
                if row["lease"]:
                    raise AuthorityError("cannot transfer while a desktop lease is outstanding")
                progress = self.store.get("progress", 0)
                stagnant = row["no_progress"] + 1 if progress <= row["progress"] else 0
                if packet.receiver != "supervisor" and (
                    row["handoffs"] >= self.settings.max_handoffs or stagnant >= self.settings.max_no_progress
                ):
                    raise AuthorityError("handoff budget exhausted; escalate to supervisor")
                db.execute(
                    """UPDATE authority SET owner=?,epoch=epoch+1,handoffs=handoffs+1,
                    no_progress=?,progress=? WHERE singleton=1""",
                    (packet.receiver, stagnant, progress),
                )
                db.execute(
                    "UPDATE handoffs SET status='committed',updated=? WHERE id=?", (time.time(), packet.id)
                )
                self.store.put("continuation", packet.resume_at)
            # Receiver must re-observe before any next plan/action; gate stays held.
            observation = await observe()
            self.store.event(
                "handoff.committed", {"packet": packet.model_dump(), "observation": observation.model_dump()}
            )
        return self.current()["epoch"]

    async def escalate(self, reason, observe):
        row = self.current()
        self.store.event("supervisor.escalation", {"reason": reason, "from": row["owner"]})
        if row["owner"] == "supervisor":
            return
        packet = Handoff(
            sender=row["owner"],
            receiver="supervisor",
            reason=reason,
            next_task="review failure and stop or replan",
            data_version=self.store.get("data_version", 0),
            completion=["failure reviewed"],
            checkpoint_id=self.store.checkpoint(
                {"data_version": self.store.get("data_version", 0), "reason": reason}
            ),
            resume_at="supervisor_review",
            authority_epoch=row["epoch"],
        )

        async def accept(_):
            return True

        await self.handoff(packet, accept, observe)
