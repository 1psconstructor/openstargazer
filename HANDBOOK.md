# openstargazer – Complete User Handbook

**Tobii Eye Tracker 5 on Linux with Star Citizen / LUG-Helper**

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
   - [Fedora (Recommended)](#31-fedora)
   - [Arch Linux](#32-arch-linux)
   - [Debian / Ubuntu](#33-debian--ubuntu)
   - [Other Distributions](#34-other-distributions)
4. [First Start & Setup Wizard](#4-first-start--setup-wizard)
5. [Uninstallation](#5-uninstallation)
6. [Configuration File Reference](#6-configuration-file-reference)
7. [Operation & Features](#7-operation--features)
8. [OpenTrack Integration](#8-opentrack-integration)
9. [Star Citizen / LUG-Helper](#9-star-citizen--lug-helper)
10. [Operating Modes & Use Cases](#10-operating-modes--use-cases)
11. [Calibration](#11-calibration)
12. [Profiles](#12-profiles)
13. [Best Practices](#13-best-practices)
14. [Tips & Tricks](#14-tips--tricks)
15. [Troubleshooting](#15-troubleshooting)
    - [Creating a Debug Report](#creating-a-debug-report)
16. [FAQ](#16-faq)
17. [Links](#17-links)

---

## 1. Overview & Architecture

openstargazer is a native Linux driver stack for the **Tobii Eye Tracker 5**. It consists of three main components:

```
┌─────────────────────────────────────────────────────────────────┐
│  Tobii Eye Tracker 5 (USB)                                      │
│    └─► libtobii_stream_engine.so  (proprietary Tobii library)   │
│          └─► osg-daemon           (Python background process)   │
│                ├─► OneEuro Filter  (noise reduction)            │
│                ├─► Curve Mapping   (axis configuration)         │
│                ├─► OpenTrack UDP   (→ OpenTrack → Star Citizen) │
│                ├─► FreeTrack SHM   (alternative output)         │
│                └─► IPC Socket      (GUI communication)          │
│                                                                  │
│  osg-config  (GTK4 GUI – optional interface)                    │
│  osg-setup   (Setup Wizard – initial configuration)             │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow in the daemon:**
```
Device → [Gaze + HeadPose Callbacks]
       → [OneEuro Filter]  (per-axis jitter reduction)
       → [Deadzone Filter] (gaze stabilization)
       → [Curve Mapping]   (nonlinear axis mapping)
       → [Scale + Invert]  (scaling and inversion)
       → [OpenTrack UDP / FreeTrack SHM]
```

---

## 2. System Requirements

### Hardware
- **Tobii Eye Tracker 5** (USB)
- USB 2.0 or 3.0 port
- Monitor mount or desk placement

### Software
| Requirement | Version |
|-------------|---------|
| Linux Kernel | 5.15 or newer |
| Python | 3.10 or newer |
| systemd | (for user service) |
| OpenTrack | 2026.1.0 or newer (recommended, for Star Citizen) |

### Supported Distributions
| Distribution | Package Manager | Tested |
|--------------|----------------|--------|
| **Fedora 39–43+** | dnf | ✓ Primary |
| Arch Linux / Manjaro | pacman | ✓ |
| Debian 12 / Ubuntu 22.04+ | apt | ✓ |
| Other distros | manual | limited |

---

## 3. Installation

### Preparation (all distros)

```bash
git clone https://github.com/1psconstructor/openstargazer.git
cd openstargazer
```

---

### Interactive Setup Menu

The script always presents a menu on startup:

```
==========================================
   openstargazer Setup
==========================================

  1) Neuinstallation
  2) Reparatur (fehlende Komponenten nachinstallieren)
  3) Deinstallation -- vollstaendig
  4) Deinstallation -- benutzerdefiniert
  5) Beenden
```

| Option | Description |
|--------|-------------|
| **1 – Fresh install** | Full installation of all components |
| **2 – Repair** | Checks each component and reinstalls only what is missing |
| **3 – Full uninstall** | Removes all components (with confirmation prompt) |
| **4 – Custom uninstall** | Shows all components with status, select by number |
| **5 – Exit** | Quit without action |

> **Install log:** Every run of `install.sh` appends to
> `~/.local/share/openstargazer/install.log` with timestamps and `[INFO|WARN|ERROR]`
> levels. Useful for reviewing past installation attempts or including in bug reports.

---

### 3.1 Fedora

```bash
cd scripts
chmod +x install.sh
./install.sh
```

**What happens (Fedora-specific):**

1. **Python check** — Fedora 43 ships Python 3.12, which is compatible.

2. **System packages** — The following packages are installed via `dnf`:
   ```
   python3-gobject  gtk4  libadwaita  libusb  usbutils  curl  tar
   ```

3. **OpenTrack** — Not in Fedora's official repos or RPM Fusion Free (Fedora 43+).
   The installer offers four options:
   1. Enable RPM Fusion Free and install via dnf (may not be available for all versions)
   2. Install via Flatpak from Flathub
   3. Build from GitHub source (recommended for Fedora 43, includes Wine/LUG support)
   4. Skip (install manually later)

4. **Python package** — Fedora has PEP 668 enabled, so:
   - First attempt: normal `pip install --user`
   - On rejection: automatic fallback to **venv** at `~/.local/share/openstargazer/venv/`
   - Entry-point scripts are symlinked into `~/.local/bin/`

5. **udev rules** — Copied to `/etc/udev/rules.d/70-openstargazer.rules`. Since `plugdev` doesn't exist on Fedora, `TAG+="uaccess"` in the rule is used (no group membership needed).

6. **systemd user service** — Installed and enabled. If a venv was used, `ExecStart` is automatically updated to the venv path.

**Installing OpenTrack on Fedora:**

```bash
# Option A: Enable RPM Fusion Free
sudo dnf install -y \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install -y opentrack

# Option B: Flatpak (Flathub)
flatpak install -y flathub io.github.opentrack.OpenTrack

# Option C: Build from GitHub source (Fedora 43+, includes Wine output plugin)
sudo dnf install cmake git qt6-qtbase-private-devel qt6-qttools-devel \
  opencv-devel procps-ng-devel libevdev-devel wine-devel wine-devel.i686
git clone --depth=1 https://github.com/opentrack/opentrack
cd opentrack && mkdir build && cd build
cmake .. -DSDK_WINE=ON -DCMAKE_INSTALL_PREFIX=/usr/local
make -j$(nproc) && sudo make install
```

---

### 3.2 Arch Linux

```bash
cd scripts
chmod +x install.sh
./install.sh
```

**Installed system packages (pacman):**
```
python-gobject  gtk4  libadwaita  libayatana-appindicator
libusb  usbutils  opentrack  curl  tar
```

**Notes for Arch:**
- Arch uses PEP 668 since Python 3.11+ → venv fallback applies automatically
- `python-venv` is bundled in the standard `python` package
- The user is added to the `plugdev` group (log out and back in afterwards)

---

### 3.3 Debian / Ubuntu

```bash
cd scripts
chmod +x install.sh
./install.sh
```

**Installed system packages (apt):**
```
python3-gi  python3-gi-cairo  gir1.2-gtk-4.0  gir1.2-adw-1
libusb-1.0-0  usbutils  opentrack
python3-venv  curl  tar
```

**Notes for Debian/Ubuntu:**
- `python3-venv` is explicitly listed since it may be missing on minimal installs
- Debian 12+ and Ubuntu 23.04+: PEP 668 active → venv fallback
- Ubuntu 22.04: direct pip install works (no venv needed)
- The user is added to the `plugdev` group

---

### 3.4 Other Distributions

For unknown package managers, the installer outputs these packages for manual installation:

```
GTK4, libadwaita, python3-gi (PyGObject), libusb, usbutils, opentrack, curl, tar
```

Then:
```bash
python3 -m pip install --user -e ".[tray]"
# or with PEP 668:
python3 -m venv ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install -e ".[tray]"
```

---

### Installation Flags

```bash
./install.sh [--no-gui] [--mock]
```

| Flag | Effect |
|------|--------|
| `--no-gui` | Skips desktop entry and icon installation |
| `--mock` | (developer) Installs without real hardware dependencies |

---

## 4. First Start & Setup Wizard

After installation the **Setup Wizard** (`osg-setup`) starts automatically.

### Wizard Steps

**Step 1: Stream Engine**
- Checks if `libtobii_stream_engine.so` and `tobiiusbservice` exist under `~/.local/share/openstargazer/`
- Offers to download them automatically (`fetch-stream-engine.sh`)

**Step 2: Hardware Detection**
- Searches via `lsusb` for known Tobii USB IDs
- Known PIDs: `0127`, `0118`, `0106`, `0128`, `010a`, `0313`
- If device not found: optionally continue without hardware

**Step 3: LUG-Helper / Star Citizen**
- Automatically searches for the LUG-Helper config under `~/.config/starcitizen-lug/`
- Detects Wine prefix, runner path, ESYNC/FSYNC settings
- Manual entry possible if config not found

**Step 4: OpenTrack Profile**
- Generates an OpenTrack INI profile for Star Citizen
- Default port: 4242 (UDP)

**Step 5: In-Game Instructions**
- Shows Star Citizen head tracking settings

**Step 6: Calibration (optional)**
- Only possible if the daemon is already running

### Re-run the Wizard

```bash
osg-setup
# or:
python3 -m openstargazer.setup.wizard
```

---

## 5. Uninstallation

### Via the install script (recommended)

```bash
cd scripts
./install.sh
# → Select option 3 (full) or option 4 (custom)
```

**Option 3 – Full uninstall** removes after confirmation:
- systemd user service (stop + disable + file deletion)
- udev rules
- Tobii USB service and binaries
- Python package / venv / symlinks
- Desktop entry and icon
- User data (`~/.config/openstargazer`) – **separate prompt, default: No**

**Option 4 – Custom uninstall** shows all components with their current installation status and lets you select individual ones by number:

```
  1) systemd user service (openstargazer.service)  [installed]
  2) udev rules (70-openstargazer.rules)            [installed]
  3) Tobii USB service (tobiiusb.service)           [installed]
  4) Tobii binaries (libtobii_stream_engine.so ...) [installed]
  5) Python package (openstargazer)                 [installed]
  6) Desktop entry + icon                           [installed]
  7) User data (~/.config/openstargazer ...)        [exists]

  Selection: 1,2,5
```

### Manual uninstall (fallback)

If the script is not available:

```bash
# Stop and disable services
systemctl --user stop openstargazer.service 2>/dev/null || true
systemctl --user disable openstargazer.service 2>/dev/null || true
sudo systemctl stop tobiiusb.service 2>/dev/null || true
sudo systemctl disable tobiiusb.service 2>/dev/null || true

# Remove service files
rm -f ~/.config/systemd/user/openstargazer.service
sudo rm -f /etc/systemd/system/tobiiusb.service
systemctl --user daemon-reload && sudo systemctl daemon-reload

# Remove udev rules
sudo rm -f /etc/udev/rules.d/70-openstargazer.rules
sudo udevadm control --reload-rules

# Remove desktop entry and icon
rm -f ~/.local/share/applications/openstargazer.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/openstargazer.svg

# Remove Python package and venv
pip uninstall openstargazer 2>/dev/null || true
rm -rf ~/.local/share/openstargazer/venv
rm -f ~/.local/bin/osg-daemon ~/.local/bin/osg-config ~/.local/bin/osg-setup

# Remove Tobii binaries
rm -f ~/.local/share/openstargazer/lib/libtobii_stream_engine.so
sudo rm -f /usr/local/sbin/tobiiusbserviced
sudo rm -rf /usr/local/lib/tobiiusb

# Remove configuration (OPTIONAL – deletes all settings!)
rm -rf ~/.config/openstargazer/

# Remove user from plugdev (Debian/Ubuntu/Arch)
sudo gpasswd -d "$USER" plugdev
```

### Reset Configuration Only (without uninstalling)

```bash
rm ~/.config/openstargazer/config.toml
osg-setup  # creates new default configuration
```

---

## 6. Configuration File Reference

The configuration is at: `~/.config/openstargazer/config.toml`

It is automatically created with default values on first run.

---

### [device]

```toml
[device]
preferred_url = ""
use_head_pose = true
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `preferred_url` | String | `""` | Direct USB URL of the device (e.g. `"usb://0x2104/0x0127"`). Empty = use first found device. |
| `use_head_pose` | Bool | `true` | If `true`: head position and rotation are processed. If `false`: gaze point data only, no head tracking. |

---

### [tracking]

```toml
[tracking]
mode = "head_and_gaze"
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `mode` | String | `"head_and_gaze"` | Tracking mode (see table) |

**Available modes:**

| Mode | Description | Sends to OpenTrack |
|------|-------------|-------------------|
| `"head_and_gaze"` | Head rotation/position + gaze point | Head data (6-DoF) |
| `"head_only"` | Head tracking only, no eye tracking | Head data (6-DoF) |
| `"gaze_only"` | Gaze point only, no head tracking | Gaze as X/Y |

---

### [filter]

```toml
[filter]
one_euro_min_cutoff = 0.5
one_euro_beta = 0.007
gaze_deadzone_px = 30.0
```

The **One-Euro Filter** is an adaptive low-pass filter. It reduces jitter at slow movements while allowing fast movements to pass through with nearly no delay.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `one_euro_min_cutoff` | Float (Hz) | `0.5` | Minimum cutoff frequency. **Smaller = smoother at rest, but more latency.** Range: 0.1–2.0 |
| `one_euro_beta` | Float | `0.007` | Speed coefficient. **Larger = less lag on fast movements.** Range: 0.0–0.1 |
| `gaze_deadzone_px` | Float (pixels) | `30.0` | Gaze deadzone in pixels. Small eye movements below this threshold are ignored to prevent flickering. |

**Filter recommendations:**

| Use case | `min_cutoff` | `beta` |
|----------|-------------|--------|
| Default (Star Citizen) | `0.5` | `0.007` |
| Very smooth, some lag | `0.2` | `0.003` |
| Fast tracking, some jitter | `1.0` | `0.02` |
| FPS shooter (max response) | `1.5` | `0.05` |

---

### [output.opentrack_udp]

```toml
[output.opentrack_udp]
enabled = true
host = "127.0.0.1"
port = 4242
```

UDP output in OpenTrack protocol (48-byte packet, 6× little-endian double).

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | Bool | `true` | Enable/disable UDP output |
| `host` | String | `"127.0.0.1"` | Target IP for UDP packets. Loopback for local OpenTrack. For remote setups, edit `config.toml` directly (loopback-only restriction applies in the GUI). |
| `port` | Int | `4242` | UDP port. Must match OpenTrack setting. Valid range: 1024–65535. |

---

### [output.freetrack_shm]

```toml
[output.freetrack_shm]
enabled = false
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | Bool | `false` | Enable FreeTrack shared memory output. Requires Wine FreeTrack support. Not needed for most setups. |

---

### [axes.yaw], [axes.pitch], [axes.roll], [axes.x], [axes.y], [axes.z]

Each of the 6 tracking axes can be configured individually:

```toml
[axes.yaw]
scale = 1.0
invert = false
curve = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `scale` | Float | `1.0` | Multiplier for the axis. `2.0` = double range, `0.5` = half range. |
| `invert` | Bool | `false` | Reverses the axis direction. |
| `curve` | List of points | linear | Response curve as list of [x, y] control points. Allows nonlinear response. |

**Axis reference:**

| Axis | Meaning | Value range |
|------|---------|-------------|
| `yaw` | Head left/right rotation | -180° to +180° |
| `pitch` | Head up/down tilt | -90° to +90° |
| `roll` | Head sideways tilt | -90° to +90° |
| `x` | Head position left/right | mm (approx. -300 to +300) |
| `y` | Head position up/down | mm (approx. -300 to +300) |
| `z` | Head position forward/back | mm (approx. -300 to +300) |

---

## 7. Operation & Features

### osg-daemon

The background process. Runs as a systemd user service.

```bash
# Check status
systemctl --user status openstargazer

# Start
systemctl --user start openstargazer

# Stop
systemctl --user stop openstargazer

# Restart (after config change)
systemctl --user restart openstargazer

# View daemon log
journalctl --user -u openstargazer -f

# Start directly with output (debugging)
osg-daemon --verbose

# Mock mode (without hardware, sinusoidal test data)
osg-daemon --mock

# Custom config file
osg-daemon --config /path/to/config.toml
```

**Daemon flags:**

| Flag | Description |
|------|-------------|
| `--mock` | Synthetic data instead of real hardware (~90 Hz, sinusoidal) |
| `--verbose` / `-v` | Detailed logging (DEBUG level) |
| `--config PATH` | Alternative path to config.toml |

**Auto-reconnect:** The daemon automatically reconnects every 2 seconds on device loss.

---

### osg-config (GUI)

```bash
osg-config
```

The GTK4 user interface. Shows:
- Live tracking data preview
- Connection status and FPS
- Profile selection
- Access to curve editor and calibration

**Note:** The GUI communicates with the daemon via a Unix socket (`~/.local/share/openstargazer/daemon.sock`). The daemon must be running.

**Mock mode** – run the GUI without any hardware or daemon:
```bash
osg-config --mock
```
Starts the GUI with a built-in simulation client (no daemon required). Useful for testing the UI and configuring curves offline.

---

### osg-setup (Wizard)

```bash
osg-setup
```

Interactive setup wizard. Can be run again at any time to:
- Re-download Stream Engine
- Update LUG-Helper configuration
- Regenerate OpenTrack profile

---

## 8. OpenTrack Integration

### How it works

osg-daemon sends 6-DoF data via UDP to OpenTrack:
```
osg-daemon → UDP :4242 → OpenTrack → Wine (FreeTrack/TrackIR) → Star Citizen
```

The UDP packet contains 48 bytes (6 × 8-byte little-endian double):
```
Bytes  0– 7: X position (mm)
Bytes  8–15: Y position (mm)
Bytes 16–23: Z position (mm)
Bytes 24–31: Yaw (degrees)
Bytes 32–39: Pitch (degrees)
Bytes 40–47: Roll (degrees)
```

### Configuring OpenTrack

**Input:** `UDP over network` – Port `4242`

**Output:** `Wine` – Runner and prefix from LUG-Helper configuration

**Filter:** None (osg-daemon already filters internally)

### Start order (important!)

```
1. Start Star Citizen
2. Start daemon:  systemctl --user start openstargazer
3. Open OpenTrack
4. Load OpenTrack profile
5. Start OpenTrack (green Play button)
```

---

## 9. Star Citizen / LUG-Helper

### In-Game Settings

```
Settings → COMMS, FOIP & HEAD TRACKING
  Head Tracking Source: TrackIR
  Enable Head Tracking: ✓
```

### LUG-Helper Config Paths

The wizard automatically searches for LUG config in this order:
```
~/.config/starcitizen-lug/config
~/.config/starcitizen-lug/settings
~/.config/starcitizen-lug/lug-helper.conf
~/.config/starcitizen-lug/lug-helper.cfg
~/.config/starcitizen-lug/preflight_conf
```
If none of these are found, any file in the directory is checked as a fallback.

Detected keys (both upper- and lowercase): `WINEPREFIX`, `wine_prefix`, `SC_PREFIX`, `WINE_RUNNER_PATH`, `runner_path`, `ESYNC`, `FSYNC`

> **Note for GE-Proton users:** Add `export PROTON_VERB="runinprefix"` to your
> launch environment (e.g. `sc-launch.sh`). This is required for OpenTrack's
> Wine output plugin to work correctly with GE-Proton runners.

---

## 10. Operating Modes & Use Cases

### Mode 1: Head Tracking + Eye Tracking (Default)

```toml
[tracking]
mode = "head_and_gaze"

[device]
use_head_pose = true
```

Enables all 6 degrees of freedom (Yaw, Pitch, Roll, X, Y, Z) plus gaze point.

---

### Mode 2: Head Tracking Only

```toml
[tracking]
mode = "head_only"

[device]
use_head_pose = true
```

**Recommended for:** Users who want head tracking for Star Citizen without eye movement involvement. Lower CPU usage, cleaner curves.

---

### Mode 3: Eye Tracking Only

```toml
[tracking]
mode = "gaze_only"

[device]
use_head_pose = false
```

**Recommended for:** Applications that only need gaze data (accessibility tools, gaze overlay, etc.).

---

### Mode 4: Rotation Only (no position tracking)

When the tracker is at a distance and position data is unreliable:

```toml
[axes.x]
scale = 0.0   # Disables X position

[axes.y]
scale = 0.0   # Disables Y position

[axes.z]
scale = 0.0   # Disables Z position
```

Yaw, Pitch, and Roll remain active.

---

## 11. Calibration

Calibration improves gaze accuracy through polynomial correction.

### Starting Calibration

The daemon must be running:

```bash
# Via GUI: osg-config → Calibration
# Or via wizard:
osg-setup  # select step 6
```

### Resetting Calibration

```bash
# Edit config.toml:
nano ~/.config/openstargazer/config.toml

# Change lines:
coeff_x = []
coeff_y = []
```

---

## 12. Profiles

Profiles allow quick switching between configurations (e.g. Star Citizen vs. desktop use).

Manage profiles via `osg-config` or the IPC API.

---

## 13. Best Practices

### Physical Setup

- Position tracker **centered below the monitor**, level
- Face distance: **60–80 cm** optimal
- Avoid direct lighting on the device (IR interference)
- Strong sunlight behind the monitor can disrupt tracking

### Configuration

- **Test filter settings first** before adjusting curves
- Always test curves with `--mock` and `osg-config` before real hardware tracking
- Adjust one axis at a time, not all at once
- Back up config before major changes:
  ```bash
  cp ~/.config/openstargazer/config.toml ~/.config/openstargazer/config.toml.bak
  ```

### Service Management

- **Don't start the daemon manually** in the terminal while the systemd service is running — this creates two instances
- Always restart after config changes:
  ```bash
  systemctl --user restart openstargazer
  ```

---

## 14. Tips & Tricks

### Quickly disable axes

Set axis to `scale = 0.0` instead of complex config changes:
```toml
[axes.roll]
scale = 0.0   # Roll disabled
```

### Invert roll

Some users prefer inverted roll:
```toml
[axes.roll]
invert = true
```

### Mock mode for setup tests

Test without a real tracker – two options:

```bash
# Option 1: Start daemon in mock mode, connect GUI normally
osg-daemon --mock --verbose &
osg-config

# Option 2: Start GUI in mock mode directly (no daemon needed)
osg-config --mock
```

### Override Stream Engine path

If the `.so` is at a non-standard location:
```bash
export OSG_STREAM_ENGINE_PATH=/path/to/libtobii_stream_engine.so
osg-daemon
```

---

## 15. Troubleshooting

### Problem: Daemon won't start – Stream Engine not found

**Error:**
```
StreamEngineError: libtobii_stream_engine.so not found.
```

**Solution:**
```bash
bash scripts/fetch-stream-engine.sh

# Or check manually:
ls ~/.local/share/openstargazer/lib/libtobii_stream_engine.so
ls ~/.local/share/openstargazer/bin/tobiiusbservice
```

---

### Problem: No device found

**Error:**
```
No Tobii devices found
```

**Steps:**

1. Check USB connection:
   ```bash
   lsusb | grep 2104
   ```
   Must show an entry with vendor ID `2104`.

2. Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger --subsystem-match=usb
   ```

3. Replug device after udev reload.

4. On Debian/Ubuntu: check group membership:
   ```bash
   groups | grep plugdev
   ```
   If not present: log out and back in.

---

### Problem: pip error (PEP 668)

**Error:**
```
error: externally-managed-environment
```

The installer handles this automatically with a venv. For manual installation:

```bash
python3 -m venv --system-site-packages ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install -e ".[tray]"
```

---

### Problem: OpenTrack receives no data

**Checklist:**
1. Daemon running? → `systemctl --user status openstargazer`
2. Port matching? → `config.toml` port vs. OpenTrack UDP port
3. OpenTrack Input set to `UDP over network`?
4. Firewall? → `sudo firewall-cmd --add-port=4242/udp --permanent` (Fedora)

---

### Problem: Tracker jumps or jitters

**Solution: adjust filter**
```toml
[filter]
one_euro_min_cutoff = 0.3
one_euro_beta = 0.003
```

Or increase deadzone:
```toml
gaze_deadzone_px = 50.0
```

---

### Problem: High latency / delay

**Solution: make filter more responsive**
```toml
[filter]
one_euro_min_cutoff = 1.0
one_euro_beta = 0.02
```

Also: set OpenTrack filter to **none**.

---

### Problem: Star Citizen shows no head tracking

1. Check order: **start Star Citizen first, then OpenTrack**
2. In Star Citizen: Settings → COMMS, FOIP & HEAD TRACKING → enable TrackIR
3. OpenTrack: Play button pressed?
4. Wine Output in OpenTrack: correct runner and prefix?

---

### Creating a Debug Report

If you encounter a problem that is difficult to diagnose, use the debug-report script
to collect all relevant system information in one file:

```bash
cd scripts
bash collect-debug-info.sh
```

Or from the install.sh menu: choose **option 6 – Debug-Report erstellen**.

The script creates a file at:
```
~/openstargazer-debug-YYYYMMDD-HHMMSS.txt
```

**What the report contains:**
- System: OS/distro, kernel version, architecture, RAM, CPU
- Python: version, pip/venv status, `pip show openstargazer`
- USB devices: Tobii device detection via `lsusb`
- Service status: `openstargazer` user service and last 50 journal lines
- Tobii USB service: `tobiiusb` system service status
- Install paths: existence check for all key files (stream engine, udev rules, venv, desktop entry)
- opentrack: version and config directory contents (filenames only)
- Config file: `~/.config/openstargazer/config.toml` with home paths redacted
- Install log: last 100 lines of `~/.local/share/openstargazer/install.log`
- udev rules: content of `/etc/udev/rules.d/70-openstargazer.rules`

Attach the resulting file to a [new GitHub issue](https://github.com/1psconstructor/openstargazer/issues/new).

> **Privacy note:** The script replaces your actual username in file paths with `<user>`
> before writing the config file content. No passwords or tokens are collected.

---

## 16. FAQ

**Q: Does OpenTrack need to be installed for osg-daemon to run?**
A: No. The daemon sends UDP packets regardless of whether OpenTrack is running.

---

**Q: Does the tracker work without Star Citizen?**
A: Yes. osg-daemon sends standard OpenTrack UDP. Any application that understands the OpenTrack UDP protocol can receive the data.

---

**Q: What is the latency?**
A: The Tobii ET5 runs at 33–90 Hz (depending on mode). Filters add 10–50 ms depending on settings. End-to-end (tracker → OpenTrack) typically under 30 ms.

---

**Q: Can I use multiple Tobii devices simultaneously?**
A: Currently the daemon connects to the first found device. Use `preferred_url` in the configuration to select a specific device.

---

**Q: How do I update openstargazer?**
```bash
cd ~/openstargazer
git pull
pip install --user -e ".[tray]"   # or venv-pip
systemctl --user restart openstargazer
```

---

**Q: Does the tracker work under Wayland?**
A: The daemon itself runs independently of Wayland/X11 (USB device). The GUI (`osg-config`) uses GTK4 and works on both.

---

**Q: What does mock mode do exactly?**
A: `--mock` generates sinusoidal test data at ~90 Hz without a real tracker. Yaw/Pitch/Roll/X/Y/Z oscillate at different frequencies. Useful for UI tests and OpenTrack connection tests.

---

**Q: Can I use openstargazer with games other than Star Citizen?**
A: Yes. Any game that supports TrackIR or FreeTrack via Wine/Proton works. OpenTrack must be configured accordingly.

---

## 17. Links

### Project & Community

| Resource | Link |
|----------|------|
| openstargazer on GitHub | https://github.com/1psconstructor/openstargazer |
| Tobii Eye Tracker 5 (official) | https://gaming.tobii.com/product/eye-tracker-5/ |
| OpenTrack | https://github.com/opentrack/opentrack |
| LUG-Helper (Star Citizen Linux) | https://github.com/starcitizen-lug/lug-helper |

### Drivers & Libraries

| Resource | Link |
|----------|------|
| Community Stream Engine Mirror | https://github.com/johngebbie/tobii_4C_for_linux/releases |
| Tobii Stream Engine (official, SDK) | https://developer.tobii.com/product-integration/stream-engine/ |

### Documentation

| Topic | Link |
|-------|------|
| OpenTrack UDP Protocol | https://github.com/opentrack/opentrack/wiki/UDP-over-network-protocol |
| One Euro Filter Paper | https://gery.casiez.net/1euro/ |
| PyGObject (GTK4 Python) | https://pygobject.gnome.org/ |
| systemd User Services | https://wiki.archlinux.org/title/Systemd/User |

### Star Citizen Linux

| Resource | Link |
|----------|------|
| Star Citizen on Linux (Wiki) | https://starcitizen.tools/Star_Citizen_on_Linux |
| LUG Community Discord | https://discord.gg/starcitizen-linux |
| GE-Proton | https://github.com/GloriousEggroll/proton-ge-custom |

---

*This handbook covers openstargazer v0.2.0.*
