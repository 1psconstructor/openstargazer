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
10a. [Sprache](#10a-sprache)
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
│    ├─► et5_native         nur pyusb -- Position,                │
│    │                      Rollwinkel, Blick (Standard)          │
│    ├─► et5_ttp_camera     + IR-Kamera, eigene ONNX-             │
│    │                      Gewichte -- Drehung und Neigung       │
│    └─► et5_stream_engine  libtobii_stream_engine.so --          │
│                           braucht eine Tobii-Lizenz, die        │
│                           die meisten Einzelhandelsgeräte       │
│                           nicht haben                           │
│                                                                 │
│  osg-daemon  (Python-Hintergrundprozess, jeweils eine           │
│               Quelle aktiv)                                     │
│    ├─► OneEuro-Filter  (Rauschunterdrückung)                    │
│    ├─► Kurven-Mapping  (Achsen-Konfiguration)                   │
│    ├─► OpenTrack UDP   (→ OpenTrack → Star Citizen)             │
│    ├─► FreeTrack SHM   (alternative Ausgabe)                    │
│    └─► IPC-Socket      (Kommunikation mit GUI)                  │
│                                                                 │
│  osg-config  (GTK4-GUI -- optionale Bedienoberfläche)           │
│  osg-setup   (Setup-Wizard -- Ersteinrichtung)                  │
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
  6) Debug-Report erstellen
```

| Option | Beschreibung |
|--------|-------------|
| **1 – Neuinstallation** | Vollständige Erstinstallation aller Komponenten |
| **2 – Reparatur** | Prüft jede Komponente einzeln und installiert nur fehlende nach |
| **3 – Volldeinstallation** | Entfernt alle Komponenten (mit Bestätigungsabfrage) |
| **4 – Benutzerdefiniert** | Zeigt alle Komponenten mit Status, Auswahl per Nummer |
| **5 – Beenden** | Skript beenden ohne Aktion |
| **6 – Debug-Report** | Sammelt Logs und Installationsstatus in einer Datei für Bugreports |

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
python3 -m pip install --user ".[tray]"
# oder bei PEP 668:
python3 -m venv ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install ".[tray]"
```

---

### Installations-Flags

```bash
./install.sh [--no-gui] [--mock] [--lang <code>]
```

| Flag | Wirkung |
|------|---------|
| `--no-gui` | Überspringt Desktop-Eintrag und Icon-Installation |
| `--mock` | (für Entwickler) Installiert ohne echte Hardware-Abhängigkeiten |
| `--lang <code>` | Erzwingt die Sprache des Installers (`en`, `de`, `fr`, `it`, `es`) für diesen Lauf, unabhängig von `OSG_LANG` und der System-Locale. Wird exportiert, der Setup-Assistent, an den übergeben wird, übernimmt sie ebenfalls. |

---

## 4. Erster Start & Setup-Wizard

Nach der Installation startet automatisch der **Setup-Wizard** (`osg-setup`).

### Wizard-Schritte

**Schritt 1: Tracking-Backend**
- Beim Standard-Backend `native` gibt es nichts zu installieren — der
  Schritt bestätigt das nur. Es spricht direkt über USB, ohne Tobii-
  Binärdateien und ohne `tobiiusbserviced`.
- Bei `stream-engine` prüft er, ob `libtobii_stream_engine.so` und
  `tobiiusbservice` unter `~/.local/share/openstargazer/` vorhanden sind,
  und bietet den Download an (`fetch-stream-engine.sh`). Das Stream-Engine-
  Backend ist optional; für Kopf-Neigung wird es nicht gebraucht — dafür
  ist der nächste Schritt da —, und auf den meisten Einzelhandels-ET5
  funktioniert es ohnehin nicht, aus dem Lizenzgrund unter `[device]`
  weiter unten.

**Erweitertes Headtracking (optional)**
- Der Schritt, der über vier oder sechs Achsen entscheidet. Der
  Blickstrom trägt keine Kopfdrehung — über alle 39 Gerätefelder gemessen
  —, also kommen Drehung und Neigung aus der geräteeigenen
  Infrarotkamera und einem neuronalen Netz, dessen Gewichte dem Projekt
  beiliegen (GPL-3.0).
- Der Preis steht **vor** der Frage, nicht danach: `onnxruntime` als
  zusätzliches Paket, rund 6 ms je Bild (ein Fünftel eines Kerns bei
  33 Hz), und dass die Bilder gelesen, vermessen und verworfen werden —
  nichts wird gespeichert, nichts verlässt den Rechner.
