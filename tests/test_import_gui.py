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


class TestFolderImportApp(unittest.TestCase):
    def setUp(self):
        self.app = FolderImportApp(initial_dir=".")
        self.app.update_idletasks()

    def tearDown(self):
        try:
            if self.app.winfo_exists():
                self.app.destroy()
        except tk.TclError:
            pass

    def test_subtitle_text(self):
        labels = []
        def collect_labels(parent):
            for child in parent.winfo_children():
                if isinstance(child, tk.Label):
                    labels.append(child.cget("text"))
                collect_labels(child)
        collect_labels(self.app)
        self.assertIn(
            "New recordings are selected. A recording already stored for this patient cannot be imported again.",
            labels,
        )

    def test_duplicate_row_state_and_summary(self):
        self.app.records = [
            {
                "filename": "R20261007120000",
                "filepath": "R20261007120000",
                "timestamp": "20261007120000",
                "datetime_display": "2026-10-07 12:00:00",
                "duration_seconds": 60,
                "duration_display": "1 m 00 s",
                "file_size": 1000,
                "is_duplicate": True,
                "existing_id": 1,
                "checked": False,
                "report": "",
                "_var": None,
            },
            {
                "filename": "R20261008120000",
                "filepath": "R20261008120000",
                "timestamp": "20261008120000",
                "datetime_display": "2026-10-08 12:00:00",
                "duration_seconds": 60,
                "duration_display": "1 m 00 s",
                "file_size": 1000,
                "is_duplicate": False,
                "existing_id": None,
                "checked": True,
                "report": "",
                "_var": None,
            },
        ]
        self.app._render_rows()
        self.app._update_summary()
        self.app._update_import_button()

        # Summary check
        self.assertEqual(
            self.app.summary_var.get(),
            "2 recordings · 1 new · 1 already exist · 1 selected",
        )

        # Import button check
        self.assertEqual(self.app.import_btn.cget("text"), "Import 1")
        self.assertEqual(str(self.app.import_btn.cget("state")), "normal")

        # Cannot select duplicate via _set_checked
        self.app._set_checked(self.app.records[0], True)
        self.assertFalse(self.app.records[0]["checked"])

        # Clear selection
        self.app._clear_selection()
        self.assertEqual(
            self.app.summary_var.get(),
            "2 recordings · 1 new · 1 already exist · 0 selected",
        )
        self.assertEqual(self.app.import_btn.cget("text"), "Import recordings")
        self.assertEqual(str(self.app.import_btn.cget("state")), "disabled")

        # Select new only selects non-duplicate
        self.app._select_new()
        self.assertFalse(self.app.records[0]["checked"])
        self.assertTrue(self.app.records[1]["checked"])
        self.assertEqual(self.app.import_btn.cget("text"), "Import 1")

    def test_paint_state_already_exist(self):
        lbl = tk.Label(self.app)
        rec_dup = {"is_duplicate": True, "checked": False, "report": ""}
        self.app._paint_state(lbl, rec_dup)
        self.assertEqual(lbl.cget("text"), "Already exist")
        from ui_theme import MUTED
        self.assertEqual(lbl.cget("fg"), MUTED)


if __name__ == "__main__":
    unittest.main()
