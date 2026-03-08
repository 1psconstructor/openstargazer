#!/usr/bin/env bash
# install.sh – Main installer for openstargazer
#
# Usage: ./install.sh [--no-gui] [--mock]
#
# What this does:
#   1. Check Python version and pip
#   2. Install system dependencies (optional, prompts user)
#   3. Fetch Tobii Stream Engine binaries
#   4. Install Python package (pip install -e .)
#   5. Install udev rules
#   6. Install systemd user service
#   7. Install desktop entry + icon
#   8. Run osg-setup wizard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}[install]${NC} $*"; }
warn()  { echo -e "${YELLOW}[install]${NC} $*"; }
error() { echo -e "${RED}[install]${NC} $*" >&2; }
header(){ echo -e "\n${BOLD}$*${NC}"; }

NO_GUI=false
MOCK=false
OSG_VENV=""          # set by install_python_package if a venv is used
PYTHON_CMD="python3" # updated to venv python when venv is used
for arg in "$@"; do
    case "$arg" in
        --no-gui) NO_GUI=true ;;
        --mock)   MOCK=true ;;
    esac
done

# ---------------------------------------------------------------------------
check_python() {
    header "Checking Python…"
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
    info "Python $version ✓"
}

# ---------------------------------------------------------------------------
install_system_deps() {
    header "System dependencies…"

    local OPENTRACK_PKGS=""

    if command -v pacman &>/dev/null; then
        PKG_MGR="pacman"
        # curl + tar: needed by fetch-stream-engine.sh (usually pre-installed, but be explicit)
        PKGS="python-gobject gtk4 libadwaita libayatana-appindicator libusb usbutils opentrack curl tar"
    elif command -v apt &>/dev/null; then
        PKG_MGR="apt"
        # python3-venv: needed for `python3 -m venv` on Debian/Ubuntu minimal installs
        # curl + tar: needed by fetch-stream-engine.sh
        PKGS="python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libusb-1.0-0 usbutils opentrack python3-venv curl tar"
    elif command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
        # opentrack is not in Fedora's official repos (available via RPM Fusion or Flatpak)
        # curl + tar: needed by fetch-stream-engine.sh
        PKGS="python3-gobject gtk4 libadwaita libusb usbutils curl tar"
        OPENTRACK_PKGS="opentrack"
    else
        warn "Unknown package manager – please install GTK4, libadwaita, libusb, usbutils, opentrack manually"
        return
    fi

    read -rp "  Install system packages via ${PKG_MGR}? [Y/n] " ans
    if [[ "${ans,,}" == "n" ]]; then
        warn "Skipping system package installation"
        return
    fi

    case "$PKG_MGR" in
        pacman) sudo pacman -S --needed --noconfirm $PKGS ;;
        apt)    sudo apt install -y $PKGS ;;
        dnf)    sudo dnf install -y $PKGS ;;
    esac
    info "System packages installed ✓"

    # opentrack on Fedora: try RPM Fusion, fall back to instructions
    if [[ -n "$OPENTRACK_PKGS" ]]; then
        install_opentrack_fedora
    fi
}

# ---------------------------------------------------------------------------
install_opentrack_fedora() {
    header "Installing opentrack…"

    # Check if opentrack is already installed
    if command -v opentrack &>/dev/null; then
        info "opentrack already installed ✓"
        return
    fi

    # Try installing directly (works if RPM Fusion is already enabled)
    if sudo dnf install -y opentrack &>/dev/null; then
        info "opentrack installed via dnf ✓"
        return
    fi

    warn "opentrack not found in enabled repositories."
    warn "opentrack is available via RPM Fusion or as a Flatpak."
    echo
    echo "  Option A – Enable RPM Fusion Free and install:"
    echo "    sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-\$(rpm -E %fedora).noarch.rpm"
    echo "    sudo dnf install -y opentrack"
    echo
    echo "  Option B – Install via Flatpak (Flathub):"
    echo "    flatpak install -y flathub io.github.opentrack.OpenTrack"
    echo
    warn "Continuing installation without opentrack – install it manually before using head tracking."
}

# ---------------------------------------------------------------------------
fetch_stream_engine() {
    header "Fetching Tobii Stream Engine…"
    bash "${SCRIPT_DIR}/fetch-stream-engine.sh"
}

