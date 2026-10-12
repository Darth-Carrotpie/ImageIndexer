#!/usr/bin/env python3
"""Render ranked search cases into compact visual-review sheets."""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


THUMBNAIL = 170
TEXT_WIDTH = 330
ROW_HEIGHT = 245
CASES_PER_PAGE = 5


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ("arialbd.ttf", "Arial Bold.ttf") if bold else ("arial.ttf", "Arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def lines(draw: ImageDraw.ImageDraw, position: tuple[int, int], text: str,
          width: int, *, fill: str = "#202430", size: int = 17,
          bold: bool = False, spacing: int = 4) -> int:
    chosen = font(size, bold)
    wrapped = "\n".join(textwrap.wrap(text, width=max(8, width // max(7, size // 2))))
    draw.multiline_text(position, wrapped, font=chosen, fill=fill, spacing=spacing)
    box = draw.multiline_textbbox(position, wrapped, font=chosen, spacing=spacing)
    return box[3] - box[1]


def thumbnail(package: Path, relative: str) -> Image.Image:
    path = (package / relative).resolve(strict=True)
    if not path.is_relative_to(package.resolve()) or not path.is_file():
        raise ValueError(f"invalid thumbnail path: {relative}")
    with Image.open(path) as source:
        source.load()
        rendered = source.convert("RGBA")
    rendered.thumbnail((THUMBNAIL, THUMBNAIL), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (THUMBNAIL, THUMBNAIL), (242, 244, 248, 255))
    canvas.alpha_composite(rendered, ((THUMBNAIL - rendered.width) // 2,
                                      (THUMBNAIL - rendered.height) // 2))
    return canvas.convert("RGB")


def render(package: Path, ranked_path: Path, output: Path) -> list[Path]:
    if output.exists() or output.is_symlink():
        raise ValueError("--output must be a new directory")
    ranked = json.loads(ranked_path.read_text(encoding="utf-8"))
    cases = [case for case in ranked["cases"] if case["family"] != "exclusion_negative"]
    output.mkdir(parents=True)
    pages = []
    width = TEXT_WIDTH + 6 * (THUMBNAIL + 10) + 20
    for page_number, offset in enumerate(range(0, len(cases), CASES_PER_PAGE), 1):
        page_cases = cases[offset:offset + CASES_PER_PAGE]
        canvas = Image.new("RGB", (width, ROW_HEIGHT * len(page_cases)), "white")
        draw = ImageDraw.Draw(canvas)
        for row_number, case in enumerate(page_cases):
            top = row_number * ROW_HEIGHT
            if row_number:
                draw.line((0, top, width, top), fill="#b6bdc9", width=2)
            y = top + 10
            y += lines(draw, (10, y), f"{case['case_id']}  [{case['family']}]",
                       TEXT_WIDTH - 20, size=18, bold=True) + 5
            request = case["request"]
            query = request.get("text") or request.get("query") or json.dumps(
                request.get("require", {}), ensure_ascii=False)
            y += lines(draw, (10, y), query, TEXT_WIDTH - 20, size=17) + 6
            lines(draw, (10, y), "Required: " + "; ".join(case["required_visual_properties"]),
                  TEXT_WIDTH - 20, fill="#4b5260", size=14)
            displayed = case["results"][:5]
            known = case["known_suitable_ids"][0] if case["known_suitable_ids"] else None
            target = next((item for item in case["results"] if item["icon_id"] == known), None)
            if target is None and known:
                # Known targets outside the request window still exist in the candidate package.
                target = {"icon_id": known, "thumbnail_relative_path": f"thumbnails/{known}.png",
                          "title": "known suitable target"}
            columns = [(f"rank {index}", item) for index, item in enumerate(displayed, 1)]
            columns.append(("known target", target))
            for column, (label, item) in enumerate(columns):
                left = TEXT_WIDTH + column * (THUMBNAIL + 10)
                draw.text((left, top + 8), label, font=font(15, True), fill="#202430")
                if item is None:
                    draw.rectangle((left, top + 32, left + THUMBNAIL, top + 32 + THUMBNAIL),
                                   outline="#999", width=2)
                    continue
                canvas.paste(thumbnail(package, item["thumbnail_relative_path"]), (left, top + 32))
                title = item.get("title", item["icon_id"][-8:])
                lines(draw, (left, top + 206), title, THUMBNAIL, size=12)
        path = output / f"review-{page_number:03}.png"
        canvas.save(path, format="PNG", optimize=True)
        pages.append(path)
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--ranked-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        pages = render(args.package.resolve(strict=True),
                       args.ranked_results.resolve(strict=True), args.output.resolve())
        print(json.dumps({"pages": len(pages), "output": args.output.as_posix()}))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
