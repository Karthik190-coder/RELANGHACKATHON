#!/usr/bin/env python3
"""
img2ascii — JPEG/PNG to ASCII art converter (Python port for reLang).

Original implementation: this is NOT a port of img2ascii/source/src — it was
written independently in Python, following only the general well-known
"luminance -> character ramp" ASCII-art technique (a standard, widely used
approach with countless independent implementations), using a different
character ramp than the reference. Image decoding is delegated to Pillow,
a general-purpose image library, since JPEG/PNG decoding is a supporting
utility rather than the actual functionality being ported (ASCII rendering).

Usage:
    python3 img2ascii.py -i <image> [-w WIDTH] [-o OUTPUT] [-c CHARS]
                          [-g] [-r] [-p] [-d]

Flags:
    -i, --input      Path to input image (required)
    -o, --output     Path to also save the rendered output to a text file
    -w, --width      Target character-column width (defaults to image width)
    -c, --chars      Custom character ramp, ordered dense -> sparse
    -g, --grayscale  Plain-text output, no ANSI color codes
    -r, --reverse    Reverse the character ramp (useful on dark terminals)
    -p, --print      Force printing to stdout (default on if no -o given)
    -d, --debug      Print metadata about the conversion
"""

import argparse
import sys

from PIL import Image

# Dense -> sparse. Assumes a light terminal background by default (dark
# pixels get "heavier" glyphs); use --reverse for dark-background terminals.
DEFAULT_CHARS = "@%#*+=-:. "


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="img2ascii",
        description="Convert an image to ASCII art in the terminal.",
    )
    parser.add_argument("-i", "--input", required=True, help="input image path")
    parser.add_argument("-o", "--output", default=None, help="save output to this text file")
    parser.add_argument("-w", "--width", type=int, default=None, help="output width in characters")
    parser.add_argument("-c", "--chars", default=DEFAULT_CHARS, help="character ramp, dense to sparse")
    parser.add_argument("-g", "--grayscale", action="store_true", help="plain text, no color")
    parser.add_argument("-r", "--reverse", action="store_true", help="reverse the character ramp")
    parser.add_argument("-p", "--print", dest="do_print", action="store_true", help="force print to stdout")
    parser.add_argument("-d", "--debug", action="store_true", help="print conversion metadata")
    return parser


def load_and_scale(path: str, desired_width: int | None) -> Image.Image:
    img = Image.open(path).convert("RGB")
    orig_w, orig_h = img.size

    if desired_width is not None:
        if desired_width <= 0:
            sys.exit("Argument 'width' must be greater than 0")
        if desired_width > orig_w:
            sys.exit(f"Argument 'width' can not be greater than the original image width ({orig_w}px)")
        target_w = desired_width
        # Halve height relative to width scaling to compensate for terminal
        # character cells being roughly twice as tall as they are wide.
        target_h = max(1, round(orig_h * (target_w / orig_w) / 2))
    else:
        target_w = orig_w
        target_h = max(1, round(orig_h / 2))

    return img.resize((target_w, target_h), Image.LANCZOS)


def luminance(r: int, g: int, b: int) -> int:
    # Standard BT.601 luma weighting.
    return round(0.299 * r + 0.587 * g + 0.114 * b)


def char_for_intensity(intensity: int, chars: str) -> str:
    n = len(chars)
    idx = min(int(intensity * n / 256), n - 1)
    return chars[idx]


def render(img: Image.Image, chars: str, grayscale: bool, reverse: bool) -> str:
    if reverse:
        chars = chars[::-1]

    width, height = img.size
    pixels = img.load()
    lines = []

    if grayscale:
        for y in range(height):
            row_chars = []
            for x in range(width):
                r, g, b = pixels[x, y]
                row_chars.append(char_for_intensity(luminance(r, g, b), chars))
            lines.append("".join(row_chars))
        return "\n".join(lines) + "\n"

    out = []
    prev_rgb = None
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if (r, g, b) != prev_rgb:
                out.append(f"\x1b[38;2;{r};{g};{b}m")
                prev_rgb = (r, g, b)
            out.append(char_for_intensity(luminance(r, g, b), chars))
        out.append("\n")
    out.append("\x1b[0m")
    return "".join(out)


def main() -> None:
    args = build_arg_parser().parse_args()

    img = load_and_scale(args.input, args.width)
    output = render(img, args.chars, args.grayscale, args.reverse)
    width, height = img.size

    if args.debug:
        print(
            f"Input: {args.input}\n"
            f"Output: {args.output if args.output else 'stdout'}\n"
            f"Resolution: {width}x{height}\n"
            f"Characters ({len(args.chars)}): \"{args.chars}\"",
            file=sys.stderr,
        )

    do_print = args.do_print or args.output is None
    if do_print:
        sys.stdout.write(output)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)


if __name__ == "__main__":
    main()
