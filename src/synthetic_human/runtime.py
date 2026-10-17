from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path

from .adapters import ApplicationAdapters
from .behaviour import HumanBehaviourEngine
from .desktop import document_matches, matches
from .models import Action, Primitive


class UncertainAction(RuntimeError):
    pass


class DesktopExecutor:
    """Only this component invokes backend.emit; validates fencing before every primitive/character."""

    def __init__(self, backend, authority, behaviour, store, stop_file):
        self.backend, self.authority, self.behaviour = backend, authority, behaviour
        self.store, self.stop_file = store, stop_file

    async def emit(self, primitive, action, token):
        if self.stop_file.exists():
            raise RuntimeError("STOP file present; emergency stop")
        self.authority.validate(action.owner, action.epoch, token)
        started = time.monotonic()
        delivery = await self.backend.emit(primitive)
        driver_seconds = time.monotonic() - started
        held = (delivery or {}).get("hold_elapsed_seconds", 0)
        if primitive.hold_seconds:
            self.behaviour.elapsed += held
        self.store.event(
            "input.dispatched",
            {
                "action_id": action.id,
                "kind": primitive.kind,
                "backend": self.backend.mode,
                "seconds": driver_seconds,
                **(
                    {
                        "requested_hold_seconds": primitive.hold_seconds,
                        "hold_elapsed_seconds": held,
                        "requested_onset_interval_seconds": primitive.onset_interval_seconds,
                    }
                    if primitive.hold_seconds or primitive.onset_interval_seconds is not None
                    else {}
                ),
            },
        )
        # No text or passwords are copied into per-keystroke logs.
        await asyncio.sleep(0)

    async def run(self, primitives, action, token, focus_check):
        async def emit(p):
            await focus_check()
            await self.emit(p, action, token)

        for primitive in primitives:
            if primitive.kind == "text":
                await self.behaviour.type(str(primitive.value), emit, primitive.allow_typo)
            elif primitive.kind == "click":
                await self.behaviour.move_to(self.backend.cursor(), primitive.value, emit)
                await emit(primitive)
            elif primitive.kind == "move":
                await self.behaviour.move_to(self.backend.cursor(), primitive.value, emit)
            elif primitive.kind == "scroll":
                await self.behaviour.scroll(primitive.value, emit)
            elif primitive.kind == "pause":
                await self.behaviour.context_pause(primitive.value)
            else:
                # Launch is the only primitive allowed while another application has focus.
                if primitive.kind == "launch":
                    await self.emit(primitive, action, token)
                    await focus_check(wait=True)
                else:
                    await emit(primitive)


