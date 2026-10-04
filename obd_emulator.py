import serial
import random
import math
import argparse
import logging
from datetime import datetime
import platform
import time
import sys

def pid_05():  # Coolant Temp
    return hex(40 + random.randint(0, 60))[2:]

def pid_06():  # Long Term Fuel Trim
    return hex(128 + random.randint(-25, 25))[2:]

def pid_07():  # Short Term Fuel Trim
    return hex(128 + random.randint(-15, 15))[2:]

def pid_08():  # Intake Manifold Pressure (legacy placeholder)
    return hex(random.randint(20, 100))[2:]

def pid_04():  # Engine Load
    # Prefer to derive from CAN state when available for more realistic values
    st = globals().get('_EMU_STATE', {})
    can = st.get('can_state') if isinstance(st, dict) else None
    if can:
        acc = float(can.get('acc', 0.0))
        rpm = float(can.get('rpm', 800))
        # rough heuristic: throttle dominates, rpm adds some load contribution
        load_pct = acc * 0.75 + (rpm / 5000.0) * 25.0 + random.uniform(-3.0, 3.0)
        load = int(max(0, min(100, load_pct)))
    else:
        load = random.randint(0, 100)
    A = int(load * 255 / 100) & 0xFF
    return f"{A:02X}"

def pid_0A():  # Fuel Pressure
    return f"{random.randint(20, 100):02X}"

def pid_0C():  # RPM
    rpm = random.randint(700, 3500)
    A = rpm // 256
    B = rpm % 256
    return f"{A:02X} {B:02X}"

def pid_0D():  # Speed
    return f"{random.randint(0, 120):02X}"

def pid_11():  # Throttle position
    return f"{random.randint(5, 80):02X}"

def pid_0B():  # Intake Manifold Absolute Pressure
    return f"{random.randint(20, 110):02X}"

def pid_0F():  # Intake Air Temperature
    # returns A where temp = A - 40
    return f"{(40 + random.randint(-10, 40)):02X}"

