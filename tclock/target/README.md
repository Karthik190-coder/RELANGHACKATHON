# tclock (Python port)

Terminal clock with large 7-segment digital display and analog mode. Ported from Go to Python 3.

| Field | Value |
|-------|-------|
| **Type** | Easy |
| **Score** | 100 |
| **Language** | Python 3 (stdlib only) |

## Prerequisites

- Python 3.8+

## Run

```bash
python3 tclock/target/tclock.py
```

## Options

| Flag | Description |
|------|-------------|
| `-analog` | Analog clock mode (Bresenham hand drawing) |
| `-aa` | Same as `-analog` (aa mode not separately implemented) |
| `-24` | 24-hour format |
| `-countdown DURATION` | Countdown mode (e.g. `5m`, `1h30m`, `2d`) |
| `-no-seconds` | Hide seconds |
| `-no-blink` | Disable colon blinking |
| `-box` | Draw a box around the clock |
| `-color COLOR` | Clock color: red, green, yellow, blue, magenta, cyan, white |
| `-h` | Print help |

## Examples

```bash
# Default digital clock
python3 tclock/target/tclock.py

# 24-hour format with box
python3 tclock/target/tclock.py -24 -box

# Analog clock
python3 tclock/target/tclock.py -analog

# Countdown 5 minutes
python3 tclock/target/tclock.py -countdown 5m

# Custom color, no seconds, no blink
python3 tclock/target/tclock.py -color green -no-seconds -no-blink
```

Press `q` or Ctrl-C to quit.

## Submit

```bash
relang "python3 tclock/target/tclock.py"
```