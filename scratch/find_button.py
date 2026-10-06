import ctypes, os, subprocess, time
from ctypes import wintypes
user32 = ctypes.windll.user32

exe_path = os.path.abspath('App/ECG Data Management.exe')
p = subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
time.sleep(3)

main_hwnd = None
def find_w(h, l):
    global main_hwnd
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value == p.pid:
        c = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, c, 256)
        if 'Qt' in c.value and user32.IsWindowVisible(h):
            main_hwnd = h
            return False
    return True

user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(find_w), 0)
print('Main HWND:', main_hwnd)

rect = wintypes.RECT()
user32.GetWindowRect(main_hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top

print(f'Main rect: ({rect.left}, {rect.top}) size: {w}x{h}')

# Test clicks across the top toolbar
# Buttons are roughly between X = 600 and 850 in a 1000px window
for test_x_ratio in [0.66, 0.68, 0.70, 0.72, 0.74, 0.76]:
    cx = rect.left + int(w * test_x_ratio)
    cy = rect.top + 30
    user32.SetForegroundWindow(main_hwnd)
    user32.SetCursorPos(cx, cy)
    time.sleep(0.05)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(4, 0, 0, 0, 0)
    time.sleep(0.5)

    # Check if a dialog appeared
    dialogs = []
    def check_dlg(h, l):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == p.pid and h != main_hwnd:
            c = ctypes.create_unicode_buffer(256)
            t = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, c, 256)
            user32.GetWindowTextW(h, t, 256)
            if user32.IsWindowVisible(h) and 'Qt' in c.value:
                dialogs.append((h, c.value, t.value))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(check_dlg), 0)
    if dialogs:
        print(f'Found dialog at ratio {test_x_ratio} (x={cx}, y={cy}):', dialogs)
        # Close dialog
        for dh, _, _ in dialogs:
            user32.PostMessageW(dh, 0x0010, 0, 0) # WM_CLOSE
        break

p.terminate()