- Die Vorgabe ist nie „ja", wenn die Quelle auf diesem Rechner gar nicht
  starten könnte, und ein „nein" wirft niemanden von seinem
  `stream-engine`-Backend. Später änderbar im Einstellungsfenster oder
  über `source` unter `[input]`.

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
backend = "native"
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `preferred_url` | String | `""` | Direkte USB-URL des Geräts (z.B. `"usb://0x2104/0x0127"`). Leer = erstes gefundenes Gerät verwenden. Wird nur vom `stream-engine`-Backend genutzt. |
| `use_head_pose` | Bool | `true` | Wenn `true`: Kopfposition und -rotation werden verarbeitet. Wenn `false`: Nur Blickpunktdaten (Eyetracking), kein Kopftracking. |
| `backend` | String | `"native"` | Der ältere Name für die Eingangsquelle, lesbar gehalten, damit bestehende Konfigurationen weiterlaufen: `"native"` meint die Quelle `et5_native`, `"stream-engine"` die Quelle `et5_stream_engine`. Pro Lauf überschreibbar mit `osg-daemon --backend stream-engine`. Ein unbekannter Wert fällt mit Warnung auf den Standard zurück. Siehe `[input]` weiter unten — dieselbe Einstellung mit der vollständigen Liste. |

**Wann `preferred_url` setzen?**
Nur nötig wenn mehrere Tobii-Geräte angeschlossen sind. Die URL kann aus dem Daemon-Log gelesen werden (`systemctl --user status openstargazer`).

**Natives Backend (Standard):** `openstargazer/native/` spricht direkt
über USB mit dem ET5, ohne Tobiis Stream-Engine-Binärdateien und ohne den
Hintergrunddienst `tobiiusbserviced`. Es liefert Kopf**position**,
**Rollwinkel** und den Blickpunkt. Es liefert **keine** Drehung und keine
Neigung — der Blickstrom trägt keine Kopfrotation, und das ist gemessen
(über alle 39 Gerätefelder), nicht bloß unfertig. Diese beiden Achsen
kommen aus der Quelle `et5_ttp_camera`, siehe `[input]`.

Ein Backend-Wechsel braucht keine Neuinstallation. Das `stream-engine`-
Backend ist optional und auf den meisten Einzelhandels-ET5 **gar nicht
nutzbar**: `tobii_gaze_data_subscribe` und `tobii_head_pose_subscribe`
liefern ohne eine Stream-Engine-Lizenz beide `INSUFFICIENT_LICENSE` —
und diese Lizenz kommt nur mit bestimmten OEM-/Partner-Deals mit, nicht
mit einem gewöhnlichen Consumer-Gerät. Genau diese Lücke — Kopfdrehung,
die unter Linux sonst niemand außerhalb von Tobiis eigener Software
erreichen konnte — ist der Grund, warum es `et5_ttp_camera` gibt:
dieselbe Infrarotkamera, aber über das eigene Modell des Projekts statt
über Tobiis Bibliothek, die für diese Pose keine Lizenz hat. Der
Installer bietet `stream-engine` nicht mehr an, und die Reparatur
erhält eine bestehende Einrichtung auch nicht mehr; der manuelle Weg für
das seltene lizenzierte Gerät bleibt bestehen — einmalig
`./scripts/fetch-stream-engine.sh` ausführen und danach selbst
`backend = "stream-engine"` unter `[device]` setzen.

**`use_head_pose = false`** → Reines Eyetracking, kein Kopf-Tracking. Sinnvoll z.B. für Anwendungen die nur Blickpunkte benötigen.

---

### [input]

```toml
[input]
source = "et5_native"

[input.et5_camera]
model_path = ""
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `source` | String | `"et5_native"` | Welche Eingangsquelle der Daemon startet. Siehe Tabelle unten. Ein unbekannter Name wird beim Start abgelehnt, zusammen mit der Liste der vorhandenen. |
| `et5_camera.model_path` | String | `""` | Pfad zu einem Head-Pose-ONNX-Modell. Leer heißt: die beiliegenden Gewichte — zuerst das Benutzerverzeichnis `~/.local/share/openstargazer/models/`, dann die Kopie im Paket. |

| Quelle | Braucht | Achsen |
|--------|---------|--------|
| `et5_native` | nichts außer `pyusb` | Position, Rollwinkel, Blick |
| `et5_ttp_camera` | `onnxruntime` (`pip install 'openstargazer[camera]'`) | dieselben **plus Drehung und Neigung** |
| `et5_stream_engine` | Tobiis inoffizielle Binärdateien **und** eine Stream-Engine-Lizenz, die die meisten Einzelhandelsgeräte nicht haben | sechs, im Prinzip — siehe Hinweis oben; ohne Lizenz keine |
| `mock` | nichts | ein simuliertes Signal, zum Testen ohne Hardware |

**Erweitertes Headtracking (`et5_ttp_camera`)** liest die Infrarotkamera
des ET5 zusätzlich zum Blickstrom und schickt jedes Bild durch ein
neuronales Netz, dessen Gewichte unter GPL-3.0 mit dem Projekt
ausgeliefert werden (`openstargazer/models/head-pose.onnx`, von Grund auf
auf `replicantface` — MIT — trainiert). Kein Download von
Drittanbieter-Modellen nötig; der Gesichtsausschnitt wird aus den
Augenpositionen des Blickstroms berechnet, ein separates Localizer-Modell
braucht es also auch nicht.

Der Preis: `onnxruntime` als zusätzliches Paket, rund 6 ms je Bild (ein
Fünftel eines Kerns bei 33 Hz), und die Kamera wird gelesen — die Bilder
werden vermessen und verworfen, nichts wird gespeichert, nichts verlässt
den Rechner. Der Blickstrom bleibt davon unberührt: 33,1 fps mit und ohne
Kamera gemessen, jeder Messwert verschieden.

Der Daemon wählt seine Quelle beim Start, eine Änderung wirkt also erst
beim nächsten:

```bash
systemctl --user restart openstargazer
```

Der Setup-Wizard fragt danach, und das Einstellungsfenster hat es als
Schalter — dafür muss keine Datei bearbeitet werden.

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
one_euro_min_cutoff = 2.0
one_euro_beta = 0.1
gaze_min_cutoff = 1.0
gaze_beta = 1.0
gaze_deadzone_px = 30.0
```

