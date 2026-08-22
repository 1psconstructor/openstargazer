#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
# install.sh – Main installer for openstargazer
#
# Usage: ./install.sh [--no-gui] [--mock] [--lang <code>]
#
# Without --lang, the script's own language follows OSG_LANG, then the
# system locale, then falls back to English -- same as every other part
# of the project. --lang overrides that for this run and is exported, so
# the Python side (the setup wizard this hands off to) inherits it too.
#
# Provides:
#   1) Fresh install
#   2) Repair (re-install missing components)
#   3) Full uninstall
#   4) Custom uninstall (choose components)
#   5) Exit
#   6) Create debug report
set -euo pipefail

# Piped into a shell there is no script directory: BASH_SOURCE is unset,
# which under `set -u` ends the script two lines in with a message about an
# unset variable. That says nothing about what actually went wrong, so the
# lookup is allowed to fail here and is answered properly below.
_osg_source="${BASH_SOURCE[0]:-}"
if [ -n "$_osg_source" ] && SCRIPT_DIR="$(cd "$(dirname "$_osg_source")" 2>/dev/null && pwd)"; then
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
else
    SCRIPT_DIR=""
    PROJECT_DIR=""
fi
unset _osg_source

if [ -z "$SCRIPT_DIR" ] || [ ! -f "${SCRIPT_DIR}/i18n.sh" ]; then
    cat >&2 <<EOF
install.sh needs the files next to it and cannot be piped into a shell.

For a one-line install use the bootstrap instead, which downloads a
release first and then runs this script from it:

    curl -fsSL https://raw.githubusercontent.com/1psconstructor/openstargazer/<tag>/scripts/bootstrap.sh \\
        | bash -s -- --ref <tag>

Or clone the repository and run ./scripts/install.sh from it.
EOF
    exit 1
fi

# A language forced with --lang has to be resolved before i18n_load
# below, which is why this scans for it separately instead of waiting
# for the general argument loop further down: everything from here on,
# including this script's own remaining output, is already translated.
# Exported so the Python side (run_setup_wizard, --profile-only) inherits
# the same choice instead of redetecting it from the system locale.
_osg_args=("$@")
for ((_osg_i = 0; _osg_i < ${#_osg_args[@]}; _osg_i++)); do
    case "${_osg_args[_osg_i]}" in
        --lang=*) OSG_LANG="${_osg_args[_osg_i]#*=}" ;;
        --lang)   OSG_LANG="${_osg_args[_osg_i + 1]:-}" ;;
    esac
done
unset _osg_args _osg_i
if [ -n "${OSG_LANG:-}" ] && [ ! -f "${PROJECT_DIR}/openstargazer/locales/${OSG_LANG}.lang" ]; then
    echo "install.sh: no translation for '${OSG_LANG}' -- falling back to English" >&2
    OSG_LANG="en"
fi
export OSG_LANG="${OSG_LANG:-}"

# Translations for the interactive parts. Diagnostics stay English on
# purpose so that bug reports remain readable.
# shellcheck source=./i18n.sh
source "${SCRIPT_DIR}/i18n.sh"
i18n_load "${PROJECT_DIR}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
CYAN='\033[0;36m'
NC='\033[0m'

# ===========================================================================
# Logging
# ===========================================================================

LOG_DIR="${HOME}/.local/share/openstargazer"
LOG_FILE="${LOG_DIR}/install.log"

_log_init() {
    mkdir -p "${LOG_DIR}"
}

_log_write() {
    local level="$1"
    shift
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    # uninstall_user_data() removes LOG_DIR and then logs having done so --
    # recreate it here rather than let that write abort the script under
    # set -e, which used to skip the summary at the end of a full uninstall.
    mkdir -p "${LOG_DIR}"
    printf '[%s] [%s] %s\n' "${ts}" "${level}" "$*" >> "${LOG_FILE}"
}

_log_run_header() {
    local action="${1:-unknown}"
    mkdir -p "${LOG_DIR}"
    {
        printf '\n'
        printf '================================================================================\n'
        printf 'openstargazer install.sh run\n'
        printf '  Date/Time   : %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        printf '  Distro      : %s\n' \
            "$(. /etc/os-release 2>/dev/null && printf '%s %s' "${NAME:-unknown}" "${VERSION_ID:-}" || printf 'unknown')"
        printf '  Kernel      : %s\n' "$(uname -r)"
        printf '  Arch        : %s\n' "$(uname -m)"
        printf '  Bash        : %s\n' "${BASH_VERSION}"
        printf '  User        : %s\n' "${USER:-$(id -un)}"
        printf '  Action      : %s\n' "${action}"
        printf '================================================================================\n'
    } >> "${LOG_FILE}"
}

info()  { echo -e "${GREEN}[openstargazer]${NC} $*"; _log_write "INFO" "$*"; }
warn()  { echo -e "${YELLOW}[openstargazer]${NC} $*"; _log_write "WARN" "$*"; }
error() { echo -e "${RED}[openstargazer]${NC} $*" >&2; _log_write "ERROR" "$*"; }
header(){ echo -e "\n${BOLD}$*${NC}"; }

NO_GUI=false
MOCK=false
OSG_VENV=""
PYTHON_CMD="python3"
# The tracking backend a fresh install always sets up: no proprietary
# binaries, and it is the only one that ever gets a choice or a prompt
# here. "stream-engine" still exists as a manual path -- fetch it
# yourself with fetch-stream-engine.sh and set backend = "stream-engine"
# in config.toml -- but on most retail ET5 units it cannot work at all:
# tobii_gaze_data_subscribe and tobii_head_pose_subscribe both need a
# Stream Engine licence that ships only with certain OEM/partner deals,
# not with a bare consumer device (INSUFFICIENT_LICENSE otherwise). That
# gap is why the native and camera sources exist. The installer neither
# offers this backend nor repairs an existing one; `do_repair` treats
# every install as native.
BACKEND="native"

# Track what was done for the summary
declare -a SUMMARY_OK=()
declare -a SUMMARY_SKIP=()
declare -a SUMMARY_FAIL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-gui) NO_GUI=true ;;
        --mock)   MOCK=true ;;
        # Already resolved into OSG_LANG above, before i18n_load; skip the
        # value token here too so it is not read as a stray argument.
        --lang)   shift ;;
        --lang=*) ;;
    esac
    shift
