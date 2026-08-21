# Changelog

All notable changes to openstargazer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0]

### Added
- **Native USB backend** (`openstargazer/native/`): a self-contained pyusb
  driver for the Eye Tracker 5 (`2104:0313`). No Tobii Stream Engine, no
  `tobiiusbserviced`, no proprietary binaries. Verified on hardware at
  33 Hz. Protocol facts corroborated against the independent clean-room
  implementation tobiifree (GPL-3.0); no code taken over. It is the
  default backend.
- **Own head-pose weights ship with the project**, under GPL-3.0. Trained
  from scratch on `replicantface` (MIT, 100 000 synthetic faces with pose
  annotations) — no pretrained checkpoint, no non-commercial training
  data. The file is `openstargazer/models/head-pose.onnx`, loaded by
  default; no download and no separate fetch is needed. The face patch it
  reads is cropped from the gaze stream's own eye positions.
- **Extended head tracking can be turned on and off without editing a
  config file** — in the setup wizard and in the settings window. It is
  off by default; turning it on adds yaw and pitch on top of the four
  axes the native backend gives.
  - The wizard step names what it costs before it asks: `onnxruntime` as
    an extra package (`pip install 'openstargazer[camera]'`), about 6 ms
    per picture (a fifth of one core at 33 Hz), and that the pictures are
    read, measured and dropped — nothing stored, nothing leaving the
    machine.
  - The settings window carries the same choice as a switch, greyed out
    with the reason on it when `onnxruntime` or the weights are missing.
- **The head keeps being tracked when the eyes are not.** The patch the
  pose network reads is cut from the eye positions the gaze stream
  reports, so losing the eyes lost the head — on 69 % of frames during a
  wide sweep. The patch is now carried forward, and the network's own
  predicted spread decides whether to keep believing it. Both halves
  measured, not chosen: on the head 4.69° median spread, on a far corner
  of the same picture 21.65°, eleven degrees of empty space between the
  two bands.
- **Real gaze calibration.** The daemon collects the samples and the GUI
  paces the run over IPC (`start_calibration` → `calibration_collect` →
  `calibration_finish`). The fitted polynomial is stored in `config.toml`
  and applied to every gaze sample by the pipeline. Cancelling with ESC
  keeps the previous calibration.
- **A status icon** (`osg-tray`). The panel gets an entry that says
  whether the daemon is running and whether it can see the tracker, and a
  menu for what one reaches for without opening a window: set the centre
  point, toggle tracking, open the settings, and start, restart, stop or
  remove the service. Everything that changes state asks first, and says
  what the answer will cost.
- **A neutral pose** (`[neutral_pose]`, GUI → *Centre point*,
  `osg-recenter`). The tracker reports where a head is in front of the
  sensor, which is not the same as how far it has moved from where its
  owner sits: 200 mm to the left of the sensor and facing the middle of
  the screen, a head really is turned by 11.7°, and the outputs said so.
  Recentring stores the current pose and subtracts it from all six axes
  before they leave the daemon. Kept in the configuration and survives a
  restart. There is no built-in global hotkey — a Wayland client cannot
  grab a shortcut for keys it has no focus for, and mid-game it never has
  focus — so `osg-recenter` exists to be bound in the desktop's own
  shortcut editor.
- **A graphical guided setup, and a settings window rebuilt around it.**
  `osg-setup` opens on a small language / graphical-or-terminal choice;
  picking graphical hands off to `osg-config`, which is the one place
  that decides — from `settings.general.setup_completed` — whether to
  show the guided dialog or the settings overview (Calibration, Games,
  Output, Gaze preview, Curves, Settings). Both setup paths end at the
  same settings window and call the same underlying functions, not a
  second implementation of each step.
- **The settings window can do what the tray icon can.** Start, restart,
  stop and remove the background service, and set up autostart.
- **The OpenTrack UDP port is configurable from the window** — until now,
  pointing OpenTrack at anything other than 4242 meant editing
  `config.toml` by hand.
- **Profiles can be saved, renamed and deleted**, and the window says
  which one is in force (`[general] active_profile`).
- **The curve editor takes a pill per axis instead of six tabs, and up to
  four extra control points per curve.** Double-clicking an empty spot on
  the curve adds a point; double-clicking or right-clicking an interior
  point removes it.
- **The IPC server can push instead of being polled.** A connection sends
  `subscribe` once and then receives a status line every time the tracker
  produces a new frame. The gaze overlay and the axis preview window —
  previously opening and closing a socket roughly thirty times a second
  each — now hold one connection open instead.
