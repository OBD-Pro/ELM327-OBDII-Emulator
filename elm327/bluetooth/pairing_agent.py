import dbus
import dbus.service

from elm327.bluetooth.constants import (
    AGENT_INTERFACE,
    AGENT_PATH,
    PAIRING_PASSKEY,
    PAIRING_PIN,
    SERIAL_PORT_UUID,
)
from elm327.bluetooth.logging_helpers import device_name, log


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


class PairingAgent(dbus.service.Object):
    def __init__(self, bus):
        super().__init__(bus, AGENT_PATH)
        self.bus = bus

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        if str(uuid).lower() != SERIAL_PORT_UUID:
            log(f"refused service {uuid} for {device_name(self.bus, device)}")
            raise Rejected("only the serial port is offered")

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        log(f"PIN {PAIRING_PIN} sent to {device_name(self.bus, device)}")
        return PAIRING_PIN

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        return dbus.UInt32(PAIRING_PASSKEY)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        pass

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        pass

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        log(f"pairing accepted: {device_name(self.bus, device)}")

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        log(f"pairing accepted: {device_name(self.bus, device)}")

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        pass