done

# ===========================================================================
# Privilege helper
# ===========================================================================

_can_sudo() {
    if command -v sudo &>/dev/null; then
        return 0
    fi
    return 1
}

_run_privileged() {
    # Run a command with elevated privileges.
    # Returns 1 if no sudo is available and we're not root.
    if [[ $EUID -eq 0 ]]; then
        "$@"
    elif _can_sudo; then
        sudo "$@"
    else
        error "Root privileges required, but sudo is not available."
        error "Run this step as root, or install sudo."
        return 1
    fi
}

# ===========================================================================
# Confirmation prompt
# ===========================================================================

_confirm() {
    local prompt="$1"
    local default="${2:-y}"
    local tag
    if [[ "$default" == "y" ]]; then
        tag="Y/n"
    else
        tag="y/N"
    fi
    read -rp "  ${prompt} [${tag}] " ans
    ans="${ans:-$default}"
    [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]
}

# ===========================================================================
# Detection helpers (check what is installed)
# ===========================================================================

_is_pip_installed() {
    python3 -m pip show openstargazer &>/dev/null 2>&1 || \
    (  [[ -d "${HOME}/.local/share/openstargazer/venv" ]] && \
       "${HOME}/.local/share/openstargazer/venv/bin/pip" show openstargazer &>/dev/null 2>&1 )
}

_is_systemd_service_installed() {
    [[ -f "${HOME}/.config/systemd/user/openstargazer.service" ]]
}

_is_udev_installed() {
    [[ -f "/etc/udev/rules.d/70-openstargazer.rules" ]]
}

_is_tobii_service_installed() {
    [[ -f "/etc/systemd/system/tobiiusb.service" ]] || \
    [[ -f "/usr/local/sbin/tobiiusbserviced" ]]
}

_is_tobii_libs_installed() {
    [[ -f "${HOME}/.local/share/openstargazer/lib/libtobii_stream_engine.so" ]]
}

_is_tobii_system_libs_installed() {
    [[ -d "/usr/local/lib/tobiiusb" ]]
}

_is_desktop_entry_installed() {
    # The old name still counts as installed, so a repair replaces it
    # instead of reporting nothing to do.
    [[ -f "${HOME}/.local/share/applications/org.openstargazer.config.desktop" ]] \
        || [[ -f "${HOME}/.local/share/applications/openstargazer.desktop" ]]
}

_is_venv_installed() {
    [[ -d "${HOME}/.local/share/openstargazer/venv" ]]
}

_has_user_data() {
    [[ -d "${HOME}/.config/openstargazer" ]] || \
    [[ -d "${HOME}/.local/share/openstargazer" ]]
}

_is_opentrack_installed() {
    command -v opentrack &>/dev/null || \
    flatpak list --app 2>/dev/null | grep -q "io.github.opentrack.OpenTrack"
}

_is_opentrack_profile_installed() {
    [[ -f "${HOME}/.config/opentrack/tobii5-starcitizen.ini" ]] || \
    [[ -f "${HOME}/.var/app/io.github.opentrack.OpenTrack/config/opentrack/tobii5-starcitizen.ini" ]]
}

# ===========================================================================
# INSTALL FUNCTIONS
# ===========================================================================

check_python() {
    header "Checking Python..."
    if ! command -v python3 &>/dev/null; then
        error "python3 not found. Please install Python 3.10+"
        exit 1
    fi
    local version
    version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    local major minor
    major="${version%%.*}"
    minor="${version##*.}"
    if [[ "$major" -lt 3 ]] || [[ "$major" -eq 3 && "$minor" -lt 10 ]]; then
        error "Python 3.10+ required (found $version)"
        exit 1
    fi
    info "Python $version OK"
}

# ---------------------------------------------------------------------------
install_system_deps() {
    header "System dependencies..."

    local OPENTRACK_PKGS=""

    if command -v pacman &>/dev/null; then
        PKG_MGR="pacman"
        PKGS="python-gobject gtk4 libadwaita libayatana-appindicator libusb usbutils opentrack curl tar"
    elif command -v apt &>/dev/null; then
        PKG_MGR="apt"
        PKGS="python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libusb-1.0-0 usbutils opentrack python3-venv curl tar"
    elif command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
        PKGS="python3-gobject gtk4 libadwaita libusb usbutils curl tar"
        OPENTRACK_PKGS="opentrack"
    else
        warn "Unknown package manager -- please install GTK4, libadwaita, libusb, usbutils, opentrack manually"
        SUMMARY_SKIP+=("System packages (unknown package manager)")
        return
    fi

    if ! _confirm "Install system packages via ${PKG_MGR}?"; then
        warn "Skipping system package installation"
        SUMMARY_SKIP+=("System packages")
        return
    fi

    case "$PKG_MGR" in
        pacman) _run_privileged pacman -S --needed --noconfirm $PKGS ;;
        apt)    _run_privileged apt install -y $PKGS ;;
        dnf)    _run_privileged dnf install -y $PKGS ;;
    esac
    SUMMARY_OK+=("System packages via ${PKG_MGR}")

    if [[ -n "$OPENTRACK_PKGS" ]]; then
        install_opentrack_fedora
    fi
}

