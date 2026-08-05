"""Characterization checks for the receive-only feature extension.

These tests deliberately stay host-side: EEPROM and BK4819 access require the
target MCU.  They verify the storage contract, menu wiring, and the bounded
policy helpers that can be checked without RF hardware.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _compute_squelch(rssi: int, noise: int, glitch: int) -> tuple[int, ...]:
    clamp = lambda value, maximum: max(0, min(value, maximum))
    return (
        clamp(rssi + 8, 255),
        clamp(rssi + 4, 255),
        max(noise - 8, 0),
        max(noise - 4, 0),
        clamp(glitch + 4, 255),
        clamp(glitch + 8, 255),
    )


class ReceiveFeatureStateTest(unittest.TestCase):
    def test_extension_uses_unoccupied_global_page_and_has_crc_contract(self) -> None:
        source = _read("app/rx_feature_state.c")

        self.assertIn("#define RX_FEATURE_EEPROM_BASE       0x1F90u", source)
        self.assertIn("#define RX_FEATURE_GLOBAL_BYTES      8u", source)
        self.assertIn("#define RX_FEATURE_GLOBAL_CRC_OFFSET 6u", source)
        self.assertIn("RX_FEATURE_EEPROM_BASE, block, sizeof(block)", source)
        self.assertNotIn("0x1E00u", source)
        self.assertLess(0x1F90 + 8, 0x1FF0)
        self.assertIn("CRC16(block, RX_FEATURE_GLOBAL_CRC_OFFSET)", source)

    def test_bank_and_wide_plus_payloads_cover_all_memory_channels(self) -> None:
        source = _read("app/rx_feature_state.c")

        self.assertIn("static uint8_t sChannelBank[MR_CHANNEL_LAST + 1u]", source)
        self.assertIn("static uint8_t sWidePlus[(MR_CHANNEL_LAST + 1u + 7u) / 8u]", source)
        self.assertIn("RX_FEATURE_BANK_MAX 8u", _read("app/rx_feature_state.h"))
        self.assertIn("sChannelBank[channel] == sSelectedBank", source)
        self.assertIn("sWidePlus[channel >> 3]", source)
        self.assertIn("data[4] & 0x7Fu", source)
        self.assertIn("data[5] & 0x0Fu", source)

        # The RAM representation is one byte per channel and is committed to
        # the reserved high nibble of the channel record on demand.
        self.assertIn("static uint8_t sChannelBank[MR_CHANNEL_LAST + 1u]", source)
        self.assertEqual((200 + 7) // 8, 25)

    def test_wide_plus_is_distinct_from_legacy_one_bit_bandwidth(self) -> None:
        radio = _read("radio.c")
        settings = _read("settings.c")
        menu = _read("app/menu.c")
        ui = _read("ui/main.c")

        self.assertIn("bool           WIDE_PLUS;", _read("radio.h"))
        self.assertIn("RX_FEATURE_STATE_GetWidePlus(channel)", radio)
        self.assertIn("RX_FEATURE_STATE_SetWidePlus(Channel, pVFO->WIDE_PLUS)", settings)
        self.assertIn("RX_FEATURE_STATE_GetChannelBank(Channel)", settings)
        self.assertIn('"WIDE+"', _read("ui/menu.c"))
        self.assertIn("gTxVfo->WIDE_PLUS = gSubMenuSelection == 1", menu)
        self.assertIn("vfoInfo->WIDE_PLUS", ui)
        self.assertRegex(
            radio,
            re.compile(r"Bandwidth == BK4819_FILTER_BW_WIDE\)\s*\n\s*weakNoDifferent = gRxVfo->WIDE_PLUS"),
        )

    def test_squelch_policy_keeps_open_and_close_hysteresis(self) -> None:
        for values in ((40, 80, 90), (250, 127, 255), (0, 0, 0)):
            thresholds = _compute_squelch(*values)
            self.assertLessEqual(thresholds[1], thresholds[0])
            self.assertLessEqual(thresholds[2], 127)
            self.assertLessEqual(thresholds[3], 127)
            self.assertLessEqual(thresholds[4], thresholds[5])

        source = _read("app/rx_feature_state.c")
        self.assertIn("thresholds[0] = ClampU8((int)rssi + 8, 255);", source)
        self.assertIn("thresholds[2] = noise > 8", source)
        self.assertIn("RX_FEATURE_STATE_RequestAutoSquelch();", _read("radio.c"))
        self.assertIn("RX_FEATURE_STATE_CalibrateSquelch(gRxVfo);", _read("radio.c"))

    def test_single_vfo_and_bank_filter_are_connected_to_runtime_paths(self) -> None:
        radio = _read("radio.c")
        common = _read("app/common.c")
        scanner = _read("app/chFrScanner.c")
        menu = _read("app/menu.c")

        self.assertIn("RX_FEATURE_STATE_IsSingleVfo()", radio)
        self.assertIn("gEeprom.DUAL_WATCH = DUAL_WATCH_OFF;", radio)
        self.assertIn("gEeprom.CROSS_BAND_RX_TX = CROSS_BAND_OFF;", radio)
        self.assertIn("if (RX_FEATURE_STATE_IsSingleVfo())", common)
        self.assertIn("RX_FEATURE_STATE_ChannelMatchesBank(channel)", radio)
        self.assertIn("RX_FEATURE_STATE_IsBankFilterActive()", scanner)
        self.assertIn("MENU_RX_BANK_SET", menu)
        self.assertIn('"SINGLE"', _read("ui/menu.c"))

    def test_agc_guard_does_not_override_non_fm_agc_ownership(self) -> None:
        source = _read("app/rx_feature_state.c")

        self.assertIn("The radio reconfiguration path owns AGC outside ordinary FM.", source)
        self.assertNotIn("if (sAgcHold != 0)\n        {\n            BK4819_SetAGC(true);", source)
        self.assertIn("gFmRadioMode", source)

    def test_makefile_compiles_feature_state_only_for_receive_only_target(self) -> None:
        makefile = _read("Makefile")

        self.assertRegex(
            makefile,
            re.compile(
                r"ifeq \(\$\(ENABLE_RX_ONLY\),1\)\s+"
                r"\s*OBJS \+= app/rx_band_presets\.o\s+"
                r"\s*OBJS \+= app/rx_scan_skip\.o\s+"
                r"\s*OBJS \+= app/rx_feature_state\.o",
            ),
        )
        self.assertIn("ENABLE_RX_AGC_GUARD             ?= 1", makefile)
        self.assertIn("-DENABLE_RX_AGC_GUARD", makefile)


if __name__ == "__main__":
    unittest.main()
