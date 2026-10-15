#!/usr/bin/env python3
"""Expose obd_emulator.py as a Bluetooth ELM327 dongle: Classic SPP (Android) and BLE (iPhone).

Uses BlueZ over D-Bus, no root, no rfcomm/sdptool:
  * powers the adapter on, names it, makes it discoverable + pairable
  * registers a pairing agent that accepts phones without a PIN prompt
    (legacy devices asking for a PIN get 1234, the usual ELM327 PIN)
  * registers the Serial Port Profile (UUID 0x1101) on RFCOMM channel 1
  * advertises over BLE with the GATT services BLE ELM327 dongles use
    (FFF0/FFF1/FFF2, FFE0/FFE1, 18F0/2AF0/2AF1, Vgate E7810A71), so iOS apps
    such as Car Scanner, OBD Fusion or Torque-like scanners find it
  * runs the emulator on a pty and relays it to whichever client is connected

The emulator keeps running between connections, and is restarted if it exits.
On exit the adapter's discoverable/pairable settings are restored.

Run with the system python (needs python3-dbus and python3-gi):
    /usr/bin/python3 bt_bridge.py [--name OBDII] [-- emulator options]
"""
import argparse
import os
import pty
import signal
import subprocess
import sys
import time
import tty
from datetime import datetime

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

BUS = "org.bluez"
SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"
AGENT_PATH = "/obd/agent"
PROFILE_PATH = "/obd/spp"
HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [bt] {msg}", flush=True)


def device_name(bus, path):
    try:
        props = dbus.Interface(bus.get_object(BUS, path), "org.freedesktop.DBus.Properties")
        return f"{props.Get('org.bluez.Device1', 'Alias')} ({props.Get('org.bluez.Device1', 'Address')})"
    except dbus.DBusException:
        return str(path)


class Rejected(dbus.DBusException):
    _dbus_error_name = "org.bluez.Error.Rejected"


class Agent(dbus.service.Object):
    """Accepts pairing without user interaction; only lets the serial port service through."""

    def __init__(self, bus):
        super().__init__(bus, AGENT_PATH)
        self.bus = bus

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        if str(uuid).lower() != SPP_UUID:
            log(f"refused service {uuid} for {device_name(self.bus, device)}")
            raise Rejected("only the serial port is offered")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        log(f"PIN 1234 sent to {device_name(self.bus, device)}")
        return "1234"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        return dbus.UInt32(1234)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        pass

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        log(f"pairing accepted: {device_name(self.bus, device)}")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        log(f"pairing accepted: {device_name(self.bus, device)}")

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        pass


class SerialProfile(dbus.service.Object):
    """SPP server: one client at a time, relayed to the emulator's pty."""

    def __init__(self, bus, emulator):
        super().__init__(bus, PROFILE_PATH)
        self.bus = bus
        self.emu = emulator
        self.client = None      # (device path, fd, GLib watch id)

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        pass

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, fd, properties):
        fd = fd.take()
        os.set_blocking(fd, False)
        if self.client:
            log("new client replaces the previous one")
            self.drop_client()
        watch = GLib.io_add_watch(fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.on_client_data)
        self.client = (device, fd, watch)
        log(f"connected: {device_name(self.bus, device)}")

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        if self.client and self.client[0] == device:
            self.drop_client()

    def on_client_data(self, fd, cond):
        data = b""
        if cond & GLib.IO_IN:
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                return True
            except OSError:
                data = b""
        if not data:
            self.drop_client()
            return False
        self.emu.write(data)
        return True

    def send(self, data):
        if not self.client:
            return  # nobody connected: output is dropped, like a dongle with no host
        try:
            os.write(self.client[1], data)
        except BlockingIOError:
            pass    # client not reading fast enough (e.g. ATMA flood): drop, like a full UART buffer
        except OSError:
            self.drop_client()

    def drop_client(self):
        if not self.client:
            return
        device, fd, watch = self.client
        self.client = None
        GLib.source_remove(watch)
        try:
            os.close(fd)
        except OSError:
            pass
        log(f"disconnected: {device_name(self.bus, device)}")
        self.emu.write(b"\r")   # ends an ATMA stream left running by the client


