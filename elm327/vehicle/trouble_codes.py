import argparse
from dataclasses import dataclass, field

from elm327.hex_format import hex_string, to_byte, to_fuel_trim, to_word
from elm327.vehicle.pids import (
    PERCENT_SCALE,
    RPM_SCALE,
    TEMPERATURE_OFFSET,
    TIMING_OFFSET,
    Pid,
)

DEFAULT_STORED_CODES = ["P0420", "P0442", "P0133"]
DEFAULT_PENDING_CODES = ["P0300"]
DEFAULT_PERMANENT_CODES = ["P0420"]

CODE_DESCRIPTIONS = {
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0442": "Evaporative Emission System Leak Detected (Small Leak)",
    "P0133": "O2 Sensor Circuit Slow Response (Bank 1 Sensor 1)",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
}

CODE_LETTERS = "PCBU"
CLOSED_LOOP = 0x02
MIL_ON_FLAG = 0x80
MAX_REPORTED_CODES = 0x7F
ALL_MONITORS_COMPLETE = "07 65 00"


@dataclass(frozen=True)
class FreezeConditions:
    load: float
    coolant: float
    short_trim: float
    long_trim: float
    manifold_pressure: float
    rpm: float
    speed: float
    timing: float
    intake_temp: float
    air_flow: float
    throttle: float
    fuel_level: float


DEFAULT_CONDITIONS = FreezeConditions(
    load=35,
    coolant=90,
    short_trim=0.8,
    long_trim=2.3,
    manifold_pressure=50,
    rpm=2000,
    speed=60,
    timing=22.0,
    intake_temp=27,
    air_flow=13.5,
    throttle=20,
    fuel_level=62,
)

CONDITIONS_BY_CODE = {
    "P0420": FreezeConditions(
        load=38,
        coolant=92,
        short_trim=1.6,
        long_trim=3.1,
        manifold_pressure=52,
        rpm=2150,
        speed=63,
        timing=24.5,
        intake_temp=28,
        air_flow=14.8,
        throttle=21,
        fuel_level=64,
    ),
    "P0442": FreezeConditions(
        load=24,
        coolant=71,
        short_trim=-0.8,
        long_trim=1.6,
        manifold_pressure=32,
        rpm=760,
        speed=0,
        timing=7.0,
        intake_temp=22,
        air_flow=3.1,
        throttle=15,
        fuel_level=58,
    ),
    "P0133": FreezeConditions(
        load=31,
        coolant=89,
        short_trim=-2.3,
        long_trim=3.1,
        manifold_pressure=45,
        rpm=1850,
        speed=72,
        timing=27.0,
        intake_temp=30,
        air_flow=11.6,
        throttle=18,
        fuel_level=61,
    ),
    "P0300": FreezeConditions(
        load=72,
        coolant=90,
        short_trim=8.6,
        long_trim=3.9,
        manifold_pressure=86,
        rpm=2620,
        speed=48,
        timing=12.5,
        intake_temp=33,
        air_flow=31.4,
        throttle=44,
        fuel_level=60,
    ),
}


def code_to_bytes(code):
    code = code.strip().upper()
    letter = CODE_LETTERS.index(code[0]) << 6
    first_byte = letter | (int(code[1]) << 4) | int(code[2], 16)
    return [first_byte, int(code[3:5], 16)]


def parse_code_list(text):
    codes = [part.strip().upper() for part in text.split(",") if part.strip()]
    for code in codes:
        if not _has_valid_shape(code):
            raise argparse.ArgumentTypeError(
                f"invalid DTC '{code}' (expected e.g. P0420, U0100)"
            )
        int(code[2:], 16)
    return codes


def _has_valid_shape(code):
    return len(code) == 5 and code[0] in CODE_LETTERS and code[1] in "0123"


def build_freeze_frame(code):
    conditions = CONDITIONS_BY_CODE.get(code, DEFAULT_CONDITIONS)
    payloads = {
        Pid.FREEZE_DTC: code_to_bytes(code),
        Pid.FUEL_SYSTEM: [CLOSED_LOOP, 0x00],
        Pid.ENGINE_LOAD: to_byte(conditions.load * PERCENT_SCALE),
        Pid.COOLANT_TEMP: to_byte(conditions.coolant + TEMPERATURE_OFFSET),
        Pid.SHORT_TERM_TRIM: to_fuel_trim(conditions.short_trim),
        Pid.LONG_TERM_TRIM: to_fuel_trim(conditions.long_trim),
        Pid.MANIFOLD_PRESSURE: to_byte(conditions.manifold_pressure),
        Pid.ENGINE_RPM: to_word(conditions.rpm * RPM_SCALE),
        Pid.VEHICLE_SPEED: to_byte(conditions.speed),
        Pid.TIMING_ADVANCE: to_byte((conditions.timing + TIMING_OFFSET) * 2),
        Pid.INTAKE_AIR_TEMP: to_byte(conditions.intake_temp + TEMPERATURE_OFFSET),
        Pid.MASS_AIR_FLOW: to_word(conditions.air_flow * 100),
        Pid.THROTTLE: to_byte(conditions.throttle * PERCENT_SCALE),
        Pid.FUEL_LEVEL: to_byte(conditions.fuel_level * PERCENT_SCALE),
    }
    return {int(pid): hex_string(payload) for pid, payload in payloads.items()}


@dataclass
class TroubleCodes:
    stored: list = field(default_factory=lambda: list(DEFAULT_STORED_CODES))
    pending: list = field(default_factory=lambda: list(DEFAULT_PENDING_CODES))
    permanent: list = field(default_factory=lambda: list(DEFAULT_PERMANENT_CODES))
    freeze_frames: list = field(default_factory=list)

    def __post_init__(self):
        codes_with_frames = self.stored + self.pending
        self.freeze_frames = [build_freeze_frame(code) for code in codes_with_frames]

    @property
    def check_engine_light_on(self):
        return bool(self.stored)

    def clear(self):
        self.stored = []
        self.pending = []
        self.freeze_frames = []

    def monitor_status(self):
        count = len(self.stored)
        light = MIL_ON_FLAG if count else 0x00
        first_byte = light | min(count, MAX_REPORTED_CODES)
        return f"{first_byte:02X} {ALL_MONITORS_COMPLETE}"