# ---------------------------------------------------------------------------
install_opentrack_from_source() {
    # Installs to $HOME/.local rather than /usr/local: opentrack binds its
    # plugins via RUNPATH (not the system ld cache), so a privileged install
    # step and ldconfig were never actually needed - and a user-owned build
    # means the user can rebuild it themselves later (e.g. after a Fedora
    # library bump breaks it, see docs/opentrack-fedora.md) without sudo.
    local build_deps=(
        cmake git gcc-c++ ninja-build
        qt6-qtbase-devel qt6-qtbase-private-devel qt6-qttools-devel qt6-qtsvg-devel
        opencv-devel procps-ng-devel libevdev-devel
        wine-devel wine-devel.i686
    )

    info "Installing build dependencies..."
    _run_privileged dnf install -y "${build_deps[@]}"

    local src_dir=""
    src_dir="$(mktemp -d)"
    trap '[[ -n "${src_dir:-}" ]] && rm -rf -- "$src_dir"' RETURN

    info "Cloning opentrack from GitHub..."
    if ! git clone --branch opentrack-2026.1.0 --depth=1 https://github.com/opentrack/opentrack "$src_dir/opentrack"; then
        error "Failed to clone opentrack repository"
        SUMMARY_FAIL+=("opentrack (git clone failed)")
        return 1
    fi

    info "Building opentrack (SDK_WINE=ON)..."
    if ! cmake -S "$src_dir/opentrack" -B "$src_dir/build" -G Ninja \
            -DSDK_WINE=ON \
            -DOPENTRACK_WINE_ARCH=-m64 \
            -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_INSTALL_PREFIX="$HOME/.local"; then
        error "cmake configuration failed"
        SUMMARY_FAIL+=("opentrack (cmake failed)")
        return 1
    fi
    if ! cmake --build "$src_dir/build" -j"$(nproc)"; then
        error "Build failed"
        SUMMARY_FAIL+=("opentrack (build failed)")
        return 1
    fi
    if ! cmake --install "$src_dir/build"; then
        error "Installation failed"
        SUMMARY_FAIL+=("opentrack (install failed)")
        return 1
    fi

    info "opentrack installed from source into \$HOME/.local ✓"
    SUMMARY_OK+=("opentrack (GitHub source, SDK_WINE=ON)")
}

# ---------------------------------------------------------------------------
install_opentrack_fedora() {
    header "Installing opentrack..."

    # Already installed natively or as Flatpak?
    if command -v opentrack &>/dev/null; then
        info "opentrack already installed (native)"
        SUMMARY_OK+=("opentrack (already installed)")
        return
    fi
    if flatpak list --app 2>/dev/null | grep -q "io.github.opentrack.OpenTrack"; then
        info "opentrack already installed (Flatpak)"
        SUMMARY_OK+=("opentrack (Flatpak, already installed)")
        return
    fi

    # Try standard dnf repos first (works if RPM Fusion is already enabled)
    if _run_privileged dnf install -y opentrack 2>/dev/null; then
        info "opentrack installed via dnf"
        SUMMARY_OK+=("opentrack (dnf)")
        return
    fi

    # Not in repos - build from source. Neither RPM Fusion nor Flathub
    # actually carry opentrack (verified August 2026: RPM Fusion Free has no
    # such package, and io.github.opentrack.OpenTrack does not exist on
    # Flathub), and upstream itself ships Windows-only release binaries - so
    # building from source is the only real Linux option, not just the
    # recommended one. See docs/opentrack-fedora.md for details.
    warn "opentrack is not in the enabled dnf repositories."
    echo
    echo "  Choose an installation method:"
    echo "  1) Build from GitHub source (only real option on Linux, includes Wine output plugin)"
    echo "  2) Skip (install manually later)"
    echo
    read -rp "  Selection [1-2]: " ot_choice

    case "${ot_choice:-2}" in
        1)
            install_opentrack_from_source
            ;;
        *)
            warn "Skipping opentrack installation."
            warn "Install manually before using head tracking:"
            echo "    git clone --branch opentrack-2026.1.0 --depth=1 https://github.com/opentrack/opentrack"
            echo "    cmake -S opentrack -B build -G Ninja -DSDK_WINE=ON -DOPENTRACK_WINE_ARCH=-m64 \\"
            echo "          -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=\$HOME/.local"
            echo "    cmake --build build -j\$(nproc) && cmake --install build"
            SUMMARY_SKIP+=("opentrack (skipped, install manually)")
            ;;
    esac
}

# ---------------------------------------------------------------------------
apply_backend_setting() {
    # Writes the chosen backend into ~/.config/openstargazer/config.toml so
    # that an existing config from an earlier install does not silently keep
    # the old backend.
    if ! "$PYTHON_CMD" - "$BACKEND" <<'PY' 2>/dev/null
import sys
from openstargazer.config.settings import Settings

settings = Settings.load()
settings.device.backend = sys.argv[1]
settings.save()
print(settings.config_path)
PY
    then
        warn "Could not write the backend setting to config.toml"
        warn "Set it manually: backend = \"${BACKEND}\" under [device]"
        SUMMARY_FAIL+=("backend setting (config.toml)")
        return
    fi
    SUMMARY_OK+=("backend = ${BACKEND}")
}

# ---------------------------------------------------------------------------
check_native_prerequisites() {
    header "Checking native backend prerequisites..."

    if ! "$PYTHON_CMD" -c 'import usb.core' 2>/dev/null; then
        warn "pyusb is not importable -- the native backend cannot talk to the device"
        SUMMARY_FAIL+=("pyusb (native backend)")
        return
    fi
    info "pyusb OK"

    if ! command -v lsusb &>/dev/null; then
        warn "lsusb not available -- skipping device check (install usbutils)"
        SUMMARY_SKIP+=("ET5 device check (lsusb missing)")
        return
    fi

    if ! lsusb | grep -qi '2104:'; then
        warn "No Tobii device found on USB -- plug the ET5 in before starting the daemon"
        SUMMARY_SKIP+=("ET5 device check (no device connected)")
        return
    fi

    if "$PYTHON_CMD" - <<'PY' 2>/dev/null
import sys
import usb.core

dev = usb.core.find(idVendor=0x2104, idProduct=0x0313)
if dev is None:
    sys.exit(2)
try:
    dev.get_active_configuration()
except Exception:
    sys.exit(1)
PY
    then
        info "ET5 detected and accessible"
        SUMMARY_OK+=("ET5 device access")
    else
        warn "ET5 found but not accessible -- the udev rule needs a replug to take effect"
        warn "Unplug and replug the device, then run: ${SCRIPT_DIR}/collect-debug-info.sh"
        SUMMARY_SKIP+=("ET5 device access (replug required)")
    fi
}

