"""Host-side checks for the receive-only scan skip behavior."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkipListModel:
    def __init__(self, limit: int = 16) -> None:
        self.limit = limit
        self.values: list[int] = []

    def add(self, frequency: int) -> str:
        if frequency in self.values:
            return "duplicate"
        if len(self.values) >= self.limit:
            return "full"
        self.values.append(frequency)
        return "added"

    def contains(self, frequency: int) -> bool:
        return frequency in self.values


def next_unskipped(candidates: list[int], start: int, direction: int, skipped: set[int]) -> int | None:
    """Return one candidate after a bounded full-cycle search."""

    index = start
    for _ in range(len(candidates)):
        index = (index + direction) % len(candidates)
        if candidates[index] not in skipped:
            return candidates[index]
    return None


class ReceiveScanSkipTest(unittest.TestCase):
    def test_add_duplicate_and_full_are_distinct(self) -> None:
        skip = SkipListModel()

        self.assertEqual(skip.add(0), "added")
        self.assertEqual(skip.add(0), "duplicate")
        for frequency in range(1, 16):
            self.assertEqual(skip.add(frequency), "added")
        self.assertEqual(len(skip.values), 16)
        self.assertEqual(skip.add(16), "full")
        self.assertEqual(skip.values, list(range(16)))

    def test_frequency_values_are_compared_without_tolerance(self) -> None:
        skip = SkipListModel()

        self.assertEqual(skip.add(43000000), "added")
        self.assertTrue(skip.contains(43000000))
        self.assertFalse(skip.contains(43000001))

    def test_candidate_search_is_bounded_when_every_candidate_is_skipped(self) -> None:
        candidates = [11800000, 11802500, 11805000]
        skipped = set(candidates)

        self.assertIsNone(next_unskipped(candidates, 0, 1, skipped))
        self.assertIsNone(next_unskipped(candidates, 2, -1, skipped))
        self.assertEqual(next_unskipped(candidates, 0, 1, {11802500}), 11805000)

    def test_module_is_ram_only_and_has_the_public_capacity(self) -> None:
        header = (ROOT / "app/rx_scan_skip.h").read_text(encoding="utf-8")
        module_text = (ROOT / "app/rx_scan_skip.c").read_text(encoding="utf-8")

        self.assertIn("#define RX_SCAN_SKIP_MAX 16U", header)
        self.assertRegex(module_text, r"static\s+uint32_t\s+sSkippedFrequencies\[")
        self.assertIn("RX_SCAN_SKIP_DUPLICATE", module_text)
        self.assertIn("RX_SCAN_SKIP_FULL", module_text)
        self.assertNotRegex(module_text, r"EEPROM_|gEeprom|SETTINGS_Save|TX_.*API")

    def test_key_dispatch_only_intercepts_a_short_side1_scan_event(self) -> None:
        app_text = (ROOT / "app/app.c").read_text(encoding="utf-8")

        branch_start = app_text.index("else if (Key == KEY_SIDE1")
        branch_end = app_text.index("#endif\n#ifdef ENABLE_FEAT_F4HWN", branch_start)
        body = app_text[branch_start:branch_end]
        self.assertIn("Key == KEY_SIDE1", body)
        self.assertIn("const bool wasFKeyPressed = gWasFKeyPressed", app_text)
        self.assertIn("!wasFKeyPressed", body)
        self.assertLess(app_text.index("const bool wasFKeyPressed"), app_text.index("// cancel the F-key"))
        self.assertIn("gScanStateDir != SCAN_OFF", body)
        self.assertIn("!bKeyHeld && bKeyPressed", body)
        self.assertIn("RX_SCAN_SKIP_Add(gRxVfo->freq_config_RX.Frequency)", body)
        self.assertIn("GENERIC_Key_PTT(bKeyPressed)", app_text)

    def test_both_scan_paths_use_the_same_exact_frequency_filter(self) -> None:
        scanner_text = (ROOT / "app/chFrScanner.c").read_text(encoding="utf-8")

        self.assertGreaterEqual(scanner_text.count("RX_SCAN_SKIP_Contains(gRxVfo->freq_config_RX.Frequency)"), 2)
        self.assertIn("attempt <= RX_SCAN_SKIP_MAX", scanner_text)
        self.assertIn("const uint16_t maxAttempts", scanner_text)
        self.assertIn("(MR_CHANNEL_LAST + 1U) * SCAN_NEXT_NUM", scanner_text)
        self.assertIn("attempt < maxAttempts", scanner_text)
        self.assertIn("static void NextMemChannelOnce(void)", scanner_text)

    def test_memory_scan_rechecks_the_selected_bank_after_each_candidate(self) -> None:
        scanner_text = (ROOT / "app/chFrScanner.c").read_text(encoding="utf-8")

        next_once = scanner_text.index("NextMemChannelOnce();")
        bank_check = scanner_text.index(
            "RX_FEATURE_STATE_ChannelMatchesBank(gNextMrChannel)", next_once
        )
        skip_check = scanner_text.index(
            "RX_SCAN_SKIP_Contains(gRxVfo->freq_config_RX.Frequency)", bank_check
        )

        self.assertLess(next_once, bank_check)
        self.assertLess(bank_check, skip_check)

    def test_incoming_resume_does_not_relisten_a_skipped_frequency(self) -> None:
        scanner_text = (ROOT / "app/chFrScanner.c").read_text(encoding="utf-8")
        continue_start = scanner_text.index("void CHFRSCANNER_ContinueScanning(void)")
        continue_end = scanner_text.index("void CHFRSCANNER_Found(void)", continue_start)
        continue_text = scanner_text[continue_start:continue_end]

        self.assertIn(
            "!RX_SCAN_SKIP_Contains(gRxVfo->freq_config_RX.Frequency) &&",
            continue_text,
        )
        self.assertIn("APP_StartListening", continue_text)

    def test_normal_build_guards_the_optional_object(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertRegex(
            makefile,
            r"ifeq \(\$\(ENABLE_RX_ONLY\),1\)\s+\tOBJS \+= app/rx_band_presets\.o\s+\tOBJS \+= app/rx_scan_skip\.o",
        )


if __name__ == "__main__":
    unittest.main()
