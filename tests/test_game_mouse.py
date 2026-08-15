from __future__ import annotations

import unittest
from unittest.mock import patch

from mrs2.model import InputEvent, Recording, RecordingFormatError
from mrs2.recorder import InputEngine


class _FakeKeyboard:
    def press(self, key: object) -> None:
        pass

    def release(self, key: object) -> None:
        pass


class _FakeMouse:
    def __init__(self) -> None:
        self.position = (0, 0)


class GameMouseTests(unittest.TestCase):
    def test_relative_mouse_event_round_trips(self) -> None:
        event = InputEvent(
            0.25,
            "mouse_move",
            {"x": 960, "y": 540, "dx": -13, "dy": 7},
        )
        loaded = Recording.from_dict(Recording(events=[event]).to_dict())
        self.assertEqual(
            {"x": 960, "y": 540, "dx": -13, "dy": 7},
            loaded.events[0].data,
        )

    def test_relative_mouse_event_requires_both_deltas(self) -> None:
        with self.assertRaisesRegex(RecordingFormatError, "both dx and dy"):
            InputEvent(0, "mouse_move", {"x": 1, "y": 2, "dx": 3})

    def test_raw_motion_is_captured_with_absolute_position(self) -> None:
        engine = InputEngine()
        engine.start_recording()
        engine._on_raw_mouse_move(dx=8, dy=-4, x=500, y=400)
        recording = engine.stop_recording()

        assert recording is not None
        self.assertEqual(1, len(recording.events))
        self.assertEqual(
            {"x": 500, "y": 400, "dx": 8, "dy": -4},
            recording.events[0].data,
        )

    @patch("mrs2.recorder.send_relative_mouse")
    def test_relative_motion_uses_send_input_instead_of_cursor_position(
        self, send_relative_mouse
    ) -> None:
        fake_mouse = _FakeMouse()
        InputEngine._replay_event(
            InputEvent(
                0,
                "mouse_move",
                {"x": 960, "y": 540, "dx": 12, "dy": -6},
            ),
            _FakeKeyboard(),  # type: ignore[arg-type]
            fake_mouse,  # type: ignore[arg-type]
            set(),
            set(),
        )

        send_relative_mouse.assert_called_once_with(12, -6)
        self.assertEqual((0, 0), fake_mouse.position)


if __name__ == "__main__":
    unittest.main()
