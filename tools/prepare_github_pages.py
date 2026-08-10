#!/usr/bin/env python3
"""Prepare a self-contained Jekyll source tree for GitHub Pages.

The repository keeps documentation as Markdown under ``docs/``.  This helper
adds front matter, rewrites internal Markdown links to the generated HTML
paths, and copies the user-facing root documents into the Pages tree.
It intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)\)")
ROOT_DOCUMENTS = ("README.md", "README.ja.md", "CHEATSHEET.ja.md", "DEVELOPMENT.md", "AGENTS.md")
EXTRA_DOCUMENTS = ("tools/chirp/README.ja.md",)
ROOT_STATIC_DOCUMENTS = ("NOTICE", "LICENSE", "tools/font_editor.html")


LAYOUT = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page.title | escape }} | WRX-JP</title>
  <link rel="stylesheet" href="{{ '/assets/pages.css' | relative_url }}">
</head>
<body>
  <header class="site-header">
    <div class="site-header-inner">
      <a class="site-title" href="{{ '/' | relative_url }}">WRX-JP</a>
      <span class="site-subtitle">日本語・受信専用ファームウェア</span>
    </div>
  </header>
  <main class="content">
    <nav class="breadcrumb"><a href="{{ '/' | relative_url }}">ドキュメント一覧</a> / {{ page.title | escape }}</nav>
    <article>{{ content }}</article>
  </main>
  <footer class="site-footer">このページはリポジトリのドキュメントから自動生成されています。</footer>
</body>
</html>
"""


CONFIG = """title: WRX-JP documentation
markdown: kramdown
kramdown:
  input: GFM
  hard_wrap: false
plugins: []
"""


def rewrite_markdown_links(line: str, flatten_docs: bool = False) -> str:
    """Point local Markdown links at the HTML emitted by Jekyll."""

    def replace(match: re.Match[str]) -> str:
        target = match.group(1)
        if target.startswith(("#", "http://", "https://", "mailto:")):
            return match.group(0)
        path, suffix = re.match(r"([^?#]*)([?#].*)?$", target).groups()
        original_path = path
        if path.startswith("docs/"):
            path = path[5:]
        if flatten_docs and path.startswith("../"):
            path = path[3:]
        if path.lower().endswith(".md"):
            path = path[:-3] + ".html"
        if path == original_path:
            return match.group(0)
        return "](" + path + (suffix or "") + ")"

    return MARKDOWN_LINK.sub(replace, line)


def add_front_matter(markdown: str, title: str, permalink: str) -> str:
    """Add deterministic Jekyll metadata to one Markdown page."""

    if markdown.startswith("---\n"):
        return markdown
    safe_title = title.replace("'", "''")
    return f"---\nlayout: default\ntitle: '{safe_title}'\npermalink: {permalink}\n---\n\n{markdown}"


def page_title(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def prepare_markdown(source: Path, destination: Path, permalink: str, flatten_docs: bool = False) -> None:
    text = source.read_text(encoding="utf-8")
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            lines.append(line)
            continue
        lines.append(line if in_fence else rewrite_markdown_links(line, flatten_docs))
    prepared = add_front_matter("".join(lines), page_title(text, source.stem), permalink)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(prepared, encoding="utf-8", newline="\n")


def copy_static_files(source_root: Path, destination_root: Path) -> None:
    for source in source_root.rglob("*"):
        if not source.is_file() or source.suffix.lower() == ".md":
            continue
        relative = source.relative_to(source_root)
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def prepare_pages_source(repo_root: Path, source_root: Path, destination_root: Path) -> None:
    """Create the source tree consumed by ``actions/jekyll-build-pages``."""

    if destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True)
    copy_static_files(source_root, destination_root)

    for source in source_root.rglob("*.md"):
        relative = source.relative_to(source_root)
        output_relative = relative.with_suffix(".html")
        prepare_markdown(source, destination_root / relative, "/" + output_relative.as_posix(), flatten_docs=True)

    for name in ROOT_DOCUMENTS + EXTRA_DOCUMENTS:
        source = repo_root / name
        if source.exists():
            relative = Path(name)
            prepare_markdown(source, destination_root / relative, "/" + relative.with_suffix(".html").as_posix())

    for name in ROOT_STATIC_DOCUMENTS:
        source = repo_root / name
        if source.exists():
            relative = Path(name)
            destination = destination_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    (destination_root / "_config.yml").write_text(CONFIG, encoding="utf-8", newline="\n")
    layout_directory = destination_root / "_layouts"
    layout_directory.mkdir(exist_ok=True)
    (layout_directory / "default.html").write_text(LAYOUT, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("docs"))
    parser.add_argument("--destination", type=Path, default=Path(".pages-source"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    source_root = (repo_root / args.source).resolve()
    destination_root = (repo_root / args.destination).resolve()
    if not source_root.is_dir():
        raise SystemExit(f"documentation source does not exist: {source_root}")
    prepare_pages_source(repo_root, source_root, destination_root)
    print(f"prepared GitHub Pages source: {destination_root}")


if __name__ == "__main__":
    main()
