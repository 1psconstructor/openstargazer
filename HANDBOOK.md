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
10a. [Language](#10a-language)
11. [Calibration](#11-calibration)
12. [Profiles](#12-profiles)
13. [Best Practices](#13-best-practices)
14. [Tips & Tricks](#14-tips--tricks)
15. [Troubleshooting](#15-troubleshooting)
    - [Creating a Debug Report](#creating-a-debug-report)
16. [FAQ](#16-faq)
17. [License](#17-license)
18. [Links](#18-links)

---

## 1. Overview & Architecture

openstargazer is a native Linux driver stack for the **Tobii Eye Tracker 5**. It consists of three main components:

```
┌─────────────────────────────────────────────────────────────────┐
│  Tobii Eye Tracker 5 (USB)                                      │
│    ├─► et5_native         pyusb only -- position, roll,         │
│    │                      gaze (default)                        │
│    ├─► et5_ttp_camera     + IR camera, own ONNX weights         │
│    │                      -- adds yaw and pitch                 │
│    ├─► et5_stream_engine  libtobii_stream_engine.so --          │
│    │                      needs a Tobii licence most             │
│    │                      retail units don't have               │
│    └─► mock               simulated signal, for testing         │
│                           without hardware                      │
│                                                                 │
│  osg-daemon  (Python background process, one source             │
│               active at a time)                                 │
│    ├─► OneEuro Filter  (noise reduction)                        │
│    ├─► Deadzone Filter (gaze stabilization)                     │
│    ├─► Curve Mapping   (axis configuration)                     │
│    ├─► OpenTrack UDP   (→ OpenTrack → Star Citizen)             │
│    ├─► FreeTrack SHM   (alternative output)                     │
│    └─► IPC Socket      (GUI communication, poll or push)        │
│                                                                 │
│  osg-config  (GTK4/libadwaita GUI -- optional interface)        │
│  osg-setup   (Setup Wizard -- initial configuration)            │
│  osg-tray    (GTK3 status icon -- separate process)             │
│  osg-recenter (one-shot command for the neutral pose)           │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow in the daemon:**
```
Device → [Gaze + HeadPose Callbacks]
       → [OneEuro Filter]  (per-axis jitter reduction)
       → [Deadzone Filter] (gaze stabilization)
       → [Curve Mapping]   (nonlinear axis mapping)
       → [Scale + Invert]  (scaling and inversion)
       → [Neutral pose subtraction] (recentring, if enabled)
       → [OpenTrack UDP / FreeTrack SHM]
```

A default install gives you **four** of the six axes — position and roll,
plus the gaze point. Yaw and pitch need the camera source
(`et5_ttp_camera`), described under [§6 \[input\]](#input)
in the configuration reference and offered by the setup wizard. This is a
sensor limit, not something left unimplemented: all 39 fields the ET5's
gaze stream reports were checked, and none of them turns with the head.

openstargazer is **GPL-3.0-or-later** — see [§17 License](#17-license).

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

CI tests against Python 3.10, 3.11 and 3.12 on every change
(`.github/workflows/ci.yml`); newer 3.x interpreters are expected to work
but are not part of the test matrix.

### Supported Distributions
| Distribution | Package Manager | Tested |
|--------------|----------------|--------|
| **Fedora 39–43+** | dnf | ✓ Primary |
| Arch Linux / Manjaro | pacman | ✓ |
| Debian 12 / Ubuntu 22.04+ | apt | ✓ |
| Other distros | manual | limited |

### Python package extras

The `openstargazer` package (`pyproject.toml`) is installed with an extras
list, most commonly `.[tray]` or `.[gui,tray]`:

| Extra | Pulls in | Needed for |
|-------|----------|------------|
| `gui` | `pygobject>=3.44` | `osg-config`, `osg-setup`'s graphical chooser |
| `tray` | `pystray>=0.19` | (kept for compatibility; the shipped tray is `osg-tray`, a GTK3/AppIndicator program, not this library) |
| `camera` | `onnxruntime>=1.17` | Extended head tracking (`et5_ttp_camera`) — yaw and pitch |
| `dev` | `pytest`, `pytest-asyncio` | Running the test suite |

None of these are required for the native backend's four axes — only
`pyusb`, which is a core dependency, not an extra.

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

  1) Fresh installation
  2) Repair (reinstall missing components)
  3) Uninstall -- everything
  4) Uninstall -- pick components
  5) Quit
  6) Create debug report
```

| Option | Description |
|--------|-------------|
| **1 – Fresh install** | Full installation of all components |
| **2 – Repair** | Checks each component and reinstalls only what is missing |
| **3 – Full uninstall** | Removes all components (with confirmation prompt) |
| **4 – Custom uninstall** | Shows all components with status, select by number |
| **5 – Exit** | Quit without action |
| **6 – Debug report** | Collects logs and install state into one file for bug reports |

> **Install log:** Every run of `install.sh` appends to
> `~/.local/share/openstargazer/install.log` with timestamps and `[INFO|WARN|ERROR]`
> levels. Useful for reviewing past installation attempts or including in bug reports.

**A fresh install no longer offers to set up Tobii's Stream Engine.** It
always configures the native (`et5_native`) backend. The Stream Engine
binaries can still be fetched by hand afterwards
(`scripts/fetch-stream-engine.sh`) for the rare licensed device — see
`[device]` in the [configuration reference](#6-configuration-file-reference).
Repair and the custom-uninstall component list still recognise and manage
an existing Stream Engine install, they just no longer offer to create one.

### What a fresh install does, in order

```
1. Detect distro, install system packages (GTK4, libadwaita, libusb, opentrack, …)
2. Install the openstargazer Python package (pip, or a venv on PEP-668 systems)
3. Set the backend in config.toml (native, unless overridden)
4. osg-setup: language + graphical/terminal choice, then the chosen setup path
5. udev rule (skipped if the terminal wizard's own service step already installed it)
6. Native-backend prerequisite checks (pyusb, udev group membership)
7. systemd user service: install, enable, start
8. Desktop entry + icon (skipped with --no-gui)
9. OpenTrack profile as a safety net, if the setup path above didn't create one
10. Summary, and a reminder to reboot once
```

The language/graphical-or-terminal choice happens right after the Python
package is installed and before any of the system-level steps below it —
udev, the service, the desktop entry — because none of those steps need to
ask anything themselves; everything from that point on is the path the
user picked. Whichever setup path runs, it installs the udev rule and the
systemd service itself; `install.sh` only does it afterwards if that
didn't already happen, so a fresh install never asks for the same
`pkexec`/`sudo` authentication twice.

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
python3 -m pip install --user ".[gui,tray]"
# or with PEP 668:
python3 -m venv ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install ".[gui,tray]"
```

---

### Installation Flags

```bash
./install.sh [--no-gui] [--mock] [--lang <code>]
```

| Flag | Effect |
|------|--------|
| `--no-gui` | Skips desktop entry and icon installation |
| `--mock` | (developer) Installs without real hardware dependencies |
| `--lang <code>` | Forces the installer's own language (`en`, `de`, `fr`, `it`, `es`) for this run, overriding `OSG_LANG` and the system locale. Exported, so the setup wizard this hands off to inherits it too. |

Without `--lang`, the script's own language follows `OSG_LANG`, then the
system locale, then English — the same order the rest of the project uses,
see [§10a Language](#10a-language).

---

## 4. First Start & Setup Wizard

`osg-setup` is the entry point for both the terminal wizard and the
graphical guided setup — which one runs is chosen once, on a small start
screen, unless you force the terminal path with `--cli`.

```bash
osg-setup                # start screen: language + Graphical/Terminal
osg-setup --cli          # skip the start screen, run the text wizard directly
osg-setup --profile-only # detect LUG-Helper and write an OpenTrack profile
                          # only; prints nothing on success, exits non-zero
                          # if none could be made. Used by install.sh as a
                          # safety net -- never touches setup_completed and
                          # never shows a window.
```

### The start screen

A small GTK window (only shown if a display and a terminal are both
available, and `--cli` was not passed): pick a language from the row of
buttons, then **Graphical** or **Terminal**. Picking **Graphical** saves
the chosen language and launches `osg-config`, which is the one place that
then decides — from `settings.general.setup_completed` in `config.toml` —
whether to show the guided assistant or the settings overview. Picking
**Terminal** runs the text wizard below in the same process.

### The text wizard (`osg-setup --cli`)

**Step 1: Tracking Backend**
- On the default `native` backend there is nothing to install — the step
  just confirms it. It speaks USB directly, with no Tobii binaries and no
  `tobiiusbserviced`.
- On `stream-engine` it checks whether `libtobii_stream_engine.so` and
  `tobiiusbservice` exist under `~/.local/share/openstargazer/` and offers
  to download them (`fetch-stream-engine.sh`). The Stream Engine backend
  is optional; it is not required for head pitch, which the next step
  covers without it — and on most retail ET5 units it does not work at
  all regardless, for the licensing reason under `[device]` below.

**Extended head tracking (asked right after Step 1, every run)**
- The step that decides whether you get four axes or six. The gaze stream
  carries no head rotation — measured across all 39 device fields — so
  turn and tilt come from the ET5's own infrared camera and a neural
  network whose weights ship with the project (GPL-3.0).
- The costs are printed before the question, not after it: `onnxruntime`
  as an extra package, about 6 ms per picture (a fifth of one core at
  33 Hz), and that the pictures are read, measured and dropped — nothing
  stored, nothing sent anywhere.
- It never defaults to yes when the source could not start on this
  machine, and answering no does not move a `stream-engine` user off
  their backend. Changeable later in the settings window or as `source`
  under `[input]`.

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
- Only possible if the daemon is already running — the wizard's own
  service step (below) hasn't run yet at this point

**Service & udev setup (last, unnumbered)**
- Installs the systemd user service, enables it (both asked with a
  `[Y/n]`), and verifies it actually reaches the `active` state within a
  couple of seconds — printing the last lines of `systemctl status` if it
  doesn't.
- Installs the udev rule (also asked), reloads udev, and reminds you to
  replug the device.
- Ends with a summary table (backend, tracking mode, hardware, OpenTrack),
  the commands to start the daemon and open the GUI, and a note about the
  project's Ko-fi page.

### The graphical guided setup (in `osg-config`)

Runs automatically inside `osg-config` when `settings.general.setup_completed`
is still `false` — a fresh install, or after **Run setup again** in the
settings window. It is eight full-screen pages, each numbered "N/8" in its
header, with **Skip** always available (with a confirmation dialog) and
**Next**/secondary buttons driving the flow:

| # | Page | Does |
|---|------|------|
| 1 | Tracking backend | Same check as the text wizard's Step 1; on `stream-engine` without the binaries, offers a **Fetch** button instead of a terminal prompt |
| 2 | Extended head tracking | Same choice as the text wizard's camera step, as **Yes**/**No** buttons; shows the missing-`onnxruntime`/missing-weights warning inline if relevant |
| 3 | Hardware detection | Same `lsusb` check as Step 2 |
| 4 | Star Citizen / LUG-Helper | Auto-detects like Step 3; if nothing is found, shows an inline form for the Wine prefix and runner instead of a second window |
| 5 | OpenTrack profile | A port spin button (default 4242) and an **Install** action |
| 6 | In-game instructions | Same text as the text wizard's Step 5 |
| 7 | Calibration | **Calibrate now** opens the calibration window right there; **Later** just moves on |
| 8 | Service & udev | One **Install** button that installs the systemd service, enables it, verifies it started, and installs the udev rule (via `pkexec`, which raises the desktop's own authentication dialog) — all in one step, with the result printed inline |

Finishing page 8 (or skipping from any page) sets
`settings.general.setup_completed = true` and replaces the assistant with
the settings overview.

### Re-run the wizard

```bash
osg-setup
# or, to force the text path:
osg-setup --cli
```

The guided assistant can also be re-opened from inside `osg-config`: the
**Settings** card → **Run setup again**.

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

Items 3 and 4 only matter to installs that fetched the optional Stream
Engine backend by hand; a default native-backend install shows them as
"not found".

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
rm -f ~/.local/bin/osg-daemon ~/.local/bin/osg-config ~/.local/bin/osg-setup \
      ~/.local/bin/osg-tray ~/.local/bin/osg-recenter

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

### [general]

```toml
[general]
language = ""
setup_completed = false
active_profile = ""
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `language` | String | `""` | The saved UI language (`en`, `de`, `fr`, `it`, `es`). Empty means autodetect — see [§10a Language](#10a-language). Written by the language picker; `OSG_LANG` still overrides it for a single run. |
| `setup_completed` | Bool | `false` | Whether `osg-config` should open the settings overview (`true`) or the guided assistant (`false`). Set by the text wizard's last step and by finishing or skipping the graphical assistant. |
| `active_profile` | String | `""` | The name of the profile currently in force, purely a label — see [§12 Profiles](#12-profiles). |

---

### [device]

```toml
[device]
preferred_url = ""
use_head_pose = true
backend = "native"
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `preferred_url` | String | `""` | Direct USB URL of the device (e.g. `"usb://0x2104/0x0127"`). Empty = use first found device. Only used by the `stream-engine` backend. |
| `use_head_pose` | Bool | `true` | If `true`: head position and rotation are processed. If `false`: gaze point data only, no head tracking. |
| `backend` | String | `"native"` | The older name for the input source, kept readable so existing configs keep working: `"native"` means the source `et5_native`, `"stream-engine"` means `et5_stream_engine`. Can be overridden per-run with `osg-daemon --backend stream-engine`. An unknown value falls back to the default with a warning. See `[input]` below, which is the same setting with the full list. |

**Native backend (default):** `openstargazer/native/` talks to the ET5
directly over USB, without Tobii's Stream Engine binaries and without the
`tobiiusbserviced` background service. It delivers head **position**,
**roll** and the gaze point. It does **not** deliver yaw or pitch — the
gaze stream carries no head rotation, which was measured across all 39
device fields rather than left unimplemented. Those two axes come from
the `et5_ttp_camera` source described under `[input]`.

Switching backends does not require a reinstall. The `stream-engine`
backend is optional and, on most retail ET5 units, **not usable at
all**: `tobii_gaze_data_subscribe` and `tobii_head_pose_subscribe` both
return `INSUFFICIENT_LICENSE` without a Stream Engine licence, and that
licence ships only with certain OEM/partner deals, not with a bare
consumer device. That gap — head rotation nobody outside Tobii's own
software could reach on Linux — is why `et5_ttp_camera` exists: it reads
the same infrared camera through the project's own model instead of
asking Tobii's library for a pose it has no licence to hand out. The
installer no longer offers `stream-engine`, and repair no longer
maintains an existing one either; the manual path is still there for the
rare licensed device — run `./scripts/fetch-stream-engine.sh` once, then
set `backend = "stream-engine"` under `[device]` yourself.

---

### [input]

```toml
[input]
source = "et5_native"

[input.et5_camera]
model_path = ""
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `source` | String | `"et5_native"` | Which input source the daemon starts. See the table below. An unknown name is refused at start-up with the list of the ones that exist. |
| `et5_camera.model_path` | String | `""` | Path to a head-pose ONNX model. Empty means the shipped weights: the user directory `~/.local/share/openstargazer/models/` first, then the copy inside the package. |

| Source | Needs | Axes |
|--------|-------|------|
| `et5_native` | nothing beyond `pyusb` | position, roll, gaze |
| `et5_ttp_camera` | `onnxruntime` (`pip install 'openstargazer[camera]'`) | the same **plus yaw and pitch** |
| `et5_stream_engine` | Tobii's unofficial binaries **and** a Stream Engine licence most retail units do not have | six, in principle — see the note above; without the licence, none |
| `mock` | nothing | a simulated signal, for testing without hardware |

`config.toml` also carries an `[input.webcam]` block
(`device_index`, `width`, `height`, `fps`, `model_path`). It is reserved
for a possible future ordinary-webcam source; there is no registered
`webcam` input source in this release, so `source` only accepts the four
names above.

**Extended head tracking (`et5_ttp_camera`)** reads the ET5's infrared
camera alongside the gaze stream and puts each picture through a neural
network whose weights ship with the project under GPL-3.0
(`openstargazer/models/head-pose.onnx`, trained from scratch on
`replicantface` — MIT). No third-party model download is needed; the face
patch is cropped from the gaze stream's eye positions, so no separate
localizer model is required either.

What it costs: `onnxruntime` as an extra package, about 6 ms per picture
(a fifth of one core at 33 Hz), and the camera being read — the pictures
are measured and dropped, nothing is stored and nothing leaves the
machine. The gaze stream is unaffected: 33.1 fps measured with and
without, every sample distinct.

**The head keeps being tracked when the eyes are briefly lost.** The face
patch the pose network reads is cut from the eye positions the gaze
stream reports, so losing the eyes used to lose the head too — on 69% of
frames during a wide sweep in earlier testing. The patch is now carried
forward across a gap, and the network's own predicted spread decides
whether to keep believing it: on the head the spread stays around 4.7°,
on empty background it jumps past 20°, with a wide gap between the two.

The daemon chooses its source when it starts, so a change takes effect on
the next start:

```bash
systemctl --user restart openstargazer
```

The setup wizard asks for this, and the settings window has it as a
switch — it is not a setting you have to edit a file for.

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
one_euro_min_cutoff = 2.0
one_euro_beta = 0.1
gaze_min_cutoff = 1.0
gaze_beta = 1.0
gaze_deadzone_px = 30.0
```

The **One-Euro Filter** is an adaptive low-pass filter. It reduces jitter at slow movements while allowing fast movements to pass through with nearly no delay.

Head axes and gaze are filtered with **separate parameters**, because they are measured in different units: the head axes in degrees and millimetres, gaze in normalised screen coordinates from 0 to 1. A head turn covers tens of degrees per second where a saccade covers whole units, so `beta` has to be orders of magnitude larger on the gaze side to engage at all.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `one_euro_min_cutoff` | Float (Hz) | `2.0` | Minimum cutoff frequency for the **head axes**. **Smaller = smoother at rest, but more latency.** Range: 0.5–5.0 |
| `one_euro_beta` | Float | `0.1` | Speed coefficient for the **head axes**. **Larger = less lag on fast movements.** Range: 0.0–0.2 |
| `gaze_min_cutoff` | Float (Hz) | `1.0` | Minimum cutoff frequency for **gaze**. Range: 0.5–3.0 |
| `gaze_beta` | Float | `1.0` | Speed coefficient for **gaze**. Range: 0.0–4.0 |
| `gaze_deadzone_px` | Float (pixels) | `30.0` | Gaze deadzone in pixels. Small eye movements below this threshold are ignored to prevent flickering. Converted to a fraction of the screen using `[display]` when that step has been run; otherwise treated as normalised-coordinate pixels on an assumed 1920×1080 canvas. |

Measured at 33 Hz, for a saccade across 60% of the screen. "Jitter kept" is the share of fixation noise that survives the filter — lower is calmer:

| `gaze_min_cutoff` | `gaze_beta` | Jitter kept | 90% of a saccade |
|---|---|---|---|
| 1.0 | 0.0 | 26% | 394 ms |
| 1.0 | 1.0 (default) | 27% | 121 ms |
| 1.0 | 2.0 | 28% | 61 ms |
| 2.0 | 1.0 | 38% | 91 ms |

Raise `gaze_beta` first if the dot drags behind your eye; lower `gaze_min_cutoff` if it never settles.

The head axes were measured the same way, at 33 Hz. "90% of a turn" is a 20° step; "behind at 60°/s" is how far the reported angle trails a steady turn, given as the time offset it amounts to; "jitter kept" is the share of the device's own 0.05°/frame jitter that survives:

| `one_euro_min_cutoff` | `one_euro_beta` | Jitter kept | 90% of a turn | Behind at 60°/s |
|---|---|---|---|---|
| 0.5 | 0.007 (v0.2.x default) | 22% | 544 ms | 173 ms |
| 1.0 | 0.02 | 30% | 211 ms | 72 ms |
| 2.0 | 0.1 (default) | 41% | 60 ms | 20 ms |
| 3.0 | 0.1 | 48% | 60 ms | 18 ms |
| 5.0 | 0.1 | 57% | 60 ms | 14 ms |

One frame of the ET5 lasts 30 ms, so pushing the delay much below that gains nothing measurable — the device, USB and the network hop already cost more. Raise `one_euro_min_cutoff` only if the view still feels like it is catching up with your head; lower it if the view drifts while you sit still.

Both settings apply to all six head axes, including the millimetre ones. `beta` scales with the signal's own speed, so the same value works for degrees per second and millimetres per second without a separate parameter.

**Filter recommendations:**

| Use case | `min_cutoff` | `beta` |
|----------|-------------|--------|
| Default (Star Citizen) | `2.0` | `0.1` |
| Very smooth, some lag | `1.0` | `0.05` |
| Fast tracking, some jitter | `3.0` | `0.1` |
| FPS shooter (max response) | `5.0` | `0.15` |

---

### [neutral_pose]

```toml
[neutral_pose]
enabled = false
yaw = 0.0
pitch = 0.0
roll = 0.0
x = 0.0
y = 0.0
z = 0.0
```

The tracker reports where your head is **in front of the sensor**, not how far it has moved from where you normally sit. Those are the same thing only if you sit exactly on the sensor's axis. Seated 200 mm to its left and facing the middle of the screen, your head really is turned by 11.7°, and the reading says so — correct as a measurement, unusable in a game, because the posture you consider "straight ahead" is whatever you happen to sit in.

Recentring stores your current pose and subtracts it from everything the outputs receive. Set it the way you actually sit:

| Where | How |
|---|---|
| GUI | Calibration card → **Set** (next to **Clear**, which goes back to device coordinates) |
| Command line | `osg-recenter`, or `osg-recenter --clear` |
| Hotkey | bind `osg-recenter` to a key in your desktop's shortcut editor |
| Tray | **Set centre point** in the `osg-tray` menu |

There is no built-in global hotkey, and that is not an oversight: on Wayland an application cannot grab a shortcut for keys it does not have focus for, which mid-game it never has. Shortcuts belong to the compositor, so the reliable route is the desktop's own shortcut editor pointing at the `osg-recenter` command. On KDE: *System Settings → Keyboard → Shortcuts → Add Command*.

The daemon refuses to recentre while it cannot see a head — an invalid frame reads as zeros, and storing those would put the origin on the sensor itself.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | Bool | `false` | Whether the stored pose is subtracted. `false` means the outputs get device coordinates. |
| `yaw`, `pitch`, `roll` | Float (degrees) | `0.0` | The remembered rotation. |
| `x`, `y`, `z` | Float (mm) | `0.0` | The remembered position. `z` is the distance to the tracker, around 600–1000 mm seated. |

Written by the recentre command; editing it by hand works but is rarely what you want. It is stored in the configuration so that it survives a restart — a centre you have to set again after every login is one nobody sets.

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
| `host` | String | `"127.0.0.1"` | Target IP for UDP packets. Only `127.0.0.1`, `::1` or `localhost` are accepted through the GUI or the IPC `set_config` call; a genuinely remote target has to be edited into `config.toml` directly, bypassing that check. |
| `port` | Int | `4242` | UDP port. Must match OpenTrack setting. Valid range enforced by `set_config`: 1024–65535. |

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
| `curve` | List of points | linear | Response curve as list of [x, y] control points, 2 to 7 points, sorted by `x`. Allows nonlinear response. |

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

### [star_citizen]

```toml
[star_citizen]
lug_prefix = ""
runner_path = ""
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `lug_prefix` | String | `""` | The Wine prefix LUG-Helper (or the setup wizard's manual entry) uses for Star Citizen. |
| `runner_path` | String | `""` | Path to the Wine/Proton runner used to launch it. |

Filled in automatically by the setup wizard or the guided assistant's
LUG-Helper step — see [§9](#9-star-citizen--lug-helper).

---

### [display]

```toml
[display]
configured = false
monitor = ""
screen_width_px = 0
screen_height_px = 0
marker_left_px = 0.0
marker_right_px = 0.0
marker_distance_mm = 185.0
```

The result of the alignment step (GUI → Calibration card → **Align**,
`gui.actions.display` = *Align the device with the screen*). Only the
**measurement** is stored; pixel density, physical screen width and
tracker position are derived from it every time (via read-only properties
on the settings object — `px_per_mm`, `screen_width_mm`,
`tracker_offset_mm`, `tracker_offset_norm`), so no stored number can drift
away from what it was computed from.

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `configured` | Bool | `false` | `false` until the step has been run. Every derived value counts as unknown while it is. |
| `monitor` | String | `""` | The screen it was measured on (e.g. `"DP-2"`). The measurement is valid for that one only. |
| `screen_width_px` / `screen_height_px` | Int | `0` | Resolution of that screen at the time of the measurement. |
| `marker_left_px` / `marker_right_px` | Float | `0.0` | The two line positions the user settled on, in pixels from the left edge. |
| `marker_distance_mm` | Float | `185.0` | Physical distance between the marks on the device. A constant of the ET5; change it only for different hardware. |

**What it is used for today:** once `configured` is true, the daemon
converts `gaze_deadzone_px` from pixels into a fraction of the actual
screen size instead of assuming a fixed canvas, so the same pixel value
means the same physical distance on any monitor. The horizontal geometry
(pixel density, screen width, tracker offset from centre) is not yet fed
into the gaze-to-screen mapping itself. Run the step again whenever the
physical setup changes.

**How the alignment window works:** it opens fullscreen on the detected
monitor. Two lines are dragged onto the two marks physically printed on
the device, 185 mm apart, with click-and-drag and arrow keys (1 px per
press, 10 px with a fast modifier) for fine adjustment. Saving sends the
measurement to the daemon over IPC (`set_config` with a `display` block);
ESC cancels without saving.

---

## 7. Operation & Features

### osg-tray — the status icon

`osg-tray` puts openstargazer in the panel and keeps it there after the configuration window is closed. It is installed to start with your session; start it by hand with `osg-tray`.

The first line of the menu is the status, refreshed every three seconds, and it distinguishes three states that are easy to confuse:

| Line | Means |
|---|---|
| *tracking, 33 fps* | daemon running, tracker connected, data flowing |
| *running, no tracker* | daemon running, device absent or claimed by something else |
| *daemon stopped* | nothing is running — the service is stopped or was never started |

Below it: **Set centre point** (the same as `osg-recenter`), a **Tracking** checkbox, **Settings…** (opens the configuration window), and a **Service** submenu with *Start*, *Restart*, *Stop* and *Remove…*.

Everything under *Service* that changes state asks before it acts, and says what the answer costs — stopping the daemon takes head tracking away from a running game, and removing the service also stops it from returning at the next login. Removing does not uninstall the program: `osg-setup` puts the service back.

It is a separate program because the tray libraries are GTK 3 while the configuration window is GTK 4, and one process cannot load both.

**If no icon appears:** the tray needs an AppIndicator library. On Fedora: `sudo dnf install libappindicator-gtk3`. Ayatana's newer `libayatana-appindicator` works too — both names are tried.

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

# Force a backend for this run only
osg-daemon --backend stream-engine
```

**Daemon flags:**

| Flag | Description |
|------|-------------|
| `--mock` | Synthetic data instead of real hardware (~90 Hz, sinusoidal) |
| `--verbose` / `-v` | Detailed logging (DEBUG level) |
| `--config PATH` | Alternative path to config.toml |
| `--backend {native,stream-engine}` | Overrides `[device] backend` / `[input] source` for this run only |

**Auto-reconnect:** The daemon automatically reconnects every 2 seconds on device loss.

`faulthandler` is enabled in the daemon process, so if the systemd
watchdog kills it for hanging, the journal gets a Python traceback instead
of an opaque libc crash.

---

### osg-config (GUI)

```bash
osg-config
```

The GTK4/libadwaita settings window. On the first run — or after **Run
setup again** — it opens the [guided assistant](#the-graphical-guided-setup-in-osg-config);
otherwise it opens the overview, a grid of cards:

| Card | What is behind it |
|------|-------------------|
| **Calibration** | Gaze calibration, the live preview, the screen alignment, the neutral point, and the axis preview |
| **Games** | Which game was detected and set up |
| **Output** | OpenTrack UDP and FreeTrack, and the **UDP port** |
| **Gaze preview** | Opens the fullscreen overlay showing where you are looking |
| **Curves** | The per-axis response curves |
| **Settings** | Extended head tracking, re-running setup, the background service, and the language |

Above the grid sits the status line: a coloured dot, what the tracker is
doing, and the on/off control. Below it, the header carries the language
picker, the profile menu and three state dots (service · head tracking ·
output).

**Turning the device off and on:**

The button beside the status line disconnects the device from the daemon
(the tracker's LEDs go out) and reconnects it, without stopping the daemon
itself.

| State | Effect |
|-------|--------|
| On  | Device connected, tracking active, LEDs on |
| Off | Device closed, no tracking, LEDs off |

Switching off takes about a third of a second, switching on is immediate.
The status line follows the daemon rather than the button, so a change made
elsewhere — the tray icon, a scripted IPC call — shows up here too.

**The Calibration card** holds, beyond the calibration run itself:

- A live preview of the current gaze position on a schematic screen.
- **Align** — opens the [display alignment window](#display).
- **Set** / **Clear** — the [neutral point](#neutral_pose), next to the gaze
  calibration: both answer what "straight ahead" means for the person in
  the chair, one for the eyes and one for the head.
- **Axis preview** (**Show**) — opens a live readout of all six axes with
  the value that actually leaves the daemon, both filtered/curved/scaled
  and raw. An axis a source cannot produce (yaw/pitch on `et5_native`) is
  marked unsupported with the reason, rather than showing a permanent
  zero — the same table the axis window uses is keyed by the *active
  source*, not by backend, so it stays correct if you flip between
  `et5_native` and `et5_ttp_camera`.

**The output port** is on the Output card. OpenTrack listens on 4242 by
default; anything from 1024 to 65535 is accepted, and the daemon refuses
the rest rather than storing a port nothing can use.

**The Settings card** carries:

- **Extended head tracking** — the switch that turns the camera source on
  and off (`et5_ttp_camera` against `et5_native`, see `[input]`), with
  what it costs written in the row. When `onnxruntime` or the weights are
  missing, the switch is greyed out and the row says which of the two it
  is — the two have different fixes. The daemon binds its source at
  start-up, so the row asks for a restart after a change and offers a
  button for it when the systemd user service is installed. Nothing is
  swapped out underneath a running calibration.
- **Run setup again** — re-opens the guided assistant from page 1.
- The **background service** — start, restart, stop, install, remove. It
  is the same service the tray icon controls, and it asks the same
  questions before stopping or removing it.
- The **language** list — every shipped language as a radio row, applied
  immediately.

**Profiles** are in the header menu: switch between saved ones, save the
current settings under a name, or open the manager to rename and delete.
The button shows which profile is in force.

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

See [§4](#4-first-start--setup-wizard) for the full flow. Can be run again
at any time to:
- Download Stream Engine binaries (optional — only needed if you use the `stream-engine` backend; the native backend needs no download)
- Update LUG-Helper configuration
- Regenerate OpenTrack profile
- Change extended head tracking on or off
- Reinstall the systemd service or udev rule

---

### IPC Interface

The daemon exposes a Unix socket at `~/.local/share/openstargazer/daemon.sock`,
one JSON object per line, `{"id": ..., "method": ..., "params": {...}}` in,
`{"id": ..., "result": {...}}` or `{"id": ..., "error": "..."}` out.

**Security:**
- Socket and directory are restricted to `0600`/`0700` (owner only)
- Only whitelisted methods are accepted
- Requests are limited to 64 KiB per line
- UDP output target must be `127.0.0.1`, `::1` or `localhost`; port must be 1024–65535

**Live status without polling — `subscribe`:**

A connection can send `{"method": "subscribe", "params": {"interval_s": 0.1}}`
once. `interval_s` is clamped to 0.015–5.0 s (default 0.1 s). From then
on, every time the tracker produces a new frame **and** at least
`interval_s` has passed since the last push, the server sends an
unsolicited message of its own — not a reply to a request:

```json
{"event": "status", "data": { …exactly the get_status shape below… }}
```

`unsubscribe` stops the pushes on that connection. Two built-in windows —
the gaze overlay and the axis preview — use this instead of polling, which
used to mean opening and closing a socket roughly thirty times a second
each; the settings overview still polls `get_status` every 100 ms, since
it only needs to refresh a status line rather than redraw at frame rate.

Available methods:

| Method | Description |
|--------|--------------|
| `ping` | Returns `{"pong": true}` |
| `get_status` | Connection status, FPS, `tracking_enabled`, latest frame — see field list below |
| `get_config` | Current configuration — see field list below |
| `set_config` | Update configuration — see below |
| `set_tracking_enabled` | `{"enabled": bool}` → pause tracking (`false`, LEDs off) or resume (`true`); returns `{"tracking_enabled": ..., "connected": ...}` |
| `recenter` | Stores the current head pose as the new neutral point (see `[neutral_pose]`); returns `{"recentered": true, "neutral_pose": {...}}`, or an error if no valid pose is available |
| `clear_recenter` | Clears the neutral point back to device coordinates; returns `{"recentered": false}` |
| `start_calibration` | `{"mode": 5\|9, "aspect": float?}` → returns the point layout, `settle_delay`, `seconds_per_point` |
| `calibration_collect` | `{"index": int}` → collects samples for that point, returns the running mean gaze |
| `calibration_finish` | Fits, checks it, stores it only if usable; returns the per-point report |
| `calibration_cancel` | Discards the run, keeps the stored calibration |
| `list_profiles` | List profiles |
| `activate_profile` | `{"name": str}` → activate a profile |
| `subscribe` / `unsubscribe` | See above |

**`get_status` fields:**

| Field | Meaning |
|---|---|
| `connected` | Tracker reachable |
| `tracking_enabled` | Whether tracking is currently paused |
| `backend` | The `[device] backend` value in force |
| `source` | The `[input] source` value in force |
| `calibrated` | Whether a calibration is stored (`coeff_x` non-empty) |
| `fps` | Tracker frame rate, `0.0` if the last frame is stale |
| `gaze_xy` | What the outputs receive: filtered and calibrated |
| `gaze_raw_xy` | The untouched device reading |
| `gaze_valid` | Whether the current gaze sample is usable |
| `head_pose` | `{x, y, z, yaw, pitch, roll, pos_valid, rot_valid, pos_from_one_eye, valid}` — what the outputs receive: filtered, and curved/scaled/inverted, with the neutral pose subtracted |
| `head_pose_raw` | The same shape, untouched device reading |
| `frame_age_s` | Seconds since the last frame, or `null` |
| `pipeline_fps` | Rate the pipeline itself is producing output at |
| `recentered` | Whether `[neutral_pose] enabled` is on |

`head_pose`/`head_pose_raw` report `pos_valid` and `rot_valid`
independently, since the device can locate a head without being able to
say how it is turned; `pos_from_one_eye` flags a position derived from a
single eye (less reliable) rather than both.

**`get_config` fields:** `filter` (all five `[filter]` keys), `output`
(`opentrack_udp` and `freetrack_shm` enabled/host/port), `tracking.mode`,
and `input` — `source` (running source), `available` (sorted list of
every registered source name), `camera` (`{onnxruntime, weights, ready}`
readiness for `et5_ttp_camera`).

**`set_config`:** accepts partial updates under `filter`, `output`
(`opentrack_udp`, `freetrack_shm`), `display`, and `input.source`.
Everything applies immediately except `input.source`: the daemon binds
its source at start-up, so changing it is stored and the response carries
`{"saved": true, "restart_required": true}`. An unknown source is refused
by name (`Unknown input source '...'. Known sources: ...`). A
non-loopback `output.opentrack_udp.host` or an out-of-range port raises
an error instead of being saved.

**Calibration sequence:** `start_calibration({"mode": 5})` →
`calibration_collect({"index": 0})` for each point in turn →
`calibration_finish()`. `calibration_finish`'s result carries `success`,
`residuals` (per-point list), `mean_residual`, `message` (the reason on
failure), and `points` — each with its coordinates, sample count and
residual, used to colour the result screen.

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

Enables all 6 degrees of freedom (Yaw, Pitch, Roll, X, Y, Z) plus gaze point — six only with `et5_ttp_camera` or a licensed `et5_stream_engine`; four (position, roll, gaze) on the default `et5_native`.

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

## 10a. Language

Every user-facing string of the installer, the setup wizard and the GUI comes
from a language file. Five ship, and all five are complete:

```
openstargazer/locales/en.lang     English (the reference)
openstargazer/locales/de.lang     Deutsch
openstargazer/locales/fr.lang     Français
openstargazer/locales/it.lang     Italiano
openstargazer/locales/es.lang     Español
```

The format is one entry per line, `#` starts a comment:

```
install.title = openstargazer Setup
backend.chosen = Backend: {backend}
```

`{name}` placeholders are filled in at runtime — keep them spelled exactly as
in `en.lang`. A test refuses a translation that spells one differently or
drops it, because that is a crash at the moment the string is shown rather
than a wrong word.

Switch language in the settings window — the globe in the header, the
Settings card's language list, or the setup start screen — or from the
environment:

```bash
OSG_LANG=fr osg-config
```

Selection order: `OSG_LANG`, then the language saved in `config.toml`
(`[general] language`), then `LC_ALL`, `LC_MESSAGES`, `LANG`, then
English. A region suffix is stripped, so `de_DE.UTF-8` finds `de.lang`.
Every entry point that can show text (`osg-config`, `osg-tray`,
`osg-recenter`, `osg-setup`) applies the saved language at start-up, so a
choice made in one of them holds for the others without re-detecting the
system locale each time.

### Adding a language

1. Copy `en.lang` to `<code>.lang`, e.g. `pt.lang`
2. Translate the text to the right of each `=`
3. Add a display name for it to *every* shipped file
   (`gui.language.pt = Português`), because the picker shows all languages
   at once, whichever one is active
4. Select it: `OSG_LANG=pt osg-config`

Keys you have not translated fall back to English individually, so a partial
translation is usable from the first line. That fallback is a safety net for
a translation in progress, not a plan for a shipped one — a window answering
half in one language and half in another is worse than either.

Log messages are deliberately not translated — they stay English so that bug
reports remain readable.

---

## 11. Calibration

Calibration improves gaze accuracy by fitting a polynomial that maps where
the tracker thinks you are looking onto where you actually looked.

### Starting Calibration

The daemon must be running — it owns the eye tracker and collects the
samples, while the GUI shows the dots and paces the run.

```bash
# Via GUI: osg-config → Calibration card → Calibrate
# Or from the setup assistant's own calibration page
# Or from the text wizard: osg-setup --cli, step 6
```

Look at each dot until it disappears. Five or nine points are supported;
five is enough for most setups. Afterwards the per-point error is shown as
coloured circles — green is good, red means that point should be repeated.

- **Enter** accepts the result. It is written to `config.toml` and applied
  to every gaze sample from that moment on; no restart needed.
- **ESC** cancels. The previously stored calibration stays untouched.

### When a run is rejected

Not every run produces a usable mapping, and a broken one is worse than
none — left alone it silently overwrites a possibly better previous one. A
run therefore has to clear three bars, or it is discarded and the stored
calibration stays untouched:

- **Samples per point.** A point that delivers less than 60% of the
  configured `samples_per_point` is left out of the fit. Its mean would be
  mostly noise and would pull the curve away from every other point. If
  fewer than three usable points remain, the run fails. Collection for a
  single point is also capped at 5 seconds regardless of how few samples
  arrived, so a lost tracker cannot stall the whole run indefinitely.
- **Deviation.** At most 0.06 on average and no more than 0.10 of the
  screen at any single point — two bars, because one ruined point
  disappears in the average of four good ones. On a 5120 px wide screen
  0.10 is roughly 500 px.
- **Reachable range.** Across the whole raw range the mapping must still
  cover at least half of the calibrated range. A fit that squeezes
  everything into a narrow band makes parts of the screen unreachable.

The result screen shows how many samples arrived at each point and how far
it is off; dropped points appear as an open red ring. If the run is
rejected, the screen names the reason and shows the same per-point numbers.
The usual cause is a point where the tracker lost your gaze — check your
seating distance and calibrate again.

### How it is stored

```toml
[calibration]
polynomial_degree = 2
samples_per_point = 30
settle_delay_s = 1.0
min_collect_seconds = 3.0
aspect_ratio = "auto"
coeff_x = [...]
coeff_y = [...]
```

| Setting | Meaning |
|---------|---------|
| `polynomial_degree` | Degree of the fit per axis. 2 is a good default; higher degrees overfit five points. |
| `samples_per_point` | Minimum gaze samples per dot. At ~33 Hz, 30 samples take about a second — but the duration is set by `min_collect_seconds`, not by this number. |
| `settle_delay_s` | Pause after the dot appears, before anything is recorded. The dot is already visible: this is the time to look at it. |
| `min_collect_seconds` | Minimum length of the recording itself. Together with `settle_delay_s` every dot stands for four seconds by default. Samples arriving during the extra time are kept. Collection for one point never exceeds 5 seconds total, even if `samples_per_point` hasn't been reached by then. |
| `aspect_ratio` | Screen shape the dots are spread over. `"auto"` takes the monitor the GUI runs on; `"32:9"` or a plain number overrides it. |

### Where the dots are placed

On 16:9 the dots sit at 10% and 90% of the screen. On a wider screen the
same fractions push the outer dots much further apart in angle, into the
region where the tracker sees fewest glints and gets least reliable. The
horizontal margin therefore grows with the aspect ratio, capped at the 21:9
value — so 32:9 is calibrated like 21:9, with dots at 19.5% and 80.5%.
Vertical placement never changes. Set `aspect_ratio` by hand if your
monitor is detected wrongly, e.g. on a spanned multi-monitor desktop.

### Resetting Calibration

```bash
# Edit config.toml and empty both coefficient lists:
coeff_x = []
coeff_y = []
```

Empty lists mean "no correction" — the raw gaze point is passed through.

---

## 12. Profiles

A profile is a named copy of the whole configuration — calibration, curves,
output, input source, everything in `config.toml`. They exist so one setup
can be kept for Star Citizen and another for desktop use without editing
anything by hand.

They live as individual files:

```
~/.config/openstargazer/profiles/<name>.toml
```

From the profile menu in the settings window's header:

| Action | What it does |
|--------|--------------|
| **Save current settings** | Writes everything as it stands right now under a name. An existing name is overwritten. |
| Pick a name from the list | Loads that profile and makes it the live configuration |
| **Manage profiles** | The same, plus rename and delete |

The header button shows which profile is in force. That is a stored label
(`[general] active_profile`) rather than something inferred: a profile that
has been activated is otherwise indistinguishable from one that was never
used, because activating it copies its contents into `config.toml`.

Deleting asks first — a profile can represent a calibration run — and
deleting the active one clears the label rather than leaving it pointing at
a file that is gone.

Profiles are also reachable over the IPC interface (`list_profiles`,
`activate_profile`).

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

If the library is present and the daemon still logs `INSUFFICIENT_LICENSE`
on `gaze_data`/`head_pose`, that is not a missing file — see the licence
note under `[device]` above. Most retail ET5 units cannot use this
backend at all; switch to `et5_ttp_camera` instead.

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

5. After a process crashed while holding the device, a stale usbfs claim
   can leave it reporting `Resource busy` to everything else. Replug the
   device, or reset it at the USB level, to clear it.

---

### Problem: pip error (PEP 668)

**Error:**
```
error: externally-managed-environment
```

The installer handles this automatically with a venv. For manual installation:

```bash
python3 -m venv --system-site-packages ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install ".[gui,tray]"
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

**Solution: adjust filter** — smoother at rest, at the price of about 100 ms more delay:
```toml
[filter]
one_euro_min_cutoff = 1.0
one_euro_beta = 0.05
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
one_euro_min_cutoff = 3.0
one_euro_beta = 0.15
```

Beyond roughly these values the filter is no longer what you are feeling: one camera frame lasts 30 ms, and OpenTrack plus the game add their own delay.

Also: set OpenTrack filter to **none**.

---

### Problem: No head yaw or pitch, only position and roll

This is the default `et5_native` backend behaving correctly, not a bug —
the gaze stream carries no head rotation at all. Turn on **Extended head
tracking** (setup wizard, or the Settings card's switch) for both axes
from the device's camera, or use `backend = "stream-engine"` if your unit
happens to carry a Stream Engine licence (pitch only, no yaw, and only on
units that have it — see `[device]`).

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

Or from the install.sh menu: choose **option 6 – Create debug report**.

The script creates a file at:
```
~/openstargazer-debug-YYYYMMDD-HHMMSS.txt
```

**What the report contains:**
- System: OS/distro, kernel version, architecture, RAM, CPU
- Python: version, pip/venv status, `pip show openstargazer`
- Tracking backend: the configured backend from `config.toml`, and
  whether `pyusb` is importable by the Python that would actually run the
  daemon (venv-aware)
- USB devices: Tobii device detection via `lsusb`
- Service status: `openstargazer` user service and last 50 journal lines
- Tobii USB service: `tobiiusb` system service status (only relevant to a
  manually added Stream Engine install)
- Install paths: existence check for all key files (stream engine, udev rules, venv, desktop entry)
- opentrack: version and config directory contents (filenames only)
- Config file: `~/.config/openstargazer/config.toml` with home paths redacted
- Install log: last 100 lines of `~/.local/share/openstargazer/install.log`
- udev rules: content of `/etc/udev/rules.d/70-openstargazer.rules`

Attach the resulting file to a [new GitHub issue](https://github.com/1psconstructor/openstargazer/issues/new).

> **Privacy note:** The script redacts your username throughout the whole
> report — not only in the config section, but also in `systemctl status`
> output, the journal excerpt, the install log and the list of checked
> paths. No passwords or tokens are collected.

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
pip install --user ".[gui,tray]"   # or venv-pip
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

**Q: Do I get all six axes out of the box?**
A: No — a default install gives head position, roll and the gaze point (four axes). Yaw and pitch need **Extended head tracking** turned on (the ET5's camera plus the project's own model), or a Stream Engine-licensed device. See [Extended head tracking](#input) and the Known Limitations note above.

---

## 17. License

**GPL-3.0-or-later** — see the `LICENSE` file. Every source file carries an
SPDX header (`# SPDX-License-Identifier: GPL-3.0-or-later`).

Up to and including v0.2.2 this project was MIT-licensed, and those
releases stay MIT — a licence already given cannot be taken back.
Everything from v0.3.0 on is GPL-3.0-or-later. In practice: use it, change
it, sell it — but if you pass a changed version on to someone else, they
get the source under the same terms.

The shipped head-pose weights (`openstargazer/models/head-pose.onnx`) are
released under the same licence, trained from scratch on `replicantface`
(MIT-licensed synthetic data) — no pretrained checkpoint and no
non-commercial training data went into them.

---

## 18. Links

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

*This handbook covers openstargazer v0.5.0.*
