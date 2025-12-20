import serial
import random
import math
import argparse
import logging
from datetime import datetime
import platform
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

def battery_voltage():
    return f"13.2V"

def pid_14_1B():
    voltage_v = random.uniform(0.05, 0.90)
    A = max(0, min(255, int(voltage_v * 200)))
    B = random.randint(100, 160)  # Short term fuel trim (%): B = trim - 128
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

# Fake DTC example
DTC_LIST = [
    "P0301", "P0420", "P0171", "U0100"
]

def get_dtc_bytes():
    dtc = random.choice(DTC_LIST)
    # Convert DTC string to hex per OBD spec
    first = {
        "P": 0x00,
        "C": 0x40,
        "B": 0x80,
        "U": 0xC0
    }[dtc[0]]

    code = int(dtc[1:])
    A = first | (code >> 8)
    B = code & 0xFF

    return f"{A:02X} {B:02X}"

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

def handle_obd(cmd):
    cmd = cmd.strip().upper()

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
            'dtc_pending': [],
            'timeout': 32,  # ATST
            'adaptive_timing': 1,  # ATAT 1
            'freeze_frame': None,
            'tx_id': '7E8',       # default ECU response ID
            'rx_id': '7E0',       # default tester request ID
            'can_mask': None,     # ATCM
            'can_filter': None,   # ATCRA
            'flow_control': None, # ATFC
            'vehicle_state': 'moving',  # 'moving' or 'stationary'
        }

    if cmd == "ATZ":
        _EMU_STATE['echo'] = True
        _EMU_STATE['linefeeds'] = False
        _EMU_STATE['spaces'] = True
        _EMU_STATE['headers'] = False
        _EMU_STATE['protocol'] = 0
        _EMU_STATE['timeout'] = 32
        _EMU_STATE['adaptive_timing'] = 1
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
            4: "ISO 14230-4 KWP",
            5: "ISO 15765-4 CAN (11 bit ID, 500 kbaud)",
            6: "ISO 15765-4 CAN (11 bit ID, 250 kbaud)",
        }
        return protos.get(_EMU_STATE['protocol'], "AUTO")
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
        # Defaults
        _EMU_STATE['echo'] = True
        _EMU_STATE['linefeeds'] = False
        _EMU_STATE['spaces'] = True
        _EMU_STATE['headers'] = False
        _EMU_STATE['protocol'] = 0
        _EMU_STATE['timeout'] = 32
        _EMU_STATE['adaptive_timing'] = 1
        return "OK"

    if cmd.startswith("ATSH") and len(cmd) > 4:
        _EMU_STATE['tx_id'] = cmd[4:].strip().upper()
        return "OK"

    if cmd.startswith("ATCRA") and len(cmd) > 5:
        _EMU_STATE['can_filter'] = cmd[5:].strip().upper()
        return "OK"

    if cmd.startswith("ATCM") and len(cmd) > 4:
        _EMU_STATE['can_mask'] = cmd[4:].strip().upper()
        return "OK"

    if cmd.startswith("ATFC") and len(cmd) > 4:
        _EMU_STATE['flow_control'] = cmd[4:].strip().upper()
        return "OK"
    if cmd.startswith("ATRV"):
        return battery_voltage()

    # Block all OBD service/PID commands until ATZ initialization
    if not _EMU_STATE.get('initialized', False) and not cmd.startswith("AT"):
        return "NO DATA" if _EMU_STATE.get('preinit_no_data') else ""

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
        return f"41 {pid_num:02X} {pid_14_1B()}"

    if cmd in {f"01{pid:02X}" for pid in range(0x24, 0x2C)}:
        pid_num = int(cmd[2:], 16)
        return f"41 {pid_num:02X} {pid_24_2B()}"

    if cmd in {"013C","013D","013E","013F"}:
        pid_num = int(cmd[2:], 16)
        return f"41 {pid_num:02X} {pid_3C_3F()}"

    if cmd == "03":
        dtc_resp = get_dtc_bytes()

        _EMU_STATE['freeze_frame'] = {
            'rpm': pid_0C(),
            'speed': pid_0D(),
            'coolant': pid_05(),
            'map': pid_0B(),
            'iat': pid_0F(),
            'throttle': pid_11(),
        }
        return f"43 {dtc_resp}"

    if cmd == "04":
        _EMU_STATE['dtc_active'] = []
        _EMU_STATE['dtc_pending'] = []
        return "44"

    if cmd == "07":
        if _EMU_STATE['dtc_pending']:
            dtc = random.choice(_EMU_STATE['dtc_pending'])
            first = {"P":0x00,"C":0x40,"B":0x80,"U":0xC0}[dtc[0]]
            code = int(dtc[1:])
            A = first | (code >> 8)
            B = code & 0xFF
            return f"47 {A:02X} {B:02X}"
        return "47 00 00"

    if cmd == "0201":
        ff = _EMU_STATE.get('freeze_frame')
        if not ff:
            return "NO DATA"

        parts = [
            f"0C {ff['rpm']}",
            f"0D {ff['speed']}",
            f"05 {ff['coolant']}",
            f"0B {ff['map']}",
            f"0F {ff['iat']}",
            f"11 {ff['throttle']}",
        ]

        return "42 " + " ".join(parts)

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


