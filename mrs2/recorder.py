"""Global input capture and playback using pynput."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable

from pynput import keyboard, mouse

from .model import InputEvent, Recording, RecordingFormatError


StateCallback = Callable[[str, object | None], None]
HOTKEY_PARTS = frozenset({"ctrl", "alt", "shift"})


def _hotkey_part(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    if key in {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}:
        return "ctrl"
    if key in {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r}:
        return "alt"
    if key in {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}:
        return "shift"
    return None


def _encode_key(key: keyboard.Key | keyboard.KeyCode) -> dict[str, Any]:
    if isinstance(key, keyboard.Key):
        return {"kind": "special", "value": key.name}

    virtual_key = getattr(key, "vk", None)
    character = getattr(key, "char", None)
    if virtual_key is not None:
        result: dict[str, Any] = {"kind": "vk", "value": int(virtual_key)}
        if character:
            result["display"] = character
        return result
    if character:
        return {"kind": "char", "value": character, "display": character}
    raise RecordingFormatError(f"Cannot represent keyboard key {key!r}.")


def _decode_key(value: dict[str, Any]) -> keyboard.Key | keyboard.KeyCode:
    if value["kind"] == "special":
        try:
            return getattr(keyboard.Key, value["value"])
        except AttributeError as exc:
            raise RecordingFormatError(
                f"This computer does not support the key {value['value']!r}."
            ) from exc
    if value["kind"] == "vk":
        return keyboard.KeyCode.from_vk(value["value"])
    return keyboard.KeyCode.from_char(value["value"])


class InputEngine:
    """Own the global listeners and one recording/playback session at a time."""

    def __init__(self, on_state_change: StateCallback | None = None) -> None:
        self._on_state_change = on_state_change or (lambda _state, _payload: None)
        self._lock = threading.RLock()
        self._recording = False
        self._playing = False
        self._events: list[InputEvent] = []
        self._started_at = 0.0
        self._created_at = ""
        self._held_hotkey_keys: set[keyboard.Key | keyboard.KeyCode] = set()
        self._hotkey_latched = False
        self._suppress_activation_chord = False
        self._hotkey_candidate_events: list[InputEvent] = []
        self._cancel_playback = threading.Event()
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    def start_listeners(self) -> None:
        """Start the global keyboard and mouse listeners."""
        if self._keyboard_listener is not None:
            return
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def shutdown(self) -> None:
        self._cancel_playback.set()
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        if self._mouse_listener is not None:
            self._mouse_listener.stop()

    def start_recording(self) -> bool:
        with self._lock:
            if self._recording:
                return False
            if self._playing:
                raise RuntimeError("Stop replay before starting a recording.")
            self._start_recording_locked()
        self._notify("recording_started")
        return True

    def stop_recording(self) -> Recording | None:
        with self._lock:
            if not self._recording:
                return None
            recording = self._finish_recording_locked()
        self._notify("recording_stopped", recording)
        return recording

    def play(self, recording: Recording, start_delay: float = 0.0) -> bool:
        with self._lock:
            if self._playing:
                return False
            if self._recording:
                raise RuntimeError("Stop recording before starting a replay.")
            self._playing = True
            self._cancel_playback.clear()
        threading.Thread(
            target=self._playback_worker,
            args=(recording, max(0.0, start_delay)),
            name="mrs2-playback",
            daemon=True,
        ).start()
        self._notify("playback_started")
        return True

    def stop_playback(self) -> None:
        if self.is_playing:
            self._cancel_playback.set()
            self._notify("playback_stop_requested")

    def _start_recording_locked(self) -> None:
        self._events = []
        self._hotkey_candidate_events = []
        self._started_at = time.perf_counter()
        self._created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._recording = True

    def _finish_recording_locked(self) -> Recording:
        recording = Recording(events=list(self._events), created_at=self._created_at)
        self._recording = False
        self._events = []
        self._hotkey_candidate_events = []
        return recording

    def _timestamp_locked(self) -> float:
        return max(0.0, time.perf_counter() - self._started_at)

    def _append_locked(self, event_type: str, **data: Any) -> InputEvent | None:
        if not self._recording or self._suppress_activation_chord:
            return None
        event = InputEvent(self._timestamp_locked(), event_type, data)
        if (
            event_type == "mouse_move"
            and self._events
            and self._events[-1].type == "mouse_move"
            and self._events[-1].data == event.data
        ):
            return None
        self._events.append(event)
        return event

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        notifications: list[tuple[str, object | None]] = []
        try:
            with self._lock:
                part = _hotkey_part(key)
                first_hotkey_key = part is not None and not self._held_hotkey_keys
                if part is not None:
                    self._held_hotkey_keys.add(key)

                if self._recording:
                    event = self._append_locked("key_down", key=_encode_key(key))
                    if part is not None and event is not None:
                        if first_hotkey_key:
                            self._hotkey_candidate_events = []
                        self._hotkey_candidate_events.append(event)

                active_parts = {
                    hotkey_part
                    for held_key in self._held_hotkey_keys
                    if (hotkey_part := _hotkey_part(held_key)) is not None
                }
                if active_parts == HOTKEY_PARTS and not self._hotkey_latched:
                    self._hotkey_latched = True
                    if self._playing:
                        self._cancel_playback.set()
                        notifications.append(("playback_stop_requested", None))
                    elif self._recording:
                        candidate_ids = {id(event) for event in self._hotkey_candidate_events}
                        self._events = [
                            event for event in self._events if id(event) not in candidate_ids
                        ]
                        recording = self._finish_recording_locked()
                        notifications.append(("recording_stopped", recording))
                    else:
                        self._start_recording_locked()
                        self._suppress_activation_chord = True
                        notifications.append(("recording_started", None))
        except Exception as exc:  # pynput stops a listener when a callback escapes
            notifications.append(("listener_error", exc))

        for state, payload in notifications:
            self._notify(state, payload)

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        try:
            with self._lock:
                part = _hotkey_part(key)
                if self._recording:
                    event = self._append_locked("key_up", key=_encode_key(key))
                    if part is not None and event is not None:
                        self._hotkey_candidate_events.append(event)

                if part is not None:
                    self._held_hotkey_keys.discard(key)
                if not self._held_hotkey_keys:
                    self._hotkey_latched = False
                    if self._suppress_activation_chord:
                        # Begin the event timeline after the activation chord
                        # is fully released, not while its keys are still up.
                        self._started_at = time.perf_counter()
                    self._suppress_activation_chord = False
                    self._hotkey_candidate_events = []
        except Exception as exc:
            self._notify("listener_error", exc)

    def _on_mouse_move(self, x: int, y: int) -> None:
        with self._lock:
            self._append_locked("mouse_move", x=x, y=y)

    def _on_mouse_click(
        self, x: int, y: int, button: mouse.Button, pressed: bool
    ) -> None:
        with self._lock:
            self._append_locked(
                "mouse_button",
                x=x,
                y=y,
                button=button.name,
                pressed=pressed,
            )

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        with self._lock:
            self._append_locked("mouse_scroll", x=x, y=y, dx=dx, dy=dy)

    def _playback_worker(self, recording: Recording, start_delay: float) -> None:
        keyboard_controller = keyboard.Controller()
        mouse_controller = mouse.Controller()
        pressed_keys: set[keyboard.Key | keyboard.KeyCode] = set()
        pressed_buttons: set[mouse.Button] = set()
        state = "playback_finished"
        payload: object | None = None
        try:
            if start_delay and self._cancel_playback.wait(start_delay):
                state = "playback_cancelled"
                return
            started_at = time.perf_counter()
            for event in recording.events:
                delay = event.time - (time.perf_counter() - started_at)
                if delay > 0 and self._cancel_playback.wait(delay):
                    state = "playback_cancelled"
                    break
                if self._cancel_playback.is_set():
                    state = "playback_cancelled"
                    break
                self._replay_event(
                    event,
                    keyboard_controller,
                    mouse_controller,
                    pressed_keys,
                    pressed_buttons,
                )
        except Exception as exc:
            state = "playback_error"
            payload = exc
        finally:
            for key in tuple(pressed_keys):
                try:
                    keyboard_controller.release(key)
                except Exception:
                    pass
            for button in tuple(pressed_buttons):
                try:
                    mouse_controller.release(button)
                except Exception:
                    pass
            with self._lock:
                self._playing = False
            self._notify(state, payload)

    @staticmethod
    def _replay_event(
        event: InputEvent,
        keyboard_controller: keyboard.Controller,
        mouse_controller: mouse.Controller,
        pressed_keys: set[keyboard.Key | keyboard.KeyCode],
        pressed_buttons: set[mouse.Button],
    ) -> None:
        if event.type in {"key_down", "key_up"}:
            key = _decode_key(event.data["key"])
            if event.type == "key_down":
                keyboard_controller.press(key)
                pressed_keys.add(key)
            else:
                keyboard_controller.release(key)
                pressed_keys.discard(key)
            return

        mouse_controller.position = (event.data["x"], event.data["y"])
        if event.type == "mouse_move":
            return
        if event.type == "mouse_scroll":
            mouse_controller.scroll(event.data["dx"], event.data["dy"])
            return

        try:
            button = getattr(mouse.Button, event.data["button"])
        except AttributeError as exc:
            raise RecordingFormatError(
                f"This computer does not support mouse button {event.data['button']!r}."
            ) from exc
        if event.data["pressed"]:
            mouse_controller.press(button)
            pressed_buttons.add(button)
        else:
            mouse_controller.release(button)
            pressed_buttons.discard(button)

    def _notify(self, state: str, payload: object | None = None) -> None:
        try:
            self._on_state_change(state, payload)
        except Exception:
            pass