- **Fullscreen gaze overlay** (GUI → *Gaze overlay*). A transparent
  fullscreen window that draws the gaze point as a bubble over the whole
  desktop, so a calibration can be judged where it is actually used. ESC
  closes it.
- **Head tracking preview** (GUI → *Check head movement*). A live readout
  of the six axes with the value that actually leaves the daemon. Axes a
  backend cannot produce are marked as unsupported rather than showing a
  permanent zero.
- **Display alignment step** (GUI → *Align the device with the screen*)
  and a `[display]` section in `config.toml`. Two lines along the bottom
  edge are dragged onto the two marks on the device, 185 mm apart; from
  that the pixel density, the physical screen width and the tracker's
  horizontal offset from the screen centre are derived, cross-checked
  against the monitor's own EDID figures.
- **One place decides what the drawn surfaces look like**: `gui/design.py`
  holds every colour, type size, spacing step and radius the painted
  windows use.
- **The fullscreen surfaces no longer turn black in one frame.**
  Calibration and the alignment step stay dark on purpose, but coming out
  of a light main window the switch was jarring; the ground now blends
  from the desktop's brightness over 120 ms.
- Five languages ship complete: **English, German, French, Italian and
  Spanish** — all 454 keys, the same placeholders in every file. Keys
  missing from a translation fall back to English individually. Log
  messages stay English on purpose so bug reports remain readable.
- `--backend {native,stream-engine}` for `osg-daemon`, and `backend`
  under `[device]` in `config.toml` (the older name for `source`; both
  still work).
- `get_status` over IPC reports the active source, whether a calibration
  is stored, and whether the camera source could run at all; `set_config`
  accepts a source, refuses an unknown one by naming the real ones, and
  answers `restart_required`.
- The debug report states the configured backend and whether pyusb is
  importable.

### Changed
- **The licence is now GPL-3.0-or-later.** Up to and including v0.2.2
  this project was MIT, and those releases stay MIT — a licence already
  given cannot be withdrawn. Every file carries an SPDX header. Anyone
  may use, change and sell this project; anyone who passes on a changed
  version passes on its source under the same terms.
- **The native backend is the default.** `stream-engine` stays available
  and is still the only backend that reports head pitch on its own.
- **No head rotation on the native backend, and it is not reconstructable
  from the gaze stream at all.** All 39 fields the device sends were
  checked against a prescribed turn and a prescribed tilt: no field
  carries the rotation, and the depth difference between the eyes — which
  an earlier build used to derive yaw from — swings ±10 mm under a pure
  tilt where geometry says it must be zero. Turn and tilt come from the
  camera source instead (see above), which is off by default; a default
  install gives position, roll and the gaze point — four of the six axes.
- **The head axes are filtered four times less heavily**
  (`one_euro_min_cutoff` 0.5 → 2.0, `one_euro_beta` 0.007 → 0.1), while
  still removing 59 % of the device's jitter. An existing `config.toml`
  keeps its own values — see `[filter]` in the handbook for the measured
  table.
- **`get_status` reports the head pose the outputs actually receive** as
  `head_pose`; the device's raw reading stays available separately as
  `head_pose_raw`, with validity reported for position and rotation
  independently.
- **Calibration points follow the screen's aspect ratio.** 16:9 keeps a
  0.10/0.90 margin, 21:9 and wider (32:9 included) get 0.1952/0.8048. The
  GUI reports its monitor; `[calibration] aspect_ratio` overrides it.
- **A calibration run is checked before it is stored.** A point below
  60 % of `samples_per_point` is left out of the fit, and the fit itself
  has to stay within 0.06 mean and 0.10 per-point deviation and keep at
  least half the calibrated range reachable. A run that fails is
  discarded with a reason; the stored calibration is kept.
- The live preview polls the daemon every 100 ms instead of every 250 ms.
- An unknown `backend` value in `config.toml` warns and falls back to the
  default instead of silently picking the wrong path.

### Fixed
- **The shipped head-pose weights are actually found.** The lookup
  pointed only at `~/.local/share/openstargazer/models/`, while the
  weights ship inside the package. An unconfigured lookup now takes the
  user directory first (still an override), then the package directory.
  Measured against the device before and after: rotation valid on 0 % of
  frames, then on 100 %.