def _passes_can_filter(id_hex, st):
    try:
        can_filter = st.get('can_filter')
        can_mask = st.get('can_mask')
        if not can_filter and not can_mask:
            return True
        id_val = int(id_hex, 16)
        filt_val = int(can_filter, 16) if can_filter else None
        mask_val = int(can_mask, 16) if can_mask else None
        if mask_val is not None and filt_val is not None:
            return (id_val & mask_val) == (filt_val & mask_val)
        if filt_val is not None:
            return id_val == filt_val
        if mask_val is not None:
            return (id_val & mask_val) == 0
    except Exception:
        return True
    return True


def _update_can_state(st):
    s = st['can_state']
    s['tick'] = s.get('tick', 0) + 1
    mode = st.get('vehicle_state', 'moving')
    if mode == 'stationary':
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
    if random.random() < 0.15:
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
        s['prndl'] = 'P' if s['brake_on'] else 'N'
        if random.random() < 0.02:
            s['prndl'] = 'R'
    else:
        s['prndl'] = 'D'

    # Lights occasional toggles
    L = s['lights']
    if random.random() < (0.005 if mode == 'stationary' else 0.03):
        L['low'] = not L['low']
    if random.random() < (0.002 if mode == 'stationary' else 0.01):
        L['high'] = not L['high']
    # Turn signals blink when active
    if L.get('left') or L.get('right') or L.get('hazard'):
        if random.random() < 0.2:
            L['left'] = not L['left'] if L['left'] else L['left']
            L['right'] = not L['right'] if L['right'] else L['right']
    else:
        if random.random() < (0.001 if mode == 'stationary' else 0.01):
            L[random.choice(['left', 'right', 'hazard'])] = True
    if L['hazard']:
        # Hazards imply both blinkers
        L['left'] = True
        L['right'] = True

    # Doors occasional open/close
    D = s['doors']
    if random.random() < (0.002 if mode == 'stationary' else 0.02):
        key = random.choice(list(D.keys()))
        D[key] = not D[key]

    # HVAC drift and toggles
    H = s['hvac']
    if random.random() < (0.005 if mode == 'stationary' else 0.03):
        H['ac'] = not H['ac']
    if random.random() < (0.02 if mode == 'stationary' else 0.1):
        H['fan'] = max(0, min(7, H['fan'] + random.choice([-1, 1])))
    if random.random() < (0.02 if mode == 'stationary' else 0.08):
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
    data_hex = " ".join(f"{b:02X}" for b in bytes8)
    return f"{id_hex} 8 {data_hex}"


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

    # Apply ATCRA/ATCM filters
    filtered = []
    for fr in frames:
        try:
            id_hex = fr.split(' ', 1)[0]
        except Exception:
            id_hex = None
        if id_hex is None or _passes_can_filter(id_hex, st):
            filtered.append(fr)
    return filtered


