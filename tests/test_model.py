from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mrs2.model import InputEvent, Recording, RecordingFormatError


class RecordingTests(unittest.TestCase):
    def sample_recording(self) -> Recording:
        return Recording(
            created_at="2026-08-14T12:00:00+00:00",
            events=[
                InputEvent(
                    0.1,
                    "key_down",
                    {"key": {"kind": "vk", "value": 65, "display": "a"}},
                ),
                InputEvent(
                    0.2,
                    "key_up",
                    {"key": {"kind": "vk", "value": 65, "display": "a"}},
                ),
                InputEvent(0.3, "mouse_move", {"x": 100, "y": 200}),
                InputEvent(
                    0.4,
                    "mouse_button",
                    {"x": 100, "y": 200, "button": "left", "pressed": True},
                ),
                InputEvent(
                    0.5,
                    "mouse_scroll",
                    {"x": 100, "y": 200, "dx": 0, "dy": -1},
                ),
            ],
        )

    def test_round_trip_file(self) -> None:
        original = self.sample_recording()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.mrs2"
            original.save(path)
            loaded = Recording.load(path)

        self.assertEqual(original.to_dict(), loaded.to_dict())
        self.assertEqual(0.5, loaded.duration)

    def test_file_is_readable_json_with_format_marker(self) -> None:
        recording = self.sample_recording()
        value = json.loads(json.dumps(recording.to_dict()))
        self.assertEqual("MRS2", value["format"])
        self.assertEqual(1, value["version"])

    def test_rejects_events_out_of_order(self) -> None:
        with self.assertRaisesRegex(RecordingFormatError, "timestamp order"):
            Recording(
                events=[
                    InputEvent(2, "mouse_move", {"x": 1, "y": 2}),
                    InputEvent(1, "mouse_move", {"x": 2, "y": 3}),
                ]
            )

    def test_rejects_unknown_version(self) -> None:
        value = self.sample_recording().to_dict()
        value["version"] = 99
        with self.assertRaisesRegex(RecordingFormatError, "Unsupported MRS2 version"):
            Recording.from_dict(value)

    def test_rejects_invalid_mouse_button_state(self) -> None:
        with self.assertRaisesRegex(RecordingFormatError, "pressed"):
            InputEvent(
                0,
                "mouse_button",
                {"x": 1, "y": 2, "button": "left", "pressed": "yes"},
            )


if __name__ == "__main__":
    unittest.main()
