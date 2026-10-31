from datetime import datetime

import dbus

from elm327.bluetooth.constants import BLUEZ, DEVICE_INTERFACE, PROPERTIES_INTERFACE


def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} [bt] {message}", flush=True)


def device_name(bus, path):
    try:
        device = bus.get_object(BLUEZ, path)
        properties = dbus.Interface(device, PROPERTIES_INTERFACE)
        alias = properties.Get(DEVICE_INTERFACE, "Alias")
        address = properties.Get(DEVICE_INTERFACE, "Address")
        return f"{alias} ({address})"
    except dbus.DBusException:
        return str(path)