- **Switching the device off now switches the device off**, and no
  longer takes three seconds. The camera source's pause used to set a
  flag and nothing else — the tracker kept its lights on and kept
  streaming while the outputs alone fell silent, and the shutdown waited
  on a confirmation the firmware never sends. Off is now 0.31 s.
- **One attached client could stop the daemon from stopping.** Every
  restart with a front end open ran into systemd's 45-second timeout and
  ended in SIGABRT; the daemon hangs up on its clients first now.
- **The camera source used up to 16 cores for one small picture.**
  `HeadPoseModel.load()` built its ONNX sessions without
  `SessionOptions`, so onnxruntime sized its intra-op thread pool to the
  machine's core count. Pinning the thread counts to 1 brought a daemon
  reporting 1116 % CPU down to ~40 %.
- **The debug report is redacted in all of it, not only in the config
  section.** `systemctl status`, the journal, the install log and a list
  of checked paths all carried the user's name in full, in a file the
  handbook tells people to attach to a public issue. The whole report now
  goes through the redaction.
- **README and both handbooks promised six axes to a default install that
  delivers four.** Corrected, together with the `[input]` reference
  section that was missing from both handbooks.
- **The graphical guided setup was unreachable.** `install.sh` generates
  a fallback OpenTrack profile by running the whole setup wizard silently
  in the background before the user's own run of it -- and the wizard's
  last line marks setup complete. By the time the real run asked the
  user to choose "Graphical" and handed off to `osg-config`, it already
  believed setup was done and opened the settings overview instead of the
  guided dialog, every time. The silent pass now only detects LUG-Helper
  and writes the profile; it no longer runs the wizard or touches that
  flag. The language/mode choice also moved to right after the package
  itself is installed, ahead of the udev rule, the service and the
  desktop entry, instead of after them.
- **The installer no longer asks whether to install Tobii's Stream
  Engine.** A fresh install always sets up the native backend; the
  Stream Engine binaries can still be fetched by hand
  (`scripts/fetch-stream-engine.sh`) and `backend = "stream-engine"` set
  in `config.toml` directly, and `osg-setup --cli`/repair still recognise
  and fix an existing install that uses it.
- **A language chosen in the settings window or the setup chooser did not
  survive the process that chose it.** `set_language()`'s own default only
  ever autodetects from `OSG_LANG` or the system locale; nothing at
  start-up read the choice back from `config.toml`, so `osg-config`,
  `osg-tray`, `osg-recenter` and the setup wizard all redetected the
  system language on every fresh launch regardless of what was picked and
  saved moments earlier -- including by the setup chooser itself, handing
  off to a freshly-launched `osg-config` that ignored the language just
  selected in the same breath. Every entry point that can show text now
  applies the saved language at start-up, with `OSG_LANG` still taking
  priority as an explicit per-run override.
- **`install.sh` gets a `--lang <code>` flag** to force its own language
  for one run, independent of `OSG_LANG` and the system locale; exported,
  so the setup wizard it hands off to inherits the same choice.
- **Calibration is paced twice as slowly.** `settle_delay_s` (0.5 s → 1 s)
  and `min_collect_seconds` (1.5 s → 3 s) doubled -- four seconds per dot
  now, not two. The previous pacing was itself a fix for dots going by
  too fast to aim at; live testing found that still rushed.
- Finishing a fresh install now says to reboot once, so the udev rule
  and the `plugdev` group membership it may have just added are both
  actually in effect.
- **The guided dialog's hand-off looked like a hung installer.** Launching
  `osg-config` at the end of either setup path used `Popen` without
  redirecting its output, so it inherited the terminal -- and GTK's own
  warnings about the settings window (below) kept printing into it long
  after `install.sh` itself had finished and returned. Detached properly
  now.
- **The settings window's default size was measured too short for its
  own content**, by exactly the height GTK spent every 100 ms status poll
  warning about: the header, status line, two full card rows and the
  footer needed 76 px more than 720 gave them. 800 now.
- **The language/mode chooser showed whatever placeholder icon the
  desktop keeps for a program it has never heard of.** It is the first
  window a fresh install can show, before `install.sh`'s own
  `install_desktop_entry` has copied anything into the system icon
  theme, and it never registered the source tree's own icons as a
  fallback the way `osg-config` already does. It does now.
- **The guided setup's udev step ran `sudo` from a button click with no
  controlling terminal at all.** `sudo` cannot ask for a password there
  and fails immediately -- silently, since the result was written into a
  label that the very same click replaced with the settings overview in
  the same instant, so nothing was ever visibly wrong either way. Now
  uses `pkexec`, which raises the desktop's own polkit dialog instead,
  and waits two seconds after showing the result before moving on.
