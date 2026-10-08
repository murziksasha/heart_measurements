using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace AI_ECG_Portable
{
    static class Program
    {
        private const string MutexName = "AI_ECG_Analysis_Portable_SingleInstance_Mutex";

        #region Win32 API Definitions

        private delegate void WinEventDelegate(
            IntPtr hWinEventHook, uint eventType, IntPtr hwnd,
            int idObject, int idChild, uint dwEventThread, uint dwmsEventTime);

        private delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        private delegate IntPtr WndProcDelegate(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern IntPtr SetWinEventHook(
            uint eventMin, uint eventMax, IntPtr hmodWinEventProc,
            WinEventDelegate lpfnWinEventProc, uint idProcess, uint idThread, uint dwFlags);

        [DllImport("user32.dll")]
        private static extern bool UnhookWinEvent(IntPtr hWinEventHook);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

        [DllImport("user32.dll")]
        private static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern bool GetMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax);

        [DllImport("user32.dll")]
        private static extern bool PeekMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax, uint wRemoveMsg);

        [DllImport("user32.dll")]
        private static extern bool TranslateMessage([In] ref MSG lpMsg);

        [DllImport("user32.dll")]
        private static extern IntPtr DispatchMessage([In] ref MSG lpMsg);

        [DllImport("user32.dll")]
        private static extern bool PostThreadMessage(uint idThread, uint Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern IntPtr GetWindow(IntPtr hWnd, uint uCmd);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("user32.dll")]
        private static extern bool AllowSetForegroundWindow(int dwProcessId);

        [DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();

        [DllImport("kernel32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr GetModuleHandle(string lpModuleName);

        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr CreateWindowEx(
            uint dwExStyle, string lpClassName, string lpWindowName, uint dwStyle,
            int x, int y, int nWidth, int nHeight, IntPtr hWndParent,
            IntPtr hMenu, IntPtr hInstance, IntPtr lpParam);

        [DllImport("user32.dll")]
        private static extern IntPtr SetWindowLong(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

        [DllImport("user32.dll")]
        private static extern IntPtr CallWindowProc(IntPtr lpPrevWndFunc, IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern IntPtr CreatePopupMenu();

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern bool AppendMenu(IntPtr hMenu, uint uFlags, UIntPtr uIDNewItem, string lpNewItem);

        [DllImport("user32.dll")]
        private static extern int TrackPopupMenuEx(IntPtr hMenu, uint uFlags, int x, int y, IntPtr hWnd, IntPtr lpTPMParams);

        [DllImport("user32.dll")]
        private static extern bool DestroyMenu(IntPtr hMenu);

        [DllImport("gdi32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr CreateFont(
            int nHeight, int nWidth, int nEscapement, int nOrientation,
            int fnWeight, uint fdwItalic, uint fdwUnderline, uint fdwStrikeOut,
            uint fdwCharSet, uint fdwOutputPrecision, uint fdwClipPrecision,
            uint fdwQuality, uint fdwPitchAndFamily, string lpszFace);

        [DllImport("user32.dll")]
        private static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);

        [DllImport("user32.dll")]
        private static extern bool UnhookWindowsHookEx(IntPtr hhk);

        [DllImport("user32.dll")]
        private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);

        // DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE. The Qt window is per-monitor aware;
        // this launcher is not, so child coordinates get shifted unless the thread is switched.
        private static readonly IntPtr DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = new IntPtr(-3);

        [DllImport("user32.dll")]
        private static extern IntPtr SetThreadDpiAwarenessContext(IntPtr dpiContext);

        [DllImport("user32.dll")]
        private static extern IntPtr GetDC(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);

        [DllImport("gdi32.dll")]
        private static extern uint GetPixel(IntPtr hdc, int x, int y);

        [DllImport("gdi32.dll", CharSet = CharSet.Auto)]
        private static extern bool GetTextExtentPoint32(IntPtr hdc, string lpString, int c, out SIZE lpSize);

        [DllImport("user32.dll")]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll")]
        private static extern IntPtr SetTimer(IntPtr hWnd, IntPtr nIDEvent, uint uElapse, IntPtr lpTimerFunc);

        [StructLayout(LayoutKind.Sequential)]
        private struct SIZE
        {
            public int cx;
            public int cy;
        }

        [DllImport("user32.dll")]
        private static extern bool ScreenToClient(IntPtr hWnd, ref POINT lpPoint);

        [DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern bool IsWindow(IntPtr hWnd);

        [StructLayout(LayoutKind.Sequential)]
        private struct PAINTSTRUCT
        {
            public IntPtr hdc;
            public bool fErase;
            public RECT rcPaint;
            public bool fRestore;
            public bool fIncUpdate;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 32)]
            public byte[] rgbReserved;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct TRACKMOUSEEVENT
        {
            public uint cbSize;
            public uint dwFlags;
            public IntPtr hwndTrack;
            public uint dwHoverTime;
        }

        [DllImport("user32.dll")]
        private static extern IntPtr BeginPaint(IntPtr hWnd, out PAINTSTRUCT lpPaint);

        [DllImport("user32.dll")]
        private static extern bool EndPaint(IntPtr hWnd, ref PAINTSTRUCT lpPaint);

        [DllImport("user32.dll")]
        private static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("user32.dll")]
        private static extern int FillRect(IntPtr hDC, [In] ref RECT lprc, IntPtr hbr);

        [DllImport("user32.dll")]
        private static extern int FrameRect(IntPtr hDC, [In] ref RECT lprc, IntPtr hbr);

        [DllImport("user32.dll")]
        private static extern bool InvalidateRect(IntPtr hWnd, IntPtr lpRect, bool bErase);

        [DllImport("user32.dll")]
        private static extern IntPtr SetCapture(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern bool ReleaseCapture();

        [DllImport("user32.dll")]
        private static extern bool TrackMouseEvent(ref TRACKMOUSEEVENT lpEventTrack);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern int DrawText(IntPtr hDC, string lpchText, int nCount, ref RECT lpRect, uint uFormat);

        [DllImport("user32.dll")]
        private static extern IntPtr LoadCursor(IntPtr hInstance, int lpCursorName);

        [DllImport("user32.dll")]
        private static extern IntPtr SetCursor(IntPtr hCursor);

        [DllImport("gdi32.dll")]
        private static extern IntPtr CreateSolidBrush(uint crColor);

        [DllImport("gdi32.dll")]
        private static extern bool DeleteObject(IntPtr hObject);

        [DllImport("gdi32.dll")]
        private static extern int SetBkMode(IntPtr hdc, int iBkMode);

        [DllImport("gdi32.dll")]
        private static extern uint SetTextColor(IntPtr hdc, uint crColor);

        [DllImport("gdi32.dll")]
        private static extern IntPtr SelectObject(IntPtr hdc, IntPtr hgdiobj);

        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct POINT
        {
            public int x;
            public int y;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MSLLHOOKSTRUCT
        {
            public POINT pt;
            public uint mouseData;
            public uint flags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct MSG
        {
            public IntPtr hwnd;
            public uint message;
            public IntPtr wParam;
            public IntPtr lParam;
            public uint time;
            public int pt_x;
            public int pt_y;
        }

        private const uint EVENT_OBJECT_SHOW = 0x8002;
        private const uint WINEVENT_OUTOFCONTEXT = 0x0000;
        private const uint GW_OWNER = 4;
        private const int SW_HIDE = 0;
        private const int SW_SHOW = 5;
        private const uint WM_CLOSE = 0x0010;
        private const uint WM_QUIT = 0x0012;
        private const uint WM_TIMER = 0x0113;
        private const uint WM_APP_ATTACH = 0x8001;
        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint WM_PAINT = 0x000F;
        private const uint WM_ERASEBKGND = 0x0014;
        private const uint WM_SETCURSOR = 0x0020;
        private const uint WM_MOUSEMOVE = 0x0200;
        private const uint WM_MOUSELEAVE = 0x02A3;
        private const uint WM_LBUTTONDOWN = 0x0201;
        private const uint WM_LBUTTONUP = 0x0202;
        private const uint WM_RBUTTONUP = 0x0205;
        private const uint WM_SETFONT = 0x0030;
        private const int WH_MOUSE_LL = 14;
        private const int GWL_WNDPROC = -4;
        private const uint WS_CHILD = 0x40000000;
        private const uint WS_VISIBLE = 0x10000000;
        private const uint BS_PUSHBUTTON = 0x00000000;
        private const int ASFW_ANY = -1;
        private const int IDC_HAND = 32649;

        #endregion

        private static IntPtr s_mainHwnd = IntPtr.Zero;
        private static IntPtr s_allowedDeviceHwnd = IntPtr.Zero;
        private static bool s_isImportModalRunning = false;
        private static bool s_isAddUserModalRunning = false;
        private static bool s_restartRequested = false;

        private static IntPtr s_btnAddHwnd = IntPtr.Zero;
        private static int s_btnX = -1;
        private static int s_btnW = -1;
        private static int s_sidebarRight = 215;
        private static string s_btnText = "+ Add User";
        private static IntPtr s_origBtnWndProc = IntPtr.Zero;
        private static WndProcDelegate s_btnWndProc = null;
        private static bool s_isHovered = false;
        private static bool s_isPressed = false;
        private static IntPtr s_hBtnFont = IntPtr.Zero;

        private static IntPtr s_mouseHook = IntPtr.Zero;
        private static HookProc s_mouseHookProc = null;

        [STAThread]
        static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            bool createdNew;
            using (Mutex mutex = new Mutex(true, MutexName, out createdNew))
            {
                if (!createdNew)
                {
                    MessageBox.Show(
                        "An instance of AI-ECG Analysis System Portable is already running.",
                        "AI-ECG Portable",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information);
                    return;
                }

                if (Process.GetProcessesByName("ECG Data Management").Length > 0)
                {
                    MessageBox.Show(
                        "An instance of ECG Data Management is currently running on this computer.\nPlease close it before starting the portable edition.",
                        "AI-ECG Portable",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                    return;
                }

                string appDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                string exePath = Path.Combine(appDir, "App", "ECG Data Management.exe");
                string workingDir = Path.Combine(appDir, "App");
                string portableDataDir = Path.Combine(appDir, "Data");

                if (!File.Exists(exePath))
                {
                    MessageBox.Show(
                        "Cannot find 'App\\ECG Data Management.exe'.\nPlease ensure the portable folder is intact.",
                        "AI-ECG Portable - Error",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return;
                }

                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string hostEcgBrowserDir = Path.Combine(localAppData, "ECG Browser");
                string backupDir = Path.Combine(Path.GetTempPath(), "ECG_Browser_HostBackup_" + Guid.NewGuid().ToString("N"));
                bool hostExisted = false;

                if (Directory.Exists(hostEcgBrowserDir))
                {
                    try
                    {
                        Directory.Move(hostEcgBrowserDir, backupDir);
                        hostExisted = true;
                    }
                    catch
                    {
                        CopyDirectory(hostEcgBrowserDir, backupDir);
                        DeleteDirectorySafely(hostEcgBrowserDir);
                        hostExisted = true;
                    }
                }

                if (Directory.Exists(portableDataDir))
                {
                    CopyDirectory(portableDataDir, hostEcgBrowserDir);
                }
                else
                {
                    Directory.CreateDirectory(hostEcgBrowserDir);
                    Directory.CreateDirectory(Path.Combine(hostEcgBrowserDir, "DATA"));
                    Directory.CreateDirectory(Path.Combine(hostEcgBrowserDir, "DATA", "userfiles"));
                    Directory.CreateDirectory(Path.Combine(hostEcgBrowserDir, "log"));
                    Directory.CreateDirectory(Path.Combine(hostEcgBrowserDir, "dump"));
                }

                string hostConfigFile = Path.Combine(hostEcgBrowserDir, "config.ini");
                if (File.Exists(hostConfigFile))
                {
                    UpdateConfigDataDir(hostConfigFile, Path.Combine(hostEcgBrowserDir, "DATA").Replace('\\', '/'));
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = exePath;
                psi.WorkingDirectory = workingDir;
                psi.UseShellExecute = false;
                if (args.Length > 0)
                {
                    psi.Arguments = string.Join(" ", args);
                }

                try
                {
                    bool shouldRun = true;
                    while (shouldRun)
                    {
                        shouldRun = false;
                        s_mainHwnd = IntPtr.Zero;
                        s_btnAddHwnd = IntPtr.Zero;
                        s_btnX = -1;
                        s_btnW = -1;
                        s_sidebarRight = 215;
                        s_btnText = "+ Add User";

                        using (Process process = Process.Start(psi))
                        {
                            // Start Unified Interceptor Thread (Downloads + Sidebar + Hook)
                            Thread interceptorThread = StartUnifiedInterceptor(process, appDir, hostEcgBrowserDir, portableDataDir);

                            process.WaitForExit();

                            StopUnifiedInterceptor(interceptorThread);
                        }

                        if (Directory.Exists(hostEcgBrowserDir))
                        {
                            CopyDirectory(hostEcgBrowserDir, portableDataDir);
                        }

                        // Seamless reload if user creation requested immediate application refresh
                        if (s_restartRequested)
                        {
                            s_restartRequested = false;
                            shouldRun = true;
                            Thread.Sleep(300);
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show(
                        "An unexpected error occurred during execution:\n" + ex.Message,
                        "AI-ECG Portable - Notice",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                }
                finally
                {
                    if (Directory.Exists(hostEcgBrowserDir))
                    {
                        DeleteDirectorySafely(hostEcgBrowserDir);
                    }

                    if (hostExisted && Directory.Exists(backupDir))
                    {
                        if (!Directory.Exists(hostEcgBrowserDir))
                        {
                            Directory.Move(backupDir, hostEcgBrowserDir);
                        }
                        else
                        {
                            CopyDirectory(backupDir, hostEcgBrowserDir);
                            DeleteDirectorySafely(backupDir);
                        }
                    }
                }
            }
        }

        #region Unified Interceptor: Download Interception, Sidebar Button & Context Menu

        private static uint s_interceptorThreadId = 0;

        private static Thread StartUnifiedInterceptor(Process targetProcess, string appDir, string hostEcgBrowserDir, string portableDataDir)
        {
            Thread t = new Thread(() =>
            {
                s_interceptorThreadId = GetCurrentThreadId();
                MSG queueReady;
                PeekMessage(out queueReady, IntPtr.Zero, 0, 0, 0);

                LogInterceptor(appDir, string.Format("Unified interceptor started for PID {0}", targetProcess.Id));

                // 1. Proactive Main Window Watcher & Child Button Creator
                ThreadPool.QueueUserWorkItem(_ =>
                {
                    int attempts = 0;
                    while (s_mainHwnd == IntPtr.Zero && attempts < 200 && !targetProcess.HasExited)
                    {
                        s_mainHwnd = FindMainWindow(targetProcess.Id);
                        if (s_mainHwnd != IntPtr.Zero)
                        {
                            LogInterceptor(appDir, string.Format("Found MainWindow HWND: {0}", s_mainHwnd));
                            // Create the button on the interceptor thread. Its window procedure
                            // has to run there, or a later resize deadlocks SetWindowPos.
                            PostThreadMessage(s_interceptorThreadId, WM_APP_ATTACH, IntPtr.Zero, IntPtr.Zero);
                            break;
                        }
                        Thread.Sleep(50);
                        attempts++;
                    }
                });

                // 2. WinEvent Hook for download dialog interception
                WinEventDelegate proc = (IntPtr hWinEventHook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint dwEventThread, uint dwmsEventTime) =>
                {
                    if (idObject == 0 && hwnd != IntPtr.Zero)
                    {
                        StringBuilder sbClass = new StringBuilder(256);
                        GetClassName(hwnd, sbClass, 256);
                        string cls = sbClass.ToString();

                        if (cls.Contains("Qt"))
                        {
                            StringBuilder sbTitle = new StringBuilder(256);
                            GetWindowText(hwnd, sbTitle, 256);
                            string title = sbTitle.ToString();

                            IntPtr owner = GetWindow(hwnd, GW_OWNER);
                            RECT r;
                            GetWindowRect(hwnd, out r);
                            int w = r.Right - r.Left;
                            int h = r.Bottom - r.Top;

                            // Update main window reference if detected here
                            if (owner == IntPtr.Zero && w >= 600 && h >= 400)
                            {
                                if (s_mainHwnd == IntPtr.Zero)
                                {
                                    s_mainHwnd = hwnd;
                                    LogInterceptor(appDir, string.Format("EVENT_SHOW main window {0}", hwnd));
                                    AttachSidebarAddButton(targetProcess, appDir, hostEcgBrowserDir, portableDataDir);
                                }
                            }
                            else if (hwnd != s_mainHwnd)
                            {
                                if (hwnd == s_allowedDeviceHwnd)
                                {
                                    return;
                                }

                                // DeviceDownloadDialog check
                                bool isDownloadDialog = (w >= 370 && w <= 405 && h >= 255 && h <= 290) ||
                                                        title.IndexOf("Download", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                                        title.IndexOf("Import", StringComparison.OrdinalIgnoreCase) >= 0;

                                if (isDownloadDialog && !s_isImportModalRunning)
                                {
                                    s_isImportModalRunning = true;
                                    LogInterceptor(appDir, string.Format("Matched Download dialog {0}! Hiding and running modal...", hwnd));

                                    ShowWindow(hwnd, SW_HIDE);

                                    ThreadPool.QueueUserWorkItem(__ =>
                                    {
                                        try
                                        {
                                            RunImportModal(hwnd, targetProcess, appDir, hostEcgBrowserDir, portableDataDir);
                                        }
                                        finally
                                        {
                                            s_isImportModalRunning = false;
                                        }
                                    });
                                }
                            }
                        }
                    }
                };

                IntPtr hook = SetWinEventHook(
                    EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW,
                    IntPtr.Zero, proc,
                    (uint)targetProcess.Id, 0,
                    WINEVENT_OUTOFCONTEXT);

                // 3. Install Mouse Hook for Right-Click on "All Users"
                s_mouseHookProc = (int nCode, IntPtr wParam, IntPtr lParam) =>
                {
                    if (nCode >= 0 && (int)wParam == WM_RBUTTONUP && !s_isAddUserModalRunning && !s_isImportModalRunning)
                    {
                        if (s_mainHwnd != IntPtr.Zero && IsWindow(s_mainHwnd))
                        {
                            IntPtr fg = GetForegroundWindow();
                            if (fg == s_mainHwnd)
                            {
                                MSLLHOOKSTRUCT hs = (MSLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(MSLLHOOKSTRUCT));
                                POINT clientPt = hs.pt;

                                // All Users row, in the Qt window's own pixels. This hook's thread
                                // is otherwise DPI-unaware, which shifts the hit test on resize.
                                IntPtr previousDpi = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE);
                                ScreenToClient(s_mainHwnd, ref clientPt);
                                if (previousDpi != IntPtr.Zero)
                                {
                                    SetThreadDpiAwarenessContext(previousDpi);
                                }
                                int rowRight = s_sidebarRight > 40 ? s_sidebarRight : 215;
                                if (clientPt.x >= 16 && clientPt.x <= rowRight && clientPt.y >= 134 && clientPt.y <= 168)
                                {
                                    IntPtr hMenu = CreatePopupMenu();
                                    AppendMenu(hMenu, 0, (UIntPtr)101, "+ Add User...");
                                    SetForegroundWindow(s_mainHwnd);
                                    int cmd = TrackPopupMenuEx(hMenu, 0x0100 | 0x0002, hs.pt.x, hs.pt.y, s_mainHwnd, IntPtr.Zero);
                                    DestroyMenu(hMenu);

                                    if (cmd == 101)
                                    {
                                        ThreadPool.QueueUserWorkItem(__ =>
                                        {
                                            RunAddUserModal(targetProcess, appDir, hostEcgBrowserDir, portableDataDir);
                                        });
                                        return (IntPtr)1; // Consume event
                                    }
                                }
                            }
                        }
                    }
                    return CallNextHookEx(s_mouseHook, nCode, wParam, lParam);
                };

                s_mouseHook = SetWindowsHookEx(WH_MOUSE_LL, s_mouseHookProc, GetModuleHandle(null), 0);

                // 4. Message Pump for Hooks. The timer refits the button as the window is resized.
                SetTimer(IntPtr.Zero, (IntPtr)1, 200, IntPtr.Zero);
                MSG msg;
                while (GetMessage(out msg, IntPtr.Zero, 0, 0))
                {
                    if (msg.message == WM_QUIT) break;
                    if (msg.message == WM_APP_ATTACH)
                    {
                        AttachSidebarAddButton(targetProcess, appDir, hostEcgBrowserDir, portableDataDir);
                    }
                    if (msg.message == WM_TIMER)
                    {
                        PlaceAddUserButton();
                    }
                    TranslateMessage(ref msg);
                    DispatchMessage(ref msg);
                }

                if (s_mouseHook != IntPtr.Zero)
                {
                    UnhookWindowsHookEx(s_mouseHook);
                    s_mouseHook = IntPtr.Zero;
                }

                if (hook != IntPtr.Zero)
                {
                    UnhookWinEvent(hook);
                }
            });

            t.IsBackground = true;
            t.Start();
            return t;
        }

        private static void StopUnifiedInterceptor(Thread thread)
        {
            try
            {
                if (s_mouseHook != IntPtr.Zero)
                {
                    UnhookWindowsHookEx(s_mouseHook);
                    s_mouseHook = IntPtr.Zero;
                }
                if (s_interceptorThreadId != 0)
                {
                    PostThreadMessage(s_interceptorThreadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
                }
            }
            catch {}
        }

        private static IntPtr FindMainWindow(int targetPid)
        {
            IntPtr found = IntPtr.Zero;
            EnumWindows((hwnd, lParam) =>
            {
                uint pid;
                GetWindowThreadProcessId(hwnd, out pid);
                if (pid == (uint)targetPid)
                {
                    StringBuilder sbClass = new StringBuilder(256);
                    GetClassName(hwnd, sbClass, 256);
                    if (sbClass.ToString().Contains("Qt"))
                    {
                        IntPtr owner = GetWindow(hwnd, GW_OWNER);
                        RECT r;
                        GetWindowRect(hwnd, out r);
                        int w = r.Right - r.Left;
                        int h = r.Bottom - r.Top;
                        if (owner == IntPtr.Zero && w >= 600 && h >= 400 && IsWindowVisible(hwnd))
                        {
                            found = hwnd;
                            return false;
                        }
                    }
                }
                return true;
            }, IntPtr.Zero);
            return found;
        }

        private static void AttachSidebarAddButton(Process targetProcess, string appDir, string hostEcgBrowserDir, string portableDataDir)
        {
            if (s_mainHwnd == IntPtr.Zero || !IsWindow(s_mainHwnd) || s_btnAddHwnd != IntPtr.Zero) return;

            try
            {
                // Physical client pixels of the Qt window: the "User" label is
                // y=110..125 and the All Users bar starts at y=137. A 24px button
                // centered on that label sits at y=106 and clears the list.
                // The label ends near x=88, so x=96 leaves a gap before the button.
                IntPtr previousDpi = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE);
                s_btnAddHwnd = CreateWindowEx(
                    0,
                    "BUTTON",
                    "+ Add User",
                    WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                    96, 106, 82, 24,
                    s_mainHwnd,
                    (IntPtr)9001,
                    GetModuleHandle(null),
                    IntPtr.Zero
                );
                if (previousDpi != IntPtr.Zero)
                {
                    SetThreadDpiAwarenessContext(previousDpi);
                }

                if (s_btnAddHwnd != IntPtr.Zero)
                {
                    // Create Segoe UI 9pt bold font
                    if (s_hBtnFont == IntPtr.Zero)
                    {
                        s_hBtnFont = CreateFont(
                            -11, 0, 0, 0, 700, 0, 0, 0,
                            1, 0, 0, 0, 0, "Segoe UI");
                    }
                    SendMessage(s_btnAddHwnd, WM_SETFONT, s_hBtnFont, (IntPtr)1);

                    // Subclass button for custom GDI paint (matching Picture 1: #e8f4fd bg, subtle border, blue text)
                    // and shield Qt from receiving mouse click activation events.
                    s_btnWndProc = (IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam) =>
                    {
                        if (msg == WM_PAINT)
                        {
                            PAINTSTRUCT ps;
                            IntPtr hdc = BeginPaint(hWnd, out ps);
                            RECT rc;
                            GetClientRect(hWnd, out rc);

                            // Background:
                            // Normal: #e8f4fd (0x00FDF4E8)
                            // Hover:  #d6eefd (0x00FDEED6)
                            // Pressed: #2ea2f8 (0x00F8A22E)
                            uint bgCol = s_isPressed ? 0x00F8A22Eu : (s_isHovered ? 0x00FDEED6u : 0x00FDF4E8u);
                            IntPtr hBrushBg = CreateSolidBrush(bgCol);
                            FillRect(hdc, ref rc, hBrushBg);
                            DeleteObject(hBrushBg);

                            // 1px Border (matches Picture 1):
                            // Normal: #5ba0dc (0x00DCA05B)
                            // Hover/Pressed: #1d8ce0 (0x00E08C1D)
                            uint borderCol = (s_isPressed || s_isHovered) ? 0x00E08C1Du : 0x00DCA05Bu;
                            IntPtr hBrushBorder = CreateSolidBrush(borderCol);
                            FrameRect(hdc, ref rc, hBrushBorder);
                            DeleteObject(hBrushBorder);

                            // Text:
                            // Normal: #2ea2f8 (0x00F8A22E)
                            // Hover:  #127fd4 (0x00D47F12)
                            // Pressed: #ffffff (0x00FFFFFF)
                            SetBkMode(hdc, 1); // TRANSPARENT
                            uint textCol = s_isPressed ? 0x00FFFFFFu : (s_isHovered ? 0x00D47F12u : 0x00F8A22Eu);
                            SetTextColor(hdc, textCol);
                            IntPtr hOldFont = SelectObject(hdc, s_hBtnFont);
                            DrawText(hdc, s_btnText, -1, ref rc, 0x00000001 | 0x00000004 | 0x00000020);
                            SelectObject(hdc, hOldFont);

                            EndPaint(hWnd, ref ps);
                            return IntPtr.Zero;
                        }
                        else if (msg == WM_ERASEBKGND)
                        {
                            return (IntPtr)1;
                        }
                        else if (msg == WM_SETCURSOR)
                        {
                            SetCursor(LoadCursor(IntPtr.Zero, IDC_HAND));
                            return (IntPtr)1;
                        }
                        else if (msg == WM_MOUSEMOVE)
                        {
                            if (!s_isHovered)
                            {
                                s_isHovered = true;
                                TRACKMOUSEEVENT tme = new TRACKMOUSEEVENT();
                                tme.cbSize = (uint)Marshal.SizeOf(typeof(TRACKMOUSEEVENT));
                                tme.dwFlags = 2; // TME_LEAVE
                                tme.hwndTrack = hWnd;
                                TrackMouseEvent(ref tme);
                                InvalidateRect(hWnd, IntPtr.Zero, false);
                            }
                            return IntPtr.Zero;
                        }
                        else if (msg == WM_MOUSELEAVE)
                        {
                            s_isHovered = false;
                            s_isPressed = false;
                            InvalidateRect(hWnd, IntPtr.Zero, false);
                            return IntPtr.Zero;
                        }
                        else if (msg == WM_LBUTTONDOWN)
                        {
                            s_isPressed = true;
                            SetCapture(hWnd);
                            InvalidateRect(hWnd, IntPtr.Zero, false);
                            return IntPtr.Zero;
                        }
                        else if (msg == WM_LBUTTONUP)
                        {
                            bool wasPressed = s_isPressed;
                            s_isPressed = false;
                            ReleaseCapture();
                            InvalidateRect(hWnd, IntPtr.Zero, false);

                            if (wasPressed)
                            {
                                RECT rc;
                                GetClientRect(hWnd, out rc);
                                int x = (short)(lParam.ToInt32() & 0xFFFF);
                                int y = (short)((lParam.ToInt32() >> 16) & 0xFFFF);
                                if (x >= 0 && x <= rc.Right && y >= 0 && y <= rc.Bottom)
                                {
                                    ThreadPool.QueueUserWorkItem(_ =>
                                    {
                                        RunAddUserModal(targetProcess, appDir, hostEcgBrowserDir, portableDataDir);
                                    });
                                }
                            }
                            return IntPtr.Zero;
                        }

                        return CallWindowProc(s_origBtnWndProc, hWnd, msg, wParam, lParam);
                    };

                    s_origBtnWndProc = SetWindowLong(s_btnAddHwnd, GWL_WNDPROC, Marshal.GetFunctionPointerForDelegate(s_btnWndProc));
                    PlaceAddUserButton();

                    LogInterceptor(appDir, string.Format("Child + Add User button created successfully at ({0}, 106) on {1}", s_btnX, s_mainHwnd));
                }
            }
            catch (Exception ex)
            {
                LogInterceptor(appDir, string.Format("Error attaching child button: {0}", ex.Message));
            }
        }

        // Keep the button on the User header and inside the patient list.
        // The list gets narrower when the window does; a fixed 82px button then covers Data ID.
        private static void PlaceAddUserButton()
        {
            if (s_btnAddHwnd == IntPtr.Zero || s_mainHwnd == IntPtr.Zero) return;
            if (!IsWindow(s_btnAddHwnd) || !IsWindow(s_mainHwnd)) return;

            IntPtr previousDpi = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE);
            try
            {
                int edge = FindSidebarRight(s_mainHwnd);
                if (edge < 80)
                {
                    // Patient list is collapsed or too narrow to host the button.
                    // Leaving it at the old spot covers the Data ID column.
                    if (IsWindowVisible(s_btnAddHwnd))
                    {
                        ShowWindow(s_btnAddHwnd, SW_HIDE);
                    }
                    s_btnX = -1;
                    if (edge > 40) s_sidebarRight = edge;
                    return;
                }
                s_sidebarRight = edge;

                // Full label sits at x=96 and is 82px. A narrower list would run that
                // into the Data ID column, so shorten the label to what still fits.
                int maxRight = edge - 4;
                int x = 96;
                int available = maxRight - x;
                if (available < 36)
                {
                    x = 90;
                    available = maxRight - x;
                }
                if (available < 16)
                {
                    if (IsWindowVisible(s_btnAddHwnd))
                    {
                        ShowWindow(s_btnAddHwnd, SW_HIDE);
                    }
                    s_btnX = -1;
                    return;
                }

                int width;
                string text;
                if (available >= 82)
                {
                    width = 82;
                    text = "+ Add User";
                }
                else
                {
                    text = FitAddButtonText(available, out width);
                }
                if (x == s_btnX && width == s_btnW && text == s_btnText && IsWindowVisible(s_btnAddHwnd))
                {
                    return;
                }

                s_btnX = x;
                s_btnW = width;
                s_btnText = text;
                SetWindowPos(s_btnAddHwnd, IntPtr.Zero, x, 106, width, 24, SWP_NOACTIVATE);
                if (!IsWindowVisible(s_btnAddHwnd))
                {
                    ShowWindow(s_btnAddHwnd, SW_SHOW);
                }
                InvalidateRect(s_btnAddHwnd, IntPtr.Zero, false);
            }
            finally
            {
                if (previousDpi != IntPtr.Zero)
                {
                    SetThreadDpiAwarenessContext(previousDpi);
                }
            }
        }

        private static string FitAddButtonText(int available, out int width)
        {
            string[] choices = { "+ Add User", "+ Add", "+" };
            IntPtr hdc = GetDC(s_btnAddHwnd);
            IntPtr old = IntPtr.Zero;
            if (s_hBtnFont != IntPtr.Zero && hdc != IntPtr.Zero)
            {
                old = SelectObject(hdc, s_hBtnFont);
            }
            try
            {
                foreach (string choice in choices)
                {
                    int textWidth = choice.Length * 8;
                    SIZE size;
                    if (hdc != IntPtr.Zero && GetTextExtentPoint32(hdc, choice, choice.Length, out size))
                    {
                        textWidth = size.cx;
                    }
                    int needed = textWidth + 6;
                    if (needed <= available)
                    {
                        width = needed;
                        return choice;
                    }
                }
            }
            finally
            {
                if (old != IntPtr.Zero)
                {
                    SelectObject(hdc, old);
                }
                if (hdc != IntPtr.Zero)
                {
                    ReleaseDC(s_btnAddHwnd, hdc);
                }
            }

            width = available;
            return "+";
        }

        // Right edge of the light-blue patient list, in the Qt window's client pixels.
        private static int FindSidebarRight(IntPtr hwnd)
        {
            RECT client;
            if (!GetClientRect(hwnd, out client) || client.Right < 100 || client.Bottom < 120)
            {
                return -1;
            }

            IntPtr hdc = GetDC(hwnd);
            if (hdc == IntPtr.Zero) return -1;
            try
            {
                int limit = Math.Min(client.Right, 700);
                int[] rows = new int[] { 100, 132 };
                int best = -1;
                foreach (int y in rows)
                {
                    if (y >= client.Bottom) continue;
                    int start = -1;
                    int end = -1;
                    int gap = 0;
                    for (int x = 0; x < limit; x++)
                    {
                        uint color = GetPixel(hdc, x, y);
                        if (color == 0xFFFFFFFFu) continue;
                        if (IsSidebarBlue(color))
                        {
                            if (start < 0) start = x;
                            end = x;
                            gap = 0;
                        }
                        else if (start >= 0)
                        {
                            gap++;
                            if (gap > 4)
                            {
                                if (end - start > 50) break;
                                start = -1;
                                end = -1;
                                gap = 0;
                            }
                        }
                    }
                    // The shorter edge wins, so a light-blue control in the table cannot pull the button over Data ID.
                    if (start >= 0 && start < 80 && end - start > 50 && (best < 0 || end < best))
                    {
                        best = end;
                    }
                }
                return best;
            }
            finally
            {
                ReleaseDC(hwnd, hdc);
            }
        }

        private static bool IsSidebarBlue(uint color)
        {
            int r = (int)(color & 0xFF);
            int g = (int)((color >> 8) & 0xFF);
            int b = (int)((color >> 16) & 0xFF);
            return r >= 210 && r <= 242 && g >= 228 && g <= 252 && b >= 246 && b > r + 8;
        }

        private static void RunAddUserModal(Process targetProcess, string appDir, string hostEcgBrowserDir, string portableDataDir)
        {
            if (s_isAddUserModalRunning) return;
            s_isAddUserModalRunning = true;

            try
            {
                string pythonExe = ResolvePythonExecutable();
                string scriptPath = Path.Combine(appDir, "manage_users.py");

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonExe;
                psi.Arguments = "\"" + scriptPath + "\" --add-gui";
                psi.WorkingDirectory = appDir;
                psi.UseShellExecute = false;

                LogInterceptor(appDir, string.Format("RunAddUserModal launching: {0}", psi.Arguments));

                AllowSetForegroundWindow(ASFW_ANY);
                int exitCode = 0;
                using (Process p = Process.Start(psi))
                {
                    p.WaitForExit();
                    exitCode = p.ExitCode;
                }

                LogInterceptor(appDir, string.Format("RunAddUserModal exitCode: {0}", exitCode));

                if (exitCode == 2 || exitCode == 3)
                {
                    // User was created: sync databases
                    try
                    {
                        if (Directory.Exists(hostEcgBrowserDir))
                        {
                            CopyDirectory(hostEcgBrowserDir, portableDataDir);
                        }
                    }
                    catch {}

                    if (exitCode == 2)
                    {
                        // Refresh requested: signal restart and close current process
                        s_restartRequested = true;
                        if (s_mainHwnd != IntPtr.Zero)
                        {
                            PostMessage(s_mainHwnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogInterceptor(appDir, string.Format("RunAddUserModal exception: {0}", ex.Message));
            }
            finally
            {
                s_isAddUserModalRunning = false;
            }
        }

        private static void RunImportModal(IntPtr dialogHwnd, Process targetProcess, string appDir, string hostEcgBrowserDir, string portableDataDir)
        {
            string pythonExe = ResolvePythonExecutable();
            string scriptPath = Path.Combine(appDir, "import_gui.py");

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonExe;
            psi.Arguments = "\"" + scriptPath + "\"";
            psi.WorkingDirectory = appDir;
            psi.UseShellExecute = false;

            LogInterceptor(appDir, string.Format("RunImportModal starting: exe={0}, args={1}", pythonExe, psi.Arguments));

            int exitCode = 0;
            try
            {
                AllowSetForegroundWindow(ASFW_ANY);
                using (Process guiProc = Process.Start(psi))
                {
                    guiProc.WaitForExit();
                    exitCode = guiProc.ExitCode;
                }
            }
            catch (Exception ex)
            {
                LogInterceptor(appDir, string.Format("RunImportModal exception: {0}", ex.Message));
                exitCode = 1;
            }

            LogInterceptor(appDir, string.Format("RunImportModal finished with exitCode {0}", exitCode));

            if (exitCode == 1)
            {
                // "From Device" -> unhide native dialog
                s_allowedDeviceHwnd = dialogHwnd;
                ShowWindow(dialogHwnd, SW_SHOW);
                SetForegroundWindow(dialogHwnd);
            }
            else
            {
                // "From Folder" (2) or Cancelled (0) -> close native dialog
                PostMessage(dialogHwnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);

                if (exitCode == 2)
                {
                    // Sync newly imported files to portable storage, then restart
                    // the Qt window so the patient list reloads. A fake click in the
                    // sidebar misses when the window is scaled or scrolled.
                    try
                    {
                        if (Directory.Exists(hostEcgBrowserDir))
                        {
                            CopyDirectory(hostEcgBrowserDir, portableDataDir);
                        }
                    }
                    catch {}

                    s_restartRequested = true;
                    IntPtr mainHwnd = s_mainHwnd != IntPtr.Zero ? s_mainHwnd : targetProcess.MainWindowHandle;
                    if (mainHwnd != IntPtr.Zero && IsWindow(mainHwnd))
                    {
                        PostMessage(mainHwnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
                    }
                }
            }
        }

        #endregion

        private static void LogInterceptor(string appDir, string message)
        {
            try
            {
                string logDir = Path.Combine(appDir, "Data", "log");
                Directory.CreateDirectory(logDir);
                string logFile = Path.Combine(logDir, "interceptor.log");
                File.AppendAllText(logFile, string.Format("[{0:yyyy-MM-dd HH:mm:ss.fff}] {1}\r\n", DateTime.Now, message));
            }
            catch {}
        }

        private static string ResolvePythonExecutable()
        {
            string pythonw = @"C:\Python312\pythonw.exe";
            if (File.Exists(pythonw)) return pythonw;

            string python = @"C:\Python312\python.exe";
            if (File.Exists(python)) return python;

            return "pythonw.exe";
        }

        private static void UpdateConfigDataDir(string configPath, string normalizedDataDirPath)
        {
            try
            {
                string[] lines = File.ReadAllLines(configPath);
                bool found = false;
                for (int i = 0; i < lines.Length; i++)
                {
                    if (lines[i].StartsWith("DataDir=", StringComparison.OrdinalIgnoreCase))
                    {
                        lines[i] = "DataDir=" + normalizedDataDirPath;
                        found = true;
                        break;
                    }
                }

                if (!found)
                {
                    Array.Resize(ref lines, lines.Length + 1);
                    lines[lines.Length - 1] = "DataDir=" + normalizedDataDirPath;
                }

                File.WriteAllLines(configPath, lines);
            }
            catch {}
        }

        private static void CopyDirectory(string sourceDir, string targetDir)
        {
            Directory.CreateDirectory(targetDir);

            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string dest = Path.Combine(targetDir, Path.GetFileName(file));
                File.Copy(file, dest, true);
            }

            foreach (string dir in Directory.GetDirectories(sourceDir))
            {
                string dest = Path.Combine(targetDir, Path.GetFileName(dir));
                CopyDirectory(dir, dest);
            }
        }

        private static void DeleteDirectorySafely(string targetDir)
        {
            if (!Directory.Exists(targetDir)) return;

            for (int i = 0; i < 10; i++)
            {
                try
                {
                    Directory.Delete(targetDir, true);
                    return;
                }
                catch
                {
                    Thread.Sleep(200);
                }
            }
        }
    }
}