# ---------------------------------------------------------------------------
install_python_package() {
    header "Installing openstargazer Python package..."
    cd "$PROJECT_DIR"

    # Not editable: an editable install keeps pointing at $PROJECT_DIR,
    # and bootstrap.sh's one-line install runs from a temp directory it
    # deletes the moment this script returns. A regular install copies
    # everything -- code, the shipped model weights, the locale files --
    # into site-packages, so the daemon survives its own source going away
    # (found live: the next restart after that raised ModuleNotFoundError).
    if python3 -m pip install --user ".[gui,tray,camera]" 2>/dev/null; then
        info "Python package installed"
        SUMMARY_OK+=("Python package (pip --user)")
        return
    fi

    warn "pip rejected system install (PEP 668)."
    warn "Installing into venv at ~/.local/share/openstargazer/venv ..."

    local venv_dir="${HOME}/.local/share/openstargazer/venv"
    python3 -m venv --system-site-packages "$venv_dir"
    "$venv_dir/bin/pip" install --quiet ".[gui,tray,camera]"

    local bin_dir="${HOME}/.local/bin"
    mkdir -p "$bin_dir"
    for script in osg-daemon osg-config osg-setup; do
        if [[ -f "${venv_dir}/bin/${script}" ]]; then
            ln -sf "${venv_dir}/bin/${script}" "${bin_dir}/${script}"
        fi
    done

    OSG_VENV="$venv_dir"
    PYTHON_CMD="${venv_dir}/bin/python3"
    SUMMARY_OK+=("Python package (venv)")
}

# ---------------------------------------------------------------------------
install_udev_rules() {
    header "Installing udev rules..."
    local src="${PROJECT_DIR}/udev/70-openstargazer.rules"
    local dst="/etc/udev/rules.d/70-openstargazer.rules"

    if [[ ! -f "$src" ]]; then
        warn "udev rules not found: $src"
        SUMMARY_FAIL+=("udev rules (source file missing)")
        return
    fi

    if ! _run_privileged cp "$src" "$dst"; then
        SUMMARY_FAIL+=("udev rules (sudo failed)")
        return
    fi
    _run_privileged udevadm control --reload-rules || true
    _run_privileged udevadm trigger --subsystem-match=usb || true
    SUMMARY_OK+=("udev rules")

    if getent group plugdev &>/dev/null; then
        if ! groups | grep -q plugdev; then
            warn "Adding user to 'plugdev' group (requires logout to take effect)"
            _run_privileged usermod -aG plugdev "$USER" || true
        fi
    fi
}

# ---------------------------------------------------------------------------
install_systemd_service() {
    header "Installing systemd user service..."

    local service_dir="${HOME}/.config/systemd/user"
    mkdir -p "$service_dir"

    local src="${PROJECT_DIR}/data/openstargazer.service"
    local dst="${service_dir}/openstargazer.service"

    if [[ ! -f "$src" ]]; then
        warn "Service file not found: $src"
        SUMMARY_FAIL+=("systemd service (source file missing)")
        return
    fi

    cp "$src" "$dst"

    # The unit has to name the daemon by absolute path. A venv install is not
    # on PATH, and a unit that looks it up there fails with exit code 127 on
    # every start -- silently, three seconds apart, for the whole session.
    local daemon_bin=""
    if [[ -n "$OSG_VENV" && -x "${OSG_VENV}/bin/osg-daemon" ]]; then
        daemon_bin="${OSG_VENV}/bin/osg-daemon"
    else
        daemon_bin="$(command -v osg-daemon 2>/dev/null || true)"
    fi

    if [[ -z "$daemon_bin" ]]; then
        rm -f "$dst"
        warn "No osg-daemon found — service not installed (a unit that cannot start is worse than none)"
        SUMMARY_FAIL+=("systemd service (osg-daemon not found)")
        return
    fi

    sed -i "s|^ExecStart=.*|ExecStart=${daemon_bin}|" "$dst"
    info "Service will start: ${daemon_bin}"

    systemctl --user daemon-reload
    systemctl --user enable openstargazer.service
    SUMMARY_OK+=("systemd user service")
}

# ---------------------------------------------------------------------------
configure_opentrack_profile() {
    header "Configuring OpenTrack for Star Citizen..."

    if ! _is_opentrack_installed; then
        warn "opentrack is not installed -- skipping profile generation"
        SUMMARY_SKIP+=("OpenTrack profile (opentrack not installed)")
        return
    fi

    # Whichever path the user just chose in run_setup_wizard may already
    # have written a real profile with the Wine paths they actually have --
    # nothing below may overwrite that with an auto-detected or minimal one.
    if _is_opentrack_profile_installed; then
        SUMMARY_OK+=("OpenTrack Star Citizen profile")
        return
    fi

    # Determine config dir (native vs Flatpak)
    local ot_config_dir="${HOME}/.config/opentrack"
    if flatpak list --app 2>/dev/null | grep -q "io.github.opentrack.OpenTrack"; then
        local flatpak_cfg="${HOME}/.var/app/io.github.opentrack.OpenTrack/config/opentrack"
        if [[ -d "$flatpak_cfg" ]] || ! [[ -d "$ot_config_dir" ]]; then
            ot_config_dir="$flatpak_cfg"
            info "Using Flatpak OpenTrack config dir: $ot_config_dir"
        fi
    fi

    mkdir -p "$ot_config_dir"

    # Try LUG-Helper auto-detection alone -- not the whole wizard, which
    # would ask its own questions again and mark setup complete before the
    # user has seen the guided dialog they may still be about to open.
    if _is_pip_installed; then
        info "Trying to auto-detect a Star Citizen / LUG-Helper install..."
        "$PYTHON_CMD" -m openstargazer.setup.wizard --profile-only 2>/dev/null || true
        if _is_opentrack_profile_installed; then
            SUMMARY_OK+=("OpenTrack Star Citizen profile")
            return
        fi
    fi

    # Fallback: write a minimal working profile directly
    local profile_file="${ot_config_dir}/tobii5-starcitizen.ini"
    info "Writing minimal OpenTrack profile to $profile_file"
    cat > "$profile_file" <<'EOF'
[General]
profile-name=tobii5-starcitizen
version=2026

[tracker]
dll=opentrack-input-udp
name=UDP over network

[filter]
dll=
name=(no filter)

[output]
dll=opentrack-output-wine
name=Wine

[tracker-dll-config]
port=4242

[output-dll-config]
protocol=1
EOF

    # Set as default profile
    local ot_ini="${ot_config_dir}/opentrack.ini"
    if [[ -f "$ot_ini" ]]; then
        # Update existing entry
        if grep -q "^profile=" "$ot_ini"; then
            sed -i "s|^profile=.*|profile=tobii5-starcitizen.ini|" "$ot_ini"
        else
            echo "profile=tobii5-starcitizen.ini" >> "$ot_ini"
        fi
    else
        printf '[General]\nprofile=tobii5-starcitizen.ini\n' > "$ot_ini"
    fi

    info "Profile installed. Wine prefix and runner must be set in OpenTrack → Output → Wine."
    warn "Run 'osg-setup' after installing the Python package to auto-configure Wine paths."
    SUMMARY_OK+=("OpenTrack profile (minimal – run osg-setup to set Wine paths)")
}

