"""Clean-room regression checks for the receive-only VFO band presets."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ReceiveBandPresetTest(unittest.TestCase):
    def test_eight_public_presets_have_requested_values(self) -> None:
        source = _read("app/rx_band_presets.c")
        expected = (
            ("AIR VHF", 11800000, 13700000, 2500, "MODULATION_AM", "BANDWIDTH_NARROW"),
            ("AIR UHF", 22500000, 40000000, 10000, "MODULATION_AM", "BANDWIDTH_NARROW"),
            ("TOKUSHO", 42205000, 42230000, 1250, "MODULATION_FM", "BANDWIDTH_NARROW"),
            ("FIRE", 46635000, 46655000, 1250, "MODULATION_FM", "BANDWIDTH_NARROW"),
            ("140 HAM", 14400000, 14600000, 2000, "MODULATION_FM", "BANDWIDTH_WIDE"),
            ("430 HAM", 43000000, 44000000, 2000, "MODULATION_FM", "BANDWIDTH_WIDE"),
            ("MAR SHIP", 15602500, 15742500, 2500, "MODULATION_FM", "BANDWIDTH_WIDE"),
            ("MAR SHORE", 16062500, 16202500, 2500, "MODULATION_FM", "BANDWIDTH_WIDE"),
        )
        rows = re.findall(
            r'\{"([A-Z0-9 ]+)",\s+(\d+)u,\s+(\d+)u,\s+(\d+)u,\s+'
            r'(MODULATION_[A-Z]+),\s+(BANDWIDTH_[A-Z]+)\}',
            source,
        )
        self.assertEqual(
            [
                (name, int(lower), int(upper), int(step), modulation, bandwidth)
                for name, lower, upper, step, modulation, bandwidth in rows
            ],
            list(expected),
        )

    def test_selection_keys_and_long_star_are_separate(self) -> None:
        main = _read("app/main.c")
        presets = _read("app/rx_band_presets.c")

        self.assertIn("RX_BAND_PRESETS_Open();", main)
        self.assertIn("RX_BAND_PRESETS_HandleKey(Key, bKeyPressed, bKeyHeld);", main)
        self.assertIn("GENERIC_Key_PTT(bKeyPressed);", main)
        open_branch = main[main.index("if (RX_BAND_PRESETS_IsOpen())") : main.index("#endif", main.index("if (RX_BAND_PRESETS_IsOpen())"))]
        self.assertIn("if (Key == KEY_PTT)", open_branch)
        self.assertIn("GENERIC_Key_PTT(bKeyPressed);", open_branch)
        self.assertIn("ACTION_Scan(false);// toggle scanning", main)
        self.assertIn("case KEY_MENU:", presets)
        self.assertIn("case KEY_STAR:", presets)
        self.assertIn("case KEY_EXIT:", presets)
        self.assertIn("case KEY_UP:", presets)
        self.assertIn("case KEY_DOWN:", presets)
        readme = _read("README.md")
        markers = (
            "受信バンドプリセット",
            "AIR VHF",
            "AIR UHF",
            "TOKUSHO",
            "FIRE",
            "140 HAM",
            "430 HAM",
            "MAR SHIP",
            "MAR SHORE",
            "| プリセット | 周波数範囲 | 変調 | 帯域幅 | step |",
            "| `AIR VHF` | 118.000-137.000 MHz | AM | narrow | 25 kHz |",
            "| `AIR UHF` | 225.000-400.000 MHz | AM | narrow | 100 kHz |",
            "| `TOKUSHO` | 422.050-422.300 MHz | FM | narrow | 12.5 kHz |",
            "| `FIRE` | 466.350-466.550 MHz | FM | narrow | 12.5 kHz |",
            "| `140 HAM` | 144.000-146.000 MHz | FM | wide | 20 kHz |",
            "| `430 HAM` | 430.000-440.000 MHz | FM | wide | 20 kHz |",
            "| `MAR SHIP` | 156.025-157.425 MHz | FM | wide | 25 kHz |",
            "| `MAR SHORE` | 160.625-162.025 MHz | FM | wide | 25 kHz |",
            "`STAR`を短押し",
            "`UP`／`DOWN`で循環選択",
            "`M`で現在のVFOへ適用",
            "`STAR`で適用後にその範囲をスキャン",
            "`EXIT`でキャンセル",
            "受信専用の操作",
            "送信は行いません",
            "デュアル受信中",
            "クロスバンド中",
            "メモリーチャンネル表示中",
            "既存の範囲指定中",
            "実行時状態",
            "VFO切替",
            "電源再投入",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, readme)

    def test_apply_is_runtime_only_and_receive_reconfiguration_is_used(self) -> None:
        source = _read("app/rx_band_presets.c")

        self.assertIn("gScanRangeStart = preset->lower;", source)
        self.assertIn("gScanRangeStop  = preset->upper;", source)
        self.assertIn("gTxVfo->freq_config_RX.Frequency = preset->lower;", source)
        self.assertIn("gTxVfo->freq_config_TX.Frequency = preset->lower;", source)
        self.assertIn("gTxVfo->WIDE_PLUS                = false;", source)
        self.assertIn("RADIO_SetModulation(gRxVfo->Modulation);", source)
        self.assertIn("gTxVfo->FrequencyReverse", source)
        self.assertIn('#include "settings.h"', source)
        self.assertNotRegex(source, re.compile(r"(?:ScreenChannel|FreqChannel|CHANNEL_SAVE)\s*="))
        self.assertIn("RADIO_SetupRegisters(true);", source)
        self.assertNotRegex(
            source,
            re.compile(r"^\s*(?:SETTINGS_Save|EEPROM_Write|gRequestSave)", re.MULTILINE),
        )
        self.assertNotRegex(source, re.compile(r"RADIO_PrepareTX|RADIO_SetTxParameters|BK4819_PrepareTransmit"))

    def test_cross_boundary_ranges_use_explicit_limits_and_validation(self) -> None:
        source = _read("app/rx_band_presets.c")
        scanner = _read("app/chFrScanner.c")

        self.assertIn("RX_freq_check(preset->lower)", source)
        self.assertIn("RX_freq_check(preset->upper)", source)
        self.assertIn("APP_SetFreqByStepAndLimits(gRxVfo, gScanStateDir, gScanRangeStart, gScanRangeStop)", scanner)
        self.assertIn("gEeprom.DUAL_WATCH != DUAL_WATCH_OFF", source)
        self.assertIn("gEeprom.CROSS_BAND_RX_TX != CROSS_BAND_OFF", source)

    def test_vfo_switch_clears_runtime_range_marker(self) -> None:
        common = _read("app/common.c")
        scanner = _read("app/chFrScanner.c")

        self.assertIn("RX_BAND_PRESETS_Reset();", common)
        self.assertIn("const bool presetRange = RX_BAND_PRESETS_IsApplied();", scanner)
        self.assertIn("&& !presetRange", scanner)

if __name__ == "__main__":
    unittest.main()
