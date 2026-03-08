# Changelog

All notable changes to openstargazer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] – 2026-03-08

### Added
- Initial release as openstargazer (renamed from tobii5-linux)
- Native Linux driver for Tobii Eye Tracker 5 via Stream Engine C library
- `osg-daemon`: asyncio background daemon with OneEuro filtering and auto-reconnect
- `osg-config`: GTK4/libadwaita GUI with live preview, curve editor, calibration wizard
- `osg-setup`: interactive setup wizard for Stream Engine, LUG-Helper, and OpenTrack
- OpenTrack UDP output (6-DoF, 48-byte packets on localhost:4242)
- FreeTrack shared memory output (optional)
- Unix socket JSON-RPC IPC between daemon and GUI
- TOML-based configuration at `~/.config/openstargazer/config.toml`
- Named profile management
- udev rules for all known Tobii ET5 USB PIDs
- systemd user service (`openstargazer.service`)
- Multi-distro installer (Arch, Fedora, Debian/Ubuntu) with PEP 668 venv fallback
- Mock tracker mode for development without hardware
- CI workflow for Python 3.10, 3.11, 3.12
