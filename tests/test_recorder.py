from __future__ import annotations

import unittest

from pynput import keyboard

from mrs2.model import Recording
from mrs2.recorder import InputEngine, _decode_key, _encode_key, _hotkey_part


class InputEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.notifications: list[tuple[str, object | None]] = []
        self.engine = InputEngine(
            lambda state, payload: self.notifications.append((state, payload))
        )

    def press_record_hotkey(self) -> None:
        self.engine._on_key_press(keyboard.Key.ctrl_l)
        self.engine._on_key_press(keyboard.Key.alt_l)

    def release_record_hotkey(self) -> None:
        self.engine._on_key_release(keyboard.Key.alt_l)
        self.engine._on_key_release(keyboard.Key.ctrl_l)

    def press_play_hotkey(self) -> None:
        self.engine._on_key_press(keyboard.Key.ctrl_l)
        self.engine._on_key_press(keyboard.Key.shift_l)

    def release_play_hotkey(self) -> None:
        self.engine._on_key_release(keyboard.Key.shift_l)
        self.engine._on_key_release(keyboard.Key.ctrl_l)

    def test_ctrl_alt_starts_and_stops_without_being_recorded(self) -> None:
        self.press_record_hotkey()
        self.assertTrue(self.engine.is_recording)
        self.release_record_hotkey()

        letter = keyboard.KeyCode.from_char("a")
        self.engine._on_key_press(letter)
        self.engine._on_key_release(letter)

        self.press_record_hotkey()
        self.assertFalse(self.engine.is_recording)

        stopped = [
            payload
            for state, payload in self.notifications
            if state == "recording_stopped"
        ]
        self.assertEqual(1, len(stopped))
        recording = stopped[0]
        self.assertIsInstance(recording, Recording)
        assert isinstance(recording, Recording)
        self.assertEqual(["key_down", "key_up"], [e.type for e in recording.events])
        self.assertTrue(
            all(e.data["key"].get("display") == "a" for e in recording.events)
        )

    def test_ctrl_shift_requests_playback_when_idle(self) -> None:
        self.press_play_hotkey()
        requests = [
            state for state, _payload in self.notifications if state == "playback_requested"
        ]
        self.assertEqual(["playback_requested"], requests)
        self.assertFalse(self.engine.is_recording)

        # Key-repeat callbacks must not generate a second request while the
        # activation chord remains held.
        self.engine._on_key_press(keyboard.Key.shift_l)
        requests = [
            state for state, _payload in self.notifications if state == "playback_requested"
        ]
        self.assertEqual(["playback_requested"], requests)

    def test_ctrl_shift_stops_active_playback_without_pause_state(self) -> None:
        with self.engine._lock:
            self.engine._playing = True
            self.engine._cancel_playback.clear()

        self.press_play_hotkey()

        self.assertTrue(self.engine._cancel_playback.is_set())
        self.assertIn(
            "playback_stop_requested",
            [state for state, _payload in self.notifications],
        )
        # The engine stores no event index or paused position; every play call
        # creates a fresh worker starting at recording.events[0].
        self.assertFalse(hasattr(self.engine, "_playback_position"))

    def test_ctrl_shift_is_ordinary_input_while_recording(self) -> None:
        self.press_record_hotkey()
        self.release_record_hotkey()

        self.press_play_hotkey()
        self.release_play_hotkey()
        self.assertTrue(self.engine.is_recording)
        self.assertNotIn(
            "playback_requested",
            [state for state, _payload in self.notifications],
        )

        self.press_record_hotkey()
        stopped = [
            payload
            for state, payload in self.notifications
            if state == "recording_stopped"
        ]
        recording = stopped[-1]
        assert isinstance(recording, Recording)
        special_keys = [event.data["key"]["value"] for event in recording.events]
        self.assertEqual(["ctrl_l", "shift", "shift", "ctrl_l"], special_keys)

    def test_hotkey_part_accepts_left_and_right_modifiers(self) -> None:
        self.assertEqual("ctrl", _hotkey_part(keyboard.Key.ctrl_r))
        self.assertEqual("alt", _hotkey_part(keyboard.Key.alt_l))
        self.assertEqual("shift", _hotkey_part(keyboard.Key.shift_r))
        self.assertIsNone(_hotkey_part(keyboard.Key.enter))

    def test_key_encoding_round_trip(self) -> None:
        for key in (keyboard.Key.enter, keyboard.KeyCode.from_char("z")):
            encoded = _encode_key(key)
            decoded = _decode_key(encoded)
            self.assertEqual(key, decoded)


if __name__ == "__main__":
    unittest.main()
