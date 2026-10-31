from datetime import datetime

from elm327.hex_format import clamp_to_byte, to_word
from elm327.vehicle.idle_car import wobble
from elm327.vehicle.pids import TEMPERATURE_OFFSET, Pid

WHEEL_STANDSTILL_RAW = 6767
WHEEL_COUNT = 4
TYRE_PRESSURES_PSI = (33.1, 32.8, 31.9, 32.2)
TYRE_TEMPS_C = (22, 22, 21, 21)
PSI_TO_KPA = 6.895
KPA_PER_BIT = 2.75
ODOMETER_84317_KM = [0x01, 0x49, 0x5D]
TRIP_A_RAW = 1234
STEERING_TRIM_RAW = -23
SET_TEMP_22_C_RAW = 44
FAN_SPEED = 2
TORQUE_OFFSET = 125
STOICHIOMETRIC_RATIO = 14.7
IDLE_RPM = 745
SECONDS_PER_HOUR = 3600.0
YEAR_BASE = 2000
PARK_GEAR = ord("P")
MIL_LAMP = 0x01
PARKING_BRAKE_LAMP = 0x40
GAUGE_NORMAL_POSITION = 128
GAUGE_NORMAL_RANGE = (75, 105)
EVAPORATOR_COLD_C = 6
EVAPORATOR_WARM_C = 27
CABIN_TEMP_C = 26.5
PAYLOAD_SIZE = 6


def crc8(data):
    crc = 0xFF
    for value in data:
        crc ^= value
        for _ in range(8):
            shifted = (crc << 1) & 0xFF
            crc = shifted ^ 0x1D if crc & 0x80 else shifted
    return crc ^ 0xFF


def with_counter_and_crc(payload, counter):
    frame = list(payload[:PAYLOAD_SIZE]) + [counter & 0x0F]
    return frame + [crc8(frame)]


def _temperature_byte(celsius):
    return clamp_to_byte(celsius + TEMPERATURE_OFFSET)


class IdleFrameBuilder:
    def __init__(self, car, encoder, trouble_codes):
        self._car = car
        self._encoder = encoder
        self._trouble_codes = trouble_codes

    def _pid(self, pid, sample):
        return self._encoder.encode(pid, sample)

    def engine_status(self, sample, counter):
        flags = 0x03
        if sample.air_conditioning > 0.05:
            flags |= 0x04
        if sample.air_conditioning > 0.5:
            flags |= 0x08
        if self._trouble_codes.check_engine_light_on:
            flags |= 0x10
        coolant = self._pid(Pid.COOLANT_TEMP, sample)[0]
        torque = clamp_to_byte(sample.torque + TORQUE_OFFSET)
        payload = self._pid(Pid.ENGINE_RPM, sample) + [0, coolant, torque, flags]
        return with_counter_and_crc(payload, counter)

    def wheel_speeds(self, sample, counter):
        return to_word(WHEEL_STANDSTILL_RAW) * WHEEL_COUNT

    def brakes_and_yaw(self, sample, counter):
        yaw = 32768 + int(wobble(self._car.elapsed(), 3, 21))
        return with_counter_and_crc(to_word(0) + [0, 0x00] + to_word(yaw), counter)

    def steering(self, sample, counter):
        angle = to_word(STEERING_TRIM_RAW & 0xFFFF)
        return with_counter_and_crc(angle + to_word(0) + [0x01, 0x00], counter)

    def transmission(self, sample, counter):
        temperature = _temperature_byte(sample.transmission)
        payload = [PARK_GEAR, 0, temperature] + to_word(0) + [0]
        return with_counter_and_crc(payload, counter)

    def engine_air_and_fuel(self, sample, counter):
        pids = (
            Pid.MANIFOLD_PRESSURE,
            Pid.MASS_AIR_FLOW,
            Pid.INTAKE_AIR_TEMP,
            Pid.THROTTLE,
            Pid.SHORT_TERM_TRIM,
            Pid.LONG_TERM_TRIM,
            Pid.TIMING_ADVANCE,
        )
        return sum((self._pid(pid, sample) for pid in pids), [])

    def engine_ambient(self, sample, counter):
        pids = (
            Pid.BAROMETRIC_PRESSURE,
            Pid.ENGINE_LOAD,
            Pid.OIL_TEMP,
            Pid.MODULE_VOLTAGE,
            Pid.FUEL_PRESSURE,
        )
        payload = sum((self._pid(pid, sample) for pid in pids), [])
        return with_counter_and_crc(payload, counter)

    def cluster(self, sample, counter):
        lamps = PARKING_BRAKE_LAMP
        if self._trouble_codes.check_engine_light_on:
            lamps |= MIL_LAMP
        low, high = GAUGE_NORMAL_RANGE
        if low <= sample.coolant <= high:
            gauge = GAUGE_NORMAL_POSITION
        else:
            gauge = _temperature_byte(sample.coolant)
        tacho = clamp_to_byte(sample.rpm / 25)
        outside = _temperature_byte(sample.ambient)
        fuel = self._pid(Pid.FUEL_LEVEL, sample)
        payload = fuel + [gauge, 0, tacho, outside, lamps]
        return with_counter_and_crc(payload, counter)

    def airbag_heartbeat(self, sample, counter):
        return with_counter_and_crc([0x01, 0x01, 0x00, 0x00, 0x00, 0x00], counter)

    def body(self, sample, counter):
        return [0x04, 0x00, 0x40, 0x00, 0x00, 0x1E, 0x00, 0x00]

    def climate(self, sample, counter):
        compressor_on = sample.air_conditioning > 0.5
        evaporator = EVAPORATOR_COLD_C if compressor_on else EVAPORATOR_WARM_C
        return [
            0x04 | int(compressor_on),
            FAN_SPEED,
            SET_TEMP_22_C_RAW,
            _temperature_byte(evaporator),
            _temperature_byte(CABIN_TEMP_C),
            0,
            0,
            0,
        ]

    def tyre_pressures(self, sample, counter):
        raw = [
            clamp_to_byte(psi * PSI_TO_KPA / KPA_PER_BIT) for psi in TYRE_PRESSURES_PSI
        ]
        return raw + [0, 0, 0, 0]

    def tyre_temperatures(self, sample, counter):
        raw = [_temperature_byte(celsius) for celsius in TYRE_TEMPS_C]
        return raw + [0x01, 0, 0, 0]

    def trip_computer(self, sample, counter):
        fuel_per_rev = sample.air_flow / STOICHIOMETRIC_RATIO / IDLE_RPM
        litres_per_hour = fuel_per_rev * SECONDS_PER_HOUR
        return (
            ODOMETER_84317_KM
            + to_word(TRIP_A_RAW)
            + to_word(litres_per_hour * 100)
            + [0]
        )

    def clock(self, sample, counter):
        now = datetime.now()
        return [
            now.hour,
            now.minute,
            now.second,
            now.day,
            now.month,
            now.year - YEAR_BASE,
            _temperature_byte(sample.ambient),
            0,
        ]