# ---------------------------------------------------------------------------
install_desktop_entry() {
    if [[ "$NO_GUI" == "true" ]]; then
        return
    fi

    header "Installing desktop entry..."

    local app_dir="${HOME}/.local/share/applications"
    local icon_dir="${HOME}/.local/share/icons/hicolor/scalable/apps"
    # The tray looks its icon up by name in the theme, so a symbolic variant
    # has to be there as well -- panels ask for <name>-symbolic first and
    # fall back to the full-colour tile only if it is missing.
    local symbolic_dir="${HOME}/.local/share/icons/hicolor/symbolic/apps"
    local autostart_dir="${HOME}/.config/autostart"
    mkdir -p "$app_dir" "$icon_dir" "$symbolic_dir" "$autostart_dir"

    # Named after the application id: a Wayland compositor looks a window's
    # app_id up as <app_id>.desktop, so any other name leaves the window
    # without its icon.
    if [[ -f "${PROJECT_DIR}/data/org.openstargazer.config.desktop" ]]; then
        cp "${PROJECT_DIR}/data/org.openstargazer.config.desktop" "${app_dir}/"
        # Installations before that rename left a file the compositor never
        # matched; it would otherwise show up twice in the menu.
        rm -f "${app_dir}/openstargazer.desktop"
    fi
    if [[ -f "${PROJECT_DIR}/data/icons/openstargazer.svg" ]]; then
        cp "${PROJECT_DIR}/data/icons/openstargazer.svg" "${icon_dir}/"
    fi
    if [[ -f "${PROJECT_DIR}/data/icons/openstargazer-symbolic.svg" ]]; then
        cp "${PROJECT_DIR}/data/icons/openstargazer-symbolic.svg" "${symbolic_dir}/"
    fi
    # The card icons of the settings overview. osg-config also adds
    # data/icons/ as a search path so a run straight out of a checkout finds
    # them, but a themed icon wins over an unthemed one -- so an installed
    # copy left over from an earlier version would be preferred over the
    # current file. Copying them here keeps the installed set current
    # instead.
    for card in "${PROJECT_DIR}"/data/icons/osg-*.svg; do
        [[ -f "$card" ]] && cp "$card" "${icon_dir}/"
    done

    # The status icon starts with the session, the way a tray program is
    # expected to. Exec is rewritten to the installed binary for the same
    # reason the service unit is: a venv is not on PATH.
    if [[ -f "${PROJECT_DIR}/data/openstargazer-tray.desktop" ]]; then
        cp "${PROJECT_DIR}/data/openstargazer-tray.desktop" "${autostart_dir}/"
        if [[ -n "$OSG_VENV" && -x "${OSG_VENV}/bin/osg-tray" ]]; then
            sed -i "s|^Exec=.*|Exec=${OSG_VENV}/bin/osg-tray|" \
                "${autostart_dir}/openstargazer-tray.desktop"
        fi
    fi

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$app_dir" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
    fi
    SUMMARY_OK+=("Desktop entry + icons + tray autostart")
}

# ---------------------------------------------------------------------------
run_setup_wizard() {
    header "Running setup wizard..."
    echo
    # Not fatal: this now runs before the system-level steps below it, and
    # a problem in the user's chosen setup path -- closing the chooser
    # window, Ctrl-C in the terminal wizard -- must not skip installing
    # the service, the udev rule and the desktop entry that follow it.
    "$PYTHON_CMD" -m openstargazer.setup.wizard || true
}

# ===========================================================================
# UNINSTALL FUNCTIONS
# ===========================================================================

uninstall_systemd_service() {
    header "Removing systemd user service..."
    local service_file="${HOME}/.config/systemd/user/openstargazer.service"

    if ! _is_systemd_service_installed; then
        info "systemd user service not installed -- skipping"
        SUMMARY_SKIP+=("systemd user service (not installed)")
        return
    fi

    # Stop if running
    systemctl --user stop openstargazer.service 2>/dev/null || true
    systemctl --user disable openstargazer.service 2>/dev/null || true
    rm -f "$service_file"
    systemctl --user daemon-reload 2>/dev/null || true
    SUMMARY_OK+=("systemd user service removed")
}

