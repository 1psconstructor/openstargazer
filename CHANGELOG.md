# Changelog

All notable changes to openstargazer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] – 2026-03-13

### Fixed
- `scripts/fetch-stream-engine.sh`: Executable-Stack-Flag wird nach dem Download von
  `libtobii_stream_engine.so` automatisch gecleart (`clear_execstack()`). Kernel 6.18+
  blockiert Shared Libraries mit GNU_STACK-Flags 0x7 (RWE). Methode: `patchelf --clear-execstack`
  → `execstack -c` → Python-struct-Fallback (Patch auf Offset 0x158 im ELF-PHDR).
- `openstargazer/engine/loader.py`: Python 3.14 verschärfte ctypes-Typprüfung – `None` ist
  kein gültiger Wert mehr für CFUNCTYPE-Parameter. `tobii_api_create` übergibt jetzt
  `ctypes.cast(None, LogCallback)` statt rohem `None`.
- `openstargazer/engine/loader.py`: Falsche Parameterreihenfolge bei `tobii_device_create` –
  das Binary erwartet `(api*, url, device**, field_of_use)`, die SDK-Doku beschreibt fälschlich
  `(api*, url, field_of_use, device**)`. Behebt SEGFAULT beim Verbindungsaufbau.
- `openstargazer/daemon/tracker.py`: `tobii_head_pose_subscribe` wirft auf ET5 (PID 0313)
  `NOT_SUPPORTED`; der Fehler wird jetzt als Warning geloggt statt den Connect-Vorgang
  abzubrechen.
- `openstargazer/daemon/tracker.py`: `wait_for_callbacks` gibt Code 6 (TIMED_OUT) zurück wenn
  innerhalb von 200 ms kein Callback eintrifft – normales SDK-Verhalten, kein Geräteverlust.
  Der Loop behandelt `TIMED_OUT` nicht mehr als Disconnect und ruft `process_callbacks` weiterhin
  auf (SDK-konformes Verhalten).

### Added
- `openstargazer/engine/api.py`: Neuer ctypes-Struct `TobiiGazeData` (tobii_gaze_data_t,
  Stream Engine 3.x ABI) – enthält per-Auge-Gaze-Origin und Gaze-Point-on-Display-Area.
- `openstargazer/engine/loader.py`: `GazeDataCallback` CFUNCTYPE; Bindings für
  `tobii_gaze_data_subscribe` / `tobii_gaze_data_unsubscribe` (try/except falls nicht
  vorhanden); neue Methoden `subscribe_gaze_data()` / `unsubscribe_gaze_data()`.
- `openstargazer/engine/callbacks.py`: `_gaze_data_callback()` verarbeitet `TobiiGazeData`
  (mittelt linkes + rechtes Auge, Fallback auf Einzelauge); Property `gaze_data_cb`.
- `openstargazer/daemon/tracker.py`: Primäre Gaze-Subscription auf `tobii_gaze_data_subscribe`
  (PRP Stream 6) umgestellt – aktiviert IR-LEDs des ET5 zuverlässig. Fallback auf
  `tobii_gaze_point_subscribe` (PRP Stream 3) bei NOT_SUPPORTED. Flag `_gaze_data_mode`
  steuert korrekte Unsubscription in `_disconnect()`.

## [0.2.1] – 2026-03-12

### Fixed
- `scripts/fetch-stream-engine.sh`: Fehlende Datei `~/.local/share/openstargazer/bin/tobiiusbservice`
  – das Script installierte `tobiiusbserviced` nur nach `/usr/local/sbin/` (system-weit), legte aber
  nie den vom Daemon erwarteten User-Local-Pfad an; jetzt wird nach der Systeminstallation ein
  Symlink `~/.local/share/openstargazer/bin/tobiiusbservice → /usr/local/sbin/tobiiusbserviced`
  erstellt; `already_installed()` prüft jetzt alle drei Pfade
- `setup/wizard.py`: Setup-Wizard friert bei Schritt 5 nicht mehr ein – `input()` in
  `step_ingame_instructions()` ist jetzt von `try/except (EOFError, KeyboardInterrupt)` umschlossen;
  verhindert stillen Absturz wenn stdin geschlossen ist (z. B. automatisierter Aufruf)
- `scripts/install.sh`: Wizard-Aufruf in `configure_opentrack_profile()` leitet stdin nun aus
  `/dev/null` um (`< /dev/null`) – der Wizard läuft nicht-interaktiv mit Defaults durch, statt
  den Installationsfluss zu blockieren
- `scripts/install.sh`: Daemon startet nach der Erstinstallation sofort (`systemctl --user start`),
  ohne dass ein Aus- und Wiedereinloggen nötig ist – behebt dauerhaftes „Disconnected" in osg-config
  direkt nach der Installation

### Added
- `data/openstargazer.service`: Explizite `OSG_STREAM_ENGINE_PATH`-Umgebungsvariable zeigt direkt
  auf `~/.local/share/openstargazer/lib/libtobii_stream_engine.so` (Belt-and-Suspenders-Absicherung
  für den Stream-Engine-Loader)
- `openstargazer/daemon/tracker.py`: Neue Methoden `pause_tracking()` / `resume_tracking()` und
  Property `tracking_enabled` – trennt das Gerät vollständig (LEDs aus) und stellt die Verbindung
  wieder her (LEDs an) ohne den Daemon-Prozess zu beenden; Reconnect-Watchdog respektiert den
  Pause-Zustand
- `openstargazer/daemon/ipc_server.py`: Neuer RPC-Befehl `set_tracking_enabled` – schaltet
  Tracking per IPC an/aus; `get_status` enthält jetzt das Feld `tracking_enabled`
- `openstargazer/ipc/client.py`: Neue Methode `set_tracking_enabled(enabled: bool)` im
  synchronen `IPCClient`
- `gui/main_window.py`: Neue „Device"-Gruppe in osg-config mit Tobii-Ein/Aus-Schalter – kippt
  den Schalter auf OFF → Gerät trennt sich, LEDs gehen aus; auf ON → Gerät verbindet sich neu;
  Status-Poll aktualisiert Schalter und Untertitel alle 250 ms via IPC

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
