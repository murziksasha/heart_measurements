import unittest
import math

def is_expected_download_dialog_size(w, h, scale=1.25):
    """Checks if dialog matches DeviceDownloadDialog for the given DPI scale."""
    if abs(scale - 1.25) < 0.1:
        if abs(w - 484) <= 12 and (abs(h - 335) <= 12 or abs(h - 341) <= 12):
            return True

    exp_w = int(round(387.0 * scale))
    exp_h = int(round(273.0 * scale))
    return abs(w - exp_w) <= 12 and abs(h - exp_h) <= 12


def is_download_dialog(w, h, title="", scale=1.25):
    """Python reference implementation of Program.cs TryInterceptDownloadDialog logic."""
    if h < 200 or w < 340:
        return False

    # Device Info exclusion (w ~ 443 * scale, h ~ 310 * scale)
    dev_w = int(round(443.0 * scale))
    dev_h = int(round(310.0 * scale))
    if abs(w - dev_w) <= 20 and abs(h - dev_h) <= 20:
        return False

    # Settings exclusion (w ~ 354 * scale, h ~ 230 * scale)
    set_w = int(round(354.0 * scale))
    set_h = int(round(230.0 * scale))
    if abs(w - set_w) <= 20 and abs(h - set_h) <= 20:
        return False

    # Notifications exclusion (w ~ 320 * scale, h ~ 262 * scale)
    not_w = int(round(320.0 * scale))
    not_h = int(round(262.0 * scale))
    if abs(w - not_w) <= 20 and abs(h - not_h) <= 20:
        return False

    if "download" in title.lower() or "import" in title.lower():
        return True

    if is_expected_download_dialog_size(w, h, scale):
        return True

    # Fallback check across all scales if scale is neutral/1.0
    for s in (1.0, 1.25, 1.5, 1.75, 2.0):
        if is_expected_download_dialog_size(w, h, s):
            return True

    return False


def is_import_button_click(client_x, client_y, main_width, dpi_scale=1.25):
    """Python reference implementation of Import Data toolbar hit-testing."""
    from_right = main_width - client_x
    min_from_right = int(170 * dpi_scale)
    max_from_right = int(265 * dpi_scale)
    min_y = int(12 * dpi_scale)
    max_y = int(58 * dpi_scale)

    return (min_from_right <= from_right <= max_from_right and
            min_y <= client_y <= max_y)


class TestInterceptorClassification(unittest.TestCase):
    def test_download_dialog_matches(self):
        # 100% DPI
        self.assertTrue(is_download_dialog(387, 273, scale=1.0))
        # 125% DPI measured & nominal
        self.assertTrue(is_download_dialog(484, 335, scale=1.25))
        self.assertTrue(is_download_dialog(484, 341, scale=1.25))
        # 150%, 175%, 200% DPI
        self.assertTrue(is_download_dialog(581, 410, scale=1.5))
        self.assertTrue(is_download_dialog(677, 478, scale=1.75))
        self.assertTrue(is_download_dialog(774, 546, scale=2.0))

    def test_device_dialog_rejected(self):
        # 125% DPI Device dialog from interceptor.log (554x388)
        self.assertFalse(is_download_dialog(554, 388, scale=1.25))
        # 100% and 150% scaled Device dialogs
        self.assertFalse(is_download_dialog(443, 310, scale=1.0))
        self.assertFalse(is_download_dialog(665, 465, scale=1.5))

    def test_settings_dialog_rejected(self):
        # 125% DPI Settings dialog from interceptor.log (443x288)
        self.assertFalse(is_download_dialog(443, 288, scale=1.25))
        # 100% and 150% scaled Settings dialogs
        self.assertFalse(is_download_dialog(354, 230, scale=1.0))
        self.assertFalse(is_download_dialog(531, 345, scale=1.5))

    def test_notifications_dialog_rejected(self):
        # 125% DPI Notifications dialog from interceptor.log (400x327)
        self.assertFalse(is_download_dialog(400, 327, scale=1.25))
        # 100% and 150% scaled Notifications dialogs
        self.assertFalse(is_download_dialog(320, 262, scale=1.0))
        self.assertFalse(is_download_dialog(480, 393, scale=1.5))

    def test_messagebox_and_confirmations_rejected(self):
        # Delete confirmation dialogs from interceptor.log
        self.assertFalse(is_download_dialog(331, 177))
        self.assertFalse(is_download_dialog(265, 142))
        self.assertFalse(is_download_dialog(265, 157))

    def test_import_button_hit_testing(self):
        main_w = 1024
        scale = 1.25
        # Click on Import Data button (from_right approx 260, y approx 38)
        import_btn_x = main_w - 260
        self.assertTrue(is_import_button_click(import_btn_x, 38, main_w, scale))

        # Click on Notifications button (from_right approx 360, y approx 38)
        notify_btn_x = main_w - 360
        self.assertFalse(is_import_button_click(notify_btn_x, 38, main_w, scale))

        # Click on Device button (from_right approx 175, y approx 38)
        device_btn_x = main_w - 175
        self.assertFalse(is_import_button_click(device_btn_x, 38, main_w, scale))

        # Click on Settings button (from_right approx 90, y approx 38)
        settings_btn_x = main_w - 90
        self.assertFalse(is_import_button_click(settings_btn_x, 38, main_w, scale))

        # Click in table / filter area (y = 120)
        self.assertFalse(is_import_button_click(import_btn_x, 120, main_w, scale))


if __name__ == "__main__":
    unittest.main()

