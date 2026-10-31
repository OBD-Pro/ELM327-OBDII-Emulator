import os

import dbus.service
from gi.repository import GLib

from elm327.bluetooth.constants import PROFILE_INTERFACE, PROFILE_PATH
from elm327.bluetooth.logging_helpers import device_name, log

BUFFER_SIZE = 4096
WATCHED_EVENTS = GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR


class SerialProfile(dbus.service.Object):
    def __init__(self, bus, emulator):
        super().__init__(bus, PROFILE_PATH)
        self.bus = bus
        self.emulator = emulator
        self.client = None

    @dbus.service.method(PROFILE_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method(PROFILE_INTERFACE, in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, descriptor, properties):
        descriptor = descriptor.take()
        os.set_blocking(descriptor, False)
        if self.client:
            log("new client replaces the previous one")
            self.drop_client()
        watch = GLib.io_add_watch(descriptor, WATCHED_EVENTS, self.on_client_data)
        self.client = (device, descriptor, watch)
        log(f"connected: {device_name(self.bus, device)}")

    @dbus.service.method(PROFILE_INTERFACE, in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        if self.client and self.client[0] == device:
            self.drop_client()

    def on_client_data(self, descriptor, condition):
        data = b""
        if condition & GLib.IO_IN:
            try:
                data = os.read(descriptor, BUFFER_SIZE)
            except BlockingIOError:
                return True
            except OSError:
                data = b""
        if not data:
            self.drop_client()
            return False
        self.emulator.write(data)
        return True

    def send(self, data):
        if not self.client:
            return
        try:
            os.write(self.client[1], data)
        except BlockingIOError:
            pass
        except OSError:
            self.drop_client()

    def drop_client(self):
        if not self.client:
            return
        device, descriptor, watch = self.client
        self.client = None
        GLib.source_remove(watch)
        try:
            os.close(descriptor)
        except OSError:
            pass
        log(f"disconnected: {device_name(self.bus, device)}")
        self.emulator.write(b"\r")
