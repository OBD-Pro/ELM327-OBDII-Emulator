from dataclasses import dataclass

from elm327.adapter.at_commands import AtCommandHandler
from elm327.adapter.elm327_adapter import Elm327Adapter
from elm327.adapter.obd_services import ObdServiceHandler
from elm327.adapter.response_formatter import ResponseFormatter
from elm327.adapter.settings import AdapterSettings
from elm327.can.monitor import CanMonitor
from elm327.vehicle.base import Vehicle
from elm327.vehicle.idle_vehicle import IdleVehicle
from elm327.vehicle.simulated_vehicle import SimulatedVehicle
from elm327.vehicle.trouble_codes import TroubleCodes


@dataclass
class Emulator:
    settings: AdapterSettings
    trouble_codes: TroubleCodes
    vehicle: Vehicle
    adapter: Elm327Adapter
    monitor: CanMonitor


def create_vehicle(mode, trouble_codes, started_at=None):
    if mode == "idle":
        return IdleVehicle(trouble_codes, started_at)
    return SimulatedVehicle(mode, trouble_codes)


def build_emulator(mode="idle", trouble_codes=None, started_at=None):
    settings = AdapterSettings()
    trouble_codes = TroubleCodes() if trouble_codes is None else trouble_codes
    vehicle = create_vehicle(mode, trouble_codes, started_at)
    formatter = ResponseFormatter(settings)
    adapter = Elm327Adapter(
        settings,
        AtCommandHandler(settings, vehicle),
        ObdServiceHandler(settings, vehicle, trouble_codes, formatter),
        formatter,
    )
    monitor = CanMonitor(vehicle, settings)
    return Emulator(settings, trouble_codes, vehicle, adapter, monitor)
