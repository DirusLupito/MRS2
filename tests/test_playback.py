from __future__ import annotations

import unittest

from pynput import keyboard, mouse

from mrs2.model import InputEvent
from mrs2.recorder import InputEngine


class FakeKeyboardController:
    def __init__(self) -> None:
        self.actions: list[tuple[str, object]] = []

    def press(self, key: object) -> None:
        self.actions.append(("press", key))

    def release(self, key: object) -> None:
        self.actions.append(("release", key))


class FakeMouseController:
    def __init__(self) -> None:
        self.actions: list[tuple[str, object]] = []
        self._position = (0, 0)

    @property
    def position(self) -> tuple[int, int]:
        return self._position

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        self._position = value
        self.actions.append(("move", value))

    def press(self, button: object) -> None:
        self.actions.append(("press", button))

    def release(self, button: object) -> None:
        self.actions.append(("release", button))

    def scroll(self, dx: int, dy: int) -> None:
        self.actions.append(("scroll", (dx, dy)))


class PlaybackDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keyboard = FakeKeyboardController()
        self.mouse = FakeMouseController()
        self.pressed_keys: set[object] = set()
        self.pressed_buttons: set[object] = set()

    def replay(self, event: InputEvent) -> None:
        InputEngine._replay_event(
            event,
            self.keyboard,  # type: ignore[arg-type]
            self.mouse,  # type: ignore[arg-type]
            self.pressed_keys,  # type: ignore[arg-type]
            self.pressed_buttons,  # type: ignore[arg-type]
        )

    def test_dispatches_keyboard_press_and_release(self) -> None:
        key_data = {"key": {"kind": "special", "value": "enter"}}
        self.replay(InputEvent(0, "key_down", key_data))
        self.replay(InputEvent(0.1, "key_up", key_data))
        self.assertEqual(
            [("press", keyboard.Key.enter), ("release", keyboard.Key.enter)],
            self.keyboard.actions,
        )
        self.assertEqual(set(), self.pressed_keys)

    def test_dispatches_mouse_movement_button_and_scroll(self) -> None:
        self.replay(InputEvent(0, "mouse_move", {"x": 10, "y": 20}))
        self.replay(
            InputEvent(
                0.1,
                "mouse_button",
                {"x": 10, "y": 20, "button": "left", "pressed": True},
            )
        )
        self.replay(
            InputEvent(
                0.2,
                "mouse_button",
                {"x": 10, "y": 20, "button": "left", "pressed": False},
            )
        )
        self.replay(
            InputEvent(
                0.3,
                "mouse_scroll",
                {"x": 30, "y": 40, "dx": 0, "dy": -2},
            )
        )

        self.assertEqual(
            [
                ("move", (10, 20)),
                ("move", (10, 20)),
                ("press", mouse.Button.left),
                ("move", (10, 20)),
                ("release", mouse.Button.left),
                ("move", (30, 40)),
                ("scroll", (0, -2)),
            ],
            self.mouse.actions,
        )
        self.assertEqual(set(), self.pressed_buttons)


if __name__ == "__main__":
    unittest.main()
