import dbus

from elm327.bluetooth.constants import (
    ADAPTER_INTERFACE,
    BLUEZ,
    OBJECT_MANAGER_INTERFACE,
    PROPERTIES_INTERFACE,
)
from elm327.bluetooth.logging_helpers import log

SAVED_PROPERTIES = (
    "Discoverable",
    "Pairable",
    "DiscoverableTimeout",
    "PairableTimeout",
)


def find_adapter_path(bus):
    root = bus.get_object(BLUEZ, "/")
    manager = dbus.Interface(root, OBJECT_MANAGER_INTERFACE)
    for path, interfaces in manager.GetManagedObjects().items():
        if ADAPTER_INTERFACE in interfaces:
            return path
    return None


class BluetoothAdapter:
    def __init__(self, bus, path):
        self.path = path
        self._properties = dbus.Interface(
            bus.get_object(BLUEZ, path), PROPERTIES_INTERFACE
        )
        self._saved = {name: self._get(name) for name in SAVED_PROPERTIES}

    def _get(self, name):
        return self._properties.Get(ADAPTER_INTERFACE, name)

    def _set(self, name, value):
        self._properties.Set(ADAPTER_INTERFACE, name, value)

    def make_visible(self, name):
        self._set("Powered", dbus.Boolean(True))
        self._set("Alias", name)
        self._set("DiscoverableTimeout", dbus.UInt32(0))
        self._set("PairableTimeout", dbus.UInt32(0))
        self._set("Discoverable", dbus.Boolean(True))
        self._set("Pairable", dbus.Boolean(True))
        address = self._get("Address")
        log(f"adapter {address} '{name}' powered, discoverable and pairable")

    def restore_steps(self):
        return [
            lambda name=name, value=value: self._set(name, value)
            for name, value in self._saved.items()
        ]
