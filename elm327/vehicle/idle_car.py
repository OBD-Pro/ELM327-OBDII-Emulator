import math
import time
from dataclasses import dataclass

FULL_CIRCLE = 2 * math.pi
AC_CYCLE_SECONDS = 170.0
AC_START_SECONDS = 30.0
AC_ON_SECONDS = 60.0
IDLE_RPM = 745
IDLE_LOAD = 22.0
OXYGEN_SWITCH_HZ = 1.05
STARTING_RUNTIME_SECONDS = 587


@dataclass(frozen=True)
class IdleSample:
    air_conditioning: float
    rpm: float
    load: float
    torque: float
    coolant: float
    oil: float
    intake_air: float
    ambient: float
    transmission: float
    short_trim: float
    long_trim: float
    manifold_pressure: float
    air_flow: float
    throttle: float
    commanded_throttle: float
    timing: float
    barometric_pressure: float
    fuel_level: float
    fuel_pressure: float
    voltage: float
    oxygen_upstream: float
    oxygen_downstream: float
    catalyst: float
    runtime: float


def wobble(t, amplitude, seed=0.0):
    waves = (
        0.35 * math.sin(FULL_CIRCLE * 0.37 * t + seed * 1.7),
        0.30 * math.sin(FULL_CIRCLE * 1.13 * t + seed * 2.9),
        0.20 * math.sin(FULL_CIRCLE * 3.71 * t + seed * 4.1),
        0.15 * math.sin(FULL_CIRCLE * 9.70 * t + seed * 5.3),
    )
    return amplitude * sum(waves)


def pulse(t, period, start, duration, ramp=2.0):
    position = (t % period) - start
    if position <= 0 or position >= duration + ramp:
        return 0.0
    rising = position / ramp
    falling = (duration + ramp - position) / ramp
    return min(1.0, rising, falling)


class IdleCar:
    def __init__(self, started_at=None):
        self._started_at = time.monotonic() if started_at is None else started_at

    def elapsed(self):
        return time.monotonic() - self._started_at

    def sample(self):
        t = self.elapsed()

        def wave(period, phase=0.0):
            return math.sin(FULL_CIRCLE * t / period + phase)

        ac = pulse(t, AC_CYCLE_SECONDS, AC_START_SECONDS, AC_ON_SECONDS)
        rpm = IDLE_RPM + 38 * ac + 9 * wave(6.3) + 5 * wave(2.1, 1.0)
        rpm += wobble(t, 6, 1)
        load = IDLE_LOAD + 3.5 * ac + 1.1 * wave(9.0, 0.5) + wobble(t, 0.7, 2)
        throttle = 15.3 + 0.35 * wave(13.0) + 0.6 * ac + wobble(t, 0.1, 7)

        oxygen_phase = FULL_CIRCLE * OXYGEN_SWITCH_HZ * t
        oxygen_swing = math.tanh(2.5 * math.sin(oxygen_phase - 0.3))
        oxygen_upstream = 0.45 + 0.40 * oxygen_swing + wobble(t, 0.02, 3)
        trim_triangle = 1 - (2 / math.pi) * math.acos(math.cos(oxygen_phase))

        return IdleSample(
            air_conditioning=ac,
            rpm=rpm,
            load=load,
            torque=9.0 + 4.0 * ac + wobble(t, 0.5, 4),
            coolant=90 + 1.4 * wave(120.0) + wobble(t, 0.15, 3),
            oil=94 + 0.5 * wave(150.0) + wobble(t, 0.1, 11),
            intake_air=34 + 0.5 * wave(90.0) + wobble(t, 0.1, 9),
            ambient=24.0,
            transmission=78 + 0.3 * wave(200.0) + wobble(t, 0.1, 12),
            short_trim=3.0 * trim_triangle + wobble(t, 0.25, 5),
            long_trim=1.6,
            manifold_pressure=30.0 + 0.85 * (load - IDLE_LOAD) + wobble(t, 0.4, 6),
            air_flow=2.9 * (rpm / IDLE_RPM) * (load / IDLE_LOAD) + wobble(t, 0.04, 8),
            throttle=throttle,
            commanded_throttle=throttle + 0.2,
            timing=8.0 + 1.5 * wave(7.0) - 1.5 * ac + wobble(t, 0.4, 8),
            barometric_pressure=101.0,
            fuel_level=62.0 + wobble(t, 0.08, 13),
            fuel_pressure=340 + 4 * wave(11.0) + wobble(t, 2, 14),
            voltage=14.2 + 0.05 * wave(17.0) - 0.15 * ac + wobble(t, 0.015, 10),
            oxygen_upstream=max(0.05, min(0.95, oxygen_upstream)),
            oxygen_downstream=0.68 + 0.02 * wave(20.0) + wobble(t, 0.01, 15),
            catalyst=420 + 8 * wave(40.0) + wobble(t, 1.5, 16),
            runtime=STARTING_RUNTIME_SECONDS + t,
        )
