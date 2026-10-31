from elm327.can.idle_bus import IdleCanBus
from elm327.can.idle_frames import IdleFrameBuilder
from elm327.hex_format import hex_string
from elm327.vehicle.base import Vehicle
from elm327.vehicle.idle_car import IdleCar
from elm327.vehicle.idle_pid_encoder import IdlePidEncoder
from elm327.vehicle.pids import SUPPORT_RANGE_PIDS, Pid, support_bitmap


class IdleVehicle(Vehicle):
    mode = "idle"

    def __init__(self, trouble_codes, started_at=None):
        super().__init__(trouble_codes)
        self.car = IdleCar(started_at)
        self.encoder = IdlePidEncoder(trouble_codes)

    def read_mode01(self, command):
        if len(command) != 4 or not command.startswith("01"):
            return None
        try:
            pid = int(command[2:], 16)
        except ValueError:
            return None

        if pid in SUPPORT_RANGE_PIDS:
            bitmap = support_bitmap(pid, self.encoder.supported_pids)
            return f"41 {pid:02X} {bitmap}"
        if pid == Pid.MONITOR_STATUS:
            return f"41 {pid:02X} {self.trouble_codes.monitor_status()}"
        if self.encoder.supports(pid):
            payload = self.encoder.encode(pid, self.car.sample())
            return f"41 {pid:02X} {hex_string(payload)}"
        return None

    def battery_voltage(self):
        return f"{self.car.sample().voltage:.1f}V"

    def open_can_source(self, now):
        builder = IdleFrameBuilder(self.car, self.encoder, self.trouble_codes)
        return IdleCanBus(now, self.car, builder)