class Runtime:
    def __init__(self, store, authority, backend, settings, directory):
        self.store, self.authority, self.backend, self.settings = store, authority, backend, settings
        self.directory = Path(directory)
        self.adapters = ApplicationAdapters(settings)
        self.behaviour = HumanBehaviourEngine(
            settings.persona, store.event, realtime=backend.mode != "simulation"
        )
        self.executor = DesktopExecutor(backend, authority, self.behaviour, store, self.directory / "STOP")
        self.last_focus_check = 0
        if saved := store.get("persona_state"):
            self.behaviour.restore(saved)

    async def observe(self, checkpoint=False):
        path = None
        if checkpoint and self.settings.screenshot_on_checkpoint:
            path = self.directory / "evidence" / f"{time.time_ns()}.png"
            path.parent.mkdir(exist_ok=True)
        observation = await self.backend.observe(path)
        self.store.event("observation", observation.model_dump())
        return observation

    async def _focus(self, action, wait=False):
        if self.backend.mode == "simulation":
            return
        now = time.monotonic()
        if not wait and now - self.last_focus_check < 0.2:
            return
        deadline = now + (12 if wait else 0)
        while True:
            observe_focus = getattr(self.backend, "observe_focus", self.backend.observe)
            observation = await observe_focus()
            if observation.application == self.adapters.expected_app(action):
                if action.kind in ("set_cell", "set_cells", "write_document") and not document_matches(
                    action.target, observation
                ):
                    raise RuntimeError("wrong document is focused; no input sent")
                self.last_focus_check = time.monotonic()
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(f"focus mismatch: {observation.application}")
            await asyncio.sleep(0.2)

    async def perform(self, action: Action):
        async with self.authority.gate:
            # Even a cached result must not let a former authority issue a new operation.
            old = self.store.action(action.id)
            token = self.authority.acquire(action.owner, action.epoch, action=None if old else action)
            try:
                if old:
                    if Action.model_validate_json(old["body"]) != action:
                        raise ValueError("action ID reused with different content")
                    if old["status"] == "done":
                        return json.loads(old["result"])
                    observation = await self.observe(checkpoint=True)
                    if action.kind in ("set_cell", "set_cells", "write_document") and matches(
                        action, observation, self.backend
                    ):
                        result = {
                            "reconciled": True,
                            "action_id": action.id,
                            "artifact": self.store.record_artifact(action.target),
                        }
                        self.store.finish_action(action.id, "done", result)
                        return result
                    raise UncertainAction("previous attempt ambiguous; inspect checkpoint before retrying")
                started = time.monotonic()
                behaviour_started = self.behaviour.elapsed
                self.last_focus_check = 0
                try:
                    async with asyncio.timeout(self.settings.action_timeout):
                        retryable = action.kind in ("navigate", "read_page", "open_file")
                        attempts = 1 + (self.settings.max_retries if retryable else 0)
                        for attempt in range(attempts):
                            before = await self.observe()
                            try:
                                await self.behaviour.context_pause("plan")
                                primitives = self.adapters.plan(action, before.application)
                                viewport = None
                                if action.kind == "scroll" and self.backend.mode == "macos":
                                    viewport = self.backend.browser_viewport()
                                    if not viewport:
                                        raise RuntimeError("cannot locate browser viewport for scrolling")
                                    x, y, width, height = viewport["bounds"]
                                    primitives.insert(
                                        0, Primitive(kind="move", value=(x + width * 0.65, y + height * 0.55))
                                    )
                                await self.executor.run(
                                    primitives, action, token, lambda wait=False: self._focus(action, wait)
                                )
                                if action.kind == "follow_link":
                                    point = self.backend.locate_link(action.payload["link_text"])
                                    activation = (
                                        Primitive(kind="click", value=point)
                                        if point
                                        else Primitive(kind="key", value="enter")
                                    )
                                    self.store.event(
                                        "browser.link_activation",
                                        {"method": "mouse" if point else "keyboard", "action_id": action.id},
                                    )
                                    await self.executor.run(
                                        [activation],
                                        action,
                                        token,
                                        lambda wait=False: self._focus(action, wait),
                                    )
                                await self.backend.effect(action)
                                result = await self._verify(action, token, viewport)
                                break
                            except (UncertainAction, OSError) as exc:
                                if attempt + 1 == attempts:
                                    raise
                                await self.observe(checkpoint=True)
                                self.store.event(
                                    "action.retry",
                                    {"action_id": action.id, "attempt": attempt + 1, "reason": str(exc)},
                                )
                        result["before"] = before.model_dump()
                        result["action_id"] = action.id
                        if action.kind in ("set_cell", "set_cells", "write_document"):
                            result["artifact"] = self.store.record_artifact(action.target)
                        self.store.finish_action(action.id, "done", result)
                        elapsed = time.monotonic() - started
                        behaviour_elapsed = self.behaviour.elapsed - behaviour_started
                        wait = result.get("application_wait_seconds", 0)
                        self.store.event(
                            "timing",
                            {
                                "category": "runtime_overhead",
                                "elapsed_seconds": max(0, elapsed - behaviour_elapsed - wait),
                            },
                        )
                        self.store.event(
                            "action.verified",
                            {
                                "action_id": action.id,
                                "kind": action.kind,
                                "elapsed_seconds": elapsed,
                                "semantic_units": len(action.payload["cells"])
                                if action.kind == "set_cells"
                                else 1,
                            },
                        )
                        return result
                except BaseException as exc:
                    self.store.finish_action(action.id, "uncertain", {"error": str(exc)})
                    self.store.event("action.uncertain", {"action_id": action.id, "error": str(exc)})
                    raise
            finally:
                try:
                    with self.store.transaction():
                        self.store.put("persona_state", self.behaviour.snapshot())
                        self.authority.release(token)
                except BaseException:
                    self.authority.release(token)
                    raise

    async def _verify(self, action, token, viewport=None):
        started = time.monotonic()
        browser = action.kind in ("navigate", "follow_link", "read_page")
        deadline = started + (15 if self.backend.mode == "macos" else 0)
        while True:
            if browser and self.backend.mode == "macos":
                # Read actual selected page text, independent of generated plan content.
                await self.executor.run(
                    [
                        Primitive(kind="hotkey", value=["command", "a"]),
                        Primitive(kind="hotkey", value=["command", "c"]),
                    ],
                    action,
                    token,
                    lambda wait=False: self._focus(action, wait),
                )
                await asyncio.sleep(0.08)
            observation = await self.observe()
            scroll_verified = True
            if action.kind == "scroll" and self.backend.mode == "macos":
                from .viewport import displacement

                after_viewport = self.backend.browser_viewport()
                delta = displacement(viewport, after_viewport)
                scroll_verified = delta is not None
                if scroll_verified:
                    self.store.event(
                        "browser.viewport_changed",
                        {
                            "action_id": action.id,
                            "before": viewport,
                            "after": after_viewport,
                            "vertical_delta_pixels": delta,
                        },
                    )
            if (
                action.kind == "open_file"
                and observation.application == self.settings.office_app
                and observation.title.startswith("Tip of the Day:")
                and "AXButton OK" in observation.focus
            ):
                await self.executor.run(
                    [Primitive(kind="key", value="enter")],
                    action,
                    token,
                    lambda wait=False: self._focus(action, wait),
                )
                self.store.event(
                    "application.dialog_dismissed", {"action_id": action.id, "title": observation.title}
                )
                await asyncio.sleep(0.15)
                continue
            page_text = self.backend.read_clipboard() if browser else None
            if scroll_verified and matches(action, observation, self.backend, clipboard_text=page_text):
                break
            if time.monotonic() >= deadline:
                raise UncertainAction(
                    "expected postcondition not observed; automatic mutation retry disabled"
                )
            await asyncio.sleep(0.25)
        self.store.event(
            "timing",
            {"category": "application_wait_and_verification", "elapsed_seconds": time.monotonic() - started},
        )
        result = {
            "observation": observation.model_dump(),
            "application_wait_seconds": time.monotonic() - started,
        }
        if browser:
            text = page_text
            evidence = self.directory / "evidence" / f"{action.id}.txt"
            evidence.parent.mkdir(exist_ok=True)
            evidence.write_text(text)
            result.update(text=text, evidence_id=action.id, sha256=hashlib.sha256(text.encode()).hexdigest())
            evidence.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "source_url": action.target,
                        "sha256": result["sha256"],
                        "backend": self.backend.mode,
                        "observation": observation.model_dump(),
                    }
                )
            )
            if action.kind == "read_page":
                await self.behaviour.context_pause("read", len(text))
        return result

    async def reconcile(self):
        """Restart never blindly replays uncertain input. File postconditions can establish completion."""
        unresolved = []
        observation = await self.observe(checkpoint=True)
        for row in self.store.uncertain():
            action = Action.model_validate_json(row["body"])
            if action.kind in ("navigate", "read_page", "open_file"):
                self.store.finish_action(
                    action.id,
                    "retryable",
                    {"reason": "idempotent observation/navigation; replan with a new action ID"},
                )
                self.store.event("restart.safe_replan", {"action_id": action.id, "kind": action.kind})
            elif action.kind in ("set_cell", "set_cells", "write_document") and matches(
                action, observation, self.backend
            ):
                self.store.finish_action(
                    action.id,
                    "done",
                    {"reconciled_after_restart": True, "artifact": self.store.record_artifact(action.target)},
                )
            else:
                unresolved.append(action.id)
        self.store.event(
            "restart.reconciled", {"unresolved": unresolved, "observation": observation.model_dump()}
        )
        if unresolved:
            raise UncertainAction(f"unresolved actions require inspection: {unresolved}")
