#!/usr/bin/env bash
# Run the ELM327 OBD-II emulator on Linux.
#
#   ./run.sh                          # Bluetooth Classic + BLE: "OBDII" for Android and iPhone apps
#   ./run.sh -s moving                # extra options are passed to obd_emulator.py
#   ./run.sh -p /dev/ttyUSB0          # a real serial device instead of Bluetooth
#   ./run.sh --pty                    # no hardware: create a virtual serial port
#   ./run.sh --tcp [PORT]             # Wi-Fi adapter mode: TCP server on PORT (default 35000)
#
# Bluetooth mode (default) needs no root: bt_bridge.py powers the adapter on,
# makes it discoverable/pairable, accepts pairing (PIN 1234 for old devices),
# registers the Serial Port Profile (Android) and BLE GATT services (iPhone)
# and relays connections to the emulator.
# Set OBD_BT_NAME to change the device name.
#
# With --pty the emulator runs on a pseudo-terminal linked at ./obd-pty
# (override with OBD_PTY=/path). Connect a client to it, e.g.:
#   venv/bin/pyserial-miniterm ./obd-pty 38400
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

VENV=venv
PY="$VENV/bin/python"

# Create the virtualenv and install pyserial on first run
if [[ ! -x "$PY" ]]; then
    echo "Creating virtualenv in $VENV ..."
    python3 -m venv "$VENV"
fi
if ! "$PY" -c "import serial; serial.Serial" >/dev/null 2>&1; then
    echo "Installing pyserial ..."
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip uninstall --yes serial >/dev/null 2>&1 || true   # conflicting package, see README
    "$PY" -m pip install --quiet "pyserial>=3.5"
fi

USE_PTY=0
TCP_PORT=""
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pty) USE_PTY=1 ;;
        --tcp)
            TCP_PORT=35000
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then TCP_PORT="$2"; shift; fi ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done

# Default to verbose RX/TX logging unless the caller already chose
[[ " ${ARGS[*]-} " == *" -v "* || " ${ARGS[*]-} " == *" --verbose "* ]] || ARGS+=("-v")

HAS_PORT=0
for a in "${ARGS[@]}"; do [[ "$a" == -p || "$a" == --port || "$a" == --port=* ]] && HAS_PORT=1; done

if [[ -n "$TCP_PORT" ]]; then
    exec "$PY" tcp_bridge.py --port "$TCP_PORT" -- "${ARGS[@]}"
fi

if [[ $USE_PTY -eq 0 && $HAS_PORT -eq 0 ]]; then
    SYSPY=/usr/bin/python3
    if ! "$SYSPY" -c "import dbus, gi; from gi.repository import GLib" >/dev/null 2>&1; then
        echo "Installing python3-dbus and python3-gi (needed to talk to BlueZ) ..."
        sudo apt-get install -y python3-dbus python3-gi
    fi
    if ! systemctl is-active --quiet bluetooth; then
        echo "Starting the bluetooth service ..."
        sudo systemctl start bluetooth
    fi
    if command -v rfkill >/dev/null && rfkill list bluetooth 2>/dev/null | grep -q "Soft blocked: yes"; then
        echo "Unblocking Bluetooth (rfkill) ..."
        rfkill unblock bluetooth 2>/dev/null || sudo rfkill unblock bluetooth
        sleep 1
    fi
    exec "$SYSPY" bt_bridge.py --name "${OBD_BT_NAME:-OBDII}" --python "$PWD/$PY" -- "${ARGS[@]}"
fi

if [[ $USE_PTY -eq 1 ]]; then
    LINK="${OBD_PTY:-$PWD/obd-pty}"
    echo "Virtual serial port: $LINK"
    # Two ptys bridged back to back (like `socat pty pty`): the emulator opens one,
    # clients open the other through the symlink.
    exec "$PY" -c '
import os, pty, select, signal, subprocess, sys, tty
link, args = sys.argv[1], sys.argv[2:]
emu_m, emu_s = pty.openpty()
cli_m, cli_s = pty.openpty()
for fd in (emu_s, cli_s):
    tty.setraw(fd)
for fd in (emu_m, cli_m):
    os.set_blocking(fd, False)   # never stall the emulator when no client is reading
if os.path.lexists(link):
    os.remove(link)
os.symlink(os.ttyname(cli_s), link)
print(f"{link} -> {os.ttyname(cli_s)}  (connect your client here)", flush=True)
emu = subprocess.Popen([sys.executable, "obd_emulator.py", "-p", os.ttyname(emu_s), *args])
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
try:
    while emu.poll() is None:
        for fd in select.select([emu_m, cli_m], [], [], 0.2)[0]:
            try:
                data = os.read(fd, 4096)
            except (BlockingIOError, OSError):   # no client attached right now
                continue
            try:
                os.write(cli_m if fd == emu_m else emu_m, data)
            except BlockingIOError:  # peer not reading: drop, like a full UART buffer
                pass
except KeyboardInterrupt:
    pass
finally:
    emu.terminate()
    if os.path.islink(link):
        os.remove(link)
' "$LINK" "${ARGS[@]}"
fi

# Real serial device: warn early about missing device / permissions
PORT=""
for ((i = 0; i < ${#ARGS[@]}; i++)); do
    case "${ARGS[i]}" in
        -p|--port) PORT="${ARGS[i+1]:-$PORT}" ;;
        --port=*)  PORT="${ARGS[i]#--port=}" ;;
    esac
done
if [[ ! -e "$PORT" ]]; then
    echo "Serial port $PORT not found. Pass -p <device>, or use --pty for a virtual port." >&2
    exit 1
fi
if [[ ! -r "$PORT" || ! -w "$PORT" ]]; then
    echo "No read/write access to $PORT. Try: sudo usermod -a -G dialout \$USER (then log in again)" >&2
    exit 1
fi

exec "$PY" obd_emulator.py "${ARGS[@]}"
