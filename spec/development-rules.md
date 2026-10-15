# Development & Engineering Rules

Operational and architectural rules for maintaining and extending the AI-ECG Analysis Portable codebase.

## 1. Build & Compilation Rules

### 1.1 C# Launcher Build Command
```cmd
C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /target:winexe /r:System.Windows.Forms.dll /out:"AI-ECG Portable.exe" Program.cs
```
- **Target Language:** C# 5.0 (.NET Framework 4.0/4.8). Avoid C# 6+ features (e.g. string interpolation `$"{x}"`, expression-bodied members `=>`, null-conditional operator `?.`).
- **Target Subsystem:** Must be built with `/target:winexe` (`IMAGE_SUBSYSTEM_WINDOWS_GUI = 2`) to ensure no command prompt console window appears when launched.
- **Verification:** Confirm subsystem via PE optional header offset 68 (`Subsystem == 2`).

---

## 2. Python Environment & Script Execution

### 2.1 Python Resolution Hierarchy
All launchers (`Program.cs`, batch files) resolve Python in the following order:
1. `C:\Python312\pythonw.exe`
2. `C:\Python312\python.exe`
3. System `PATH` `pythonw.exe` / `python.exe`

### 2.2 Encoding Rules
- All Python source files, Markdown documents, batch scripts, and text files must strictly use **UTF-8** encoding.
- Do not emit UTF-16, BOMs, or ANSI-encoded files.

### 2.3 Windows CRLF Safety
- On Windows environments, atomic writes (`write_to_file`) are preferred over chained partial-line edits on large files to prevent line duplication and CRLF corruption.

---

## 3. Interceptor Integrity & Safety Rules

1. **No Accidental Vendor Dialog Exposure:**
   - Exit code `0` (Cancel) and exit code `-1` (Crash/Exception) must always close the vendor dialog with Win32 `WM_CLOSE`.
   - **Exit code `1`** (explicit click on "Import from device" or "Original device import") is the **only** code that unhides the vendor dialog (`ShowWindow(SW_SHOW)`).
2. **DPI-Aware Coordinate Reading:**
   - Any Win32 API measuring the Qt application (`GetWindowRect`, `ScreenToClient`) must be wrapped with `SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE)`.
3. **No Double-Launch / Concurrency Lock:**
   - All modal launches must synchronize on `s_importLock` and `s_isImportModalRunning` to guarantee only one chooser or folder import modal is active at any time.
4. **Ownerless Window Handling:**
   - Once `s_mainHwnd` is identified, all subsequent Qt windows belonging to the target process must be evaluated through `TryInterceptDownloadDialog`, regardless of whether `GW_OWNER` is null.

---

## 4. Testing & Verification Requirements

### 4.1 Running Test Suites
```powershell
python -m unittest discover tests
python -m unittest tests.test_import_gui
```
- Co-locate tests under `tests/test_*.py`.
- Mock external GUI mainloops (`tkinter.Tk.mainloop`) and OS subprocess calls to keep tests headless and deterministic.

### 4.2 Non-Destructive Testing
- Never start `AI-ECG Portable.exe` or `App/ECG Data Management.exe` against the user's active host profile during automated test runs.
- Verify assembly compilation, PE headers, and test coverage programmatically.

