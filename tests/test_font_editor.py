"""Static checks for the dependency-free interactive font editor."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FontEditorTests(unittest.TestCase):
    def test_editor_contains_editing_and_export_controls(self) -> None:
        html = (ROOT / "tools" / "font_editor.html").read_text(encoding="utf-8")
        for marker in ("inventoryFile", "arraySelect", "glyphSelect", "grid", "copyC", "downloadPatch",
                       "layoutGuide", "BIG_TOP_PADDING", "BIG_BOTTOM_PADDING", "guide-top",
                       "guide-glyph", "guide-bottom", "欧文・日本語共通", "特大"):
            self.assertIn(marker, html)
        self.assertIn("bitmap_atlas_inventory.json", html)
        self.assertNotIn("C:" + "/Users", html)
        self.assertNotIn("C:" + "\\" + "Users", html)


if __name__ == "__main__":
    unittest.main()
