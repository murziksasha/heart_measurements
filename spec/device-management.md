# Device Management Specification

Component: `manage_devices.py`  
Launcher Shortcut: `Manage Devices.bat`  
Storage: SQLite Database (`tb_device`, `tb_bind_dev`), `config.ini`

## 1. Supported Device Models & Hardware Profiles

| Model | Display Name | DeviceType | BranchCode | HW Version | FW Version | Protocol |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ER1** | ER1 (Single-lead Holter) | `13873` | `40040000` | `67` | `16844800` | `1` |
| **ER1-LW** | ER1-LW | `13873` | `40012101` | `67` | `16844800` | `1` |
| **ER1-LB** | ER1-LB | `13873` | `40012201` | `67` | `16844800` | `1` |
| **ER2** | ER2 / DuoEK | `13874` | `40020000` | `68` | `16844800` | `1` |

---

## 2. Serial Binding Rules

### 2.1 Explicit Serial Entry
- The user can type a 10-digit serial number manually (e.g., `2306490032`).
- The serial must match standard alphanumeric device formats.

### 2.2 USB Scan Matching
- When clicking "Scan USB", the tool scans connected drives for ER1 recording files matching `is_er1_recording`.
- **Safety Rule:** A serial is bound only if the serial number is explicitly present in a file name on the drive (`(\d{8,12})R`). It **never** writes a built-in default or fallback serial.
- Prevents corrupting user device bindings with generic manufacturer serials.

### 2.3 Database Tables
- `tb_device`: Stores registered physical devices (`serialnum`, `devicename`, `devicetype`, `hwversion`, `fwversion`).
- `tb_bind_dev`: Maps device serials to user accounts (`admin`, `serialnum`, `bindtime`).
- Multi-location sync: Writes binding records to both active host `%LOCALAPPDATA%\ECG Browser\DATA\` and portable `Data/DATA/`.
