import os
import select
import signal
import subprocess
import sys

from elm327.transport.raw_pty import emulator_command, open_raw_pty

BUFFER_SIZE = 4096
POLL_SECONDS = 0.2


class PtyBridge:
    def __init__(self, link_path, emulator_args):
        self._link_path = link_path
        self._emulator_master, emulator_slave = open_raw_pty()
        self._client_master, client_slave = open_raw_pty()
        self._publish_link(os.ttyname(client_slave))
        command = emulator_command(os.ttyname(emulator_slave), emulator_args)
        self._emulator = subprocess.Popen(command)

    def _publish_link(self, device):
        if os.path.lexists(self._link_path):
            os.remove(self._link_path)
        os.symlink(device, self._link_path)
        print(f"{self._link_path} -> {device}  (connect your client here)", flush=True)

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            while self._emulator.poll() is None:
                self._relay_once()
        except KeyboardInterrupt:
            pass
        finally:
            self._emulator.terminate()
            if os.path.islink(self._link_path):
                os.remove(self._link_path)

    def _relay_once(self):
        watched = [self._emulator_master, self._client_master]
        for ready in select.select(watched, [], [], POLL_SECONDS)[0]:
            self._forward(ready)

    def _forward(self, source):
        try:
            data = os.read(source, BUFFER_SIZE)
        except (BlockingIOError, OSError):
            return
        from_emulator = source == self._emulator_master
        target = self._client_master if from_emulator else self._emulator_master
        try:
            os.write(target, data)
        except BlockingIOError:
            pass


def main():
    PtyBridge(sys.argv[1], sys.argv[2:]).run()
