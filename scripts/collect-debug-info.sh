#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
# collect-debug-info.sh – Collects system/installation information for GitHub bug reports.
#
# Usage: ./collect-debug-info.sh
#   Creates: ~/openstargazer-debug-YYYYMMDD-HHMMSS.txt
#
# No root required. Safe to run standalone or via install.sh menu (option 6).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SCRIPT_VERSION="1.0"
OUTPUT_FILE="${HOME}/openstargazer-debug-$(date '+%Y%m%d-%H%M%S').txt"
GITHUB_ISSUES="https://github.com/1psconstructor/openstargazer/issues/new"

# ---------------------------------------------------------------------------
_get_version() {
    local ver=""
    if [[ -f "${PROJECT_DIR}/pyproject.toml" ]]; then
        ver="$(grep -m1 '^version' "${PROJECT_DIR}/pyproject.toml" \
               | sed 's/version *= *"\(.*\)"/\1/' 2>/dev/null || true)"
    fi
    if [[ -z "${ver}" ]]; then
        ver="$(python3 -m pip show openstargazer 2>/dev/null \
               | awk '/^Version:/{print $2}')" || true
    fi
    if [[ -z "${ver}" ]]; then
        local venv_pip="${HOME}/.local/share/openstargazer/venv/bin/pip"
        if [[ -x "${venv_pip}" ]]; then
            ver="$("${venv_pip}" show openstargazer 2>/dev/null \
                   | awk '/^Version:/{print $2}')" || true
        fi
    fi
    printf '%s' "${ver:-unknown}"
}

_section() {
    local title="$1"
    printf '\n\n================================================================================\n'
    printf '  %s\n' "${title}"
    printf '================================================================================\n'
}

_check_path() {
    local label="$1"
    local path="$2"
    if [[ -e "${path}" ]]; then
        printf '  [OK]      %s\n           -> %s\n' "${label}" "${path}"
    else
        printf '  [MISSING] %s\n           -> %s\n' "${label}" "${path}"
    fi
}

_redact_config() {
    local file="$1"
    if [[ ! -f "${file}" ]]; then
        printf '  (not found: %s)\n' "${file}"
        return
    fi
    cat "${file}"
}

# Every home path in the finished report, not only the ones in the config.
#
# This used to run on the config section alone, while the report also
# carries `systemctl status` (which prints the unit path), the journal,
# the install log and a list of checked paths -- all of them full of
# /home/<name>. The report says the paths are redacted, so they have to
# be, in all of it: it is written to be attached to a public issue.
#
# $HOME first and separately, because it is not always /home/<name>.
_redact() {
    local username home host
    username="$(id -un)"
    home="${HOME%/}"
    # The journal stamps every line with the machine's name, and people
    # name their machines after themselves. Only on journal lines, which
    # begin with a syslog timestamp: a hostname is often an ordinary word
    # -- this machine's is its distribution's name -- and replacing it
    # everywhere blanked `ID=fedora` out of the os-release section.
    host="$(hostname -s 2>/dev/null || true)"
    sed -e "s|${home}|/home/<user>|g" \
        -e "s|/home/${username}|/home/<user>|g" \
        ${host:+-e "/^ *[A-Z][a-z][a-z] [ 0-9][0-9] [0-9][0-9]:[0-9][0-9]:/ s|${host}|<host>|g"}
}

