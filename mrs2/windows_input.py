"""Windows raw-mouse capture and relative ``SendInput`` playback.

Games commonly consume relative ``WM_INPUT`` mouse data instead of cursor
positions. This module keeps the Win32-specific code isolated from the rest of
MRS2 and provides availability stubs on other operating systems.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import threading
from typing import Callable


WINDOWS_RAW_INPUT_AVAILABLE = sys.platform == "win32"
RawMotionCallback = Callable[[int, int, int, int], None]


if WINDOWS_RAW_INPUT_AVAILABLE:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WM_INPUT = 0x00FF
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    RID_INPUT = 0x10000003
    RIM_TYPEMOUSE = 0
    RIDEV_REMOVE = 0x00000001
    RIDEV_INPUTSINK = 0x00000100
    MOUSE_MOVE_ABSOLUTE = 0x0001
    MOUSEEVENTF_MOVE = 0x0001
    INPUT_MOUSE = 0

    class _RawInputDevice(ctypes.Structure):
        _fields_ = [
            ("usUsagePage", wintypes.USHORT),
            ("usUsage", wintypes.USHORT),
            ("dwFlags", wintypes.DWORD),
            ("hwndTarget", wintypes.HWND),
        ]

    class _RawInputHeader(ctypes.Structure):
        _fields_ = [
            ("dwType", wintypes.DWORD),
            ("dwSize", wintypes.DWORD),
            ("hDevice", wintypes.HANDLE),
            ("wParam", wintypes.WPARAM),
        ]

    class _RawMouseButtons(ctypes.Structure):
        _fields_ = [
            ("usButtonFlags", wintypes.USHORT),
            ("usButtonData", wintypes.USHORT),
        ]

    class _RawMouseButtonUnion(ctypes.Union):
        _fields_ = [
            ("ulButtons", wintypes.ULONG),
            ("buttons", _RawMouseButtons),
        ]

    class _RawMouse(ctypes.Structure):
        _anonymous_ = ("button_union",)
        _fields_ = [
            ("usFlags", wintypes.USHORT),
            ("button_union", _RawMouseButtonUnion),
            ("ulRawButtons", wintypes.ULONG),
            ("lLastX", wintypes.LONG),
            ("lLastY", wintypes.LONG),
            ("ulExtraInformation", wintypes.ULONG),
        ]

    class _MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.WPARAM),
        ]

    class _InputUnion(ctypes.Union):
        _fields_ = [("mouse", _MouseInput)]

    class _Input(ctypes.Structure):
        _anonymous_ = ("data",)
        _fields_ = [("type", wintypes.DWORD), ("data", _InputUnion)]

    _WindowProc = ctypes.WINFUNCTYPE(
        wintypes.LPARAM,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    class _WindowClass(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", _WindowProc),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    _user32.RegisterClassW.argtypes = [ctypes.POINTER(_WindowClass)]
    _user32.RegisterClassW.restype = wintypes.ATOM
    _user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    _user32.UnregisterClassW.restype = wintypes.BOOL
    _user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HANDLE,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    _user32.CreateWindowExW.restype = wintypes.HWND
    _user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _user32.DefWindowProcW.restype = wintypes.LPARAM
    _user32.DestroyWindow.argtypes = [wintypes.HWND]
    _user32.DestroyWindow.restype = wintypes.BOOL
    _user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _user32.PostMessageW.restype = wintypes.BOOL
    _user32.PostQuitMessage.argtypes = [ctypes.c_int]
    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.GetMessageW.restype = wintypes.BOOL
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.TranslateMessage.restype = wintypes.BOOL
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.restype = wintypes.LPARAM
    _user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    _user32.GetCursorPos.restype = wintypes.BOOL
    _user32.RegisterRawInputDevices.argtypes = [
        ctypes.POINTER(_RawInputDevice),
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.RegisterRawInputDevices.restype = wintypes.BOOL
    _user32.GetRawInputData.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.UINT),
        wintypes.UINT,
    ]
    _user32.GetRawInputData.restype = wintypes.UINT
    _user32.SendInput.argtypes = [
        wintypes.UINT,
        ctypes.POINTER(_Input),
        ctypes.c_int,
    ]
    _user32.SendInput.restype = wintypes.UINT
    _kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    _kernel32.GetModuleHandleW.restype = wintypes.HMODULE


    class RawMouseListener:
        """Receive background physical mouse deltas from the Raw Input API."""

        def __init__(self, callback: RawMotionCallback) -> None:
            self._callback = callback
            self._thread: threading.Thread | None = None
            self._ready = threading.Event()
            self._error: BaseException | None = None
            self._hwnd: int | None = None
            self._class_name = f"MRS2RawMouse_{id(self):x}"
            self._window_proc_callback = _WindowProc(self._window_proc)

        def start(self) -> None:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._message_loop,
                name="mrs2-raw-mouse",
                daemon=True,
            )
            self._thread.start()
            if not self._ready.wait(2.0):
                raise TimeoutError("Timed out while starting Windows raw mouse input.")
            if self._error is not None:
                raise RuntimeError("Unable to start Windows raw mouse input.") from self._error

        def stop(self) -> None:
            hwnd = self._hwnd
            if hwnd:
                _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            if self._thread is not None:
                self._thread.join(timeout=2.0)

        def _message_loop(self) -> None:
            instance = _kernel32.GetModuleHandleW(None)
            window_class = _WindowClass(
                0,
                self._window_proc_callback,
                0,
                0,
                instance,
                None,
                None,
                None,
                None,
                self._class_name,
            )
            registered = False
            try:
                if not _user32.RegisterClassW(ctypes.byref(window_class)):
                    raise ctypes.WinError(ctypes.get_last_error())
                registered = True
                hwnd = _user32.CreateWindowExW(
                    0,
                    self._class_name,
                    "MRS2 Raw Mouse Input",
                    0,
                    0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    instance,
                    None,
                )
                if not hwnd:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._hwnd = hwnd

                device = _RawInputDevice(0x01, 0x02, RIDEV_INPUTSINK, hwnd)
                if not _user32.RegisterRawInputDevices(
                    ctypes.byref(device), 1, ctypes.sizeof(_RawInputDevice)
                ):
                    raise ctypes.WinError(ctypes.get_last_error())

                self._ready.set()
                message = wintypes.MSG()
                while True:
                    result = _user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                    if result == 0:
                        break
                    if result == -1:
                        raise ctypes.WinError(ctypes.get_last_error())
                    _user32.TranslateMessage(ctypes.byref(message))
                    _user32.DispatchMessageW(ctypes.byref(message))
            except BaseException as exc:
                self._error = exc
                self._ready.set()
            finally:
                remove_device = _RawInputDevice(0x01, 0x02, RIDEV_REMOVE, None)
                _user32.RegisterRawInputDevices(
                    ctypes.byref(remove_device), 1, ctypes.sizeof(_RawInputDevice)
                )
                self._hwnd = None
                if registered:
                    _user32.UnregisterClassW(self._class_name, instance)

        def _window_proc(
            self,
            hwnd: int,
            message: int,
            w_param: int,
            l_param: int,
        ) -> int:
            if message == WM_INPUT:
                self._process_raw_input(l_param)
            elif message == WM_CLOSE:
                _user32.DestroyWindow(hwnd)
                return 0
            elif message == WM_DESTROY:
                _user32.PostQuitMessage(0)
                return 0
            return _user32.DefWindowProcW(hwnd, message, w_param, l_param)

        def _process_raw_input(self, raw_input_handle: int) -> None:
            size = wintypes.UINT(0)
            header_size = ctypes.sizeof(_RawInputHeader)
            result = _user32.GetRawInputData(
                raw_input_handle,
                RID_INPUT,
                None,
                ctypes.byref(size),
                header_size,
            )
            if result == 0xFFFFFFFF or size.value < header_size:
                return
            buffer = ctypes.create_string_buffer(size.value)
            result = _user32.GetRawInputData(
                raw_input_handle,
                RID_INPUT,
                buffer,
                ctypes.byref(size),
                header_size,
            )
            if result == 0xFFFFFFFF or result < header_size + ctypes.sizeof(_RawMouse):
                return
            header = _RawInputHeader.from_buffer_copy(buffer)
            if header.dwType != RIM_TYPEMOUSE:
                return
            raw_mouse = _RawMouse.from_buffer_copy(buffer, header_size)
            if raw_mouse.usFlags & MOUSE_MOVE_ABSOLUTE:
                return
            dx = int(raw_mouse.lLastX)
            dy = int(raw_mouse.lLastY)
            if dx == 0 and dy == 0:
                return
            point = wintypes.POINT()
            if not _user32.GetCursorPos(ctypes.byref(point)):
                return
            try:
                self._callback(dx, dy, int(point.x), int(point.y))
            except Exception:
                pass


    def send_relative_mouse(dx: int, dy: int) -> None:
        """Inject one relative mouse movement through Windows ``SendInput``."""
        input_event = _Input(
            INPUT_MOUSE,
            _InputUnion(
                mouse=_MouseInput(int(dx), int(dy), 0, MOUSEEVENTF_MOVE, 0, 0)
            ),
        )
        sent = _user32.SendInput(1, ctypes.byref(input_event), ctypes.sizeof(_Input))
        if sent != 1:
            raise ctypes.WinError(ctypes.get_last_error())


else:

    class RawMouseListener:
        def __init__(self, callback: RawMotionCallback) -> None:
            self._callback = callback

        def start(self) -> None:
            raise OSError("Windows Raw Input is unavailable on this operating system.")

        def stop(self) -> None:
            return


    def send_relative_mouse(dx: int, dy: int) -> None:
        raise OSError("Relative SendInput mouse playback is only available on Windows.")
