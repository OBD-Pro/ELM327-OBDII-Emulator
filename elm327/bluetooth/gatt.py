import dbus
import dbus.service

from elm327.bluetooth.constants import (
    ADVERT_PATH,
    ADVERTISEMENT_INTERFACE,
    CHARACTERISTIC_INTERFACE,
    GATT_APP_PATH,
    OBJECT_MANAGER_INTERFACE,
    PROPERTIES_INTERFACE,
    SERVICE_INTERFACE,
)
from elm327.bluetooth.logging_helpers import log


def uuid16(short_id):
    return f"0000{short_id}-0000-1000-8000-00805f9b34fb"


READ_NOTIFY = ["read", "notify"]
WRITE = ["read", "write", "write-without-response"]
READ_WRITE_NOTIFY = ["read", "write", "write-without-response", "notify"]

ELM_BLE_SERVICES = [
    (
        uuid16("fff0"),
        [(uuid16("fff1"), READ_NOTIFY), (uuid16("fff2"), WRITE)],
    ),
    (
        uuid16("ffe0"),
        [(uuid16("ffe1"), READ_WRITE_NOTIFY)],
    ),
    (
        uuid16("18f0"),
        [(uuid16("2af0"), READ_NOTIFY), (uuid16("2af1"), WRITE)],
    ),
    (
        "e7810a71-73ae-499d-8c15-faa9aef0c3f2",
        [("bef8d6c9-9c21-4c9e-b632-bd58c1009f9f", READ_WRITE_NOTIFY)],
    ),
]
ADVERTISED_UUIDS = ["FFF0", "FFE0", "18F0"]


class PropertiesObject(dbus.service.Object):
    INTERFACE = None

    def props(self):
        return {}

    @dbus.service.method(PROPERTIES_INTERFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, name):
        return self.GetAll(interface)[name]

    @dbus.service.method(PROPERTIES_INTERFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != self.INTERFACE:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs"
            )
        return self.props()

    @dbus.service.signal(PROPERTIES_INTERFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class GattService(PropertiesObject):
    INTERFACE = SERVICE_INTERFACE

    def __init__(self, bus, index, uuid):
        self.path = f"{GATT_APP_PATH}/service{index}"
        super().__init__(bus, self.path)
        self.uuid = uuid
        self.characteristics = []

    def props(self):
        return {"UUID": self.uuid, "Primary": dbus.Boolean(True)}


class GattCharacteristic(PropertiesObject):
    INTERFACE = CHARACTERISTIC_INTERFACE

    def __init__(self, bus, service, index, uuid, flags, link):
        self.path = f"{service.path}/char{index}"
        super().__init__(bus, self.path)
        self.service = service
        self.uuid = uuid
        self.flags = flags
        self.link = link
        self.value = b""
        self.notifying = False

    def props(self):
        return {
            "Service": dbus.ObjectPath(self.service.path),
            "UUID": self.uuid,
            "Flags": dbus.Array(self.flags, signature="s"),
            "Value": dbus.Array(self.value, signature="y"),
        }

    @dbus.service.method(
        CHARACTERISTIC_INTERFACE, in_signature="a{sv}", out_signature="ay"
    )
    def ReadValue(self, options):
        return dbus.Array(self.value, signature="y")

    @dbus.service.method(
        CHARACTERISTIC_INTERFACE, in_signature="aya{sv}", out_signature=""
    )
    def WriteValue(self, value, options):
        self.link.received(bytes(value), options)

    @dbus.service.method(CHARACTERISTIC_INTERFACE, in_signature="", out_signature="")
    def StartNotify(self):
        if not self.notifying:
            self.notifying = True
            self.link.subscribed(self)

    @dbus.service.method(CHARACTERISTIC_INTERFACE, in_signature="", out_signature="")
    def StopNotify(self):
        if self.notifying:
            self.notifying = False
            self.link.unsubscribed(self)

    def notify(self, chunk):
        self.value = chunk
        changed = {"Value": dbus.Array(chunk, signature="y")}
        self.PropertiesChanged(self.INTERFACE, changed, [])


class GattApplication(dbus.service.Object):
    def __init__(self, bus, link):
        super().__init__(bus, GATT_APP_PATH)
        self.services = [
            self._build_service(bus, link, index, uuid, characteristics)
            for index, (uuid, characteristics) in enumerate(ELM_BLE_SERVICES)
        ]

    def _build_service(self, bus, link, index, uuid, characteristics):
        service = GattService(bus, index, uuid)
        service.characteristics = [
            GattCharacteristic(bus, service, number, char_uuid, flags, link)
            for number, (char_uuid, flags) in enumerate(characteristics)
        ]
        return service

    @dbus.service.method(OBJECT_MANAGER_INTERFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        objects = {}
        for service in self.services:
            objects[dbus.ObjectPath(service.path)] = {
                service.INTERFACE: service.props()
            }
            for characteristic in service.characteristics:
                objects[dbus.ObjectPath(characteristic.path)] = {
                    characteristic.INTERFACE: characteristic.props()
                }
        return objects


class Advertisement(PropertiesObject):
    INTERFACE = ADVERTISEMENT_INTERFACE

    def __init__(self, bus, name):
        super().__init__(bus, ADVERT_PATH)
        self.name = name

    def props(self):
        return {
            "Type": "peripheral",
            "ServiceUUIDs": dbus.Array(ADVERTISED_UUIDS, signature="s"),
            "LocalName": self.name,
            "Discoverable": dbus.Boolean(True),
        }

    @dbus.service.method(ADVERTISEMENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        log("BLE advertisement released by BlueZ")