# ---------------------------------------------------------------------------
uninstall_udev_rules() {
    header "Removing udev rules..."
    local rules_file="/etc/udev/rules.d/70-openstargazer.rules"

    if ! _is_udev_installed; then
        info "udev rules not installed -- skipping"
        SUMMARY_SKIP+=("udev rules (not installed)")
        return
    fi

    if _run_privileged rm -f "$rules_file"; then
        _run_privileged udevadm control --reload-rules 2>/dev/null || true
        _run_privileged udevadm trigger --subsystem-match=usb 2>/dev/null || true
        SUMMARY_OK+=("udev rules removed")
    else
        SUMMARY_FAIL+=("udev rules (sudo failed)")
    fi
}

# ---------------------------------------------------------------------------
uninstall_tobii_binaries() {
    header "Removing Tobii binaries..."

    # Found vs. removed are tracked separately: a privileged removal can
    # fail for a file that is genuinely there, and "not found -- skipping"
    # would misreport that as nothing to do instead of as a failure.
    local found=false
    local removed=false

    # User-local stream engine library
    local user_lib="${HOME}/.local/share/openstargazer/lib/libtobii_stream_engine.so"
    if [[ -f "$user_lib" ]]; then
        found=true
        rm -f "$user_lib"
        info "Removed: $user_lib"
        removed=true
    fi

    # System-wide tobiiusbserviced
    if [[ -f "/usr/local/sbin/tobiiusbserviced" ]]; then
        found=true
        if _run_privileged rm -f "/usr/local/sbin/tobiiusbserviced"; then
            info "Removed: /usr/local/sbin/tobiiusbserviced"
            removed=true
        fi
    fi

    # System-wide tobii USB libraries
    if [[ -d "/usr/local/lib/tobiiusb" ]]; then
        found=true
        if _run_privileged rm -rf "/usr/local/lib/tobiiusb"; then
            info "Removed: /usr/local/lib/tobiiusb/"
            removed=true
        fi
    fi

    if [[ "$found" == "false" ]]; then
        info "Tobii binaries not found -- skipping"
        SUMMARY_SKIP+=("Tobii binaries (not installed)")
    elif [[ "$removed" == "false" ]]; then
        SUMMARY_FAIL+=("Tobii binaries (sudo failed)")
    else
        SUMMARY_OK+=("Tobii binaries removed")
    fi
}

# ---------------------------------------------------------------------------
uninstall_tobii_service() {
    header "Removing Tobii USB service..."

    if ! _is_tobii_service_installed; then
        info "Tobii USB service not installed -- skipping"
        SUMMARY_SKIP+=("tobiiusb.service (not installed)")
        return
    fi

    _run_privileged systemctl stop tobiiusb.service 2>/dev/null || true
    _run_privileged systemctl disable tobiiusb.service 2>/dev/null || true

    if [[ -f "/etc/systemd/system/tobiiusb.service" ]]; then
        _run_privileged rm -f "/etc/systemd/system/tobiiusb.service"
    fi
    _run_privileged systemctl daemon-reload 2>/dev/null || true
    SUMMARY_OK+=("tobiiusb.service removed")
}

# ---------------------------------------------------------------------------
uninstall_python_package() {
    header "Removing Python package..."

    local removed=false

    # Try pip uninstall (user install)
    if python3 -m pip show openstargazer &>/dev/null 2>&1; then
        python3 -m pip uninstall -y openstargazer 2>/dev/null || true
        info "pip uninstall openstargazer done"
        removed=true
    fi

    # Venv install
    local venv_dir="${HOME}/.local/share/openstargazer/venv"
    if [[ -d "$venv_dir" ]]; then
        rm -rf "$venv_dir"
        info "Removed venv: $venv_dir"
        removed=true
    fi

    # Remove symlinks from ~/.local/bin
    local bin_dir="${HOME}/.local/bin"
    for script in osg-daemon osg-config osg-setup; do
        if [[ -L "${bin_dir}/${script}" ]]; then
            rm -f "${bin_dir}/${script}"
        fi
    done

    if [[ "$removed" == "false" ]]; then
        info "Python package not installed -- skipping"
        SUMMARY_SKIP+=("Python package (not installed)")
    else
        SUMMARY_OK+=("Python package removed")
    fi
}

# ---------------------------------------------------------------------------
uninstall_desktop_entry() {
    header "Removing desktop entry..."

    # The autostart file below only stops a *future* login from starting
    # the tray; an instance already running (this login's autostart, or a
    # manual launch) survives its removal and keeps sitting in the panel.
    if pgrep -f 'bin/osg-tray' &>/dev/null; then
        pkill -f 'bin/osg-tray' 2>/dev/null || true
        info "Stopped a running osg-tray"
    fi

    local desktop_file="${HOME}/.local/share/applications/org.openstargazer.config.desktop"
    local legacy_desktop="${HOME}/.local/share/applications/openstargazer.desktop"
    local autostart_file="${HOME}/.config/autostart/openstargazer-tray.desktop"
    local icon_file="${HOME}/.local/share/icons/hicolor/scalable/apps/openstargazer.svg"
    local card_glob="${HOME}/.local/share/icons/hicolor/scalable/apps/osg-*.svg"
    local symbolic_file="${HOME}/.local/share/icons/hicolor/symbolic/apps/openstargazer-symbolic.svg"

    if [[ -f "$desktop_file" ]] || [[ -f "$legacy_desktop" ]] || [[ -f "$icon_file" ]] \
       || [[ -f "$symbolic_file" ]] || [[ -f "$autostart_file" ]]; then
        rm -f "$desktop_file" "$legacy_desktop" "$icon_file" "$symbolic_file" "$autostart_file"
        # shellcheck disable=SC2086  # deliberate glob
        rm -f $card_glob
        if command -v update-desktop-database &>/dev/null; then
            update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
        fi
        # install_desktop_entry rebuilds this on the way in; leaving it
        # stale on the way out means gtk-icon-theme.cache keeps claiming
        # icons exist at paths that no longer do, which the *next* fresh
        # install's language chooser then trips over before it has
        # reinstalled anything -- "Failed to load icon ...: file or
        # directory not found" for an icon that really was there once.
        if command -v gtk-update-icon-cache &>/dev/null; then
            gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
        fi
        SUMMARY_OK+=("Desktop entry, icons and tray autostart removed")
    else
        info "Desktop entry not installed -- skipping"
        SUMMARY_SKIP+=("Desktop entry (not installed)")
    fi
}

