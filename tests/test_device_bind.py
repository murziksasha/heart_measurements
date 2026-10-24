import os
import shutil
import sqlite3
import tempfile
import unittest

import manage_devices


class TestDeviceBind(unittest.TestCase):
    def test_bind_writes_nothing_without_account(self):
        temp_dir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(temp_dir, "db_lepu_care_world.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE tb_admin (admin varchar(50), userid INTEGER, vanish_id TEXT)"
            )
            conn.execute(
                "INSERT INTO tb_admin (admin, userid, vanish_id) VALUES ('', 1, '')"
            )
            conn.execute(
                """
                CREATE TABLE tb_device (
                    sn varchar(40) PRIMARY KEY,
                    admin varchar(50),
                    hwversion INT,
                    fwversion INT,
                    blversion INT,
                    devicetype INT,
                    protocolversion INT,
                    branchcode varchar(20)
                )
                """
            )
            conn.commit()
            conn.close()

            orig_paths = manage_devices.database_paths
            orig_config = manage_devices.CONFIG_PATH
            orig_script = manage_devices.SCRIPT_DIR
            manage_devices.database_paths = lambda: [db_path]
            manage_devices.CONFIG_PATH = os.path.join(temp_dir, "missing-config.ini")
            manage_devices.SCRIPT_DIR = temp_dir
            try:
                ok = manage_devices.bind_device("2306490032", admin="other@example.com")
                self.assertFalse(ok)
                conn = sqlite3.connect(db_path)
                count = conn.execute("SELECT COUNT(*) FROM tb_device").fetchone()[0]
                conn.close()
                self.assertEqual(count, 0)
            finally:
                manage_devices.database_paths = orig_paths
                manage_devices.CONFIG_PATH = orig_config
                manage_devices.SCRIPT_DIR = orig_script
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
