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

        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
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
        private const uint WM_LBUTTONDOWN = 0x0201;
        private const uint WM_LBUTTONUP = 0x0202;
        private const int ASFW_ANY = -1;

        #endregion

        private static IntPtr s_mainHwnd = IntPtr.Zero;
        private static IntPtr s_allowedDeviceHwnd = IntPtr.Zero;
        private static bool s_isImportModalRunning = false;

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
                    using (Process process = Process.Start(psi))
                    {
                        // Start our Import Button Interceptor
                        Thread interceptorThread = StartImportInterceptor(process, appDir, hostEcgBrowserDir, portableDataDir);

                        process.WaitForExit();

                        // Stop interceptor thread when main app exits
                        StopImportInterceptor(interceptorThread);
                    }

                    if (Directory.Exists(hostEcgBrowserDir))
                    {
                        CopyDirectory(hostEcgBrowserDir, portableDataDir);
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

        #region Import Interceptor Mechanism

        private static uint s_interceptorThreadId = 0;

        private static Thread StartImportInterceptor(Process targetProcess, string appDir, string hostEcgBrowserDir, string portableDataDir)
        {
            Thread t = new Thread(() =>
            {
                s_interceptorThreadId = GetCurrentThreadId();

                LogInterceptor(appDir, string.Format("Interceptor started for PID {0}", targetProcess.Id));

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

                            LogInterceptor(appDir, string.Format("EVENT_SHOW: HWND={0}, Cls={1}, Title='{2}', Owner={3}, Size={4}x{5}",
                                hwnd, cls, title, owner, w, h));

                            // Main window has no owner and large dimensions
                            if (owner == IntPtr.Zero && w >= 600 && h >= 400)
                            {
                                s_mainHwnd = hwnd;
                            }
                            else if (hwnd != s_mainHwnd)
                            {
                                if (hwnd == s_allowedDeviceHwnd)
                                {
                                    LogInterceptor(appDir, string.Format("Ignored allowed device dialog {0}", hwnd));
                                    return;
                                }

                                // DeviceDownloadDialog has fixed size 387x273
                                bool isDownloadDialog = (w >= 370 && w <= 405 && h >= 255 && h <= 290) ||
                                                        title.IndexOf("Download", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                                        title.IndexOf("Import", StringComparison.OrdinalIgnoreCase) >= 0;

                                if (isDownloadDialog && !s_isImportModalRunning)
                                {
                                    s_isImportModalRunning = true;
                                    LogInterceptor(appDir, string.Format("Matched Download dialog {0}! Hiding and running modal...", hwnd));

                                    // Instantly hide the native USB dialog so "Please connect your device first!" never displays
                                    ShowWindow(hwnd, SW_HIDE);

                                    // Launch custom Import Modal (Choice: From Device vs From Folder)
                                    ThreadPool.QueueUserWorkItem(_ =>
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

                MSG msg;
                while (GetMessage(out msg, IntPtr.Zero, 0, 0))
                {
                    if (msg.message == WM_QUIT) break;
                    TranslateMessage(ref msg);
                    DispatchMessage(ref msg);
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

        private static void StopImportInterceptor(Thread thread)
        {
            try
            {
                if (s_interceptorThreadId != 0)
                {
                    PostThreadMessage(s_interceptorThreadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
                }
            }
            catch {}
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
                    // Sync newly imported files to portable storage
                    try
                    {
                        if (Directory.Exists(hostEcgBrowserDir))
                        {
                            CopyDirectory(hostEcgBrowserDir, portableDataDir);
                        }
                    }
                    catch {}

                    Thread.Sleep(300);

                    // Trigger UI table reload on main window
                    try
                    {
                        IntPtr mainHwnd = s_mainHwnd != IntPtr.Zero ? s_mainHwnd : targetProcess.MainWindowHandle;
                        if (mainHwnd != IntPtr.Zero)
                        {
                            IntPtr lparam = (IntPtr)((165 << 16) | 90);
                            PostMessage(mainHwnd, WM_LBUTTONDOWN, new IntPtr(1), lparam);
                            PostMessage(mainHwnd, WM_LBUTTONUP, IntPtr.Zero, lparam);
                        }
                    }
                    catch {}
                }
            }
        }

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

        #endregion

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
