# openstargazer – Vollständiges Benutzerhandbuch

**Tobii Eye Tracker 5 auf Linux mit Star Citizen / LUG-Helper**

---

## Inhaltsverzeichnis

1. [Übersicht & Architektur](#1-übersicht--architektur)
2. [Systemvoraussetzungen](#2-systemvoraussetzungen)
3. [Installation](#3-installation)
   - [Fedora (Empfohlen)](#31-fedora)
   - [Arch Linux](#32-arch-linux)
   - [Debian / Ubuntu](#33-debian--ubuntu)
   - [Andere Distributionen](#34-andere-distributionen)
4. [Erster Start & Setup-Wizard](#4-erster-start--setup-wizard)
5. [Deinstallation](#5-deinstallation)
6. [Konfigurationsdatei im Detail](#6-konfigurationsdatei-im-detail)
7. [Betrieb & Funktionen](#7-betrieb--funktionen)
8. [OpenTrack-Integration](#8-opentrack-integration)
9. [Star Citizen / LUG-Helper](#9-star-citizen--lug-helper)
10. [Betriebsmodi & Einsatzszenarien](#10-betriebsmodi--einsatzszenarien)
11. [Kalibrierung](#11-kalibrierung)
12. [Profile](#12-profile)
13. [Best Practices](#13-best-practices)
14. [Tipps & Tricks](#14-tipps--tricks)
15. [Fehlerbehebung](#15-fehlerbehebung)
    - [Debug-Report erstellen](#debug-report-erstellen)
16. [FAQ](#16-faq)
17. [Linksammlung](#17-linksammlung)

---

## 1. Übersicht & Architektur

openstargazer ist ein nativer Linux-Treiber-Stack für den **Tobii Eye Tracker 5**. Er besteht aus drei Hauptkomponenten:

```
┌─────────────────────────────────────────────────────────────────┐
│  Tobii Eye Tracker 5 (USB)                                      │
│    └─► libtobii_stream_engine.so  (proprietäre Tobii-Bibliothek)│
│          └─► osg-daemon        (Python-Hintergrundprozess)   │
│                ├─► OneEuro-Filter  (Rauschunterdrückung)        │
│                ├─► Kurven-Mapping  (Achsen-Konfiguration)       │
│                ├─► OpenTrack UDP   (→ OpenTrack → Star Citizen) │
│                ├─► FreeTrack SHM   (alternative Ausgabe)        │
│                └─► IPC-Socket      (Kommunikation mit GUI)      │
│                                                                  │
│  osg-config  (GTK4-GUI – optionale Bedienoberfläche)         │
│  osg-setup   (Setup-Wizard – Ersteinrichtung)                │
└─────────────────────────────────────────────────────────────────┘
```

**Datenfluss im Daemon:**
```
Gerät → [Gaze + HeadPose Callbacks]
       → [OneEuro-Filter]  (Jitter-Reduktion pro Achse)
       → [Deadzone-Filter] (Augenstabilisierung)
       → [Kurven-Mapping]  (nichtlineare Achsenabbildung)
       → [Scale + Invert]  (Skalierung und Invertierung)
       → [OpenTrack UDP / FreeTrack SHM]
```

---

## 2. Systemvoraussetzungen

### Hardware
- **Tobii Eye Tracker 5** (USB)
- USB 2.0 oder 3.0 Port
- Bildschirm-Montage oder Schreibtisch-Aufstellung

### Software
| Anforderung | Version |
|-------------|---------|
| Linux-Kernel | 5.15 oder neuer |
| Python | 3.10 oder neuer |
| systemd | (für User-Service) |
| OpenTrack | 2026.1.0 oder neuer (empfohlen, für Star Citizen) |

### Unterstützte Distributionen
| Distribution | Paketmanager | Getestet |
|--------------|-------------|---------|
| **Fedora 39–43+** | dnf | ✓ Primär |
| Arch Linux / Manjaro | pacman | ✓ |
| Debian 12 / Ubuntu 22.04+ | apt | ✓ |
| andere Distros | manuell | eingeschränkt |

---

## 3. Installation

### Vorbereitung (alle Distros)

```bash
git clone https://github.com/1psconstructor/openstargazer.git
cd openstargazer
```

---

### Interaktives Installations-Menü

Das Skript zeigt beim Start immer ein Menü:

```
==========================================
   openstargazer Setup
==========================================

  1) Neuinstallation
  2) Reparatur (fehlende Komponenten nachinstallieren)
  3) Deinstallation -- vollständig
  4) Deinstallation -- benutzerdefiniert
  5) Beenden
```

| Option | Beschreibung |
|--------|-------------|
| **1 – Neuinstallation** | Vollständige Erstinstallation aller Komponenten |
| **2 – Reparatur** | Prüft jede Komponente einzeln und installiert nur fehlende nach |
| **3 – Volldeinstallation** | Entfernt alle Komponenten (mit Bestätigungsabfrage) |
| **4 – Benutzerdefiniert** | Zeigt alle Komponenten mit Status, Auswahl per Nummer |
| **5 – Beenden** | Skript beenden ohne Aktion |

> **Installations-Log:** Jeder `install.sh`-Aufruf schreibt einen Eintrag in
> `~/.local/share/openstargazer/install.log` mit Zeitstempel und `[INFO|WARN|ERROR]`-Level.
> Hilfreich zur Nachverfolgung früherer Installationsversuche und für Bug-Reports.

---

### 3.1 Fedora

```bash
cd scripts
chmod +x install.sh
./install.sh
```

**Was passiert dabei (Fedora-spezifisch):**

1. **Python-Prüfung** — Fedora 43 hat Python 3.12, das ist kompatibel.

2. **Systempakete** — Folgende Pakete werden per `dnf` installiert:
   ```
   python3-gobject  gtk4  libadwaita  libusb  usbutils  curl  tar
   ```

3. **OpenTrack** — Nicht in Fedoras offiziellen Repos oder RPM Fusion Free (Fedora 43+).
   Das Skript bietet vier Installationsoptionen:
   1. RPM Fusion Free aktivieren und per dnf installieren (evtl. nicht für alle Versionen verfügbar)
   2. Via Flatpak von Flathub installieren
   3. Aus GitHub-Quellcode bauen (empfohlen für Fedora 43, inkl. Wine-/LUG-Unterstützung)
   4. Überspringen (manuell nachinstallieren)

4. **Python-Paket** — Fedora hat PEP 668 aktiviert, daher:
   - Erster Versuch: normales `pip install --user`
   - Bei Ablehnung: automatischer Fallback auf **venv** unter `~/.local/share/openstargazer/venv/`
   - Entry-Points werden als Symlinks nach `~/.local/bin/` angelegt

5. **udev-Regeln** — Werden nach `/etc/udev/rules.d/70-openstargazer.rules` kopiert. Da `plugdev` auf Fedora nicht existiert, wird `TAG+="uaccess"` in der Regel genutzt (kein Gruppen-Beitritt nötig).

6. **systemd User-Service** — Wird aktiviert. Bei venv-Install wird `ExecStart` automatisch auf den venv-Pfad angepasst.

**OpenTrack auf Fedora nachinstallieren:**

```bash
# Option A: RPM Fusion Free aktivieren
sudo dnf install -y \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install -y opentrack

# Option B: Flatpak (Flathub)
flatpak install -y flathub io.github.opentrack.OpenTrack

# Option C: Aus GitHub-Quellcode bauen (Fedora 43+, enthält Wine-Output-Plugin)
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

**Installierte Systempakete (pacman):**
```
python-gobject  gtk4  libadwaita  libayatana-appindicator
libusb  usbutils  opentrack  curl  tar
```

**Hinweise für Arch:**
- Arch setzt seit Python 3.11+ ebenfalls PEP 668 um → venv-Fallback greift automatisch
- `python-venv` ist in das Standard-`python`-Paket integriert, kein Extra-Paket nötig
- Der Benutzer wird zur Gruppe `plugdev` hinzugefügt (Abmelden und neu anmelden danach nötig)

---

### 3.3 Debian / Ubuntu

```bash
cd scripts
chmod +x install.sh
./install.sh
```

**Installierte Systempakete (apt):**
```
python3-gi  python3-gi-cairo  gir1.2-gtk-4.0  gir1.2-adw-1
libusb-1.0-0  usbutils  opentrack
python3-venv  curl  tar
```

**Hinweise für Debian/Ubuntu:**
- `python3-venv` ist explizit in der Paketliste, da es auf Minimal-Installs fehlen kann
- Debian 12+ und Ubuntu 23.04+: PEP 668 aktiv → venv-Fallback
- Ubuntu 22.04: pip install direkt möglich (kein venv nötig)
- Der Benutzer wird zur Gruppe `plugdev` hinzugefügt

---

### 3.4 Andere Distributionen

Bei unbekanntem Paketmanager gibt das Installer-Skript folgende Pakete zur manuellen Installation aus:

```
GTK4, libadwaita, python3-gi (PyGObject), libusb, usbutils, opentrack, curl, tar
```

Danach:
```bash
python3 -m pip install --user -e ".[tray]"
# oder bei PEP 668:
python3 -m venv ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install -e ".[tray]"
```

---

### Installations-Flags

```bash
./install.sh [--no-gui] [--mock]
```

| Flag | Wirkung |
|------|---------|
| `--no-gui` | Überspringt Desktop-Eintrag und Icon-Installation |
| `--mock` | (für Entwickler) Installiert ohne echte Hardware-Abhängigkeiten |

---

## 4. Erster Start & Setup-Wizard

Nach der Installation startet automatisch der **Setup-Wizard** (`osg-setup`).

### Wizard-Schritte

**Schritt 1: Stream Engine**
- Prüft ob `libtobii_stream_engine.so` und `tobiiusbservice` unter `~/.local/share/openstargazer/` vorhanden sind
- Bietet an, sie automatisch herunterzuladen (`fetch-stream-engine.sh`)

**Schritt 2: Hardware-Erkennung**
- Sucht per `lsusb` nach bekannten Tobii-USB-IDs
- Bekannte PIDs: `0127`, `0118`, `0106`, `0128`, `010a`, `0313`
- Wenn Gerät nicht gefunden: optionale Weiterführung ohne Hardware

**Schritt 3: LUG-Helper / Star Citizen**
- Sucht automatisch nach der LUG-Helper-Konfiguration unter `~/.config/starcitizen-lug/`
- Erkennt Wine-Prefix, Runner-Pfad, ESYNC/FSYNC-Einstellungen
- Bei nicht gefundener Konfiguration: manuelle Eingabe möglich

**Schritt 4: OpenTrack-Profil**
- Generiert ein OpenTrack-INI-Profil für Star Citizen
- Standardport: 4242 (UDP)
- Installiert unter `~/.config/opentrack/tobii5-starcitizen.ini`

**Schritt 5: In-Game-Hinweise**
- Zeigt die Star Citizen Einstellungen für Head Tracking

**Schritt 6: Kalibrierung (optional)**
- Nur möglich wenn Daemon bereits läuft

### Wizard erneut ausführen

```bash
osg-setup
# oder:
python3 -m openstargazer.setup.wizard
```

---

## 5. Deinstallation

### Über das Installations-Skript (empfohlen)

```bash
cd scripts
./install.sh
# → Option 3 (vollständig) oder Option 4 (benutzerdefiniert) wählen
```

**Option 3 – Vollständige Deinstallation** entfernt nach Bestätigung:
- systemd User-Service (stop + disable + Datei löschen)
- udev-Regeln
- Tobii USB-Service und Binaries
- Python-Paket / venv / Symlinks
- Desktop-Eintrag und Icon
- Benutzerdaten (`~/.config/openstargazer`) – **separate Rückfrage, Standard: Nein**

**Option 4 – Benutzerdefinierte Deinstallation** zeigt alle Komponenten mit ihrem aktuellen Installationsstatus und lässt einzelne per Nummer auswählen:

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

### Manuelle Deinstallation (Fallback)

Falls das Skript nicht verfügbar ist:

```bash
# Services stoppen und deaktivieren
systemctl --user stop openstargazer.service 2>/dev/null || true
systemctl --user disable openstargazer.service 2>/dev/null || true
sudo systemctl stop tobiiusb.service 2>/dev/null || true
sudo systemctl disable tobiiusb.service 2>/dev/null || true

# Service-Dateien entfernen
rm -f ~/.config/systemd/user/openstargazer.service
sudo rm -f /etc/systemd/system/tobiiusb.service
systemctl --user daemon-reload
sudo systemctl daemon-reload

# udev-Regeln entfernen
sudo rm -f /etc/udev/rules.d/70-openstargazer.rules
sudo udevadm control --reload-rules

# Desktop-Eintrag und Icon
rm -f ~/.local/share/applications/openstargazer.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/openstargazer.svg

# Python-Paket und venv
pip uninstall openstargazer 2>/dev/null || true
rm -rf ~/.local/share/openstargazer/venv
rm -f ~/.local/bin/osg-daemon ~/.local/bin/osg-config ~/.local/bin/osg-setup

# Tobii Binaries
rm -f ~/.local/share/openstargazer/lib/libtobii_stream_engine.so
sudo rm -f /usr/local/sbin/tobiiusbserviced
sudo rm -rf /usr/local/lib/tobiiusb

# Konfiguration (OPTIONAL – löscht alle Einstellungen!)
rm -rf ~/.config/openstargazer/

# Benutzer aus plugdev entfernen (Debian/Ubuntu/Arch)
sudo gpasswd -d "$USER" plugdev
```

### Nur Konfiguration zurücksetzen (ohne Deinstallation)

```bash
rm ~/.config/openstargazer/config.toml
osg-setup  # erstellt neue Standard-Konfiguration
```

---

## 6. Konfigurationsdatei im Detail

Die Konfiguration liegt unter: `~/.config/openstargazer/config.toml`

Sie wird beim ersten Start automatisch mit Standardwerten erstellt.

---

### [device]

```toml
[device]
preferred_url = ""
use_head_pose = true
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `preferred_url` | String | `""` | Direkte USB-URL des Geräts (z.B. `"usb://0x2104/0x0127"`). Leer = erstes gefundenes Gerät verwenden. |
| `use_head_pose` | Bool | `true` | Wenn `true`: Kopfposition und -rotation werden verarbeitet. Wenn `false`: Nur Blickpunktdaten (Eyetracking), kein Kopftracking. |

**Wann `preferred_url` setzen?**
Nur nötig wenn mehrere Tobii-Geräte angeschlossen sind. Die URL kann aus dem Daemon-Log gelesen werden (`systemctl --user status openstargazer`).

**`use_head_pose = false`** → Reines Eyetracking, kein Kopf-Tracking. Sinnvoll z.B. für Anwendungen die nur Blickpunkte benötigen.

---

### [tracking]

```toml
[tracking]
mode = "head_and_gaze"
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `mode` | String | `"head_and_gaze"` | Tracking-Modus (siehe Tabelle) |

**Verfügbare Modi:**

| Modus | Beschreibung | Sendet an OpenTrack |
|-------|-------------|---------------------|
| `"head_and_gaze"` | Kopf-Rotation/Position + Blickpunkt | Kopf-Daten (6-DoF) |
| `"head_only"` | Nur Kopf-Tracking, kein Eyetracking | Kopf-Daten (6-DoF) |
| `"gaze_only"` | Nur Blickpunkt, kein Kopf-Tracking | Blickpunkt als X/Y |

---

### [filter]

```toml
[filter]
one_euro_min_cutoff = 0.5
one_euro_beta = 0.007
gaze_deadzone_px = 30.0
```

Der **One-Euro-Filter** ist ein adaptiver Tiefpassfilter. Er reduziert Zittern (Jitter) bei langsamen Bewegungen, erlaubt aber schnelle Bewegungen nahezu verzögerungsfrei.

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `one_euro_min_cutoff` | Float (Hz) | `0.5` | Mindest-Grenzfrequenz. **Kleiner = glatter bei Ruhezustand, aber mehr Latenz.** Bereich: 0.1–2.0 |
| `one_euro_beta` | Float | `0.007` | Geschwindigkeitskoeffizient. **Größer = weniger Lag bei schnellen Bewegungen.** Bereich: 0.0–0.1 |
| `gaze_deadzone_px` | Float (Pixel) | `30.0` | Totzone für Blickpunkt in Pixeln. Kleine Augenbewegungen unter diesem Schwellwert werden ignoriert, um Flackern zu vermeiden. |

**Filter-Empfehlungen:**

| Anwendungsfall | `min_cutoff` | `beta` |
|----------------|-------------|--------|
| Standard (Star Citizen) | `0.5` | `0.007` |
| Sehr glatt, etwas Lag | `0.2` | `0.003` |
| Schnelles Tracking, etwas Jitter | `1.0` | `0.02` |
| FPS-Shooter (max. Reaktion) | `1.5` | `0.05` |

---

### [output.opentrack_udp]

```toml
[output.opentrack_udp]
enabled = true
host = "127.0.0.1"
port = 4242
```

UDP-Ausgabe im OpenTrack-Protokoll (48-Byte-Paket, 6× little-endian double).

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `enabled` | Bool | `true` | UDP-Ausgabe aktivieren/deaktivieren |
| `host` | String | `"127.0.0.1"` | Ziel-IP für UDP-Pakete. Loopback für lokales OpenTrack. |
| `port` | Int | `4242` | UDP-Port. Muss mit OpenTrack-Einstellung übereinstimmen. |

**Für Remote-OpenTrack** (anderer PC im LAN) muss `config.toml` direkt bearbeitet werden (über `osg-config` sind aus Sicherheitsgründen nur Loopback-Adressen einstellbar):
```toml
host = "192.168.1.100"  # IP des OpenTrack-PCs
port = 4242
```

---

### [output.freetrack_shm]

```toml
[output.freetrack_shm]
enabled = false
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `enabled` | Bool | `false` | FreeTrack Shared Memory Ausgabe aktivieren. Benötigt Wine-FreeTrack-Unterstützung. Für die meisten Setups nicht nötig, da OpenTrack das übernimmt. |

---

### [axes.yaw], [axes.pitch], [axes.roll], [axes.x], [axes.y], [axes.z]

Jede der 6 Tracking-Achsen kann individuell konfiguriert werden:

```toml
[axes.yaw]
scale = 1.0
invert = false
curve = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `scale` | Float | `1.0` | Multiplikator für die Achse. `2.0` = doppelter Ausschlag, `0.5` = halber Ausschlag. |
| `invert` | Bool | `false` | Dreht die Richtung der Achse um. |
| `curve` | Liste von Punkten | linear | Steuerkurve als Liste von [x, y]-Kontrollpunkten. Erlaubt nichtlineare Antwort. |

**Achsenreferenz:**

| Achse | Bedeutung | Wertebereich |
|-------|-----------|-------------|
| `yaw` | Kopf links/rechts drehen | -180° bis +180° |
| `pitch` | Kopf hoch/runter neigen | -90° bis +90° |
| `roll` | Kopf zur Seite kippen | -90° bis +90° |
| `x` | Kopf-Position links/rechts | mm (ca. -300 bis +300) |
| `y` | Kopf-Position hoch/runter | mm (ca. -300 bis +300) |
| `z` | Kopf-Position vor/zurück | mm (ca. -300 bis +300) |

**Kurven-Beispiele:**

Lineare Kurve (Standard):
```toml
curve = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
```

Exponentiell (sanft bei kleinen, stark bei großen Bewegungen):
```toml
curve = [[0.0, 0.0], [0.3, 0.1], [0.7, 0.5], [1.0, 1.0]]
```

Dead-Zone in der Mitte (Stabilisierung):
```toml
curve = [[0.0, 0.0], [0.4, 0.0], [0.6, 1.0], [1.0, 1.0]]
```

---

### [calibration]

```toml
[calibration]
polynomial_degree = 2
samples_per_point = 30
coeff_x = []
coeff_y = []
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `polynomial_degree` | Int | `2` | Grad des Korrekturpolynoms. `2` = quadratisch. Höher = präziser aber über-fitted. |
| `samples_per_point` | Int | `30` | Messungen pro Kalibrierpunkt (Mittelwert). Mehr = genauer, aber langsamer. |
| `coeff_x` | Liste | `[]` | Kalibrierkoeffizienten für X-Achse. Automatisch gefüllt nach Kalibrierung. |
| `coeff_y` | Liste | `[]` | Kalibrierkoeffizienten für Y-Achse. Automatisch gefüllt nach Kalibrierung. |

**Kalibrierung löschen:**
```bash
# In config.toml die Koeffizienten leeren:
sed -i 's/^coeff_x = .*/coeff_x = []/' ~/.config/openstargazer/config.toml
sed -i 's/^coeff_y = .*/coeff_y = []/' ~/.config/openstargazer/config.toml
```

---

### [star_citizen]

```toml
[star_citizen]
lug_prefix = ""
runner_path = ""
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `lug_prefix` | String | `""` | Pfad zum Wine-Prefix (Star Citizen Installation). Beispiel: `/home/user/Games/star-citizen/prefix` |
| `runner_path` | String | `""` | Pfad zum Wine-Binary. Beispiel: `/home/user/Games/runners/lug-wine-tkg/bin/wine` |

---

## 7. Betrieb & Funktionen

### osg-daemon

Der Hintergrundprozess. Läuft als systemd User-Service.

```bash
# Status prüfen
systemctl --user status openstargazer

# Starten
systemctl --user start openstargazer

# Stoppen
systemctl --user stop openstargazer

# Neu starten (nach Konfigurationsänderung)
systemctl --user restart openstargazer

# Daemon-Log anzeigen
journalctl --user -u openstargazer -f

# Direkt mit Ausgabe starten (Debugging)
osg-daemon --verbose

# Mock-Modus (ohne Hardware, sinusförmige Testdaten)
osg-daemon --mock

# Eigene Konfigurationsdatei
osg-daemon --config /pfad/zur/config.toml
```

**Daemon-Flags:**

| Flag | Beschreibung |
|------|-------------|
| `--mock` | Synthetische Daten statt echter Hardware (~90 Hz, sinusförmig) |
| `--verbose` / `-v` | Detailliertes Logging (DEBUG-Level) |
| `--config PATH` | Alternativer Pfad zur config.toml |

**Auto-Reconnect:** Der Daemon verbindet sich bei Geräteverlust automatisch alle 2 Sekunden neu.

---

### osg-config (GUI)

```bash
osg-config
```

Die GTK4-Benutzeroberfläche. Zeigt:
- Live-Vorschau der Tracking-Daten
- Verbindungsstatus und FPS
- Profil-Auswahl
- Zugang zu Kurven-Editor und Kalibrierung

**Hinweis:** Die GUI kommuniziert mit dem Daemon über einen Unix-Socket (`~/.local/share/openstargazer/daemon.sock`). Der Daemon muss laufen.

---

### osg-setup (Wizard)

```bash
osg-setup
```

Interaktiver Einrichtungs-Wizard. Kann jederzeit erneut aufgerufen werden, um:
- Stream Engine neu herunterzuladen
- LUG-Helper-Konfiguration zu aktualisieren
- OpenTrack-Profil neu zu generieren

---

### IPC-Schnittstelle

Der Daemon bietet einen Unix-Socket unter `~/.local/share/openstargazer/daemon.sock`.

**Sicherheitshinweise:**
- Der Socket und sein Verzeichnis sind auf `0600`/`0700` gesetzt (nur der eigene Benutzer kann verbinden)
- Nur erlaubte Methoden werden akzeptiert (Whitelist)
- Anfragen sind auf 64 KiB begrenzt
- UDP-Zieladressen müssen Loopback sein (`127.0.0.1`, `::1`, `localhost`)
- UDP-Ports müssen im Bereich 1024–65535 liegen

Verfügbare Befehle (für Entwickler / Skripting):

| Methode | Beschreibung |
|---------|-------------|
| `ping` | Prüft ob Daemon läuft |
| `get_status` | Verbindungsstatus, FPS, letztes Frame |
| `get_config` | Aktuelle Konfiguration |
| `set_config` | Konfiguration ändern (ohne Neustart) |
| `start_calibration` | Kalibrierung starten |
| `list_profiles` | Profile auflisten |
| `activate_profile` | Profil aktivieren |

---

## 8. OpenTrack-Integration

### Funktionsweise

osg-daemon sendet 6-DoF-Daten per UDP an OpenTrack:
```
osg-daemon → UDP :4242 → OpenTrack → Wine (FreeTrack/TrackIR) → Star Citizen
```

Das UDP-Paket enthält 48 Bytes (6 × 8-Byte little-endian double):
```
Bytes  0– 7: X-Position (mm)
Bytes  8–15: Y-Position (mm)
Bytes 16–23: Z-Position (mm)
Bytes 24–31: Yaw (Grad)
Bytes 32–39: Pitch (Grad)
Bytes 40–47: Roll (Grad)
```

### OpenTrack konfigurieren

**Input:** `UDP over network` – Port `4242`

**Output:** `Wine` – Runner und Prefix aus LUG-Helper-Konfiguration

**Filter:** Keinen (osg-daemon filtert bereits intern)

Das Installationsskript erstellt automatisch ein vorkonfiguriertes Profil unter:
```
~/.config/opentrack/tobii5-starcitizen.ini
```

### Startreihenfolge (wichtig!)

```
1. Star Citizen starten
2. Tobii5-Daemon starten:  systemctl --user start openstargazer
3. OpenTrack öffnen
4. OpenTrack-Profil "tobii5-starcitizen" laden
5. OpenTrack starten (grüner Play-Button)
```

Head Tracking ist innerhalb weniger Sekunden aktiv.

---

## 9. Star Citizen / LUG-Helper

### In-Game-Einstellungen

```
Einstellungen → COMMS, FOIP & HEAD TRACKING
  Head Tracking Source: TrackIR
  Head Tracking aktivieren: ✓
```

### LUG-Helper-Konfigurationspfade

Der Wizard sucht automatisch nach der LUG-Konfiguration in dieser Reihenfolge:
```
~/.config/starcitizen-lug/config
~/.config/starcitizen-lug/settings
~/.config/starcitizen-lug/lug-helper.conf
~/.config/starcitizen-lug/lug-helper.cfg
~/.config/starcitizen-lug/preflight_conf
```
Falls keine dieser Dateien gefunden wird, wird jede Datei im Verzeichnis geprüft.

Erkannte Schlüssel (Groß- und Kleinschreibung wird beachtet): `WINEPREFIX`, `wine_prefix`, `SC_PREFIX`, `WINE_RUNNER_PATH`, `runner_path`, `ESYNC`, `FSYNC`

> **Hinweis für GE-Proton-Nutzer:** `export PROTON_VERB="runinprefix"` zur
> Startumgebung hinzufügen (z. B. in `sc-launch.sh`). Erforderlich damit das
> Wine-Output-Plugin von OpenTrack mit GE-Proton-Runnern korrekt funktioniert.

### Runner-Suchpfade

```
~/Games/star-citizen/runners/*/bin/wine
~/.local/share/lutris/runners/wine/*/bin/wine
~/.local/share/Steam/compatibilitytools.d/*/files/bin/wine  (GE-Proton)
```

---

## 10. Betriebsmodi & Einsatzszenarien

### Modus 1: Kopftracking + Eyetracking (Standard)

**config.toml:**
```toml
[tracking]
mode = "head_and_gaze"

[device]
use_head_pose = true
```

Aktiviert alle 6 Freiheitsgrade (Yaw, Pitch, Roll, X, Y, Z) plus Blickpunkt.
An OpenTrack werden Kopfdaten gesendet; Blickpunkt kann intern für Kurven-Kalibrierung genutzt werden.

---

### Modus 2: Nur Kopftracking (kein Eye-Tracking)

**config.toml:**
```toml
[tracking]
mode = "head_only"

[device]
use_head_pose = true
```

**Empfohlen für:** Nutzer die Head Tracking für Star Citizen wollen, ohne Augenbewegungen einzubeziehen. Geringerer CPU-Verbrauch, sauberere Kurven.

**Filter optimieren für head_only:**
```toml
[filter]
one_euro_min_cutoff = 0.8   # etwas responsiver
one_euro_beta = 0.01
gaze_deadzone_px = 0.0      # irrelevant, kann 0 sein
```

---

### Modus 3: Nur Eyetracking (kein Kopftracking)

**config.toml:**
```toml
[tracking]
mode = "gaze_only"

[device]
use_head_pose = false
```

**Empfohlen für:** Anwendungen die ausschließlich Blickdaten brauchen (Accessibility-Tools, Gaze-Overlay etc.).

OpenTrack erhält X/Y aus den Blickkoordinaten (normalisiert 0.0–1.0 auf Bildschirm).

---

### Modus 4: Nur Rotation (kein Positions-Tracking)

Wenn der Tracker auf Distanz steht und Positionsdaten unzuverlässig sind:

**config.toml:**
```toml
[axes.x]
scale = 0.0   # Deaktiviert X-Position

[axes.y]
scale = 0.0   # Deaktiviert Y-Position

[axes.z]
scale = 0.0   # Deaktiviert Z-Position
```

Yaw, Pitch und Roll bleiben aktiv.

---

### Modus 5: Minimale Bewegung (Cockpit-Stil)

Für Spiele wo Kopfbewegungen nur leichte Korrekturen machen sollen:

```toml
[axes.yaw]
scale = 0.3

[axes.pitch]
scale = 0.3

[axes.roll]
scale = 0.2
invert = true   # Roll oft invertiert gewünscht

[axes.x]
scale = 0.1

[axes.y]
scale = 0.1

[axes.z]
scale = 0.0     # Z meist deaktiviert für Cockpit
```

---

### Modus 6: Remote-Setup (Tracker auf anderem PC)

```toml
[output.opentrack_udp]
enabled = true
host = "192.168.1.100"   # IP des Gaming-PCs
port = 4242
```

OpenTrack auf dem Gaming-PC auf `UDP over network` von `0.0.0.0:4242` konfigurieren.

---

## 11. Kalibrierung

Die Kalibrierung verbessert die Genauigkeit des Blickpunkts durch polynomiale Korrektur.

### Kalibrierung starten

Der Daemon muss laufen:

```bash
# Über GUI: osg-config → Kalibrierung
# Oder über Wizard:
osg-setup  # Schritt 6 auswählen
```

### Kalibrierung zurücksetzen

```bash
# config.toml editieren:
nano ~/.config/openstargazer/config.toml

# Zeilen ändern:
coeff_x = []
coeff_y = []
```

### Wann kalibrieren?

- Nach dem Umzug des Monitors
- Nach dem Verstellen des Trackers
- Wenn Blickpunkt systematisch versetzt erscheint

---

## 12. Profile

Profile erlauben schnelles Umschalten zwischen Konfigurationen (z.B. Star Citizen vs. Desktop-Nutzung).

```bash
# Profile auflisten
osg-daemon  # dann per IPC:
# client.list_profiles()

# Profil aktivieren (über GUI oder IPC)
```

---

## 13. Best Practices

### Physische Aufstellung

- Tracker **mittig unter dem Monitor** positionieren, waagerecht ausgerichtet
- Abstand zum Gesicht: **60–80 cm** optimal
- Direkte Beleuchtung auf das Gerät vermeiden (IR-Interferenz)
- Starkes Sonnenlicht hinter dem Monitor kann Tracking stören

### Konfiguration

- **Filter zuerst testen** bevor Kurven angepasst werden
- Immer mit `--mock` und `osg-config` die Kurven testen, bevor echtes Hardware-Tracking läuft
- Eine Achse nach der anderen anpassen, nicht alle gleichzeitig
- Konfigurationsbackup vor größeren Änderungen:
  ```bash
  cp ~/.config/openstargazer/config.toml ~/.config/openstargazer/config.toml.bak
  ```

### Service-Management

- Den Daemon **nicht manuell im Terminal starten** wenn der systemd-Service läuft — sonst zwei Instanzen
- Nach Konfigurationsänderungen immer neu starten:
  ```bash
  systemctl --user restart openstargazer
  ```
- Log-Monitoring für Probleme:
  ```bash
  journalctl --user -u openstargazer -f --since "10 minutes ago"
  ```

### Performance

- Für Star Citizen: OpenTrack-Filter auf **keine** stellen (osg-daemon filtert bereits)
- `gaze_deadzone_px = 30` ist ein guter Ausgangswert, bei stabilem Tracking reduzieren
- Bei hoher CPU-Last: `mode = "head_only"` spart Ressourcen

---

## 14. Tipps & Tricks

### Achsen schnell deaktivieren

Achse auf `scale = 0.0` setzen statt die Konfiguration komplex zu ändern:
```toml
[axes.roll]
scale = 0.0   # Roll deaktiviert
```

### Invertierung für Roll

Manche Nutzer empfinden Roll invertiert natürlicher:
```toml
[axes.roll]
invert = true
```

### Deadzone für die Mitte (Kurven-Trick)

Kleiner stabiler Bereich in der Mitte verringert ungewollte Mikrobewegungen:
```toml
[axes.yaw]
curve = [[0.0, 0.0], [0.45, 0.0], [0.55, 0.0], [0.75, 0.6], [1.0, 1.0]]
```

### Separate OpenTrack-Profile

Für verschiedene Spiele eigene OpenTrack-Profile anlegen und im Dateinamen kennzeichnen:
```
~/.config/opentrack/tobii5-starcitizen.ini
~/.config/opentrack/tobii5-elite.ini
~/.config/opentrack/tobii5-dcs.ini
```

### Daemon automatisch mit dem Login starten

Ist bereits durch `systemctl --user enable openstargazer` erledigt, wenn `lingering` aktiviert ist:
```bash
sudo loginctl enable-linger "$USER"
```

### Mock-Modus für Setup-Tests

Testen ohne echten Tracker – zwei Wege:

```bash
# Weg 1: Daemon im Mock-Modus starten, GUI normal verbinden
osg-daemon --mock --verbose &
osg-config

# Weg 2: GUI direkt im Mock-Modus starten (kein Daemon nötig)
osg-config --mock
```

`osg-config --mock` startet die GUI mit einem integrierten Simulations-Client und benötigt keinen laufenden Daemon. Nützlich für UI-Tests und Kurven-Konfiguration.

### Konfiguration live neu laden

Der Daemon unterstützt Live-Aktualisierung über IPC ohne Neustart:
```bash
# Über GUI osg-config änderungen speichern
# oder per IPC (für Skripting):
# client.set_config({...})
```

### Debugging: UDP-Pakete prüfen

Verifizieren ob Daten ankommen:
```bash
# Lauscht auf UDP:4242 und zeigt Byte-Größe
nc -lu 4242 | while read -n 48 data; do echo "Paket empfangen: 48 Bytes"; done
```

### Stream Engine Pfad manuell überschreiben

Wenn die `.so` an einem nicht-Standard-Ort liegt:
```bash
export TOBII_STREAM_ENGINE_PATH=/pfad/zu/libtobii_stream_engine.so
osg-daemon
```

Oder dauerhaft in `~/.bashrc` / `~/.zshrc`:
```bash
echo 'export TOBII_STREAM_ENGINE_PATH=~/.local/share/openstargazer/lib/libtobii_stream_engine.so' >> ~/.bashrc
```

---

## 15. Fehlerbehebung

### Problem: Daemon startet nicht – Stream Engine nicht gefunden

**Fehlermeldung:**
```
StreamEngineError: libtobii_stream_engine.so not found.
```

**Lösung:**
```bash
# Stream Engine herunterladen
bash scripts/fetch-stream-engine.sh

# Oder manuell prüfen:
ls ~/.local/share/openstargazer/lib/libtobii_stream_engine.so
ls ~/.local/share/openstargazer/bin/tobiiusbservice
```

---

### Problem: Kein Gerät gefunden

**Fehlermeldung:**
```
No Tobii devices found
```

**Lösungsschritte:**

1. USB-Verbindung prüfen:
   ```bash
   lsusb | grep 2104
   ```
   Muss einen Eintrag mit Vendor-ID `2104` zeigen.

2. udev-Regeln prüfen (Fedora/kein plugdev):
   ```bash
   ls -la /etc/udev/rules.d/70-openstargazer.rules
   ```

3. udev neu laden:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger --subsystem-match=usb
   ```

4. Gerät neu einstecken nach udev-Reload

5. Auf Debian/Ubuntu: Gruppe prüfen:
   ```bash
   groups | grep plugdev
   ```
   Falls nicht vorhanden: abmelden und neu anmelden.

---

### Problem: pip-Fehler bei Installation (PEP 668)

**Fehlermeldung:**
```
error: externally-managed-environment
```

Das Installationsskript fängt dies automatisch ab und nutzt ein venv. Falls manuell installiert wird:

```bash
python3 -m venv --system-site-packages ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install -e ".[tray]"
```

---

### Problem: OpenTrack empfängt keine Daten

**Checkliste:**
1. Daemon läuft? → `systemctl --user status openstargazer`
2. Port übereinstimmend? → `config.toml` port vs. OpenTrack UDP-Port
3. OpenTrack Input auf `UDP over network` gestellt?
4. Firewall? → `sudo firewall-cmd --add-port=4242/udp --permanent` (Fedora)

**UDP-Verbindung testen:**
```bash
# Terminal 1: Lauschen
nc -lu 4242 | od -t x1 | head -5

# Terminal 2: Manuelles Testpaket
python3 -c "
import socket, struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(struct.pack('<6d', 0,0,600,10,5,0), ('127.0.0.1', 4242))
print('Testpaket gesendet')
"
```

---

### Problem: Tracker springt oder zittert stark

**Lösung: Filter anpassen**
```toml
[filter]
one_euro_min_cutoff = 0.3   # Glätter
one_euro_beta = 0.003
```

Oder Deadzone erhöhen:
```toml
gaze_deadzone_px = 50.0
```

---

### Problem: Hohes Latenz / Verzögerung

**Lösung: Filter responsiver machen**
```toml
[filter]
one_euro_min_cutoff = 1.0
one_euro_beta = 0.02
```

Zusätzlich: OpenTrack-Filter auf **keine** setzen.

---

### Problem: Tracker verliert Verbindung häufig

**Ursachen:**
- USB-Kabelproblem (anderes Kabel/Port testen)
- `tobiiusbservice` nicht aktiv

**Prüfen:**
```bash
# USB-Service prüfen
systemctl --user status tobii-usbservice

# Manuell starten
~/.local/share/openstargazer/bin/tobiiusbservice &
```

---

### Problem: `osg-config` startet nicht (GUI)

```bash
# Abhängigkeiten prüfen
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; print('GTK4 OK')"
python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw; print('Adwaita OK')"
```

Fehlende Pakete nachinstallieren:
```bash
# Fedora:
sudo dnf install python3-gobject gtk4 libadwaita

# Debian/Ubuntu:
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

# Arch:
sudo pacman -S python-gobject gtk4 libadwaita
```

---

### Problem: Star Citizen zeigt kein Head Tracking

1. Reihenfolge prüfen: **erst Star Citizen, dann OpenTrack starten**
2. In Star Citizen: Settings → COMMS, FOIP & HEAD TRACKING → TrackIR aktivieren
3. OpenTrack: Play-Button gedrückt?
4. Wine Output in OpenTrack: korrekter Runner und Prefix?

---

### Problem: Service startet nach Reboot nicht automatisch

```bash
# Lingering aktivieren (Service ohne Login-Session starten)
sudo loginctl enable-linger "$USER"

# Service ist enabled?
systemctl --user is-enabled openstargazer
# Muss "enabled" zeigen, sonst:
systemctl --user enable openstargazer
```

---

### Problem: Konfiguration wird nicht gespeichert

```bash
# Verzeichnis vorhanden?
ls ~/.config/openstargazer/

# Schreibrechte prüfen
ls -la ~/.config/openstargazer/config.toml

# Manuell erstellen lassen:
osg-daemon --mock &
sleep 2
kill %1
ls ~/.config/openstargazer/config.toml
```

---

### Debug-Report erstellen

Wenn ein Problem schwer zu diagnostizieren ist, sammelt das Debug-Report-Skript alle
relevanten Systeminformationen in einer einzigen Datei:

```bash
cd scripts
bash collect-debug-info.sh
```

Oder aus dem install.sh-Menü: **Option 6 – Debug-Report erstellen** wählen.

Das Skript erstellt eine Datei unter:
```
~/openstargazer-debug-JJJJMMTT-HHMMSS.txt
```

**Inhalt des Reports:**
- System: OS/Distro, Kernel-Version, Architektur, RAM, CPU
- Python: Version, pip/venv-Status, `pip show openstargazer`
- USB-Geräte: Tobii-Geräteerkennung per `lsusb`
- Service-Status: `openstargazer` User-Service und letzte 50 Journal-Zeilen
- Tobii USB-Service: `tobiiusb` System-Service-Status
- Installationspfade: Vorhandensein aller Schlüsseldateien (Stream Engine, udev-Regeln, venv, Desktop-Eintrag)
- opentrack: Version und Inhalt des Config-Verzeichnisses (nur Dateinamen)
- Konfigurationsdatei: `~/.config/openstargazer/config.toml` mit gekürzten Home-Pfaden
- Installations-Log: Letzte 100 Zeilen aus `~/.local/share/openstargazer/install.log`
- udev-Regeln: Inhalt von `/etc/udev/rules.d/70-openstargazer.rules`

Die erzeugte Datei als Anhang an ein [neues GitHub-Issue](https://github.com/1psconstructor/openstargazer/issues/new) anhängen.

> **Datenschutz-Hinweis:** Das Skript ersetzt deinen tatsächlichen Benutzernamen in
> Dateipfaden durch `<user>`. Passwörter oder Tokens werden nicht erfasst.

---

## 16. FAQ

**F: Muss OpenTrack installiert sein damit osg-daemon läuft?**
A: Nein. Der Daemon sendet UDP-Pakete unabhängig davon ob OpenTrack läuft. Er braucht OpenTrack nur als Empfänger.

---

**F: Funktioniert der Tracker auch ohne Star Citizen?**
A: Ja. osg-daemon sendet Standard-OpenTrack-UDP. Jedes Programm das das OpenTrack-UDP-Protokoll versteht kann die Daten empfangen.

---

**F: Wie hoch ist die Latenz?**
A: Der Tobii ET5 läuft mit 33–90 Hz (je nach Modus). Die Filter addieren je nach Einstellung 10–50 ms. End-to-end (Tracker → OpenTrack) typischerweise unter 30 ms.

---

**F: Kann ich mehrere Tobii-Geräte gleichzeitig nutzen?**
A: Aktuell verbindet sich der Daemon mit dem ersten gefundenen Gerät. Über `preferred_url` in der Konfiguration kann ein bestimmtes Gerät ausgewählt werden.

---

**F: Wie aktualisiere ich openstargazer?**
```bash
cd ~/openstargazer
git pull
pip install --user -e ".[tray]"   # oder venv-pip
systemctl --user restart openstargazer
```

---

**F: Funktioniert der Tracker unter Wayland?**
A: Der Daemon selbst läuft unabhängig von Wayland/X11 (USB-Gerät). Die GUI (`osg-config`) nutzt GTK4 und funktioniert auf beiden.

---

**F: Was macht der Mock-Modus genau?**
A: `--mock` erzeugt sinusförmige Testdaten bei ~90 Hz ohne echten Tracker. Yaw/Pitch/Roll/X/Y/Z schwingen mit unterschiedlichen Frequenzen. Gut für UI-Tests und OpenTrack-Verbindungstests.

---

**F: Wie erkenne ich ob Kalibrierung aktiv ist?**
A: Wenn `coeff_x` und `coeff_y` in `config.toml` nicht leer sind, ist Kalibrierung aktiv. Leere Listen = keine Korrektur.

---

**F: Kann ich openstargazer mit anderen Spielen als Star Citizen nutzen?**
A: Ja. Jedes Spiel das TrackIR oder FreeTrack via Wine/Proton unterstützt funktioniert. OpenTrack muss entsprechend konfiguriert sein.

---

**F: Warum sendet der Daemon auch wenn kein Spiel läuft?**
A: Der Daemon sendet kontinuierlich UDP-Pakete solange er läuft. UDP-Pakete ohne Empfänger werden einfach verworfen. Das ist normales Verhalten.

---

**F: Was passiert bei USB-Trennung?**
A: Der Daemon erkennt den Verbindungsabbruch und versucht alle 2 Sekunden automatisch die Verbindung wiederherzustellen. Kein manueller Eingriff nötig.

---

## 17. Linksammlung

### Projekt & Community

| Ressource | Link |
|-----------|------|
| Tobii Eye Tracker 5 (offiziell) | https://gaming.tobii.com/product/eye-tracker-5/ |
| OpenTrack | https://github.com/opentrack/opentrack |
| LUG-Helper (Star Citizen Linux) | https://github.com/starcitizen-lug/lug-helper |

### Treiber & Bibliotheken

| Ressource | Link |
|-----------|------|
| Community Stream Engine Mirror | https://github.com/johngebbie/tobii_4C_for_linux/releases |
| Tobii Stream Engine (offiziell, SDK) | https://developer.tobii.com/product-integration/stream-engine/ |

### Distribution / Pakete

| Distribution | Ressource |
|-------------|-----------|
| Fedora – RPM Fusion Free | https://rpmfusion.org/Configuration |
| OpenTrack Flatpak | https://flathub.org/apps/io.github.opentrack.OpenTrack |
| Arch – AUR opentrack | https://aur.archlinux.org/packages/opentrack |

### Dokumentation

| Thema | Link |
|-------|------|
| OpenTrack UDP-Protokoll | https://github.com/opentrack/opentrack/wiki/UDP-over-network-protocol |
| One Euro Filter Paper | https://gery.casiez.net/1euro/ |
| PyGObject (GTK4 Python) | https://pygobject.gnome.org/ |
| systemd User Services | https://wiki.archlinux.org/title/Systemd/User |
| udev uaccess | https://www.freedesktop.org/software/systemd/man/udev_rules.html |

### Star Citizen Linux

| Ressource | Link |
|-----------|------|
| Star Citizen auf Linux (Wiki) | https://starcitizen.tools/Star_Citizen_on_Linux |
| LUG Community Discord | https://discord.gg/starcitizen-linux |
| GE-Proton | https://github.com/GloriousEggroll/proton-ge-custom |

---

*Dieses Handbuch entspricht openstargazer v0.2.0.*