def pid_10():  # Mass Air Flow (MAF) sensor
    maf = random.uniform(2.0, 60.0)
    value = int(maf * 100)
    A = (value // 256) & 0xFF
    B = value % 256
    return f"{A:02X} {B:02X}"

def pid_2F():  # Fuel Level Input
    level = random.uniform(5.0, 95.0)
    A = int(level * 255 / 100) & 0xFF
    return f"{A:02X}"

def pid_33():  # Barometric Pressure
    return f"{random.randint(80, 105):02X}"

def pid_42():  # Control Module Voltage
    voltage = random.uniform(12.0, 14.8)
    value = int(voltage * 1000)
    A = (value // 256) & 0xFF
    B = value % 256
    return f"{A:02X} {B:02X}"

def pid_4C():  # Commanded Throttle Actuator
    return f"{random.randint(0, 100):02X}"

def pid_46():  # Ambient Air Temperature
    return f"{(40 + random.randint(-15, 35)):02X}"

def pid_52():  # Engine Oil Temperature
    return f"{(40 + random.randint(-10, 60)):02X}"


def pid_14_1B():
    voltage_v = random.uniform(0.05, 0.90)
    A = max(0, min(255, int(voltage_v * 200)))
    B = random.randint(100, 160)  # Short term fuel trim (%): B = trim - 128
    return f"{A:02X} {B:02X}"

def pid_oxygen_14_1B(pid_num):
    """
    Mode 01 O2 sensor voltage and STFT for PIDs 0x14..0x1B.
    Returns two bytes: A = voltage (V) scaled by 200; B = STFT where percent = (B - 128) / 1.28.
    Uses CAN-derived state when available for more realistic behavior.
    """
    # Map PID to (bank, sensor) semantics (simplified conventional mapping)
    mapping = {
        0x14: (1, 1),  # Bank 1 Sensor 1 (upstream)
        0x15: (1, 2),  # Bank 1 Sensor 2 (upstream)
        0x16: (2, 1),  # Bank 2 Sensor 1 (upstream)
        0x17: (2, 2),  # Bank 2 Sensor 2 (upstream)
        0x18: (1, 3),  # Bank 1 Sensor 3 (downstream)
        0x19: (1, 4),  # Bank 1 Sensor 4 (downstream)
        0x1A: (2, 3),  # Bank 2 Sensor 3 (downstream)
        0x1B: (2, 4),  # Bank 2 Sensor 4 (downstream)
    }
    bank, sensor = mapping.get(pid_num, (1, 1))

    st = globals().get('_EMU_STATE', {})
    can = st.get('can_state') if isinstance(st, dict) else None

    # Default/fallback random behavior if no CAN state is available
    if not can:
        voltage_v = random.uniform(0.05, 0.90)
        trim_pct = random.uniform(-20.0, 20.0)
    else:
        tick = float(can.get('tick', 0))
        acc = float(can.get('acc', 0.0))        # 0..100
        rpm = float(can.get('rpm', 800))        # ~600..5000
        speed = float(can.get('speed', 0.0))

        # Estimate mixture deviation around stoich based on throttle/load
        # Negative -> lean, Positive -> rich
        load_factor = (acc / 100.0) - 0.25  # centered near cruise
        rpm_factor = (rpm - 2000.0) / 3000.0
        mixture_dev = 0.5 * load_factor + 0.2 * rpm_factor + random.uniform(-0.05, 0.05)

        upstream = sensor in (1, 2)
        if upstream:
            # Upstream sensors oscillate around ~0.45 V with richer/leaner swings
            osc = math.sin(2 * math.pi * ((tick + sensor * 7) % 40) / 40.0)
            base = 0.45 + 0.35 * mixture_dev + 0.20 * osc
            voltage_v = max(0.05, min(0.95, base + random.uniform(-0.03, 0.03)))
        else:
            # Downstream sensors are more stable, typically ~0.7-0.85 V
            base = 0.78 + 0.10 * mixture_dev
            voltage_v = max(0.50, min(0.95, base + random.uniform(-0.02, 0.02)))

        # Short-term fuel trim reacts to mixture deviation (opposes it) with small noise
        trim_pct = max(-25.0, min(25.0, (-mixture_dev * 50.0) + random.uniform(-2.0, 2.0)))

    # Encode A and B per OBD scaling
    A = max(0, min(255, int(voltage_v * 200)))
    B = max(0, min(255, int(128 + (trim_pct * 1.28))))
    return f"{A:02X} {B:02X}"

def pid_24_2B():  # O2 Sensor current (CAN) and lambda
    # A,B => equivalent ratio; C,D => current in mA
    eq_ratio = random.uniform(0.95, 1.05)
    eq_val = int(eq_ratio * 32768)  # (256*A + B)/32768
    A = (eq_val // 256) & 0xFF
    B = eq_val & 0xFF
    current_ma = random.uniform(-1.5, 1.5)
    cur_val = int((current_ma + 1.275) * 1000)  # rough map to 0..255*255
    C = (cur_val // 256) & 0xFF
    D = cur_val & 0xFF
    return f"{A:02X} {B:02X} {C:02X} {D:02X}"

def pid_3C_3F():  # Catalyst temperature
    # A,B => temperature (°C) = (256*A + B)/10
    temp_c = random.uniform(300.0, 750.0)
    val = int(temp_c * 10)
    A = (val // 256) & 0xFF
    B = val & 0xFF
    return f"{A:02X} {B:02X}"

# ---------------------------------------------------------------------------
# Warm-idle car model (single source of truth)
#
# Every sensor is a pure function of time, so a Mode 01 answer and the CAN
# frames broadcast at the same instant always agree. PID answers and CAN
# signals are both encoded through _PID_ENC, i.e. the CAN bus carries the same
# raw bytes the ECU would return for the matching OBD-II PID.
# ---------------------------------------------------------------------------
_IDLE_T0 = time.monotonic()

def _T():
    return time.monotonic() - _IDLE_T0

def _wob(t, amp, seed=0.0):
    """Smooth pseudo-noise in [-amp, amp] (sum of incommensurate sines, no RNG)."""
    return amp * (0.35 * math.sin(2 * math.pi * 0.37 * t + seed * 1.7)
                  + 0.30 * math.sin(2 * math.pi * 1.13 * t + seed * 2.9)
                  + 0.20 * math.sin(2 * math.pi * 3.71 * t + seed * 4.1)
                  + 0.15 * math.sin(2 * math.pi * 9.70 * t + seed * 5.3))

def _pulse(t, period, start, dur, ramp=2.0):
    """Trapezoid 0..1: rises at `start`, holds for `dur`, falls; repeats every `period` s."""
    x = (t % period) - start
    if x <= 0 or x >= dur + ramp:
        return 0.0
    return min(1.0, x / ramp, (dur + ramp - x) / ramp)

def idle_state(t=None):
    """Physical sensor values of a warm 4-cylinder petrol car idling in Park."""
    t = _T() if t is None else t
    sin = lambda period, ph=0.0: math.sin(2 * math.pi * t / period + ph)
    ac = _pulse(t, 170.0, 30.0, 60.0)                       # A/C compressor cycling
    rpm = 745 + 38 * ac + 9 * sin(6.3) + 5 * sin(2.1, 1.0) + _wob(t, 6, 1)   # idle governor hunting
    load = 22.0 + 3.5 * ac + 1.1 * sin(9.0, 0.5) + _wob(t, 0.7, 2)
    # Closed loop: STFT is a triangle wave integrating against the switching upstream O2 sensor
    phase = 2 * math.pi * 1.05 * t
    o2_up = 0.45 + 0.40 * math.tanh(2.5 * math.sin(phase - 0.3)) + _wob(t, 0.02, 3)
    stft = 3.0 * (1 - (2 / math.pi) * math.acos(math.cos(phase))) + _wob(t, 0.25, 5)
    throttle = 15.3 + 0.35 * sin(13.0) + 0.6 * ac + _wob(t, 0.1, 7)
    return {
        'ac': ac,
        'rpm': rpm,
        'load': load,
        'torque': 9.0 + 4.0 * ac + _wob(t, 0.5, 4),           # actual engine torque, %
        'coolant': 90 + 1.4 * sin(120.0) + _wob(t, 0.15, 3),  # thermostat hunting
        'oil': 94 + 0.5 * sin(150.0) + _wob(t, 0.1, 11),
        'iat': 34 + 0.5 * sin(90.0) + _wob(t, 0.1, 9),
        'ambient': 24.0,
        'trans': 78 + 0.3 * sin(200.0) + _wob(t, 0.1, 12),
        'stft': stft,
        'ltft': 1.6,
        'map': 30.0 + 0.85 * (load - 22.0) + _wob(t, 0.4, 6),
        'maf': 2.9 * (rpm / 745.0) * (load / 22.0) + _wob(t, 0.04, 8),   # g/s
        'throttle': throttle,
        'cmd_throttle': throttle + 0.2,
        'timing': 8.0 + 1.5 * sin(7.0) - 1.5 * ac + _wob(t, 0.4, 8),
        'baro': 101.0,
        'fuel': 62.0 + _wob(t, 0.08, 13),
        'fuel_press': 340 + 4 * sin(11.0) + _wob(t, 2, 14),
        'volts': 14.2 + 0.05 * sin(17.0) - 0.15 * ac + _wob(t, 0.015, 10),
        'o2_b1s1': max(0.05, min(0.95, o2_up)),
        'o2_b1s2': 0.68 + 0.02 * sin(20.0) + _wob(t, 0.01, 15),
        'cat': 420 + 8 * sin(40.0) + _wob(t, 1.5, 16),
        'runtime': 587 + t,                                    # s since engine start
    }

def idle_rpm():
    return idle_state()['rpm']

def battery_voltage():
    st = globals().get('_EMU_STATE', {})
    if st.get('vehicle_state') == 'idle':
        return f"{idle_state()['volts']:.1f}V"
    return f"13.2V"

def _clamp8(v):
    return max(0, min(255, int(round(v))))

def _b8(v):
    return [_clamp8(v)]

def _b16(v):
    v = max(0, min(0xFFFF, int(round(v))))
    return [v >> 8, v & 0xFF]

def _btrim(pct):  # fuel trim % -> A, percent = A/1.28 - 100
    return _b8((pct + 100) * 1.28)

def _u8(v):
    return f"{_clamp8(v):02X}"

def _u16(v):
    return " ".join(f"{b:02X}" for b in _b16(v))

def _trim(pct):
    return _u8((pct + 100) * 1.28)

def _hexs(bs):
    return " ".join(f"{b:02X}" for b in bs)

# Mode 01 raw data bytes per supported PID (typical 4-cylinder petrol, one bank, B1S1 + B1S2)
_PID_ENC = {
    0x04: lambda s: _b8(s['load'] * 2.55),
    0x05: lambda s: _b8(s['coolant'] + 40),
    0x06: lambda s: _btrim(s['stft']),
    0x07: lambda s: _btrim(s['ltft']),
    0x0A: lambda s: _b8(s['fuel_press'] / 3),
    0x0B: lambda s: _b8(s['map']),
    0x0C: lambda s: _b16(s['rpm'] * 4),
    0x0D: lambda s: [0],                                           # parked
    0x0E: lambda s: _b8((s['timing'] + 64) * 2),
    0x0F: lambda s: _b8(s['iat'] + 40),
    0x10: lambda s: _b16(s['maf'] * 100),
    0x11: lambda s: _b8(s['throttle'] * 2.55),
    0x14: lambda s: _b8(s['o2_b1s1'] * 200) + _btrim(s['stft']),  # upstream: voltage + STFT
    0x15: lambda s: _b8(s['o2_b1s2'] * 200) + [0xFF],             # downstream: STFT not used
    0x1C: lambda s: [0x06],                                        # EOBD
    0x1F: lambda s: _b16(s['runtime']),
    0x21: lambda s: _b16(142 if _EMU_STATE.get('dtc_active') else 0),  # km driven with MIL on
    0x2F: lambda s: _b8(s['fuel'] * 2.55),
    0x31: lambda s: _b16(1873),                                    # km since codes cleared
    0x33: lambda s: _b8(s['baro']),
    0x3C: lambda s: _b16((s['cat'] + 40) * 10),
    0x42: lambda s: _b16(s['volts'] * 1000),
    0x46: lambda s: _b8(s['ambient'] + 40),
    0x4C: lambda s: _b8(s['cmd_throttle'] * 2.55),
    0x52: lambda s: _b8(s['oil'] + 40),
}

# PIDs a typical 4-cylinder petrol car reports (PID 0x01 handled by monitor_status)
IDLE_SUPPORTED = {0x01} | set(_PID_ENC)

def idle_support_bitmap(base, supported=None):
    """Supported-PID bitmap for base 0x00/0x20/0x40 (bit 32 chains to next range)."""
    supported = IDLE_SUPPORTED if supported is None else supported
    bits = 0
    for pid in range(base + 1, base + 0x21):
        if pid in supported or (pid == base + 0x20 and any(p > pid for p in supported)):
            bits |= 1 << (base + 0x20 - pid)
    return " ".join(f"{(bits >> sh) & 0xFF:02X}" for sh in (24, 16, 8, 0))

def idle_pid(pid):
    """Mode 01 payload for a warm idling, parked car; None if the PID is not supported."""
    if pid == 0x01:
        return monitor_status(_EMU_STATE)
    enc = _PID_ENC.get(pid)
    return _hexs(enc(idle_state())) if enc else None

# Diagnostic trouble codes. Defaults are consistent with the idle data above
# (none of them contradicts a live sensor value). Override with --dtc/--pending-dtc/--permanent-dtc.
DTC_LIST = ["P0420", "P0442", "P0133"]          # confirmed/stored (mode 03), MIL on
DTC_PENDING_LIST = ["P0300"]                    # pending (mode 07)
DTC_PERMANENT_LIST = ["P0420"]                  # permanent (mode 0A), survive mode 04 clear

DTC_DESCRIPTIONS = {
    "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
    "P0442": "Evaporative Emission System Leak Detected (Small Leak)",
    "P0133": "O2 Sensor Circuit Slow Response (Bank 1 Sensor 1)",
    "P0300": "Random/Multiple Cylinder Misfire Detected",
}

# Freeze frames: one per DTC (mode 02 frame number = index), each holding the
# operating conditions at the moment that code set. Frame 00 is the code that
# turned the MIL on. Unknown codes (from --dtc) fall back to FREEZE_DEFAULT.
FREEZE_CONDITIONS = {
    # catalyst monitor runs at warm steady cruise
    "P0420": dict(fuel=0x02, load=38, coolant=92, stft=1.6, ltft=3.1, map=52, rpm=2150, speed=63,
                  timing=24.5, iat=28, maf=14.8, throttle=21, fuel_level=64),
    # EVAP small-leak test runs at idle during warm-up after a cold soak
    "P0442": dict(fuel=0x02, load=24, coolant=71, stft=-0.8, ltft=1.6, map=32, rpm=760, speed=0,
                  timing=7.0, iat=22, maf=3.1, throttle=15, fuel_level=58),
    # O2 response-rate test at light steady cruise
    "P0133": dict(fuel=0x02, load=31, coolant=89, stft=-2.3, ltft=3.1, map=45, rpm=1850, speed=72,
                  timing=27.0, iat=30, maf=11.6, throttle=18, fuel_level=61),
    # misfire under acceleration / load
    "P0300": dict(fuel=0x02, load=72, coolant=90, stft=8.6, ltft=3.9, map=86, rpm=2620, speed=48,
                  timing=12.5, iat=33, maf=31.4, throttle=44, fuel_level=60),
}
FREEZE_DEFAULT = dict(fuel=0x02, load=35, coolant=90, stft=0.8, ltft=2.3, map=50, rpm=2000, speed=60,
                      timing=22.0, iat=27, maf=13.5, throttle=20, fuel_level=62)

def _freeze_frame_for(code):
    c = FREEZE_CONDITIONS.get(code, FREEZE_DEFAULT)
    A, B = dtc_to_bytes(code)
    return {
        0x02: f"{A:02X} {B:02X}",                 # DTC that stored this frame
        0x03: f"{c['fuel']:02X} 00",              # fuel system: closed loop
        0x04: _u8(c['load'] * 2.55),
        0x05: _u8(c['coolant'] + 40),
        0x06: _trim(c['stft']),
        0x07: _trim(c['ltft']),
        0x0B: _u8(c['map']),
        0x0C: _u16(c['rpm'] * 4),
        0x0D: _u8(c['speed']),
        0x0E: _u8((c['timing'] + 64) * 2),
        0x0F: _u8(c['iat'] + 40),
        0x10: _u16(c['maf'] * 100),
        0x11: _u8(c['throttle'] * 2.55),
        0x2F: _u8(c['fuel_level'] * 2.55),
    }

def dtc_to_bytes(code):
    """'P0420' -> (0x04, 0x20) per SAE J2012 two-byte encoding."""
    code = code.strip().upper()
    A = ("PCBU".index(code[0]) << 6) | (int(code[1]) << 4) | int(code[2], 16)
    return A, int(code[3:5], 16)

def parse_dtc_list(text):
    codes = [c.strip().upper() for c in text.split(",") if c.strip()]
    for c in codes:
        if len(c) != 5 or c[0] not in "PCBU" or c[1] not in "0123":
            raise argparse.ArgumentTypeError(f"invalid DTC '{c}' (expected e.g. P0420, U0100)")
        int(c[2:], 16)
    return codes

def make_freeze_frames(st):
    """Frame 00.. = stored DTCs in order, then pending DTCs."""
    codes = list(st.get('dtc_active', [])) + list(st.get('dtc_pending', []))
    return [_freeze_frame_for(c) for c in codes]

def monitor_status(st):
    """Mode 01 PID 01: MIL + DTC count, spark-ignition monitors all complete."""
    count = len(st.get('dtc_active', []))
    A = (0x80 if count else 0x00) | min(count, 0x7F)
    # B: misfire/fuel/components supported & complete; C: catalyst, EVAP, O2, O2 heater supported; D: all complete
    return f"{A:02X} 07 65 00"

def can_response_lines(payload, st):
    """Format a service response like an ELM327 on ISO 15765-4, incl. ISO-TP multi-frame."""
    tx_id = st.get('tx_id', '7E8')
    hdr = st.get('headers')
    n = len(payload)
    hx = lambda bs: " ".join(f"{b:02X}" for b in bs)
    if n <= 7:
        return f"{tx_id} {n:02X} {hx(payload)}" if hdr else hx(payload)
    frames = [[0x10 | (n >> 8), n & 0xFF] + payload[:6]]
    rest, seq = payload[6:], 1
    while rest:
        chunk, rest = rest[:7], rest[7:]
        frames.append([0x20 | (seq & 0x0F)] + chunk + [0x00] * (7 - len(chunk)))
        seq += 1
    if hdr:
        return "\r".join(f"{tx_id} {hx(f)}" for f in frames)
    lines = [f"{n:03X}"]
    for i, f in enumerate(frames):
        lines.append(f"{i & 0x0F:X}: {hx(f[2:] if i == 0 else f[1:])}")
    return "\r".join(lines)

def dtc_response(service, codes, st):
    payload = [service, len(codes)]
    for c in codes:
        payload.extend(dtc_to_bytes(c))
    return can_response_lines(payload, st)

def _ascii_to_hex_bytes(s):
    return " ".join(f"{ord(ch):02X}" for ch in s)

def gen_vin():
    # A few realistic WMI prefixes
    wmis = [
        "1HG",  # Honda USA
        "1FA",  # Ford USA
        "3VW",  # VW Mexico
        "WVW",  # VW Germany
        "JHM",  # Honda Japan
        "SAL",  # Land Rover UK
    ]
    wmi = random.choice(wmis)
    vds = "".join(random.choice("ABCDEFGHJKLPRSTUVWXYZ0123456789") for _ in range(5))
    year_codes = "ABCDEFGHJKLMNPRSTVWXY"  # 1980-2000 mapping, simplified
    year = random.choice(year_codes)
    plant = random.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
    serial = f"{random.randint(100000, 999999):06d}"
    return f"{wmi}{vds}{year}{plant}{serial}"

def gen_ecu_version():
    major = random.randint(1, 3)
    minor = random.randint(0, 9)
    patch = random.randint(0, 9)
    return f"ECU SW v{major}.{minor}.{patch}"

def gen_calibration_id():
    base = random.choice(["CALID", "SWID", "CAL"])
    num = random.randint(100000, 999999)
    return f"{base}{num}"

MONITOR_START = object()  # handle_obd result for ATMA/ATMR/ATMT: the main loop starts streaming

def _reset_elm_defaults(st):
    st['echo'] = True
    st['linefeeds'] = False
    st['spaces'] = True
    st['headers'] = False
    st['show_dlc'] = False
    st['protocol'] = 0
    st['timeout'] = 32
    st['adaptive_timing'] = 1
    st['rx_id'] = '7DF'
    st['tx_id'] = '7E8'
    st['can_filter'] = None
    st['can_mask'] = None
    st['flow_control'] = None
    st['monitor'] = None

def _parse_can_id(text):
    """1-3 hex digits (11-bit) or up to 8 (29-bit) -> int, else None."""
    if not text or len(text) > 8:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None

# AT commands a real ELM327 accepts that have no visible effect on this emulator
_AT_NOOP = {"ATAL", "ATNL", "ATCAF0", "ATCAF1", "ATCSM0", "ATCSM1", "ATR0", "ATR1", "ATFE",
            "ATPC", "ATLP", "ATIB10", "ATIB96", "ATJHF0", "ATJHF1", "ATJTM1", "ATJTM5", "ATS"}

def handle_obd(cmd):
    cmd = cmd.replace(" ", "").upper()  # a real ELM ignores spaces ("AT MA" == "ATMA")

    global _EMU_STATE
    if '_EMU_STATE' not in globals():
        _EMU_STATE = {
            'initialized': False,
            'preinit_no_data': False,
            'echo': True,
            'linefeeds': False,
            'spaces': True,
            'headers': False,
            'protocol': 0,  # 0 = automatic
            'dtc_active': DTC_LIST.copy(),
            'dtc_pending': DTC_PENDING_LIST.copy(),
            'dtc_permanent': DTC_PERMANENT_LIST.copy(),
            'timeout': 32,  # ATST
            'adaptive_timing': 1,  # ATAT 1
            'freeze_frames': [],
            'tx_id': '7E8',       # ECU response ID (derived from the ATSH request header)
            'rx_id': '7DF',       # request header (ATSH), default functional broadcast
            'can_mask': None,     # ATCM
            'can_filter': None,   # ATCF / ATCRA
            'flow_control': None, # ATFC
            'monitor': None,      # set by ATMA/ATMR/ATMT while streaming
            'show_dlc': False,    # ATD0/ATD1
            'vehicle_state': 'idle',  # 'idle', 'stationary' or 'moving'
        }

    if cmd in ("ATZ", "ATWS"):
        _reset_elm_defaults(_EMU_STATE)
        _EMU_STATE['initialized'] = True
        return "ELM327 v1.5"
    if cmd == "ATI":
        return "ELM327 Emulator"
    if cmd == "ATE0":
        _EMU_STATE['echo'] = False
        return "OK"
    if cmd == "ATE1":
        _EMU_STATE['echo'] = True
        return "OK"
    if cmd == "ATL0":
        _EMU_STATE['linefeeds'] = False
        return "OK"
    if cmd == "ATL1":
        _EMU_STATE['linefeeds'] = True
        return "OK"
    if cmd == "ATS0":
        _EMU_STATE['spaces'] = False
        return "OK"
    if cmd == "ATS1":
        _EMU_STATE['spaces'] = True
        return "OK"
    if cmd == "ATH0":
        _EMU_STATE['headers'] = False
        return "OK"
    if cmd == "ATH1":
        _EMU_STATE['headers'] = True
        return "OK"
    if cmd.startswith("ATSP"):
        try:
            p = int(cmd.replace("ATSP", ""))
            _EMU_STATE['protocol'] = p
            return "OK"
        except Exception:
            return "?"
    if cmd == "ATDP":
        protos = {
            0: "AUTO",
            1: "SAE J1850 PWM",
            2: "SAE J1850 VPW",
            3: "ISO 9141-2",
            4: "ISO 14230-4 (KWP 5BAUD)",
            5: "ISO 14230-4 (KWP FAST)",
            6: "ISO 15765-4 (CAN 11/500)",
            7: "ISO 15765-4 (CAN 29/500)",
            8: "ISO 15765-4 (CAN 11/250)",
            9: "ISO 15765-4 (CAN 29/250)",
        }
        if _EMU_STATE['protocol'] == 0:
            return "AUTO, ISO 15765-4 (CAN 11/500)"
        return protos.get(_EMU_STATE['protocol'], "AUTO")
    if cmd == "ATDPN":
        return "A6" if _EMU_STATE['protocol'] == 0 else f"{_EMU_STATE['protocol']:X}"
    if cmd.startswith("ATST") and len(cmd) > 4:
        try:
            val = int(cmd[4:], 16)
            _EMU_STATE['timeout'] = val
            return "OK"
        except Exception:
            return "?"
    if cmd.startswith("ATAT") and len(cmd) > 4:
        try:
            val = int(cmd[4:])
            _EMU_STATE['adaptive_timing'] = val
            return "OK"
        except Exception:
            return "?"
    if cmd.startswith("ATPND") and len(cmd) > 5:
        try:
            val = cmd[5:]
            if val in {"0","1"}:
                _EMU_STATE['preinit_no_data'] = (val == "1")
                return "OK"
            return "?"
        except Exception:
            return "?"
    if cmd == "ATD":
        _reset_elm_defaults(_EMU_STATE)
        return "OK"
    if cmd in ("ATD0", "ATD1"):
        _EMU_STATE['show_dlc'] = (cmd == "ATD1")
        return "OK"

    if cmd.startswith("ATSH"):
        # Request header. Only the engine ECU answers: 7DF (broadcast) and 7E0 -> 7E8.
        can_id = _parse_can_id(cmd[4:])
        if can_id is None:
            return "?"
        _EMU_STATE['rx_id'] = f"{can_id:03X}"
        _EMU_STATE['tx_id'] = "7E8" if can_id in (0x7DF, 0x7E0) else None
        return "OK"

    # CAN receive filtering (applies to monitor mode and to the ECU's replies)
    if cmd == "ATCRA":
        _EMU_STATE['can_filter'] = None
        _EMU_STATE['can_mask'] = None
        return "OK"
    if cmd.startswith("ATCRA"):
        can_id = _parse_can_id(cmd[5:])
        if can_id is None:
            return "?"
        _EMU_STATE['can_filter'] = can_id
        _EMU_STATE['can_mask'] = 0x7FF
        return "OK"
    if cmd.startswith("ATCF") and not cmd.startswith("ATCFC"):
        can_id = _parse_can_id(cmd[4:])
        if can_id is None:
            return "?"
        _EMU_STATE['can_filter'] = can_id
        return "OK"
    if cmd.startswith("ATCM"):
        can_id = _parse_can_id(cmd[4:])
        if can_id is None:
            return "?"
        _EMU_STATE['can_mask'] = can_id
        return "OK"

    if cmd.startswith("ATFC"):
        _EMU_STATE['flow_control'] = cmd[4:]
        return "OK"
    if cmd == "ATRV":
        return battery_voltage()

    if cmd == "ATMA":
        _EMU_STATE['monitor'] = {'addr': None}
        return MONITOR_START
    if cmd.startswith(("ATMR", "ATMT")):
        # Monitor for receiver / transmitter hh. On 11-bit CAN both are matched on the ID's low byte.
        try:
            addr = int(cmd[4:], 16)
        except ValueError:
            return "?"
        _EMU_STATE['monitor'] = {'addr': addr & 0xFF}
        return MONITOR_START

    if cmd in _AT_NOOP:
        return "OK"
    if cmd.startswith("AT"):
        return "?"

    # Block all OBD service/PID commands until ATZ initialization
    if not _EMU_STATE.get('initialized', False) and not cmd.startswith("AT"):
        return "NO DATA" if _EMU_STATE.get('preinit_no_data') else ""

    if _EMU_STATE.get('tx_id') is None:
        return "NO DATA"  # request header addresses an ECU that does not exist on this bus

    if _EMU_STATE.get('vehicle_state') == 'idle' and len(cmd) == 4 and cmd.startswith("01"):
        try:
            pid_num = int(cmd[2:], 16)
        except ValueError:
            pid_num = -1
        if pid_num in (0x00, 0x20, 0x40):
            return f"41 {pid_num:02X} {idle_support_bitmap(pid_num)}"
        payload = idle_pid(pid_num)
        return f"41 {pid_num:02X} {payload}" if payload is not None else "NO DATA"

    if cmd == "010C": return f"41 0C {pid_0C()}"
    if cmd == "010D": return f"41 0D {pid_0D()}"
    if cmd == "0104": return f"41 04 {pid_04()}"
    if cmd == "0111": return f"41 11 {pid_11()}"
    if cmd == "0105": return f"41 05 {pid_05()}"
    if cmd == "0106": return f"41 06 {pid_06()}"
    if cmd == "0107": return f"41 07 {pid_07()}"
    if cmd == "0108": return f"41 08 {pid_08()}"
    if cmd == "010A": return f"41 0A {pid_0A()}"
    if cmd == "010B": return f"41 0B {pid_0B()}"
    if cmd == "010F": return f"41 0F {pid_0F()}"
    if cmd == "0110": return f"41 10 {pid_10()}"
    if cmd == "012F": return f"41 2F {pid_2F()}"
    if cmd == "0133": return f"41 33 {pid_33()}"
    if cmd == "0142": return f"41 42 {pid_42()}"
    if cmd == "014C": return f"41 4C {pid_4C()}"
    if cmd == "0146": return f"41 46 {pid_46()}"
    if cmd == "0152": return f"41 52 {pid_52()}"

    if cmd in {f"01{pid:02X}" for pid in range(0x14, 0x1C)}:
        pid_num = int(cmd[2:], 16)
        return f"41 {pid_num:02X} {pid_oxygen_14_1B(pid_num)}"

    if cmd in {f"01{pid:02X}" for pid in range(0x24, 0x2C)}:
        pid_num = int(cmd[2:], 16)
        return f"41 {pid_num:02X} {pid_24_2B()}"

    if cmd in {"013C","013D","013E","013F"}:
        pid_num = int(cmd[2:], 16)
        return f"41 {pid_num:02X} {pid_3C_3F()}"

    if cmd == "0101":
        return f"41 01 {monitor_status(_EMU_STATE)}"

    if cmd == "03":
        return dtc_response(0x43, _EMU_STATE.get('dtc_active', []), _EMU_STATE)

    if cmd == "07":
        return dtc_response(0x47, _EMU_STATE.get('dtc_pending', []), _EMU_STATE)

    if cmd == "0A":
        return dtc_response(0x4A, _EMU_STATE.get('dtc_permanent', []), _EMU_STATE)

    if cmd == "04":
        # Clears stored + pending codes, MIL and freeze frame; permanent codes remain
        _EMU_STATE['dtc_active'] = []
        _EMU_STATE['dtc_pending'] = []
        _EMU_STATE['freeze_frames'] = []
        return "44"

    if cmd.startswith("02") and len(cmd) in (4, 6):
        # Mode 02 freeze frame: 02 <pid> [frame], frame defaults to 00
        try:
            pid_num = int(cmd[2:4], 16)
            frame = int(cmd[4:6], 16) if len(cmd) == 6 else 0
        except ValueError:
            return "NO DATA"
        frames = _EMU_STATE.get('freeze_frames') or []
        if frame >= len(frames):
            return "NO DATA"
        ff = frames[frame]
        if pid_num in (0x00, 0x20, 0x40):
            return f"42 {pid_num:02X} {frame:02X} {idle_support_bitmap(pid_num, set(ff))}"
        if pid_num in ff:
            return f"42 {pid_num:02X} {frame:02X} {ff[pid_num]}"
        return "NO DATA"

    if cmd == "06":
        def encode_min_max_cur(min_v, max_v, cur_v, scale=1000):
            def enc(val):
                raw = int(val * scale)
                return ((raw // 256) & 0xFF, raw & 0xFF)
            a1,b1 = enc(min_v); a2,b2 = enc(max_v); a3,b3 = enc(cur_v)
            return f"{a1:02X} {b1:02X} {a2:02X} {b2:02X} {a3:02X} {b3:02X}"

        o2_min, o2_max = 0.1, 0.9
        o2_cur = random.uniform(o2_min, o2_max)
        tid01 = f"46 01 00 {encode_min_max_cur(o2_min, o2_max, o2_cur, scale=1000)}"

        egr_min, egr_max = 0.05, 0.20
        egr_cur = random.uniform(egr_min, egr_max)
        tid02 = f"46 02 00 {encode_min_max_cur(egr_min, egr_max, egr_cur, scale=1000)}"

        return tid01 + "\r" + tid02

    # PID support
    if cmd == "0100":
        return "41 00 BF 3E A8 13"

    if cmd == "0120":
        return "41 20 80 00 00 00"

    if cmd == "0140":
        return "41 40 94 00 10 00"

    if cmd == "0900":
        return "4A 54 32 42 47 32 32 4B 34 56 30 31 32 33 34 35 36"
        pass

    if cmd == "0902": 
        vin = "MHXPB41BB1A123456"
        data = _ascii_to_hex_bytes(vin).split(" ")
        frames = []
        chunk = []
        for b in data:
            chunk.append(b)
            if len(chunk) >= 20:
                frames.append("49 02 " + " ".join(chunk))
                chunk = []
        if chunk:
            frames.append("49 02 " + " ".join(chunk))
        return "\r".join(frames)


    if cmd == "0904":
        calid = gen_calibration_id()
        s = _ascii_to_hex_bytes(calid)
        parts = s.split(" ")
        frames = []
        while parts:
            chunk = parts[:20]
            parts = parts[20:]
            frames.append("49 04 " + " ".join(chunk))
        return "\r".join(frames)

    if cmd == "0906":
        ecu = gen_ecu_version()
        return f"49 06 {_ascii_to_hex_bytes(ecu)}"

    return "NO DATA"

# ---------------------------------------------------------------------------
# Idle HS-CAN bus (11-bit, 500 kbit/s). Each message has its own cycle time,
# like a real vehicle network, and carries values from idle_state() so the
# broadcast signals match what Mode 01 reports. Safety-relevant frames carry a
# 4-bit rolling counter and a SAE J1850 CRC-8, as OEM messages do.
# ---------------------------------------------------------------------------
def _crc8(data):
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1D) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc ^ 0xFF

def _sealed(payload6, cnt):
    d = list(payload6[:6]) + [cnt & 0x0F]
    return d + [_crc8(d)]

def _enc(pid, s):
    return _PID_ENC[pid](s)

def _m_ecm1(s, st, cnt):      # 0x0A0 engine: rpm, pedal, coolant, torque, status
    ac_req = s['ac'] > 0.05
    flags = 0x03 | (0x04 if ac_req else 0) | (0x08 if s['ac'] > 0.5 else 0) | (0x10 if st.get('dtc_active') else 0)
    return _sealed(_enc(0x0C, s) + [0, _enc(0x05, s)[0], _clamp8(s['torque'] + 125), flags], cnt)

def _m_wheels(s, st, cnt):    # 0x0A8 ABS wheel speeds, raw = 6767 + km/h*100 (standstill offset)
    return sum((_b16(6767) for _ in range(4)), [])

def _m_abs2(s, st, cnt):      # 0x0B0 vehicle speed, brake pressure, flags, yaw rate
    t = _T()
    yaw = 32768 + int(_wob(t, 3, 21))
    return _sealed(_b16(0) + [0, 0x00] + _b16(yaw), cnt)

def _m_sas(s, st, cnt):       # 0x0C4 steering angle (0.1 deg), rate, calibrated flag
    return _sealed(_b16(-23 & 0xFFFF) + _b16(0) + [0x01, 0x00], cnt)

def _m_tcm(s, st, cnt):       # 0x1C0 gear lever, gear, ATF temp, turbine rpm, lock-up
    return _sealed([ord('P'), 0, _clamp8(s['trans'] + 40)] + _b16(0) + [0], cnt)

def _m_ecm2(s, st, cnt):      # 0x2A0 same bytes as PIDs 0B, 10, 0F, 11, 06, 07, 0E
    return (_enc(0x0B, s) + _enc(0x10, s) + _enc(0x0F, s) + _enc(0x11, s)
            + _enc(0x06, s) + _enc(0x07, s) + _enc(0x0E, s))

def _m_ecm3(s, st, cnt):      # 0x2B0 same bytes as PIDs 33, 04, 52, 42, 0A
    return _sealed(_enc(0x33, s) + _enc(0x04, s) + _enc(0x52, s) + _enc(0x42, s) + _enc(0x0A, s), cnt)

def _m_cluster(s, st, cnt):   # 0x3A0 fuel, coolant gauge, speed, tacho, outside temp, lamps
    lamps = (0x01 if st.get('dtc_active') else 0) | 0x40   # MIL, parking brake
    gauge = 128 if 75 <= s['coolant'] <= 105 else _clamp8(s['coolant'] + 40)   # needle parks mid-scale
    return _sealed(_enc(0x2F, s) + [gauge, 0, _clamp8(s['rpm'] / 25), _clamp8(s['ambient'] + 40), lamps], cnt)

def _m_srs(s, st, cnt):       # 0x300 airbag ECU heartbeat
    return _sealed([0x01, 0x01, 0x00, 0x00, 0x00, 0x00], cnt)

def _m_body(s, st, cnt):      # 0x3B0 ignition RUN, doors closed, DRL on
    return [0x04, 0x00, 0x40, 0x00, 0x00, 0x1E, 0x00, 0x00]

def _m_hvac(s, st, cnt):      # 0x3C0 compressor, fan 2, set 22.0 C, evaporator, cabin
    comp = 1 if s['ac'] > 0.5 else 0
    return [0x04 | comp, 2, 44, _clamp8((6 if comp else 27) + 40), _clamp8(26.5 + 40), 0, 0, 0]

def _m_tpms_p(s, st, cnt):    # 0x4A0 tyre pressure, kPa / 2.75 (FL, FR, RL, RR)
    return [_clamp8(psi * 6.895 / 2.75) for psi in (33.1, 32.8, 31.9, 32.2)] + [0, 0, 0, 0]

def _m_tpms_t(s, st, cnt):    # 0x4B0 tyre temperature +40 (cold-ish, car parked in the shade)
    return [_clamp8(t + 40) for t in (22, 22, 21, 21)] + [0x01, 0, 0, 0]

def _m_trip(s, st, cnt):      # 0x510 odometer (km), trip A (0.1 km), instantaneous fuel use (L/h * 100)
    lph = s['maf'] / 14.7 / 745.0 * 3600.0
    return [0x01, 0x49, 0x5D] + _b16(1234) + _b16(lph * 100) + [0]   # 84317 km

def _m_clock(s, st, cnt):     # 0x5A0 date/time and outside temperature
    n = datetime.now()
    return [n.hour, n.minute, n.second, n.day, n.month, n.year - 2000, _clamp8(s['ambient'] + 40), 0]

# (CAN ID, cycle time in s, builder)
CAN_MESSAGES = [
    (0x0A0, 0.020, _m_ecm1),
    (0x0A8, 0.050, _m_wheels),
    (0x0B0, 0.050, _m_abs2),
    (0x0C4, 0.050, _m_sas),
    (0x1C0, 0.100, _m_tcm),
    (0x2A0, 0.100, _m_ecm2),
    (0x2B0, 0.100, _m_ecm3),
    (0x3A0, 0.100, _m_cluster),
    (0x300, 0.200, _m_srs),
    (0x3B0, 0.200, _m_body),
    (0x3C0, 0.200, _m_hvac),
    (0x4A0, 0.500, _m_tpms_p),
    (0x4B0, 0.500, _m_tpms_t),
    (0x510, 1.000, _m_trip),
    (0x5A0, 1.000, _m_clock),
]

class IdleCanBus:
    """Cyclic scheduler: due(now) returns the (id, data) frames whose cycle time elapsed."""
    def __init__(self, now):
        self.slots = [{'id': cid, 'period': period, 'fn': fn,
                       'next': now + random.uniform(0, period), 'n': random.randrange(16)}
                      for cid, period, fn in CAN_MESSAGES]

    def due(self, now, st):
        ready = sorted((m for m in self.slots if m['next'] <= now), key=lambda m: m['id'])
        if not ready:
            return []
        s = idle_state()  # one sample per batch: frames sent together are consistent
        frames = []
        for m in ready:
            m['next'] += m['period']
            if m['next'] < now - 0.1:   # fell behind (stall): resync instead of bursting
                m['next'] = now + m['period']
            frames.append((m['id'], m['fn'](s, st, m['n'])))
            m['n'] = (m['n'] + 1) & 0x0F
        return frames

def format_monitor_frame(cid, data, st):
    """One ATMA line: ID only with ATH1, DLC with ATD1, spaces per ATS."""
    parts = []
    if st.get('headers'):
        parts.append(f"{cid:03X}" if cid <= 0x7FF else f"{cid:08X}")
        if st.get('show_dlc'):
            parts.append(str(len(data)))
    parts += [f"{b:02X}" for b in data]
    return (" " if st.get('spaces', True) else "").join(parts)

def _gen_can_frame():
    can_id = random.randint(0x100, 0x7FF)
    dlc = random.randint(1, 8)
    data = [random.randint(0, 255) for _ in range(dlc)]
    id_hex = f"{can_id:03X}"
    data_hex = " ".join(f"{b:02X}" for b in data)
    return f"{id_hex} {dlc} {data_hex}"


def _init_can_state():
    return {
        'rr_index': 0,
        'tick': 0,
        'acc': 5.0,                 # % accelerator
        'brake_on': False,
        'brake_pressure': 0,        # 0..255
        'speed': 0.0,               # km/h
        'rpm': 800,                 # engine rpm
        'steer_angle': 0.0,         # degrees, -540..+540
        'prev_steer_angle': 0.0,    # last angle to estimate rate
        'steer_rate': 0.0,          # degrees/s approx
        'wheels': {                 # wheel speeds km/h
            'fl': 0.0, 'fr': 0.0, 'rl': 0.0, 'rr': 0.0
        },
        'prndl': 'P',               # 'P','R','N','D','L'
        'gear': 0,                  # 0=N, 1..6 gears
        'lights': {
            'low': False,
            'high': False,
            'left': False,
            'right': False,
            'hazard': False,
        },
        'doors': {
            'fl': False, 'fr': False, 'rl': False, 'rr': False, 'trunk': False
        },
        'hvac': {
            'ac': False,
            'fan': 2,               # 0..7
            'set_temp': 22          # Celsius 16..30
        },
        'tpms': {                   # pressures in psi, temps in C
            'p': {'fl': 33.0, 'fr': 33.0, 'rl': 32.0, 'rr': 32.0},
            't': {'fl': 25, 'fr': 25, 'rl': 24, 'rr': 24}
        },
        'radio': {
            'source': 1,            # 0 off, 1 FM, 2 AM, 3 BT
            'volume': 10,           # 0..100
            'button': 0,            # 0 none, 1 next, 2 prev, 3 play/pause
        }
    }


def _passes_can_filter(cid, st):
    """ATCF/ATCM/ATCRA receive filter plus the ATMR/ATMT address, as the ELM applies them."""
    if isinstance(cid, str):
        cid = int(cid, 16)
    mon = st.get('monitor') or {}
    if mon.get('addr') is not None and (cid & 0xFF) != mon['addr']:
        return False
    flt, mask = st.get('can_filter'), st.get('can_mask')
    if flt is None and mask is None:
        return True
    flt = flt or 0
    mask = 0x7FF if mask is None else mask
    return (cid & mask) == (flt & mask)


def _update_can_state(st):
    s = st['can_state']
    s['tick'] = s.get('tick', 0) + 1
    mode = st.get('vehicle_state', 'moving')
    if mode == 'idle':
        s['acc'] = 0.0
        s['brake_on'] = False
        s['brake_pressure'] = 0
        s['speed'] = 0.0
        s['rpm'] = int(idle_rpm())
        s['_steer_target'] = 0.0
    elif mode == 'stationary':
        # Settle accelerator near 0-5%
        s['_acc_target'] = 3.0
        s['acc'] += (s['_acc_target'] - s['acc']) * 0.2 + random.uniform(-0.2, 0.2)
        s['acc'] = max(0.0, min(8.0, s['acc']))

        # Brake mostly on, light pressure
        s['brake_on'] = True if random.random() < 0.9 else s['brake_on']
        s['brake_pressure'] = max(10, min(60, s['brake_pressure'] + random.randint(-2, 2)))

        # Speed tends to 0
        s['speed'] += (0.0 - s['speed']) * 0.3
        s['speed'] = max(0.0, s['speed'])

        # RPM near idle with tiny jitter
        base_idle = 750
        s['rpm'] = int(base_idle + random.uniform(-20, 20))
    else:
        # Moving: follow a smooth target speed waveform 60 +/- 20 km/h
        speed_target = 60.0 + 20.0 * math.sin(2 * math.pi * (s['tick'] % 300) / 300.0)
        # Compute simple pedal target toward speed difference
        spd_err = speed_target - s['speed']
        acc_target = max(0.0, min(70.0, 0.8 * spd_err + 15.0))
        s['acc'] += (acc_target - s['acc']) * 0.15 + random.uniform(-0.3, 0.3)
        s['acc'] = max(0.0, min(100.0, s['acc']))

        # Occasional braking
        if random.random() < 0.03:
            s['brake_on'] = not s['brake_on']
        if s['brake_on'] and s['speed'] > speed_target + 5:
            s['brake_pressure'] = min(255, s['brake_pressure'] + random.randint(5, 20))
        else:
            s['brake_pressure'] = max(0, s['brake_pressure'] - random.randint(3, 10))

        # Speed dynamics: accelerate with acc, decelerate with brake and drag
        accel_term = s['acc'] * 0.04
        brake_term = s['brake_pressure'] * 0.10
        s['speed'] += accel_term - brake_term - (s['speed'] * 0.02)
        s['speed'] = max(0.0, min(180.0, s['speed']))

        # RPM roughly tied to speed and throttle
        base_idle = 750
        s['rpm'] = int(base_idle + s['speed'] * 35 + s['acc'] * 6)
        s['rpm'] = max(600, min(5000, s['rpm']))

    # Steering angle slow random walk
    if mode != 'idle' and random.random() < 0.15:
        s['_steer_target'] = random.uniform(-360, 360)
    stgt = s.get('_steer_target', 0.0)
    s['prev_steer_angle'] = s['steer_angle']
    s['steer_angle'] += (stgt - s['steer_angle']) * 0.1 + random.uniform(-2, 2)
    s['steer_angle'] = max(-540.0, min(540.0, s['steer_angle']))
    # Approximate rate (deg/s). Assuming ~10Hz loop -> delta * 10
    s['steer_rate'] = (s['steer_angle'] - s['prev_steer_angle']) * 10.0

    # Gear estimate based on speed and rpm, with smoothing
    est = 0
    if s['speed'] < 2:
        est = 0
    elif s['speed'] < 15:
        est = 1
    elif s['speed'] < 30:
        est = 2
    elif s['speed'] < 50:
        est = 3
    elif s['speed'] < 80:
        est = 4
    elif s['speed'] < 120:
        est = 5
    else:
        est = 6
    if 'gear' in s:
        if est > s['gear'] and random.random() < 0.3:
            s['gear'] += 1
        elif est < s['gear'] and random.random() < 0.3:
            s['gear'] -= 1
        s['gear'] = max(0, min(6, s['gear']))

    # PRNDL heuristic: P if stopped and brake on; R rarely; D when moving
    if s['speed'] < 1.0:
        s['prndl'] = 'P' if (s['brake_on'] or mode == 'idle') else 'N'
        if mode != 'idle' and random.random() < 0.02:
            s['prndl'] = 'R'
    else:
        s['prndl'] = 'D'

    # Lights occasional toggles
    L = s['lights']
    if random.random() < (0.005 if mode in ('stationary', 'idle') else 0.03):
        L['low'] = not L['low']
    if random.random() < (0.002 if mode in ('stationary', 'idle') else 0.01):
        L['high'] = not L['high']
    # Turn signals blink when active
    if L.get('left') or L.get('right') or L.get('hazard'):
        if random.random() < 0.2:
            L['left'] = not L['left'] if L['left'] else L['left']
            L['right'] = not L['right'] if L['right'] else L['right']
    else:
        if random.random() < (0.001 if mode in ('stationary', 'idle') else 0.01):
            L[random.choice(['left', 'right', 'hazard'])] = True
    if L['hazard']:
        # Hazards imply both blinkers
        L['left'] = True
        L['right'] = True

    # Doors occasional open/close
    D = s['doors']
    if random.random() < (0.002 if mode in ('stationary', 'idle') else 0.02):
        key = random.choice(list(D.keys()))
        D[key] = not D[key]

    # HVAC drift and toggles
    H = s['hvac']
    if random.random() < (0.005 if mode in ('stationary', 'idle') else 0.03):
        H['ac'] = not H['ac']
    if random.random() < (0.02 if mode in ('stationary', 'idle') else 0.1):
        H['fan'] = max(0, min(7, H['fan'] + random.choice([-1, 1])))
    if random.random() < (0.02 if mode in ('stationary', 'idle') else 0.08):
        H['set_temp'] = max(16, min(30, H['set_temp'] + random.choice([-1, 1])))

    # Wheel speeds: around vehicle speed with small variance
    base = max(0.0, s['speed'])
    s['wheels']['fl'] = max(0.0, base + random.uniform(-0.8, 0.8))
    s['wheels']['fr'] = max(0.0, base + random.uniform(-0.8, 0.8))
    s['wheels']['rl'] = max(0.0, base + random.uniform(-0.8, 0.8))
    s['wheels']['rr'] = max(0.0, base + random.uniform(-0.8, 0.8))

    # TPMS slow drift
    for corner in ['fl','fr','rl','rr']:
        s['tpms']['p'][corner] = max(24.0, min(45.0, s['tpms']['p'][corner] + random.uniform(-0.05, 0.05)))
        delta_t = random.choice([-1, 0, 1]) if random.random() < 0.2 else 0
        s['tpms']['t'][corner] = max(-20, min(90, s['tpms']['t'][corner] + delta_t))

    # Radio small volume drift and occasional button press
    R = s['radio']
    R['volume'] = max(0, min(100, R['volume'] + random.randint(-1, 1)))
    if random.random() < 0.03:
        R['button'] = random.choice([1, 2, 3])
    else:
        R['button'] = 0


def _pack_can_frame(id_hex, bytes_list):
    bytes8 = (bytes_list + [0] * 8)[:8]
    return int(id_hex, 16), bytes8


def _gen_known_can_frames(st):
    # Ensure state exists and update it
    if 'can_state' not in st:
        st['can_state'] = _init_can_state()
    _update_can_state(st)
    s = st['can_state']

    # Round-robin two frames per tick to avoid flooding
    ids = ['0C8', '0C9', '0AA', '224', '1A6', '2F1', '0A5', '1B0', '1F2', '2C1', '0A6', '1C3', '2F2', '2F3']
    idx = s.get('rr_index', 0)
    send_ids = [ids[idx % len(ids)], ids[(idx + 1) % len(ids)]]
    s['rr_index'] = (idx + 1) % len(ids)

    frames = []
    for fid in send_ids:
        if fid == '0C8':  # Engine RPM (rpm/4 in bytes 0..1)
            val = max(0, min(65535, s['rpm'] // 4))
            a = (val >> 8) & 0xFF
            b = val & 0xFF
            frames.append(_pack_can_frame(fid, [a, b]))
        elif fid == '0C9':  # Accelerator pedal % (0..255)
            acc = int(max(0, min(100, s['acc'])) * 2.55)
            frames.append(_pack_can_frame(fid, [acc]))
        elif fid == '0AA':  # Vehicle speed km/h (0..255)
            spd = int(max(0, min(255, s['speed'])))
            frames.append(_pack_can_frame(fid, [spd]))
        elif fid == '224':  # Brake status
            bflag = 0x01 if s['brake_on'] else 0x00
            frames.append(_pack_can_frame(fid, [bflag, int(s['brake_pressure'])]))
        elif fid == '1A6':  # Lights status bits
            L = s['lights']
            bits = 0
            bits |= 0x01 if L['low'] else 0
            bits |= 0x02 if L['high'] else 0
            bits |= 0x04 if L['left'] else 0
            bits |= 0x08 if L['right'] else 0
            bits |= 0x10 if L['hazard'] else 0
            frames.append(_pack_can_frame(fid, [bits]))
        elif fid == '2F1':  # Radio
            R = s['radio']
            frames.append(_pack_can_frame(fid, [R['source'] & 0xFF, R['volume'] & 0xFF, R['button'] & 0xFF]))
        elif fid == '0A5':  # Steering angle (deg*10 signed in bytes 0..1, big-endian)
            sval = int(max(-540.0, min(540.0, s['steer_angle'])) * 10)
            sval &= 0xFFFF
            a = (sval >> 8) & 0xFF
            b = sval & 0xFF
            frames.append(_pack_can_frame(fid, [a, b]))
        elif fid == '0A6':  # Steering rate (deg/s * 10 signed 16-bit BE)
            r = int(max(-2047.0, min(2047.0, s['steer_rate'])) * 10)
            r &= 0xFFFF
            a = (r >> 8) & 0xFF
            b = r & 0xFF
            frames.append(_pack_can_frame(fid, [a, b]))
        elif fid == '1B0':  # Gear (0=N, 1..6)
            frames.append(_pack_can_frame(fid, [s['gear'] & 0x0F]))
        elif fid == '1C3':  # Wheel speeds (km/h * 10, 16-bit each: FL,FR,RL,RR)
            FL = int(max(0, min(6553, s['wheels']['fl'] * 10)))
            FR = int(max(0, min(6553, s['wheels']['fr'] * 10)))
            RL = int(max(0, min(6553, s['wheels']['rl'] * 10)))
            RR = int(max(0, min(6553, s['wheels']['rr'] * 10)))
            bytes_list = [
                (FL >> 8) & 0xFF, FL & 0xFF,
                (FR >> 8) & 0xFF, FR & 0xFF,
                (RL >> 8) & 0xFF, RL & 0xFF,
                (RR >> 8) & 0xFF, RR & 0xFF,
            ]
            frames.append(_pack_can_frame(fid, bytes_list))
        elif fid == '1F2':  # Doors status bits
            D = s['doors']
            bits = 0
            bits |= 0x01 if D['fl'] else 0
            bits |= 0x02 if D['fr'] else 0
            bits |= 0x04 if D['rl'] else 0
            bits |= 0x08 if D['rr'] else 0
            bits |= 0x10 if D['trunk'] else 0
            frames.append(_pack_can_frame(fid, [bits]))
        elif fid == '2C1':  # HVAC
            H = s['hvac']
            ac = 0x01 if H['ac'] else 0x00
            fan = H['fan'] & 0x07
            temp = max(16, min(30, H['set_temp']))
            frames.append(_pack_can_frame(fid, [ac, fan, temp]))
        elif fid == '2F2':  # TPMS pressures (psi * 2): FL, FR, RL, RR
            P = s['tpms']['p']
            vals = [P['fl'], P['fr'], P['rl'], P['rr']]
            bytes_list = [max(0, min(255, int(v * 2))) & 0xFF for v in vals]
            frames.append(_pack_can_frame(fid, bytes_list))
        elif fid == '2F3':  # TPMS temps (C + 40 offset): FL, FR, RL, RR
            T = s['tpms']['t']
            vals = [T['fl'], T['fr'], T['rl'], T['rr']]
            bytes_list = [max(0, min(255, int(v + 40))) & 0xFF for v in vals]
            frames.append(_pack_can_frame(fid, bytes_list))

    return frames


def format_response(response, st):
    """Apply ATH (ECU header on each line) and ATS (spaces) to an OBD reply."""
    tx_id = st.get('tx_id', '7E8')
    lines = response.split("\r")
    if st.get('headers'):
        lines = [l if l.startswith(tx_id) else f"{tx_id} {l}" for l in lines]
    if not st.get('spaces', True):
        lines = [l.replace(" ", "") for l in lines]
    return "\r".join(lines)

def process_command(raw, st):
    """One line from the tester -> reply text ('' = stay silent) or MONITOR_START."""
    cmd = raw.replace(" ", "").upper()
    response = handle_obd(cmd)
    if response is MONITOR_START or not response or cmd.startswith("AT"):
        return response
    if response in ("NO DATA", "?"):
        return response
    if not _passes_can_filter(int(st['tx_id'], 16), st):
        return "NO DATA"  # reply was received but ATCRA/ATCF/ATCM filtered it out
    return format_response(response, st)


def start_emulator(port="COM3", baud=38400):
    logger = logging.getLogger("obd-emulator")
    logger.info("ELM327 Emulator running on %s @ %s...", port, baud)
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.01)
    except Exception as e:
        logger.error("Failed to open serial port %s: %s", port, e)
        raise

    # Visible startup message with timestamp
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} started at COM : {port}")

    buf = b""
    bus = None
    legacy_next = 0.0
    try:
        while True:
            st = globals()['_EMU_STATE']
            data = ser.read(max(1, ser.in_waiting))

            if data and st.get('monitor') is not None:
                # Like the real ELM, any received character ends monitoring
                st['monitor'] = None
                bus = None
                buf = b""
                logger.info("monitor stopped")
                ser.write(b"\r>")
                continue

            buf += data.replace(b"\n", b"")
            while b"\r" in buf:
                line, _, buf = buf.partition(b"\r")
                raw = line.decode(errors="ignore").strip()
                if not raw:
                    continue
                logger.info("RX: %s", raw)
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} RX: {raw}")

                response = process_command(raw, st)
                if response is MONITOR_START:
                    # No reply and no prompt: frames stream until the next character arrives
                    bus = None
                    legacy_next = 0.0
                    buf = b""
                    logger.info("monitor started")
                    break

                # If empty response (e.g., before ATZ init), do not send anything
                if not response:
                    continue
                logger.info("TX: %s", response)
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} TX: {response}")
                ser.write((response + "\r\r>").encode())

            if st.get('monitor') is not None:
                now = time.monotonic()
                if st.get('vehicle_state') == 'idle':
                    if bus is None:
                        bus = IdleCanBus(now)
                    frames = bus.due(now, st)
                elif now >= legacy_next:
                    legacy_next = now + 0.1
                    try:
                        frames = _gen_known_can_frames(st)
                    except Exception:
                        frames = []
                else:
                    frames = []
                eol = "\r\n" if st.get('linefeeds') else "\r"
                lines = [format_monitor_frame(cid, d, st) for cid, d in frames if _passes_can_filter(cid, st)]
                if lines:
                    ser.write("".join(l + eol for l in lines).encode())
                    logger.debug("TX: %s", lines)
    except KeyboardInterrupt:
        logger.info("Shutting down emulator...")
    finally:
        try:
            ser.close()
        except Exception:
            pass


def _default_port():
    sysname = platform.system().lower()
    if 'windows' in sysname:
        return "COM3"
    # Linux/macOS common defaults
    return "/dev/ttyUSB0"


def main():
    epilog = (
        "Example:\n"
        "  python obd_emulator.py --port COM3 --baud 38400 --vehicle-state idle --verbose\n"
    )
    parser = argparse.ArgumentParser(
        description="ELM327 OBD-II emulator with CAN signal stream",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", "-p", default=_default_port(), help="Serial port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", default=38400, type=int, help="Baud rate (default: 38400)")
    parser.add_argument("--vehicle-state", "-s", choices=["idle", "stationary", "moving"], default="idle", help="Vehicle scenario to emulate")
    parser.add_argument("--dtc", type=parse_dtc_list, default=DTC_LIST, help="Stored DTCs, comma-separated; MIL on if any (default: %(default)s; '' for none)")
    parser.add_argument("--pending-dtc", type=parse_dtc_list, default=DTC_PENDING_LIST, help="Pending DTCs for mode 07 (default: %(default)s)")
    parser.add_argument("--permanent-dtc", type=parse_dtc_list, default=DTC_PERMANENT_LIST, help="Permanent DTCs for mode 0A (default: %(default)s)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

    # Seed state with safe defaults before loop begins (without auto-initializing ATZ)
    st = globals().get('_EMU_STATE')
    if st is None:
        globals()['_EMU_STATE'] = {
            'initialized': False,
            'preinit_no_data': False,
            'echo': True,
            'linefeeds': False,
            'spaces': True,
            'headers': False,
            'protocol': 0,
            'dtc_active': list(args.dtc),
            'dtc_pending': list(args.pending_dtc),
            'dtc_permanent': list(args.permanent_dtc),
            'timeout': 32,
            'adaptive_timing': 1,
            'freeze_frames': [],
            'tx_id': '7E8',
            'rx_id': '7DF',
            'can_mask': None,
            'can_filter': None,
            'flow_control': None,
            'monitor': None,
            'show_dlc': False,
            'vehicle_state': args.vehicle_state,
        }
    else:
        st['vehicle_state'] = args.vehicle_state
    st = globals()['_EMU_STATE']
    st['freeze_frames'] = make_freeze_frames(st)
    for kind, key in (("stored", 'dtc_active'), ("pending", 'dtc_pending'), ("permanent", 'dtc_permanent')):
        for c in st[key]:
            logging.getLogger("obd-emulator").warning("DTC %s: %s %s", kind, c, DTC_DESCRIPTIONS.get(c, ""))

    start_emulator(args.port, args.baud)


if __name__ == "__main__":
    main()

#usage Windows: python obd_emulator.py --port COM3 --baud 38400 --vehicle-state idle --verbose
#usage linux: python obd_emulator.py --port /dev/ttyUSB0 --baud 38400 --vehicle-state idle --verbose