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
        self.assertIn("0x98 専 (project-authored)", font)
        self.assertIn("0x99 用 (project-authored)", font)

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

    def test_txlock_is_not_compiled_into_rx_only_menu(self) -> None:
        header = read("ui/menu.h")
        menu = read("ui/menu.c")
        self.assertIn("!defined(ENABLE_RX_ONLY)", header)
        self.assertIn("#ifndef ENABLE_RX_ONLY\n        case MENU_TX_LOCK", menu)


if __name__ == "__main__":
    unittest.main()