Der **One-Euro-Filter** ist ein adaptiver Tiefpassfilter. Er reduziert Zittern (Jitter) bei langsamen Bewegungen, erlaubt aber schnelle Bewegungen nahezu verzögerungsfrei.

Kopfachsen und Blickpunkt werden mit **getrennten Parametern** gefiltert, weil sie in verschiedenen Einheiten gemessen werden: die Kopfachsen in Grad und Millimetern, der Blickpunkt in normierten Bildschirmkoordinaten von 0 bis 1. Eine Kopfdrehung legt Dutzende Grad pro Sekunde zurück, eine Sakkade dagegen ganze Einheiten — `beta` muss auf der Blickseite deshalb um Größenordnungen größer sein, um überhaupt zu greifen.

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `one_euro_min_cutoff` | Float (Hz) | `2.0` | Mindest-Grenzfrequenz der **Kopfachsen**. **Kleiner = glatter bei Ruhezustand, aber mehr Latenz.** Bereich: 0.5–5.0 |
| `one_euro_beta` | Float | `0.1` | Geschwindigkeitskoeffizient der **Kopfachsen**. **Größer = weniger Lag bei schnellen Bewegungen.** Bereich: 0.0–0.2 |
| `gaze_min_cutoff` | Float (Hz) | `1.0` | Mindest-Grenzfrequenz des **Blickpunkts**. Bereich: 0.5–3.0 |
| `gaze_beta` | Float | `1.0` | Geschwindigkeitskoeffizient des **Blickpunkts**. Bereich: 0.0–4.0 |
| `gaze_deadzone_px` | Float (Pixel) | `30.0` | Totzone für Blickpunkt in Pixeln. Kleine Augenbewegungen unter diesem Schwellwert werden ignoriert, um Flackern zu vermeiden. |

Gemessen bei 33 Hz, für eine Sakkade über 60 % der Bildschirmbreite. „Jitter übrig" ist der Anteil des Fixationsrauschens, der den Filter überlebt — kleiner ist ruhiger:

| `gaze_min_cutoff` | `gaze_beta` | Jitter übrig | 90 % der Sakkade |
|---|---|---|---|
| 1.0 | 0.0 | 26 % | 394 ms |
| 1.0 | 1.0 (Standard) | 27 % | 121 ms |
| 1.0 | 2.0 | 28 % | 61 ms |
| 2.0 | 1.0 | 38 % | 91 ms |

Zuerst `gaze_beta` erhöhen, wenn der Punkt dem Auge hinterherhängt; `gaze_min_cutoff` senken, wenn er nie zur Ruhe kommt.

Die Kopfachsen sind genauso gemessen worden, bei 33 Hz. „90 % der Drehung" ist ein Sprung um 20°; „hinterher bei 60°/s" ist der Nachlauf bei gleichmäßiger Drehung, angegeben als der Zeitversatz, dem er entspricht; „Jitter übrig" ist der Anteil des Gerätezitterns von 0,05°/Frame, der den Filter überlebt:

| `one_euro_min_cutoff` | `one_euro_beta` | Jitter übrig | 90 % der Drehung | Hinterher bei 60°/s |
|---|---|---|---|---|
| 0.5 | 0.007 (bisheriger Standard) | 22 % | 544 ms | 173 ms |
| 1.0 | 0.02 | 30 % | 211 ms | 72 ms |
| 2.0 | 0.1 (Standard) | 41 % | 60 ms | 20 ms |
| 3.0 | 0.1 | 48 % | 60 ms | 18 ms |
| 5.0 | 0.1 | 57 % | 60 ms | 14 ms |

Ein Bild des ET5 dauert 30 ms — die Verzögerung deutlich darunter zu drücken, bringt nichts mehr, weil Gerät, USB und der Netzwerkweg ohnehin mehr kosten. `one_euro_min_cutoff` nur erhöhen, wenn die Sicht dem Kopf immer noch nachläuft; senken, wenn die Sicht im Stillsitzen wandert.

Beide Werte gelten für alle sechs Kopfachsen, auch die in Millimetern. `beta` skaliert mit der Geschwindigkeit des Signals selbst, deshalb passt derselbe Wert für Grad pro Sekunde wie für Millimeter pro Sekunde.

