from elm327.bluetooth.logging_helpers import device_name, log

DEFAULT_PAYLOAD_SIZE = 20
MAX_PAYLOAD_SIZE = 512
ATT_HEADER_SIZE = 3


class BleLink:
    def __init__(self, bus, emulator):
        self.bus = bus
        self.emulator = emulator
        self.subscribers = []
        self.payload_size = DEFAULT_PAYLOAD_SIZE
        self.device = None

    def received(self, data, options):
        mtu = int(options.get("mtu", 0))
        if mtu > ATT_HEADER_SIZE:
            self.payload_size = min(mtu - ATT_HEADER_SIZE, MAX_PAYLOAD_SIZE)
        if "device" in options and options["device"] != self.device:
            self.device = options["device"]
            log(f"BLE client: {device_name(self.bus, self.device)}")
        self.emulator.write(data)

    def subscribed(self, characteristic):
        if not self.subscribers:
            log("BLE connected")
        self.subscribers.append(characteristic)

    def unsubscribed(self, characteristic):
        if characteristic in self.subscribers:
            self.subscribers.remove(characteristic)
        if not self.subscribers:
            log("BLE disconnected")
            self.device = None
            self.payload_size = DEFAULT_PAYLOAD_SIZE
            self.emulator.write(b"\r")

    def send(self, data):
        size = self.payload_size
        for characteristic in self.subscribers:
            for start in range(0, len(data), size):
                characteristic.notify(data[start : start + size])
