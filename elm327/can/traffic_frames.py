from dataclasses import astuple

from elm327.can.traffic_state import CORNERS
from elm327.hex_format import split_word
from elm327.vehicle.pids import TEMPERATURE_OFFSET

FRAME_SIZE = 8
DOOR_NAMES = ("fl", "fr", "rl", "rr", "trunk")


def _limit(value, low, high):
    return max(low, min(high, value))


def _bit_flags(flags):
    return sum(1 << position for position, flag in enumerate(flags) if flag)


def rpm_frame(state):
    return split_word(_limit(state.rpm // 4, 0, 65535))


def pedal_frame(state):
    return [int(_limit(state.pedal, 0, 100) * 2.55)]


def speed_frame(state):
    return [int(_limit(state.speed, 0, 255))]


def brake_frame(state):
    return [0x01 if state.brake_on else 0x00, int(state.brake_pressure)]


def lights_frame(state):
    return [_bit_flags(astuple(state.lights))]


def radio_frame(state):
    radio = state.radio
    return [radio.source & 0xFF, radio.volume & 0xFF, radio.button & 0xFF]


def steering_angle_frame(state):
    tenths = int(_limit(state.steering_angle, -540.0, 540.0) * 10)
    return split_word(tenths & 0xFFFF)


def steering_rate_frame(state):
    tenths = int(_limit(state.steering_rate, -2047.0, 2047.0) * 10)
    return split_word(tenths & 0xFFFF)


def gear_frame(state):
    return [state.gear & 0x0F]


def wheels_frame(state):
    frame = []
    for corner in CORNERS:
        frame += split_word(int(_limit(state.wheel_speeds[corner] * 10, 0, 6553)))
    return frame


def doors_frame(state):
    return [_bit_flags(state.doors[name] for name in DOOR_NAMES)]


def climate_frame(state):
    climate = state.climate
    ac_flag = 0x01 if climate.air_conditioning else 0x00
    return [ac_flag, climate.fan & 0x07, _limit(climate.set_temp, 16, 30)]


def tyre_pressure_frame(state):
    pressures = (state.tyre_pressures[corner] for corner in CORNERS)
    return [_limit(int(psi * 2), 0, 255) & 0xFF for psi in pressures]


def tyre_temperature_frame(state):
    temperatures = (state.tyre_temps[corner] for corner in CORNERS)
    raw = (int(celsius + TEMPERATURE_OFFSET) for celsius in temperatures)
    return [_limit(value, 0, 255) & 0xFF for value in raw]


FRAME_BUILDERS = {
    0x0C8: rpm_frame,
    0x0C9: pedal_frame,
    0x0AA: speed_frame,
    0x224: brake_frame,
    0x1A6: lights_frame,
    0x2F1: radio_frame,
    0x0A5: steering_angle_frame,
    0x1B0: gear_frame,
    0x1F2: doors_frame,
    0x2C1: climate_frame,
    0x0A6: steering_rate_frame,
    0x1C3: wheels_frame,
    0x2F2: tyre_pressure_frame,
    0x2F3: tyre_temperature_frame,
}


def build_frame(can_id, state):
    data = list(FRAME_BUILDERS[can_id](state))
    padding = [0] * FRAME_SIZE
    return can_id, (data + padding)[:FRAME_SIZE]