# ---------------------------------------------------------------------------
# Bluetooth Low Energy (iPhone and BLE-only apps)
#
# iOS apps cannot use Classic SPP, so BLE ELM327 dongles expose a GATT
# "serial" service: the app writes commands to one characteristic and gets
# the replies as notifications. Different dongle brands use different UUIDs,
# so all the common layouts are offered; each app finds the one it knows.
# No pairing is needed (like the real dongles), the characteristics are open.
# ---------------------------------------------------------------------------
GATT_APP_PATH = "/obd/gatt"
ADVERT_PATH = "/obd/advert"

def _uuid16(short):
    return f"0000{short}-0000-1000-8000-00805f9b34fb"

READ_NOTIFY = ["read", "notify"]
WRITE = ["read", "write", "write-without-response"]
BOTH = ["read", "write", "write-without-response", "notify"]

ELM_BLE_SERVICES = [
    (_uuid16("fff0"), [(_uuid16("fff1"), READ_NOTIFY), (_uuid16("fff2"), WRITE)]),  # most clones, Veepeak, Konnwei
    (_uuid16("ffe0"), [(_uuid16("ffe1"), BOTH)]),                                    # HM-10 style clones
    (_uuid16("18f0"), [(_uuid16("2af0"), READ_NOTIFY), (_uuid16("2af1"), WRITE)]),   # Vgate iCar / some OBDLink-style
    ("e7810a71-73ae-499d-8c15-faa9aef0c3f2",                                         # Vgate vLinker / iOS-Vlink
     [("bef8d6c9-9c21-4c9e-b632-bd58c1009f9f", BOTH)]),
]
ADVERTISED_UUIDS = ["FFF0", "FFE0", "18F0"]  # 16-bit ones fit in the 31-byte advert with the name


class BlePropsObject(dbus.service.Object):
    """dbus.service.Object with the org.freedesktop.DBus.Properties read side BlueZ needs."""
    IFACE = None

    def props(self):
        return {}

    @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
    def Get(self, iface, name):
        return self.GetAll(iface)[name]

    @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        if iface != self.IFACE:
            raise dbus.exceptions.DBusException("org.freedesktop.DBus.Error.InvalidArgs")
        return self.props()

    @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
    def PropertiesChanged(self, iface, changed, invalidated):
        pass


class GattService(BlePropsObject):
    IFACE = "org.bluez.GattService1"

    def __init__(self, bus, index, uuid):
        self.path = f"{GATT_APP_PATH}/service{index}"
        super().__init__(bus, self.path)
        self.uuid = uuid
        self.chars = []

    def props(self):
        return {"UUID": self.uuid, "Primary": dbus.Boolean(True)}


