from elm327.adapter.replies import OK, START_MONITORING, UNKNOWN_COMMAND
from elm327.adapter.settings import ENGINE_RESPONSE_ID, STANDARD_ID_MASK

ELM_VERSION = "ELM327 v1.5"
DEVICE_NAME = "ELM327 Emulator"
AUTO_PROTOCOL_DESCRIPTION = "AUTO, ISO 15765-4 (CAN 11/500)"
AUTO_PROTOCOL_NUMBER = "A6"
ENGINE_REQUEST_IDS = (0x7DF, 0x7E0)
MAX_CAN_ID_DIGITS = 8

PROTOCOL_NAMES = {
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

SETTING_SWITCHES = {
    "ATE0": ("echo", False),
    "ATE1": ("echo", True),
    "ATL0": ("linefeeds", False),
    "ATL1": ("linefeeds", True),
    "ATS0": ("spaces", False),
    "ATS1": ("spaces", True),
    "ATH0": ("headers", False),
    "ATH1": ("headers", True),
    "ATD0": ("show_dlc", False),
    "ATD1": ("show_dlc", True),
}

COMMANDS_WITHOUT_EFFECT = {
    "ATAL",
    "ATNL",
    "ATCAF0",
    "ATCAF1",
    "ATCSM0",
    "ATCSM1",
    "ATR0",
    "ATR1",
    "ATFE",
    "ATPC",
    "ATLP",
    "ATIB10",
    "ATIB96",
    "ATJHF0",
    "ATJHF1",
    "ATJTM1",
    "ATJTM5",
    "ATS",
}


def parse_can_id(text):
    if not text or len(text) > MAX_CAN_ID_DIGITS:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


class AtCommandHandler:
    def __init__(self, settings, vehicle):
        self._settings = settings
        self._vehicle = vehicle
        self._exact_commands = {
            "ATZ": self._restart,
            "ATWS": self._restart,
            "ATI": self._device_name,
            "ATD": self._restore_defaults,
            "ATDP": self._describe_protocol,
            "ATDPN": self._protocol_number,
            "ATRV": self._battery_voltage,
            "ATMA": self._monitor_all,
            "ATCRA": self._clear_can_filter,
        }
        self._prefix_commands = [
            ("ATSP", self._set_protocol),
            ("ATST", self._set_timeout),
            ("ATAT", self._set_adaptive_timing),
            ("ATPND", self._set_preinit_reply),
            ("ATSH", self._set_request_header),
            ("ATCRA", self._set_receive_address),
            ("ATCFC", self._reject),
            ("ATCF", self._set_can_filter),
            ("ATCM", self._set_can_mask),
            ("ATFC", self._set_flow_control),
            ("ATMR", self._monitor_address),
            ("ATMT", self._monitor_address),
        ]

    def handle(self, command):
        if command in SETTING_SWITCHES:
            name, value = SETTING_SWITCHES[command]
            setattr(self._settings, name, value)
            return OK
        if command in self._exact_commands:
            return self._exact_commands[command]()
        if command in COMMANDS_WITHOUT_EFFECT:
            return OK

        for prefix, handler in self._prefix_commands:
            if command.startswith(prefix):
                return handler(command[len(prefix) :])
        return UNKNOWN_COMMAND

    def _reject(self, _argument):
        return UNKNOWN_COMMAND

    def _restart(self):
        self._settings.reset()
        self._settings.initialized = True
        return ELM_VERSION

    def _device_name(self):
        return DEVICE_NAME

    def _restore_defaults(self):
        self._settings.reset()
        return OK

    def _describe_protocol(self):
        protocol = self._settings.protocol
        if protocol == 0:
            return AUTO_PROTOCOL_DESCRIPTION
        return PROTOCOL_NAMES.get(protocol, "AUTO")

    def _protocol_number(self):
        protocol = self._settings.protocol
        return AUTO_PROTOCOL_NUMBER if protocol == 0 else f"{protocol:X}"

    def _battery_voltage(self):
        return self._vehicle.battery_voltage()

    def _monitor_all(self):
        self._settings.start_monitoring()
        return START_MONITORING

    def _monitor_address(self, argument):
        try:
            address = int(argument, 16) & 0xFF
        except ValueError:
            return UNKNOWN_COMMAND
        self._settings.start_monitoring(address)
        return START_MONITORING

    def _store_number(self, name, text, base=10):
        try:
            value = int(text, base)
        except ValueError:
            return UNKNOWN_COMMAND
        setattr(self._settings, name, value)
        return OK

    def _set_protocol(self, argument):
        return self._store_number("protocol", argument)

    def _set_timeout(self, argument):
        return self._store_number("timeout", argument, base=16)

    def _set_adaptive_timing(self, argument):
        return self._store_number("adaptive_timing", argument)

    def _set_preinit_reply(self, argument):
        if argument not in ("0", "1"):
            return UNKNOWN_COMMAND
        self._settings.preinit_no_data = argument == "1"
        return OK

    def _set_request_header(self, argument):
        can_id = parse_can_id(argument)
        if can_id is None:
            return UNKNOWN_COMMAND
        answered = can_id in ENGINE_REQUEST_IDS
        self._settings.request_id = f"{can_id:03X}"
        self._settings.response_id = ENGINE_RESPONSE_ID if answered else None
        return OK

    def _clear_can_filter(self):
        self._settings.can_filter = None
        self._settings.can_mask = None
        return OK

    def _set_receive_address(self, argument):
        reply = self._set_can_filter(argument)
        if reply == OK:
            self._settings.can_mask = STANDARD_ID_MASK
        return reply

    def _set_can_filter(self, argument):
        can_id = parse_can_id(argument)
        if can_id is None:
            return UNKNOWN_COMMAND
        self._settings.can_filter = can_id
        return OK

    def _set_can_mask(self, argument):
        can_id = parse_can_id(argument)
        if can_id is None:
            return UNKNOWN_COMMAND
        self._settings.can_mask = can_id
        return OK

    def _set_flow_control(self, argument):
        self._settings.flow_control = argument
        return OK