**Filter-Empfehlungen:**

| Anwendungsfall | `min_cutoff` | `beta` |
|----------------|-------------|--------|
| Standard (Star Citizen) | `2.0` | `0.1` |
| Sehr glatt, etwas Lag | `1.0` | `0.05` |
| Schnelles Tracking, etwas Jitter | `3.0` | `0.1` |
| FPS-Shooter (max. Reaktion) | `5.0` | `0.15` |

---

### [neutral_pose]

```toml
[neutral_pose]
enabled = true
yaw = 11.7
pitch = 0.0
roll = -1.2
x = -200.0
y = -105.0
z = 970.0
```

Der Tracker meldet, wo dein Kopf **vor dem Sensor** ist — nicht, wie weit er sich von deiner gewohnten Sitzhaltung entfernt hat. Dasselbe ist das nur, wenn du genau auf der Sensorachse sitzt. Sitzt du 200 mm links davon und schaust zur Bildschirmmitte, ist dein Kopf tatsächlich um 11,7° gedreht, und genau das wird gemeldet: als Messung richtig, im Spiel unbrauchbar, weil „geradeaus" die Haltung ist, in der du zufällig sitzt.

Das Zentrieren merkt sich deine aktuelle Haltung und zieht sie von allem ab, was an die Ausgänge geht. Setze sie so, wie du wirklich sitzt:

| Wo | Wie |
|---|---|
| GUI | *Mittelpunkt* → **Setzen**. **Aufheben** kehrt zu Gerätekoordinaten zurück. |
| Kommandozeile | `osg-recenter`, bzw. `osg-recenter --clear` |
| Hotkey | `osg-recenter` in der Tastenkürzel-Verwaltung des Desktops auf eine Taste legen |

Einen eingebauten globalen Hotkey gibt es nicht, und das ist kein Versäumnis: Unter Wayland kann sich eine Anwendung keine Taste greifen, für die sie keinen Fokus hat — und den hat sie mitten im Spiel nie. Tastenkürzel gehören dem Compositor, also führt der verlässliche Weg über dessen eigene Verwaltung mit dem Befehl `osg-recenter`. Unter KDE: *Systemeinstellungen → Tastatur → Kurzbefehle → Befehl hinzufügen*.

Solange der Daemon keinen Kopf sieht, verweigert er das Zentrieren — ein ungültiges Bild meldet Nullen, und die zu speichern würde den Nullpunkt auf den Sensor selbst legen.

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `enabled` | Bool | `false` | Ob die gespeicherte Haltung abgezogen wird. `false` heißt: die Ausgänge bekommen Gerätekoordinaten. |
| `yaw`, `pitch`, `roll` | Float (Grad) | `0.0` | Die gemerkte Drehung. |
| `x`, `y`, `z` | Float (mm) | `0.0` | Die gemerkte Position. `z` ist der Abstand zum Tracker, im Sitzen etwa 600–1000 mm. |