- **That polkit dialog then asked three times in a row for the same
  click.** `install_udev_rules()` made three separate privileged calls
  (`cp`, then two `udevadm` commands); an interactive `sudo` session
  caches one authentication across all three, but `pkexec` re-asks on
  every separate invocation. One call now (`sh -c '... && ... && ...'`)
  instead of three.
- **A fresh install could ask for that authentication up to three times
  total, not just three within one click.** The terminal wizard's own
  service step already installs the udev rule once; `install.sh` then
  installed it again unconditionally afterward, and the guided GUI
  dialog's own Step 8 could attempt it a third time regardless of
  whether either of the other two had already succeeded. All three
  places now skip the rule if it is already there.
- **Uninstalling never told the icon cache anything had left.**
  `install_desktop_entry` rebuilds `~/.local/share/icons/hicolor`'s
  cache on the way in; `uninstall_desktop_entry` deleted the icon files
  on the way out but left the stale cache still claiming they were
  there, so the *next* fresh install's language chooser -- the first
  window it can show, before anything is reinstalled -- failed to load
  an icon that, per the cache, should have existed. Uninstall rebuilds
  the cache now too.
- **The one-line install (`bootstrap.sh`) broke its own daemon on the
  first restart.** `install.sh` installed the Python package editable,
  which keeps pointing at the directory it was installed from;
  `bootstrap.sh` downloads a release into a temp directory and deletes it
  the moment the installer returns. The service kept running until
  something restarted it -- a reboot, a crash, the settings window's own
  restart button -- and then failed with `ModuleNotFoundError`. Found by
  reproducing it: stop the daemon, remove the source tree, start it again.
  The install is a regular, non-editable one now, which copies the code,
  the shipped model weights and the locale files into place instead of
  pointing back at a directory that may no longer exist.
- **`install.sh`'s full uninstall crashed right after deleting your
  configuration and data**, and never reached its own summary: the log
  writer appended to a file in the directory that removal step had just
  deleted, without recreating it first. It also reported Tobii's
  Stream Engine binaries as "not found" when they were there but a
  privileged removal failed for lack of `sudo`, and left a running
  `osg-tray` sitting in the panel after removing only the file that
  would have started it next login.
- The card icons are drawn again instead of blotted: GTK renders a
  `-symbolic` icon as a silhouette, forcing `fill` on every shape and
  ignoring `stroke`, so several outline drawings came out as solid blobs.
- `osg-config --mock` (and `--verbose`) crashed on startup: `main()`
  handed `sys.argv` to `Gio.Application.run()` after `argparse` had
  already consumed it.
- The axis window no longer declares yaw and pitch impossible while they
  are arriving from the camera source; it now keys its "this source
  cannot do that" table by the active source rather than the backend.
- The axis window's "missing axes" banner no longer crashes the window
  the moment it has something to say.
- Roll no longer snaps level when the eyes are lost, and the settings
  page no longer claims the daemon is gone when the tracker was switched
  off from that same window.
- The calibration result no longer draws a stray line across the screen
  from the last point to every dot after it.
- Calibration dots go by slowly enough to look at: `settle_delay_s`
  (0.5 s) passes before the first sample is recorded, and
  `min_collect_seconds` (1.5 s) is a floor under the recording regardless
  of how quickly the sample count is reached.
- The tracking switch no longer jumps around under a click and refuses to
  come back on: the status poll now leaves the switch alone while a
  toggle is in flight.
- A disconnected tracker no longer reports a stale frame rate and a valid
  gaze — both fall to zero on a receive timeout.
- Enabling or disabling tracking is now logged, request and resulting
  state both.
- The native driver now explicitly asks the tracker to start streaming at
  startup instead of relying on a setting left over from a previous OS.
- The live preview shows the processed gaze position (filtered,
  calibrated) rather than the raw device reading; the raw reading remains
  available separately for diagnostics.
- Gaze is now filtered with its own `gaze_min_cutoff`/`gaze_beta` under
  `[filter]` — it used to pass through the pipeline untouched.
- A blink no longer drags the reported gaze towards the top-left corner:
  invalid `(0.0, 0.0)` samples bypass the filters and the last good
  position is held instead.
- `faulthandler` is enabled in the daemon, so a service killed for
  hanging prints a Python traceback instead of forty frames of libc.
