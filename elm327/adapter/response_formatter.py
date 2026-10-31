from elm327.adapter.replies import FramedReply
from elm327.hex_format import hex_string
from elm327.vehicle.trouble_codes import code_to_bytes

SINGLE_FRAME_LIMIT = 7
FIRST_FRAME_DATA = 6
FIRST_FRAME_FLAG = 0x10
NEXT_FRAME_FLAG = 0x20


def split_into_frames(payload):
    size = len(payload)
    frames = [
        [FIRST_FRAME_FLAG | (size >> 8), size & 0xFF] + payload[:FIRST_FRAME_DATA]
    ]
    remaining = payload[FIRST_FRAME_DATA:]
    sequence = 1
    while remaining:
        chunk = remaining[:SINGLE_FRAME_LIMIT]
        remaining = remaining[SINGLE_FRAME_LIMIT:]
        padding = [0x00] * (SINGLE_FRAME_LIMIT - len(chunk))
        frames.append([NEXT_FRAME_FLAG | (sequence & 0x0F)] + chunk + padding)
        sequence += 1
    return frames


class ResponseFormatter:
    def __init__(self, settings):
        self._settings = settings

    def payload_lines(self, payload):
        if len(payload) <= SINGLE_FRAME_LIMIT:
            return self._single_frame(payload)
        frames = split_into_frames(payload)
        if self._settings.headers:
            return self._frames_with_headers(frames)
        return self._numbered_frames(frames, len(payload))

    def _single_frame(self, payload):
        data = hex_string(payload)
        if not self._settings.headers:
            return data
        return f"{self._settings.response_id} {len(payload):02X} {data}"

    def _frames_with_headers(self, frames):
        response_id = self._settings.response_id
        return "\r".join(f"{response_id} {hex_string(frame)}" for frame in frames)

    def _numbered_frames(self, frames, size):
        lines = [f"{size:03X}"]
        for index, frame in enumerate(frames):
            data = frame[2:] if index == 0 else frame[1:]
            lines.append(f"{index & 0x0F:X}: {hex_string(data)}")
        return "\r".join(lines)

    def framed(self, payload):
        return FramedReply(self.payload_lines(payload))

    def code_list(self, service, codes):
        payload = [service, len(codes)]
        for code in codes:
            payload.extend(code_to_bytes(code))
        return self.framed(payload)

    def format(self, reply):
        settings = self._settings
        if settings.headers and not isinstance(reply, FramedReply):
            reply = self._add_frame_info(reply)

        lines = reply.split("\r")
        if settings.headers:
            lines = [self._with_header(line) for line in lines]
        if not settings.spaces:
            lines = [line.replace(" ", "") for line in lines]
        return "\r".join(lines)

    def _add_frame_info(self, reply):
        framed_lines = []
        for line in reply.split("\r"):
            if line.strip():
                payload = [int(value, 16) for value in line.split()]
                framed_lines.append(self.payload_lines(payload))
        return "\r".join(framed_lines)

    def _with_header(self, line):
        response_id = self._settings.response_id
        return line if line.startswith(response_id) else f"{response_id} {line}"
