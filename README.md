# OBD Emulator (ELM327-Compatible)

A production-ready, ELM327-like OBD-II emulator that communicates over a serial port and can stream synthetic CAN frames for common vehicle signals. Useful for testing scan tools, validating OBD workflows, and CI/integration setups without needing a live vehicle.

## Features
- ELM AT command handling: ATE0/1, ATL0/1, ATS0/1, ATH0/1, ATSP, ATDP, ATRV, ATMA/MR/PC, ATCRA/ATCM/ATSH, etc.
- OBD Mode 01 PIDs: RPM, speed, coolant, throttle, freeze-frame, DTCs.
- CAN monitor stream: realistic signals (RPM, accel, speed, brake, lights, radio, steering angle/rate, gear, PRNDL heuristic, doors, HVAC, TPMS).
- Pre-init behavior toggle: `ATPND0` (silent) vs `ATPND1` (reply `NO DATA`) before `ATZ`.
- Cross-platform defaults: Windows and Linux.
- CLI configuration with structured logging.

## Installation

1) Install dependencies:
```
pip install -r requirements.txt
```

2) Critical warning about `serial` vs `pyserial`:

Many environments accidentally install `serial` (unrelated/obsolete) instead of `pyserial`, which breaks serial communication. To ensure a clean setup, uninstall any conflicting packages and install `pyserial` explicitly:

```
pip uninstall serial pyserial
pip install pyserial
```

If you use virtual environments, run these commands inside your venv.

## Quick Start

Windows (COM3 example):
```
python obd_emulator.py -p COM3 -b 38400 -s moving -v
```

Linux (/dev/ttyUSB0 example):
```
python obd_emulator.py -p /dev/ttyUSB0 -b 38400 -s stationary -v
```

## Usage & Options
- `-p/--port`: serial port device (e.g., `COM3`, `/dev/ttyUSB0`).
- `-b/--baud`: baud rate (default 38400).
- `-s/--vehicle-state`: `moving` or `stationary`.
- `-v/--verbose`: enable console RX/TX logs.

### CAN Monitor Controls
- Start stream: `AT MA` (all) or `AT MR` (receive).
- Stop stream: `AT PC`.
- Filters: `ATCRA`/`ATCM` to filter IDs.

### Initialization Notes
- Before `ATZ`, PIDs are gated. Use `ATPND1` if you prefer seeing `NO DATA` instead of silence pre-init.
- This emulator uses synthetic (non-OEM) IDs/encodings for demonstration. Provide your DBC/ID list if you need specific formats.

## Troubleshooting
- Port busy/in use: close other serial tools (scan apps, terminals) that may hold the port.
- Linux permissions: add your user to the `dialout` group and re-login:
	- `sudo usermod -a -G dialout $USER`
- Discover available ports:
	- `python -m serial.tools.list_ports`
- Baud mismatch: ensure your scan tool baud rate matches the emulator.

## Production Notes
- For long-running deployments, wrap the emulator with a service manager (e.g., systemd on Linux or NSSM on Windows), and configure log rotation.
- Enable `-v` during bring-up; disable later or redirect logs for cleaner output.