- Calibration results were displayed but never applied; the coefficients
  now reach the pipeline.
- Rapidly reopening the device no longer leaves the gaze stream dead for
  the rest of the session.

### Security
- **The realm-authentication HMAC key is no longer shipped in this public
  repo.** It was only a defensive fallback for a non-zero `realm_type`
  that no tested device has ever reported; the driver now raises
  `ProtocolError` instead of authenticating if one ever does.

### Known limitations
- **No head pitch and no head yaw on the native backend without the
  camera source.** The ET5 does not report head rotation in its gaze
  sample at all — this is a sensor limit, not a bug. Turn on the camera
  source (see Extended head tracking above) for both, or use
  `backend = "stream-engine"` for pitch alone.
- After a crashed process, a stale usbfs claim can block the interface
  (`Resource busy`). Replug the device or reset it on the USB level.

## [0.2.2] – 2026-03-13

### Fixed
- `scripts/fetch-stream-engine.sh`: clears the executable-stack flag after
  downloading `libtobii_stream_engine.so`. Kernel 6.18+ refuses to load
  shared libraries with `GNU_STACK` flags `0x7` (RWE).
- `openstargazer/engine/loader.py`: Python 3.14 tightened ctypes type
  checking — `None` is no longer a valid `CFUNCTYPE` argument.
- `openstargazer/engine/loader.py`: corrected the argument order of
  `tobii_device_create`; the binary expects `(api*, url, device**,
  field_of_use)`, not the order given in the SDK docs. Fixes a segfault on
  connect.
- `openstargazer/daemon/tracker.py`: `tobii_head_pose_subscribe` returns
  `NOT_SUPPORTED` on the ET5; this is logged as a warning instead of
  aborting the connection.
- `openstargazer/daemon/tracker.py`: `wait_for_callbacks` returning
  `TIMED_OUT` is normal SDK behaviour and is no longer treated as a device
  disconnect.

### Added
- `TobiiGazeData` struct plus `tobii_gaze_data_subscribe` bindings; the
  primary gaze subscription now uses that stream, which reliably activates
  the ET5's IR LEDs, and falls back to `tobii_gaze_point_subscribe`.

## [0.2.1] – 2026-03-12

### Fixed
- `scripts/fetch-stream-engine.sh`: creates the user-local
  `tobiiusbservice` symlink the daemon expects.
- `setup/wizard.py`: no longer freezes at step 5 when stdin is closed.
- `scripts/install.sh`: runs the wizard with stdin from `/dev/null` during
  installation, and starts the daemon right after a fresh install.

### Added
- `pause_tracking()` / `resume_tracking()` and the `tracking_enabled`
  property: fully disconnects the device (LEDs off) and reconnects it
  without stopping the daemon.
- IPC command `set_tracking_enabled` plus the matching switch in
  `osg-config`.

## [0.2.0] – 2026-03-11

### Fixed
- `fetch-stream-engine.sh`: crash under `set -u`.
- `install.sh`: opentrack installation on Fedora 43 offers a fallback menu
  instead of aborting.

### Added
- `install.sh`: "Build from GitHub source" option for opentrack, and a
  persistent install log under `~/.local/share/openstargazer/install.log`.
- `scripts/collect-debug-info.sh`: collects a debug report with anonymised
  paths.
- `opentrack_config.py`: warns about GE-Proton runners needing
  `PROTON_VERB="runinprefix"`.

## [0.1.0] – 2026-03-08

### Added
- Initial release as openstargazer (renamed from tobii5-linux)
- Linux driver for the Tobii Eye Tracker 5 via the Stream Engine C library
- `osg-daemon`: asyncio background daemon with OneEuro filtering and
  auto-reconnect
- `osg-config`: GTK4/libadwaita GUI with live preview, curve editor,
  calibration wizard
- `osg-setup`: interactive setup wizard for Stream Engine, LUG-Helper, and
  OpenTrack
- OpenTrack UDP output (6-DoF, 48-byte packets on localhost:4242)
- FreeTrack shared memory output (optional)
- Unix socket JSON-RPC IPC between daemon and GUI
- TOML configuration at `~/.config/openstargazer/config.toml`
- Named profile management
- udev rules for all known Tobii ET5 USB PIDs
- systemd user service (`openstargazer.service`)
- Multi-distro installer (Arch, Fedora, Debian/Ubuntu) with PEP 668 venv
  fallback
- Mock tracker mode for development without hardware
- CI workflow for Python 3.10, 3.11, 3.12