Wird vom Zentrier-Befehl geschrieben; von Hand editieren geht, ist aber selten das, was man will. Der Wert steht in der Konfiguration, damit er einen Neustart überlebt — ein Mittelpunkt, den man nach jeder Anmeldung neu setzen muss, wird nie gesetzt.

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
settle_delay_s = 1.0
min_collect_seconds = 3.0
aspect_ratio = "auto"
coeff_x = []
coeff_y = []
```

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `polynomial_degree` | Int | `2` | Grad des Korrekturpolynoms. `2` = quadratisch. Höher = präziser aber über-fitted. |
| `samples_per_point` | Int | `30` | Mindestzahl Messungen pro Kalibrierpunkt (Mittelwert). Mehr = genauer, aber langsamer. |
| `settle_delay_s` | Float | `1.0` | Pause zwischen dem Erscheinen des Punkts und der ersten Messung. Solange wandert der Blick noch dorthin. |
| `min_collect_seconds` | Float | `3.0` | Mindestdauer der Messung je Punkt, unabhängig davon, wie schnell `samples_per_point` erreicht ist. |
| `aspect_ratio` | String | `"auto"` | Seitenverhältnis, über das die Kalibrierpunkte verteilt werden. `"auto"` nimmt den Monitor, auf dem die GUI läuft; `"32:9"` oder eine Zahl übersteuert das. |
| `coeff_x` | Liste | `[]` | Kalibrierkoeffizienten für X-Achse. Automatisch gefüllt nach Kalibrierung. |
| `coeff_y` | Liste | `[]` | Kalibrierkoeffizienten für Y-Achse. Automatisch gefüllt nach Kalibrierung. |

**Kalibrierung löschen:**
```bash
# In config.toml die Koeffizienten leeren:
sed -i 's/^coeff_x = .*/coeff_x = []/' ~/.config/openstargazer/config.toml
sed -i 's/^coeff_y = .*/coeff_y = []/' ~/.config/openstargazer/config.toml
```

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

Ergebnis des Ausricht-Schritts (GUI → *Gerät am Bildschirm ausrichten*).
Gespeichert wird **nur die Messung**; Pixeldichte, Bildschirmbreite und
Trackerposition werden daraus jedes Mal neu berechnet, damit keine
abgeleitete Zahl von ihrer Grundlage abdriften kann.

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|---------|--------------|
| `configured` | Bool | `false` | `false`, solange der Schritt nicht gelaufen ist. Alle abgeleiteten Werte gelten dann als unbekannt. |
| `monitor` | String | `""` | Bildschirm, auf dem gemessen wurde (z. B. `"DP-2"`). Die Messung gilt nur für diesen. |
| `screen_width_px` / `screen_height_px` | Int | `0` | Auflösung dieses Bildschirms zum Zeitpunkt der Messung. |
| `marker_left_px` / `marker_right_px` | Float | `0.0` | Die beiden Linienpositionen, die eingestellt wurden — in Pixeln vom linken Rand. |
| `marker_distance_mm` | Float | `185.0` | Physischer Abstand der beiden Markierungen am Gerät. Konstante des ET5; nur für andere Hardware zu ändern. |

**Wichtig:** Diese Werte werden derzeit **noch nicht** auf die Blickdaten
angewandt. Der Schritt misst die waagerechte Geometrie; senkrechter
Abstand und Sitzabstand werden separat abgeleitet. Seit v0.4.0 liegen dem
Projekt eigene Kopfhaltungs-Gewichte bei, sodass für ein vollständiges
Kopftracking-Setup kein Modell-Download nötig ist. Nach einem Umbau des
Aufbaus den Schritt einfach erneut ausführen.

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

### osg-tray — das Statussymbol

`osg-tray` bringt openstargazer in die Leiste und lässt es dort, auch wenn das Konfigurationsfenster geschlossen ist. Es wird so installiert, dass es mit der Sitzung startet; von Hand startet es `osg-tray`.

Die erste Menüzeile ist der Status, alle drei Sekunden aktualisiert, und sie unterscheidet drei Zustände, die man sonst leicht verwechselt:

| Zeile | Bedeutet |
|---|---|
| *verfolgt, 33 fps* | Daemon läuft, Tracker verbunden, Daten fließen |
| *läuft, kein Tracker* | Daemon läuft, Gerät fehlt oder ist von etwas anderem belegt |
| *Daemon gestoppt* | Es läuft nichts — der Dienst ist gestoppt oder wurde nie gestartet |

Darunter: **Mittelpunkt setzen** (dasselbe wie `osg-recenter`), **Tracking an**, **Einstellungen…** (öffnet das Konfigurationsfenster) und ein Untermenü **Dienst** mit *Starten*, *Neu starten*, *Stoppen* und *Entfernen…*.

Alles unter *Dienst*, was den Zustand ändert, fragt vorher nach — und sagt dazu, was die Antwort kostet: Ein gestoppter Daemon nimmt einem laufenden Spiel das Headtracking, und ein entfernter Dienst startet auch beim nächsten Anmelden nicht mehr. Entfernen deinstalliert das Programm nicht; `osg-setup` richtet den Dienst wieder ein.

Es ist ein eigenes Programm, weil die Tray-Bibliotheken GTK 3 sind und das Konfigurationsfenster GTK 4 ist — ein Prozess kann nicht beide laden.

**Wenn kein Symbol erscheint:** Das Tray braucht eine AppIndicator-Bibliothek. Unter Fedora: `sudo dnf install libappindicator-gtk3`. Ayatanas neueres `libayatana-appindicator` geht auch — beide Namen werden probiert.

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

Das GTK4/libadwaita-Einstellungsfenster. Beim ersten Start öffnet es die
geführte Ersteinrichtung, danach die Übersicht — ein 3×2-Raster aus Karten:

| Karte | Was dahinter liegt |
|-------|--------------------|
| **Kalibrierung** | Blickkalibrierung, Live-Vorschau, Bildschirm-Ausrichtung — und der Nullpunkt |
| **Spiele** | Welches Spiel erkannt und eingerichtet wurde |
| **Ausgabe** | OpenTrack UDP und FreeTrack, und der **UDP-Port** |
| **Blickvorschau** | Die Vollbild-Anzeige, wohin du gerade schaust |
| **Kurven** | Die Reaktionskurven je Achse |
| **Einstellungen** | Quelle der Kopfverfolgung, der Hintergrunddienst, die Sprache |

Über dem Raster steht die Statuszeile: ein farbiger Punkt, was der Tracker
gerade tut, und der Ein-/Ausschalter. Darüber trägt die Kopfzeile die
Sprachauswahl, das Profilmenü und drei Zustandspunkte (Dienst ·
Kopfverfolgung · Ausgabe).

**Gerät aus- und einschalten:**

Der Knopf neben der Statuszeile trennt das Gerät vom Daemon (die LEDs des
Trackers gehen aus) und verbindet es wieder — ohne den Daemon selbst zu
stoppen.

| Zustand | Wirkung |
|---------|---------|
| Ein | Gerät verbunden, Tracking aktiv, LEDs an |
| Aus | Gerät geschlossen, kein Tracking, LEDs aus |

Ausschalten dauert etwa eine Drittelsekunde, Einschalten ist sofort. Die
Statuszeile richtet sich nach dem Daemon, nicht nach dem Knopf — eine
Änderung von woanders (Tray-Symbol, `osg-ipc`) erscheint also auch hier.

**Der Nullpunkt** liegt auf der Kalibrierungsseite, neben der
Blickkalibrierung: beide beantworten, wo „geradeaus" für die Person im
Stuhl ist, einmal für die Augen und einmal für den Kopf.

**Der Ausgabe-Port** steht auf der Ausgabeseite. OpenTrack hört
standardmäßig auf 4242; zulässig ist 1024 bis 65535, und der Daemon lehnt
alles andere ab, statt einen Port zu speichern, den nichts benutzen kann.

**Der Hintergrunddienst** — starten, neu starten, stoppen, entfernen und
Autostart einrichten — liegt auf der Einstellungsseite. Es ist derselbe
Dienst, den auch das Tray-Symbol steuert, und er stellt vor dem Stoppen
und Entfernen dieselben Rückfragen.

**Profile** liegen im Kopfzeilen-Menü: zwischen gespeicherten wechseln, die
aktuellen Einstellungen unter einem Namen sichern, oder die Verwaltung zum
Umbenennen und Löschen öffnen. Der Knopf zeigt, welches Profil gerade gilt.

**Erweiterte Kopfverfolgung:**

Der Schalter auf der Einstellungsseite schaltet die Kameraquelle ein und aus
(`et5_ttp_camera` gegen `et5_native`, siehe `[input]`), mit den Kosten in
der Zeile. Zwei Dinge tut er, statt so zu tun als ob:

- Fehlt `onnxruntime` oder fehlen die Gewichte, ist der Schalter ausgegraut
  und die Zeile sagt, welches von beidem — die zwei brauchen verschiedene
  Abhilfen.
- Der Daemon bindet seine Quelle beim Start, also bittet die Zeile nach
  einer Änderung um einen Neustart und bietet einen Knopf dafür an, wenn der
  systemd-Benutzerdienst installiert ist. Nichts wird unter einer laufenden
  Kalibrierung ausgetauscht.

**Hinweis:** Die GUI kommuniziert mit dem Daemon über einen Unix-Socket (`~/.local/share/openstargazer/daemon.sock`). Der Daemon muss laufen.

---

### osg-setup (Wizard)

```bash
osg-setup
```

Interaktiver Einrichtungs-Wizard. Kann jederzeit erneut aufgerufen werden, um:
- Stream-Engine-Binärdateien herunterzuladen (optional — nur nötig bei Nutzung des `stream-engine`-Backends; das native Backend benötigt keinen Download)
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
| `get_status` | Verbindungsstatus, FPS, `tracking_enabled`, letztes Frame. `gaze_xy` und `head_pose` sind das, was die Ausgänge bekommen -- gefiltert, bei den Kopfachsen zusätzlich über Kurve, Skalierung und Invertierung; `gaze_raw_xy` und `head_pose_raw` die unveränderten Gerätewerte. `head_pose` führt `pos_valid` und `rot_valid` getrennt, weil das Gerät einen Kopf orten kann, ohne seine Drehung zu kennen |
| `get_config` | Aktuelle Konfiguration. `input` meldet die laufende Quelle, die vorhandenen Quellen und ob die Kameraquelle hier überhaupt starten könnte (`onnxruntime`, `weights`, `ready`) |
| `set_config` | Konfiguration ändern. Wirkt ohne Neustart, außer bei `input.source`: der Daemon bindet seine Quelle beim Start, diese wird also gespeichert und die Antwort trägt `restart_required`. Eine unbekannte Quelle wird namentlich abgelehnt |
| `set_tracking_enabled` | Tracking pausieren (`false`) oder fortsetzen (`true`) |
| `start_calibration` | Kalibrierung starten, liefert die Punktliste |
| `calibration_collect` | Messwerte für den gerade angezeigten Punkt sammeln |
| `calibration_finish` | Polynome berechnen, prüfen, nur bei brauchbarem Ergebnis speichern, Bericht je Punkt liefern |
| `calibration_cancel` | Lauf verwerfen, gespeicherte Kalibrierung bleibt |
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
one_euro_min_cutoff = 3.0   # etwas responsiver als der Standard
one_euro_beta = 0.1
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

## 10a. Sprache

Jeder Text, den Installer, Setup-Assistent und GUI anzeigen, kommt aus einer
Sprachdatei. Fünf werden mitgeliefert, und alle fünf sind vollständig:

```
openstargazer/locales/en.lang     English (die Referenz)
openstargazer/locales/de.lang     Deutsch
openstargazer/locales/fr.lang     Français
openstargazer/locales/it.lang     Italiano
openstargazer/locales/es.lang     Español
```

Das Format ist ein Eintrag je Zeile, `#` beginnt einen Kommentar:

```
install.title = openstargazer Setup
backend.chosen = Backend: {backend}
```

`{name}`-Platzhalter werden zur Laufzeit gefüllt — sie müssen genau so
geschrieben bleiben wie in `en.lang`. Ein Test weist eine Übersetzung
zurück, die einen anders schreibt oder weglässt: das wäre ein Absturz in
dem Moment, in dem der Text angezeigt wird, kein falsches Wort.

Umschalten im Einstellungsfenster — der Globus in der Kopfzeile oder die
vollständige Liste unter „Einstellungen" — oder über die Umgebung:

```bash
OSG_LANG=fr osg-config
```

Reihenfolge der Auswahl: `OSG_LANG`, dann `LC_ALL`, `LC_MESSAGES`, `LANG`,
dann Englisch. Ein Regionszusatz wird abgeschnitten, `de_DE.UTF-8` findet
also `de.lang`.

### Eine Sprache hinzufügen

1. `en.lang` nach `<code>.lang` kopieren, z. B. `pt.lang`
2. Die Texte rechts vom `=` übersetzen
3. Einen Anzeigenamen dafür in **jede** mitgelieferte Datei eintragen
   (`gui.language.pt = Português`) — die Auswahl zeigt alle Sprachen
   gleichzeitig, gleich welche gerade aktiv ist