# ---------------------------------------------------------------------------
uninstall_user_data() {
    header "Removing user data..."

    local config_dir="${HOME}/.config/openstargazer"
    local data_dir="${HOME}/.local/share/openstargazer"

    local found=false
    [[ -d "$config_dir" ]] && found=true
    [[ -d "$data_dir" ]] && found=true

    if [[ "$found" == "false" ]]; then
        info "No user data found -- skipping"
        SUMMARY_SKIP+=("User data (not found)")
        return
    fi

    echo -e "  ${YELLOW}WARNING: This will delete your configuration, profiles, and calibration data!${NC}"
    echo "    $config_dir"
    echo "    $data_dir"

    if ! _confirm "Delete user data? This cannot be undone." "n"; then
        SUMMARY_SKIP+=("User data (user declined)")
        return
    fi

    [[ -d "$config_dir" ]] && rm -rf "$config_dir" && info "Removed: $config_dir"
    [[ -d "$data_dir" ]]   && rm -rf "$data_dir"   && info "Removed: $data_dir"
    SUMMARY_OK+=("User data removed")
}

# ===========================================================================
# REPAIR
# ===========================================================================

_resolve_python() {
    # A previous install may have fallen back to a venv (PEP 668). Repair
    # and the prerequisite checks have to use that interpreter, otherwise
    # they test a Python that does not have openstargazer installed.
    local venv_dir="${HOME}/.local/share/openstargazer/venv"
    if [[ -x "${venv_dir}/bin/python3" ]]; then
        OSG_VENV="$venv_dir"
        PYTHON_CMD="${venv_dir}/bin/python3"
    fi
}

do_repair() {
    header "Repair -- checking installed components..."
    echo

    check_python
    _resolve_python

    if ! _is_pip_installed; then
        warn "Python package not found -- reinstalling"
        install_python_package
    else
        info "Python package OK"
    fi

    if ! _is_udev_installed; then
        warn "udev rules missing -- reinstalling"
        install_udev_rules
    else
        info "udev rules OK"
    fi

    check_native_prerequisites

    if ! _is_systemd_service_installed; then
        warn "systemd user service missing -- reinstalling"
        install_systemd_service
    else
        info "systemd user service OK"
    fi

    if [[ "$NO_GUI" != "true" ]] && ! _is_desktop_entry_installed; then
        warn "Desktop entry missing -- reinstalling"
        install_desktop_entry
    else
        info "Desktop entry OK"
    fi

    if ! _is_opentrack_installed; then
        warn "opentrack not installed"
        if command -v dnf &>/dev/null; then
            install_opentrack_fedora
        else
            warn "Install opentrack via your package manager before using head tracking"
            SUMMARY_SKIP+=("opentrack (not installed)")
        fi
    else
        info "opentrack OK"
        if ! _is_opentrack_profile_installed; then
            warn "OpenTrack Star Citizen profile missing -- regenerating"
            configure_opentrack_profile
        else
            info "OpenTrack Star Citizen profile OK"
        fi
    fi

    print_summary
}

# ===========================================================================
# FULL UNINSTALL
# ===========================================================================

do_full_uninstall() {
    echo
    echo -e "  ${RED}${BOLD}$(t uninstall.full.title)${NC}"
    echo "  $(t uninstall.full.warning)"
    echo

    if ! _confirm "$(t uninstall.full.confirm)" "n"; then
        info "$(t common.cancelled)"
        return
    fi

    uninstall_systemd_service
    uninstall_udev_rules
    uninstall_tobii_service
    uninstall_tobii_binaries
    uninstall_python_package
    uninstall_desktop_entry
    uninstall_user_data

    print_summary
}

# ===========================================================================
# CUSTOM UNINSTALL
# ===========================================================================

do_custom_uninstall() {
    echo
    echo -e "  ${BOLD}$(t uninstall.custom.title)${NC}"
    echo

    # Build component list with install status
    local -a components=(
        "systemd user service (openstargazer.service)"
        "udev rules (70-openstargazer.rules)"
        "Tobii USB service (tobiiusb.service)"
        "Tobii binaries (libtobii_stream_engine.so, tobiiusbserviced)"
        "Python package (openstargazer)"
        "Desktop entry + icon"
        "User data (~/.config/openstargazer, ~/.local/share/openstargazer)"
    )

    local st_installed st_missing st_exists
    st_installed="$(t uninstall.status.installed)"
    st_missing="$(t uninstall.status.not_found)"
    st_exists="$(t uninstall.status.exists)"

    local -a status=()
    _is_systemd_service_installed   && status+=("$st_installed") || status+=("$st_missing")
    _is_udev_installed              && status+=("$st_installed") || status+=("$st_missing")
    _is_tobii_service_installed     && status+=("$st_installed") || status+=("$st_missing")
    ( _is_tobii_libs_installed || _is_tobii_system_libs_installed ) && status+=("$st_installed") || status+=("$st_missing")
    _is_pip_installed               && status+=("$st_installed") || status+=("$st_missing")
    _is_desktop_entry_installed     && status+=("$st_installed") || status+=("$st_missing")
    _has_user_data                  && status+=("$st_exists")    || status+=("$st_missing")

    for i in "${!components[@]}"; do
        local idx=$((i + 1))
        local st="${status[$i]}"
        local color="$GREEN"
        [[ "$st" == "$st_missing" ]] && color="$YELLOW"
        echo -e "  ${idx}) ${components[$i]}  ${color}[${st}]${NC}"
    done

    echo
    echo "  $(t uninstall.custom.hint)"
    echo "  $(t uninstall.custom.example)"
    read -rp "  $(t uninstall.custom.selection) " selection

    if [[ "$selection" == "q" || -z "$selection" ]]; then
        info "$(t common.cancelled)"
        return
    fi

    # Parse selection
    local -a selected=()
    IFS=', ' read -ra tokens <<< "$selection"
    for token in "${tokens[@]}"; do
        if [[ "$token" =~ ^[1-7]$ ]]; then
            selected+=("$token")
        else
            warn "$(t uninstall.custom.invalid token="$token")"
        fi
    done

    if [[ ${#selected[@]} -eq 0 ]]; then
        info "$(t uninstall.custom.nothing)"
        return
    fi

    echo
    echo "  $(t uninstall.custom.to_remove)"
    for s in "${selected[@]}"; do
        echo "    - ${components[$((s - 1))]}"
    done

    if ! _confirm "$(t uninstall.custom.proceed)" "n"; then
        info "$(t common.cancelled)"
        return
    fi

    for s in "${selected[@]}"; do
        case "$s" in
            1) uninstall_systemd_service ;;
            2) uninstall_udev_rules ;;
            3) uninstall_tobii_service ;;
            4) uninstall_tobii_binaries ;;
            5) uninstall_python_package ;;
            6) uninstall_desktop_entry ;;
            7) uninstall_user_data ;;
        esac
    done

    print_summary
}

