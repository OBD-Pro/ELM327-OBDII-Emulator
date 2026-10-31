def format_frame(can_id, data, settings):
    parts = []
    if settings.headers:
        is_standard_id = can_id <= 0x7FF
        parts.append(f"{can_id:03X}" if is_standard_id else f"{can_id:08X}")
        if settings.show_dlc:
            parts.append(str(len(data)))
    parts += [f"{value:02X}" for value in data]
    separator = " " if settings.spaces else ""
    return separator.join(parts)


class CanMonitor:
    def __init__(self, vehicle, settings):
        self._vehicle = vehicle
        self._settings = settings
        self._source = None

    @property
    def active(self):
        return self._settings.monitoring

    def restart(self):
        self._source = None

    def stop(self):
        self._settings.monitoring = False
        self._source = None

    def read_lines(self, now):
        if self._source is None:
            self._source = self._vehicle.open_can_source(now)
        return [
            format_frame(can_id, data, self._settings)
            for can_id, data in self._source.frames_due(now)
            if self._settings.accepts(can_id)
        ]
