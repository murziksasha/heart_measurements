# Patient Management Specification

Component: `manage_users.py`  
Storage: SQLite Database (`db_lepu_care_world.db`)

## 1. Database Schema & Tables

### 1.1 Tables
- `tb_subuser`: Primary patient profile records.
  - `subusr_id` (INTEGER, Primary Key): Unique numeric patient identifier.
  - `familyid` (INTEGER): Family identifier (generated sequentially, base >= 800000).
  - `userkey` (TEXT): Associated account email address.
  - `admin` (TEXT): Blank or admin identifier.
  - `name` (TEXT): Patient full name (maximum 20 characters).
  - `gender` (INTEGER): Gender code (`2` = Male, `1` = Female).
  - `birthday` (TEXT): Birthday string formatted as `YYYY-MM-DD`.
  - `height` (INTEGER): Height in centimeters (0..250, 0 = unrecorded).
  - `weight` (INTEGER): Weight in kilograms (0..400, 0 = unrecorded).
  - *Note: `tb_subuser` does not contain a notes or remark field.*
- `tb_subusr_selected_time`: Tracks last selected timestamp for active patient focus.
  - `subusr_id` (INTEGER, Primary Key)
  - `selected_time` (TEXT): Formatted as `YYYYMMDDHHMMSS`.
- `tb_admin`: Contains primary account login metadata.

### 1.2 Data Synchronization
- Multi-location writes: `get_target_locations()` writes updates to both portable `Data/DATA/` and active host `%LOCALAPPDATA%\ECG Browser\DATA/` if both directories exist.
- Patient directory structure: Automatically creates recording storage directory at `DATA/userfiles/subusr/{subusr_id}/`.

---

## 2. Validation Rules & Constraints

- **Name:** Required, stripped of leading/trailing whitespace, maximum length 20 characters.
- **Gender:** Converted to code `2` (Male) or `1` (Female).
- **Birthday & Age:** Birthday stored as `YYYY-MM-DD`. Age is calculated dynamically based on current local date and birthday.
- **Height:** Whole number between 0 and 250 cm (optional; 0 indicates not recorded).
- **Weight:** Whole number between 0 and 400 kg (optional; 0 indicates not recorded).
- **Deletion Guard:** Deleting a patient profile with existing recordings requires explicitly typing the patient's full name to confirm. Deletion cascades to remove `tb_record` rows and physical files under `userfiles/subusr/{subusr_id}/`.

---

## 3. UI Interfaces

### 3.1 `AddUserDialog` (Tkinter Modal)
- Invoked via:
  - Sidebar `+ Add User` button on Qt main window (via `manage_users.py --add-gui`).
  - Right-click context menu on "All Users" (`WM_RBUTTONUP`).
  - "+ New patient" button inside `FolderImportApp`.
- Topmost focus: Enforces foreground presentation with 400 ms topmost drop.
- Return exit codes:
  - `2`: User created, application reload requested.
  - `3`: User created, no reload requested (e.g. called from inside import GUI).
  - `0`: Cancelled or window dismissed.

### 3.2 Patient Manager GUI (`Manage Users.bat`)
- Standalone patient list window for browsing, adding, editing, and deleting patient records.

