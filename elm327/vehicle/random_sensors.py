import math
import random

UPSTREAM_SENSORS = (1, 2)
SENSOR_NUMBER_BY_PID = {
    0x14: 1,
    0x15: 2,
    0x16: 1,
    0x17: 2,
    0x18: 3,
    0x19: 4,
    0x1A: 3,
    0x1B: 4,
}


def _hex_pair(value):
    return f"{(value // 256) & 0xFF:02X} {value & 0xFF:02X}"


def _percent_byte(percent):
    return f"{int(percent * 255 / 100) & 0xFF:02X}"


class RandomSensors:
    def __init__(self):
        self.traffic = None

    def coolant_temp(self):
        return format(40 + random.randint(0, 60), "x")

    def short_term_trim(self):
        return format(128 + random.randint(-25, 25), "x")

    def long_term_trim(self):
        return format(128 + random.randint(-15, 15), "x")

    def manifold_pressure_legacy(self):
        return format(random.randint(20, 100), "x")

    def engine_load(self):
        if self.traffic is None:
            return _percent_byte(random.randint(0, 100))
        pedal_part = self.traffic.pedal * 0.75
        rpm_part = (self.traffic.rpm / 5000.0) * 25.0
        percent = pedal_part + rpm_part + random.uniform(-3.0, 3.0)
        return _percent_byte(int(max(0, min(100, percent))))

    def fuel_pressure(self):
        return f"{random.randint(20, 100):02X}"

    def engine_rpm(self):
        return _hex_pair(random.randint(700, 3500))

    def vehicle_speed(self):
        return f"{random.randint(0, 120):02X}"

    def throttle_position(self):
        return f"{random.randint(5, 80):02X}"

    def manifold_pressure(self):
        return f"{random.randint(20, 110):02X}"

    def intake_air_temp(self):
        return f"{40 + random.randint(-10, 40):02X}"

    def mass_air_flow(self):
        return _hex_pair(int(random.uniform(2.0, 60.0) * 100))

    def fuel_level(self):
        return _percent_byte(random.uniform(5.0, 95.0))

    def barometric_pressure(self):
        return f"{random.randint(80, 105):02X}"

    def module_voltage(self):
        return _hex_pair(int(random.uniform(12.0, 14.8) * 1000))

    def commanded_throttle(self):
        return f"{random.randint(0, 100):02X}"

    def ambient_temp(self):
        return f"{40 + random.randint(-15, 35):02X}"

    def oil_temp(self):
        return f"{40 + random.randint(-10, 60):02X}"

    def oxygen_sensor(self, pid):
        sensor = SENSOR_NUMBER_BY_PID.get(pid, 1)
        if self.traffic is None:
            volts = random.uniform(0.05, 0.90)
            trim = random.uniform(-20.0, 20.0)
        else:
            richness = self._mixture_richness()
            volts = self._oxygen_volts(sensor, richness)
            trim = self._trim_against(richness)

        voltage_byte = max(0, min(255, int(volts * 200)))
        trim_byte = max(0, min(255, int(128 + trim * 1.28)))
        return f"{voltage_byte:02X} {trim_byte:02X}"

    def _mixture_richness(self):
        load_factor = (self.traffic.pedal / 100.0) - 0.25
        rpm_factor = (self.traffic.rpm - 2000.0) / 3000.0
        return 0.5 * load_factor + 0.2 * rpm_factor + random.uniform(-0.05, 0.05)

    def _oxygen_volts(self, sensor, richness):
        if sensor in UPSTREAM_SENSORS:
            position = (self.traffic.tick + sensor * 7) % 40
            swing = math.sin(2 * math.pi * position / 40.0)
            base = 0.45 + 0.35 * richness + 0.20 * swing
            return max(0.05, min(0.95, base + random.uniform(-0.03, 0.03)))
        base = 0.78 + 0.10 * richness
        return max(0.50, min(0.95, base + random.uniform(-0.02, 0.02)))

    def _trim_against(self, richness):
        trim = -richness * 50.0 + random.uniform(-2.0, 2.0)
        return max(-25.0, min(25.0, trim))

    def wideband_oxygen(self):
        ratio = int(random.uniform(0.95, 1.05) * 32768)
        current = int((random.uniform(-1.5, 1.5) + 1.275) * 1000)
        return f"{_hex_pair(ratio)} {_hex_pair(current)}"

    def catalyst_temp(self):
        return _hex_pair(int(random.uniform(300.0, 750.0) * 10))
