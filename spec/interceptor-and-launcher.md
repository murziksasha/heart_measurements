# Launcher & Interceptor Specification

Component: `AI-ECG Portable.exe` / `Program.cs`  
Target Runtime: .NET Framework 4.0 / C# 5  
Subsystem: `IMAGE_SUBSYSTEM_WINDOWS_GUI (2)`

## 1. Process Lifecycle & Environment Isolation

### 1.1 Single-Instance Mutex
- Mutex Name: `AI_ECG_Analysis_Portable_SingleInstance_Mutex`
- Behavior: Aborts startup with an error dialog if another portable instance is running.
- Conflict Prevention: Checks `Process.GetProcessesByName("ECG Data Management")`. If already active, prompts user to close it before portable launcher execution.

### 1.2 Storage Isolation
- Host profile directory: `%LOCALAPPDATA%\ECG Browser`
- Temporary backup directory: `%TEMP%\ECG_Browser_HostBackup_{GUID}`
- Startup:
  1. If host `%LOCALAPPDATA%\ECG Browser` exists, moves/copies it to temporary backup directory.
  2. Copies portable `Data/` contents into `%LOCALAPPDATA%\ECG Browser`.
  3. Updates `config.ini` setting `DataDir=` to normalized path (`Path.Combine(hostEcgBrowserDir, "DATA").Replace('\\', '/')`).
- Shutdown:
  1. Copies host `%LOCALAPPDATA%\ECG Browser` contents back into portable `Data/`.
  2. Safely deletes temporary host `%LOCALAPPDATA%\ECG Browser`.
  3. Restores original host profile from backup directory.

---

## 2. Unified Interceptor Thread Architecture

### 2.1 Thread & DPI Context
- Dedicated background thread with active Win32 message pump (`GetMessage`, `TranslateMessage`, `DispatchMessage`).
- Uses `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE` (`IntPtr(-3)`) when querying window bounds (`GetWindowRectDpiAware`) and calculating sidebar metrics to prevent high-DPI coordinate distortion.

### 2.2 Main Window Detection
- Enumerates windows matching target process PID with Qt window class (`sbClass.Contains("Qt")`).
- Identified when: `owner == IntPtr.Zero && width >= 600 && height >= 400 && IsWindowVisible(hwnd)`.
- Stored globally in `s_mainHwnd`.

### 2.3 Show-Event Hook (`EVENT_OBJECT_SHOW`)
- Uses `SetWinEventHook` with `EVENT_OBJECT_SHOW` and `WINEVENT_OUTOFCONTEXT`.
- Main Window: If `s_mainHwnd == IntPtr.Zero` and window is ownerless with `w >= 600 && h >= 400`, sets `s_mainHwnd` and triggers sidebar button attachment.
- Popups: Once `s_mainHwnd` is set, **all other Qt windows** (`hwnd != s_mainHwnd`) belonging to target process are evaluated via `TryInterceptDownloadDialog`, **including ownerless windows**.
- Ignored Windows: Ignores `s_allowedDeviceHwnd` (the native dialog revealed after choosing **Import from device**).

### 2.4 Download Dialog Interception (`TryInterceptDownloadDialog`)
- **Matching Criteria:**
  1. Window title contains `"Download"` or `"Import"` (case-insensitive).
  2. OR window dimensions match known scaled download dialog bands (tolerance ±56 px):
     - **100% DPI:** `387 × 273`
     - **125% DPI:** `484 × 341`
     - **Screenshot Measured:** `484 × 335`
     - **150% DPI:** `581 × 410`
     - **175% DPI:** `677 × 478`
     - **200% DPI:** `774 × 546`
  3. OR window dimensions match small no-device dialogs (tolerance ±40 px):
     - `265 × 142`
     - `265 × 157`
- **Execution Actions:**
  - Guards against re-entrancy via `lock (s_importLock)` and `s_isImportModalRunning`.
  - Hides intercepted window immediately via `ShowWindow(hwnd, SW_HIDE)`.
  - Offloads modal execution to background ThreadPool calling `RunImportModal`.
