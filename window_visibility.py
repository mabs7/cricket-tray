"""Restore the portable bar without taking focus from the user's application."""
import ctypes
import sys
from ctypes import wintypes

def monitor_work_area(x, y, screen_w, screen_h):
    """Return (left, top, right, bottom) of the monitor work area containing (x, y)."""
    if sys.platform != "win32":
        return 0, 0, screen_w, screen_h
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = wintypes.HMONITOR
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        monitor = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)  # MONITOR_DEFAULTTONEAREST
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, screen_w, screen_h

def ensure_bar_visible(root, hidden, topmost):
    if hidden:
        return
    if sys.platform != "win32":
        if root.state() in {"withdrawn", "iconic"}:
            root.deiconify()
        if topmost:
            root.attributes("-topmost", True)
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    handle = user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT, Tk's wrapper HWND
    if not handle:
        return
    if not user32.IsWindowVisible(handle) or user32.IsIconic(handle):
        user32.ShowWindow(handle, 4)  # SW_SHOWNOACTIVATE
    if topmost:
        # NOSIZE | NOMOVE | NOACTIVATE | SHOWWINDOW; never SetForegroundWindow.
        if not user32.SetWindowPos(handle, wintypes.HWND(-1), 0, 0, 0, 0, 0x0053):
            err = ctypes.get_last_error()
            if err != 5:  # Expected ERROR_ACCESS_DENIED on locked/secure Windows desktops.
                raise ctypes.WinError(err)

