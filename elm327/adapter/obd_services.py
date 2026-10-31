import random

from elm327.adapter.replies import NO_DATA, SILENT
from elm327.vehicle.identity import ECU_NAME, VehicleIdentity
from elm327.vehicle.pids import SUPPORT_RANGE_PIDS, support_bitmap

STORED_CODES_REPLY = 0x43
PENDING_CODES_REPLY = 0x47
PERMANENT_CODES_REPLY = 0x4A
VEHICLE_INFO_REPLY = 0x49
CLEAR_CODES_REPLY = "44"
VEHICLE_INFO_SUPPORT_REPLY = "49 00 55 40 00 00"
VIN_PID = 0x02
CALIBRATION_PID = 0x04
ECU_VERSION_PID = 0x06
ECU_NAME_PID = 0x0A
CALIBRATION_SIZE = 16
ECU_NAME_SIZE = 20
VIN_CHUNK_SIZE = 20
SINGLE_VALUE_COUNT = 0x01


def min_max_current(low, high, current):
    values = []
    for value in (low, high, current):
        raw = int(value * 1000)
        values += [(raw // 256) & 0xFF, raw & 0xFF]
    return " ".join(f"{value:02X}" for value in values)


def fixed_length(data, size):
    return (data + [0] * size)[:size]


class ObdServiceHandler:
    def __init__(self, settings, vehicle, trouble_codes, formatter):
        self._settings = settings
        self._vehicle = vehicle
        self._trouble_codes = trouble_codes
        self._formatter = formatter
        self.identity = None
        self._services = {
            "03": self._stored_codes,
            "04": self._clear_codes,
            "06": self._monitor_tests,
            "07": self._pending_codes,
            "0A": self._permanent_codes,
            "0900": lambda: VEHICLE_INFO_SUPPORT_REPLY,
            "0902": lambda: self._vehicle_info(VIN_PID),
            "0904": lambda: self._vehicle_info(CALIBRATION_PID),
            "0906": lambda: self._vehicle_info(ECU_VERSION_PID),
            "090A": lambda: self._vehicle_info(ECU_NAME_PID),
        }

    def handle(self, command):
        if not self._settings.initialized:
            return NO_DATA if self._settings.preinit_no_data else SILENT
        if self._settings.response_id is None:
            return NO_DATA

        mode01_reply = self._vehicle.read_mode01(command)
        if mode01_reply is not None:
            return mode01_reply
        if command in self._services:
            return self._services[command]()
        if command.startswith("02") and len(command) in (4, 6):
            return self._freeze_frame(command)
        return NO_DATA

    def _stored_codes(self):
        codes = self._trouble_codes.stored
        return self._formatter.code_list(STORED_CODES_REPLY, codes)

    def _pending_codes(self):
        codes = self._trouble_codes.pending
        return self._formatter.code_list(PENDING_CODES_REPLY, codes)

    def _permanent_codes(self):
        codes = self._trouble_codes.permanent
        return self._formatter.code_list(PERMANENT_CODES_REPLY, codes)

    def _clear_codes(self):
        self._trouble_codes.clear()
        return CLEAR_CODES_REPLY

    def _freeze_frame(self, command):
        try:
            pid = int(command[2:4], 16)
            number = int(command[4:6], 16) if len(command) == 6 else 0
        except ValueError:
            return NO_DATA

        frames = self._trouble_codes.freeze_frames
        if number >= len(frames):
            return NO_DATA

        frame = frames[number]
        if pid in SUPPORT_RANGE_PIDS:
            bitmap = support_bitmap(pid, set(frame))
            return f"42 {pid:02X} {number:02X} {bitmap}"
        if pid in frame:
            return f"42 {pid:02X} {number:02X} {frame[pid]}"
        return NO_DATA

    def _monitor_tests(self):
        oxygen_min, oxygen_max = 0.1, 0.9
        oxygen_now = random.uniform(oxygen_min, oxygen_max)
        oxygen = min_max_current(oxygen_min, oxygen_max, oxygen_now)

        egr_min, egr_max = 0.05, 0.20
        egr_now = random.uniform(egr_min, egr_max)
        egr = min_max_current(egr_min, egr_max, egr_now)

        return f"46 01 00 {oxygen}\r46 02 00 {egr}"

    def _vehicle_info(self, pid):
        data = self._vehicle_info_bytes(pid)
        if self._settings.headers:
            payload = [VEHICLE_INFO_REPLY, pid, SINGLE_VALUE_COUNT] + data
            return self._formatter.framed(payload)
        if pid == VIN_PID:
            return self._vin_lines(data)
        values = " ".join(f"{value:02X}" for value in data)
        return f"49 {pid:02X} 01 {values}"

    def _vehicle_info_bytes(self, pid):
        if self.identity is None:
            self.identity = VehicleIdentity.generate()
        texts = {
            VIN_PID: self.identity.vin,
            CALIBRATION_PID: self.identity.calibration_id,
            ECU_VERSION_PID: self.identity.ecu_version,
            ECU_NAME_PID: ECU_NAME,
        }
        data = [ord(character) for character in texts[pid]]
        if pid == ECU_NAME_PID:
            return fixed_length(data, ECU_NAME_SIZE)
        if pid == CALIBRATION_PID:
            return fixed_length(data, CALIBRATION_SIZE)
        return data

    def _vin_lines(self, data):
        values = [f"{value:02X}" for value in data]
        chunks = [
            values[start : start + VIN_CHUNK_SIZE]
            for start in range(0, len(values), VIN_CHUNK_SIZE)
        ]
        return "\r".join("49 02 " + " ".join(chunk) for chunk in chunks)
