import unittest

from elm327.adapter.settings import AdapterSettings
from elm327.can.idle_frames import crc8, with_counter_and_crc
from elm327.can.monitor import format_frame
from elm327.emulator import build_emulator
from elm327.vehicle.pids import support_bitmap


class CanFilterTestCase(unittest.TestCase):
    def test_accepts_everything_without_filter(self):
        self.assertTrue(AdapterSettings().accepts(0x123))

    def test_filter_with_mask(self):
        settings = AdapterSettings(can_filter=0x7E8, can_mask=0x7FF)
        self.assertTrue(settings.accepts(0x7E8))
        self.assertFalse(settings.accepts(0x7E9))

    def test_monitor_address_matches_low_byte(self):
        settings = AdapterSettings()
        settings.start_monitoring(0xA0)
        self.assertTrue(settings.accepts(0x0A0))
        self.assertFalse(settings.accepts(0x0A8))


class FrameFormatTestCase(unittest.TestCase):
    def test_header_and_dlc(self):
        settings = AdapterSettings(headers=True, show_dlc=True)
        self.assertEqual(format_frame(0x0A0, [1, 2], settings), "0A0 2 01 02")

    def test_no_spaces(self):
        settings = AdapterSettings(spaces=False)
        self.assertEqual(format_frame(0x0A0, [1, 2], settings), "0102")


class IdleBusTestCase(unittest.TestCase):
    def test_counter_is_followed_by_crc(self):
        frame = with_counter_and_crc([1, 2, 3, 4, 5, 6], 3)
        self.assertEqual(frame[6], 3)
        self.assertEqual(frame[7], crc8(frame[:7]))

    def test_monitor_streams_lines(self):
        emulator = build_emulator("idle")
        emulator.settings.start_monitoring()
        lines = emulator.monitor.read_lines(now=0.0)
        lines += emulator.monitor.read_lines(now=2.0)
        self.assertTrue(lines)


class TrafficTestCase(unittest.TestCase):
    def test_moving_car_sends_two_frames_per_tick(self):
        source = build_emulator("moving").vehicle.open_can_source(0.0)
        self.assertEqual(len(source.frames_due(1.0)), 2)
        self.assertEqual(source.frames_due(1.05), [])


class BitmapTestCase(unittest.TestCase):
    def test_chain_bit_is_set_when_higher_pids_exist(self):
        self.assertEqual(support_bitmap(0x00, {0x01, 0x21}), "80 00 00 01")


if __name__ == "__main__":
    unittest.main()
