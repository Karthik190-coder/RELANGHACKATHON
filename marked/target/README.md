# marked (Python Implementation)

This is the Python port of the `marked` Markdown-to-HTML parser.

## Prerequisites

- Python 3.10+ (tested on Ubuntu 24.04).
- The `regex` library (used for GFM/CommonMark Unicode character properties).

## Build

Install dependencies:
```bash
pip install regex
```

## Run

```bash
python3 target/main.py
```

## Validate (local)

```bash
cd relang && python3 -X utf8 validate.py "python3 -X utf8 ../target/main.py"
```

## Submit

```bash
source ../setup.sh
relang "python3 target/main.py"
```
