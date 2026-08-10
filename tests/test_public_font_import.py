"""Tests for the independent public-font to LCD-cell conversion tool."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_converter():
    name = "k5_import_public_domain_bitmap_font"
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "import_public_domain_bitmap_font.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load import_public_domain_bitmap_font.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PublicFontImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.converter = load_converter()

    def test_jis_mapping_is_independent_of_firmware_code_page(self) -> None:
        self.assertEqual(self.converter.jis_codepoint("専"), 0x406C)
        self.assertEqual(self.converter.jis_codepoint("用"), 0x4D51)

    def test_resized_glyph_keeps_the_shared_baseline(self) -> None:
        source = [[0] * 16 for _ in range(16)]
        source[0][0] = 1
        source[15][15] = 1
        glyph = self.converter.resize_glyph(source, 10)
        self.assertEqual(len(glyph), 16)
        self.assertTrue(all(len(row) == 10 for row in glyph))
        self.assertEqual(sum(map(sum, glyph[:2])), 0)
        self.assertEqual(sum(map(sum, glyph[12:])), 0)
        self.assertEqual(len(self.converter.to_page_bytes(glyph, 10)), 20)

    def test_readable_reconstructions_preserve_welcome_strokes(self) -> None:
        source = [[0] * 16 for _ in range(16)]
        expected = {
            ("専", 7): bytes.fromhex("48 e8 58 fc 58 e8 48 02 03 02 07 02 03 02"),
            ("用", 10): bytes.fromhex(
                "00 fc 24 24 fc 24 24 24 fc 00 0e 01 00 00 0f 00 00 00 0f 00"
            ),
        }
        for (character, width), bitmap in expected.items():
            glyph = self.converter.resize_glyph(source, width, character=character)
            self.assertEqual(bytes(self.converter.to_page_bytes(glyph, width)), bitmap)


if __name__ == "__main__":
    unittest.main()
