import unittest

from elm327.adapter.replies import NO_DATA, START_MONITORING, UNKNOWN_COMMAND
from elm327.emulator import build_emulator
from elm327.vehicle.trouble_codes import TroubleCodes


class AdapterTestCase(unittest.TestCase):
    def setUp(self):
        self.emulator = build_emulator("idle")
        self.adapter = self.emulator.adapter
        self.adapter.handle_line("ATZ")

    def test_ignores_commands_before_reset(self):
        fresh = build_emulator("idle").adapter
        self.assertEqual(fresh.handle_line("010C"), "")

    def test_spaces_and_case_are_ignored(self):
        self.assertEqual(self.adapter.handle_line("at i"), "ELM327 Emulator")

    def test_unknown_at_command(self):
        self.assertEqual(self.adapter.handle_line("ATFOO"), UNKNOWN_COMMAND)

    def test_supported_pid_bitmap(self):
        self.assertEqual(self.adapter.handle_line("0100"), "41 00 9E 7F 98 13")

    def test_unsupported_pid(self):
        self.assertEqual(self.adapter.handle_line("0199"), NO_DATA)

    def test_header_for_missing_ecu_gets_no_data(self):
        self.adapter.handle_line("ATSH7E1")
        self.assertEqual(self.adapter.handle_line("010C"), NO_DATA)

    def test_stored_codes_use_multi_frame_with_headers(self):
        self.adapter.handle_line("ATH1")
        self.assertEqual(
            self.adapter.handle_line("03"),
            "7E8 10 08 43 03 04 20 04 42\r7E8 21 01 33 00 00 00 00 00",
        )

    def test_clearing_codes_keeps_permanent_codes(self):
        self.adapter.handle_line("04")
        self.assertEqual(self.emulator.trouble_codes.stored, [])
        self.assertEqual(self.emulator.trouble_codes.permanent, ["P0420"])

    def test_monitor_all_starts_monitoring(self):
        self.assertIs(self.adapter.handle_line("ATMA"), START_MONITORING)
        self.assertTrue(self.emulator.settings.monitoring)

    def test_custom_codes_build_freeze_frames(self):
        codes = TroubleCodes(stored=["U0100"], pending=[], permanent=[])
        adapter = build_emulator("idle", codes).adapter
        adapter.handle_line("ATZ")
        self.assertEqual(adapter.handle_line("020200"), "42 02 00 C1 00")


if __name__ == "__main__":
    unittest.main()
