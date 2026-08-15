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

1. Press **Ctrl + Alt** anywhere to start recording. The window minimizes so it
   does not get in the way.
2. Perform the keyboard and mouse actions to capture.
3. Press **Ctrl + Alt** again to stop. The hotkey at either end is not included
   in the recording.
4. MRS2 restores its window and automatically saves the recording under
   `recordings/recording-<timestamp>.mrs2`.
5. Press **Ctrl + Shift** anywhere to replay the current recording, including
   while a game has focus. Press it again to stop playback. Stopping does not
   pause or save a position; the next play always starts from the beginning.
6. Use **File > Load recording** to make a previously saved `.mrs2` file the
   current recording.

The **Start recording** and **Replay current** buttons remain available in the
window. Button-started playback minimizes MRS2 before sending input.

## Game camera movement on Windows

MRS2 registers a hidden Windows Raw Input listener. New recordings store the
mouse's hardware-relative `dx` and `dy` movement as well as its desktop cursor
position. During playback those recordings use Windows `SendInput` relative
motion, which is the form commonly consumed by first-person and third-person
game cameras.

Record the macro again after updating MRS2. Older `.mrs2` files contain only
absolute cursor positions and continue to replay in the old desktop-compatible
mode.

If the game is running as administrator, run MRS2 at the same privilege level;
Windows blocks input injection from a lower-integrity process. Some games or
anti-cheat systems deliberately reject all injected input. MRS2 does not attempt
to bypass those protections.

Microsoft references: [Raw Input overview](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-raw-input),
[RAWMOUSE](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-rawmouse),
and [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput).

## Recording format

`.mrs2` files are versioned JSON documents. Each event has a timestamp, a type,
and the relevant key, button, coordinate, delta, or scroll data. Mouse positions
are absolute screen coordinates, so desktop replay is most reliable with the
same monitor layout, display scaling, and application window positions used
while recording.

## Safety and permissions

Replay sends real input to the desktop. Put the target application in the same
state it was in while recording, and keep the stop hotkey in mind. Recordings can
contain sensitive keystrokes, including passwords, so treat `.mrs2` files as
sensitive data.

Windows normally needs no extra configuration. macOS may require Accessibility
and Input Monitoring permission for the Python executable or terminal. Linux
desktop support depends on the active display server and its input permissions.
