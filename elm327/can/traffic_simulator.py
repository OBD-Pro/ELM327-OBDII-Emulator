import bisect
import random

from elm327.can.driving_styles import MovingDriving, StationaryDriving
from elm327.can.traffic_state import CORNERS, TrafficState

GEAR_SHIFT_SPEEDS = [2, 15, 30, 50, 80, 120]
TOP_GEAR = 6
CHANCE_OF_GEAR_SHIFT = 0.3
TICKS_PER_SECOND = 10.0
MAX_STEERING_ANGLE = 540.0


class TrafficSimulator:
    def __init__(self, mode):
        self.state = TrafficState()
        styles = {"stationary": StationaryDriving, "moving": MovingDriving}
        self._driving = styles[mode]()

    def _chance(self, parked_rate, moving_rate):
        rate = parked_rate if self._driving.parked else moving_rate
        return random.random() < rate

    def step(self):
        state = self.state
        state.tick += 1
        self._driving.step(state)
        self._update_steering()
        self._update_gearbox()
        self._update_lights()
        self._update_doors()
        self._update_climate()
        self._update_wheels()
        self._update_tyres()
        self._update_radio()

    def _update_steering(self):
        state = self.state
        if random.random() < 0.15:
            state.steering_target = random.uniform(-360, 360)
        previous = state.steering_angle
        gap = state.steering_target - previous
        angle = previous + gap * 0.1 + random.uniform(-2, 2)
        angle = max(-MAX_STEERING_ANGLE, min(MAX_STEERING_ANGLE, angle))
        state.steering_angle = angle
        state.steering_rate = (angle - previous) * TICKS_PER_SECOND

    def _update_gearbox(self):
        state = self.state
        wanted_gear = bisect.bisect_right(GEAR_SHIFT_SPEEDS, state.speed)
        if wanted_gear > state.gear and random.random() < CHANCE_OF_GEAR_SHIFT:
            state.gear += 1
        elif wanted_gear < state.gear and random.random() < CHANCE_OF_GEAR_SHIFT:
            state.gear -= 1
        state.gear = max(0, min(TOP_GEAR, state.gear))

        if state.speed >= 1.0:
            state.gear_lever = "D"
            return
        state.gear_lever = "P" if state.brake_on else "N"
        if random.random() < 0.02:
            state.gear_lever = "R"

    def _update_lights(self):
        lights = self.state.lights
        if self._chance(0.005, 0.03):
            lights.low = not lights.low
        if self._chance(0.002, 0.01):
            lights.high = not lights.high

        if lights.left or lights.right or lights.hazard:
            if random.random() < 0.2:
                lights.left = False
                lights.right = False
        elif self._chance(0.001, 0.01):
            setattr(lights, random.choice(["left", "right", "hazard"]), True)

        if lights.hazard:
            lights.left = True
            lights.right = True

    def _update_doors(self):
        doors = self.state.doors
        if self._chance(0.002, 0.02):
            door = random.choice(list(doors))
            doors[door] = not doors[door]

    def _update_climate(self):
        climate = self.state.climate
        if self._chance(0.005, 0.03):
            climate.air_conditioning = not climate.air_conditioning
        if self._chance(0.02, 0.1):
            fan = climate.fan + random.choice([-1, 1])
            climate.fan = max(0, min(7, fan))
        if self._chance(0.02, 0.08):
            set_temp = climate.set_temp + random.choice([-1, 1])
            climate.set_temp = max(16, min(30, set_temp))

    def _update_wheels(self):
        state = self.state
        base_speed = max(0.0, state.speed)
        for corner in CORNERS:
            wheel_speed = base_speed + random.uniform(-0.8, 0.8)
            state.wheel_speeds[corner] = max(0.0, wheel_speed)

    def _update_tyres(self):
        state = self.state
        for corner in CORNERS:
            pressure = state.tyre_pressures[corner] + random.uniform(-0.05, 0.05)
            state.tyre_pressures[corner] = max(24.0, min(45.0, pressure))
            change = random.choice([-1, 0, 1]) if random.random() < 0.2 else 0
            temperature = state.tyre_temps[corner] + change
            state.tyre_temps[corner] = max(-20, min(90, temperature))

    def _update_radio(self):
        radio = self.state.radio
        radio.volume = max(0, min(100, radio.volume + random.randint(-1, 1)))
        radio.button = random.choice([1, 2, 3]) if random.random() < 0.03 else 0
