#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
# i18n.sh -- translation helper for the shell scripts.
#
# Reads the same language files as openstargazer/i18n.py:
#   openstargazer/locales/<code>.lang    "key = value", "#" starts a comment.
#
# Usage:
#   source "${SCRIPT_DIR}/i18n.sh"
#   i18n_load "${PROJECT_DIR}"
#   echo "$(t install.title)"
#   echo "$(t backend.chosen backend=native)"
#
# English is always loaded first and stays as the fallback, so an incomplete
# translation degrades to English per key instead of printing nothing.

declare -A OSG_MSG=()
OSG_LANGUAGE="en"

_i18n_parse_file() {
    local file="$1"
    [[ -f "$file" ]] || return 1

    local line key value
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#"${line%%[![:space:]]*}"}"      # strip leading blanks
        [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
        [[ "$line" != *"="* ]] && continue
        key="${line%%=*}"
        value="${line#*=}"
        key="${key%"${key##*[![:space:]]}"}"          # rstrip key
        value="${value#"${value%%[![:space:]]*}"}"    # lstrip value
        value="${value%"${value##*[![:space:]]}"}"    # rstrip value
        OSG_MSG["$key"]="$value"
    done < "$file"
}

_i18n_detect() {
    local locale_dir="$1"
    local candidate code short

    for candidate in "${OSG_LANG:-}" "${LC_ALL:-}" "${LC_MESSAGES:-}" "${LANG:-}"; do
        [[ -z "$candidate" ]] && continue
        code="${candidate%%.*}"
        code="${code%%@*}"
        if [[ -f "${locale_dir}/${code}.lang" ]]; then
            printf '%s' "$code"
            return
        fi
        short="${code%%_*}"
        short="${short,,}"
        if [[ -f "${locale_dir}/${short}.lang" ]]; then
            printf '%s' "$short"
            return
        fi
    done

    printf 'en'
}

i18n_load() {
    local project_dir="${1:-.}"
    local locale_dir="${project_dir}/openstargazer/locales"

    OSG_MSG=()
    _i18n_parse_file "${locale_dir}/en.lang" || return 0

    OSG_LANGUAGE="$(_i18n_detect "$locale_dir")"
    if [[ "$OSG_LANGUAGE" != "en" ]]; then
        _i18n_parse_file "${locale_dir}/${OSG_LANGUAGE}.lang" || true
    fi
}

# t <key> [name=value ...]  -- prints the translated text
t() {
    local key="$1"
    shift || true

    local text="${OSG_MSG[$key]-}"
    [[ -z "$text" ]] && text="$key"

    local arg name value
    for arg in "$@"; do
        name="${arg%%=*}"
        value="${arg#*=}"
        text="${text//\{$name\}/$value}"
    done

    printf '%s' "$text"
}
