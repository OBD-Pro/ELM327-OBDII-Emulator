import argparse
import signal
import sys

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from elm327.bluetooth.ble_link import BleLink
from elm327.bluetooth.ble_server import BleServer
from elm327.bluetooth.bluetooth_adapter import BluetoothAdapter, find_adapter_path
from elm327.bluetooth.constants import (
    AGENT_PATH,
    BLUEZ,
    BLUEZ_ROOT,
    PROFILE_PATH,
    RFCOMM_CHANNEL,
    SERIAL_PORT_UUID,
)
from elm327.bluetooth.emulator_process import EmulatorProcess
from elm327.bluetooth.logging_helpers import log
from elm327.bluetooth.pairing_agent import PairingAgent
from elm327.bluetooth.serial_profile import SerialProfile

ALIVE_CHECK_SECONDS = 2
NO_ADAPTER_MESSAGE = (
    "No Bluetooth adapter found. "
    "Is the bluetooth service running and the adapter unblocked (rfkill)?"
)


def glib_signal_add():
    try:
        from gi.repository import GLibUnix

        return GLibUnix.signal_add
    except ImportError:
        return GLib.unix_signal_add


class BluetoothBridge:
    def __init__(self, name, python, emulator_args):
        self._name = name
        DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()

        adapter_path = find_adapter_path(self._bus)
        if not adapter_path:
            sys.exit(NO_ADAPTER_MESSAGE)
        self._adapter = BluetoothAdapter(self._bus, adapter_path)
        self._adapter.make_visible(name)

        self._agent = PairingAgent(self._bus)
        self._agent_manager = self._bluez_manager("org.bluez.AgentManager1")
        self._agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
        self._agent_manager.RequestDefaultAgent(AGENT_PATH)

        self._emulator = EmulatorProcess(python, emulator_args)
        self._serial_profile = SerialProfile(self._bus, self._emulator)
        self._ble_link = BleLink(self._bus, self._emulator)
        self._emulator.on_output = self._send_to_clients
        self._emulator.start()

        self._profile_manager = self._bluez_manager("org.bluez.ProfileManager1")
        self._register_serial_profile()

        self._ble_server = BleServer(self._bus, adapter_path, name, self._ble_link)
        self._ble_server.register()
        log("waiting for connections (Ctrl+C to stop)")

    def _bluez_manager(self, interface):
        return dbus.Interface(self._bus.get_object(BLUEZ, BLUEZ_ROOT), interface)

    def _register_serial_profile(self):
        options = {
            "Name": self._name,
            "Role": "server",
            "Channel": dbus.UInt16(RFCOMM_CHANNEL),
            "RequireAuthentication": dbus.Boolean(False),
            "RequireAuthorization": dbus.Boolean(False),
            "AutoConnect": dbus.Boolean(True),
        }
        self._profile_manager.RegisterProfile(PROFILE_PATH, SERIAL_PORT_UUID, options)
        log(
            f"Classic SPP ready on RFCOMM channel {RFCOMM_CHANNEL} "
            f"(Android: pair with '{self._name}')"
        )

    def _send_to_clients(self, data):
        self._serial_profile.send(data)
        self._ble_link.send(data)

    def run(self):
        loop = GLib.MainLoop()
        GLib.timeout_add_seconds(ALIVE_CHECK_SECONDS, self._emulator.restart_if_stopped)
        add_signal = glib_signal_add()
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            add_signal(GLib.PRIORITY_HIGH, signal_number, loop.quit)
        try:
            loop.run()
        finally:
            self._shut_down()

    def _shut_down(self):
        log("shutting down")
        self._serial_profile.drop_client()
        steps = [
            *self._ble_server.unregister_steps(),
            lambda: self._profile_manager.UnregisterProfile(PROFILE_PATH),
            lambda: self._agent_manager.UnregisterAgent(AGENT_PATH),
            *self._adapter.restore_steps(),
        ]
        for step in steps:
            try:
                step()
            except dbus.DBusException:
                pass
        self._emulator.close()


def main():
    parser = argparse.ArgumentParser(
        description="Expose the emulator as a Bluetooth ELM327 dongle "
        "(Classic SPP and BLE)."
    )
    parser.add_argument(
        "--name",
        default="OBDII",
        help="Bluetooth name shown to phones (default: %(default)s)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python that runs obd_emulator.py (needs pyserial)",
    )
    parser.add_argument(
        "emulator_args",
        nargs="*",
        help="extra obd_emulator.py options, after --",
    )
    args = parser.parse_args()
    BluetoothBridge(args.name, args.python, args.emulator_args).run()
