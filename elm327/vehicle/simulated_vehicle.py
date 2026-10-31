from elm327.can.traffic_simulator import TrafficSimulator
from elm327.can.traffic_stream import TrafficStream
from elm327.vehicle.base import Vehicle
from elm327.vehicle.random_sensors import RandomSensors

BATTERY_VOLTAGE = "13.2V"

SUPPORTED_PID_REPLIES = {
    "0100": "41 00 BF 3E A8 13",
    "0120": "41 20 80 00 00 00",
    "0140": "41 40 94 00 10 00",
}

OXYGEN_COMMANDS = {f"01{pid:02X}" for pid in range(0x14, 0x1C)}
WIDEBAND_COMMANDS = {f"01{pid:02X}" for pid in range(0x24, 0x2C)}
CATALYST_COMMANDS = {"013C", "013D", "013E", "013F"}


class SimulatedVehicle(Vehicle):
    def __init__(self, mode, trouble_codes):
        super().__init__(trouble_codes)
        self.mode = mode
        self.sensors = RandomSensors()
        self.simulator = None
        self._readers = self._build_readers()

    def _build_readers(self):
        sensors = self.sensors
        return {
            "010C": sensors.engine_rpm,
            "010D": sensors.vehicle_speed,
            "0104": sensors.engine_load,
            "0111": sensors.throttle_position,
            "0105": sensors.coolant_temp,
            "0106": sensors.short_term_trim,
            "0107": sensors.long_term_trim,
            "0108": sensors.manifold_pressure_legacy,
            "010A": sensors.fuel_pressure,
            "010B": sensors.manifold_pressure,
            "010F": sensors.intake_air_temp,
            "0110": sensors.mass_air_flow,
            "012F": sensors.fuel_level,
            "0133": sensors.barometric_pressure,
            "0142": sensors.module_voltage,
            "014C": sensors.commanded_throttle,
            "0146": sensors.ambient_temp,
            "0152": sensors.oil_temp,
        }

    def read_mode01(self, command):
        if command in SUPPORTED_PID_REPLIES:
            return SUPPORTED_PID_REPLIES[command]
        if command == "0101":
            return f"41 01 {self.trouble_codes.monitor_status()}"

        value = self._read_sensor(command)
        return None if value is None else f"41 {command[2:]} {value}"

    def _read_sensor(self, command):
        if command in self._readers:
            return self._readers[command]()
        if command in OXYGEN_COMMANDS:
            return self.sensors.oxygen_sensor(int(command[2:], 16))
        if command in WIDEBAND_COMMANDS:
            return self.sensors.wideband_oxygen()
        if command in CATALYST_COMMANDS:
            return self.sensors.catalyst_temp()
        return None

    def battery_voltage(self):
        return BATTERY_VOLTAGE

    def open_can_source(self, now):
        if self.simulator is None:
            self.simulator = TrafficSimulator(self.mode)
            self.sensors.traffic = self.simulator.state
        return TrafficStream(self.simulator)
