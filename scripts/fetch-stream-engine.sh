#!/usr/bin/env bash
# fetch-stream-engine.sh – Download Tobii Stream Engine binaries for Linux
#
# Sources community-provided binaries from GitHub releases.
# The Tobii Stream Engine .so is not open-source, but has been distributed
# with community eye-tracking projects under permissive terms.
#
# Installs to: ~/.local/share/openstargazer/{bin,lib}/
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/openstargazer"
BIN_DIR="${INSTALL_DIR}/bin"
LIB_DIR="${INSTALL_DIR}/lib"

# Community mirror – update URL if release moves
REPO_BASE="https://github.com/johngebbie/tobii_4C_for_linux/releases/latest/download"

SO_NAME="libtobii_stream_engine.so"
USBSVC_NAME="tobiiusbservice"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[openstargazer]${NC} $*"; }
warn()  { echo -e "${YELLOW}[openstargazer]${NC} $*"; }
error() { echo -e "${RED}[openstargazer]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
check_deps() {
    for cmd in curl tar; do
        if ! command -v "$cmd" &>/dev/null; then
            error "Required tool not found: $cmd"
            exit 1
        fi
    done
}

# ---------------------------------------------------------------------------
fetch_file() {
    local url="$1"
    local dest="$2"
    info "Downloading: $url"
    if ! curl -fsSL --retry 3 -o "$dest" "$url"; then
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
install_from_release() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap "rm -rf '$tmpdir'" RETURN

    local tarball="${tmpdir}/tobii-stream-engine.tar.gz"

    # Try primary source
    local url="${REPO_BASE}/tobii-stream-engine-linux.tar.gz"
    if ! fetch_file "$url" "$tarball"; then
        warn "Primary source failed, trying alternative…"
        url="${REPO_BASE}/stream_engine_linux.tar.gz"
        if ! fetch_file "$url" "$tarball"; then
            error "Could not download Stream Engine binaries."
            echo
            echo "Please download manually:"
            echo "  ${REPO_BASE}/"
            echo
            echo "Extract and place:"
            echo "  libtobii_stream_engine.so → ${LIB_DIR}/"
            echo "  tobiiusbservice           → ${BIN_DIR}/"
            return 1
        fi
    fi

    info "Extracting…"
    tar -xzf "$tarball" -C "$tmpdir"

    # Find and copy the files
    local so_file usb_svc
    so_file="$(find "$tmpdir" -name "${SO_NAME}" | head -1)"
    usb_svc="$(find "$tmpdir" -name "${USBSVC_NAME}" | head -1)"

    if [[ -z "$so_file" ]]; then
        error "Could not find ${SO_NAME} in downloaded archive"
        ls "$tmpdir"
        return 1
    fi

    mkdir -p "${LIB_DIR}" "${BIN_DIR}"
    cp "$so_file" "${LIB_DIR}/${SO_NAME}"
    info "Installed: ${LIB_DIR}/${SO_NAME}"

    if [[ -n "$usb_svc" ]]; then
        cp "$usb_svc" "${BIN_DIR}/${USBSVC_NAME}"
        chmod +x "${BIN_DIR}/${USBSVC_NAME}"
        info "Installed: ${BIN_DIR}/${USBSVC_NAME}"
    else
        warn "${USBSVC_NAME} not found in archive – may not be needed for ET5"
    fi
}

# ---------------------------------------------------------------------------
install_usbservice_systemd() {
    local service_dir="${HOME}/.config/systemd/user"
    mkdir -p "$service_dir"

    cat > "${service_dir}/tobii-usbservice.service" <<EOF
[Unit]
Description=Tobii USB Service
After=graphical-session.target

[Service]
Type=simple
ExecStart=${BIN_DIR}/tobiiusbservice
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable tobii-usbservice.service
    info "tobii-usbservice systemd unit installed and enabled"
}

# ---------------------------------------------------------------------------
main() {
    info "openstargazer – Tobii Stream Engine installer"
    echo

    check_deps

    if [[ -f "${LIB_DIR}/${SO_NAME}" ]] && [[ -f "${BIN_DIR}/${USBSVC_NAME}" ]]; then
        info "Stream Engine already installed in ${INSTALL_DIR}"
        read -rp "Re-install? [y/N] " ans
        if [[ "${ans,,}" != "y" ]]; then
            info "Skipping re-installation"
        else
            install_from_release
        fi
    else
        install_from_release
    fi

    if [[ -f "${BIN_DIR}/${USBSVC_NAME}" ]]; then
        if command -v systemctl &>/dev/null; then
            read -rp "Install tobiiusbservice as systemd --user service? [Y/n] " ans
            if [[ "${ans,,}" != "n" ]]; then
                install_usbservice_systemd
            fi
        fi
    fi

    echo
    info "Done! Stream Engine installed to ${INSTALL_DIR}"
    info "Test with: osg-daemon --mock"
}

main "$@"
