#!/usr/bin/env bash
# install.sh – Main installer for openstargazer
#
# Usage: ./install.sh [--no-gui] [--mock]
#
# Provides:
#   1) Fresh install
#   2) Repair (re-install missing components)
#   3) Full uninstall
#   4) Custom uninstall (choose components)
#   5) Exit
#   6) Create debug report
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

# Track what was done for the summary
declare -a SUMMARY_OK=()
declare -a SUMMARY_SKIP=()
declare -a SUMMARY_FAIL=()

for arg in "$@"; do
    case "$arg" in
        --no-gui) NO_GUI=true ;;
        --mock)   MOCK=true ;;
    esac
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
        error "Root-Rechte benoetigt, aber sudo ist nicht verfuegbar."
        error "Fuehre diesen Schritt als root aus oder installiere sudo."
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
    [[ -f "${HOME}/.local/share/applications/openstargazer.desktop" ]]
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
    local build_deps=(
        cmake git
        qt6-qtbase-private-devel qt6-qttools-devel
        opencv-devel procps-ng-devel libevdev-devel
        wine-devel wine-devel.i686
    )

    info "Installing build dependencies..."
    _run_privileged dnf install -y "${build_deps[@]}"

    local src_dir=""
    src_dir="$(mktemp -d)"
    trap '[[ -n "${src_dir:-}" ]] && rm -rf -- "$src_dir"' RETURN

    info "Cloning opentrack from GitHub..."
    if ! git clone --depth=1 https://github.com/opentrack/opentrack "$src_dir/opentrack"; then
        error "Failed to clone opentrack repository"
        SUMMARY_FAIL+=("opentrack (git clone failed)")
        return 1
    fi

    info "Building opentrack (SDK_WINE=ON)..."
    mkdir -p "$src_dir/build"
    if ! cmake -S "$src_dir/opentrack" -B "$src_dir/build" \
            -DSDK_WINE=ON \
            -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_INSTALL_PREFIX=/usr/local; then
        error "cmake configuration failed"
        SUMMARY_FAIL+=("opentrack (cmake failed)")
        return 1
    fi
    if ! make -C "$src_dir/build" -j"$(nproc)"; then
        error "Build failed"
        SUMMARY_FAIL+=("opentrack (make failed)")
        return 1
    fi
    if ! _run_privileged make -C "$src_dir/build" install; then
        error "Installation failed"
        SUMMARY_FAIL+=("opentrack (make install failed)")
        return 1
    fi
    _run_privileged ldconfig

    info "opentrack installed from source ✓"
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

    # Not in repos – ask user which method to use
    warn "opentrack is not in the enabled dnf repositories."
    echo
    echo "  Choose an installation method:"
    echo "  1) Enable RPM Fusion Free and install via dnf"
    echo "  2) Install via Flatpak from Flathub"
    echo "  3) Build from GitHub source (recommended for Fedora 43, Wine/LUG support)"
    echo "  4) Skip (install manually later)"
    echo
    read -rp "  Selection [1-4]: " ot_choice

    case "${ot_choice:-4}" in
        1)
            info "Enabling RPM Fusion Free..."
            local fedora_ver
            fedora_ver="$(rpm -E %fedora)"
            local rpmfusion_url="https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-${fedora_ver}.noarch.rpm"
            if _run_privileged dnf install -y "$rpmfusion_url"; then
                info "RPM Fusion Free enabled"
                if _run_privileged dnf install -y opentrack; then
                    info "opentrack installed via RPM Fusion"
                    SUMMARY_OK+=("opentrack (RPM Fusion)")
                else
                    error "opentrack installation failed after enabling RPM Fusion"
                    SUMMARY_FAIL+=("opentrack (RPM Fusion install failed)")
                fi
            else
                error "Failed to enable RPM Fusion Free"
                SUMMARY_FAIL+=("opentrack (RPM Fusion enable failed)")
            fi
            ;;
        2)
            if ! command -v flatpak &>/dev/null; then
                warn "flatpak not installed -- installing it first..."
                _run_privileged dnf install -y flatpak
                _run_privileged flatpak remote-add --if-not-exists flathub \
                    https://dl.flathub.org/repo/flathub.flatpakrepo
            fi
            info "Installing opentrack via Flatpak..."
            if flatpak install -y flathub io.github.opentrack.OpenTrack; then
                info "opentrack installed as Flatpak"
                info "Note: Flatpak config dir is ~/.var/app/io.github.opentrack.OpenTrack/config/opentrack/"
                info "The OpenTrack profile will be written there automatically."
                SUMMARY_OK+=("opentrack (Flatpak)")
            else
                error "Flatpak install failed"
                SUMMARY_FAIL+=("opentrack (Flatpak install failed)")
            fi
            ;;
        3)
            install_opentrack_from_source
            ;;
        *)
            warn "Skipping opentrack installation."
            warn "Install manually before using head tracking:"
            echo "    sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-\$(rpm -E %fedora).noarch.rpm"
            echo "    sudo dnf install -y opentrack"
            echo "  or:"
            echo "    flatpak install flathub io.github.opentrack.OpenTrack"
            echo "  or (Fedora 43+, includes Wine output plugin):"
            echo "    git clone --depth=1 https://github.com/opentrack/opentrack"
            echo "    cmake -S opentrack -B build -DSDK_WINE=ON -DCMAKE_INSTALL_PREFIX=/usr/local"
            echo "    make -C build -j\$(nproc) && sudo make -C build install"
            SUMMARY_SKIP+=("opentrack (skipped, install manually)")
            ;;
    esac
}

