"""Host-side checks for the RX-only UI and reverse CTCSS path."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class ReceiveUiAndToneTests(unittest.TestCase):
    def test_help_is_clipped_cleared_and_time_sliced(self) -> None:
        menu = read("ui/menu.c")
        app = read("app/app.c")
        self.assertIn("#define UI_MENU_HELP_WIDTH 15u", menu)
        self.assertIn("memset(gFrameBuffer[6] + 18, 0, LCD_WIDTH - 18)", menu)
        self.assertIn("UI_MENU_TimeSlice500ms();", app)
        self.assertIn('return "scan list 1 member";', menu)
        self.assertIn('return "normal/reverse tone";', menu)

    def test_rx_only_welcome_is_terminated_and_uses_annotated_glyphs(self) -> None:
        welcome = read("ui/welcome.c")
        font = read("font.c")
        self.assertIn("char WelcomeString0[17];", welcome)
        self.assertIn("UI_SanitizeWelcomeString", welcome)
        self.assertIn("UI_RxOnlyWelcome0", welcome)
        self.assertIn("POWER_ON_DISPLAY_MODE_MESSAGE", welcome)
        self.assertIn("POWER_ON_DISPLAY_MODE_ALL", welcome)
        self.assertIn("UI_PrintString(WelcomeString0, 0, 127, 0, 8);", welcome)
        self.assertNotIn("code >= 0x98 && code <= 0x99", read("ui/helper.c"))
        self.assertIn("0x98 専 (Izumi 16-derived, low-resolution reconstruction)", font)
        self.assertIn("0x99 用 (Izumi 16-derived, low-resolution reconstruction)", font)
        self.assertIn("0x80 //受", font)
        self.assertIn("0x81 //信", font)
        self.assertIn("0x10,0x90,0x50,0x50,0xfc,0x50,0x50,0xd0,0x10,0x10", font)

    def test_reverse_ctcss_is_stored_displayed_and_inverted_at_runtime(self) -> None:
        dcs = read("dcs.h")
        radio = read("radio.c")
        menu = read("app/menu.c")
        ui = read("ui/menu.c")
        app = read("app/app.c")
        self.assertIn("CODE_TYPE_REVERSE_CONTINUOUS_TONE", dcs)
        self.assertIn("*pMax = ARRAY_SIZE(CTCSS_Options) * 2", menu)
        self.assertIn("pConfig->CodeType = CODE_TYPE_REVERSE_CONTINUOUS_TONE", menu)
        self.assertIn('sprintf(String, "R%u.%uHz"', ui)
        self.assertIn("static bool APP_CtcssMatch(void)", app)
        self.assertIn("CODE_TYPE_REVERSE_CONTINUOUS_TONE", radio)

    def test_txlock_menu_is_removed(self) -> None:
        header = read("ui/menu.h")
        menu = read("ui/menu.c")
        self.assertNotIn("MENU_TX_LOCK", header)
        self.assertNotIn("TXLock", menu)

    def test_rejected_receive_actions_are_visible_and_audible(self) -> None:
        presets = read("app/rx_band_presets.c")
        radio = read("radio.c")
        helper = read("ui/helper.c")
        self.assertIn("UI_DisplayUnavailable", presets)
        self.assertIn('return "RXExt OFF";', presets)
        self.assertIn('return "SCAN ACTIVE";', presets)
        self.assertIn("UI_DisplayUnavailable", helper)
        self.assertIn("VFO_STATE_TX_DISABLE", radio)
        self.assertIn("AUDIO_PlayBeep(BEEP_500HZ_60MS_DOUBLE_BEEP_OPTIONAL);", radio)

    def test_large_font_uses_one_source_coordinate_system(self) -> None:
        header = read("font.h")
        helper = read("ui/helper.c")
        self.assertIn("#define FONT_BIG_TOP_PADDING 2u", header)
        self.assertIn("#define FONT_BIG_BOTTOM_PADDING 4u", header)
        self.assertIn("source tables already contain display rows", helper)
        self.assertNotIn("FONT_BIG_JAPANESE_RENDER_SHIFT", helper)


if __name__ == "__main__":
    unittest.main()
