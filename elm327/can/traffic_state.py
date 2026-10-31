from dataclasses import dataclass, field

CORNERS = ("fl", "fr", "rl", "rr")


def _for_each_corner(front, rear):
    return {"fl": front, "fr": front, "rl": rear, "rr": rear}


@dataclass
class Lights:
    low: bool = False
    high: bool = False
    left: bool = False
    right: bool = False
    hazard: bool = False


@dataclass
class Climate:
    air_conditioning: bool = False
    fan: int = 2
    set_temp: int = 22


@dataclass
class Radio:
    source: int = 1
    volume: int = 10
    button: int = 0


@dataclass
class TrafficState:
    tick: int = 0
    next_frame_index: int = 0
    pedal: float = 5.0
    brake_on: bool = False
    brake_pressure: int = 0
    speed: float = 0.0
    rpm: int = 800
    steering_angle: float = 0.0
    steering_rate: float = 0.0
    steering_target: float = 0.0
    gear: int = 0
    gear_lever: str = "P"
    lights: Lights = field(default_factory=Lights)
    climate: Climate = field(default_factory=Climate)
    radio: Radio = field(default_factory=Radio)
    doors: dict = field(
        default_factory=lambda: {
            "fl": False,
            "fr": False,
            "rl": False,
            "rr": False,
            "trunk": False,
        }
    )
    wheel_speeds: dict = field(default_factory=lambda: _for_each_corner(0.0, 0.0))
    tyre_pressures: dict = field(default_factory=lambda: _for_each_corner(33.0, 32.0))
    tyre_temps: dict = field(default_factory=lambda: _for_each_corner(25, 24))
