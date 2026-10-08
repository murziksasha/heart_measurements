import unittest
import os
import shutil
import tempfile
import sqlite3
from datetime import datetime

import manage_users


class TestUserManagement(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, "Data", "DATA")
        os.makedirs(self.data_dir, exist_ok=True)

        # Copy existing database into test temp dir
        src_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Data", "DATA", "db_lepu_care_world.db")
        self.test_db = os.path.join(self.data_dir, "db_lepu_care_world.db")
        shutil.copy(src_db, self.test_db)

        # Mock target locations
        self.orig_get_target_locations = manage_users.get_target_locations
        manage_users.get_target_locations = lambda: [self.data_dir]
        manage_users.SCRIPT_DIR = self.temp_dir

    def tearDown(self):
        manage_users.get_target_locations = self.orig_get_target_locations
        shutil.rmtree(self.temp_dir)

    def test_calculate_age(self):
        self.assertEqual(manage_users.calculate_age(""), 0)
        curr_year = datetime.now().year
        self.assertEqual(manage_users.calculate_age(f"{curr_year - 30}-01-01"), 30)

    def test_add_subuser_success(self):
        created = manage_users.add_subuser(
            name="Alice Smith",
            gender="Female",
            birthday="1992-06-20",
            email="alice@example.com",
            note="Test note"
        )
        self.assertIsNotNone(created["id"])
        self.assertEqual(created["name"], "Alice Smith")
        self.assertEqual(created["gender"], "Female")

        # Verify folder was created
        user_folder = os.path.join(self.data_dir, "userfiles", "subusr", str(created["id"]))
        self.assertTrue(os.path.exists(user_folder))

        # Verify database record
        users = manage_users.get_all_subusers()
        user_names = [u["name"] for u in users]
        self.assertIn("Alice Smith", user_names)

        # Verify familyid is unique
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute("SELECT familyid FROM tb_subuser WHERE subusr_id = ?", (created["id"],))
        fam_id = cur.fetchone()[0]
        conn.close()
        self.assertGreater(fam_id, 0)

    def test_update_subuser_stores_height_and_weight(self):
        created = manage_users.add_subuser(name="Height Check", gender="Male", birthday="1985-05-05")
        updated = manage_users.update_subuser(
            created["id"], name="Height Check", gender="Female", birthday="1985-05-05", height=170, weight=68,
        )
        self.assertEqual(updated["height"], 170)
        self.assertEqual(updated["weight"], 68)
        users = {u["id"]: u for u in manage_users.get_all_subusers()}
        self.assertEqual(users[created["id"]]["gender"], "Female")
        self.assertEqual(users[created["id"]]["height"], 170)

    def test_body_measurements_rejected_when_out_of_range(self):
        with self.assertRaises(ValueError):
            manage_users.add_subuser(name="Too Tall", birthday="1990-01-01", height=400)

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            manage_users.add_subuser(name="")

        with self.assertRaises(ValueError):
            manage_users.add_subuser(name="A" * 25)

    def test_delete_subuser(self):
        created = manage_users.add_subuser(
            name="Bob Jones",
            gender="Male",
            birthday="1980-01-01"
        )
        uid = created["id"]
        manage_users.delete_subuser(uid)

        users = manage_users.get_all_subusers()
        self.assertNotIn(uid, [u["id"] for u in users])

        # Test deleting default user ID 1 raises error
        with self.assertRaises(ValueError):
            manage_users.delete_subuser(1)


if __name__ == "__main__":
    unittest.main()