# ===========================================================================
# FRESH INSTALL
# ===========================================================================

do_fresh_install() {
    check_python
    install_system_deps       # installs opentrack for Arch/apt; triggers install_opentrack_fedora for Fedora
    install_python_package
    apply_backend_setting

    # Language + graphical/terminal, asked once, as early as it can be:
    # right after the package that this chooser and everything past it is
    # part of actually exists, and before any of the system-level steps
    # below that neither path needs to ask about. Everything from here on
    # is the user's chosen path, not install.sh's own prompts.
    run_setup_wizard          # osg-setup: chooses language + mode, then runs it

    # Terminal path already installed this itself (step_install_service,
    # its own [Y/n]); asking sudo/pkexec to do the same thing again meant
    # a second, entirely redundant authentication for a rule already in
    # place -- three password prompts in a row on top of the graphical
    # assistant's own attempt at its Step 8.
    if ! _is_udev_installed; then
        install_udev_rules
    else
        SUMMARY_OK+=("udev rules")
    fi
    check_native_prerequisites
    install_systemd_service
    systemctl --user start openstargazer.service 2>/dev/null && \
        info "$(t install.daemon_started)" || \
        warn "$(t install.daemon_start_failed)"
    install_desktop_entry
    configure_opentrack_profile   # safety net if the chosen path was skipped or left early

    print_summary

    echo
    echo "  $(t next.start_daemon) : systemctl --user start openstargazer"
    echo "  $(t next.open_gui) : osg-config"
    echo "  $(t next.setup_again) : osg-setup"
    echo
    echo "  $(t next.reboot)"
    echo
}

# ===========================================================================
# SUMMARY
# ===========================================================================

print_summary() {
    echo
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}  $(t summary.title)${NC}"
    echo -e "${BOLD}========================================${NC}"

    if [[ ${#SUMMARY_OK[@]} -gt 0 ]]; then
        echo -e "  ${GREEN}$(t summary.ok)${NC}"
        for item in "${SUMMARY_OK[@]}"; do
            echo -e "    ${GREEN}+${NC} $item"
        done
    fi

    if [[ ${#SUMMARY_SKIP[@]} -gt 0 ]]; then
        echo -e "  ${YELLOW}$(t summary.skipped)${NC}"
        for item in "${SUMMARY_SKIP[@]}"; do
            echo -e "    ${YELLOW}-${NC} $item"
        done
    fi

    if [[ ${#SUMMARY_FAIL[@]} -gt 0 ]]; then
        echo -e "  ${RED}$(t summary.failed)${NC}"
        for item in "${SUMMARY_FAIL[@]}"; do
            echo -e "    ${RED}x${NC} $item"
        done
    fi

    echo
    {
        printf '[%s] [INFO] --- Summary ---\n' "$(date '+%Y-%m-%d %H:%M:%S')"
        for item in "${SUMMARY_OK[@]+"${SUMMARY_OK[@]}"}"; do
            printf '[%s] [INFO]   OK:   %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${item}"
        done
        for item in "${SUMMARY_SKIP[@]+"${SUMMARY_SKIP[@]}"}"; do
            printf '[%s] [WARN]   SKIP: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${item}"
        done
        for item in "${SUMMARY_FAIL[@]+"${SUMMARY_FAIL[@]}"}"; do
            printf '[%s] [ERROR]  FAIL: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "${item}"
        done
    } >> "${LOG_FILE}"
}

# ===========================================================================
# MAIN MENU
# ===========================================================================

main() {
    _log_init

    echo -e "${BOLD}"
    echo "=========================================="
    echo "   $(t install.title)"
    echo "=========================================="
    echo -e "${NC}"
    echo "  1) $(t install.menu.fresh)"
    echo "  2) $(t install.menu.repair)"
    echo "  3) $(t install.menu.uninstall_full)"
    echo "  4) $(t install.menu.uninstall_custom)"
    echo "  5) $(t install.menu.quit)"
    echo "  6) $(t install.menu.debug)"
    echo

    # Without a terminal (piped input, CI) read fails on EOF; say so
    # instead of exiting silently through set -e.
    if ! read -rp "  $(t install.menu.prompt) " choice; then
        echo
        error "$(t install.invalid_choice choice="<no input>")"
        exit 1
    fi

    case "$choice" in
        1)
            _log_run_header "fresh install"
            do_fresh_install
            ;;
        2)
            _log_run_header "repair"
            do_repair
            ;;
        3)
            _log_run_header "full uninstall"
            do_full_uninstall
            ;;
        4)
            _log_run_header "custom uninstall"
            do_custom_uninstall
            ;;
        5)
            info "$(t install.quit)"
            exit 0
            ;;
        6)
            _log_run_header "debug report"
            bash "${SCRIPT_DIR}/collect-debug-info.sh"
            ;;
        *)
            error "$(t install.invalid_choice choice="$choice")"
            exit 1
            ;;
    esac
}

main "$@"