# ---------------------------------------------------------------------------
install_python_package() {
    header "Installing openstargazer Python package…"
    cd "$PROJECT_DIR"

    # Try normal user install first
    if python3 -m pip install --user -e ".[tray]" 2>/dev/null; then
        info "Python package installed ✓"
        return
    fi

    # Fedora 43+ (Python 3.12+): pip refuses to install into the system env (PEP 668).
    # Fall back to a virtual environment in ~/.local/share/openstargazer/venv
    warn "pip rejected system install (PEP 668 – externally managed environment)."
    warn "Installing into a virtual environment at ~/.local/share/openstargazer/venv …"

    local venv_dir="${HOME}/.local/share/openstargazer/venv"
    python3 -m venv --system-site-packages "$venv_dir"
    "$venv_dir/bin/pip" install --quiet -e ".[tray]"

    # Symlink the entry-point scripts into ~/.local/bin so they are on PATH
    local bin_dir="${HOME}/.local/bin"
    mkdir -p "$bin_dir"
    for script in osg-daemon osg-config osg-setup; do
        if [[ -f "${venv_dir}/bin/${script}" ]]; then
            ln -sf "${venv_dir}/bin/${script}" "${bin_dir}/${script}"
        fi
    done

    # Remember the venv path so the service installer and wizard can use it
    OSG_VENV="$venv_dir"
    PYTHON_CMD="${venv_dir}/bin/python3"
    info "Python package installed in venv ✓"
}

# ---------------------------------------------------------------------------
install_udev_rules() {
    header "Installing udev rules…"
    local src="${PROJECT_DIR}/udev/70-openstargazer.rules"
    local dst="/etc/udev/rules.d/70-openstargazer.rules"

    if [[ ! -f "$src" ]]; then
        warn "udev rules not found: $src"
        return
    fi

    sudo cp "$src" "$dst"
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=usb
    info "udev rules installed: $dst ✓"

    # Add user to plugdev group if it exists on this system.
    # On Fedora, plugdev does not exist – TAG+="uaccess" in the udev rule handles access.
    if getent group plugdev &>/dev/null; then
        if ! groups | grep -q plugdev; then
            warn "Adding user to 'plugdev' group (requires logout to take effect)"
            sudo usermod -aG plugdev "$USER"
        fi
    else
        info "No 'plugdev' group on this system – udev TAG+=uaccess grants access ✓"
    fi
}

# ---------------------------------------------------------------------------
install_systemd_service() {
    header "Installing systemd user service…"

    local service_dir="${HOME}/.config/systemd/user"
    mkdir -p "$service_dir"

    local src="${PROJECT_DIR}/data/openstargazer.service"
    local dst="${service_dir}/openstargazer.service"

    cp "$src" "$dst"

    # If a venv was used, rewrite ExecStart to point at the venv binary
    if [[ -n "$OSG_VENV" && -f "${OSG_VENV}/bin/osg-daemon" ]]; then
        sed -i "s|ExecStart=.*|ExecStart=${OSG_VENV}/bin/osg-daemon|" "$dst"
        info "Service ExecStart updated to use venv binary ✓"
    fi

    systemctl --user daemon-reload
    systemctl --user enable openstargazer.service
    info "systemd service installed and enabled ✓"
    info "Start with: systemctl --user start openstargazer"
}

# ---------------------------------------------------------------------------
install_desktop_entry() {
    if [[ "$NO_GUI" == "true" ]]; then
        return
    fi

    header "Installing desktop entry…"

    local app_dir="${HOME}/.local/share/applications"
    local icon_dir="${HOME}/.local/share/icons/hicolor/scalable/apps"
    mkdir -p "$app_dir" "$icon_dir"

    cp "${PROJECT_DIR}/data/openstargazer.desktop" "${app_dir}/"
    cp "${PROJECT_DIR}/data/icons/openstargazer.svg" "${icon_dir}/"

    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$app_dir" 2>/dev/null || true
    fi
    info "Desktop entry installed ✓"
}

# ---------------------------------------------------------------------------
run_setup_wizard() {
    header "Running setup wizard…"
    echo
    "$PYTHON_CMD" -m openstargazer.setup.wizard
}

# ---------------------------------------------------------------------------
main() {
    echo -e "${BOLD}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║   openstargazer Installer                    ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"

    check_python
    install_system_deps
    fetch_stream_engine
    install_python_package
    install_udev_rules
    install_systemd_service
    install_desktop_entry
    run_setup_wizard

    echo
    info "Installation complete!"
    echo
    echo "  Start daemon : systemctl --user start openstargazer"
    echo "  Open GUI     : osg-config"
    echo "  Setup again  : osg-setup"
    echo
}

main "$@"
