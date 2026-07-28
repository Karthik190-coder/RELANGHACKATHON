#!/usr/bin/env python3
"""Terminal clock with analog/digital modes, countdown, and tailing."""
import argparse
import math
import os
import signal
import struct
import sys
import time
import io

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    import fcntl
    import termios
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

# --- ANSI / Terminal Helpers ---
ESC = "\x1b"
RESET = f"{ESC}[0m"
HIDE_CURSOR = f"{ESC}[?25l"
SHOW_CURSOR = f"{ESC}[?25h"
MOUSE_TRACK_ON = f"{ESC}[?1000h{ESC}[?1002h{ESC}[?1003h{ESC}[?1006h"
MOUSE_TRACK_OFF = f"{ESC}[?1000l{ESC}[?1002l{ESC}[?1003l{ESC}[?1006l"
SAVE_CURSOR = f"{ESC}[s"
RESTORE_CURSOR = f"{ESC}[u"
CLEAR_SCREEN = f"{ESC}[2J"
HOME_CURSOR = f"{ESC}[H"
SYNC_START = f"{ESC}[?2026h"
SYNC_END = f"{ESC}[?2026l"
FULL_PIXEL = "\u2588"
LOWER_HALF = "\u2584"
BELL = "\a"


def write(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def write_at(x, y, s):
    write(f"{ESC}[{y+1};{x+1}H{s}")


def get_terminal_size():
    try:
        cols, rows = os.get_terminal_size()
        return cols, rows
    except Exception:
        return 80, 24


def rgb_fg(r, g, b):
    return f"{ESC}[38;2;{r};{g};{b}m"


def rgb_bg(r, g, b):
    return f"{ESC}[48;2;{r};{g};{b}m"


def basic_fg(code):
    if code < 8:
        return f"{ESC}[{30+code}m"
    return f"{ESC}[{82+code-8}m"


def basic_bg(code):
    if code < 8:
        return f"{ESC}[{40+code}m"
    return f"{ESC}[[{92+code-8}m"


def color_fg(r, g, b, truecolor=True):
    if truecolor:
        return rgb_fg(r, g, b)
    return basic_fg(nearest_ansi(r, g, b))


def color_bg(r, g, b, truecolor=True):
    if truecolor:
        return rgb_bg(r, g, b)
    return basic_bg(nearest_ansi(r, g, b))


ANSI_256_COLORS = [
    (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
    (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
    (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]


def nearest_ansi(r, g, b):
    best = 0
    best_dist = float("inf")
    for i, (cr, cg, cb) in enumerate(ANSI_256_COLORS):
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if d < best_dist:
            best_dist = d
            best = i
    return best


def parse_color(s, truecolor=True):
    """Parse color string: RRGGBB hex, named color, or hue,sat,lum.
    Returns (r, g, b) or None on error.
    """
    s = s.strip().lower()
    NAMES = {
        "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
        "yellow": (255, 255, 0), "cyan": (0, 255, 255), "magenta": (255, 0, 255),
        "white": (255, 255, 255), "black": (0, 0, 0), "orange": (255, 165, 0),
        "pink": (255, 192, 203), "gray": (128, 128, 128), "grey": (128, 128, 128),
    }
    if s in NAMES:
        return NAMES[s]
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            pass
    parts = s.split(",")
    if len(parts) == 3:
        try:
            h, sat, lum = float(parts[0]), float(parts[1]), float(parts[2])
            return hsl_to_rgb(h, sat, lum)
        except ValueError:
            pass
    return None


def hsl_to_rgb(h, s, l):
    """h in [0,1], s in [0,1], l in [0,1]."""
    if s == 0:
        v = int(l * 255)
        return (v, v, v)

    def hue2rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return (
        int(hue2rgb(p, q, h + 1 / 3) * 255),
        int(hue2rgb(p, q, h) * 255),
        int(hue2rgb(p, q, h - 1 / 3) * 255),
    )

# --- Bignum Display (7-segment style) ---
HEIGHT = 5
WIDTH = 4

_NUMBER_LINES_RAW = [
    " ━━", "┃  ┃", "", "┃  ┃", " ━━", "",                          # 0
    "", "   ┃", "", "   ┃", "", "",                                  # 1
    " ━━", "   ┃", " ━━", "┃", " ━━", "",                           # 2
    " ━━", "   ┃", " ━━", "   ┃", " ━━", "",                        # 3
    "", "┃  ┃", " ━━", "   ┃", "", "",                               # 4
    " ━━", "┃", " ━━", "   ┃", " ━━", "",                           # 5
    " ━━", "┃", " ━━", "┃  ┃", " ━━", "",                           # 6
    " ━━", "   ┃", "", "   ┃", "", "",                               # 7
    " ━━", "┃  ┃", " ━━", "┃  ┃", " ━━", "",                        # 8
    " ━━", "┃  ┃", " ━━", "   ┃", " ━━", "",                        # 9
    "", "", "::", "", "", "",                                         # : (colon)
    "", "", "..", "", "", "",                                         # . (dot/blink)
]

NUMBER_LINES = []
for i in range(len(_NUMBER_LINES_RAW)):
    extra = 1 if i < 10 * (HEIGHT + 1) else -1
    line = _NUMBER_LINES_RAW[i]
    target = WIDTH + extra
    padding = target - len(line)
    if padding > 0:
        line += " " * padding
    NUMBER_LINES.append(line)


def time_string(num_str, blink):
    lines = [""] * HEIGHT
    for ch in num_str:
        digit = 10  # colon
        if ch.isdigit():
            digit = int(ch)
        elif ch == ":":
            digit = 10
            if blink:
                digit = 11  # dot
        start = digit * (HEIGHT + 1)
        for i in range(HEIGHT):
            lines[i] += NUMBER_LINES[start + i]
    return "\n".join(lines)


# --- Duration formatting ---
def duration_string(duration_secs, with_seconds=True):
    d = duration_ddhhmm(duration_secs)
    if with_seconds:
        secs = int(duration_secs) % 60
        d += f":{secs:02d}"
    return d


def duration_ddhhmm(duration_secs):
    total_mins = int(duration_secs) // 60
    minutes = total_mins % 60
    hours = (int(duration_secs) // 3600) % 24
    if duration_secs >= 24 * 3600:
        days = int(duration_secs) // (24 * 3600)
        return f"{days:02d}:{hours:02d}:{minutes:02d}"
    if duration_secs >= 3600:
        return f"{hours:02d}:{minutes:02d}"
    return f"{minutes:02d}"


# --- Blend functions ---
def blend_nsrgb(c1, c2, t):
    """Non-linear (sRGB) blending."""
    def gamma(v):
        v = v / 255.0
        return v ** 2.2 if v > 0.04045 else v / 12.92

    def inv_gamma(v):
        v = max(0, min(1, v))
        return int((v ** (1 / 2.2) * 255) if v > 0.0031308 else (v * 12.92 * 255))

    r = inv_gamma(gamma(c1[0]) * (1 - t) + gamma(c2[0]) * t)
    g = inv_gamma(gamma(c1[1]) * (1 - t) + gamma(c2[1]) * t)
    b = inv_gamma(gamma(c1[2]) * (1 - t) + gamma(c2[2]) * t)
    return (r, g, b)


def blend_linear(c1, c2, t):
    return (
        int(c1[0] * (1 - t) + c2[0] * t),
        int(c1[1] * (1 - t) + c2[1] * t),
        int(c1[2] * (1 - t) + c2[2] * t),
    )


def disc_blend(cx, cy, radius, background, disc_color, aliasing, blend_fn, w, h):
    """Draw a circular disc with blended background colors behind the clock text.
    Matches Go's ansipixels.DiscBlendFN: iterate cells in bounding box,
    compute distance from center, apply aliasing soft-edge, blend bg↔disc color."""
    if radius <= 0:
        return
    out = []
    aliasing = max(0.0, min(1.0, aliasing))
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            cell_x = cx + dx
            cell_y = cy + dy
            if cell_x < 0 or cell_x >= w or cell_y < 0 or cell_y >= h:
                continue
            d = math.sqrt(dx * dx + dy * dy)
            if d > radius:
                continue
            if aliasing <= 0:
                alpha = 1.0
            else:
                nd = d / radius
                inner = 1.0 - aliasing
                if nd <= inner:
                    alpha = 1.0
                else:
                    alpha = max(0.0, (1.0 - nd) / aliasing)
            if alpha <= 0.004:
                continue
            alpha = min(1.0, alpha)
            r, g, b = blend_fn(background, disc_color, alpha)
            out.append(f"{ESC}[{cell_y + 1};{cell_x + 1}H{rgb_bg(r, g, b)} ")
    if out:
        write("".join(out))


# --- Bounce ---
def bounce_val(frame, maximum):
    m = frame % (2 * maximum)
    if m < maximum:
        return m
    return 2 * maximum - 1 - m


# --- Analog clock ---
def rotate_from_12(theta, radius):
    return int(round(-math.sin(theta) * radius)), int(round(-math.cos(theta) * radius))


def calculate_angle(max_v, time_val):
    return 2.0 * math.pi * (max_v - time_val) / max_v


def angle_coords(max_v, time_val, radius):
    return rotate_from_12(calculate_angle(max_v, time_val), radius)


def draw_line_pixels(pixels, sx, sy, x0i, y0i, color):
    """Bresenham line drawing collecting into pixels dict."""
    x1i = x0i + sx
    y0i_2 = y0i * 2
    y1i = y0i_2 + sy

    steep = abs(y1i - y0i_2) > abs(x1i - x0i)
    a0, a1 = x0i, x1i
    b0, b1 = y0i_2, y1i
    if steep:
        a0, b0 = b0, a0
        a1, b1 = b1, a1

    if a0 > a1:
        a0, a1 = a1, a0
        b0, b1 = b1, b0

    dx = a1 - a0
    dy = abs(b1 - b0)
    err = dx / 2.0
    y_step = 1 if b0 <= b1 else -1
    y = b0

    for x in range(a0, a1 + 1):
        if steep:
            pixels[(y, x)] = color
        else:
            pixels[(x, y)] = color
        err -= dy
        if err < 0:
            y += y_step
            err += dx


def draw_pixels_analog(pixels, background):
    """Draw collected pixels to terminal using half-block characters."""
    sorted_pixels = {}
    for (x, y), color in pixels.items():
        sorted_pixels[(x, y)] = color

    used = set()
    result = []
    for (x, y), color in sorted(sorted_pixels.items()):
        if (x, y) in used:
            continue
        if y % 2 == 0:
            lower = (x, y + 1)
            if lower in sorted_pixels:
                if sorted_pixels[lower] == color:
                    result.append((x, y // 2, color, color, FULL_PIXEL))
                else:
                    result.append((x, y // 2, color, sorted_pixels[lower], LOWER_HALF))
                used.add(lower)
            else:
                result.append((x, y // 2, background, color, LOWER_HALF))
        else:
            upper = (x, y - 1)
            if upper not in sorted_pixels:
                result.append((x, y // 2, color, background, LOWER_HALF))
    return result


def draw_analog_clock(cx, cy, radius, background, now, show_seconds, continuous, truecolor):
    """Draw analog clock with hour/minute/second hands."""
    sec = now.second
    minute = now.minute
    hour = now.hour

    if continuous:
        sec = (now.timestamp() * 1000000 % 60000000) / 1000000.0

    r = float(radius)
    sx, sy = angle_coords(60, sec, 0.9 * r)
    m = minute + sec / 60.0
    mx, my = angle_coords(60, m, 0.80 * r)
    hx, hy = angle_coords(12, hour % 12 + m / 60.0, 0.47 * r)

    pixels = {}
    if show_seconds:
        draw_line_pixels(pixels, sx, sy, cx, cy, (0x50, 0x80, 0x50))
    draw_line_pixels(pixels, mx, my, cx, cy, (0x2C, 0x59, 0xD4))
    draw_line_pixels(pixels, hx, hy, cx, cy, (255, 0xA7, 10))

    draw_commands = draw_pixels_analog(pixels, background)

    out = []
    for (x, y, fg, bg, ch) in draw_commands:
        out.append(f"{ESC}[{y+1};{x+1}H")
        if fg == bg:
            out.append(color_fg(*fg, truecolor))
            out.append(color_bg(*bg, truecolor))
            out.append(ch)
        else:
            out.append(color_fg(*fg, truecolor))
            out.append(color_bg(*bg, truecolor))
            out.append(ch)
    out.append(RESET)

    for n in range(1, 61):
        nx, ny = angle_coords(60, n % 60, r)
        if n % 5 == 0:
            m_val = n // 5
            if m_val >= 10:
                nx -= 1
            write_at(cx + nx, cy + (ny - 1) // 2, str(m_val))
        elif show_seconds:
            write_at(cx + nx, cy + (ny - 1) // 2, "\u00b7")

    write("".join(out))


# --- Config ---
class Config:
    def __init__(self):
        self.boxed = False
        self.color = ""
        self.color_box = ""
        self.analog = False
        self.inverse = False
        self.debug = False
        self.bounce = 0
        self.bounce_speed = 0
        self.frame = 0
        self.breath = False
        self.bcolor = (0, 0, 0)
        self.color_disc = None
        self.radius = 1.2
        self.fill_black = False
        self.aliasing = 0.8
        self.black_bg = ""
        self.blend_fn = blend_nsrgb
        self.text = ""
        self.top_right = False
        self.count_down = False
        self.end_time = None
        self.extra_newlines = True
        self.format = "3:04"
        self.track_mouse = False
        self.blink_enabled = True
        self.seconds = True
        self.now = time.time()
        self.aa = False
        self.continuous = False
        self.truecolor = True
        self.w = 80
        self.h = 24
        self.mx = 0
        self.my = 0
        self.tail = None
        self.color_output_truecolor = True

    def breath_color(self):
        spread = 100
        alpha = 0.15 + 0.85 * bounce_val(self.frame, spread) / spread
        return self.blend_fn((0, 0, 0), self.bcolor, alpha)

    def clear_screen(self):
        if self.fill_black:
            write(self.black_bg)
        write(CLEAR_SCREEN)

    def draw_at(self, x, y, s, now_dt):
        if self.aa:
            return  # AA mode handled separately

        if self.analog:
            radius = min(self.w // 2, self.h) - 1
            draw_analog_clock(
                self.w // 2, self.h // 2, radius, (0, 0, 0),
                now_dt, self.seconds, self.continuous, self.truecolor
            )
            return

        lines = s.split("\n")
        width = len(lines[0]) if lines else 0
        if self.boxed:
            width += 2
        height = len(lines)
        if self.boxed:
            height += 2

        if (x < 0 and y < 0) or self.analog:
            x = self.w // 2 + width // 2
            y = self.h // 2 + height // 2

        if self.top_right:
            x = self.w - 1
            y = height - 1

        x = min(x, self.w - 1)
        y = min(y, self.h - 1)

        if self.bounce_speed > 0 and self.bounce > 0:
            x = width - 1 + bounce_val(self.bounce, self.w - width + 1)
            y = height - 1 + bounce_val(self.bounce, self.h - height + 1)

        x += 1
        y += 1
        x = max(x, width)
        y = max(y, height)

        if self.color_disc is not None and self.color_disc != (0, 0, 0):
            mult = self.radius
            if self.breath:
                mult *= (1.0 + bounce_val(self.frame // 7, 10) / 15.0)
            disc_radius = 2 * int(round(mult * width / 4.0))
            if disc_radius <= height:
                disc_radius = (2 * (height + 1)) // 2
            cx = x - width // 2 - 1
            cy = y - height // 2 - 1
            disc_blend(cx, cy, disc_radius, (0, 0, 0), self.color_disc,
                       self.aliasing, self.blend_fn, self.w, self.h)

        prefix = ""
        if self.breath:
            r, g, b = self.breath_color()
            prefix = color_fg(r, g, b, self.truecolor)
        elif self.color:
            prefix = self.color
        if self.inverse:
            prefix = f"{ESC}[7m" + (self.color or "")

        suffix = ""
        if self.fill_black:
            prefix += self.black_bg
        else:
            suffix = RESET

        for i, line in enumerate(lines):
            write_at(x - width, y - height + i, prefix + line + suffix)

        if self.text:
            text_w = len(self.text)
            center = x - width // 2 - text_w // 2
            write_at(center, y + 1, self.text)


# --- Parse time string for --until ---
def parse_until(now_ts, s):
    """Parse datetime string like 'YYYY-MM-DD HH:MM:SS' or '3:05 pm'.
    now_ts is a timestamp (float seconds since epoch).
    Returns a timestamp in the future.
    """
    s = s.strip()
    now_local = time.localtime(now_ts)

    # Try "YYYY-MM-DD HH:MM:SS"
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        pass

    # Try "YYYY-MM-DD"
    try:
        t = time.strptime(s, "%Y-%m-%d")
        return time.mktime(t)
    except ValueError:
        pass

    # Try "HH:MM:SS"
    try:
        t = time.strptime(s, "%H:%M:%S")
        result = time.mktime(time.strptime(
            f"{now_local.tm_year}-{now_local.tm_mon:02d}-{now_local.tm_mday:02d} "
            f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}",
            "%Y-%m-%d %H:%M:%S"
        ))
        if result <= now_ts:
            result += 86400
        return result
    except ValueError:
        pass

    # Try "H:MM am/pm" or "H:MMAM/PM"
    for fmt in ["%I:%M %p", "%I:%M%p", "%I:%M %P", "%I:%M%P"]:
        try:
            t = time.strptime(s, fmt)
            result = time.mktime(time.strptime(
                f"{now_local.tm_year}-{now_local.tm_mon:02d}-{now_local.tm_mday:02d} "
                f"{t.tm_hour:02d}:{t.tm_min:02d}:00",
                "%Y-%m-%d %H:%M:%S"
            ))
            if result <= now_ts:
                result += 43200
                result2 = time.mktime(time.strptime(
                    f"{now_local.tm_year}-{now_local.tm_mon:02d}-{now_local.tm_mday:02d} "
                    f"{t.tm_hour:02d}:{t.tm_min:02d}:00",
                    "%Y-%m-%d %H:%M:%S"
                ))
                if result2 > now_ts:
                    result = result2
                else:
                    result += 43200
            return result
        except ValueError:
            continue

    raise ValueError(f"Invalid until time: {s}")


def parse_duration(s):
    """Parse duration like '5m', '1h30m', '2d', '1w', '30s'."""
    s = s.strip().lower()
    total = 0
    current_num = ""
    for ch in s:
        if ch.isdigit() or ch == '.':
            current_num += ch
        elif ch in ('d', 'w', 'h', 'm', 's'):
            val = float(current_num) if current_num else 0
            if ch == 'd':
                total += val * 86400
            elif ch == 'w':
                total += val * 604800
            elif ch == 'h':
                total += val * 3600
            elif ch == 'm':
                total += val * 60
            elif ch == 's':
                total += val
            current_num = ""
        else:
            current_num += ch
    if current_num:
        total += float(current_num)
    return total


# --- Raw mode handling ---
_orig_termios = None
_orig_mode = None


def enable_raw_mode():
    global _orig_termios, _orig_mode
    if HAS_TERMIOS:
        fd = sys.stdin.fileno()
        _orig_termios = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    elif HAS_MSVCRT:
        _orig_mode = True


def disable_raw_mode():
    global _orig_termios, _orig_mode
    if HAS_TERMIOS and _orig_termios is not None:
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, _orig_termios)
        _orig_termios = None
    elif HAS_MSVCRT:
        _orig_mode = None


def read_input_nonblocking(timeout_ms=100):
    """Read input with timeout. Returns bytes or empty."""
    if HAS_TERMIOS:
        import select
        r, _, _ = select.select([sys.stdin], [], [], timeout_ms / 1000.0)
        if r:
            try:
                return os.read(sys.stdin.fileno(), 4096)
            except (OSError, IOError):
                return b""
        return b""
    elif HAS_MSVCRT:
        result = b""
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ('\x00', '\xe0'):
                    ch2 = msvcrt.getwch()
                    result += ch.encode('latin-1') + ch2.encode('latin-1')
                else:
                    result += ch.encode('utf-8', errors='replace')
            else:
                time.sleep(0.01)
        return result
    return b""


def parse_all_mouse_events(data):
    """Parse ALL SGR mouse events from a data buffer. Returns list of (event, x, y).
    Matches Go's ansipixels library which parses all events per read batch.
    SGR protocol: btn=0 left press, btn=32 motion(drag), M=press m=release."""
    events = []
    if not data:
        return events
    s = data.decode('latin-1', errors='replace')
    i = 0
    while i < len(s):
        idx = s.find(f"{ESC}[<", i)
        if idx == -1:
            break
        end = s.find('M', idx + 3)
        if end == -1:
            end = s.find('m', idx + 3)
        if end == -1:
            break
        params = s[idx + 3:end]
        parts = params.split(';')
        if len(parts) >= 3:
            try:
                btn = int(parts[0])
                x = int(parts[1])
                y = int(parts[2])
                is_release = s[end] == 'm'
                is_press = s[end] == 'M'
                if is_release:
                    events.append(("release", x, y))
                elif is_press and btn == 0:
                    events.append(("left", x, y))
                elif is_press and btn == 32:
                    events.append(("drag", x, y))
                else:
                    events.append(("other", x, y))
            except ValueError:
                pass
        i = end + 1
    return events


# --- Main loop ---
def raw_mode_loop(cfg):
    num_str = ""
    blink = False
    prev_now = 0
    x, y = cfg.mx, cfg.my
    frame = 0
    prev = ""

    enable_raw_mode()

    try:
        write(HIDE_CURSOR)
        if not cfg.fill_black:
            write(f"{ESC}[48;2;0;0;0m")
        cfg.clear_screen()

        if cfg.bounce_speed <= 0 and not cfg.top_right and not cfg.analog:
            write(MOUSE_TRACK_ON)
            cfg.track_mouse = True

        while True:
            data = read_input_nonblocking(100)

            do_draw = cfg.breath or cfg.continuous

            # Process keyboard input
            if data:
                for byte in data:
                    if byte in (ord('q'), 3):
                        if cfg.count_down:
                            write_at(0, cfg.h - 3, f"Countdown aborted at {time.strftime(cfg.format)}\r\n")
                            return 1
                        return 0
                    elif byte in (ord('a'), ord('A')):
                        cfg.aa = not cfg.aa
                        cfg.analog = not cfg.aa
                        do_draw = True
                    elif byte in (ord('c'), ord('C')):
                        cfg.continuous = not cfg.continuous
                        do_draw = True

            # Process ALL mouse events from this read batch
            mouse_events = parse_all_mouse_events(data)
            had_left_click = False
            had_release = False
            for event, mx, my in mouse_events:
                cfg.mx = mx
                cfg.my = my
                if event == "left":
                    had_left_click = True
                elif event == "release":
                    had_release = True
            # Toggle tracking on quick click (press + release in same batch)
            # Matches Go: if ap.LeftClick() && ap.MouseRelease() { trackMouse = !trackMouse }
            if had_left_click and had_release:
                cfg.track_mouse = not cfg.track_mouse

            cfg.now = time.time()
            now_dt = time.localtime(cfg.now)

            if cfg.count_down:
                left = cfg.end_time - cfg.now
                if left < 0:
                    write(f"{BELL}Time's up reached at {time.strftime(cfg.format)}\r\n")
                    cfg.extra_newlines = False
                    return 0
                num_str = duration_string(left, cfg.seconds)
            else:
                num_str = time.strftime(cfg.format, now_dt)

            if num_str != prev:
                do_draw = True
            prev = num_str

            if not cfg.continuous:
                truncated = int(cfg.now)
            else:
                truncated = cfg.now

            if int(truncated) != int(prev_now) and cfg.blink_enabled:
                blink = not blink
                do_draw = True
            prev_now = truncated

            if cfg.bounce_speed > 0:
                if frame % cfg.bounce_speed == 0:
                    cfg.bounce += 1
                    do_draw = True
                frame += 1
            elif cfg.track_mouse and (cfg.mx != x or cfg.my != y):
                x, y = cfg.mx, cfg.my
                do_draw = True

            if do_draw:
                cfg.frame += 1
                write(SYNC_START)
                cfg.clear_screen()
                if cfg.analog:
                    radius = min(cfg.w // 2, cfg.h) - 1
                    now_dt_obj = time.localtime(cfg.now)
                    draw_analog_clock(
                        cfg.w // 2, cfg.h // 2, radius, (0, 0, 0),
                        time.localtime(cfg.now), cfg.seconds, cfg.continuous, cfg.truecolor
                    )
                else:
                    cfg.draw_at(x - 1, y - 1, time_string(num_str, blink), time.localtime(cfg.now))
                write(SYNC_END)

    finally:
        write(SAVE_CURSOR)
        if cfg.extra_newlines:
            write("\r\n\n\n\n")
        write(SHOW_CURSOR)
        write(MOUSE_TRACK_OFF)
        write(SYNC_END)
        write(RESET)
        disable_raw_mode()


# --- Stdin tail mode ---
def stdin_tail(cfg):
    enable_raw_mode()
    try:
        blink = False
        prev_now = 0
        prev = ""

        while True:
            now = time.time()

            if cfg.count_down:
                left = cfg.end_time - now
                if left < 0:
                    write(f"\n\n{BELL}Time's up reached at {time.strftime(cfg.format)}\r\n")
                    return 0
                num_str = duration_string(left, cfg.seconds)
            else:
                num_str = time.strftime(cfg.format, time.localtime(now))

            if num_str != prev:
                pass
            prev = num_str

            truncated = int(now)
            if truncated != int(prev_now) and cfg.blink_enabled:
                blink = not blink
            prev_now = truncated

            data = read_input_nonblocking(100)
            if data:
                for byte in data:
                    if byte in (ord('q'), 3):
                        return 0

            sys.stdout.buffer.write(data)
            write(SAVE_CURSOR)
            cfg.draw_at(-1, -1, time_string(num_str, blink), time.localtime(now))
            write(RESTORE_CURSOR)

    finally:
        disable_raw_mode()


# --- Detect truecolor ---
def detect_truecolor():
    colorterm = os.environ.get("COLORTERM", "").lower()
    if "truecolor" in colorterm or "24bit" in colorterm:
        return True
    term = os.environ.get("TERM", "").lower()
    if "256color" in term:
        return True
    return False


# --- Parse args and run ---
def main():
    truecolor_default = detect_truecolor()

    parser = argparse.ArgumentParser(description="Terminal clock")
    parser.add_argument("digits", nargs="?", default=None,
                        help="digits:digits... or - for stdin tailing")
    parser.add_argument("-bounce", type=int, default=0, help="Bounce speed")
    parser.add_argument("-24", dest="h24", action="store_true", help="24-hour format")
    parser.add_argument("-analog", action="store_true", help="Analog clock")
    parser.add_argument("-no-seconds", action="store_true", help="Don't show seconds")
    parser.add_argument("-no-blink", action="store_true", help="Don't blink the colon")
    parser.add_argument("-box", action="store_true", help="Draw rounded box outline")
    parser.add_argument("-color-disc", dest="color_disc", default="E0C020" if truecolor_default else "FFFFFF",
                        help="Color disc around time")
    parser.add_argument("-radius", type=float, default=1.2, help="Disc radius")
    parser.add_argument("-black-bg", action="store_true", help="Black background")
    parser.add_argument("-aliasing", type=float, default=0.8, help="Aliasing factor")
    parser.add_argument("-color-box", dest="color_box", default="", help="Color box")
    parser.add_argument("-color", default="red", help="Color: RRGGBB or name")
    parser.add_argument("-breath", action="store_true", help="Pulse color")
    parser.add_argument("-inverse", action="store_true", help="Inverse fg/bg")
    parser.add_argument("-debug", action="store_true", help="Debug mode")
    parser.add_argument("-truecolor", dest="truecolor", default=truecolor_default, type=lambda x: x.lower() in ('true', '1', 'yes'),
                        help="Use true color")
    parser.add_argument("-linear", action="store_true", help="Linear blending")
    parser.add_argument("-countdown", type=float, default=0, help="Countdown duration")
    parser.add_argument("-text", default="", help="Text below clock")
    parser.add_argument("-until", default="", help="Countdown until date/time")
    parser.add_argument("-tail", default="", help="Tail filename or - for stdin")
    parser.add_argument("-aa", action="store_true", help="Anti-aliased analog")
    parser.add_argument("-c", dest="continuous", action="store_true", help="Continuous update")
    parser.add_argument("-fps", type=float, default=30, help="Max FPS for continuous")

    args = parser.parse_args()

    cfg = Config()
    cfg.boxed = args.box
    cfg.inverse = args.inverse
    cfg.debug = args.debug
    cfg.breath = args.breath
    cfg.radius = args.radius
    cfg.fill_black = args.black_bg
    cfg.aliasing = args.aliasing
    cfg.seconds = not args.no_seconds
    cfg.bounce_speed = args.bounce
    cfg.blink_enabled = not args.no_blink
    cfg.extra_newlines = True
    cfg.analog = args.analog
    cfg.aa = args.aa
    cfg.continuous = args.continuous
    cfg.truecolor = args.truecolor

    if args.h24:
        cfg.format = "15:04"
    else:
        cfg.format = "3:04"

    if cfg.continuous and not cfg.analog and not cfg.aa:
        cfg.aa = True

    if args.linear:
        cfg.blend_fn = blend_linear
    else:
        cfg.blend_fn = blend_nsrgb

    # Parse colors
    if cfg.breath:
        c = parse_color(args.color)
        if c:
            cfg.bcolor = c
    else:
        c = parse_color(args.color)
        if c:
            cfg.color = color_fg(*c, cfg.truecolor)
        else:
            print(f"Color error: {args.color}", file=sys.stderr)
            return 1

    if args.color_box:
        c = parse_color(args.color_box)
        if c:
            cfg.color_box = color_fg(*c, cfg.truecolor)
            cfg.boxed = True

    if args.color_disc:
        c = parse_color(args.color_disc)
        if c:
            cfg.color_disc = c

    # Format with seconds
    if cfg.seconds:
        cfg.format += ":05"

    # Text
    show_text = args.text != "none"
    if show_text:
        cfg.text = args.text

    cfg.now = time.time()

    # Countdown
    if args.countdown > 0:
        cfg.count_down = True
        cfg.end_time = cfg.now + args.countdown

    if args.until:
        cfg.count_down = True
        try:
            cfg.end_time = parse_until(cfg.now, args.until)
        except ValueError as e:
            print(f"Invalid until time: {e}", file=sys.stderr)
            return 1

    if cfg.count_down and show_text and not cfg.text:
        to_str = time.strftime(cfg.format, time.localtime(cfg.end_time))
        if cfg.end_time - cfg.now >= 86400:
            to_str = f"{time.strftime('%Y-%m-%d', time.localtime(cfg.end_time))} {to_str}"
        extra = ""
        if not args.h24 and time.localtime(cfg.end_time).tm_hour >= 12:
            extra = " pm"
        cfg.text = "Countdown to " + to_str + extra

    # Black background
    if cfg.truecolor:
        cfg.black_bg = rgb_bg(0, 0, 0)
    else:
        cfg.black_bg = basic_bg(0)

    # Get terminal size
    cols, rows = get_terminal_size()
    cfg.w = cols
    cfg.h = rows

    # Digits argument
    if args.digits is not None:
        num_str = args.digits
        if num_str == "-":
            return stdin_tail(cfg)
        if not num_str or not num_str[0].isdigit():
            print("Usage: tclock [digits] or -", file=sys.stderr)
            return 1
        print(time_string(num_str, False))
        return 0

    if args.tail:
        cfg.top_right = True
        cfg.color_disc = None
        cfg.boxed = True
        if args.tail == "-":
            return stdin_tail(cfg)
        try:
            cfg.tail = open(args.tail, "r")
        except Exception as e:
            print(f"Error opening tail file: {e}", file=sys.stderr)
            return 1
        cfg.extra_newlines = False

    return raw_mode_loop(cfg)


if __name__ == "__main__":
    sys.exit(main())
