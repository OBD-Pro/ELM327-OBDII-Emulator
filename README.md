# OBD Emulator (ELM327-Compatible)

A production-ready, ELM327-like OBD-II emulator that communicates over a serial port and can stream synthetic CAN frames for common vehicle signals. Useful for testing scan tools, validating OBD workflows, and CI/integration setups without needing a live vehicle.

## Features
- ELM AT command handling: ATE0/1, ATL0/1, ATS0/1, ATH0/1, ATSP, ATDP, ATRV, ATMA/MR/PC, ATCRA/ATCM/ATSH, etc.
- OBD Mode 01 PIDs: RPM, speed, coolant, throttle, freeze-frame, DTCs.
- Idle CAN bus (`idle` state): 15 cyclic messages (20 ms-1 s cycle times, rolling counters + J1850 CRC-8) carrying the same values the Mode 01 PIDs return (RPM, coolant, MAP/MAF, trims, voltage, A/C compressor, ...), plus ABS, steering, TCM, cluster, body, HVAC, TPMS, odometer and clock frames. `stationary`/`moving` use the older synthetic stream.
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
python obd_emulator.py -p COM3 -b 38400 -s idle -v
```

Linux (/dev/ttyUSB0 example):
```
python obd_emulator.py -p /dev/ttyUSB0 -b 38400 -s stationary -v
```

## Usage & Options
- `-p/--port`: serial port device (e.g., `COM3`, `/dev/ttyUSB0`).
- `-b/--baud`: baud rate (default 38400).
- `-s/--vehicle-state`: `idle` (default: warm engine idling in Park, 0 km/h), `stationary`, or `moving`.
- `-v/--verbose`: enable console RX/TX logs.

### CAN Monitor Controls
- Start stream: `ATMA` (all frames; spaces in AT commands are ignored, so `AT MA` works), `ATMR hh` / `ATMT hh` (frames whose ID low byte is `hh`).
- Stop stream: send any character, as on a real ELM327.
- Output: data bytes only with `ATH0`; `ATH1` adds the ID, `ATD1` also the DLC, `ATS0` removes spaces.
- Filters: `ATCRA hhh` (exact ID, `ATCRA` clears), `ATCF hhh` + `ATCM hhh` (ID & mask must equal filter & mask). They apply to the stream and to the ECU's replies (a non-matching reply gives `NO DATA`).
- `ATSH 7E0`/`7DF` address the engine ECU (reply ID `7E8`); any other header gets `NO DATA`.

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
