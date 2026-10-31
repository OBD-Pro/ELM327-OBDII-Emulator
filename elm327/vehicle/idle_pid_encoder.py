from elm327.hex_format import to_byte, to_fuel_trim, to_word
from elm327.vehicle.pids import (
    PERCENT_SCALE,
    RPM_SCALE,
    TEMPERATURE_OFFSET,
    TIMING_OFFSET,
    Pid,
)

PARKED_SPEED = 0
EOBD_STANDARD = 0x06
TRIM_NOT_USED = 0xFF
KM_WITH_LIGHT_ON = 142
KM_SINCE_CLEAR = 1873
FUEL_PRESSURE_STEP = 3
OXYGEN_VOLTS_SCALE = 200


class IdlePidEncoder:
    def __init__(self, trouble_codes):
        self._trouble_codes = trouble_codes
        self._encoders = {
            Pid.ENGINE_LOAD: self._engine_load,
            Pid.COOLANT_TEMP: self._coolant,
            Pid.SHORT_TERM_TRIM: self._short_trim,
            Pid.LONG_TERM_TRIM: self._long_trim,
            Pid.FUEL_PRESSURE: self._fuel_pressure,
            Pid.MANIFOLD_PRESSURE: self._manifold_pressure,
            Pid.ENGINE_RPM: self._rpm,
            Pid.VEHICLE_SPEED: self._speed,
            Pid.TIMING_ADVANCE: self._timing,
            Pid.INTAKE_AIR_TEMP: self._intake_air,
            Pid.MASS_AIR_FLOW: self._air_flow,
            Pid.THROTTLE: self._throttle,
            Pid.OXYGEN_UPSTREAM: self._oxygen_upstream,
            Pid.OXYGEN_DOWNSTREAM: self._oxygen_downstream,
            Pid.OBD_STANDARD: self._obd_standard,
            Pid.ENGINE_RUNTIME: self._runtime,
            Pid.DISTANCE_WITH_MIL: self._distance_with_light,
            Pid.FUEL_LEVEL: self._fuel_level,
            Pid.DISTANCE_SINCE_CLEAR: self._distance_since_clear,
            Pid.BAROMETRIC_PRESSURE: self._barometric_pressure,
            Pid.CATALYST_TEMP: self._catalyst,
            Pid.MODULE_VOLTAGE: self._voltage,
            Pid.AMBIENT_TEMP: self._ambient,
            Pid.COMMANDED_THROTTLE: self._commanded_throttle,
            Pid.OIL_TEMP: self._oil,
        }

    @property
    def supported_pids(self):
        return {int(Pid.MONITOR_STATUS)} | {int(pid) for pid in self._encoders}

    def supports(self, pid):
        return pid in self._encoders

    def encode(self, pid, sample):
        return self._encoders[pid](sample)

    def _engine_load(self, sample):
        return to_byte(sample.load * PERCENT_SCALE)

    def _coolant(self, sample):
        return to_byte(sample.coolant + TEMPERATURE_OFFSET)

    def _short_trim(self, sample):
        return to_fuel_trim(sample.short_trim)

    def _long_trim(self, sample):
        return to_fuel_trim(sample.long_trim)

    def _fuel_pressure(self, sample):
        return to_byte(sample.fuel_pressure / FUEL_PRESSURE_STEP)

    def _manifold_pressure(self, sample):
        return to_byte(sample.manifold_pressure)

    def _rpm(self, sample):
        return to_word(sample.rpm * RPM_SCALE)

    def _speed(self, sample):
        return [PARKED_SPEED]

    def _timing(self, sample):
        return to_byte((sample.timing + TIMING_OFFSET) * 2)

    def _intake_air(self, sample):
        return to_byte(sample.intake_air + TEMPERATURE_OFFSET)

    def _air_flow(self, sample):
        return to_word(sample.air_flow * 100)

    def _throttle(self, sample):
        return to_byte(sample.throttle * PERCENT_SCALE)

    def _oxygen_upstream(self, sample):
        voltage = to_byte(sample.oxygen_upstream * OXYGEN_VOLTS_SCALE)
        return voltage + to_fuel_trim(sample.short_trim)

    def _oxygen_downstream(self, sample):
        voltage = to_byte(sample.oxygen_downstream * OXYGEN_VOLTS_SCALE)
        return voltage + [TRIM_NOT_USED]

    def _obd_standard(self, sample):
        return [EOBD_STANDARD]

    def _runtime(self, sample):
        return to_word(sample.runtime)

    def _distance_with_light(self, sample):
        light_on = self._trouble_codes.check_engine_light_on
        return to_word(KM_WITH_LIGHT_ON if light_on else 0)

    def _fuel_level(self, sample):
        return to_byte(sample.fuel_level * PERCENT_SCALE)

    def _distance_since_clear(self, sample):
        return to_word(KM_SINCE_CLEAR)

    def _barometric_pressure(self, sample):
        return to_byte(sample.barometric_pressure)

    def _catalyst(self, sample):
        return to_word((sample.catalyst + TEMPERATURE_OFFSET) * 10)

    def _voltage(self, sample):
        return to_word(sample.voltage * 1000)

    def _ambient(self, sample):
        return to_byte(sample.ambient + TEMPERATURE_OFFSET)

    def _commanded_throttle(self, sample):
        return to_byte(sample.commanded_throttle * PERCENT_SCALE)

    def _oil(self, sample):
        return to_byte(sample.oil + TEMPERATURE_OFFSET)
