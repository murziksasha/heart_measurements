import sys
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from import_gui import APP_TITLE, ImportChooserApp, FolderImportApp, main


class TestImportChooser(unittest.TestCase):
    def setUp(self):
        # Create a chooser instance without blocking mainloop
        self.chooser = ImportChooserApp()
        self.chooser.update_idletasks()

    def tearDown(self):
        try:
            if self.chooser.winfo_exists():
                self.chooser.destroy()
        except tk.TclError:
            pass

    def test_chooser_window_properties(self):
        self.assertEqual(self.chooser.title(), APP_TITLE)
        self.assertEqual(self.chooser.title(), "Import recordings")
        # Check controls inside chooser
        buttons = []
        labels = []
        combos = []

        def collect_widgets(parent):
            for child in parent.winfo_children():
                if isinstance(child, tk.Button):
                    buttons.append(child.cget("text"))
                elif isinstance(child, tk.Label):
                    labels.append(child.cget("text"))
                elif "Combobox" in child.__class__.__name__:
                    combos.append(child)
                collect_widgets(child)

        collect_widgets(self.chooser)
        self.assertIn("Import from folder", buttons)
        self.assertIn("Import from device", buttons)
        self.assertIn("Cancel", buttons)
        self.assertEqual(len(buttons), 3)

        # No patient picker, drive chip, or help line
        self.assertEqual(len(combos), 0)
        self.assertEqual(len(labels), 0)

    def test_device_choice(self):
        self.chooser._choose_device()
        self.assertEqual(self.chooser.choice, "device")

    def test_cancel_choice(self):
        self.chooser._cancel()
        self.assertEqual(self.chooser.choice, "cancel")

    def test_folder_choice(self):
        self.chooser._choose_folder()
        self.assertEqual(self.chooser.choice, "folder")


class TestMainDispatch(unittest.TestCase):
    @patch("import_gui.FolderImportApp")
    def test_main_with_folder_flag(self, mock_folder_app):
        mock_instance = MagicMock()
        mock_instance.exit_code = 0
        mock_folder_app.return_value = mock_instance

        with patch.object(sys, "argv", ["import_gui.py", "--folder"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_folder_app.assert_called_once_with(initial_dir=None)

    @patch("import_gui.FolderImportApp")
    def test_main_with_folder_path(self, mock_folder_app):
        mock_instance = MagicMock()
        mock_instance.exit_code = 2
        mock_folder_app.return_value = mock_instance

        with patch.object(sys, "argv", ["import_gui.py", "C:\\some\\folder"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
            mock_folder_app.assert_called_once_with(initial_dir="C:\\some\\folder")

    @patch("import_gui.FolderImportApp")
    def test_main_with_folder_flag_and_path(self, mock_folder_app):
        mock_instance = MagicMock()
        mock_instance.exit_code = 0
        mock_folder_app.return_value = mock_instance

        with patch.object(sys, "argv", ["import_gui.py", "--folder", "C:\\custom"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_folder_app.assert_called_once_with(initial_dir="C:\\custom")

    @patch("import_gui.ImportChooserApp")
    def test_main_no_args_cancel_exits_0(self, mock_chooser):
        chooser_instance = MagicMock()
        chooser_instance.choice = "cancel"
        mock_chooser.return_value = chooser_instance

        with patch.object(sys, "argv", ["import_gui.py"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            mock_chooser.assert_called_once()

    @patch("import_gui.ImportChooserApp")
    def test_main_no_args_device_exits_1(self, mock_chooser):
        chooser_instance = MagicMock()
        chooser_instance.choice = "device"
        mock_chooser.return_value = chooser_instance

        with patch.object(sys, "argv", ["import_gui.py"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)
            mock_chooser.assert_called_once()

    @patch("import_gui.FolderImportApp")
    @patch("import_gui.ImportChooserApp")
    def test_main_no_args_folder_opens_folder_app(self, mock_chooser, mock_folder_app):
        chooser_instance = MagicMock()
        chooser_instance.choice = "folder"
        mock_chooser.return_value = chooser_instance

        mock_app = MagicMock()
        mock_app.exit_code = 2
        mock_folder_app.return_value = mock_app

        with patch.object(sys, "argv", ["import_gui.py"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
            mock_chooser.assert_called_once()
            mock_folder_app.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
