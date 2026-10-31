from elm327.can.traffic_frames import FRAME_BUILDERS, build_frame

TICK_SECONDS = 0.1
FRAMES_PER_TICK = 2


class TrafficStream:
    def __init__(self, simulator):
        self._simulator = simulator
        self._frame_ids = list(FRAME_BUILDERS)
        self._next_tick = 0.0

    def frames_due(self, now):
        if now < self._next_tick:
            return []
        self._next_tick = now + TICK_SECONDS
        return self.next_frames()

    def next_frames(self):
        self._simulator.step()
        state = self._simulator.state

        total = len(self._frame_ids)
        start = state.next_frame_index
        state.next_frame_index = (start + 1) % total

        positions = (start + offset for offset in range(FRAMES_PER_TICK))
        chosen_ids = (self._frame_ids[position % total] for position in positions)
        return [build_frame(can_id, state) for can_id in chosen_ids]
