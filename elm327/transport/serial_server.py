import logging
import time
from datetime import datetime

import serial

from elm327.adapter.replies import START_MONITORING

READ_TIMEOUT_SECONDS = 0.01
PROMPT = "\r\r>"
MONITOR_STOPPED = b"\r>"

logger = logging.getLogger("obd-emulator")


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_traffic(direction, text):
    logger.info("%s: %s", direction, text)
    print(f"{timestamp()} {direction}: {text}")


class SerialServer:
    def __init__(self, port_name, baud, emulator):
        self._port_name = port_name
        self._baud = baud
        self._adapter = emulator.adapter
        self._monitor = emulator.monitor
        self._settings = emulator.settings
        self._port = None
        self._buffer = b""

    def run(self):
        self._open_port()
        try:
            while True:
                self._serve_once()
        except KeyboardInterrupt:
            logger.info("Shutting down emulator...")
        finally:
            self._close_port()

    def _open_port(self):
        logger.info(
            "ELM327 Emulator running on %s @ %s...", self._port_name, self._baud
        )
        try:
            self._port = serial.Serial(
                self._port_name, baudrate=self._baud, timeout=READ_TIMEOUT_SECONDS
            )
        except Exception as error:
            logger.error("Failed to open serial port %s: %s", self._port_name, error)
            raise
        print(f"{timestamp()} started at COM : {self._port_name}")

    def _close_port(self):
        try:
            self._port.close()
        except Exception:
            pass

    def _serve_once(self):
        data = self._port.read(max(1, self._port.in_waiting))
        if data and self._monitor.active:
            self._stop_monitoring()
            return

        self._buffer += data.replace(b"\n", b"")
        self._answer_complete_lines()
        if self._monitor.active:
            self._send_monitor_lines()

    def _stop_monitoring(self):
        self._monitor.stop()
        self._buffer = b""
        logger.info("monitor stopped")
        self._port.write(MONITOR_STOPPED)

    def _answer_complete_lines(self):
        while b"\r" in self._buffer:
            line, _, self._buffer = self._buffer.partition(b"\r")
            command = line.decode(errors="ignore").strip()
            if command:
                self._answer(command)

    def _answer(self, command):
        print_traffic("RX", command)
        reply = self._adapter.handle_line(command)
        if reply is START_MONITORING:
            self._monitor.restart()
            self._buffer = b""
            logger.info("monitor started")
        elif reply:
            print_traffic("TX", reply)
            self._port.write((reply + PROMPT).encode())

    def _send_monitor_lines(self):
        lines = self._monitor.read_lines(time.monotonic())
        if lines:
            line_end = "\r\n" if self._settings.linefeeds else "\r"
            text = "".join(line + line_end for line in lines)
            self._port.write(text.encode())
            logger.debug("TX: %s", lines)