class GattChar(BlePropsObject):
    IFACE = "org.bluez.GattCharacteristic1"

    def __init__(self, bus, service, index, uuid, flags, link):
        self.path = f"{service.path}/char{index}"
        super().__init__(bus, self.path)
        self.service, self.uuid, self.flags, self.link = service, uuid, flags, link
        self.value = b""
        self.notifying = False

    def props(self):
        return {"Service": dbus.ObjectPath(self.service.path), "UUID": self.uuid,
                "Flags": dbus.Array(self.flags, signature="s"),
                "Value": dbus.Array(self.value, signature="y")}

    @dbus.service.method("org.bluez.GattCharacteristic1", in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return dbus.Array(self.value, signature="y")

    @dbus.service.method("org.bluez.GattCharacteristic1", in_signature="aya{sv}", out_signature="")
    def WriteValue(self, value, options):
        self.link.received(bytes(value), options)

    @dbus.service.method("org.bluez.GattCharacteristic1", in_signature="", out_signature="")
    def StartNotify(self):
        if not self.notifying:
            self.notifying = True
            self.link.subscribed(self)

    @dbus.service.method("org.bluez.GattCharacteristic1", in_signature="", out_signature="")
    def StopNotify(self):
        if self.notifying:
            self.notifying = False
            self.link.unsubscribed(self)

    def notify(self, chunk):
        self.value = chunk
        self.PropertiesChanged(self.IFACE, {"Value": dbus.Array(chunk, signature="y")}, [])


class GattApplication(dbus.service.Object):
    def __init__(self, bus, link):
        super().__init__(bus, GATT_APP_PATH)
        self.services = []
        for i, (suuid, chars) in enumerate(ELM_BLE_SERVICES):
            svc = GattService(bus, i, suuid)
            svc.chars = [GattChar(bus, svc, j, cuuid, flags, link) for j, (cuuid, flags) in enumerate(chars)]
            self.services.append(svc)

    @dbus.service.method("org.freedesktop.DBus.ObjectManager", out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        objs = {}
        for svc in self.services:
            objs[dbus.ObjectPath(svc.path)] = {svc.IFACE: svc.props()}
            for ch in svc.chars:
                objs[dbus.ObjectPath(ch.path)] = {ch.IFACE: ch.props()}
        return objs


class Advertisement(BlePropsObject):
    IFACE = "org.bluez.LEAdvertisement1"

    def __init__(self, bus, name):
        super().__init__(bus, ADVERT_PATH)
        self.name = name

    def props(self):
        return {"Type": "peripheral",
                "ServiceUUIDs": dbus.Array(ADVERTISED_UUIDS, signature="s"),
                "LocalName": self.name,
                "Discoverable": dbus.Boolean(True)}

    @dbus.service.method("org.bluez.LEAdvertisement1", in_signature="", out_signature="")
    def Release(self):
        log("BLE advertisement released by BlueZ")


class BleLink:
    """Moves bytes between the GATT characteristics and the emulator."""

    def __init__(self, bus, emulator):
        self.bus, self.emu = bus, emulator
        self.subscribers = []
        self.payload = 20       # notification size: ATT MTU - 3, updated from the client's writes
        self.device = None

    def received(self, data, options):
        mtu = int(options.get("mtu", 0))
        if mtu > 3:
            self.payload = min(mtu - 3, 512)
        if "device" in options and options["device"] != self.device:
            self.device = options["device"]
            log(f"BLE client: {device_name(self.bus, self.device)}")
        self.emu.write(data)

    def subscribed(self, char):
        if not self.subscribers:
            log("BLE connected")
        self.subscribers.append(char)

    def unsubscribed(self, char):
        if char in self.subscribers:
            self.subscribers.remove(char)
        if not self.subscribers:
            log("BLE disconnected")
            self.device = None
            self.payload = 20
            self.emu.write(b"\r")   # ends an ATMA stream left running by the client

    def send(self, data):
        for char in self.subscribers:
            for i in range(0, len(data), self.payload):
                char.notify(data[i:i + self.payload])


class Emulator:
    """obd_emulator.py on a raw pty; restarted automatically if it exits."""

    def __init__(self, python, args):
        self.python, self.args = python, args
        self.proc = None
        self.master = None
        self.slave = None
        self.on_output = lambda data: None
        self.watch = None

    def start(self):
        master, slave = pty.openpty()
        tty.setraw(slave)
        os.set_blocking(master, False)
        self.master = master
        port = os.ttyname(slave)
        self.proc = subprocess.Popen([self.python, os.path.join(HERE, "obd_emulator.py"), "-p", port, *self.args],
                                     cwd=HERE)
        self.slave = slave  # kept open so the master never sees a hang-up before/while the emulator opens it
        self.watch = GLib.io_add_watch(master, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._read)
        log(f"emulator started (pid {self.proc.pid}) on {port}")

    def _read(self, fd, cond):
        try:
            data = os.read(fd, 65536)
        except BlockingIOError:
            return True
        except OSError:
            return True
        if data:
            self.on_output(data)
        return True

    def write(self, data):
        try:
            os.write(self.master, data)
        except (BlockingIOError, OSError):
            pass

    def check_alive(self):
        if self.proc and self.proc.poll() is not None:
            log(f"emulator exited with code {self.proc.returncode}, restarting")
            self.close()
            time.sleep(1)
            self.start()
        return True

    def close(self):
        if self.watch:
            GLib.source_remove(self.watch)
            self.watch = None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for fd in (self.master, self.slave):
            if fd is not None:
                os.close(fd)
        self.master = self.slave = None


def find_adapter(bus):
    om = dbus.Interface(bus.get_object(BUS, "/"), "org.freedesktop.DBus.ObjectManager")
    for path, ifaces in om.GetManagedObjects().items():
        if "org.bluez.Adapter1" in ifaces:
            return path
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="OBDII", help="Bluetooth name shown to phones (default: %(default)s)")
    ap.add_argument("--python", default=sys.executable, help="Python that runs obd_emulator.py (needs pyserial)")
    ap.add_argument("emulator_args", nargs="*", help="extra obd_emulator.py options, after --")
    opts = ap.parse_args()

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus)
    if not adapter:
        sys.exit("No Bluetooth adapter found. Is the bluetooth service running and the adapter unblocked (rfkill)?")
    props = dbus.Interface(bus.get_object(BUS, adapter), "org.freedesktop.DBus.Properties")
    get = lambda k: props.Get("org.bluez.Adapter1", k)
    put = lambda k, v: props.Set("org.bluez.Adapter1", k, v)
    saved = {k: get(k) for k in ("Discoverable", "Pairable", "DiscoverableTimeout", "PairableTimeout")}

    put("Powered", dbus.Boolean(True))
    put("Alias", opts.name)
    put("DiscoverableTimeout", dbus.UInt32(0))
    put("PairableTimeout", dbus.UInt32(0))
    put("Discoverable", dbus.Boolean(True))
    put("Pairable", dbus.Boolean(True))
    log(f"adapter {get('Address')} '{opts.name}' powered, discoverable and pairable")

    agent = Agent(bus)
    agent_mgr = dbus.Interface(bus.get_object(BUS, "/org/bluez"), "org.bluez.AgentManager1")
    agent_mgr.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    agent_mgr.RequestDefaultAgent(AGENT_PATH)

    emu = Emulator(opts.python, opts.emulator_args)
    profile = SerialProfile(bus, emu)
    ble = BleLink(bus, emu)

    def fan_out(data):  # SPP and BLE clients both see the emulator's output
        profile.send(data)
        ble.send(data)
    emu.on_output = fan_out
    emu.start()

    profile_mgr = dbus.Interface(bus.get_object(BUS, "/org/bluez"), "org.bluez.ProfileManager1")
    profile_mgr.RegisterProfile(PROFILE_PATH, SPP_UUID, {
        "Name": opts.name,
        "Role": "server",
        "Channel": dbus.UInt16(1),
        "RequireAuthentication": dbus.Boolean(False),
        "RequireAuthorization": dbus.Boolean(False),
        "AutoConnect": dbus.Boolean(True),
    })
    log(f"Classic SPP ready on RFCOMM channel 1 (Android: pair with '{opts.name}')")

    gatt_app = GattApplication(bus, ble)
    advert = Advertisement(bus, opts.name)
    gatt_mgr = dbus.Interface(bus.get_object(BUS, adapter), "org.bluez.GattManager1")
    adv_mgr = dbus.Interface(bus.get_object(BUS, adapter), "org.bluez.LEAdvertisingManager1")
    ble_ok = set()

    # Async: BlueZ calls back into this process (GetManagedObjects/GetAll) while registering
    def ble_failed(what):
        return lambda e: log(f"BLE {what} failed ({e.get_dbus_message()}); Classic SPP still works")

    def gatt_registered():
        ble_ok.add("gatt")
        adv_mgr.RegisterAdvertisement(ADVERT_PATH, {}, reply_handler=advert_registered,
                                      error_handler=ble_failed("advertising"))

    def advert_registered():
        ble_ok.add("advert")
        log(f"BLE ready, advertising '{opts.name}' (iPhone: connect from the OBD app, not from Settings)")

    gatt_mgr.RegisterApplication(GATT_APP_PATH, {}, reply_handler=gatt_registered,
                                 error_handler=ble_failed("GATT server"))
    log("waiting for connections (Ctrl+C to stop)")

    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(2, emu.check_alive)
    try:
        from gi.repository import GLibUnix
        signal_add = GLibUnix.signal_add
    except ImportError:
        signal_add = GLib.unix_signal_add
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal_add(GLib.PRIORITY_HIGH, sig, loop.quit)
    try:
        loop.run()
    finally:
        log("shutting down")
        profile.drop_client()
        ble_undo = ((lambda: adv_mgr.UnregisterAdvertisement(ADVERT_PATH)) if "advert" in ble_ok else None,
                    (lambda: gatt_mgr.UnregisterApplication(GATT_APP_PATH)) if "gatt" in ble_ok else None)
        ble_undo = [u for u in ble_undo if u]
        for undo in (*ble_undo,
                     lambda: profile_mgr.UnregisterProfile(PROFILE_PATH),
                     lambda: agent_mgr.UnregisterAgent(AGENT_PATH),
                     *(lambda k=k, v=v: put(k, v) for k, v in saved.items())):
            try:
                undo()
            except dbus.DBusException:
                pass
        emu.close()


if __name__ == "__main__":
    main()
