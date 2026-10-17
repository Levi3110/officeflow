from __future__ import annotations

import asyncio
import math
import random
import re
import time

from .models import Persona, Primitive


class HumanBehaviourEngine:
    """A session-scoped persona; conditional timing, not an independent delay per action."""

    def __init__(self, persona, event, realtime=True):
        self.persona, self.event, self.realtime = persona, event, realtime
        self.random = random.Random(persona.seed)
        self.rhythm = 1.0
        self.fatigue = 0.0
        self.elapsed = 0.0
        self.chunk_remaining = self.random.randint(3, 7)

    def snapshot(self):
        return {
            "persona": self.persona.model_dump(),
            "rng": self.random.getstate(),
            "rhythm": self.rhythm,
            "fatigue": self.fatigue,
            "chunk_remaining": self.chunk_remaining,
        }

    def restore(self, state):
        if Persona.model_validate(state["persona"]).model_dump() != self.persona.model_dump():
            raise ValueError("persona differs from saved session; use original persona when resuming")

        def tuples(value):
            return tuple(tuples(x) for x in value) if isinstance(value, (list, tuple)) else value

        self.random.setstate(tuples(state["rng"]))
        self.rhythm, self.fatigue = state["rhythm"], state["fatigue"]
        self.chunk_remaining = state["chunk_remaining"]

    async def pause(self, category, seconds):
        sampled = max(0, seconds * self.persona.pause_scale)
        started = time.monotonic()
        if self.realtime:
            await asyncio.sleep(sampled)
        # Executor already yields between primitives in simulation; no duplicate scheduling per pause.
        elapsed = time.monotonic() - started
        self.elapsed += elapsed
        self.event(
            "timing",
            {
                "category": category,
                "requested_seconds": sampled,
                "elapsed_seconds": elapsed,
                "simulated_timing": not self.realtime,
            },
        )

    async def context_pause(self, context, characters=0):
        if context == "read":
            seconds = min(6, max(0.4, characters / self.random.uniform(45, 80)))
        elif context == "switch":
            seconds = self.random.lognormvariate(math.log(0.45), 0.25)
        else:
            seconds = self.random.lognormvariate(math.log(0.18), 0.35)
        await self.pause("behaviour." + context, seconds)

    async def type(self, text, emit, allow_typo=False):
        protected = set()
        for match in re.finditer(r"\S*(?:://|@)\S*", text):
            protected.update(range(match.start(), match.end()))
        for index, char in enumerate(text):
            self.rhythm = 0.88 * self.rhythm + 0.12 * self.random.uniform(0.75, 1.3)
            self.fatigue = min(0.18, self.fatigue + 0.00002)
            # Never perturb commands, URLs, numbers or formulas. Fix prose typos before continuing.
            if (
                allow_typo
                and index not in protected
                and char.isascii()
                and char.isalpha()
                and self.random.random() < self.persona.typo_probability
            ):
                neighbors = {
                    "q": "wa",
                    "w": "qeas",
                    "e": "wrsd",
                    "r": "etdf",
                    "t": "ryfg",
                    "y": "tugh",
                    "u": "yihj",
                    "i": "uojk",
                    "o": "ipkl",
                    "p": "ol",
                    "a": "qwsz",
                    "s": "awedxz",
                    "d": "serfcx",
                    "f": "drtgvc",
                    "g": "ftyhbv",
                    "h": "gyujnb",
                    "j": "huikmn",
                    "k": "jiolm",
                    "l": "kop",
                    "z": "asx",
                    "x": "zsdc",
                    "c": "xdfv",
                    "v": "cfgb",
                    "b": "vghn",
                    "n": "bhjm",
                    "m": "njk",
                }
                wrong = self.random.choice(neighbors[char.lower()])
                await emit(
                    Primitive(
                        kind="text",
                        value=wrong,
                        hold_seconds=self.random.uniform(0.045, 0.085) * self.persona.pause_scale,
                    )
                )
                await self.pause("behaviour.typo_notice", self.random.uniform(0.12, 0.4))
                await emit(Primitive(kind="key", value="backspace"))
            interval = self.random.lognormvariate(
                math.log((1 + self.fatigue) * self.rhythm / self.persona.characters_per_second),
                self.persona.typing_log_sigma,
            )
            if char in ".!?\n":
                interval += self.random.uniform(0.15, 0.5)
            elif char == " ":
                self.chunk_remaining -= 1
                if self.chunk_remaining <= 0:
                    interval += self.random.lognormvariate(math.log(0.24), 0.35)
                    self.chunk_remaining = self.random.randint(3, 7)
            sampled_hold = self.random.lognormvariate(
                math.log(self.persona.key_hold_median_seconds), self.persona.key_hold_log_sigma
            )
            if self.persona.independent_key_hold:
                # Serial delivery cannot overlap keys. Preserve the independently sampled hold
                # and extend a too-short onset; do not clip fast intervals into unnaturally short holds.
                hold = min(0.45, sampled_hold)
                interval = max(interval, hold + 0.012)
            else:
                hold = min(interval * 0.65, sampled_hold)
            await emit(
                Primitive(
                    kind="text",
                    value=char,
                    hold_seconds=hold * self.persona.pause_scale,
                    onset_interval_seconds=interval * self.persona.pause_scale,
                )
            )
            await self.pause("behaviour.typing", interval - hold)

    async def scroll(self, amount, emit):
        remaining = abs(int(amount))
        direction = 1 if amount > 0 else -1
        while remaining:
            burst = min(remaining, self.random.randint(1, 3))
            await emit(Primitive(kind="scroll", value=direction * burst))
            remaining -= burst
            if remaining:
                await self.pause("behaviour.scroll", self.random.uniform(0.12, 0.32))

    async def move_to(self, origin, target, emit):
        dx, dy = target[0] - origin[0], target[1] - origin[1]
        distance = math.hypot(dx, dy)
        if distance < 1:
            return
        bend = self.random.uniform(-0.14, 0.14)
        control = (origin[0] + dx * 0.45 - dy * bend, origin[1] + dy * 0.45 + dx * bend)
        duration = min(0.9, 0.12 + 0.11 * math.log2(distance / 24 + 1)) * self.random.uniform(0.9, 1.1)
        steps = max(6, int(duration / 0.025))
        for step in range(1, steps + 1):
            t = step / steps
            # Smooth acceleration/deceleration with a small, session-consistent curved path.
            t = 3 * t * t - 2 * t * t * t
            point = [
                (1 - t) ** 2 * origin[i] + 2 * (1 - t) * t * control[i] + t * t * target[i] for i in (0, 1)
            ]
            await emit(Primitive(kind="move", value=point))
            await self.pause("behaviour.pointer", duration / steps)
