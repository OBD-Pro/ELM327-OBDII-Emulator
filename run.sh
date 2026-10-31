#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

VENV=venv
PY="$VENV/bin/python"
SYSTEM_PY=/usr/bin/python3
DEFAULT_TCP_PORT=35000

USE_PTY=0
TCP_PORT=""
ARGS=()

ensure_virtualenv() {
    if [[ ! -x "$PY" ]]; then
        echo "Creating virtualenv in $VENV ..."
        python3 -m venv "$VENV"
    fi
    if ! "$PY" -c "import serial; serial.Serial" >/dev/null 2>&1; then
        echo "Installing pyserial ..."
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip uninstall --yes serial >/dev/null 2>&1 || true
        "$PY" -m pip install --quiet "pyserial>=3.5"
    fi
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --pty)
                USE_PTY=1
                ;;
            --tcp)
                TCP_PORT=$DEFAULT_TCP_PORT
                if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
                    TCP_PORT="$2"
                    shift
                fi
                ;;
            *)
                ARGS+=("$1")
                ;;
        esac
        shift
    done
}

enable_verbose_by_default() {
    local joined=" ${ARGS[*]-} "
    if [[ "$joined" != *" -v "* && "$joined" != *" --verbose "* ]]; then
        ARGS+=("-v")
    fi
}

has_port_option() {
    local arg
    for arg in "${ARGS[@]}"; do
        if [[ "$arg" == -p || "$arg" == --port || "$arg" == --port=* ]]; then
            return 0
        fi
    done
    return 1
}

prepare_bluetooth() {
    if ! "$SYSTEM_PY" -c "import dbus, gi; from gi.repository import GLib" \
        >/dev/null 2>&1; then
        echo "Installing python3-dbus and python3-gi (needed to talk to BlueZ) ..."
        sudo apt-get install -y python3-dbus python3-gi
    fi
    if ! systemctl is-active --quiet bluetooth; then
        echo "Starting the bluetooth service ..."
        sudo systemctl start bluetooth
    fi
    if bluetooth_is_blocked; then
        echo "Unblocking Bluetooth (rfkill) ..."
        rfkill unblock bluetooth 2>/dev/null || sudo rfkill unblock bluetooth
        sleep 1
    fi
}

bluetooth_is_blocked() {
    command -v rfkill >/dev/null \
        && rfkill list bluetooth 2>/dev/null | grep -q "Soft blocked: yes"
}

run_bluetooth() {
    prepare_bluetooth
    exec "$SYSTEM_PY" bt_bridge.py \
        --name "${OBD_BT_NAME:-OBDII}" \
        --python "$PWD/$PY" \
        -- "${ARGS[@]}"
}

run_tcp() {
    exec "$PY" tcp_bridge.py --port "$TCP_PORT" -- "${ARGS[@]}"
}

run_pty() {
    local link="${OBD_PTY:-$PWD/obd-pty}"
    echo "Virtual serial port: $link"
    exec "$PY" pty_bridge.py "$link" "${ARGS[@]}"
}

selected_serial_port() {
    local port=""
    local i
    for ((i = 0; i < ${#ARGS[@]}; i++)); do
        case "${ARGS[i]}" in
            -p|--port) port="${ARGS[i+1]:-$port}" ;;
            --port=*) port="${ARGS[i]#--port=}" ;;
        esac
    done
    echo "$port"
}

check_serial_port() {
    local port="$1"
    if [[ ! -e "$port" ]]; then
        echo "Serial port $port not found." \
            "Pass -p <device>, or use --pty for a virtual port." >&2
        exit 1
    fi
    if [[ ! -r "$port" || ! -w "$port" ]]; then
        echo "No read/write access to $port." \
            "Try: sudo usermod -a -G dialout \$USER (then log in again)" >&2
        exit 1
    fi
}

run_serial() {
    check_serial_port "$(selected_serial_port)"
    exec "$PY" obd_emulator.py "${ARGS[@]}"
}

main() {
    ensure_virtualenv
    parse_arguments "$@"
    enable_verbose_by_default

    if [[ -n "$TCP_PORT" ]]; then
        run_tcp
    elif [[ $USE_PTY -eq 1 ]]; then
        run_pty
    elif has_port_option; then
        run_serial
    else
        run_bluetooth
    fi
}

main "$@"
