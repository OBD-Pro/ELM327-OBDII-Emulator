import argparse
import logging
import platform

from elm327.emulator import build_emulator
from elm327.transport.serial_server import SerialServer
from elm327.vehicle.trouble_codes import (
    CODE_DESCRIPTIONS,
    DEFAULT_PENDING_CODES,
    DEFAULT_PERMANENT_CODES,
    DEFAULT_STORED_CODES,
    TroubleCodes,
    parse_code_list,
)

EXAMPLE = (
    "Example:\n"
    "  python obd_emulator.py --port COM3 --baud 38400 "
    "--vehicle-state idle --verbose\n"
)


def default_port():
    is_windows = "windows" in platform.system().lower()
    return "COM3" if is_windows else "/dev/ttyUSB0"


def build_parser():
    parser = argparse.ArgumentParser(
        description="ELM327 OBD-II emulator with CAN signal stream",
        epilog=EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port",
        "-p",
        default=default_port(),
        help="Serial port (e.g., COM3, /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--baud",
        "-b",
        default=38400,
        type=int,
        help="Baud rate (default: 38400)",
    )
    parser.add_argument(
        "--vehicle-state",
        "-s",
        choices=["idle", "stationary", "moving"],
        default="idle",
        help="Vehicle scenario to emulate",
    )
    parser.add_argument(
        "--dtc",
        type=parse_code_list,
        default=DEFAULT_STORED_CODES,
        help="Stored DTCs, comma-separated; MIL on if any "
        "(default: %(default)s; '' for none)",
    )
    parser.add_argument(
        "--pending-dtc",
        type=parse_code_list,
        default=DEFAULT_PENDING_CODES,
        help="Pending DTCs for mode 07 (default: %(default)s)",
    )
    parser.add_argument(
        "--permanent-dtc",
        type=parse_code_list,
        default=DEFAULT_PERMANENT_CODES,
        help="Permanent DTCs for mode 0A (default: %(default)s)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def configure_logging(verbose):
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def log_trouble_codes(trouble_codes):
    logger = logging.getLogger("obd-emulator")
    groups = (
        ("stored", trouble_codes.stored),
        ("pending", trouble_codes.pending),
        ("permanent", trouble_codes.permanent),
    )
    for kind, codes in groups:
        for code in codes:
            description = CODE_DESCRIPTIONS.get(code, "")
            logger.warning("DTC %s: %s %s", kind, code, description)


def main():
    args = build_parser().parse_args()
    configure_logging(args.verbose)

    trouble_codes = TroubleCodes(
        stored=list(args.dtc),
        pending=list(args.pending_dtc),
        permanent=list(args.permanent_dtc),
    )
    log_trouble_codes(trouble_codes)

    emulator = build_emulator(args.vehicle_state, trouble_codes)
    SerialServer(args.port, args.baud, emulator).run()