# ---------------------------------------------------------------------------
fetch_stream_engine() {
    header "Fetching Tobii Stream Engine..."
    if ! bash "${SCRIPT_DIR}/fetch-stream-engine.sh"; then
        warn "Stream Engine could not be installed automatically."
        warn "Install it manually, then run: osg-setup"
        warn "See: https://github.com/johngebbie/tobii_4C_for_linux"
        SUMMARY_FAIL+=("Tobii Stream Engine")
        return 1
    fi
    SUMMARY_OK+=("Tobii Stream Engine")
}

# ---------------------------------------------------------------------------
install_python_package() {
    header "Installing openstargazer Python package..."
    cd "$PROJECT_DIR"

    if python3 -m pip install --user -e ".[gui,tray]" 2>/dev/null; then
        info "Python package installed"
        SUMMARY_OK+=("Python package (pip --user)")
        return
    fi

    warn "pip rejected system install (PEP 668)."
    warn "Installing into venv at ~/.local/share/openstargazer/venv ..."

    local venv_dir="${HOME}/.local/share/openstargazer/venv"
    python3 -m venv --system-site-packages "$venv_dir"
    "$venv_dir/bin/pip" install --quiet -e ".[gui,tray]"

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

    if [[ -n "$OSG_VENV" && -f "${OSG_VENV}/bin/osg-daemon" ]]; then
        sed -i "s|ExecStart=.*|ExecStart=${OSG_VENV}/bin/osg-daemon|" "$dst"
        info "Service ExecStart updated to use venv binary"
    fi

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

    # Generate profile via Python (wizard step 4) if package is installed
    if _is_pip_installed; then
        info "Running osg-setup to generate OpenTrack profile..."
        "$PYTHON_CMD" -m openstargazer.setup.wizard 2>/dev/null || true
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
    mkdir -p "$app_dir" "$icon_dir"

    if [[ -f "${PROJECT_DIR}/data/openstargazer.desktop" ]]; then
        cp "${PROJECT_DIR}/data/openstargazer.desktop" "${app_dir}/"
    fi
    if [[ -f "${PROJECT_DIR}/data/icons/openstargazer.svg" ]]; then
        cp "${PROJECT_DIR}/data/icons/openstargazer.svg" "${icon_dir}/"
    fi

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$app_dir" 2>/dev/null || true
    fi
    SUMMARY_OK+=("Desktop entry + icon")
}

