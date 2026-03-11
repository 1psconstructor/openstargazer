# Changelog

All notable changes to openstargazer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] – 2026-03-11

### Fixed
- `fetch-stream-engine.sh`: Crash "tmpdir ist nicht gesetzt" unter `set -u` behoben –
  lokale Variable wird jetzt als leerer String initialisiert und der RETURN-Trap
  ist set-u-sicher (`${tmpdir:-}`)
- `install.sh`: opentrack-Installation über RPM Fusion Free schlägt auf Fedora 43 nicht mehr
  den Installer ab, sondern zeigt einen erweiterten Auswahlmenü-Fallback

### Added
- `install.sh`: Neue Option „Build from GitHub source" in `install_opentrack_fedora()` –
  klont `https://github.com/opentrack/opentrack` und baut mit `-DSDK_WINE=ON` (empfohlen
  für Fedora 43, da opentrack nicht in RPM Fusion Free verfügbar ist)
- `opentrack_config.py`: Warnung bei GE-Proton-Runnern – gibt Hinweis auf erforderliche
  Umgebungsvariable `PROTON_VERB="runinprefix"` aus
- `install.sh`: Persistentes Installations-Log unter `~/.local/share/openstargazer/install.log` –
  jeder Aufruf hängt einen Eintrag mit Zeitstempel, System-Info (Distro, Kernel, Arch, Bash,
  User, Aktion) und strukturierten `[INFO|WARN|ERROR]`-Zeilen an
- `scripts/collect-debug-info.sh`: Neues Debug-Report-Skript – sammelt OS/Distro, Kernel,
  Python-Umgebung, USB-Geräte, Service-Status, Installationspfade, opentrack-Version,
  Konfigurationsdatei (Pfade anonymisiert), Install-Log und udev-Regeln in einer Datei
  `~/openstargazer-debug-YYYYMMDD-HHMMSS.txt`; aufrufbar per `./collect-debug-info.sh`
  oder über install.sh Menü-Option 6
- `install.sh`: Neue Menü-Option 6 „Debug-Report erstellen" ruft `collect-debug-info.sh` auf

### Changed
- Handbücher (HANDBOOK.md / HANDBUCH.md): Fedora-Installationsabschnitt um GitHub-Source-
  Option und GE-Proton-Hinweis erweitert; OpenTrack-Mindestversion auf 2026.1.0 aktualisiert

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
