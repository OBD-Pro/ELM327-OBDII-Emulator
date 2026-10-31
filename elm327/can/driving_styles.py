import math
import random
from abc import ABC, abstractmethod

BASE_IDLE_RPM = 750
MIN_MOVING_RPM = 600
MAX_MOVING_RPM = 5000
MAX_SPEED = 180.0
MAX_MOVING_PEDAL = 70.0
TARGET_SPEED_CYCLE_TICKS = 300
CHANCE_OF_BRAKE_TOGGLE = 0.03
CHANCE_OF_BRAKE_HELD = 0.9


class DrivingStyle(ABC):
    parked = False

    @abstractmethod
    def step(self, state):
        raise NotImplementedError


class StationaryDriving(DrivingStyle):
    parked = True

    def step(self, state):
        state.pedal += (3.0 - state.pedal) * 0.2 + random.uniform(-0.2, 0.2)
        state.pedal = max(0.0, min(8.0, state.pedal))

        if random.random() < CHANCE_OF_BRAKE_HELD:
            state.brake_on = True
        pressure = state.brake_pressure + random.randint(-2, 2)
        state.brake_pressure = max(10, min(60, pressure))

        state.speed = max(0.0, state.speed * 0.7)
        state.rpm = int(BASE_IDLE_RPM + random.uniform(-20, 20))


class MovingDriving(DrivingStyle):
    def step(self, state):
        target_speed = self._target_speed(state.tick)
        self._update_pedal(state, target_speed)
        self._update_brake(state, target_speed)
        self._update_speed(state)

        rpm = int(BASE_IDLE_RPM + state.speed * 35 + state.pedal * 6)
        state.rpm = max(MIN_MOVING_RPM, min(MAX_MOVING_RPM, rpm))

    def _target_speed(self, tick):
        position = (tick % TARGET_SPEED_CYCLE_TICKS) / TARGET_SPEED_CYCLE_TICKS
        return 60.0 + 20.0 * math.sin(2 * math.pi * position)

    def _update_pedal(self, state, target_speed):
        speed_gap = target_speed - state.speed
        target_pedal = max(0.0, min(MAX_MOVING_PEDAL, 0.8 * speed_gap + 15.0))
        noise = random.uniform(-0.3, 0.3)
        pedal = state.pedal + (target_pedal - state.pedal) * 0.15 + noise
        state.pedal = max(0.0, min(100.0, pedal))

    def _update_brake(self, state, target_speed):
        if random.random() < CHANCE_OF_BRAKE_TOGGLE:
            state.brake_on = not state.brake_on
        if state.brake_on and state.speed > target_speed + 5:
            pressure = state.brake_pressure + random.randint(5, 20)
            state.brake_pressure = min(255, pressure)
        else:
            pressure = state.brake_pressure - random.randint(3, 10)
            state.brake_pressure = max(0, pressure)

    def _update_speed(self, state):
        acceleration = state.pedal * 0.04
        braking = state.brake_pressure * 0.10
        drag = state.speed * 0.02
        speed = state.speed + acceleration - braking - drag
        state.speed = max(0.0, min(MAX_SPEED, speed))
