import random
from dataclasses import dataclass

DEFAULT_VIN = "MHXPB41BB1A123456"
ECU_NAME = "ECM\0-EngineControl"


def _random_ecu_version():
    major = random.randint(1, 3)
    minor = random.randint(0, 9)
    patch = random.randint(0, 9)
    return f"ECU SW v{major}.{minor}.{patch}"


def _random_calibration_id():
    prefix = random.choice(["CALID", "SWID", "CAL"])
    return f"{prefix}{random.randint(100000, 999999)}"


@dataclass(frozen=True)
class VehicleIdentity:
    vin: str
    calibration_id: str
    ecu_version: str

    @classmethod
    def generate(cls):
        calibration_id = _random_calibration_id()
        return cls(DEFAULT_VIN, calibration_id, _random_ecu_version())
