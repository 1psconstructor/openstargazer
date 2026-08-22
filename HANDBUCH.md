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
17. [Lizenz](#17-lizenz)
18. [Linksammlung](#18-linksammlung)

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
│    ├─► et5_stream_engine  libtobii_stream_engine.so --          │
│    │                      braucht eine Tobii-Lizenz, die        │
│    │                      die meisten Einzelhandelsgeräte       │
│    │                      nicht haben                           │
│    └─► mock                simuliertes Signal, zum Testen        │
│                            ohne Hardware                        │
│                                                                 │
│  osg-daemon  (Python-Hintergrundprozess, jeweils eine           │
│               Quelle aktiv)                                     │
│    ├─► OneEuro-Filter  (Rauschunterdrückung)                    │
│    ├─► Deadzone-Filter (Blickstabilisierung)                    │
│    ├─► Kurven-Mapping  (Achsen-Konfiguration)                   │
│    ├─► OpenTrack UDP   (→ OpenTrack → Star Citizen)             │
│    ├─► FreeTrack SHM   (alternative Ausgabe)                    │
│    └─► IPC-Socket      (Kommunikation mit GUI, Poll oder Push)  │
│                                                                 │
│  osg-config  (GTK4/libadwaita-GUI -- optionale Oberfläche)      │
│  osg-setup   (Setup-Wizard -- Ersteinrichtung)                  │
│  osg-tray    (GTK3-Statussymbol -- eigener Prozess)             │
│  osg-recenter (Einzelbefehl für den Nullpunkt)                  │
└─────────────────────────────────────────────────────────────────┘
```

**Datenfluss im Daemon:**
```
Gerät → [Gaze + HeadPose Callbacks]
       → [OneEuro-Filter]  (Jitter-Reduktion pro Achse)
       → [Deadzone-Filter] (Blickstabilisierung)
       → [Kurven-Mapping]  (nichtlineare Achsenabbildung)
       → [Scale + Invert]  (Skalierung und Invertierung)
       → [Nullpunkt-Abzug] (Zentrierung, falls aktiv)
       → [OpenTrack UDP / FreeTrack SHM]
```

Eine Standardinstallation liefert **vier** der sechs Achsen — Position und
Rollwinkel, dazu den Blickpunkt. Drehung (Yaw) und Neigung (Pitch)
brauchen die Kamera-Quelle (`et5_ttp_camera`), siehe
[§6 \[input\]](#input)
in der Konfigurationsreferenz; der Setup-Wizard bietet sie an. Das ist
eine Grenze des Sensors, keine offene Baustelle: alle 39 Felder, die der
Blickdatenstrom des ET5 liefert, wurden geprüft — keines dreht sich mit
dem Kopf.

openstargazer steht unter **GPL-3.0-or-later** — siehe
[§17 Lizenz](#17-lizenz).

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

Die CI testet bei jeder Änderung gegen Python 3.10, 3.11 und 3.12
(`.github/workflows/ci.yml`); neuere 3.x-Interpreter sollten funktionieren,
sind aber nicht Teil der Testmatrix.

### Unterstützte Distributionen
| Distribution | Paketmanager | Getestet |
|--------------|-------------|---------|
| **Fedora 39–43+** | dnf | ✓ Primär |
| Arch Linux / Manjaro | pacman | ✓ |
| Debian 12 / Ubuntu 22.04+ | apt | ✓ |
| andere Distros | manuell | eingeschränkt |

### Python-Paket-Extras

Das Paket `openstargazer` (`pyproject.toml`) wird mit einer Extras-Liste
installiert, meist `.[tray]` oder `.[gui,tray]`:

| Extra | Zieht nach | Nötig für |
|-------|-----------|-----------|
| `gui` | `pygobject>=3.44` | `osg-config`, den grafischen Auswahlbildschirm von `osg-setup` |
| `tray` | `pystray>=0.19` | (aus Kompatibilitätsgründen mitgeführt; das ausgelieferte Statussymbol ist `osg-tray`, ein GTK3/AppIndicator-Programm, nicht diese Bibliothek) |
| `camera` | `onnxruntime>=1.17` | Erweitertes Headtracking (`et5_ttp_camera`) — Drehung und Neigung |
| `dev` | `pytest`, `pytest-asyncio` | Die Test-Suite ausführen |

Für die vier Achsen des nativen Backends ist keins davon nötig — nur
`pyusb`, das als Kernabhängigkeit mitkommt, kein Extra.

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

  1) Fresh installation
  2) Repair (reinstall missing components)
  3) Uninstall -- everything
  4) Uninstall -- pick components
  5) Quit
  6) Create debug report
```

| Option | Beschreibung |
|--------|-------------|
| **1 – Neuinstallation** | Vollständige Installation aller Komponenten |
| **2 – Reparatur** | Prüft jede Komponente und installiert nur, was fehlt |
| **3 – Vollständige Deinstallation** | Entfernt alle Komponenten (mit Sicherheitsabfrage) |
| **4 – Ausgewählte Deinstallation** | Zeigt alle Komponenten mit Status, Auswahl per Nummer |
| **5 – Beenden** | Ohne Aktion verlassen |
| **6 – Debug-Report** | Sammelt Logs und Installationsstatus in einer Datei für Bugreports |

> **Installations-Log:** Jeder Lauf von `install.sh` schreibt an
> `~/.local/share/openstargazer/install.log` an, mit Zeitstempel und
> `[INFO|WARN|ERROR]`-Stufen. Nützlich, um frühere Installationsversuche
> nachzuvollziehen oder einem Bugreport beizulegen.

**Eine Neuinstallation bietet Tobiis Stream Engine nicht mehr an.** Sie
richtet immer das native Backend (`et5_native`) ein. Die Stream-Engine-
Binärdateien lassen sich weiterhin von Hand nachrüsten
(`scripts/fetch-stream-engine.sh`) — für das seltene lizenzierte Gerät,
siehe `[device]` in der [Konfigurationsreferenz](#6-konfigurationsdatei-im-detail).
Reparatur und die Liste der ausgewählten Deinstallation erkennen und
verwalten eine vorhandene Stream-Engine-Installation weiterhin, bieten
nur nicht mehr an, eine neue anzulegen.

### Ablauf einer Neuinstallation

```
1. Distribution erkennen, Systempakete installieren (GTK4, libadwaita, libusb, opentrack, …)
2. Python-Paket openstargazer installieren (pip, oder ein venv auf PEP-668-Systemen)
3. Backend in config.toml setzen (native, sofern nicht überschrieben)
4. osg-setup: Sprache + Wahl grafisch/Terminal, dann der gewählte Einrichtungsweg
5. udev-Regel (übersprungen, falls der Terminal-Wizard sie schon selbst installiert hat)
6. Prüfungen der Voraussetzungen des nativen Backends (pyusb, udev-Gruppenmitgliedschaft)
7. systemd-User-Service: installieren, aktivieren, starten
8. Desktop-Eintrag + Icon (übersprungen mit --no-gui)
9. OpenTrack-Profil als Sicherheitsnetz, falls der Weg oben keines angelegt hat
10. Zusammenfassung, mit dem Hinweis, einmal neu zu starten
```

Die Wahl von Sprache und grafisch/Terminal fällt direkt nach der
Installation des Python-Pakets, noch vor allen Schritten auf Systemebene
darunter — udev, der Dienst, der Desktop-Eintrag —, weil keiner davon
selbst noch etwas fragen muss: ab diesem Punkt läuft der Weg, den die
Nutzerin oder der Nutzer gewählt hat. Welcher Einrichtungsweg auch läuft,
er installiert udev-Regel und systemd-Dienst selbst; `install.sh` holt das
danach nur nach, falls das noch nicht passiert ist — eine Neuinstallation
fragt also nie zweimal nach derselben `pkexec`-/`sudo`-Authentifizierung.

---

### 3.1 Fedora

```bash
cd scripts
chmod +x install.sh
./install.sh
```

**Was passiert (Fedora-spezifisch):**

1. **Python-Prüfung** — Fedora 43 liefert Python 3.12, das ist kompatibel.

2. **Systempakete** — folgende Pakete werden über `dnf` installiert:
   ```
   python3-gobject  gtk4  libadwaita  libusb  usbutils  curl  tar
   ```

3. **OpenTrack** — nicht in Fedoras offiziellen Repos oder RPM Fusion Free (Fedora 43+).
   Der Installer bietet vier Optionen an:
   1. RPM Fusion Free aktivieren und via dnf installieren (nicht für alle Versionen verfügbar)
   2. Via Flatpak von Flathub installieren
   3. Aus dem GitHub-Quellcode bauen (empfohlen für Fedora 43, inklusive Wine/LUG-Unterstützung)
   4. Überspringen (später manuell installieren)

4. **Python-Paket** — Fedora hat PEP 668 aktiviert, daher:
   - Erster Versuch: normales `pip install --user`
   - Bei Ablehnung: automatischer Fallback auf **venv** unter `~/.local/share/openstargazer/venv/`
   - Entry-Point-Skripte werden nach `~/.local/bin/` verlinkt

5. **udev-Regeln** — nach `/etc/udev/rules.d/70-openstargazer.rules` kopiert. Da `plugdev` unter Fedora nicht existiert, nutzt die Regel `TAG+="uaccess"` (keine Gruppenmitgliedschaft nötig).

6. **systemd-User-Service** — installiert und aktiviert. Wurde ein venv verwendet, wird `ExecStart` automatisch auf den venv-Pfad angepasst.

**OpenTrack unter Fedora installieren:**

```bash
# Option A: RPM Fusion Free aktivieren
sudo dnf install -y \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install -y opentrack

# Option B: Flatpak (Flathub)
flatpak install -y flathub io.github.opentrack.OpenTrack

# Option C: Aus dem GitHub-Quellcode bauen (Fedora 43+, inklusive Wine-Ausgabe-Plugin)
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
- Arch nutzt PEP 668 seit Python 3.11+ → venv-Fallback greift automatisch
- `python-venv` ist im Standardpaket `python` enthalten
- Der Benutzer wird der Gruppe `plugdev` hinzugefügt (danach ab- und wieder anmelden)

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
- `python3-venv` wird explizit gelistet, da es auf Minimal-Installationen fehlen kann
- Debian 12+ und Ubuntu 23.04+: PEP 668 aktiv → venv-Fallback
- Ubuntu 22.04: direkte pip-Installation funktioniert (kein venv nötig)
- Der Benutzer wird der Gruppe `plugdev` hinzugefügt

---

### 3.4 Andere Distributionen

Bei unbekannten Paketmanagern gibt der Installer diese Pakete zur manuellen Installation aus:

```
GTK4, libadwaita, python3-gi (PyGObject), libusb, usbutils, opentrack, curl, tar
```

Danach:
```bash
python3 -m pip install --user ".[gui,tray]"
# oder mit PEP 668:
python3 -m venv ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install ".[gui,tray]"
```

---

### Installations-Flags

```bash
./install.sh [--no-gui] [--mock] [--lang <code>]
```

| Flag | Wirkung |
|------|--------|
| `--no-gui` | Überspringt Desktop-Eintrag und Icon-Installation |
| `--mock` | (Entwickler) Installiert ohne echte Hardware-Abhängigkeiten |
| `--lang <code>` | Erzwingt die Sprache des Installers selbst (`en`, `de`, `fr`, `it`, `es`) für diesen Lauf, unabhängig von `OSG_LANG` und der Systemsprache. Wird exportiert, sodass der Setup-Wizard, an den übergeben wird, dieselbe Wahl übernimmt. |

Ohne `--lang` folgt die Sprache des Skripts selbst `OSG_LANG`, dann der
Systemsprache, dann Englisch — dieselbe Reihenfolge wie im Rest des
Projekts, siehe [§10a Sprache](#10a-sprache).

---

## 4. Erster Start & Setup-Wizard

`osg-setup` ist der Einstiegspunkt für sowohl den Terminal-Wizard als auch
die grafische geführte Einrichtung — welcher der beiden läuft, wird einmal
auf einem kleinen Startbildschirm entschieden, außer der Terminal-Weg wird
mit `--cli` erzwungen.

```bash
osg-setup                # Startbildschirm: Sprache + Grafisch/Terminal
osg-setup --cli          # Startbildschirm überspringen, direkt den Text-Wizard starten
osg-setup --profile-only # Nur LUG-Helper erkennen und ein OpenTrack-Profil
                          # schreiben; gibt bei Erfolg nichts aus, beendet
                          # sich mit Fehlercode, wenn keins erzeugt werden
                          # konnte. Wird von install.sh als Sicherheitsnetz
                          # genutzt -- rührt setup_completed nie an und
                          # zeigt kein Fenster.
```

### Der Startbildschirm

Ein kleines GTK-Fenster (nur sichtbar, wenn sowohl ein Display als auch
ein Terminal vorhanden sind und `--cli` nicht übergeben wurde): eine
Sprache aus der Knopfreihe wählen, dann **Grafisch** oder **Terminal**.
**Grafisch** speichert die gewählte Sprache und startet `osg-config` — das
ist die einzige Stelle, die dann anhand von
`settings.general.setup_completed` in `config.toml` entscheidet, ob die
geführte Einrichtung oder die Einstellungsübersicht erscheint. **Terminal**
startet den Text-Wizard unten im selben Prozess.

### Der Text-Wizard (`osg-setup --cli`)

**Schritt 1 – Tracking-Backend**
- Beim voreingestellten `native`-Backend gibt es nichts zu installieren —
  der Schritt bestätigt das nur. Es spricht direkt über USB, ohne
  Tobii-Binärdateien und ohne `tobiiusbserviced`.
- Bei `stream-engine` prüft der Schritt, ob `libtobii_stream_engine.so`
  und `tobiiusbservice` unter `~/.local/share/openstargazer/` liegen, und
  bietet an, sie herunterzuladen (`fetch-stream-engine.sh`). Das
  Stream-Engine-Backend ist optional; für Head-Pitch ist es nicht nötig
  (das übernimmt der nächste Schritt ohne es) — und auf den meisten
  Einzelhandelsgeräten funktioniert es ohnehin nicht, aus dem
  Lizenzgrund unter `[device]` unten.

**Erweitertes Headtracking (direkt nach Schritt 1, bei jedem Lauf)**
- Der Schritt, der entscheidet, ob es vier oder sechs Achsen gibt. Der
  Blickdatenstrom trägt keine Kopfdrehung — über alle 39 Gerätefelder
  gemessen —, daher kommen Drehung und Neigung von der Infrarotkamera des
  ET5 und einem neuronalen Netz, dessen Gewichte mit dem Projekt
  ausgeliefert werden (GPL-3.0).
- Die Kosten stehen vor der Frage, nicht danach: `onnxruntime` als
  Extra-Paket, etwa 6 ms pro Bild (ein Fünftel eines Kerns bei 33 Hz), und
  dass die Bilder gelesen, ausgewertet und verworfen werden — nichts wird
  gespeichert, nichts verlässt die Maschine.
- Die Vorauswahl ist nie Ja, wenn die Quelle auf dieser Maschine nicht
  starten konnte, und Nein bewegt eine `stream-engine`-Nutzerin oder
  einen -Nutzer nicht vom eigenen Backend weg. Später änderbar im
  Einstellungsfenster oder als `source` unter `[input]`.

**Schritt 2 – Hardware-Erkennung**
- Sucht via `lsusb` nach bekannten Tobii-USB-IDs
- Bekannte PIDs: `0127`, `0118`, `0106`, `0128`, `010a`, `0313`
- Gerät nicht gefunden: optional trotzdem fortfahren

**Schritt 3 – LUG-Helper / Star Citizen**
- Sucht automatisch nach der LUG-Helper-Konfiguration unter `~/.config/starcitizen-lug/`
- Erkennt Wine-Prefix, Runner-Pfad, ESYNC/FSYNC-Einstellungen
- Manuelle Eingabe möglich, falls keine Konfiguration gefunden wird

**Schritt 4 – OpenTrack-Profil**
- Erzeugt ein OpenTrack-INI-Profil für Star Citizen
- Standard-Port: 4242 (UDP)

**Schritt 5 – Anleitung im Spiel**
- Zeigt die Star-Citizen-Head-Tracking-Einstellungen

**Schritt 6 – Kalibrierung (optional)**
- Nur möglich, wenn der Daemon bereits läuft — der eigene Dienst-Schritt
  des Wizards (unten) ist an dieser Stelle noch nicht gelaufen

**Dienst & udev einrichten (zuletzt, ohne Nummer)**
- Installiert den systemd-User-Service, aktiviert ihn (beides mit
  `[Y/n]` abgefragt) und prüft, ob er wirklich innerhalb weniger Sekunden
  den Zustand `active` erreicht — bei Fehlschlag werden die letzten
  Zeilen von `systemctl status` ausgegeben.
- Installiert die udev-Regel (ebenfalls abgefragt), lädt udev neu und
  erinnert daran, das Gerät ab- und wieder anzustecken.
- Endet mit einer Zusammenfassung (Backend, Tracking-Modus, Hardware,
  OpenTrack), den Befehlen zum Starten des Daemons und Öffnen der GUI,
  sowie einem Hinweis auf die Ko-fi-Seite des Projekts.

### Die grafische geführte Einrichtung (in `osg-config`)

Läuft automatisch in `osg-config`, solange
`settings.general.setup_completed` noch `false` ist — bei einer
Neuinstallation, oder nach **Setup erneut ausführen** im
Einstellungsfenster. Es sind acht Vollbildseiten, jede mit "N/8" im
Kopfbereich nummeriert, mit **Überspringen** jederzeit verfügbar (mit
Sicherheitsabfrage) und **Weiter**/Zweitknöpfen, die den Ablauf steuern:

| # | Seite | Macht |
|---|------|------|
| 1 | Tracking-Backend | Dieselbe Prüfung wie Schritt 1 des Text-Wizards; bei `stream-engine` ohne die Binärdateien gibt es statt einer Terminalfrage einen **Abrufen**-Knopf |
| 2 | Erweitertes Headtracking | Dieselbe Entscheidung wie beim Kamera-Schritt des Text-Wizards, als **Ja**/**Nein**-Knöpfe; zeigt den Hinweis auf fehlendes `onnxruntime`/fehlende Gewichte direkt inline |
| 3 | Hardware-Erkennung | Dieselbe `lsusb`-Prüfung wie Schritt 2 |
| 4 | Star Citizen / LUG-Helper | Erkennt automatisch wie Schritt 3; findet sich nichts, zeigt die Seite ein eingebettetes Formular für Wine-Prefix und Runner statt eines zweiten Fensters |
| 5 | OpenTrack-Profil | Ein Port-Auswahlfeld (Standard 4242) und ein **Installieren**-Knopf |
| 6 | Anleitung im Spiel | Derselbe Text wie Schritt 5 des Text-Wizards |
| 7 | Kalibrierung | **Jetzt kalibrieren** öffnet das Kalibrierungsfenster direkt hier; **Später** geht einfach weiter |
| 8 | Dienst & udev | Ein **Installieren**-Knopf, der den systemd-Service installiert, aktiviert, dessen Start prüft und die udev-Regel installiert (via `pkexec`, das den eigenen Authentifizierungsdialog des Desktops aufruft) — alles in einem Schritt, das Ergebnis wird direkt angezeigt |

Seite 8 abzuschließen (oder von irgendeiner Seite aus zu überspringen)
setzt `settings.general.setup_completed = true` und ersetzt die geführte
Einrichtung durch die Einstellungsübersicht.

### Den Wizard erneut ausführen

```bash
osg-setup
# oder, um den Text-Weg zu erzwingen:
osg-setup --cli
```

Die geführte Einrichtung lässt sich auch aus `osg-config` heraus erneut
öffnen: Karte **Einstellungen** → **Setup erneut ausführen**.

---

## 5. Deinstallation

### Über das Installationsskript (empfohlen)

```bash
cd scripts
./install.sh
# → Option 3 (vollständig) oder Option 4 (ausgewählt) wählen
```

**Option 3 – Vollständige Deinstallation** entfernt nach Bestätigung:
- systemd-User-Service (stoppen + deaktivieren + Datei löschen)
- udev-Regeln
- Tobii-USB-Service und Binärdateien
- Python-Paket / venv / Symlinks
- Desktop-Eintrag und Icon
- Benutzerdaten (`~/.config/openstargazer`) – **separate Abfrage, Standard: Nein**

**Option 4 – Ausgewählte Deinstallation** zeigt alle Komponenten mit ihrem aktuellen Installationsstatus und lässt einzelne per Nummer auswählen:

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

Punkte 3 und 4 betreffen nur Installationen, die die optionale Stream
Engine von Hand nachgerüstet haben; eine Standardinstallation mit
nativem Backend zeigt dort "nicht gefunden".

### Manuelle Deinstallation (Fallback)

Falls das Skript nicht verfügbar ist:

```bash
# Dienste stoppen und deaktivieren
systemctl --user stop openstargazer.service 2>/dev/null || true
systemctl --user disable openstargazer.service 2>/dev/null || true
sudo systemctl stop tobiiusb.service 2>/dev/null || true
sudo systemctl disable tobiiusb.service 2>/dev/null || true

# Service-Dateien entfernen
rm -f ~/.config/systemd/user/openstargazer.service
sudo rm -f /etc/systemd/system/tobiiusb.service
systemctl --user daemon-reload && sudo systemctl daemon-reload

# udev-Regeln entfernen
sudo rm -f /etc/udev/rules.d/70-openstargazer.rules
sudo udevadm control --reload-rules

# Desktop-Eintrag und Icon entfernen
rm -f ~/.local/share/applications/openstargazer.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/openstargazer.svg

# Python-Paket und venv entfernen
pip uninstall openstargazer 2>/dev/null || true
rm -rf ~/.local/share/openstargazer/venv
rm -f ~/.local/bin/osg-daemon ~/.local/bin/osg-config ~/.local/bin/osg-setup \
      ~/.local/bin/osg-tray ~/.local/bin/osg-recenter

# Tobii-Binärdateien entfernen
rm -f ~/.local/share/openstargazer/lib/libtobii_stream_engine.so
sudo rm -f /usr/local/sbin/tobiiusbserviced
sudo rm -rf /usr/local/lib/tobiiusb

# Konfiguration entfernen (OPTIONAL – löscht alle Einstellungen!)
rm -rf ~/.config/openstargazer/

# Benutzer aus plugdev entfernen (Debian/Ubuntu/Arch)
sudo gpasswd -d "$USER" plugdev
```

### Nur Konfiguration zurücksetzen (ohne Deinstallation)

```bash
rm ~/.config/openstargazer/config.toml
osg-setup  # erzeugt neue Standardkonfiguration
```

---

## 6. Konfigurationsdatei im Detail

Die Konfiguration liegt unter: `~/.config/openstargazer/config.toml`

Sie wird beim ersten Start automatisch mit Standardwerten angelegt.

---

### [general]

```toml
[general]
language = ""
setup_completed = false
active_profile = ""
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `language` | String | `""` | Die gespeicherte UI-Sprache (`en`, `de`, `fr`, `it`, `es`). Leer bedeutet automatische Erkennung — siehe [§10a Sprache](#10a-sprache). Wird von der Sprachauswahl geschrieben; `OSG_LANG` überschreibt sie weiterhin für einen einzelnen Lauf. |
| `setup_completed` | Bool | `false` | Ob `osg-config` die Einstellungsübersicht (`true`) oder die geführte Einrichtung (`false`) öffnet. Wird vom letzten Schritt des Text-Wizards gesetzt, und beim Abschließen oder Überspringen der grafischen geführten Einrichtung. |
| `active_profile` | String | `""` | Der Name des gerade geltenden Profils, rein als Beschriftung — siehe [§12 Profile](#12-profile). |

---

### [device]

```toml
[device]
preferred_url = ""
use_head_pose = true
backend = "native"
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `preferred_url` | String | `""` | Direkte USB-URL des Geräts (z. B. `"usb://0x2104/0x0127"`). Leer = erstes gefundenes Gerät verwenden. Wird nur vom `stream-engine`-Backend genutzt. |
| `use_head_pose` | Bool | `true` | Bei `true`: Kopfposition und -drehung werden verarbeitet. Bei `false`: nur Blickpunktdaten, kein Headtracking. |
| `backend` | String | `"native"` | Der ältere Name für die Eingabequelle, lesbar gehalten, damit bestehende Konfigurationen weiter funktionieren: `"native"` bedeutet die Quelle `et5_native`, `"stream-engine"` bedeutet `et5_stream_engine`. Pro Lauf überschreibbar mit `osg-daemon --backend stream-engine`. Ein unbekannter Wert fällt mit einer Warnung auf den Standard zurück. Siehe `[input]` unten, dieselbe Einstellung mit der vollständigen Liste. |

**Natives Backend (Standard):** `openstargazer/native/` spricht direkt über
USB mit dem ET5, ohne Tobiis Stream-Engine-Binärdateien und ohne den
Hintergrunddienst `tobiiusbserviced`. Es liefert Kopf**position**,
**Rollwinkel** und den Blickpunkt. Es liefert **keine** Drehung oder
Neigung — der Blickdatenstrom trägt keine Kopfdrehung, was über alle 39
Gerätefelder gemessen wurde, statt einfach nicht implementiert zu sein.
Diese beiden Achsen kommen von der unten unter `[input]` beschriebenen
Quelle `et5_ttp_camera`.

Ein Backend-Wechsel erfordert keine Neuinstallation. Das
`stream-engine`-Backend ist optional und auf den meisten
Einzelhandelsgeräten **überhaupt nicht nutzbar**: `tobii_gaze_data_subscribe`
und `tobii_head_pose_subscribe` geben ohne Stream-Engine-Lizenz beide
`INSUFFICIENT_LICENSE` zurück, und diese Lizenz gibt es nur mit
bestimmten OEM-/Partner-Deals, nicht mit einem bloßen Endkundengerät.
Diese Lücke — Kopfdrehung, die außerhalb von Tobiis eigener Software
niemand unter Linux erreichen konnte — ist der Grund für `et5_ttp_camera`:
es liest dieselbe Infrarotkamera über das eigene Modell des Projekts aus,
statt Tobiis Bibliothek um eine Pose zu bitten, für die keine Lizenz
vorliegt. Der Installer bietet `stream-engine` nicht mehr an, und die
Reparatur pflegt eine vorhandene Installation auch nicht mehr; der
manuelle Weg bleibt für das seltene lizenzierte Gerät bestehen — einmal
`./scripts/fetch-stream-engine.sh` ausführen, dann selbst
`backend = "stream-engine"` unter `[device]` setzen.

---

### [input]

```toml
[input]
source = "et5_native"

[input.et5_camera]
model_path = ""
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `source` | String | `"et5_native"` | Welche Eingabequelle der Daemon startet. Siehe Tabelle unten. Ein unbekannter Name wird beim Start mit der Liste der vorhandenen Namen abgelehnt. |
| `et5_camera.model_path` | String | `""` | Pfad zu einem Head-Pose-ONNX-Modell. Leer bedeutet die mitgelieferten Gewichte: zuerst das Benutzerverzeichnis `~/.local/share/openstargazer/models/`, dann die Kopie im Paket selbst. |

| Quelle | Braucht | Achsen |
|--------|-------|------|
| `et5_native` | nichts außer `pyusb` | Position, Rollwinkel, Blick |
| `et5_ttp_camera` | `onnxruntime` (`pip install 'openstargazer[camera]'`) | dasselbe **plus Drehung und Neigung** |
| `et5_stream_engine` | Tobiis inoffizielle Binärdateien **und** eine Stream-Engine-Lizenz, die die meisten Einzelhandelsgeräte nicht haben | im Prinzip alle sechs — siehe Hinweis oben; ohne Lizenz keine |
| `mock` | nichts | ein simuliertes Signal, zum Testen ohne Hardware |

`config.toml` führt außerdem einen Block `[input.webcam]`
(`device_index`, `width`, `height`, `fps`, `model_path`). Er ist für eine
mögliche künftige Quelle auf Basis einer gewöhnlichen Webcam reserviert;
in diesem Release ist keine Eingabequelle namens `webcam` registriert,
`source` akzeptiert also nur die vier Namen oben.

**Erweitertes Headtracking (`et5_ttp_camera`)** liest die Infrarotkamera
des ET5 parallel zum Blickdatenstrom und schickt jedes Bild durch ein
neuronales Netz, dessen Gewichte mit dem Projekt unter GPL-3.0
ausgeliefert werden (`openstargazer/models/head-pose.onnx`, von Grund auf
auf `replicantface` trainiert — MIT). Kein Download eines Fremdmodells
nötig; der Gesichtsausschnitt wird aus den Augenpositionen des
Blickdatenstroms geschnitten, ein separates Lokalisierungsmodell ist also
ebenfalls nicht nötig.

Was es kostet: `onnxruntime` als Extra-Paket, etwa 6 ms pro Bild (ein
Fünftel eines Kerns bei 33 Hz), und dass die Kamera gelesen wird — die
Bilder werden ausgewertet und verworfen, nichts wird gespeichert und
nichts verlässt die Maschine. Der Blickdatenstrom bleibt unbeeinflusst:
33,1 fps gemessen mit und ohne, jedes Sample eigenständig.

**Der Kopf bleibt auch verfolgt, wenn die Augen kurz verloren gehen.** Der
Gesichtsausschnitt, den das Pose-Netz liest, wird aus den Augenpositionen
des Blickdatenstroms geschnitten — verlor man die Augen, verlor man
früher also auch den Kopf, in früheren Tests bei einer weiten
Kopfbewegung auf 69 % der Bilder. Der Ausschnitt wird jetzt über eine
Lücke hinweg fortgeschrieben, und die vom Netz selbst vorhergesagte
Streuung entscheidet, ob ihm weiter zu trauen ist: auf dem Kopf bleibt die
Streuung bei rund 4,7°, auf leerem Hintergrund springt sie über 20° — mit
deutlichem Abstand zwischen beiden Bereichen.

Der Daemon wählt seine Quelle beim Start, eine Änderung wirkt also erst
beim nächsten Start:

```bash
systemctl --user restart openstargazer
```

Der Setup-Wizard fragt danach, und im Einstellungsfenster gibt es dafür
einen Schalter — keine Einstellung, für die eine Datei bearbeitet werden
muss.

---

### [tracking]

```toml
[tracking]
mode = "head_and_gaze"
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `mode` | String | `"head_and_gaze"` | Tracking-Modus (siehe Tabelle) |

**Verfügbare Modi:**

| Modus | Beschreibung | Sendet an OpenTrack |
|------|-------------|-------------------|
| `"head_and_gaze"` | Kopfdrehung/-position + Blickpunkt | Kopfdaten (6-DoF) |
| `"head_only"` | Nur Headtracking, kein Eyetracking | Kopfdaten (6-DoF) |
| `"gaze_only"` | Nur Blickpunkt, kein Headtracking | Blick als X/Y |

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

Der **One-Euro-Filter** ist ein adaptiver Tiefpassfilter. Er reduziert Jitter bei langsamen Bewegungen und lässt schnelle Bewegungen fast verzögerungsfrei durch.

Kopfachsen und Blick werden mit **getrennten Parametern** gefiltert, weil sie in unterschiedlichen Einheiten gemessen werden: die Kopfachsen in Grad und Millimetern, der Blick in normierten Bildschirmkoordinaten von 0 bis 1. Eine Kopfdrehung überstreicht Dutzende Grad pro Sekunde, eine Sakkade dagegen ganze Einheiten — daher muss `beta` auf der Blickseite um Größenordnungen höher liegen, um überhaupt zu greifen.

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `one_euro_min_cutoff` | Float (Hz) | `2.0` | Minimale Grenzfrequenz für die **Kopfachsen**. **Kleiner = ruhiger im Stillstand, aber mehr Verzögerung.** Bereich: 0,5–5,0 |
| `one_euro_beta` | Float | `0.1` | Geschwindigkeitskoeffizient für die **Kopfachsen**. **Größer = weniger Nacheilen bei schnellen Bewegungen.** Bereich: 0,0–0,2 |
| `gaze_min_cutoff` | Float (Hz) | `1.0` | Minimale Grenzfrequenz für den **Blick**. Bereich: 0,5–3,0 |
| `gaze_beta` | Float | `1.0` | Geschwindigkeitskoeffizient für den **Blick**. Bereich: 0,0–4,0 |
| `gaze_deadzone_px` | Float (Pixel) | `30.0` | Totzone des Blickpunkts in Pixeln. Kleine Augenbewegungen unterhalb dieser Schwelle werden ignoriert, um Flackern zu vermeiden. Wird über `[display]` in einen Bruchteil des Bildschirms umgerechnet, sobald dieser Schritt einmal ausgeführt wurde; sonst als Pixel auf einer angenommenen 1920×1080-Fläche behandelt. |

Gemessen bei 33 Hz, für eine Sakkade über 60 % des Bildschirms. "Verbleibender Jitter" ist der Anteil des Fixationsrauschens, der den Filter übersteht — niedriger ist ruhiger:

| `gaze_min_cutoff` | `gaze_beta` | Verbleibender Jitter | 90 % einer Sakkade |
|---|---|---|---|
| 1,0 | 0,0 | 26 % | 394 ms |
| 1,0 | 1,0 (Standard) | 27 % | 121 ms |
| 1,0 | 2,0 | 28 % | 61 ms |
| 2,0 | 1,0 | 38 % | 91 ms |

`gaze_beta` zuerst erhöhen, wenn der Punkt dem Blick hinterherhinkt; `gaze_min_cutoff` senken, wenn er nie zur Ruhe kommt.

Die Kopfachsen wurden genauso gemessen, bei 33 Hz. "90 % einer Drehung" ist ein 20°-Schritt; "Rückstand bei 60°/s" ist, wie weit der gemeldete Winkel einer gleichmäßigen Drehung hinterherhinkt, angegeben als der Zeitversatz, dem das entspricht; "verbleibender Jitter" ist der Anteil des geräteeigenen Jitters von 0,05°/Bild, der übersteht:

| `one_euro_min_cutoff` | `one_euro_beta` | Verbleibender Jitter | 90 % einer Drehung | Rückstand bei 60°/s |
|---|---|---|---|---|
| 0,5 | 0,007 (Standard bis v0.2.x) | 22 % | 544 ms | 173 ms |
| 1,0 | 0,02 | 30 % | 211 ms | 72 ms |
| 2,0 | 0,1 (Standard) | 41 % | 60 ms | 20 ms |
| 3,0 | 0,1 | 48 % | 60 ms | 18 ms |
| 5,0 | 0,1 | 57 % | 60 ms | 14 ms |

Ein Bild des ET5 dauert 30 ms, die Verzögerung deutlich darunter zu drücken bringt daher nichts Messbares mehr — Gerät, USB und der Netzwerksprung kosten schon mehr. `one_euro_min_cutoff` nur erhöhen, wenn sich die Ansicht immer noch anfühlt, als würde sie dem Kopf hinterherlaufen; senken, wenn sie im Sitzen driftet.

Beide Einstellungen gelten für alle sechs Kopfachsen, auch die in Millimetern. `beta` skaliert mit der Geschwindigkeit des Signals selbst, derselbe Wert funktioniert also für Grad pro Sekunde und Millimeter pro Sekunde ohne eigenen Parameter.

**Filter-Empfehlungen:**

| Einsatzzweck | `min_cutoff` | `beta` |
|----------|-------------|--------|
| Standard (Star Citizen) | `2.0` | `0.1` |
| Sehr ruhig, etwas Verzögerung | `1.0` | `0.05` |
| Schnelles Tracking, etwas Jitter | `3.0` | `0.1` |
| FPS-Shooter (maximale Reaktion) | `5.0` | `0.15` |

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

Der Tracker meldet, wo sich der Kopf **vor dem Sensor** befindet, nicht wie weit er sich von der gewöhnlichen Sitzposition entfernt hat. Das ist nur dasselbe, wenn genau auf der Achse des Sensors gesessen wird. 200 mm links davon, mit Blick zur Bildschirmmitte, ist der Kopf tatsächlich um 11,7° gedreht, und die Messung sagt das auch so — als Messung korrekt, in einem Spiel unbrauchbar, weil "geradeaus" immer die Haltung ist, in der man gerade sitzt.

Zentrieren speichert die aktuelle Pose und zieht sie von allem ab, was die Ausgaben erhalten. So einstellen, wie tatsächlich gesessen wird:

| Wo | Wie |
|---|---|
| GUI | Karte Kalibrierung → **Setzen** (neben **Aufheben**, das zu Gerätekoordinaten zurückkehrt) |
| Kommandozeile | `osg-recenter`, oder `osg-recenter --clear` |
| Tastenkürzel | `osg-recenter` im Tastenkürzel-Editor des Desktops auf eine Taste legen |
| Statussymbol | **Mittelpunkt setzen** im Menü von `osg-tray` |

Es gibt kein eingebautes globales Tastenkürzel, und das ist kein Versehen: unter Wayland kann eine Anwendung sich kein Tastenkürzel für Tasten reservieren, für die sie keinen Fokus hat — und mitten im Spiel hat sie den nie. Tastenkürzel gehören dem Compositor, der verlässliche Weg ist daher der Tastenkürzel-Editor des Desktops, der auf den Befehl `osg-recenter` zeigt. Unter KDE: *Systemeinstellungen → Kurzbefehle → Befehle → Hinzufügen*.

Der Daemon verweigert das Zentrieren, solange er keinen Kopf sieht — ein ungültiges Bild liest sich als Nullen, und diese zu speichern würde den Ursprung auf den Sensor selbst legen.

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `enabled` | Bool | `false` | Ob die gespeicherte Pose abgezogen wird. `false` bedeutet: die Ausgaben erhalten Gerätekoordinaten. |
| `yaw`, `pitch`, `roll` | Float (Grad) | `0.0` | Die gemerkte Drehung. |
| `x`, `y`, `z` | Float (mm) | `0.0` | Die gemerkte Position. `z` ist der Abstand zum Tracker, sitzend etwa 600–1000 mm. |

Wird vom Zentrier-Befehl geschrieben; von Hand editieren funktioniert, ist aber selten das, was man will. Der Wert steht in der Konfiguration, damit er einen Neustart übersteht — ein Nullpunkt, den man nach jeder Anmeldung neu setzen muss, wird nie gesetzt.

---

### [output.opentrack_udp]

```toml
[output.opentrack_udp]
enabled = true
host = "127.0.0.1"
port = 4242
```

UDP-Ausgabe im OpenTrack-Protokoll (48-Byte-Paket, 6× Little-Endian-Double).

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `enabled` | Bool | `true` | UDP-Ausgabe an/aus |
| `host` | String | `"127.0.0.1"` | Ziel-IP für UDP-Pakete. Über die GUI oder den IPC-Aufruf `set_config` werden nur `127.0.0.1`, `::1` oder `localhost` akzeptiert; ein wirklich entferntes Ziel muss direkt in `config.toml` eingetragen werden, das umgeht diese Prüfung. |
| `port` | Int | `4242` | UDP-Port. Muss mit der OpenTrack-Einstellung übereinstimmen. Von `set_config` durchgesetzter gültiger Bereich: 1024–65535. |

---

### [output.freetrack_shm]

```toml
[output.freetrack_shm]
enabled = false
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `enabled` | Bool | `false` | FreeTrack-Shared-Memory-Ausgabe aktivieren. Erfordert Wine-FreeTrack-Unterstützung. Für die meisten Setups nicht nötig. |

---

### [axes.yaw], [axes.pitch], [axes.roll], [axes.x], [axes.y], [axes.z]

Jede der 6 Tracking-Achsen lässt sich einzeln konfigurieren:

```toml
[axes.yaw]
scale = 1.0
invert = false
curve = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `scale` | Float | `1.0` | Multiplikator für die Achse. `2.0` = doppelter Bereich, `0.5` = halber Bereich. |
| `invert` | Bool | `false` | Kehrt die Achsenrichtung um. |
| `curve` | Liste von Punkten | linear | Reaktionskurve als Liste von [x, y]-Kontrollpunkten, 2 bis 7 Punkte, nach `x` sortiert. Erlaubt nichtlineare Antwort. |

**Achsenreferenz:**

| Achse | Bedeutung | Wertebereich |
|------|---------|-------------|
| `yaw` | Kopfdrehung links/rechts | -180° bis +180° |
| `pitch` | Kopfneigung hoch/runter | -90° bis +90° |
| `roll` | Kopfneigung seitlich | -90° bis +90° |
| `x` | Kopfposition links/rechts | mm (ca. -300 bis +300) |
| `y` | Kopfposition hoch/runter | mm (ca. -300 bis +300) |
| `z` | Kopfposition vor/zurück | mm (ca. -300 bis +300) |

---

### [star_citizen]

```toml
[star_citizen]
lug_prefix = ""
runner_path = ""
```

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `lug_prefix` | String | `""` | Der Wine-Prefix, den LUG-Helper (oder die manuelle Eingabe des Setup-Wizards) für Star Citizen nutzt. |
| `runner_path` | String | `""` | Pfad zum Wine-/Proton-Runner, mit dem es gestartet wird. |

Wird automatisch vom Setup-Wizard oder dem LUG-Helper-Schritt der
geführten Einrichtung eingetragen — siehe [§9](#9-star-citizen--lug-helper).

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

Das Ergebnis des Ausrichtungsschritts (GUI → Karte Kalibrierung →
**Ausrichten**, `gui.actions.display` = *Gerät am Bildschirm ausrichten*).
Nur die **Messung** wird gespeichert; Pixeldichte, physische
Bildschirmbreite und Trackerposition werden jedes Mal neu daraus
abgeleitet (über schreibgeschützte Eigenschaften auf dem
Einstellungsobjekt — `px_per_mm`, `screen_width_mm`, `tracker_offset_mm`,
`tracker_offset_norm`), sodass keine gespeicherte Zahl von dem abweichen
kann, woraus sie berechnet wurde.

| Einstellung | Typ | Standard | Beschreibung |
|---------|------|---------|-------------|
| `configured` | Bool | `false` | `false`, bis der Schritt einmal ausgeführt wurde. Solange gilt jeder abgeleitete Wert als unbekannt. |
| `monitor` | String | `""` | Der Bildschirm, auf dem gemessen wurde (z. B. `"DP-2"`). Die Messung gilt nur für diesen. |
| `screen_width_px` / `screen_height_px` | Int | `0` | Auflösung dieses Bildschirms zum Zeitpunkt der Messung. |
| `marker_left_px` / `marker_right_px` | Float | `0.0` | Die beiden Linienpositionen, auf die man sich geeinigt hat, in Pixeln vom linken Rand. |
| `marker_distance_mm` | Float | `185.0` | Physischer Abstand zwischen den Markierungen auf dem Gerät. Eine Konstante des ET5; nur bei anderer Hardware ändern. |

**Wofür es heute verwendet wird:** sobald `configured` wahr ist, rechnet
der Daemon `gaze_deadzone_px` aus Pixeln in einen Bruchteil der
tatsächlichen Bildschirmgröße um, statt eine feste Fläche anzunehmen —
derselbe Pixelwert bedeutet damit auf jedem Monitor denselben physischen
Abstand. Die horizontale Geometrie (Pixeldichte, Bildschirmbreite,
Tracker-Versatz zur Mitte) fließt noch nicht in die Blick-auf-Bildschirm-
Abbildung selbst ein. Den Schritt erneut ausführen, wann immer sich der
physische Aufbau ändert.

**So funktioniert das Ausrichtungsfenster:** Es öffnet sich im Vollbild
auf dem erkannten Monitor. Zwei Linien werden per Ziehen und mit den
Pfeiltasten (1 px pro Tastendruck, 10 px mit einem schnellen Modifikator)
auf die beiden physisch auf dem Gerät aufgedruckten Markierungen gezogen,
185 mm auseinander. Speichern schickt die Messung per IPC an den Daemon
(`set_config` mit einem `display`-Block); ESC bricht ohne Speichern ab.

---

## 7. Betrieb & Funktionen

### osg-tray — das Statussymbol

`osg-tray` bringt openstargazer in die Leiste und lässt es dort, auch wenn das Konfigurationsfenster geschlossen ist. Es wird so installiert, dass es mit der Sitzung startet; von Hand startet es `osg-tray`.

Die erste Zeile des Menüs ist der Status, alle drei Sekunden aktualisiert, und unterscheidet drei leicht zu verwechselnde Zustände:

| Zeile | Bedeutet |
|---|---|
| *tracking, 33 fps* | Daemon läuft, Tracker verbunden, Daten fließen |
| *running, no tracker* | Daemon läuft, Gerät fehlt oder ist von etwas anderem belegt |
| *daemon stopped* | nichts läuft — der Dienst ist gestoppt oder wurde nie gestartet |

Darunter: **Mittelpunkt setzen** (dasselbe wie `osg-recenter`), eine Checkbox **Tracking an**, **Einstellungen…** (öffnet das Konfigurationsfenster) und ein Untermenü **Dienst** mit *Starten*, *Neu starten*, *Stoppen* und *Entfernen…*.

Alles unter *Dienst*, was den Zustand ändert, fragt vorher nach und sagt, was die Antwort kostet — den Daemon zu stoppen nimmt einem laufenden Spiel das Headtracking weg, und den Dienst zu entfernen verhindert auch, dass er beim nächsten Login zurückkehrt. Entfernen deinstalliert das Programm nicht: `osg-setup` bringt den Dienst zurück.

Es ist ein eigenes Programm, weil die Tray-Bibliotheken GTK 3 sind, während das Konfigurationsfenster GTK 4 ist, und ein Prozess nicht beides laden kann.

**Wenn kein Icon erscheint:** Der Tray braucht eine AppIndicator-Bibliothek. Unter Fedora: `sudo dnf install libappindicator-gtk3`. Ayatanas neuere `libayatana-appindicator` funktioniert ebenfalls — beide Namen werden versucht.

### osg-daemon

Der Hintergrundprozess. Läuft als systemd-User-Service.

```bash
# Status prüfen
systemctl --user status openstargazer

# Starten
systemctl --user start openstargazer

# Stoppen
systemctl --user stop openstargazer

# Neu starten (nach Konfigurationsänderung)
systemctl --user restart openstargazer

# Daemon-Log ansehen
journalctl --user -u openstargazer -f

# Direkt mit Ausgabe starten (Debugging)
osg-daemon --verbose

# Mock-Modus (ohne Hardware, sinusförmige Testdaten)
osg-daemon --mock

# Eigene Konfigurationsdatei
osg-daemon --config /pfad/zu/config.toml

# Backend nur für diesen Lauf erzwingen
osg-daemon --backend stream-engine
```

**Daemon-Flags:**

| Flag | Beschreibung |
|------|-------------|
| `--mock` | Synthetische Daten statt echter Hardware (~90 Hz, sinusförmig) |
| `--verbose` / `-v` | Ausführliches Logging (DEBUG-Level) |
| `--config PFAD` | Alternativer Pfad zu config.toml |
| `--backend {native,stream-engine}` | Überschreibt `[device] backend` / `[input] source` nur für diesen Lauf |

**Auto-Reconnect:** Der Daemon verbindet sich bei Geräteverlust automatisch alle 2 Sekunden neu.

Im Daemon-Prozess ist `faulthandler` aktiviert: killt der systemd-Watchdog
ihn wegen eines Hängers, landet im Journal ein Python-Traceback statt
eines undurchsichtigen libc-Absturzes.

---

### osg-config (GUI)

```bash
osg-config
```

Das GTK4/libadwaita-Einstellungsfenster. Beim ersten Start — oder nach
**Setup erneut ausführen** — öffnet es die
[geführte Einrichtung](#die-grafische-geführte-einrichtung-in-osg-config);
sonst die Übersicht, ein Raster aus Karten:

| Karte | Was dahintersteckt |
|------|-------------------|
| **Kalibrierung** | Blickkalibrierung, die Live-Vorschau, die Bildschirmausrichtung, der Nullpunkt und die Achsenvorschau |
| **Spiele** | Welches Spiel erkannt und eingerichtet wurde |
| **Ausgabe** | OpenTrack-UDP und FreeTrack, und der **UDP-Port** |
| **Blickvorschau** | Öffnet die Vollbild-Überlagerung, die zeigt, wohin gerade geblickt wird |
| **Kurven** | Die Reaktionskurven pro Achse |
| **Einstellungen** | Erweitertes Headtracking, Setup erneut ausführen, der Hintergrunddienst und die Sprache |

Über dem Raster sitzt die Statuszeile: ein farbiger Punkt, was der Tracker gerade tut, und die An/Aus-Kontrolle. Darunter trägt die Kopfzeile die Sprachauswahl, das Profilmenü und drei Zustandspunkte (Dienst · Headtracking · Ausgabe).

**Gerät aus- und wieder einschalten:**

Der Knopf neben der Statuszeile trennt das Gerät vom Daemon (die LEDs des Trackers erlöschen) und verbindet es wieder, ohne den Daemon selbst zu stoppen.

| Zustand | Wirkung |
|-------|--------|
| An  | Gerät verbunden, Tracking aktiv, LEDs an |
| Aus | Gerät geschlossen, kein Tracking, LEDs aus |

Ausschalten dauert etwa ein Drittel einer Sekunde, Einschalten geschieht sofort. Die Statuszeile folgt dem Daemon, nicht dem Knopf, eine Änderung von anderswo — dem Tray-Symbol, einem gescripteten IPC-Aufruf — zeigt sich also auch hier.

**Die Karte Kalibrierung** enthält, über den Kalibrierlauf selbst hinaus:

- Eine Live-Vorschau der aktuellen Blickposition auf einem schematischen Bildschirm.
- **Ausrichten** — öffnet das [Fenster zur Bildschirmausrichtung](#display).
- **Setzen** / **Aufheben** — den [Nullpunkt](#neutral_pose), direkt neben
  der Blickkalibrierung: beide beantworten, was "geradeaus" für die
  Person im Stuhl bedeutet, einmal für die Augen und einmal für den Kopf.
- **Achsenvorschau** (**Anzeigen**) — öffnet einen Live-Überblick aller
  sechs Achsen mit dem Wert, der tatsächlich den Daemon verlässt, sowohl
  gefiltert/kurviert/skaliert als auch roh. Eine Achse, die eine Quelle
  nicht liefern kann (Drehung/Neigung bei `et5_native`), wird mit dem
  Grund als nicht unterstützt markiert, statt eine dauerhafte Null zu
  zeigen — dieselbe Tabelle, die das Achsenfenster nutzt, ist nach der
  *aktiven Quelle* geordnet, nicht nach Backend, und bleibt daher auch
  korrekt, wenn zwischen `et5_native` und `et5_ttp_camera` gewechselt wird.

**Der Ausgabe-Port** steht auf der Karte Ausgabe. OpenTrack hört standardmäßig auf 4242; alles von 1024 bis 65535 wird akzeptiert, und der Daemon verweigert den Rest, statt einen Port zu speichern, den nichts nutzen kann.

**Die Karte Einstellungen** enthält:

- **Erweitertes Headtracking** — der Schalter, der die Kamera-Quelle an-
  und ausschaltet (`et5_ttp_camera` gegen `et5_native`, siehe `[input]`),
  mit den Kosten direkt in der Zeile. Fehlen `onnxruntime` oder die
  Gewichte, ist der Schalter ausgegraut und die Zeile sagt, welches von
  beiden es ist — beides hat unterschiedliche Lösungen. Der Daemon bindet
  seine Quelle beim Start, die Zeile fragt daher nach einem Neustart und
  bietet dafür einen Knopf, wenn der systemd-User-Service installiert
  ist. Nichts wird unter einer laufenden Kalibrierung ausgetauscht.
- **Setup erneut ausführen** — öffnet die geführte Einrichtung erneut, ab Seite 1.
- Der **Hintergrunddienst** — starten, neu starten, stoppen, installieren, entfernen. Derselbe Dienst, den auch das Tray-Symbol steuert, mit denselben Rückfragen vor dem Stoppen oder Entfernen.
- Die Liste der **Sprachen** — jede mitgelieferte Sprache als Radio-Zeile, sofort wirksam.

**Profile** liegen im Kopfzeilen-Menü: zwischen gespeicherten wechseln, die aktuellen Einstellungen unter einem Namen speichern, oder die Verwaltung zum Umbenennen und Löschen öffnen. Der Knopf zeigt, welches Profil gerade gilt.

**Hinweis:** Die GUI kommuniziert mit dem Daemon über einen Unix-Socket (`~/.local/share/openstargazer/daemon.sock`). Der Daemon muss laufen.

**Mock-Modus** – die GUI ohne Hardware oder Daemon starten:
```bash
osg-config --mock
```
Startet die GUI mit einem eingebauten Simulations-Client (kein Daemon nötig). Nützlich zum Testen der Oberfläche und zum Konfigurieren von Kurven ohne Hardware.

---

### osg-setup (Wizard)

```bash
osg-setup
```

Der vollständige Ablauf steht in [§4](#4-erster-start--setup-wizard). Kann jederzeit erneut ausgeführt werden, um:
- Stream-Engine-Binärdateien herunterzuladen (optional — nur nötig bei Nutzung des `stream-engine`-Backends; das native Backend braucht keinen Download)
- die LUG-Helper-Konfiguration zu aktualisieren
- das OpenTrack-Profil neu zu erzeugen
- Erweitertes Headtracking an- oder abzuschalten
- den systemd-Dienst oder die udev-Regel neu zu installieren

---

### IPC-Schnittstelle

Der Daemon stellt einen Unix-Socket unter
`~/.local/share/openstargazer/daemon.sock` bereit, ein JSON-Objekt pro
Zeile: `{"id": ..., "method": ..., "params": {...}}` rein,
`{"id": ..., "result": {...}}` oder `{"id": ..., "error": "..."}` raus.

**Sicherheit:**
- Socket und Verzeichnis sind auf `0600`/`0700` beschränkt (nur Besitzer)
- Nur freigegebene Methoden werden akzeptiert
- Anfragen sind auf 64 KiB pro Zeile begrenzt
- Das UDP-Ausgabeziel muss `127.0.0.1`, `::1` oder `localhost` sein; der Port muss 1024–65535 liegen

**Live-Status ohne Polling — `subscribe`:**

Eine Verbindung kann einmal `{"method": "subscribe", "params": {"interval_s": 0.1}}`
senden. `interval_s` wird auf 0,015–5,0 s begrenzt (Standard 0,1 s). Ab
dann schickt der Server jedes Mal, wenn der Tracker ein neues Bild
liefert **und** seit der letzten Zustellung mindestens `interval_s`
vergangen ist, von sich aus eine Nachricht — keine Antwort auf eine
Anfrage:

```json
{"event": "status", "data": { …genau die get_status-Form unten… }}
```

`unsubscribe` beendet die Zustellung auf dieser Verbindung. Zwei
eingebaute Fenster — die Blicküberlagerung und die Achsenvorschau —
nutzen das statt Polling, was früher hieß, rund dreißigmal pro Sekunde
je einen Socket zu öffnen und zu schließen; die Einstellungsübersicht
fragt weiterhin alle 100 ms per `get_status` ab, da sie nur eine
Statuszeile aktualisieren muss statt mit Bildwiederholrate neu zu
zeichnen.

Verfügbare Methoden:

| Methode | Beschreibung |
|--------|--------------|
| `ping` | Gibt `{"pong": true}` zurück |
| `get_status` | Verbindungsstatus, FPS, `tracking_enabled`, aktuelles Bild — siehe Feldliste unten |
| `get_config` | Aktuelle Konfiguration — siehe Feldliste unten |
| `set_config` | Konfiguration ändern — siehe unten |
| `set_tracking_enabled` | `{"enabled": bool}` → Tracking pausieren (`false`, LEDs aus) oder fortsetzen (`true`); gibt `{"tracking_enabled": ..., "connected": ...}` zurück |
| `recenter` | Speichert die aktuelle Kopfpose als neuen Nullpunkt (siehe `[neutral_pose]`); gibt `{"recentered": true, "neutral_pose": {...}}` zurück, oder einen Fehler, falls keine gültige Pose vorliegt |
| `clear_recenter` | Setzt den Nullpunkt zurück auf Gerätekoordinaten; gibt `{"recentered": false}` zurück |
| `start_calibration` | `{"mode": 5\|9, "aspect": float?}` → gibt das Punktlayout, `settle_delay`, `seconds_per_point` zurück |
| `calibration_collect` | `{"index": int}` → sammelt Samples für diesen Punkt, gibt den laufenden Mittelwert zurück |
| `calibration_finish` | Fittet, prüft, speichert nur bei brauchbarem Ergebnis; gibt den Bericht pro Punkt zurück |
| `calibration_cancel` | Verwirft den Lauf, behält die gespeicherte Kalibrierung |
| `list_profiles` | Profile auflisten |
| `activate_profile` | `{"name": str}` → ein Profil aktivieren |
| `subscribe` / `unsubscribe` | Siehe oben |

**Felder von `get_status`:**

| Feld | Bedeutung |
|---|---|
| `connected` | Tracker erreichbar |
| `tracking_enabled` | Ob Tracking gerade pausiert ist |
| `backend` | Der geltende Wert von `[device] backend` |
| `source` | Der geltende Wert von `[input] source` |
| `calibrated` | Ob eine Kalibrierung gespeichert ist (`coeff_x` nicht leer) |
| `fps` | Bildrate des Trackers, `0.0` wenn das letzte Bild veraltet ist |
| `gaze_xy` | Was die Ausgaben erhalten: gefiltert und kalibriert |
| `gaze_raw_xy` | Die unveränderte Gerätemessung |
| `gaze_valid` | Ob das aktuelle Blick-Sample brauchbar ist |
| `head_pose` | `{x, y, z, yaw, pitch, roll, pos_valid, rot_valid, pos_from_one_eye, valid}` — was die Ausgaben erhalten: gefiltert, kurviert/skaliert/invertiert, mit abgezogenem Nullpunkt |
| `head_pose_raw` | Dieselbe Form, unveränderte Gerätemessung |
| `frame_age_s` | Sekunden seit dem letzten Bild, oder `null` |
| `pipeline_fps` | Rate, mit der die Pipeline selbst Ausgaben erzeugt |
| `recentered` | Ob `[neutral_pose] enabled` gesetzt ist |

`head_pose`/`head_pose_raw` melden `pos_valid` und `rot_valid` getrennt,
da das Gerät einen Kopf orten kann, ohne sagen zu können, wie er gedreht
ist; `pos_from_one_eye` markiert eine Position, die aus nur einem Auge
abgeleitet wurde (weniger verlässlich) statt aus beiden.

**Felder von `get_config`:** `filter` (alle fünf Schlüssel von `[filter]`),
`output` (`opentrack_udp` und `freetrack_shm`, jeweils
enabled/host/port), `tracking.mode`, sowie `input` — `source` (laufende
Quelle), `available` (sortierte Liste aller registrierten
Quellennamen), `camera` (`{onnxruntime, weights, ready}` — Bereitschaft
von `et5_ttp_camera`).

**`set_config`:** akzeptiert Teil-Updates unter `filter`, `output`
(`opentrack_udp`, `freetrack_shm`), `display` und `input.source`. Alles
wirkt sofort außer `input.source`: der Daemon bindet seine Quelle beim
Start, eine Änderung wird also nur gespeichert, und die Antwort trägt
`{"saved": true, "restart_required": true}`. Eine unbekannte Quelle wird
mit Namen abgelehnt (`Unknown input source '...'. Known sources: ...`).
Ein nicht-loopback `output.opentrack_udp.host` oder ein Port außerhalb
des Bereichs löst einen Fehler aus, statt gespeichert zu werden.

**Kalibrierungsablauf:** `start_calibration({"mode": 5})` →
`calibration_collect({"index": 0})` für jeden Punkt der Reihe nach →
`calibration_finish()`. Das Ergebnis von `calibration_finish` trägt
`success`, `residuals` (Liste pro Punkt), `mean_residual`, `message` (der
Grund bei Fehlschlag) und `points` — jeweils mit Koordinaten, Sample-Zahl
und Residuum, womit der Ergebnisbildschirm eingefärbt wird.

---

## 8. OpenTrack-Integration

### So funktioniert es

osg-daemon sendet 6-DoF-Daten via UDP an OpenTrack:
```
osg-daemon → UDP :4242 → OpenTrack → Wine (FreeTrack/TrackIR) → Star Citizen
```

Das UDP-Paket enthält 48 Byte (6 × 8-Byte Little-Endian-Double):
```
Byte  0– 7: X-Position (mm)
Byte  8–15: Y-Position (mm)
Byte 16–23: Z-Position (mm)
Byte 24–31: Yaw (Grad)
Byte 32–39: Pitch (Grad)
Byte 40–47: Roll (Grad)
```

### OpenTrack konfigurieren

**Eingang:** `UDP over network` – Port `4242`

**Ausgang:** `Wine` – Runner und Prefix aus der LUG-Helper-Konfiguration

**Filter:** Keiner (osg-daemon filtert bereits intern)

### Startreihenfolge (wichtig!)

```
1. Star Citizen starten
2. Daemon starten:  systemctl --user start openstargazer
3. OpenTrack öffnen
4. OpenTrack-Profil laden
5. OpenTrack starten (grüner Play-Knopf)
```

---

## 9. Star Citizen / LUG-Helper

### Einstellungen im Spiel

```
Einstellungen → COMMS, FOIP & HEAD TRACKING
  Head Tracking Source: TrackIR
  Enable Head Tracking: ✓
```

### LUG-Helper-Konfigurationspfade

Der Wizard sucht automatisch in dieser Reihenfolge nach der LUG-Konfiguration:
```
~/.config/starcitizen-lug/config
~/.config/starcitizen-lug/settings
~/.config/starcitizen-lug/lug-helper.conf
~/.config/starcitizen-lug/lug-helper.cfg
~/.config/starcitizen-lug/preflight_conf
```
Findet sich keine davon, wird als Fallback jede Datei im Verzeichnis geprüft.

Erkannte Schlüssel (Groß- und Kleinschreibung): `WINEPREFIX`, `wine_prefix`, `SC_PREFIX`, `WINE_RUNNER_PATH`, `runner_path`, `ESYNC`, `FSYNC`

> **Hinweis für GE-Proton-Nutzer:** `export PROTON_VERB="runinprefix"` zur
> Startumgebung hinzufügen (z. B. `sc-launch.sh`). Das ist nötig, damit
> das Wine-Ausgabe-Plugin von OpenTrack mit GE-Proton-Runnern korrekt
> funktioniert.

---

## 10. Betriebsmodi & Einsatzszenarien

### Modus 1: Headtracking + Eyetracking (Standard)

```toml
[tracking]
mode = "head_and_gaze"

[device]
use_head_pose = true
```

Aktiviert alle 6 Freiheitsgrade (Yaw, Pitch, Roll, X, Y, Z) plus Blickpunkt — sechs nur mit `et5_ttp_camera` oder einem lizenzierten `et5_stream_engine`; vier (Position, Rollwinkel, Blick) beim standardmäßigen `et5_native`.

---

### Modus 2: Nur Headtracking

```toml
[tracking]
mode = "head_only"

[device]
use_head_pose = true
```

**Empfohlen für:** Nutzer, die Headtracking für Star Citizen ohne Beteiligung der Augenbewegung wollen. Geringere CPU-Last, klarere Kurven.

---

### Modus 3: Nur Eyetracking

```toml
[tracking]
mode = "gaze_only"

[device]
use_head_pose = false
```

**Empfohlen für:** Anwendungen, die nur Blickdaten brauchen (Barrierefreiheits-Werkzeuge, Blicküberlagerung usw.).

---

### Modus 4: Nur Rotation (keine Positionsverfolgung)

Wenn der Tracker weit entfernt sitzt und Positionsdaten unzuverlässig werden:

```toml
[axes.x]
scale = 0.0   # X-Position deaktiviert

[axes.y]
scale = 0.0   # Y-Position deaktiviert

[axes.z]
scale = 0.0   # Z-Position deaktiviert
```

Yaw, Pitch und Roll bleiben aktiv.

---

## 10a. Sprache

Jeder sichtbare Text des Installers, des Setup-Wizards und der GUI kommt
aus einer Sprachdatei. Fünf sind mitgeliefert, alle fünf vollständig:

```
openstargazer/locales/en.lang     English (die Referenz)
openstargazer/locales/de.lang     Deutsch
openstargazer/locales/fr.lang     Français
openstargazer/locales/it.lang     Italiano
openstargazer/locales/es.lang     Español
```

Das Format ist ein Eintrag pro Zeile, `#` beginnt einen Kommentar:

```
install.title = openstargazer Setup
backend.chosen = Backend: {backend}
```

`{name}`-Platzhalter werden zur Laufzeit gefüllt — genau so buchstabiert lassen wie in `en.lang`. Ein Test lehnt eine Übersetzung ab, die einen Platzhalter anders schreibt oder weglässt, weil das ein Absturz im Moment der Anzeige wäre, nicht nur ein falsches Wort.

Sprache umschalten im Einstellungsfenster — der Globus in der Kopfzeile,
die Sprachliste der Karte Einstellungen, oder der Startbildschirm des
Setups — oder über die Umgebung:

```bash
OSG_LANG=fr osg-config
```

Reihenfolge der Auswahl: `OSG_LANG`, dann die in `config.toml`
gespeicherte Sprache (`[general] language`), dann `LC_ALL`,
`LC_MESSAGES`, `LANG`, dann Englisch. Ein Regionssuffix wird abgeschnitten,
`de_DE.UTF-8` findet also `de.lang`. Jeder Einstiegspunkt, der Text zeigt
(`osg-config`, `osg-tray`, `osg-recenter`, `osg-setup`), wendet die
gespeicherte Sprache beim Start an — eine in einem von ihnen getroffene
Wahl gilt also auch für die anderen, ohne die Systemsprache jedes Mal neu
zu erkennen.

### Eine Sprache hinzufügen

1. `en.lang` nach `<code>.lang` kopieren, z. B. `pt.lang`
2. Den Text rechts von jedem `=` übersetzen
3. Einen Anzeigenamen dafür in *jede* mitgelieferte Datei eintragen
   (`gui.language.pt = Português`), weil die Auswahl alle Sprachen
   gleichzeitig zeigt, egal welche gerade aktiv ist
4. Auswählen: `OSG_LANG=pt osg-config`

Nicht übersetzte Schlüssel fallen einzeln auf Englisch zurück, eine
unvollständige Übersetzung ist also von der ersten Zeile an nutzbar. Das
ist ein Sicherheitsnetz für eine Übersetzung in Arbeit, kein Plan für eine
ausgelieferte — ein Fenster, das halb in einer und halb in einer anderen
Sprache antwortet, ist schlimmer als beides einzeln.

Log-Meldungen werden absichtlich nicht übersetzt — sie bleiben Englisch, damit Bugreports lesbar bleiben.

---

## 11. Kalibrierung

Kalibrierung verbessert die Blickgenauigkeit, indem ein Polynom gefittet
wird, das abbildet, wo der Tracker glaubt hinzusehen, auf das, wohin
tatsächlich geblickt wurde.

### Kalibrierung starten

Der Daemon muss laufen — er besitzt den Eye Tracker und sammelt die
Samples, während die GUI die Punkte anzeigt und den Ablauf taktet.

```bash
# Über die GUI: osg-config → Karte Kalibrierung → Kalibrieren
# Oder von der Kalibrierungsseite der geführten Einrichtung
# Oder vom Text-Wizard: osg-setup --cli, Schritt 6
```

Jeden Punkt ansehen, bis er verschwindet. Fünf oder neun Punkte werden unterstützt; fünf reichen für die meisten Setups. Danach wird der Fehler pro Punkt als farbiger Kreis angezeigt — grün ist gut, rot bedeutet, dieser Punkt sollte wiederholt werden.

- **Enter** übernimmt das Ergebnis. Es wird in `config.toml` geschrieben und ab diesem Moment auf jedes Blick-Sample angewendet; kein Neustart nötig.
- **ESC** bricht ab. Die vorher gespeicherte Kalibrierung bleibt unverändert.

### Wenn ein Lauf abgelehnt wird

Nicht jeder Lauf ergibt eine brauchbare Abbildung, und eine kaputte ist schlimmer als keine — unbemerkt überschreibt sie stillschweigend eine möglicherweise bessere vorherige. Ein Lauf muss daher drei Hürden nehmen, sonst wird er verworfen und die gespeicherte Kalibrierung bleibt unangetastet:

- **Samples pro Punkt.** Ein Punkt, der weniger als 60 % der konfigurierten `samples_per_point` liefert, fällt aus dem Fit heraus. Sein Mittelwert wäre größtenteils Rauschen und würde die Kurve von allen anderen Punkten wegziehen. Bleiben weniger als drei brauchbare Punkte übrig, schlägt der Lauf fehl. Die Sammlung für einen einzelnen Punkt ist außerdem auf 5 Sekunden gedeckelt, egal wie wenige Samples bis dahin ankamen, damit ein verlorener Tracker den ganzen Lauf nicht unbegrenzt aufhält.
- **Abweichung.** Höchstens 0,06 im Mittel und höchstens 0,10 des Bildschirms an einem einzelnen Punkt — zwei Hürden, weil ein verunglückter Punkt im Mittel von vier guten verschwindet. Auf einem 5120 px breiten Bildschirm sind 0,10 etwa 500 px.
- **Erreichbarer Bereich.** Über den gesamten rohen Bereich muss die Abbildung mindestens die Hälfte des kalibrierten Bereichs abdecken. Ein Fit, der alles in ein schmales Band quetscht, macht Teile des Bildschirms unerreichbar.

Der Ergebnisbildschirm zeigt, wie viele Samples an jedem Punkt ankamen und wie weit er daneben liegt; verworfene Punkte erscheinen als offener roter Ring. Wird der Lauf abgelehnt, nennt der Bildschirm den Grund und zeigt dieselben Zahlen pro Punkt. Die übliche Ursache ist ein Punkt, an dem der Tracker den Blick verloren hat — Sitzabstand prüfen und erneut kalibrieren.

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
|---------|---------|
| `polynomial_degree` | Grad des Fits pro Achse. 2 ist ein guter Standard; höhere Grade überfitten fünf Punkte. |
| `samples_per_point` | Mindestzahl an Blick-Samples pro Punkt. Bei ~33 Hz dauern 30 Samples etwa eine Sekunde — die Dauer wird aber von `min_collect_seconds` bestimmt, nicht von dieser Zahl. |
| `settle_delay_s` | Pause, nachdem der Punkt erscheint, bevor irgendetwas aufgezeichnet wird. Der Punkt ist schon sichtbar: das ist die Zeit, ihn anzusehen. |
| `min_collect_seconds` | Mindestdauer der Aufzeichnung selbst. Zusammen mit `settle_delay_s` steht jeder Punkt standardmäßig für vier Sekunden. Samples, die in der Extrazeit ankommen, werden behalten. Die Sammlung für einen Punkt dauert nie länger als 5 Sekunden insgesamt, selbst wenn `samples_per_point` bis dahin nicht erreicht wurde. |
| `aspect_ratio` | Bildschirmform, über die die Punkte verteilt werden. `"auto"` nimmt den Monitor, auf dem die GUI läuft; `"32:9"` oder eine reine Zahl überschreibt das. |

### Wo die Punkte platziert werden

Bei 16:9 sitzen die Punkte bei 10 % und 90 % des Bildschirms. Auf einem breiteren Bildschirm treiben dieselben Anteile die äußeren Punkte im Winkel deutlich weiter auseinander, in den Bereich, in dem der Tracker die wenigsten Glints sieht und am unzuverlässigsten wird. Der horizontale Rand wächst daher mit dem Seitenverhältnis, gedeckelt beim Wert für 21:9 — 32:9 wird also wie 21:9 kalibriert, mit Punkten bei 19,5 % und 80,5 %. Die vertikale Platzierung ändert sich nie. `aspect_ratio` von Hand setzen, wenn der Monitor falsch erkannt wird, z. B. auf einem über mehrere Monitore gespannten Desktop.

### Kalibrierung zurücksetzen

```bash
# config.toml bearbeiten und beide Koeffizientenlisten leeren:
coeff_x = []
coeff_y = []
```

Leere Listen bedeuten "keine Korrektur" — der rohe Blickpunkt wird unverändert durchgereicht.

---

## 12. Profile

Ein Profil ist eine benannte Kopie der gesamten Konfiguration — Kalibrierung, Kurven, Ausgabe, Eingabequelle, alles in `config.toml`. Sie existieren, damit ein Setup für Star Citizen und ein anderes für den Desktop-Einsatz vorgehalten werden können, ohne von Hand etwas zu bearbeiten.

Sie liegen als einzelne Dateien:

```
~/.config/openstargazer/profiles/<name>.toml
```

Aus dem Profilmenü in der Kopfzeile des Einstellungsfensters:

| Aktion | Was sie tut |
|--------|--------------|
| **Aktuelle Einstellungen speichern** | Schreibt alles, wie es gerade steht, unter einem Namen. Ein bestehender Name wird überschrieben. |
| Einen Namen aus der Liste wählen | Lädt dieses Profil und macht es zur gültigen Konfiguration |
| **Profile verwalten** | Dasselbe, plus Umbenennen und Löschen |

Der Knopf in der Kopfzeile zeigt, welches Profil gerade gilt. Das ist eine gespeicherte Beschriftung (`[general] active_profile`) statt etwas Erschlossenes: ein aktiviertes Profil ist sonst nicht von einem zu unterscheiden, das nie genutzt wurde, weil das Aktivieren seinen Inhalt in `config.toml` kopiert.

Löschen fragt vorher — hinter einem Profil kann ein Kalibrierlauf stehen — und das Löschen des aktiven Profils entfernt die Beschriftung, statt sie auf eine Datei zeigen zu lassen, die nicht mehr existiert.

Profile sind auch über die IPC-Schnittstelle erreichbar (`list_profiles`, `activate_profile`).

---

## 13. Best Practices

### Physischer Aufbau

- Tracker **zentriert unter dem Monitor**, gerade ausgerichtet
- Gesichtsabstand: **60–80 cm** optimal
- Direktes Licht auf das Gerät vermeiden (IR-Störung)
- Starkes Sonnenlicht hinter dem Monitor kann das Tracking stören

### Konfiguration

- **Filtereinstellungen zuerst testen**, bevor Kurven angepasst werden
- Kurven immer mit `--mock` und `osg-config` testen, bevor mit echter Hardware getrackt wird
- Immer nur eine Achse anpassen, nicht alle auf einmal
- Vor größeren Änderungen die Konfiguration sichern:
  ```bash
  cp ~/.config/openstargazer/config.toml ~/.config/openstargazer/config.toml.bak
  ```

### Dienstverwaltung

- Den Daemon **nicht manuell** im Terminal starten, während der systemd-Dienst läuft — das erzeugt zwei Instanzen
- Nach Konfigurationsänderungen immer neu starten:
  ```bash
  systemctl --user restart openstargazer
  ```

---

## 14. Tipps & Tricks

### Achsen schnell deaktivieren

Achse auf `scale = 0.0` setzen statt komplexer Konfigurationsänderungen:
```toml
[axes.roll]
scale = 0.0   # Rollwinkel deaktiviert
```

### Rollwinkel umkehren

Manche bevorzugen einen invertierten Rollwinkel:
```toml
[axes.roll]
invert = true
```

### Mock-Modus für Setup-Tests

Ohne echten Tracker testen – zwei Optionen:

```bash
# Option 1: Daemon im Mock-Modus starten, GUI normal verbinden
osg-daemon --mock --verbose &
osg-config

# Option 2: GUI direkt im Mock-Modus starten (kein Daemon nötig)
osg-config --mock
```

### Stream-Engine-Pfad überschreiben

Liegt die `.so` an einem nicht standardmäßigen Ort:
```bash
export OSG_STREAM_ENGINE_PATH=/pfad/zu/libtobii_stream_engine.so
osg-daemon
```

---

## 15. Fehlerbehebung

### Problem: Daemon startet nicht – Stream Engine nicht gefunden

**Fehler:**
```
StreamEngineError: libtobii_stream_engine.so not found.
```

**Lösung:**
```bash
bash scripts/fetch-stream-engine.sh

# Oder manuell prüfen:
ls ~/.local/share/openstargazer/lib/libtobii_stream_engine.so
ls ~/.local/share/openstargazer/bin/tobiiusbservice
```

Ist die Bibliothek vorhanden und der Daemon loggt trotzdem `INSUFFICIENT_LICENSE` bei `gaze_data`/`head_pose`, ist das keine fehlende Datei — siehe den Lizenzhinweis unter `[device]` oben. Die meisten Einzelhandelsgeräte können dieses Backend gar nicht nutzen; stattdessen auf `et5_ttp_camera` wechseln.

---

### Problem: Kein Gerät gefunden

**Fehler:**
```
No Tobii devices found
```

**Schritte:**

1. USB-Verbindung prüfen:
   ```bash
   lsusb | grep 2104
   ```
   Muss einen Eintrag mit Vendor-ID `2104` zeigen.

2. udev-Regeln neu laden:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger --subsystem-match=usb
   ```

3. Gerät nach dem udev-Reload aus- und wieder einstecken.

4. Unter Debian/Ubuntu: Gruppenmitgliedschaft prüfen:
   ```bash
   groups | grep plugdev
   ```
   Fehlt sie: ab- und wieder anmelden.

5. Ist ein Prozess abgestürzt, während er das Gerät hielt, kann eine
   verwaiste usbfs-Reservierung zurückbleiben und allem anderen
   `Resource busy` melden. Das Gerät ausstecken und wieder einstecken,
   oder auf USB-Ebene zurücksetzen, um sie zu lösen.

---

### Problem: pip-Fehler (PEP 668)

**Fehler:**
```
error: externally-managed-environment
```

Der Installer behandelt das automatisch mit einem venv. Für die manuelle Installation:

```bash
python3 -m venv --system-site-packages ~/.local/share/openstargazer/venv
~/.local/share/openstargazer/venv/bin/pip install ".[gui,tray]"
```

---

### Problem: OpenTrack erhält keine Daten

**Checkliste:**
1. Daemon läuft? → `systemctl --user status openstargazer`
2. Port passt? → Port in `config.toml` vs. OpenTrack-UDP-Port
3. OpenTrack-Eingang auf `UDP over network` gestellt?
4. Firewall? → `sudo firewall-cmd --add-port=4242/udp --permanent` (Fedora)

---

### Problem: Tracker springt oder ruckelt

**Lösung: Filter anpassen** — ruhiger im Stillstand, auf Kosten von etwa 100 ms mehr Verzögerung:
```toml
[filter]
one_euro_min_cutoff = 1.0
one_euro_beta = 0.05
```

Oder die Totzone vergrößern:
```toml
gaze_deadzone_px = 50.0
```

---

### Problem: Hohe Latenz / Verzögerung

**Lösung: Filter reaktionsfreudiger machen**
```toml
[filter]
one_euro_min_cutoff = 3.0
one_euro_beta = 0.15
```

Über diese Werte hinaus ist der Filter nicht mehr das, was spürbar ist: ein Kamerabild dauert 30 ms, und OpenTrack plus das Spiel kommen mit eigener Verzögerung dazu.

Außerdem: den OpenTrack-Filter auf **keinen** stellen.

---

### Problem: Keine Kopfdrehung oder -neigung, nur Position und Rollwinkel

Das ist das voreingestellte `et5_native`-Backend, das sich korrekt
verhält, kein Fehler — der Blickdatenstrom trägt gar keine Kopfdrehung.
**Erweitertes Headtracking** einschalten (Setup-Wizard, oder der Schalter
auf der Karte Einstellungen) für beide Achsen aus der Kamera des Geräts,
oder `backend = "stream-engine"` verwenden, falls das eigene Gerät
zufällig eine Stream-Engine-Lizenz mitbringt (nur Pitch, kein Yaw, und
nur auf Geräten, die sie haben — siehe `[device]`).

---

### Problem: Star Citizen zeigt kein Headtracking

1. Reihenfolge prüfen: **erst Star Citizen starten, dann OpenTrack**
2. In Star Citizen: Einstellungen → COMMS, FOIP & HEAD TRACKING → TrackIR aktivieren
3. OpenTrack: Play-Knopf gedrückt?
4. Wine-Ausgang in OpenTrack: richtiger Runner und Prefix?

---

### Debug-Report erstellen

Bei einem schwer zu diagnostizierenden Problem sammelt das
Debug-Report-Skript alle relevanten Systeminformationen in einer Datei:

```bash
cd scripts
bash collect-debug-info.sh
```

Oder aus dem install.sh-Menü: **Option 6 – Debug-Report erstellen** wählen.

Das Skript erzeugt eine Datei unter:
```
~/openstargazer-debug-YYYYMMDD-HHMMSS.txt
```

**Was der Report enthält:**
- System: Betriebssystem/Distribution, Kernel-Version, Architektur, RAM, CPU
- Python: Version, pip-/venv-Status, `pip show openstargazer`
- Tracking-Backend: das in `config.toml` konfigurierte Backend, und ob
  `pyusb` von dem Python importierbar ist, das den Daemon tatsächlich
  ausführen würde (venv-bewusst)
- USB-Geräte: Tobii-Geräteerkennung via `lsusb`
- Service-Status: `openstargazer`-User-Service und die letzten 50 Journal-Zeilen
- Tobii-USB-Service: Status des Systemdiensts `tobiiusb` (nur relevant bei manuell nachgerüsteter Stream Engine)
- Installationspfade: Existenzprüfung aller wichtigen Dateien (Stream Engine, udev-Regeln, venv, Desktop-Eintrag)
- opentrack: Version und Inhalt des Konfigurationsverzeichnisses (nur Dateinamen)
- Konfigurationsdatei: `~/.config/openstargazer/config.toml` mit geschwärzten Home-Pfaden
- Installations-Log: letzte 100 Zeilen von `~/.local/share/openstargazer/install.log`
- udev-Regeln: Inhalt von `/etc/udev/rules.d/70-openstargazer.rules`

Die entstandene Datei einem [neuen GitHub-Issue](https://github.com/1psconstructor/openstargazer/issues/new) beilegen.

> **Datenschutzhinweis:** Das Skript schwärzt den Benutzernamen im
> gesamten Report — nicht nur im Konfigurationsabschnitt, sondern auch in
> der `systemctl status`-Ausgabe, dem Journal-Auszug, dem Installations-
> Log und der Liste der geprüften Pfade. Es werden keine Passwörter oder
> Tokens gesammelt.

---

## 16. FAQ

**F: Muss OpenTrack installiert sein, damit osg-daemon läuft?**
A: Nein. Der Daemon sendet UDP-Pakete unabhängig davon, ob OpenTrack läuft.

---

**F: Funktioniert der Tracker ohne Star Citizen?**
A: Ja. osg-daemon sendet Standard-OpenTrack-UDP. Jede Anwendung, die das OpenTrack-UDP-Protokoll versteht, kann die Daten empfangen.

---

**F: Wie hoch ist die Latenz?**
A: Der Tobii ET5 läuft mit 33–90 Hz (je nach Modus). Filter fügen je nach Einstellung 10–50 ms hinzu. End-to-End (Tracker → OpenTrack) typischerweise unter 30 ms.

---

**F: Kann ich mehrere Tobii-Geräte gleichzeitig nutzen?**
A: Aktuell verbindet sich der Daemon mit dem ersten gefundenen Gerät. `preferred_url` in der Konfiguration wählt ein bestimmtes Gerät aus.

---

**F: Wie aktualisiere ich openstargazer?**
```bash
cd ~/openstargazer
git pull
pip install --user ".[gui,tray]"   # oder venv-pip
systemctl --user restart openstargazer
```

---

**F: Funktioniert der Tracker unter Wayland?**
A: Der Daemon selbst läuft unabhängig von Wayland/X11 (USB-Gerät). Die GUI (`osg-config`) nutzt GTK4 und funktioniert auf beiden.

---

**F: Was macht der Mock-Modus genau?**
A: `--mock` erzeugt sinusförmige Testdaten mit ~90 Hz ohne echten Tracker. Yaw/Pitch/Roll/X/Y/Z schwingen mit unterschiedlichen Frequenzen. Nützlich für UI-Tests und OpenTrack-Verbindungstests.

---

**F: Kann ich openstargazer mit anderen Spielen als Star Citizen nutzen?**
A: Ja. Jedes Spiel, das TrackIR oder FreeTrack via Wine/Proton unterstützt, funktioniert. OpenTrack muss entsprechend konfiguriert werden.

---

**F: Bekomme ich von Anfang an alle sechs Achsen?**
A: Nein — eine Standardinstallation liefert Kopfposition, Rollwinkel und den Blickpunkt (vier Achsen). Drehung und Neigung brauchen eingeschaltetes **Erweitertes Headtracking** (die Kamera des ET5 plus das eigene Modell des Projekts), oder ein Gerät mit Stream-Engine-Lizenz. Siehe [Erweitertes Headtracking](#input) und den Hinweis zu bekannten Einschränkungen oben.

---

## 17. Lizenz

**GPL-3.0-or-later** — siehe die Datei `LICENSE`. Jede Quelldatei trägt
einen SPDX-Header (`# SPDX-License-Identifier: GPL-3.0-or-later`).

Bis einschließlich v0.2.2 stand dieses Projekt unter MIT, und diese
Releases bleiben MIT — eine einmal erteilte Lizenz lässt sich nicht
zurückziehen. Alles ab v0.3.0 ist GPL-3.0-or-later. In der Praxis: nutzen,
ändern, verkaufen — wird eine geänderte Version aber weitergegeben,
bekommt die empfangende Person den Quellcode unter denselben Bedingungen.

Die mitgelieferten Head-Pose-Gewichte
(`openstargazer/models/head-pose.onnx`) stehen unter derselben Lizenz,
von Grund auf auf `replicantface` trainiert (MIT-lizenzierte synthetische
Daten) — kein vortrainierter Checkpoint und keine nicht-kommerziellen
Trainingsdaten sind eingeflossen.

---

## 18. Linksammlung

### Projekt & Community

| Ressource | Link |
|----------|------|
| openstargazer auf GitHub | https://github.com/1psconstructor/openstargazer |
| Tobii Eye Tracker 5 (offiziell) | https://gaming.tobii.com/product/eye-tracker-5/ |
| OpenTrack | https://github.com/opentrack/opentrack |
| LUG-Helper (Star Citizen Linux) | https://github.com/starcitizen-lug/lug-helper |

### Treiber & Bibliotheken

| Ressource | Link |
|----------|------|
| Community Stream Engine Mirror | https://github.com/johngebbie/tobii_4C_for_linux/releases |
| Tobii Stream Engine (offiziell, SDK) | https://developer.tobii.com/product-integration/stream-engine/ |

### Dokumentation

| Thema | Link |
|-------|------|
| OpenTrack-UDP-Protokoll | https://github.com/opentrack/opentrack/wiki/UDP-over-network-protocol |
| One-Euro-Filter-Paper | https://gery.casiez.net/1euro/ |
| PyGObject (GTK4 Python) | https://pygobject.gnome.org/ |
| systemd-User-Services | https://wiki.archlinux.org/title/Systemd/User |

### Star Citizen Linux

| Ressource | Link |
|----------|------|
| Star Citizen unter Linux (Wiki) | https://starcitizen.tools/Star_Citizen_on_Linux |
| LUG-Community-Discord | https://discord.gg/starcitizen-linux |
| GE-Proton | https://github.com/GloriousEggroll/proton-ge-custom |

---

*Dieses Handbuch beschreibt openstargazer v0.5.0.*
