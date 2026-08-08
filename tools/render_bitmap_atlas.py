#!/usr/bin/env python3
"""Render C uint8_t bitmap/font arrays as an SVG atlas.

The source arrays are treated as OLED columns: bit 0 is drawn at the top.
This is an offline inspection tool and does not modify firmware sources or
participate in the build.
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path


DECL_RE = re.compile(
    r"\b(?:(?:static)\s+)?const\s+(?:uint8_t|unsigned\s+char)\s+"
    r"(?P<name>[A-Za-z_]\w*)(?P<dims>(?:\s*\[[^\]]*\])+?)\s*=\s*\{"
)
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])(?:0[xX][0-9A-Fa-f]+|0[bB][01]+|[0-9]+)[uUlL]*")
SHARED_GLYPH_LABELS = dict(zip(
    range(0x80, 0x98),
    "受信変調追加保存削除名長短押音電源更圧表示画面無",
))


@dataclass
class Array:
    name: str
    source: str
    dimensions: list[str]
    values: bytes
    occurrence: int
    element_width: int | None
    glyphs: list[dict] | None

    @property
    def label(self) -> str:
        suffix = f" [{self.occurrence}]" if self.occurrence > 1 else ""
        return f"{self.name}{suffix}"

    @property
    def category(self) -> str:
        if self.name.startswith("BITMAP_"):
            return "bitmap"
        if self.name.startswith("gFont"):
            return "font"
        return "array"

    @property
    def glyph_layout(self) -> tuple[int, int] | None:
        """Return (columns, pages) for fonts stored as two OLED pages."""
        if self.name in {"gFontBig", "gFontBigJapanese"} and self.element_width == 14:
            return (7, 2)
        if self.name == "gFontBigDigits" and self.element_width and self.element_width % 2 == 0:
            return (self.element_width // 2, 2)
        return None

    @property
    def glyph_data(self) -> list[bytes] | None:
        if not self.glyphs:
            return None
        return [bytes(glyph["bytes"]) for glyph in self.glyphs]


def remove_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"//.*", " ", text)


def remove_if_zero_blocks(text: str) -> str:
    """Remove disabled #if 0 branches while retaining their #else branch."""
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        if not re.match(r"^\s*#if\s+0\b", lines[index]):
            output.append(lines[index])
            index += 1
            continue
        depth = 1
        else_index: int | None = None
        cursor = index + 1
        while cursor < len(lines) and depth:
            line = lines[cursor]
            if re.match(r"^\s*#if(?:def|ndef)?\b", line):
                depth += 1
            elif re.match(r"^\s*#endif\b", line):
                depth -= 1
            elif depth == 1 and re.match(r"^\s*#else\b", line):
                else_index = cursor
            cursor += 1
        if depth:
            raise ValueError("unterminated #if 0 block")
        if else_index is not None:
            output.extend(lines[else_index + 1 : cursor - 1])
        index = cursor
    return "".join(output)


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"unterminated initializer at offset {opening}")


