"""The on-disk MRS2 recording model.

The format is intentionally JSON so that a recording can be inspected without
special tools. Input capture and playback live in :mod:`mrs2.recorder`; this
module has no third-party dependencies and is safe to use in tests or tooling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Mapping


FORMAT_NAME = "MRS2"
FORMAT_VERSION = 1
EVENT_TYPES = {
    "key_down",
    "key_up",
    "mouse_move",
    "mouse_button",
    "mouse_scroll",
}


class RecordingFormatError(ValueError):
    """Raised when a file is not a valid, supported MRS2 recording."""


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecordingFormatError(f"{label} must be a number.")
    converted = float(value)
    if not math.isfinite(converted):
        raise RecordingFormatError(f"{label} must be finite.")
    return converted


def _integer(value: object, label: str) -> int:
    number = _number(value, label)
    if not number.is_integer():
        raise RecordingFormatError(f"{label} must be an integer.")
    return int(number)


def _validate_key(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RecordingFormatError("A keyboard event must contain a key object.")

    key_kind = value.get("kind")
    key_value = value.get("value")
    if key_kind == "special":
        if not isinstance(key_value, str) or not key_value:
            raise RecordingFormatError("A special key must have a name.")
    elif key_kind == "char":
        if not isinstance(key_value, str) or not key_value:
            raise RecordingFormatError("A character key must have a value.")
    elif key_kind == "vk":
        key_value = _integer(key_value, "Virtual-key value")
    else:
        raise RecordingFormatError(f"Unsupported key kind: {key_kind!r}.")

    result: dict[str, Any] = {"kind": key_kind, "value": key_value}
    display = value.get("display")
    if display is not None:
        if not isinstance(display, str):
            raise RecordingFormatError("A key display value must be text.")
        result["display"] = display
    return result


@dataclass(slots=True, eq=False)
class InputEvent:
    """One timestamped keyboard or mouse event."""

    time: float
    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.time = _number(self.time, "Event time")
        if self.time < 0:
            raise RecordingFormatError("Event time cannot be negative.")
        if self.type not in EVENT_TYPES:
            raise RecordingFormatError(f"Unsupported event type: {self.type!r}.")
        self.data = self._validated_data(self.type, self.data)

    @staticmethod
    def _validated_data(event_type: str, data: object) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            raise RecordingFormatError("Event data must be an object.")

        if event_type in {"key_down", "key_up"}:
            return {"key": _validate_key(data.get("key"))}

        x = _integer(data.get("x"), "Mouse x coordinate")
        y = _integer(data.get("y"), "Mouse y coordinate")
        if event_type == "mouse_move":
            result = {"x": x, "y": y}
            has_dx = "dx" in data
            has_dy = "dy" in data
            if has_dx != has_dy:
                raise RecordingFormatError(
                    "A relative mouse event must contain both dx and dy."
                )
            if has_dx:
                result["dx"] = _integer(data.get("dx"), "Relative mouse x movement")
                result["dy"] = _integer(data.get("dy"), "Relative mouse y movement")
            return result
        if event_type == "mouse_button":
            button = data.get("button")
            pressed = data.get("pressed")
            if not isinstance(button, str) or not button:
                raise RecordingFormatError("A mouse button event needs a button name.")
            if not isinstance(pressed, bool):
                raise RecordingFormatError("Mouse button 'pressed' must be true or false.")
            return {"x": x, "y": y, "button": button, "pressed": pressed}

        return {
            "x": x,
            "y": y,
            "dx": _integer(data.get("dx"), "Horizontal scroll amount"),
            "dy": _integer(data.get("dy"), "Vertical scroll amount"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"time": round(self.time, 6), "type": self.type, **self.data}

    @classmethod
    def from_dict(cls, value: object) -> "InputEvent":
        if not isinstance(value, Mapping):
            raise RecordingFormatError("Each event must be an object.")
        event_type = value.get("type")
        if not isinstance(event_type, str):
            raise RecordingFormatError("Each event must have a type.")
        return cls(
            time=value.get("time"),  # type: ignore[arg-type]
            type=event_type,
            data={key: item for key, item in value.items() if key not in {"time", "type"}},
        )


@dataclass(slots=True)
class Recording:
    """A complete sequence of input events."""

    events: list[InputEvent] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        if not isinstance(self.created_at, str) or not self.created_at:
            raise RecordingFormatError("Recording creation time must be text.")
        previous = -1.0
        for event in self.events:
            if not isinstance(event, InputEvent):
                raise RecordingFormatError("Recording events must be InputEvent objects.")
            if event.time < previous:
                raise RecordingFormatError("Recording events must be in timestamp order.")
            previous = event.time

    @property
    def duration(self) -> float:
        return self.events[-1].time if self.events else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "created_at": self.created_at,
            "duration_seconds": round(self.duration, 6),
            "events": [event.to_dict() for event in self.events],
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return destination

    @classmethod
    def from_dict(cls, value: object) -> "Recording":
        if not isinstance(value, Mapping):
            raise RecordingFormatError("The recording must be a JSON object.")
        if value.get("format") != FORMAT_NAME:
            raise RecordingFormatError("This is not an MRS2 recording.")
        if value.get("version") != FORMAT_VERSION:
            raise RecordingFormatError(
                f"Unsupported MRS2 version: {value.get('version')!r}."
            )
        raw_events = value.get("events")
        if not isinstance(raw_events, list):
            raise RecordingFormatError("The recording must contain an event list.")
        created_at = value.get("created_at")
        if not isinstance(created_at, str):
            raise RecordingFormatError("The recording must have a creation time.")
        return cls(
            events=[InputEvent.from_dict(event) for event in raw_events],
            created_at=created_at,
        )

    @classmethod
    def load(cls, path: str | Path) -> "Recording":
        source = Path(path)
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RecordingFormatError(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}."
            ) from exc
        return cls.from_dict(value)
