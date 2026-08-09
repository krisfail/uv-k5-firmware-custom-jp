"""Host-side checks for the font atlas parser and generated inventory."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def load_atlas_module():
    spec = importlib.util.spec_from_file_location("k5_render_bitmap_atlas", ROOT / "tools" / "render_bitmap_atlas.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load render_bitmap_atlas.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FontAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.atlas = load_atlas_module()

    def parse_array(self, name: str):
        arrays = self.atlas.parse_source(ROOT / "font.c", {})
        return next(array for array in arrays if array.name == name)

    def test_big_font_keeps_every_source_slot_and_annotation(self) -> None:
        array = self.parse_array("gFontBig")
        self.assertIsNotNone(array.glyphs)
        glyphs = array.glyphs
        assert glyphs is not None
        self.assertEqual([glyph["code"] for glyph in glyphs], list(range(0x21, 0xE0)))
        self.assertEqual(len(glyphs), len(array.values) // 14)
        self.assertEqual(glyphs[0x98 - 0x21]["label"], "専 (project-authored)")
        self.assertFalse(glyphs[0x9A - 0x21]["occupied"])

    def test_small_japanese_font_materializes_sparse_slots(self) -> None:
        array = self.parse_array("gFontSmallJapanese")
        self.assertIsNotNone(array.glyphs)
        glyphs = array.glyphs
        assert glyphs is not None
        self.assertEqual([glyph["code"] for glyph in glyphs], list(range(0x80, 0xE0)))
        self.assertFalse(glyphs[0x9A - 0x80]["occupied"])

    def test_project_authored_large_glyphs_have_stable_readable_bitmaps(self) -> None:
        array = self.parse_array("gFontBig")
        glyphs = array.glyphs
        assert glyphs is not None
        expected = {
            0x98: bytes.fromhex("04 88 50 20 50 88 04 01 00 00 00 00 00 01"),
            0x99: bytes.fromhex("fc 54 54 fc 54 54 fc 0f 00 00 03 00 08 0f"),
        }
        for code, bitmap in expected.items():
            glyph = glyphs[code - 0x21]
            self.assertEqual(bytes(glyph["bytes"]), bitmap)
            self.assertTrue(glyph["occupied"])
        self.assertEqual(array.source, "font.c")

    def test_extra_large_japanese_table_is_compact_and_editable(self) -> None:
        array = self.parse_array("gFontJapaneseExtraLarge")
        self.assertEqual(array.glyph_layout, (10, 2))
        self.assertEqual([glyph["code"] for glyph in array.glyphs or []], [0x80, 0x81, 0x98, 0x99])
        self.assertTrue(all(not glyph["occupied"] for glyph in array.glyphs or []))

    def test_malformed_contiguous_glyph_is_rejected(self) -> None:
        initializer = "{" + ",".join(["0"] * 13) + "}"
        with self.assertRaises(ValueError):
            self.atlas.parse_glyph_annotations("gFontBig", initializer, 14)

    def test_markdown_inventory_is_human_readable(self) -> None:
        arrays = self.atlas.parse_source(ROOT / "font.c", {})
        report = self.atlas.make_markdown_inventory(arrays)
        self.assertIn("# フォント一覧", report)
        self.assertIn("| `gFontBig` | font |", report)
        self.assertIn("| `0x98` | 専 (project-authored) | 使用中 |", report)

    def test_svg_escapes_ascii_glyph_labels(self) -> None:
        array = self.parse_array("gFontBig")
        svg = self.atlas.make_svg([array], scale=2, wrap=64)
        ET.fromstring(svg)
        self.assertIn("0x26 &amp;", svg)
        self.assertIn("0x3C &lt;", svg)
        self.assertIn("0x98 専", svg)
        self.assertNotIn("project-authored", svg)
        self.assertNotIn("C:" + "/Users", svg)
        self.assertNotIn("C:" + "\\", svg)


if __name__ == "__main__":
    unittest.main()