def start_emulator(port="COM3", baud=38400):
    logger = logging.getLogger("obd-emulator")
    logger.info("ELM327 Emulator running on %s @ %s...", port, baud)
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.2)
    except Exception as e:
        logger.error("Failed to open serial port %s: %s", port, e)
        raise

    # Visible startup message with timestamp
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} started at COM : {port}")

    try:
        while True:
            raw = ser.readline().decode(errors="ignore").strip()
            st = globals().get('_EMU_STATE', {})
            if st.get('monitor', False):
                # Generate and stream known CAN signal frames (accelerator, brake, lights, radio, etc.)
                try:
                    frames = _gen_known_can_frames(st)
                except Exception:
                    frames = []
                for frame in frames:
                    ser.write((frame + "\r\n").encode())
                    logger.info("TX: %s", frame)
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} TX: {frame}")

            if not raw:
                continue
            logger.info("RX: %s", raw)
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} RX: {raw}")

            incoming_id = None
            cmd = raw
            if ' ' in raw:
                first, rest = raw.split(' ', 1)

                try:
                    int(first, 16)
                    incoming_id = first.upper()
                    cmd = rest.strip()
                except Exception:
                    incoming_id = None

            st = globals().get('_EMU_STATE', {})
            can_filter = st.get('can_filter')
            can_mask = st.get('can_mask')
            if incoming_id and (can_filter or can_mask):
                try:
                    id_val = int(incoming_id, 16)
                    filt_val = int(can_filter, 16) if can_filter else None
                    mask_val = int(can_mask, 16) if can_mask else None
                    match = True
                    if mask_val is not None and filt_val is not None:
                        match = (id_val & mask_val) == (filt_val & mask_val)
                    elif filt_val is not None:
                        match = id_val == filt_val
                    elif mask_val is not None:
                        match = (id_val & mask_val) == 0
                    if not match:
                        logger.debug("Frame dropped due to ATCRA/ATCM mismatch")
                        continue
                except Exception:
                    pass

            response = handle_obd(cmd)
 
            if cmd == "AT MA":
                st['monitor'] = True
                response = "OK"
            elif cmd == "AT MR":
                st['monitor'] = True
                response = "OK"
            elif cmd == "AT PC":
                st['monitor'] = False
                response = "OK"

            # If empty response (e.g., before ATZ init), do not send anything
            if not response:
                continue

            try:
                st = globals().get('_EMU_STATE', {})
                if st.get('headers') and response not in {"OK","NO DATA","?","ELM327 Emulator","ELM327 v1.5"}:
                    tx_id = st.get('tx_id', '7E8')
                    response = f"{tx_id} {response}"
                
                if st.get('spaces') is False and response not in {"OK","NO DATA","?"}:
                    if response.startswith(('7E','18')) and ' ' in response:
                        parts = response.split(' ', 1)
                        response = parts[0] + ' ' + parts[1].replace(' ', '')
                    else:
                        response = response.replace(' ', '')
            except Exception:
                pass

            logger.info("TX: %s", response)
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} TX: {response}")
            ser.write((response + "\r\n").encode())
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
        "  python obd_emulator.py --port COM3 --baud 38400 --vehicle-state moving --verbose\n"
    )
    parser = argparse.ArgumentParser(
        description="ELM327 OBD-II emulator with CAN signal stream",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", "-p", default=_default_port(), help="Serial port (e.g., COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", default=38400, type=int, help="Baud rate (default: 38400)")
    parser.add_argument("--vehicle-state", "-s", choices=["stationary", "moving"], default="moving", help="Vehicle scenario to emulate")
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
            'dtc_active': DTC_LIST.copy(),
            'dtc_pending': [],
            'timeout': 32,
            'adaptive_timing': 1,
            'freeze_frame': None,
            'tx_id': '7E8',
            'rx_id': '7E0',
            'can_mask': None,
            'can_filter': None,
            'flow_control': None,
            'vehicle_state': args.vehicle_state,
        }
    else:
        st['vehicle_state'] = args.vehicle_state

    start_emulator(args.port, args.baud)


if __name__ == "__main__":
    main()

#usage Windows: python obd_emulator.py --port COM3 --baud 38400 --vehicle-state moving --verbose
#usage linux: python obd_emulator.py --port /dev/ttyUSB0 --baud 38400 --vehicle-state moving --verbose