4. Auswählen: `OSG_LANG=pt osg-config`

Nicht übersetzte Schlüssel fallen einzeln auf Englisch zurück, eine
Teilübersetzung ist also ab der ersten Zeile benutzbar. Dieser Rückfall ist
ein Sicherheitsnetz für eine Übersetzung in Arbeit, kein Plan für eine
ausgelieferte — ein Fenster, das halb in der einen und halb in der anderen
Sprache antwortet, ist schlechter als beides.

Log-Meldungen werden bewusst nicht übersetzt — sie bleiben englisch, damit
Fehlerberichte lesbar bleiben.

---

## 11. Kalibrierung

Die Kalibrierung verbessert die Genauigkeit des Blickpunkts: Sie legt ein
Polynom durch die Abweichung zwischen dem, wohin der Tracker glaubt dass du
schaust, und dem, wohin du tatsächlich geschaut hast.

### Kalibrierung starten

Der Daemon muss laufen — er besitzt den Eye Tracker und sammelt die
Messwerte, die GUI zeigt die Punkte an und gibt den Takt vor.

```bash
# Über GUI: osg-config → Blickkalibrierung → Kalibrieren
# Oder über den Assistenten:
osg-setup  # Schritt 6
```

Jeden Punkt ansehen, bis er verschwindet. Fünf oder neun Punkte sind
möglich; fünf reichen meistens. Danach wird der Fehler je Punkt als farbiger
Kreis gezeigt — grün ist gut, rot heißt: diesen Punkt wiederholen.

- **Enter** übernimmt das Ergebnis. Es landet in `config.toml` und wirkt ab
  sofort auf jeden Blickpunkt, ohne Neustart.
- **ESC** bricht ab. Die vorher gespeicherte Kalibrierung bleibt unberührt.

### Wann ein Lauf abgelehnt wird

Nicht jeder Lauf ergibt eine brauchbare Abbildung, und eine kaputte ist
schlechter als gar keine — sie überschreibt sonst kommentarlos eine
womöglich bessere vorherige. Ein Lauf muss deshalb drei Dinge erfüllen,
sonst wird er verworfen und die gespeicherte Kalibrierung bleibt unberührt:

- **Messwerte je Punkt.** Ein Punkt, der weniger als 60 % der eingestellten
  `samples_per_point` liefert, geht nicht in die Anpassung ein. Sein
  Mittelwert bestünde überwiegend aus Rauschen und würde die Kurve von allen
  anderen Punkten wegziehen. Bleiben weniger als drei brauchbare Punkte
  übrig, scheitert der Lauf.
- **Abweichung.** Im Mittel höchstens 0,06 und an keinem einzelnen Punkt
  mehr als 0,10 des Bildschirms — zwei Schranken, weil ein einzelner
  ruinierter Punkt im Mittelwert von vier guten untergeht. Auf 5120 px
  Breite sind 0,10 rund 500 px.
- **Erreichbarer Bereich.** Die Abbildung muss über die gesamte Rohspanne
  noch mindestens die Hälfte des kalibrierten Bereichs abdecken. Eine
  Anpassung, die alles in ein schmales Band staucht, macht Teile des
  Bildschirms unerreichbar.

Das Ergebnisfenster zeigt zu jedem Punkt, wie viele Messwerte ankamen und
wie weit er danebenliegt; verworfene Punkte erscheinen als offener roter
Ring. Wird der Lauf abgelehnt, nennt das Fenster den Grund und dieselben
Zahlen je Punkt. In aller Regel ist die Ursache ein Punkt, an dem der
Tracker den Blick verloren hat — dann hilft, den Sitzabstand zu prüfen und
neu zu kalibrieren.

### Wie es gespeichert wird

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

