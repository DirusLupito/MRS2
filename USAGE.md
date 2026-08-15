# MRS2 usage

MRS2 is a small Python desktop macro recorder. It records keyboard presses,
mouse movement, mouse buttons, mouse-wheel scrolling, and the timing between
those events, then replays them at the same speed.

The interface follows the intentionally simple shape of A3-MRS: one current
macro, load/save/clear file controls, a replay action, and a plain event preview.

## Install and run

Python 3.10 or newer is recommended.

```powershell
python -m pip install -r requirements.txt
python -m mrs2
```

## Record and replay

1. Press **Ctrl + Alt + Shift** anywhere to start recording. The window
   minimizes so it does not get in the way.
2. Perform the keyboard and mouse actions to capture.
3. Press **Ctrl + Alt + Shift** again to stop. The hotkey at either end is not
   included in the recording.
4. MRS2 restores its window and automatically saves the recording under
   `recordings/recording-<timestamp>.mrs2`.
5. Use **Replay current** to replay it, or **File > Load recording** to select a
   previously saved `.mrs2` file. The same hotkey stops a replay early.

The **Start recording** button is also available. It minimizes the window and
waits briefly for the button release before capture begins.

## Recording format

`.mrs2` files are versioned JSON documents. Each event has a timestamp, a type,
and the relevant key, button, coordinate, or scroll data. Mouse positions are
absolute screen coordinates, so replay is most reliable with the same monitor
layout, display scaling, and application window positions used while recording.

## Safety and permissions

Replay sends real input to the desktop. Put the target application in the same
state it was in while recording, and keep the stop hotkey in mind. Recordings can
contain sensitive keystrokes, including passwords, so treat `.mrs2` files as
sensitive data.

Windows normally needs no extra configuration. macOS may require Accessibility
and Input Monitoring permission for the Python executable or terminal. Linux
desktop support depends on the active display server and its input permissions.
