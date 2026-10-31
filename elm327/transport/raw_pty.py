import os
import pty
import sys
import tty
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRY_POINT = PROJECT_ROOT / "obd_emulator.py"


def open_raw_pty():
    master, slave = pty.openpty()
    tty.setraw(slave)
    os.set_blocking(master, False)
    return master, slave


def emulator_command(port, extra_args, python=sys.executable):
    return [python, str(ENTRY_POINT), "-p", port, *extra_args]
