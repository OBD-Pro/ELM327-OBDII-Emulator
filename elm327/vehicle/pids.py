from enum import IntEnum

PERCENT_SCALE = 2.55
TEMPERATURE_OFFSET = 40
RPM_SCALE = 4
TIMING_OFFSET = 64
SUPPORT_RANGE_PIDS = (0x00, 0x20, 0x40)


class Pid(IntEnum):
    MONITOR_STATUS = 0x01
    FREEZE_DTC = 0x02
    FUEL_SYSTEM = 0x03
    ENGINE_LOAD = 0x04
    COOLANT_TEMP = 0x05
    SHORT_TERM_TRIM = 0x06
    LONG_TERM_TRIM = 0x07
    FUEL_PRESSURE = 0x0A
    MANIFOLD_PRESSURE = 0x0B
    ENGINE_RPM = 0x0C
    VEHICLE_SPEED = 0x0D
    TIMING_ADVANCE = 0x0E
    INTAKE_AIR_TEMP = 0x0F
    MASS_AIR_FLOW = 0x10
    THROTTLE = 0x11
    OXYGEN_UPSTREAM = 0x14
    OXYGEN_DOWNSTREAM = 0x15
    OBD_STANDARD = 0x1C
    ENGINE_RUNTIME = 0x1F
    DISTANCE_WITH_MIL = 0x21
    FUEL_LEVEL = 0x2F
    DISTANCE_SINCE_CLEAR = 0x31
    BAROMETRIC_PRESSURE = 0x33
    CATALYST_TEMP = 0x3C
    MODULE_VOLTAGE = 0x42
    AMBIENT_TEMP = 0x46
    COMMANDED_THROTTLE = 0x4C
    OIL_TEMP = 0x52


def support_bitmap(base, supported):
    last_pid = base + 0x20
    bits = 0
    for pid in range(base + 1, last_pid + 1):
        chains_to_next_range = pid == last_pid and any(p > pid for p in supported)
        if pid in supported or chains_to_next_range:
            bits |= 1 << (last_pid - pid)
    return " ".join(f"{(bits >> shift) & 0xFF:02X}" for shift in (24, 16, 8, 0))
