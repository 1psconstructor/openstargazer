# openstargazer

[![CI](https://github.com/1psconstructor/openstargazer/actions/workflows/ci.yml/badge.svg)](https://github.com/1psconstructor/openstargazer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

Native Linux driver for the **Tobii Eye Tracker 5** with automatic Star Citizen /
LUG-Helper integration.

> **No Windows VM required.** The ET5 talks directly to Linux via Tobii's unofficial
> Stream Engine binaries, and openstargazer bridges the data to OpenTrack.

---

## Quick Start

```bash
./scripts/install.sh              # 1× setup (auto-detects LUG, fetches Stream Engine, installs udev)
systemctl --user start openstargazer  # start the background daemon
osg-config                        # open GUI → "Star Citizen Setup" → done
```

Then: start Star Citizen → start OpenTrack → head tracking is active.

---

## Architecture

```
ET5 ──► osg-daemon ──► OpenTrack UDP:4242 ──► OpenTrack (Linux, Wine-Output) ──► Star Citizen
```

The daemon (`osg-daemon`) reads gaze and head-pose data from the Eye Tracker 5 via the
Tobii Stream Engine C library, applies OneEuro filtering, and outputs 6-DoF data as a
48-byte UDP packet to OpenTrack on `localhost:4242`.

A GTK4/libadwaita GUI (`osg-config`) provides:
- Live gaze & head-pose preview
- Calibration wizard (5- or 9-point)
- Per-axis Bezier curve editor
- Profile management
- System tray integration

---

## Requirements

### System packages (Arch / Manjaro)
```bash
sudo pacman -S python-gobject gtk4 libadwaita libayatana-appindicator \
               libusb usbutils opentrack
```

### Tobii Stream Engine (fetched automatically by install.sh)
- `tobiiusbservice` – USB host daemon
- `libtobii_stream_engine.so` – tracking API shared library

Source: community binaries from `johngebbie/tobii_4C_for_linux` and related repos.

---

## In-game Settings (Star Citizen)

1. Open **COMMS, FOIP & HEAD TRACKING**
2. Set **Head Tracking Source** → `TrackIR`
3. **Start order**: Star Citizen first → then OpenTrack

---

## Configuration

`~/.config/openstargazer/config.toml` – auto-created on first run.

See [HANDBOOK.md](HANDBOOK.md) for full reference.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT – see [LICENSE](LICENSE).