# ---------------------------------------------------------------------------
collect() {
    # ---- Section 1: Header ----
    printf 'openstargazer Debug Report\n'
    printf '  Generated   : %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
    printf '  App version : %s\n' "$(_get_version)"
    printf '  Script ver  : %s\n' "${SCRIPT_VERSION}"

    # ---- Section 2: System ----
    _section "System"
    if [[ -f /etc/os-release ]]; then
        grep -E '^(NAME|VERSION|ID|VERSION_ID|PRETTY_NAME)=' /etc/os-release | sed 's/^/  /'
    else
        printf '  /etc/os-release not found\n'
    fi
    printf '  Kernel      : %s\n' "$(uname -r)"
    printf '  Architecture: %s\n' "$(uname -m)"
    printf '  RAM         : %s\n' "$(free -h 2>/dev/null | awk '/^Mem:/{print $2}' || printf 'n/a')"
    printf '  CPU         : %s\n' \
        "$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || printf 'n/a')"

    # ---- Section 3: Python ----
    _section "Python"
    printf '  Python      : %s\n' "$(python3 --version 2>/dev/null || printf 'not found')"
    printf '  pip         : %s\n' "$(python3 -m pip --version 2>/dev/null || printf 'not found')"
    local venv_dir="${HOME}/.local/share/openstargazer/venv"
    if [[ -d "${venv_dir}" ]]; then
        printf '  venv        : present (%s)\n' "${venv_dir}"
        printf '  venv python : %s\n' "$("${venv_dir}/bin/python3" --version 2>/dev/null || printf 'error')"
    else
        printf '  venv        : not present\n'
    fi
    printf '\n  pip show openstargazer:\n'
    python3 -m pip show openstargazer 2>/dev/null | sed 's/^/    /' \
        || printf '    (not found via system pip)\n'
    if [[ -d "${venv_dir}" ]]; then
        printf '\n  venv pip show openstargazer:\n'
        "${venv_dir}/bin/pip" show openstargazer 2>/dev/null | sed 's/^/    /' \
            || printf '    (not found in venv)\n'
    fi

    # ---- Section 4: USB devices ----
    _section "USB Devices (Tobii)"
    lsusb 2>/dev/null | grep -i tobii || printf '  (no Tobii device found via lsusb)\n'

    # The configured backend decides which of the sections below matter:
    # "native" needs pyusb and the udev rule, "stream-engine" needs Tobii's
    # binaries and tobiiusbserviced.
    _section "Tracking Backend"
    local cfg_file="${XDG_CONFIG_HOME:-${HOME}/.config}/openstargazer/config.toml"
    local backend="native (default)"
    if [[ -f "${cfg_file}" ]]; then
        local configured
        configured="$(sed -n 's/^[[:space:]]*backend[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "${cfg_file}" | head -1)"
        [[ -n "${configured}" ]] && backend="${configured}"
    fi
    printf '  Configured backend: %s\n' "${backend}"

    # An install that hit PEP 668 lives in a venv -- checking the system
    # python3 there would report a missing pyusb that is actually present.
    local py="python3"
    [[ -x "${venv_dir}/bin/python3" ]] && py="${venv_dir}/bin/python3"
    printf '  Python used       : %s\n' "${py}"
    printf '  pyusb             : '
    "${py}" -c 'import usb; print(getattr(usb, "__version__", "unknown"))' 2>/dev/null \
        || printf 'not importable\n'

    # ---- Section 5: openstargazer service ----
    _section "openstargazer systemd User Service"
    systemctl --user status openstargazer 2>/dev/null || printf '  (service not found or not running)\n'
    printf '\n  Last 50 journal lines:\n'
    journalctl --user -u openstargazer -n 50 --no-pager 2>/dev/null \
        | sed 's/^/  /' || printf '  (no journal entries)\n'

    # ---- Section 6: tobiiusb service ----
    _section "tobiiusb System Service"
    systemctl status tobiiusb 2>/dev/null || printf '  (tobiiusb service not found)\n'

    # ---- Section 7: Install paths ----
    _section "Install Paths"
    _check_path "Stream Engine .so" \
        "${HOME}/.local/share/openstargazer/lib/libtobii_stream_engine.so"
    _check_path "tobiiusbserviced" \
        "/usr/local/sbin/tobiiusbserviced"
    _check_path "udev rules" \
        "/etc/udev/rules.d/70-openstargazer.rules"
    _check_path "venv" \
        "${HOME}/.local/share/openstargazer/venv"
    _check_path "desktop entry" \
        "${HOME}/.local/share/applications/openstargazer.desktop"
    _check_path "systemd user service file" \
        "${HOME}/.config/systemd/user/openstargazer.service"
    _check_path "config dir" \
        "${HOME}/.config/openstargazer"

    # ---- Section 8: opentrack ----
    _section "opentrack"
    if command -v opentrack &>/dev/null; then
        printf '  Version (native): '
        timeout 3 opentrack --version 2>/dev/null || printf 'n/a\n'
    else
        printf '  Native opentrack : not found\n'
    fi
    if flatpak list --app 2>/dev/null | grep -q 'io.github.opentrack.OpenTrack'; then
        printf '  Flatpak opentrack: installed\n'
        printf '  Version: '
        timeout 3 flatpak run io.github.opentrack.OpenTrack --version 2>/dev/null \
            || printf 'n/a\n'
    else
        printf '  Flatpak opentrack: not found\n'
    fi
    local ot_native="${HOME}/.config/opentrack"
    local ot_flatpak="${HOME}/.var/app/io.github.opentrack.OpenTrack/config/opentrack"
    for ot_dir in "${ot_native}" "${ot_flatpak}"; do
        if [[ -d "${ot_dir}" ]]; then
            printf '\n  Config dir: %s\n' "${ot_dir}"
            ls -1 "${ot_dir}" 2>/dev/null | sed 's/^/    /' || printf '    (empty)\n'
        fi
    done

    # ---- Section 9: Config file (redacted) ----
    _section "Config File (~/.config/openstargazer/config.toml)"
    _redact_config "${HOME}/.config/openstargazer/config.toml"

    # ---- Section 10: Install log ----
    _section "Install Log (last 100 lines)"
    local install_log="${HOME}/.local/share/openstargazer/install.log"
    if [[ -f "${install_log}" ]]; then
        tail -n 100 "${install_log}"
    else
        printf '  (install log not found: %s)\n' "${install_log}"
    fi

    # ---- Section 11: udev rules ----
    _section "udev Rules (/etc/udev/rules.d/70-openstargazer.rules)"
    local udev_file="/etc/udev/rules.d/70-openstargazer.rules"
    if [[ -f "${udev_file}" ]]; then
        cat "${udev_file}"
    else
        printf '  (file not found)\n'
    fi
}

# ---------------------------------------------------------------------------
echo "Collecting debug information..."
collect 2>&1 | _redact > "${OUTPUT_FILE}"

echo ""
echo "Debug report saved to:"
echo "  ${OUTPUT_FILE}"
echo ""
echo "Open a new GitHub issue and attach this file:"
echo "  ${GITHUB_ISSUES}"
echo ""