- **Delayed Recheck:**
  - If show-event does not match initially, queues `RecheckDownloadDialog` after 150 ms to catch late title/dimension updates from Qt layout engines.

### 2.5 Periodic Timer Scanning (200 ms)
- Timer installed via Win32 `SetTimer(IntPtr.Zero, (IntPtr)1, 200, IntPtr.Zero)`.
- Actions on `WM_TIMER`:
  1. Repositions sidebar `+ Add User` button via `PlaceAddUserButton()`.
  2. If `!s_isImportModalRunning && s_mainHwnd != IntPtr.Zero`, invokes `ScanForDownloadDialog()`:
     - Calls `EnumWindows` to detect any visible Qt window from target process that bypassed `EVENT_OBJECT_SHOW`.
     - Skips `s_mainHwnd` and `s_allowedDeviceHwnd`.
     - Runs `TryInterceptDownloadDialog()`. If matched, stops window enumeration immediately.

---

## 3. Sidebar `+ Add User` Button Injection

### 3.1 Child Window Creation
- Class: `"BUTTON"`, Style: `WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON`, Parent: `s_mainHwnd`.
- Font: Segoe UI, 9pt bold (`CreateFont(-11, ..., 700, ..., "Segoe UI")`).
- Subclassed via `GWL_WNDPROC` for custom GDI painting:
  - Normal: `#e8f4fd` background, `#5ba0dc` border, `#2ea2f8` text.
  - Hover: `#d6eefd` background, `#1d8ce0` border, `#127fd4` text.
  - Pressed: `#2ea2f8` background, `#1d8ce0` border, `#ffffff` text.
  - Custom cursor: `IDC_HAND`.

### 3.2 Dynamic Layout Adjustment
- Scans client pixels at y=100 and y=132 via `GetPixel` to find patient list sidebar blue boundary (`FindSidebarRight`).
- Adapts text based on available width:
  - Width >= 82 px: `"+ Add User"`
  - Fits available width: `"+ Add"`
  - Narrow fallback: `"+"`
  - Width < 16 px: Hides button.

### 3.3 Low-Level Mouse Hook (`WH_MOUSE_LL`)
- Detects `WM_RBUTTONUP` on main window.
- Maps point to client coordinates using `ScreenToClient` with per-monitor DPI awareness.
- If clicked within "All Users" row bounds (`x in [16, sidebarRight]`, `y in [134, 168]`):
  - Displays Win32 popup menu (`TrackPopupMenuEx`) with `"+ Add User..."`.
  - On click, triggers `RunAddUserModal()`.

---

## 4. Subprocess Execution & Exit Codes

### 4.1 Import Modal Execution (`RunImportModal`)
- Launches: `pythonw.exe import_gui.py` (with no arguments).
- Fallback: Uses `python.exe` if `pythonw.exe` is not found.
- Handled Exit Codes:
  - **Code 0 (Cancel):** Closes intercepted native dialog with `WM_CLOSE`.
  - **Code 1 (Original Device Import):** Sets `s_allowedDeviceHwnd = dialogHwnd`, unhides native dialog (`ShowWindow(dialogHwnd, SW_SHOW)`), and brings it to foreground.
  - **Code 2 (Recordings Imported):** Closes native dialog, synchronizes host storage to portable `Data/`, sets `s_restartRequested = true`, and closes `s_mainHwnd` with `WM_CLOSE` to trigger a clean reload.
  - **Code -1 / Failure:** Closes native dialog with `WM_CLOSE`.

### 4.2 Add User Modal Execution (`RunAddUserModal`)
- Launches: `pythonw.exe manage_users.py --add-gui`.
- Handled Exit Codes:
  - **Code 2:** Patient added and refresh requested -> syncs database, sets `s_restartRequested = true`, and closes main window to reload.
  - **Code 3:** Patient added without reload request -> syncs database.

