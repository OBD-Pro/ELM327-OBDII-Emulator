import argparse
import os
import select
import signal
import socket
import subprocess
import sys

from elm327.transport.raw_pty import emulator_command, open_raw_pty

BUFFER_SIZE = 4096
POLL_SECONDS = 0.2


class TcpBridge:
    def __init__(self, host, port, emulator_args):
        self._host = host
        self._port = port
        self._master, slave = open_raw_pty()
        command = emulator_command(os.ttyname(slave), emulator_args)
        self._emulator = subprocess.Popen(command)
        self._server = self._listen()
        self._client = None

    def _listen(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self._host, self._port))
        server.listen(1)
        return server

    def run(self):
        print(
            f"ELM327 emulator on tcp://{self._host}:{self._port} (Wi-Fi adapter mode)",
            flush=True,
        )
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            while self._emulator.poll() is None:
                self._relay_once()
        except KeyboardInterrupt:
            pass
        finally:
            self._emulator.terminate()
            self._server.close()

    def _relay_once(self):
        watched = [self._server, self._master]
        if self._client:
            watched.append(self._client)
        for ready in select.select(watched, [], [], POLL_SECONDS)[0]:
            if ready is self._server:
                self._accept_client()
            elif ready is self._master:
                self._forward_to_client()
            else:
                self._forward_to_emulator()

    def _accept_client(self):
        connection, address = self._server.accept()
        if self._client:
            self._client.close()
        self._client = connection
        self._client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"client connected: {address[0]}:{address[1]}", flush=True)

    def _forward_to_client(self):
        try:
            data = os.read(self._master, BUFFER_SIZE)
        except (BlockingIOError, OSError):
            return
        if not self._client:
            return
        try:
            self._client.sendall(data)
        except OSError:
            self._client.close()
            self._client = None

    def _forward_to_emulator(self):
        data = self._client.recv(BUFFER_SIZE)
        if data:
            os.write(self._master, data)
            return
        print("client disconnected", flush=True)
        self._client.close()
        self._client = None


def main():
    parser = argparse.ArgumentParser(
        description="Serve the emulator over TCP, like a Wi-Fi ELM327 adapter."
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=35000)
    parser.add_argument(
        "emulator_args",
        nargs="*",
        help="passed to obd_emulator.py (after --)",
    )
    args = parser.parse_args()
    TcpBridge(args.host, args.port, args.emulator_args).run()
