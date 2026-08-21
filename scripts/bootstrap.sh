#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
# bootstrap.sh - fetch a release of openstargazer and run its installer.
#
# The one-line install. `install.sh` cannot be piped into a shell: it finds
# its own directory through BASH_SOURCE to load the translations next to
# it, and through a pipe there is no directory to find, so it aborts in its
# first few lines. That is not a bug to paper over -- an installer that
# reads files from its own tree needs a tree. So this script fetches one.
#
#   curl -fsSL https://raw.githubusercontent.com/1psconstructor/openstargazer/<tag>/scripts/bootstrap.sh \
#       | bash -s -- --ref <tag>
#
# Pinned on purpose. Fetching a branch means the code that runs is whatever
# the repository happened to contain at that second, which is not something
# a checksum can fix and not something a user can check afterwards.
#
# The whole script is one function called on the last line. A download that
# is cut short then runs nothing at all, rather than running the first half
# of an installer.

set -euo pipefail

OSG_REPO="${OSG_REPO:-1psconstructor/openstargazer}"

osg_bootstrap() {
    local ref="" sha256="" keep=0
    local -a install_args=()

    while [ $# -gt 0 ]; do
        case "$1" in
            --ref)      ref="${2:-}";    shift 2 ;;
            --sha256)   sha256="${2:-}"; shift 2 ;;
            --keep)     keep=1;          shift ;;
            --help|-h)
                sed -n '4,22p' "$0" 2>/dev/null || cat <<'USAGE'
bootstrap.sh --ref <tag> [--sha256 <hash>] [--keep] [-- <install.sh args>]
USAGE
                return 0 ;;
            --)         shift; install_args+=("$@"); break ;;
            *)          install_args+=("$1"); shift ;;
        esac
    done

    for tool in curl tar; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            echo "bootstrap: $tool is required but not installed." >&2
            return 1
        fi
    done

    if [ -z "$ref" ]; then
        cat >&2 <<EOF
bootstrap: no version given.

    --ref <tag>   which release to install, for example --ref v0.1.0

Deliberately has no default. A default of "main" would install whatever
the repository contains at the moment of the call, and nobody -- including
whoever wrote this -- could say afterwards what that was.

Released versions: https://github.com/${OSG_REPO}/tags
EOF
        return 1
    fi

    local url="https://github.com/${OSG_REPO}/archive/refs/tags/${ref}.tar.gz"
    local workdir
    workdir="$(mktemp -d "${TMPDIR:-/tmp}/openstargazer-XXXXXX")"
    if [ "$keep" -eq 0 ]; then
        trap 'rm -rf "$workdir"' EXIT
    else
        echo "bootstrap: keeping $workdir"
    fi

    echo "bootstrap: fetching ${ref}"
    if ! curl -fsSL "$url" -o "${workdir}/source.tar.gz"; then
        echo "bootstrap: could not download ${url}" >&2
        echo "bootstrap: check the tag exists: https://github.com/${OSG_REPO}/tags" >&2
        return 1
    fi

    if [ -n "$sha256" ]; then
        if ! command -v sha256sum >/dev/null 2>&1; then
            echo "bootstrap: --sha256 given but sha256sum is not installed." >&2
            return 1
        fi
        local actual
        actual="$(sha256sum "${workdir}/source.tar.gz" | cut -d' ' -f1)"
        if [ "$actual" != "$sha256" ]; then
            echo "bootstrap: checksum mismatch. Nothing was installed." >&2
            echo "  expected $sha256" >&2
            echo "  actual   $actual" >&2
            return 1
        fi
        echo "bootstrap: checksum verified"
    else
        # Said plainly rather than left out. A user who is piping a script
        # into a shell should be told exactly how much has been checked,
        # and the answer here is: the transport, and nothing else.
        echo "bootstrap: no --sha256 given; trusting TLS and GitHub alone."
    fi

    tar -xzf "${workdir}/source.tar.gz" -C "$workdir"

    local tree
    tree="$(find "$workdir" -mindepth 1 -maxdepth 1 -type d | head -n1)"
    if [ -z "$tree" ] || [ ! -x "${tree}/scripts/install.sh" ]; then
        echo "bootstrap: the archive does not look like openstargazer." >&2
        return 1
    fi

    echo "bootstrap: running the installer from ${tree}"
    # Handed a real directory, so it can find its translations and
    # everything else it reads.
    if [ "${#install_args[@]}" -gt 0 ]; then
        "${tree}/scripts/install.sh" "${install_args[@]}"
    else
        "${tree}/scripts/install.sh"
    fi
}

osg_bootstrap "$@"
