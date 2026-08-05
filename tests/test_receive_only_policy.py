"""Regression tests for the Japanese UV-K5 receive-only policy.

The firmware depends on ARM hardware and an unavailable cross-compiler in many
development environments. These tests therefore inspect the guarded source
paths directly. They are a policy regression check, not a replacement for an
ARM build or device-level RF validation.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    """Return one C function body, ignoring braces in comments and strings."""

    pattern = re.compile(
        rf"\b{re.escape(name)}\s*\([^;{{}}]*\)\s*\{{",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if match is None:
        raise AssertionError(f"function definition not found: {name}")

    opening_brace = source.find("{", match.start(), match.end())
    depth = 0
    state = "code"
    index = opening_brace

    while index < len(source):
        character = source[index]

        if state == "line_comment":
            if character == "\n":
                state = "code"
            index += 1
            continue

        if state == "block_comment":
            if source.startswith("*/", index):
                state = "code"
                index += 2
            else:
                index += 1
            continue

        if state in ("string", "char"):
            if character == "\\":
                index += 2
            elif (state == "string" and character == '"') or (
                state == "char" and character == "'"
            ):
                state = "code"
                index += 1
            else:
                index += 1
            continue

        if source.startswith("//", index):
            state = "line_comment"
            index += 2
            continue
        if source.startswith("/*", index):
            state = "block_comment"
            index += 2
            continue
        if character == '"':
            state = "string"
            index += 1
            continue
        if character == "'":
            state = "char"
            index += 1
            continue

        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1 : index]
        index += 1

    raise AssertionError(f"unclosed function body: {name}")


def _receive_only_branch(body: str) -> str:
    match = re.search(
        r"#ifdef\s+ENABLE_RX_ONLY(?P<branch>.*?)(?:#else|#endif)",
        body,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("ENABLE_RX_ONLY guard not found")
    return match.group("branch")


class ReceiveOnlyPolicyTest(unittest.TestCase):
    def test_build_defaults_enable_receive_only_mode(self) -> None:
        makefile = _read("Makefile")

        self.assertRegex(
            makefile,
            re.compile(r"^ENABLE_JAPANESE\s*\?=\s*1\s*$", re.MULTILINE),
        )
        self.assertIn("CFLAGS  += -DENABLE_JAPANESE", makefile)
        self.assertIn("AUTHOR_STRING_2 ?= Kris", makefile)
        self.assertIn("VERSION_STRING_2 ?= v4.3J", makefile)
        self.assertIn("EDITION_STRING ?= JP-RX-Only", makefile)
        self.assertIn("AUTHOR_STRING_2 ?= F4HWN", makefile)

        for option in ("ENABLE_VOX", "ENABLE_TX1750"):
            self.assertRegex(
                makefile,
                re.compile(rf"^{option}\s*\?=\s*0\s*$", re.MULTILINE),
            )
        self.assertRegex(
            makefile,
            re.compile(
                r"^ENABLE_FEAT_F4HWN_RX_TX_TIMER\s*\?=\s*0\s*$",
                re.MULTILINE,
            ),
        )
        self.assertIn("CFLAGS += -DENABLE_RX_ONLY", makefile)

    def test_receive_only_target_forces_tx_capable_options_off(self) -> None:
        makefile = _read("Makefile")
        options = (
            "ENABLE_AIRCOPY",
            "ENABLE_ALARM",
            "ENABLE_DTMF_CALLING",
            "ENABLE_EXTRA_UART_CMD",
            "ENABLE_F_CAL_MENU",
            "ENABLE_REGA",
            "ENABLE_TX1750",
            "ENABLE_TX_WHEN_AM",
            "ENABLE_UART_RW_BK_REGS",
            "ENABLE_VOX",
            "ENABLE_FEAT_F4HWN_RX_TX_TIMER",
        )

        for option in options:
            with self.subTest(option=option):
                self.assertRegex(
                    makefile,
                    re.compile(
                        rf"^override\s+{option}\s*:=\s*0\s*$",
                        re.MULTILINE,
                    ),
                )

    def test_ptt_toggles_monitor_only_on_press(self) -> None:
        body = _function_body(_read("app/generic.c"), "GENERIC_Key_PTT")
        branch = _receive_only_branch(body)

        self.assertRegex(
            branch,
            re.compile(r"ACTION_Monitor\s*\(\s*\)\s*;"),
        )
        self.assertRegex(branch, re.compile(r"goto\s+done\s*;"))
        self.assertEqual(body.count("ACTION_Monitor()"), 1)
        self.assertLess(body.index("if (!bKeyPressed"), body.index("#ifdef ENABLE_RX_ONLY"))
        self.assertLess(
            body.index("SCANNER_Stop()"), body.index("#ifdef ENABLE_RX_ONLY")
        )
        self.assertLess(
            body.index("CHFRSCANNER_Stop()"), body.index("#ifdef ENABLE_RX_ONLY")
        )
        self.assertLess(
            body.index("FM_PlayAndUpdate()"), body.index("#ifdef ENABLE_RX_ONLY")
        )

    def test_rx_mode_actions_cannot_restore_cross_band_tx(self) -> None:
        source = _read("app/action.c")

        rx_mode = _function_body(source, "ACTION_RxMode")
        rx_branch = _receive_only_branch(rx_mode)
        self.assertIn("gEeprom.CROSS_BAND_RX_TX = CROSS_BAND_OFF;", rx_branch)
        self.assertRegex(rx_branch, re.compile(r"\breturn\s*;"))

        main_only = _function_body(source, "ACTION_MainOnly")
        self.assertIn("gEeprom.CROSS_BAND_RX_TX = CROSS_BAND_OFF;", main_only)

        ptt = _function_body(source, "ACTION_Ptt")
        ptt_branch = _receive_only_branch(ptt)
        self.assertIn("gSetting_set_ptt_session = 0;", ptt_branch)
        self.assertRegex(ptt_branch, re.compile(r"\breturn\s*;"))

    def test_hidden_menu_marker_and_cursor_remain_valid(self) -> None:
        menu = _read("ui/menu.c")
        main = _read("main.c")

        self.assertIn('{"F Lock",      MENU_F_LOCK        },', menu)
        self.assertIn("UI_MENU_GetMenuIdx(MENU_F_LOCK)", main)
        self.assertNotRegex(
            main,
            re.compile(r"gMenuCursor\s*=\s*(?:67|68)\s*;"),
        )

    def test_high_level_transmit_entries_are_guarded(self) -> None:
        entries = (
            ("functions.c", "FUNCTION_Transmit"),
            ("functions.c", "FUNCTION_Select"),
            ("radio.c", "RADIO_SetTxParameters"),
            ("radio.c", "RADIO_PrepareTX"),
            ("radio.c", "RADIO_SendCssTail"),
            ("radio.c", "RADIO_SendEndOfTransmission"),
            ("radio.c", "RADIO_PrepareCssTX"),
        )

        for relative_path, name in entries:
            with self.subTest(function=name):
                body = _function_body(_read(relative_path), name)
                self.assertRegex(
                    body,
                    re.compile(r"^\s*#ifdef\s+ENABLE_RX_ONLY", re.MULTILINE),
                )
                self.assertRegex(
                    _receive_only_branch(body),
                    re.compile(r"\breturn\s*;"),
                )

    def test_bk4819_transmit_primitives_are_guarded(self) -> None:
        names = (
            "BK4819_PlaySingleTone",
            "BK4819_PrepareTransmit",
            "BK4819_TxOn_Beep",
            "BK4819_EnterDTMF_TX",
            "BK4819_ExitDTMF_TX",
            "BK4819_EnableTXLink",
            "BK4819_PlayDTMF",
            "BK4819_PlayDTMFString",
            "BK4819_TransmitTone",
            "BK4819_PlayCDCSSTail",
            "BK4819_PlayCTCSSTail",
            "BK4819_SendFSKData",
            "BK4819_PlayRoger",
            "BK4819_Enable_AfDac_DiscMode_TxDsp",
            "BK4819_PlayDTMFEx",
        )
        source = _read("driver/bk4819.c")

        for name in names:
            with self.subTest(function=name):
                body = _function_body(source, name)
                self.assertRegex(
                    body,
                    re.compile(r"^\s*#ifdef\s+ENABLE_RX_ONLY", re.MULTILINE),
                )
                self.assertRegex(
                    _receive_only_branch(body),
                    re.compile(r"\breturn\s*;"),
                )

    def test_japanese_big_font_and_menu_codes_are_enabled(self) -> None:
        font_header = _read("font.h")
        font_source = _read("font.c")
        helper = _read("ui/helper.c")
        menu = _read("ui/menu.c")
        readme = _read("README.md")

        self.assertIn("#define FONT_CODE_MAX 0xDF", font_header)
        self.assertRegex(font_header, re.compile(r"gFontBig\[191\]"))
        self.assertIn("gFontSmallJapanese[FONT_CODE_MAX - 0x7F + 1][6]", font_header)
        active_big_font = font_source.split("#else", 1)[1].split("#endif", 1)[0]
        self.assertEqual(
            len(re.findall(r"^\s*\{", active_big_font, re.MULTILINE)),
            191,
        )
        self.assertRegex(
            active_big_font,
            re.compile(r"\},\s*// '->',\s*\n\s*\{0x00.*//0x7F"),
        )
        hyphen = re.search(
            r"^\s*\{(?P<values>[^}]+)\},\s*// '-'\s*$",
            active_big_font,
            re.MULTILINE,
        )
        self.assertIsNotNone(hyphen)
        self.assertTrue(
            any(
                int(value, 0)
                for value in re.findall(r"0x[0-9A-Fa-f]+", hyphen.group("values"))
            )
        )
        self.assertIn("const uint8_t code = (uint8_t)pString[i];", helper)
        self.assertIn("is_extended_small", helper)
        self.assertIn("gFontSmallJapanese[code - 0x7F]", helper)
        self.assertIn("font == (const uint8_t *)gFontSmallBold", helper)
        self.assertIn("code <= FONT_CODE_MAX", helper)
        self.assertIn("const bool is_extended_big = code >= 0x7F;", helper)
        self.assertIn("(page0 >> 1) | (page1 << 7)", helper)
        self.assertIn("page1 >> 1", helper)
        small_table = font_source.split(
            "const uint8_t gFontSmallJapanese", 1
        )[1].split("};", 1)[0]
        for code in range(0x80, 0x98):
            entry = re.search(
                rf"\[0x{code:02X} - 0x7F\]\s*=\s*\{{([^}}]+)\}}",
                small_table,
            )
            self.assertIsNotNone(entry, hex(code))
            values = re.findall(r"0x[0-9A-Fa-f]+", entry.group(1)) if entry else []
            self.assertTrue(any(int(value, 0) for value in values), hex(code))
        for menu_id in ("MENU_STEP", "MENU_R_DCS", "MENU_R_CTCS", "MENU_TDR", "MENU_SQL"):
            self.assertIn(menu_id, menu)
        self.assertIn("0x80, 0x81, 0xD3", menu)
        self.assertIn("{{0xB7, '-', 0xDB, 0xAF, 0xB8}", menu)
        self.assertIn("{{0xB7, '-', 0x8E}", menu)
        self.assertNotIn("0xB7, 0xB0", menu)
        for label in ("BLTime", "BLMin", "BLMax", "LCDCtr", "LCDInv", "SMeter", "Sleep"):
            with self.subTest(label=label):
                self.assertIn(label, menu)
        for marker in (
            "v4.3J",
            "JP-RX-Only",
            "モニター機能に割り当てています",
            "76.0–95.0 MHz",
            "Flashing-the-firmware",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, readme)

    def test_fm_radio_is_fixed_to_the_japanese_receive_band(self) -> None:
        makefile = _read("Makefile")
        bk1080 = _read("driver/bk1080.c")
        fm = _read("app/fm.c")
        settings = _read("settings.c")
        menu = _read("app/menu.c")

        self.assertRegex(
            makefile,
            re.compile(r"^ENABLE_FMRADIO\s*\?=\s*1\s*$", re.MULTILINE),
        )
        self.assertIn("return 760;", _receive_only_branch(_function_body(bk1080, "BK1080_GetFreqLoLimit")))
        self.assertIn("return 950;", _receive_only_branch(_function_body(bk1080, "BK1080_GetFreqHiLimit")))
        self.assertRegex(
            _function_body(bk1080, "BK1080_SetFrequency"),
            re.compile(r"#ifdef\s+ENABLE_RX_ONLY.*?band\s*=\s*1\s*;", re.DOTALL),
        )
        self.assertNotIn("gEeprom.FM_Band++;", fm)
        self.assertIn("gEeprom.FM_Band = 1;", fm)
        self.assertIn("gEeprom.FM_Band = 1;", settings)
        self.assertIn("*pMax = 2;", menu)  # MAIN ONLY, DUAL RX, SINGLE


if __name__ == "__main__":
    unittest.main()
