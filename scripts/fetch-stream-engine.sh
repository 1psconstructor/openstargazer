#!/usr/bin/env bash
# fetch-stream-engine.sh – Download Tobii Stream Engine binaries for Linux
#
# Sources files directly from the johngebbie/tobii_4C_for_linux repository.
# The Tobii Stream Engine .so is not open-source but has been distributed
# with community eye-tracking projects under permissive terms.
#
# libtobii_stream_engine.so → ~/.local/share/openstargazer/lib/
# tobiiusbserviced          → /usr/local/sbin/              (system, needs sudo)
# libtobii_*.so (3 libs)   → /usr/local/lib/tobiiusb/      (system, needs sudo)
# tobiiusb.service          → /etc/systemd/system/          (system, needs sudo)
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/openstargazer"
LIB_DIR="${INSTALL_DIR}/lib"

REPO_RAW="https://raw.githubusercontent.com/johngebbie/tobii_4C_for_linux/main"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[openstargazer]${NC} $*"; }
warn()  { echo -e "${YELLOW}[openstargazer]${NC} $*"; }
error() { echo -e "${RED}[openstargazer]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
check_deps() {
    for cmd in curl; do
        if ! command -v "$cmd" &>/dev/null; then
            error "Required tool not found: $cmd"
            exit 1
        fi
    done
}

# ---------------------------------------------------------------------------
detect_arch() {
    case "$(uname -m)" in
        x86_64)  echo "x64" ;;
        i*86)    echo "x86" ;;
        *)
            warn "Unknown architecture $(uname -m), defaulting to x64"
            echo "x64"
            ;;
    esac
}

# ---------------------------------------------------------------------------
fetch_file() {
    local url="$1"
    local dest="$2"
    local desc="${3:-$dest}"
    info "Downloading: $desc"
    if ! curl -fsSL --retry 3 -o "$dest" "$url"; then
        error "Failed to download: $url"
        return 1
    fi
}

# ---------------------------------------------------------------------------
install_stream_engine_so() {
    local arch
    arch="$(detect_arch)"

    local url="${REPO_RAW}/lib/lib/${arch}/libtobii_stream_engine.so"
    local dest="${LIB_DIR}/libtobii_stream_engine.so"

    mkdir -p "${LIB_DIR}"
    if fetch_file "$url" "$dest" "libtobii_stream_engine.so (${arch})"; then
        chmod 755 "$dest"
        info "Installed: ${dest}"
    else
        error "Could not download libtobii_stream_engine.so"
        echo
        echo "Download manually from:"
        echo "  https://github.com/johngebbie/tobii_4C_for_linux/tree/main/lib/lib/${arch}"
        echo "and place as: ${dest}"
        return 1
    fi
}

# ---------------------------------------------------------------------------
install_usb_service() {
    local sbin_dir="/usr/local/sbin"
    local lib_dir="/usr/local/lib/tobiiusb"
    local service_dir="/etc/systemd/system"
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf -- "$tmpdir"' RETURN

    info "Installing tobiiusbserviced (system-wide, requires sudo)…"

    # Download daemon binary
    fetch_file \
        "${REPO_RAW}/tobii_usb_service/usr/local/sbin/tobiiusbserviced" \
        "${tmpdir}/tobiiusbserviced" \
        "tobiiusbserviced"

    # Download the three support libraries
    for lib in libtobii_libc.so libtobii_osal.so libtobii_usb.so; do
        fetch_file \
            "${REPO_RAW}/tobii_usb_service/usr/local/lib/tobiiusb/${lib}" \
            "${tmpdir}/${lib}" \
            "${lib}"
    done

    # Download service unit
    fetch_file \
        "${REPO_RAW}/tobii_usb_service/etc/systemd/system/tobiiusb.service" \
        "${tmpdir}/tobiiusb.service" \
        "tobiiusb.service"

    # Determine privilege escalation method
    local priv=""
    if [[ $EUID -eq 0 ]]; then
        priv=""
    elif command -v sudo &>/dev/null; then
        priv="sudo"
    else
        error "Root privileges required but sudo is not available."
        error "Re-run this script as root."
        return 1
    fi

    # Install (needs root)
    $priv mkdir -p "$lib_dir"
    $priv install -m 755 "${tmpdir}/tobiiusbserviced" "${sbin_dir}/tobiiusbserviced"
    info "Installed: ${sbin_dir}/tobiiusbserviced"

    for lib in libtobii_libc.so libtobii_osal.so libtobii_usb.so; do
        $priv install -m 644 "${tmpdir}/${lib}" "${lib_dir}/${lib}"
        info "Installed: ${lib_dir}/${lib}"
    done

    $priv install -m 644 "${tmpdir}/tobiiusb.service" "${service_dir}/tobiiusb.service"
    info "Installed: ${service_dir}/tobiiusb.service"

    $priv systemctl daemon-reload
    $priv systemctl enable --now tobiiusb.service
    info "tobiiusb.service enabled and started ✓"
}

# ---------------------------------------------------------------------------
already_installed() {
    [[ -f "${LIB_DIR}/libtobii_stream_engine.so" ]] && \
    [[ -f "/usr/local/sbin/tobiiusbserviced" ]]
}

# ---------------------------------------------------------------------------
main() {
    info "openstargazer – Tobii Stream Engine installer"
    echo

    check_deps

    if already_installed; then
        info "Stream Engine already installed in ${INSTALL_DIR}"
        read -rp "Re-install? [y/N] " ans
        if [[ "${ans,,}" != "y" ]]; then
            info "Skipping re-installation"
            return 0
        fi
    fi

    install_stream_engine_so
    install_usb_service

    echo
    info "Done! Stream Engine installed."
    info "Test with: osg-daemon --mock"
}

main "$@"
