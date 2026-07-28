# img2ascii — target implementation (Python)

Original Python port. Not a translation of `img2ascii/source/src` — it
implements the general, well-known "luminance -> character ramp" ASCII-art
technique independently, with its own character ramp (`@%#*+=-:. `, dense to
sparse) rather than the reference's ramp. JPEG/PNG decoding is delegated to
Pillow (a general-purpose image library — the reference itself relies on a
third-party decode library, stb_image, for the same reason); the actual
ASCII-rendering logic is original.

## Prerequisites

- Python 3.10+
- Pillow: `pip install pillow`

## Build

No build step — it's a Python script.

## Run

```bash
python3 img2ascii/target/img2ascii.py -i <image> -w <width> -p
```

Example (matches the reference demo command):

```bash
python3 img2ascii/target/img2ascii.py -i img2ascii/source/images/c.png -w 40 -p
```

## Flags

| Flag | Long form | Meaning |
|---|---|---|
| `-i` | `--input` | Input image path (required) |
| `-o` | `--output` | Also write the rendered output to a text file |
| `-w` | `--width` | Output width in characters (defaults to image width) |
| `-c` | `--chars` | Custom character ramp, ordered dense -> sparse |
| `-g` | `--grayscale` | Plain-text output, no ANSI color codes |
| `-r` | `--reverse` | Reverse the character ramp (for dark-background terminals) |
| `-p` | `--print` | Force printing to stdout (on by default if `-o` isn't given) |
| `-d` | `--debug` | Print conversion metadata to stderr |

## Validate

Volunteer-verified (Easy tier, no automated hash grading) — demonstrate it
rendering one of the sample images in `img2ascii/source/images/` during
review, e.g. `c.png`, `pikachu.jpg`, `mona_lisa.jpg`.

## Submit

```bash
source setup.sh
relang "python3 img2ascii/target/img2ascii.py"
```