| Einstellung | Bedeutung |
|-------------|-----------|
| `polynomial_degree` | Grad der Anpassung je Achse. 2 ist ein guter Standard; höhere Grade überanpassen fünf Punkte. |
| `samples_per_point` | Mindestzahl Messwerte je Punkt. Bei ~33 Hz sind 30 Messwerte etwa eine Sekunde — die Dauer bestimmt aber `min_collect_seconds`, nicht diese Zahl. |
| `settle_delay_s` | Pause nach dem Erscheinen des Punkts, bevor gemessen wird. Der Punkt ist dabei schon zu sehen: das ist die Zeit zum Hinsehen. |
| `min_collect_seconds` | Mindestdauer der eigentlichen Messung. Zusammen mit `settle_delay_s` steht jeder Punkt so per Voreinstellung vier Sekunden. Samples, die in der Verlängerung noch eintreffen, werden mitgenommen. |
| `aspect_ratio` | Seitenverhältnis, über das die Punkte verteilt werden. `"auto"` nimmt den Monitor der GUI; `"32:9"` oder eine Zahl übersteuert das. |

### Wo die Punkte liegen

Auf 16:9 sitzen die Punkte bei 10 % und 90 % der Bildschirmbreite. Auf einem
breiteren Monitor rücken dieselben Anteile die äußeren Punkte im Winkel
deutlich weiter auseinander — in den Bereich, in dem der Tracker die
wenigsten Glints sieht und am unzuverlässigsten wird. Der waagerechte
Randabstand wächst deshalb mit dem Seitenverhältnis, gedeckelt beim
21:9-Wert: 32:9 wird also wie 21:9 kalibriert, mit Punkten bei 19,5 % und
80,5 %. Die senkrechte Verteilung bleibt unverändert. `aspect_ratio` von
Hand setzen, wenn der Monitor falsch erkannt wird, etwa auf einem über
mehrere Bildschirme gespannten Desktop.

### Kalibrierung zurücksetzen

```bash
# config.toml editieren und beide Koeffizientenlisten leeren:
coeff_x = []
coeff_y = []
```

Leere Listen bedeuten „keine Korrektur" — der rohe Blickpunkt wird
durchgereicht.

### Wann kalibrieren?

- Nach dem Umzug des Monitors
- Nach dem Verstellen des Trackers
- Wenn Blickpunkt systematisch versetzt erscheint

---

## 12. Profile

Ein Profil ist eine benannte Kopie der gesamten Konfiguration —
Kalibrierung, Kurven, Ausgabe, Eingangsquelle, alles aus `config.toml`. Sie
gibt es, damit sich eine Einrichtung für Star Citizen und eine für den
Schreibtischbetrieb nebeneinander halten lassen, ohne von Hand zu editieren.

Sie liegen als einzelne Dateien:

```
~/.config/openstargazer/profiles/<name>.toml
```

Im Profilmenü in der Kopfzeile des Einstellungsfensters:

| Aktion | Was sie tut |
|--------|-------------|
| **Aktuelle Einstellungen speichern** | Schreibt alles so, wie es gerade steht, unter einen Namen. Ein vorhandener Name wird überschrieben. |
| Einen Namen aus der Liste wählen | Lädt dieses Profil und macht es zur gültigen Konfiguration |
| **Profile verwalten** | Dasselbe, plus Umbenennen und Löschen |

Der Knopf in der Kopfzeile zeigt, welches Profil gilt. Das ist eine
gespeicherte Beschriftung (`[general] active_profile`), nicht etwas
Erschlossenes: ein aktiviertes Profil ist sonst nicht von einem zu
unterscheiden, das nie benutzt wurde — beim Aktivieren wird sein Inhalt ja
in `config.toml` kopiert.

Löschen fragt vorher — hinter einem Profil kann ein Kalibrierlauf stehen —
und das Löschen des aktiven Profils entfernt die Beschriftung, statt sie auf
eine Datei zeigen zu lassen, die es nicht mehr gibt.

Profile sind auch über die IPC-Schnittstelle erreichbar (`list_profiles`,
`activate_profile`).

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

Meldet der Daemon trotz vorhandener Bibliothek `INSUFFICIENT_LICENSE` bei
`gaze_data`/`head_pose`, fehlt keine Datei — siehe den Lizenzhinweis unter
`[device]` oben. Die meisten Einzelhandels-ET5 können dieses Backend gar
nicht nutzen; auf `et5_ttp_camera` wechseln.

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
~/.local/share/openstargazer/venv/bin/pip install ".[tray]"
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

**Lösung: Filter anpassen** — glatter im Stillstand, kostet rund 100 ms mehr Verzögerung:
```toml
[filter]
one_euro_min_cutoff = 1.0   # Glätter
one_euro_beta = 0.05
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
one_euro_min_cutoff = 3.0
one_euro_beta = 0.15
```

Viel weiter zu gehen lohnt nicht: Ein Kamerabild dauert 30 ms, und OpenTrack und das Spiel bringen ihre eigene Verzögerung mit.

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
pip install --user ".[tray]"   # oder venv-pip
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