def eval_dimension(expression: str) -> int | None:
    expression = expression.strip()
    if not expression:
        return None
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None

    allowed = (ast.Expression, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        return None
    try:
        value = eval(compile(tree, "<dimension>", "eval"), {"__builtins__": {}}, {})
    except (ArithmeticError, NameError, TypeError, ValueError):
        return None
    return value if isinstance(value, int) and value > 0 else None


def eval_integer_expression(expression: str) -> int | None:
    expression = expression.strip()
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    allowed = (ast.Expression, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub,
               ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        return None
    try:
        value = eval(compile(tree, "<expression>", "eval"), {"__builtins__": {}}, {})
    except (ArithmeticError, NameError, TypeError, ValueError):
        return None
    return value if isinstance(value, int) else None


def parse_values(initializer: str) -> bytes:
    initializer = remove_comments(initializer)
    # C designated initializers such as [0x80 - 0x7F] = are metadata, not
    # bitmap bytes. Remove them before scanning literal byte values.
    initializer = re.sub(r"\[[^\]]*\]\s*=", " ", initializer)
    values: list[int] = []
    for match in NUMBER_RE.finditer(initializer):
        token = match.group(0).rstrip("uUlL")
        value = int(token, 0)
        if not 0 <= value <= 0xFF:
            raise ValueError(f"non-byte initializer {token}")
        values.append(value)
    if not values:
        raise ValueError("initializer contains no byte literals")
    return bytes(values)


def comment_label(comment: str) -> str | None:
    """Extract the human annotation after a glyph initializer."""
    parts = [part.strip() for part in comment.split("//") if part.strip()]
    if not parts:
        return None
    candidate = parts[-1]
    candidate = re.sub(r"^0[xX][0-9A-Fa-f]+\s*", "", candidate)
    candidate = re.sub(r"^['\"](.+)['\"]$", r"\1", candidate)
    candidate = candidate.strip(" ,")
    return candidate or None


def parse_glyph_annotations(name: str, initializer: str, element_width: int | None) -> list[dict] | None:
    """Return code-point and label annotations for Japanese glyph tables."""
    if name == "gFontBig" and element_width == 14:
        # The source keeps a disabled space glyph as a line comment.  Do not
        # count that brace as a real glyph, otherwise every code point shifts.
        initializer = re.sub(r"//\s*\{[^\r\n]*", "", initializer)
        entries = re.findall(r"\{([^{}]*)\}([^\r\n]*)", initializer)
        glyphs = []
        for index, (body, comment) in enumerate(entries):
            values = parse_values(body)
            if len(values) != element_width:
                continue
            code = 0x21 + index
            label = comment_label(comment) or SHARED_GLYPH_LABELS.get(code)
            if label is None and 0x20 < code < 0x7F:
                label = chr(code)
            glyphs.append({"code": code, "label": label, "bytes": values,
                           "occupied": any(values), "source_index": index})
        return glyphs

    if name not in {"gFontBigJapanese", "gFontSmallJapanese"}:
        return None

    entries = re.findall(r"\[([^\]]+)\]\s*=\s*\{([^{}]*)\}([^\r\n]*)", initializer)
    parsed = []
    max_code = 0x7F
    for expression, body, comment in entries:
        index = eval_integer_expression(expression)
        if index is None:
            continue
        code = index + 0x7F
        values = parse_values(body)
        if element_width is not None:
            values = values[:element_width] + bytes(max(0, element_width - len(values)))
        parsed.append((code, comment_label(comment) or SHARED_GLYPH_LABELS.get(code), values))
        max_code = max(max_code, code)
    if not parsed:
        return []
    glyphs = []
    for code in range(0x80, max_code + 1):
        entry = next((item for item in parsed if item[0] == code), None)
        values = entry[2] if entry is not None else bytes(element_width or 0)
        glyphs.append({"code": code, "label": entry[1] if entry else None,
                       "bytes": values, "occupied": any(values),
                       "source_index": code - 0x80})
    return glyphs


def parse_source(path: Path, occurrences: dict[str, int]) -> list[Array]:
    original = path.read_text(encoding="utf-8")
    text = remove_if_zero_blocks(original)
    arrays: list[Array] = []
    for match in DECL_RE.finditer(text):
        opening = text.find("{", match.start(), match.end())
        closing = matching_brace(text, opening)
        values = parse_values(text[opening + 1 : closing])
        dimensions = re.findall(r"\[([^\]]*)\]", match.group("dims"))
        width = eval_dimension(dimensions[-1]) if dimensions else None
        initializer = text[opening + 1 : closing]
        occurrences[match.group("name")] = occurrences.get(match.group("name"), 0) + 1
        arrays.append(
            Array(
                name=match.group("name"),
                source=path.as_posix(),
                dimensions=dimensions,
                values=values,
                occurrence=occurrences[match.group("name")],
                element_width=width,
                glyphs=parse_glyph_annotations(match.group("name"), initializer, width),
            )
        )
    return arrays


def xml_text(value: str) -> str:
    return html.escape(value, quote=True)


def draw_bytes(lines: list[str], data: bytes, x: int, y: int, scale: int, label: str) -> int:
    lines.append(f'<text x="{x}" y="{y - 7}" class="sub">{xml_text(label)}</text>')
    for column, value in enumerate(data):
        for row in range(8):
            fill = "#111111" if (value >> row) & 1 else "#f1f1f1"
            lines.append(
                f'<rect x="{x + column * scale}" y="{y + row * scale}" '
                f'width="{scale - 1}" height="{scale - 1}" fill="{fill}"/>'
            )
    return y + (8 * scale)


def draw_glyph_atlas(lines: list[str], array: Array, x: int, y: int, scale: int) -> int:
    layout = array.glyph_layout
    if layout is None:
        raise ValueError(f"no glyph layout for {array.name}")
    glyph_width, pages = layout
    glyph_size = glyph_width * pages
    glyph_data = array.glyph_data
    if glyph_data is None:
        if len(array.values) % glyph_size:
            raise ValueError(f"{array.label} has incomplete glyph data")
        glyph_data = [array.values[index:index + glyph_size]
                      for index in range(0, len(array.values), glyph_size)]
    glyph_count = len(glyph_data)
    per_row = 12 if glyph_width <= 7 else 8
    cell_width = glyph_width * scale + 24
    cell_height = pages * 8 * scale + 30
    for index in range(glyph_count):
        cell_x = x + (index % per_row) * cell_width
        cell_y = y + (index // per_row) * cell_height
        annotation = array.glyphs[index] if array.glyphs else None
        code_label = f"0x{annotation['code']:02X}" if annotation else f"g{index:03d}"
        if annotation and annotation.get("label"):
            code_label += f" {annotation['label']}"
        lines.append(f'<text x="{cell_x}" y="{cell_y - 5}" class="sub">{code_label}</text>')
        for page in range(pages):
            page_data = glyph_data[index][page * glyph_width : (page + 1) * glyph_width]
            for column, value in enumerate(page_data):
                for row in range(8):
                    fill = "#111111" if (value >> row) & 1 else "#f1f1f1"
                    lines.append(
                        f'<rect x="{cell_x + column * scale}" y="{cell_y + page * 8 * scale + row * scale}" '
                        f'width="{scale - 1}" height="{scale - 1}" fill="{fill}"/>'
                    )
    rows = (glyph_count + per_row - 1) // per_row
    return y + rows * cell_height


def make_svg(arrays: list[Array], scale: int, wrap: int) -> str:
    width = max(1200, 80 + wrap * scale + 700)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" viewBox="0 0 {width} 100">',
        '<style>.title{font:bold 24px sans-serif}.meta{font:14px sans-serif}.section{font:bold 17px sans-serif}.sub{font:12px Consolas,monospace}</style>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="32" y="36" class="title">C bitmap/font atlas</text>',
        '<text x="32" y="60" class="meta">Each byte is one OLED column; bit 0 is at the top. Source order and conditional variants are preserved.</text>',
    ]
    y = 98
    for array in arrays:
        dims = "".join(f"[{d}]" for d in array.dimensions)
        lines.append(
            f'<text x="32" y="{y}" class="section">{xml_text(array.label)} '
            f'({xml_text(array.category)}, {len(array.values)} bytes, {xml_text(dims)})</text>'
        )
        lines.append(
            f'<text x="32" y="{y + 20}" class="meta">source: {xml_text(array.source)}; '
            f'element width: {array.element_width or "inferred"}</text>'
        )
        y += 52
        if array.glyph_layout is not None:
            y = draw_glyph_atlas(lines, array, 48, y + 20, scale) + 42
        else:
            for chunk_index in range(0, len(array.values), wrap):
                chunk = array.values[chunk_index : chunk_index + wrap]
                draw_bytes(lines, chunk, 48, y + 20, scale, f"byte offset +0x{chunk_index:04X}")
                y += 8 * scale + 42
        y += 25
    lines[0] = lines[0].replace('viewBox="0 0 ' + str(width) + ' 100"', f'viewBox="0 0 {width} {y + 30}"')
    lines[2] = f'<rect width="100%" height="{y + 30}" fill="white"/>'
    lines.append(f'<text x="32" y="{y + 5}" class="meta">arrays: {len(arrays)}; generated offline from C sources</text>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, help="C source containing uint8_t arrays (repeatable)")
    parser.add_argument("--out", type=Path, default=Path("bitmap-atlas"), help="output directory")
    parser.add_argument("--scale", type=int, default=6, help="pixels per bitmap cell in SVG")
    parser.add_argument("--wrap", type=int, default=64, help="maximum columns per rendered strip")
    args = parser.parse_args()
    if args.scale < 2 or args.wrap < 1:
        raise SystemExit("--scale must be >= 2 and --wrap must be >= 1")

    root = Path.cwd()
    sources = args.source
    if not sources:
        candidates = [root / "bitmaps.c", root / "font.c", root / "App" / "bitmaps.c", root / "App" / "font.c", root / "App" / "japanese_font.c"]
        sources = [candidate for candidate in candidates if candidate.exists()]
    if not sources:
        raise SystemExit("no source supplied and no bitmaps.c/App/bitmaps.c found")

    arrays: list[Array] = []
    occurrences: dict[str, int] = {}
    for source in sources:
        source = source.resolve()
        if not source.is_file():
            raise SystemExit(f"source not found: {source}")
        arrays.extend(parse_source(source, occurrences))
    if not arrays:
        raise SystemExit("no uint8_t arrays found")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    inventory = []
    for array in arrays:
        layout = array.glyph_layout
        record = {
            "name": array.label,
            "category": array.category,
            "source": array.source,
            "dimensions": array.dimensions,
            "element_width": array.element_width,
            "size": len(array.values),
            "bytes_hex": array.values.hex(" "),
            "layout": "glyph-2page" if layout else "column-strip",
        }
        if layout:
            record["glyph_width"] = layout[0]
            record["glyph_pages"] = layout[1]
            record["glyph_count"] = len(array.glyphs) if array.glyphs else len(array.values) // (layout[0] * layout[1])
        if array.glyphs:
            record["glyphs"] = [
                {"code": f"0x{glyph['code']:02X}", "label": glyph["label"],
                 "occupied": glyph["occupied"],
                 "bytes_hex": bytes(glyph["bytes"]).hex(" ")}
                for glyph in array.glyphs
            ]
        inventory.append(record)
    (out / "bitmap_atlas_inventory.json").write_text(
        json.dumps({"sources": [str(path.resolve()) for path in sources], "arrays": inventory}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "bitmap_atlas.svg").write_text(make_svg(arrays, args.scale, args.wrap), encoding="utf-8")
    print(f"arrays: {len(arrays)}")
    print(f"svg: {out / 'bitmap_atlas.svg'}")
    print(f"inventory: {out / 'bitmap_atlas_inventory.json'}")


if __name__ == "__main__":
    main()
