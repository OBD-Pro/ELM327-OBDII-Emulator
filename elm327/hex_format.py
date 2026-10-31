def clamp_to_byte(value):
    return max(0, min(255, int(round(value))))


def to_byte(value):
    return [clamp_to_byte(value)]


def to_word(value):
    limited = max(0, min(0xFFFF, int(round(value))))
    return [limited >> 8, limited & 0xFF]


def split_word(value):
    return [(value >> 8) & 0xFF, value & 0xFF]


def to_fuel_trim(percent):
    return to_byte((percent + 100) * 1.28)


def hex_string(values):
    return " ".join(f"{value:02X}" for value in values)
