import random
from dataclasses import dataclass
from typing import Callable

MAX_LAG_SECONDS = 0.1
COUNTER_MODULO = 16


@dataclass
class ScheduledMessage:
    can_id: int
    period: float
    build: Callable
    next_send: float
    counter: int

    def build_frame(self, sample):
        return self.can_id, self.build(sample, self.counter)

    def advance(self, now):
        self.next_send += self.period
        if self.next_send < now - MAX_LAG_SECONDS:
            self.next_send = now + self.period
        self.counter = (self.counter + 1) % COUNTER_MODULO


def message_table(builder):
    return [
        (0x0A0, 0.020, builder.engine_status),
        (0x0A8, 0.050, builder.wheel_speeds),
        (0x0B0, 0.050, builder.brakes_and_yaw),
        (0x0C4, 0.050, builder.steering),
        (0x1C0, 0.100, builder.transmission),
        (0x2A0, 0.100, builder.engine_air_and_fuel),
        (0x2B0, 0.100, builder.engine_ambient),
        (0x3A0, 0.100, builder.cluster),
        (0x300, 0.200, builder.airbag_heartbeat),
        (0x3B0, 0.200, builder.body),
        (0x3C0, 0.200, builder.climate),
        (0x4A0, 0.500, builder.tyre_pressures),
        (0x4B0, 0.500, builder.tyre_temperatures),
        (0x510, 1.000, builder.trip_computer),
        (0x5A0, 1.000, builder.clock),
    ]


class IdleCanBus:
    def __init__(self, now, car, builder):
        self._car = car
        self._messages = [
            ScheduledMessage(
                can_id=can_id,
                period=period,
                build=build,
                next_send=now + random.uniform(0, period),
                counter=random.randrange(COUNTER_MODULO),
            )
            for can_id, period, build in message_table(builder)
        ]

    def frames_due(self, now):
        ready = [m for m in self._messages if m.next_send <= now]
        if not ready:
            return []

        sample = self._car.sample()
        frames = []
        for message in sorted(ready, key=lambda m: m.can_id):
            frames.append(message.build_frame(sample))
            message.advance(now)
        return frames
