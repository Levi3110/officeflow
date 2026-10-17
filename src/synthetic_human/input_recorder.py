"""Passive, independent macOS input telemetry. No characters or raw key codes are saved."""

from __future__ import annotations

import json
import platform
import queue
import threading
import time


class InputRecorder:
    def __init__(self, path, role="agent"):
        self.path, self.role = path, role
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.thread = None
        self.enabled = False
        self.reason = None
        self.dropped = 0
        self._queue = queue.Queue(maxsize=32768)

    def _status(self, **extra):
        return {
            "kind": "recorder.status",
            "timestamp": time.time(),
            "recording_role": self.role,
            "enabled": self.enabled,
            "reason": self.reason,
            "dropped_events": self.dropped,
            "source": "CGEventTap.listenOnly",
            "scope": "entire login session; not solely attributable to agent",
            "contains_key_content": False,
            **extra,
        }

    def start(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if platform.system() != "Darwin":
            self.reason = "macOS event tap is unavailable on this platform"
        else:
            try:
                import Quartz as Q

                if not Q.CGPreflightListenEventAccess():
                    self.reason = "Input Monitoring permission is missing"
            except ImportError:
                self.reason = "desktop dependencies are not installed"
        if self.reason:
            with self.path.open("a") as stream:
                stream.write(json.dumps(self._status()) + "\n")
            return False
        self.thread = threading.Thread(target=self._run, name="passive-input-recorder", daemon=True)
        self.thread.start()
        if not self.ready.wait(timeout=3):
            self.reason = "event tap initialization timed out"
            self.stop()
            return False
        return self.enabled

    def _run(self):
        try:
            self._listen()
        except Exception as exc:
            self.reason = str(exc)
            self.enabled = False
            with self.path.open("a") as stream:
                stream.write(json.dumps(self._status(phase="error")) + "\n")
        finally:
            self.ready.set()

    def _listen(self):
        import CoreFoundation as CF
        import Quartz as Q

        names = {
            Q.kCGEventKeyDown: "key_down",
            Q.kCGEventKeyUp: "key_up",
            Q.kCGEventLeftMouseDown: "mouse_down",
            Q.kCGEventLeftMouseUp: "mouse_up",
            Q.kCGEventRightMouseDown: "mouse_down",
            Q.kCGEventRightMouseUp: "mouse_up",
            Q.kCGEventMouseMoved: "move",
            Q.kCGEventLeftMouseDragged: "move",
            Q.kCGEventScrollWheel: "scroll",
        }
        pressed = {}
        press_sequence = 0
        tap = source = loop = None

        def enqueue(record):
            try:
                self._queue.put_nowait(record)
            except queue.Full:
                self.dropped += 1

        def callback(_proxy, event_type, event, _refcon):
            nonlocal press_sequence
            if event_type in (Q.kCGEventTapDisabledByTimeout, Q.kCGEventTapDisabledByUserInput):
                enqueue({"kind": "recorder.gap", "timestamp": time.time(), "reason": "tap disabled"})
                if tap:
                    Q.CGEventTapEnable(tap, True)
                return event
            if event_type not in names:
                return event
            try:
                record = {
                    "kind": "input.observed",
                    "event": names[event_type],
                    "timestamp": time.time(),
                    "native_timestamp_ns": int(Q.CGEventGetTimestamp(event)),
                    "target_pid": int(Q.CGEventGetIntegerValueField(event, Q.kCGEventTargetUnixProcessID)),
                    "source_pid": int(Q.CGEventGetIntegerValueField(event, Q.kCGEventSourceUnixProcessID)),
                }
                if event_type in (Q.kCGEventKeyDown, Q.kCGEventKeyUp):
                    key = int(Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode))
                    repeat = bool(Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventAutorepeat))
                    if event_type == Q.kCGEventKeyDown and not repeat:
                        press_sequence += 1
                        pressed[key] = press_sequence
                    record.update(
                        press_id=pressed.get(key),
                        repeat=repeat,
                        is_modifier=key in (54, 55, 56, 57, 58, 59, 60, 61, 62, 63),
                        is_correction=key in (51, 117),
                        is_shortcut=bool(
                            Q.CGEventGetFlags(event)
                            & (
                                Q.kCGEventFlagMaskCommand
                                | Q.kCGEventFlagMaskControl
                                | Q.kCGEventFlagMaskAlternate
                            )
                        ),
                    )
                    if event_type == Q.kCGEventKeyUp:
                        pressed.pop(key, None)
                else:
                    point = Q.CGEventGetLocation(event)
                    record.update(x=round(point.x, 2), y=round(point.y, 2))
                    if event_type == Q.kCGEventScrollWheel:
                        record["delta_y"] = int(
                            Q.CGEventGetIntegerValueField(event, Q.kCGScrollWheelEventDeltaAxis1)
                        )
                enqueue(record)
            except Exception as exc:
                enqueue({"kind": "recorder.error", "timestamp": time.time(), "error": str(exc)})
            return event

        self._callback = callback  # Keep the native callback alive for the full run loop lifetime.
        with self.path.open("a") as stream:
            try:
                mask = sum(1 << kind for kind in names)
                tap = Q.CGEventTapCreate(
                    Q.kCGSessionEventTap,
                    Q.kCGHeadInsertEventTap,
                    Q.kCGEventTapOptionListenOnly,
                    mask,
                    callback,
                    None,
                )
                if tap is None:
                    raise RuntimeError("CGEventTapCreate returned NULL")
                source = CF.CFMachPortCreateRunLoopSource(None, tap, 0)
                loop = CF.CFRunLoopGetCurrent()
                CF.CFRunLoopAddSource(loop, source, CF.kCFRunLoopCommonModes)
                Q.CGEventTapEnable(tap, True)
                self.enabled = True
                stream.write(json.dumps(self._status(phase="start")) + "\n")
                stream.flush()
                self.ready.set()
                last_flush = time.monotonic()
                while not self.stopped.is_set():
                    CF.CFRunLoopRunInMode(CF.kCFRunLoopDefaultMode, 0.1, False)
                    self._drain(stream)
                    if time.monotonic() - last_flush >= 0.5:
                        stream.flush()
                        last_flush = time.monotonic()
            except Exception as exc:
                self.reason = str(exc)
                self.enabled = False
                stream.write(json.dumps(self._status(phase="error")) + "\n")
            finally:
                self.ready.set()
                if tap:
                    Q.CGEventTapEnable(tap, False)
                if source and loop:
                    CF.CFRunLoopRemoveSource(loop, source, CF.kCFRunLoopCommonModes)
                if tap:
                    CF.CFMachPortInvalidate(tap)
                self._drain(stream)
                stream.write(json.dumps(self._status(phase="stop")) + "\n")
                self.enabled = False

    def _drain(self, stream):
        while True:
            try:
                stream.write(json.dumps(self._queue.get_nowait(), separators=(",", ":")) + "\n")
            except queue.Empty:
                break

    def stop(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=3)
