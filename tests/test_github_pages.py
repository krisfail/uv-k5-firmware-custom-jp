"""Tests for the dependency-free GitHub Pages source builder."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("prepare_github_pages", ROOT / "tools" / "prepare_github_pages.py")
MODULE = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GitHubPagesTests(unittest.TestCase):
    def test_workflow_and_site_entrypoint_exist(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        for marker in ("actions/jekyll-build-pages@v1", "actions/upload-pages-artifact@v3", "actions/deploy-pages@v4"):
            self.assertIn(marker, workflow)
        self.assertIn("WRX-JP ドキュメント", index)

    def test_builder_adds_front_matter_and_rewrites_local_links(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "docs"
            source.mkdir()
            (source / "index.md").write_text(
                "# Index\n\n[README](../README.ja.md#build)\n\n```text\nREADME.md\n```\n",
                encoding="utf-8",
            )
            (root / "README.ja.md").write_text("# README\n", encoding="utf-8")
            destination = root / ".pages-source"
            MODULE.prepare_pages_source(root, source, destination)
            generated = (destination / "index.md").read_text(encoding="utf-8")
            self.assertIn("permalink: /index.html", generated)
            self.assertIn("README.ja.html#build", generated)
            self.assertIn("README.md", generated.split("```", 2)[1])
            self.assertTrue((destination / "README.ja.md").exists())
            self.assertTrue((destination / "AGENTS.md").exists() or not (root / "AGENTS.md").exists())
            self.assertTrue((destination / "_layouts" / "default.html").exists())
            self.assertTrue((destination / "_config.yml").exists())

    def test_link_rewriter_flattens_repository_docs_prefix(self) -> None:
        self.assertEqual(MODULE.rewrite_markdown_links("[guide](docs/guide.md#intro)"), "[guide](guide.html#intro)")
        self.assertEqual(MODULE.rewrite_markdown_links("[guide](../README.md)", flatten_docs=True), "[guide](README.html)")
        self.assertEqual(MODULE.rewrite_markdown_links("[editor](../tools/font_editor.html)", flatten_docs=True), "[editor](tools/font_editor.html)")


if __name__ == "__main__":
    unittest.main()
