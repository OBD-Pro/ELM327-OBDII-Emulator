import os
import subprocess
import time

from gi.repository import GLib

from elm327.bluetooth.logging_helpers import log
from elm327.transport.raw_pty import PROJECT_ROOT, emulator_command, open_raw_pty

BUFFER_SIZE = 65536
RESTART_DELAY_SECONDS = 1
STOP_TIMEOUT_SECONDS = 3
WATCHED_EVENTS = GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR


class EmulatorProcess:
    def __init__(self, python, args):
        self.python = python
        self.args = args
        self.process = None
        self.master = None
        self.slave = None
        self.watch = None
        self.on_output = lambda data: None

    def start(self):
        self.master, self.slave = open_raw_pty()
        port = os.ttyname(self.slave)
        command = emulator_command(port, self.args, self.python)
        self.process = subprocess.Popen(command, cwd=PROJECT_ROOT)
        self.watch = GLib.io_add_watch(self.master, WATCHED_EVENTS, self._read)
        log(f"emulator started (pid {self.process.pid}) on {port}")

    def _read(self, descriptor, condition):
        try:
            data = os.read(descriptor, BUFFER_SIZE)
        except OSError:
            return True
        if data:
            self.on_output(data)
        return True

    def write(self, data):
        try:
            os.write(self.master, data)
        except OSError:
            pass

    def restart_if_stopped(self):
        if self.process and self.process.poll() is not None:
            code = self.process.returncode
            log(f"emulator exited with code {code}, restarting")
            self.close()
            time.sleep(RESTART_DELAY_SECONDS)
            self.start()
        return True

    def close(self):
        if self.watch:
            GLib.source_remove(self.watch)
            self.watch = None
        self._stop_process()
        for descriptor in (self.master, self.slave):
            if descriptor is not None:
                os.close(descriptor)
        self.master = None
        self.slave = None

    def _stop_process(self):
        if not self.process or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