# ---------------------------------------------------------------------------
run_setup_wizard() {
    header "Running setup wizard..."
    echo
    "$PYTHON_CMD" -m openstargazer.setup.wizard
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

    local removed=false

    # User-local stream engine library
    local user_lib="${HOME}/.local/share/openstargazer/lib/libtobii_stream_engine.so"
    if [[ -f "$user_lib" ]]; then
        rm -f "$user_lib"
        info "Removed: $user_lib"
        removed=true
    fi

    # System-wide tobiiusbserviced
    if [[ -f "/usr/local/sbin/tobiiusbserviced" ]]; then
        if _run_privileged rm -f "/usr/local/sbin/tobiiusbserviced"; then
            info "Removed: /usr/local/sbin/tobiiusbserviced"
            removed=true
        fi
    fi

    # System-wide tobii USB libraries
    if [[ -d "/usr/local/lib/tobiiusb" ]]; then
        if _run_privileged rm -rf "/usr/local/lib/tobiiusb"; then
            info "Removed: /usr/local/lib/tobiiusb/"
            removed=true
        fi
    fi

    if [[ "$removed" == "false" ]]; then
        info "Tobii binaries not found -- skipping"
        SUMMARY_SKIP+=("Tobii binaries (not installed)")
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

    local desktop_file="${HOME}/.local/share/applications/openstargazer.desktop"
    local icon_file="${HOME}/.local/share/icons/hicolor/scalable/apps/openstargazer.svg"

    if [[ -f "$desktop_file" ]] || [[ -f "$icon_file" ]]; then
        rm -f "$desktop_file" "$icon_file"
        if command -v update-desktop-database &>/dev/null; then
            update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
        fi
        SUMMARY_OK+=("Desktop entry + icon removed")
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

do_repair() {
    header "Repair -- checking installed components..."
    echo

    check_python

    if ! _is_pip_installed; then
        warn "Python package not found -- reinstalling"
        install_python_package
    else
        info "Python package OK"
    fi

    if ! _is_tobii_libs_installed; then
        warn "Tobii Stream Engine library missing -- reinstalling"
        fetch_stream_engine
    else
        info "Tobii Stream Engine library OK"
    fi

    if ! _is_udev_installed; then
        warn "udev rules missing -- reinstalling"
        install_udev_rules
    else
        info "udev rules OK"
    fi

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
    echo -e "  ${RED}${BOLD}FULL UNINSTALL${NC}"
    echo "  This will remove ALL openstargazer components from this system."
    echo

    if ! _confirm "Continue with full uninstall?" "n"; then
        info "Cancelled."
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
    echo -e "  ${BOLD}Custom Uninstall -- select components to remove:${NC}"
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

    local -a status=()
    _is_systemd_service_installed   && status+=("installed") || status+=("not found")
    _is_udev_installed              && status+=("installed") || status+=("not found")
    _is_tobii_service_installed     && status+=("installed") || status+=("not found")
    ( _is_tobii_libs_installed || _is_tobii_system_libs_installed ) && status+=("installed") || status+=("not found")
    _is_pip_installed               && status+=("installed") || status+=("not found")
    _is_desktop_entry_installed     && status+=("installed") || status+=("not found")
    _has_user_data                  && status+=("exists")    || status+=("not found")

    for i in "${!components[@]}"; do
        local idx=$((i + 1))
        local st="${status[$i]}"
        local color="$GREEN"
        [[ "$st" == "not found" ]] && color="$YELLOW"
        echo -e "  ${idx}) ${components[$i]}  ${color}[${st}]${NC}"
    done

    echo
    echo "  Enter component numbers to remove (comma/space separated), or 'q' to cancel."
    echo "  Example: 1,3,5"
    read -rp "  Selection: " selection

    if [[ "$selection" == "q" || -z "$selection" ]]; then
        info "Cancelled."
        return
    fi

    # Parse selection
    local -a selected=()
    IFS=', ' read -ra tokens <<< "$selection"
    for token in "${tokens[@]}"; do
        if [[ "$token" =~ ^[1-7]$ ]]; then
            selected+=("$token")
        else
            warn "Ignoring invalid selection: $token"
        fi
    done

    if [[ ${#selected[@]} -eq 0 ]]; then
        info "Nothing selected."
        return
    fi

    echo
    echo "  Components to remove:"
    for s in "${selected[@]}"; do
        echo "    - ${components[$((s - 1))]}"
    done

    if ! _confirm "Proceed?" "n"; then
        info "Cancelled."
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
    fetch_stream_engine
    install_python_package
    install_udev_rules
    install_systemd_service
    install_desktop_entry
    configure_opentrack_profile
    run_setup_wizard          # osg-setup: detects LUG, finalises OpenTrack Wine paths

    print_summary

    echo
    echo "  Start daemon : systemctl --user start openstargazer"
    echo "  Open GUI     : osg-config"
    echo "  Setup again  : osg-setup"
    echo
}

# ===========================================================================
# SUMMARY
# ===========================================================================

print_summary() {
    echo
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}  Summary${NC}"
    echo -e "${BOLD}========================================${NC}"

    if [[ ${#SUMMARY_OK[@]} -gt 0 ]]; then
        echo -e "  ${GREEN}OK:${NC}"
        for item in "${SUMMARY_OK[@]}"; do
            echo -e "    ${GREEN}+${NC} $item"
        done
    fi

    if [[ ${#SUMMARY_SKIP[@]} -gt 0 ]]; then
        echo -e "  ${YELLOW}Skipped:${NC}"
        for item in "${SUMMARY_SKIP[@]}"; do
            echo -e "    ${YELLOW}-${NC} $item"
        done
    fi

    if [[ ${#SUMMARY_FAIL[@]} -gt 0 ]]; then
        echo -e "  ${RED}Failed:${NC}"
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
    echo "   openstargazer Setup"
    echo "=========================================="
    echo -e "${NC}"
    echo "  1) Neuinstallation"
    echo "  2) Reparatur (fehlende Komponenten nachinstallieren)"
    echo "  3) Deinstallation -- vollstaendig"
    echo "  4) Deinstallation -- benutzerdefiniert"
    echo "  5) Beenden"
    echo "  6) Debug-Report erstellen"
    echo

    read -rp "  Auswahl [1-6]: " choice

    case "$choice" in
        1)
            _log_run_header "Neuinstallation (fresh install)"
            do_fresh_install
            ;;
        2)
            _log_run_header "Reparatur (repair)"
            do_repair
            ;;
        3)
            _log_run_header "Deinstallation vollstaendig (full uninstall)"
            do_full_uninstall
            ;;
        4)
            _log_run_header "Deinstallation benutzerdefiniert (custom uninstall)"
            do_custom_uninstall
            ;;
        5)
            info "Beendet."
            exit 0
            ;;
        6)
            _log_run_header "Debug-Report"
            bash "${SCRIPT_DIR}/collect-debug-info.sh"
            ;;
        *)
            error "Ungueltige Auswahl: $choice"
            exit 1
            ;;
    esac
}

main "$@"
