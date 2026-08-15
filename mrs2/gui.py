"""A deliberately small Tk interface for MRS2."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

from .model import InputEvent, Recording, RecordingFormatError
from .recorder import InputEngine


APP_TITLE = "MRS2 - Macro Recorder"
HOTKEY_TEXT = "Ctrl + Alt + Shift"
FILE_TYPES = [("MRS2 recordings", "*.mrs2"), ("All files", "*.*")]


def _key_label(key: dict[str, Any]) -> str:
    display = key.get("display")
    if display:
        if display == " ":
            return "Space"
        if display.isprintable():
            return repr(display)
    if key["kind"] == "special":
        return str(key["value"]).replace("_", " ").title()
    if key["kind"] == "vk":
        return f"VK {key['value']}"
    return repr(key["value"])


def describe_event(event: InputEvent) -> str:
    timestamp = f"{event.time:8.3f}s"
    if event.type == "key_down":
        return f"{timestamp}  Key down    {_key_label(event.data['key'])}"
    if event.type == "key_up":
        return f"{timestamp}  Key up      {_key_label(event.data['key'])}"
    if event.type == "mouse_move":
        return f"{timestamp}  Mouse move  ({event.data['x']}, {event.data['y']})"
    if event.type == "mouse_button":
        action = "down" if event.data["pressed"] else "up"
        return (
            f"{timestamp}  Mouse {action:<4}  {event.data['button']} at "
            f"({event.data['x']}, {event.data['y']})"
        )
    return (
        f"{timestamp}  Scroll      ({event.data['dx']}, {event.data['dy']}) at "
        f"({event.data['x']}, {event.data['y']})"
    )


class MacroRecorderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("720x520")
        self.root.minsize(580, 400)

        self._notifications: queue.SimpleQueue[tuple[str, object | None]] = (
            queue.SimpleQueue()
        )
        self.engine = InputEngine(
            lambda state, payload: self._notifications.put((state, payload))
        )
        self.current_recording: Recording | None = None
        self.current_path: Path | None = None

        self.status_text = tk.StringVar(value="Ready")
        self.current_text = tk.StringVar(value="Current recording: none")
        self._build_menu()
        self._build_window()
        self._update_controls()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.after(50, self._poll_notifications)

        try:
            self.engine.start_listeners()
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                "MRS2 could not start its global input listeners.\n\n"
                f"{exc}\n\nSee USAGE.md for operating-system permissions.",
            )
            self.status_text.set("Input listeners unavailable")

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Load recording...", command=self._load)
        file_menu.add_command(label="Save recording as...", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Clear recording", command=self._clear)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.configure(menu=menu_bar)
        self.file_menu = file_menu

    def _build_window(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(outer, text="Macro Recorder", font=("Segoe UI", 18, "bold"))
        title.pack(anchor=tk.W)
        ttk.Label(
            outer,
            text=f"Press {HOTKEY_TEXT} anywhere to start or stop recording.",
        ).pack(anchor=tk.W, pady=(2, 14))

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X)
        self.record_button = ttk.Button(
            controls, text="Start recording", command=self._start_from_button
        )
        self.record_button.pack(side=tk.LEFT)
        self.replay_button = ttk.Button(
            controls, text="Replay current", command=self._toggle_replay
        )
        self.replay_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Load...", command=self._load).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(controls, text="Save as...", command=self._save_as).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        status_row = ttk.Frame(outer)
        status_row.pack(fill=tk.X, pady=(14, 6))
        ttk.Label(status_row, text="Status:", font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Label(status_row, textvariable=self.status_text).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        ttk.Label(outer, textvariable=self.current_text).pack(anchor=tk.W, pady=(0, 8))
        self.event_preview = scrolledtext.ScrolledText(
            outer,
            height=16,
            wrap=tk.NONE,
            state=tk.DISABLED,
            font=("Consolas", 9),
        )
        self.event_preview.pack(fill=tk.BOTH, expand=True)
        self._set_preview("No recording loaded.\n")

        ttk.Label(
            outer,
            text=(
                "Replay uses the recorded timing and absolute screen coordinates. "
                f"Press {HOTKEY_TEXT} during replay to stop it."
            ),
            wraplength=680,
        ).pack(anchor=tk.W, pady=(10, 0))

    def _start_from_button(self) -> None:
        if self.engine.is_recording:
            return
        self.root.iconify()
        self.status_text.set("Recording will start...")
        self.root.after(250, self._start_after_button_release)

    def _start_after_button_release(self) -> None:
        try:
            self.engine.start_recording()
        except RuntimeError as exc:
            self.root.deiconify()
            messagebox.showwarning(APP_TITLE, str(exc))

    def _toggle_replay(self) -> None:
        if self.engine.is_playing:
            self.engine.stop_playback()
            return
        if self.current_recording is None:
            messagebox.showinfo(APP_TITLE, "Load or record a macro first.")
            return
        try:
            # Return focus to the previously active application before the
            # first recorded event is sent.
            self.root.iconify()
            self.engine.play(self.current_recording, start_delay=0.75)
        except RuntimeError as exc:
            self.root.deiconify()
            messagebox.showwarning(APP_TITLE, str(exc))

    def _load(self) -> None:
        filename = filedialog.askopenfilename(
            title="Load an MRS2 recording",
            filetypes=FILE_TYPES,
        )
        if not filename:
            return
        try:
            recording = Recording.load(filename)
        except (OSError, RecordingFormatError) as exc:
            messagebox.showerror(APP_TITLE, f"Unable to load recording.\n\n{exc}")
            return
        self.current_recording = recording
        self.current_path = Path(filename)
        self.status_text.set("Recording loaded")
        self._show_recording()

    def _save_as(self) -> None:
        if self.current_recording is None:
            messagebox.showinfo(APP_TITLE, "There is no recording to save.")
            return
        initial = self.current_path.name if self.current_path else "recording.mrs2"
        filename = filedialog.asksaveasfilename(
            title="Save MRS2 recording",
            defaultextension=".mrs2",
            initialfile=initial,
            filetypes=FILE_TYPES,
        )
        if not filename:
            return
        try:
            self.current_recording.save(filename)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Unable to save recording.\n\n{exc}")
            return
        self.current_path = Path(filename)
        self.status_text.set(f"Saved to {self.current_path}")
        self._show_recording()

    def _clear(self) -> None:
        if self.engine.is_recording or self.engine.is_playing:
            messagebox.showinfo(APP_TITLE, "Stop recording or replay before clearing.")
            return
        self.current_recording = None
        self.current_path = None
        self.current_text.set("Current recording: none")
        self.status_text.set("Ready")
        self._set_preview("No recording loaded.\n")
        self._update_controls()

    def _default_recording_path(self) -> Path:
        folder = Path.cwd() / "recordings"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        return folder / f"recording-{timestamp}.mrs2"

    def _handle_stopped_recording(self, recording: Recording) -> None:
        self.current_recording = recording
        self.current_path = self._default_recording_path()
        try:
            recording.save(self.current_path)
            self.status_text.set(f"Recording saved to {self.current_path}")
        except OSError as exc:
            self.current_path = None
            self.status_text.set("Recording stopped, but automatic save failed")
            messagebox.showerror(
                APP_TITLE,
                "The recording is still available in memory, but it could not be "
                f"saved automatically.\n\n{exc}",
            )
        self.root.deiconify()
        self.root.lift()
        self._show_recording()

    def _show_recording(self) -> None:
        if self.current_recording is None:
            return
        path_label = str(self.current_path) if self.current_path else "not saved"
        self.current_text.set(
            f"Current recording: {len(self.current_recording.events)} events, "
            f"{self.current_recording.duration:.3f} seconds — {path_label}"
        )
        lines = [describe_event(event) for event in self.current_recording.events[:500]]
        if len(self.current_recording.events) > 500:
            lines.append(
                f"\n... {len(self.current_recording.events) - 500} more events are in the file."
            )
        self._set_preview("\n".join(lines) + ("\n" if lines else "No input events.\n"))
        self._update_controls()

    def _set_preview(self, text: str) -> None:
        self.event_preview.configure(state=tk.NORMAL)
        self.event_preview.delete("1.0", tk.END)
        self.event_preview.insert("1.0", text)
        self.event_preview.configure(state=tk.DISABLED)

    def _restore_window(self) -> None:
        self.root.deiconify()
        self.root.lift()

    def _poll_notifications(self) -> None:
        while True:
            try:
                state, payload = self._notifications.get_nowait()
            except queue.Empty:
                break
            if state == "recording_started":
                self.status_text.set(
                    f"Recording — press {HOTKEY_TEXT} to stop and save"
                )
                self.root.iconify()
            elif state == "recording_stopped" and isinstance(payload, Recording):
                self._handle_stopped_recording(payload)
            elif state == "playback_started":
                self.status_text.set(
                    f"Replaying — press {HOTKEY_TEXT} to cancel"
                )
            elif state == "playback_stop_requested":
                self.status_text.set("Stopping replay...")
            elif state == "playback_finished":
                self.status_text.set("Replay finished")
                self._restore_window()
            elif state == "playback_cancelled":
                self.status_text.set("Replay stopped")
                self._restore_window()
            elif state in {"playback_error", "listener_error"}:
                self.status_text.set("Input error")
                self._restore_window()
                messagebox.showerror(APP_TITLE, f"Input operation failed.\n\n{payload}")
            self._update_controls()
        self.root.after(50, self._poll_notifications)

    def _update_controls(self) -> None:
        recording = self.engine.is_recording
        playing = self.engine.is_playing
        self.record_button.configure(
            state=tk.DISABLED if recording or playing else tk.NORMAL
        )
        self.replay_button.configure(
            text="Stop replay" if playing else "Replay current",
            state=(
                tk.NORMAL
                if playing or (self.current_recording is not None and not recording)
                else tk.DISABLED
            ),
        )
        self.file_menu.entryconfigure(
            "Save recording as...",
            state=tk.NORMAL if self.current_recording is not None else tk.DISABLED,
        )

    def _quit(self) -> None:
        self.engine.shutdown()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    MacroRecorderApp(root)
    root.mainloop()
