#!/usr/bin/env python3
"""Convert selected public-domain 16x16 BDF glyphs to the LCD cell format.

The firmware stores large glyphs as columns split across two OLED pages.  This
tool deliberately has no dependency on the reverse-engineering handoff or on
the firmware source: it reads a Unicode/JIS BDF file and emits a deterministic
C initializer for the requested display width.
"""

from __future__ import annotations

import argparse
import gzip
import math
from pathlib import Path
from typing import TextIO


SOURCE_SIZE = 16
TOP_PADDING = 2
DEFAULT_GLYPHS = ("受", "信", "専", "用")

# A direct 16-to-7 reduction drops the one-pixel horizontal strokes that make
# these kanji recognizable.  These small cells are an independent,
# low-resolution reconstruction guided by the public-domain source glyphs.
READABLE_CELLS = {
    ("専", 7): (
        "...#...",
        "#######",
        "..###..",
        ".#.#.#.",
        "#######",
        ".#.#.#.",
        ".#.#.#.",
        "#######",
        "...#...",
        ".......",
    ),
    ("用", 7): (
        ".#####.",
        ".#.#.#.",
        ".#.#.#.",
        ".#####.",
        ".#.#.#.",
        ".#.#.#.",
        ".#.#.#.",
        "#.#.#.#",
        "#.#.#.#",
        ".......",
    ),
    ("専", 10): (
        "....#.....",
        "....#.....",
        "##########",
        "....#.....",
        "..######..",
        ".#..#..#..",
        "##########",
        ".#..#..#..",
        ".#..#..#..",
        "##########",
    ),
    ("用", 10): (
        ".########.",
        ".#..#...#.",
        ".#..#...#.",
        ".########.",
        ".#..#...#.",
        ".#..#...#.",
        ".#..#...#.",
        "#...#...#.",
        "#...#...#.",
        "#...#...#.",
    ),
}


def open_bdf(path: Path) -> TextIO:
    """Open a plain or gzip-compressed BDF as ASCII text."""

    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="ascii")
    return path.open("r", encoding="ascii")


def jis_codepoint(character: str) -> int:
    """Return the JIS row-cell code used by the legacy BDF files."""

    encoded = character.encode("iso2022_jp")
    if not (encoded.startswith(b"\x1b$B") and encoded.endswith(b"\x1b(B")):
        raise ValueError(f"{character!r} is not a single ISO-2022-JP character")
    return int.from_bytes(encoded[3:-3], "big")


def read_glyphs(path: Path, characters: tuple[str, ...]) -> dict[str, list[list[int]]]:
    """Read 16x16 bitmap rows for the requested characters from a BDF."""

    wanted = {jis_codepoint(character): character for character in characters}
    with open_bdf(path) as source:
        lines = source.read().splitlines()

    glyphs: dict[str, list[list[int]]] = {}
    for index, line in enumerate(lines):
        if not line.startswith("ENCODING "):
            continue
        code = int(line.split()[1])
        character = wanted.get(code)
        if character is None:
            continue

        end = next(
            (candidate for candidate in range(index, len(lines)) if lines[candidate] == "ENDCHAR"),
            len(lines),
        )
        bitmap_index = next(
            (candidate for candidate in range(index, end) if lines[candidate] == "BITMAP"),
            None,
        )
        if bitmap_index is None:
            raise ValueError(f"{path}: {character} has no BITMAP section")
        rows = lines[bitmap_index + 1 : bitmap_index + 1 + SOURCE_SIZE]
        if len(rows) != SOURCE_SIZE or any(len(row) != 4 for row in rows):
            raise ValueError(f"{path}: {character} does not have a 16x16 bitmap")
        glyphs[character] = [
            [(int(row, 16) >> (SOURCE_SIZE - 1 - x)) & 1 for x in range(SOURCE_SIZE)]
            for row in rows
        ]

    missing = [character for character in characters if character not in glyphs]
    if missing:
        raise ValueError(f"{path}: missing glyphs: {' '.join(missing)}")
    return glyphs


def resize_glyph(
    source: list[list[int]],
    width: int,
    active_height: int = 10,
    character: str | None = None,
) -> list[list[int]]:
    """Fit a 16x16 source into the shared 16-row LCD baseline contract.

    ``専`` and ``用`` use independent, hand-tuned low-resolution cells guided
    by the public-domain source so their defining strokes survive the narrow
    LCD columns. Other characters use deterministic coverage reduction. Both
    paths preserve the 10-row glyph area between two top and four bottom
    padding rows used by both firmware variants.
    """

    if len(source) != SOURCE_SIZE or any(len(row) != SOURCE_SIZE for row in source):
        raise ValueError("expected a 16x16 source glyph")
    if width <= 0 or active_height <= 0 or active_height > 16:
        raise ValueError("width must be positive and active_height must be 1..16")

    if active_height != 10:
        raise ValueError("the LCD contract currently requires a 10-row glyph area")
    top_padding = TOP_PADDING
    template = READABLE_CELLS.get((character, width))
    if template is not None:
        if len(template) != active_height or any(len(row) != width for row in template):
            raise ValueError("readable cell dimensions do not match the LCD contract")
        return (
            [[0] * width for _ in range(top_padding)]
            + [[int(pixel == "#") for pixel in row] for row in template]
            + [[0] * width for _ in range(16 - top_padding - active_height)]
        )
    result = [[0] * width for _ in range(16)]
    for target_y in range(active_height):
        source_y = min(
            SOURCE_SIZE - 1,
            round((target_y + 0.5) * SOURCE_SIZE / active_height - 0.5),
        )
        for target_x in range(width):
            source_x0 = math.floor(target_x * SOURCE_SIZE / width)
            source_x1 = math.ceil((target_x + 1) * SOURCE_SIZE / width)
            result[top_padding + target_y][target_x] = int(
                any(source[source_y][source_x] for source_x in range(source_x0, source_x1))
            )
    return result


def to_page_bytes(glyph: list[list[int]], width: int) -> list[int]:
    """Convert row-major pixels to two LSB-first OLED pages."""

    if len(glyph) != 16 or any(len(row) != width for row in glyph):
        raise ValueError("glyph dimensions do not match width x 16")
    return [
        sum(glyph[row][column] << (row - page * 8) for row in range(page * 8, (page + 1) * 8))
        for page in range(2)
        for column in range(width)
    ]


def format_initializer(character: str, bytes_: list[int]) -> str:
    """Format one C initializer without embedding host paths."""

    values = ", ".join(f"0x{value:02X}" for value in bytes_)
    return f"/* {character} */ {{ {values} }}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdf", type=Path, help="plain or gzip-compressed 16x16 BDF")
    parser.add_argument("--width", type=int, default=10, help="target glyph width (default: 10)")
    parser.add_argument(
        "--characters",
        default="".join(DEFAULT_GLYPHS),
        help="characters to extract in table order (default: 受信専用)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    characters = tuple(args.characters)
    glyphs = read_glyphs(args.bdf, characters)
    for character in characters:
        resized = resize_glyph(glyphs[character], args.width, character=character)
        print(format_initializer(character, to_page_bytes(resized, args.width)))


if __name__ == "__main__":
    main()
