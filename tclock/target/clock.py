import math
import os
import re
import signal
import sys
import time

from segments import SevenSegmentRenderer
from renderer import TerminalRenderer


# ─── Duration helpers (for countdown) ────────────────────────────────

_DUR_RE = re.compile(r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$')


def parse_duration(s: str):
    m = _DUR_RE.match(s)
    if not m:
        return None
    days = int(m.group(1)) if m.group(1) else 0
    hours = int(m.group(2)) if m.group(2) else 0
    mins = int(m.group(3)) if m.group(3) else 0
    secs = int(m.group(4)) if m.group(4) else 0
    return days * 86400 + hours * 3600 + mins * 60 + secs


def duration_str(total_secs: int, show_secs: bool) -> str:
    total_secs = int(total_secs)
    days = total_secs // 86400
    rem = total_secs % 86400
    hours = rem // 3600
    rem %= 3600
    mins = rem // 60
    secs = rem % 60
    if days > 0:
        base = f'{days:02d}:{hours:02d}:{mins:02d}'
    elif hours > 0:
        base = f'{hours:02d}:{mins:02d}'
    else:
        base = f'{mins:02d}'
    if show_secs:
        base += f':{secs:02d}'
    return base


# ─── Bresenham line + half-pixel analog clock ───────────────────────

def _angle_coords(max_val: float, val: float, r: int):
    theta = 2.0 * math.pi * (max_val - val) / max_val
    return (int(round(-math.sin(theta) * r)),
            int(round(-math.cos(theta) * r)))


def _bresenham(x0: int, y0: int, x1: int, y1: int):
    y0 *= 2
    y1 *= 2
    points = set()
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        points.add((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return points


def _draw_analog(hour: int, minute: int, second: int, width: int, height: int) -> str:
    if height < 6:
        return ''
    cx = width // 2
    cy = height // 2
    radius = min(width // 2, height) - 1
    if radius < 3:
        return ''

    frac = second
    sx, sy = _angle_coords(60, frac, int(0.9 * radius))
    mx, my = _angle_coords(60, minute + frac / 60.0, int(0.8 * radius))
    hx, hy = _angle_coords(12, (hour % 12) + minute / 60.0, int(0.47 * radius))

    pixels = set()
    for px, py in _bresenham(cx, cy, cx + hx, cy + hy):
        if 0 <= px < width and 0 <= py < height * 2:
            pixels.add((px, py))
    for px, py in _bresenham(cx, cy, cx + mx, cy + my):
        if 0 <= px < width and 0 <= py < height * 2:
            pixels.add((px, py))
    for px, py in _bresenham(cx, cy, cx + sx, cy + sy):
        if 0 <= px < width and 0 <= py < height * 2:
            pixels.add((px, py))

    out = []
    for ty in range(height):
        row = ''
        for tx in range(width):
            top = (tx, ty * 2) in pixels
            bot = (tx, ty * 2 + 1) in pixels
            if top and bot:
                row += chr(0x2588)
            elif top:
                row += chr(0x2580)
            elif bot:
                row += chr(0x2584)
            else:
                row += ' '
        out.append(row)

    for n in range(1, 13):
        nx, ny = _angle_coords(60, n * 5, radius)
        label = str(n)
        nx_pos = cx + nx
        ny_pos = cy + (ny - 1) // 2
        if n >= 10:
            nx_pos -= 1
        if 0 <= ny_pos < height and 0 <= nx_pos < width - len(label):
            line = out[ny_pos]
            out[ny_pos] = line[:nx_pos] + label + line[nx_pos + len(label):]

    return '\n'.join(out)


# ─── Platform key reader ─────────────────────────────────────────────

_READER_MODE = None


def _init_reader():
    global _READER_MODE
    if not sys.stdin.isatty():
        _READER_MODE = 'pipe'
        return
    if os.name == 'nt':
        _READER_MODE = 'msvcrt'
    else:
        try:
            import atexit
            import termios
            import tty

            fd = sys.stdin.fileno()
            _READER_attrs = termios.tcgetattr(fd)

            def _restore():
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, _READER_attrs)
                except Exception:
                    pass

            atexit.register(_restore)
            tty.setraw(fd)
            _READER_MODE = 'unix'
        except Exception:
            _READER_MODE = 'pipe'


def _key_pressed() -> bool:
    if _READER_MODE == 'msvcrt':
        import msvcrt
        return msvcrt.kbhit()
    elif _READER_MODE == 'unix':
        import select
        try:
            return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
        except Exception:
            return False
    return False


def _read_key():
    if _READER_MODE == 'msvcrt':
        import msvcrt
        ch = msvcrt.getch()
        if ch == b'\x03':
            return '\x03'
        try:
            return ch.decode('ascii').lower()
        except Exception:
            return None
    elif _READER_MODE == 'unix':
        try:
            ch = sys.stdin.read(1)
            return ch.lower() if ch else None
        except Exception:
            return None
    return None


# ─── Clock class ─────────────────────────────────────────────────────

class Clock:
    def __init__(self, fmt24: bool = False, show_seconds: bool = True,
                 blink_enabled: bool = True, boxed: bool = False,
                 color: str = 'red', analog: bool = False,
                 countdown: int = 0):
        self.fmt24 = fmt24
        self.show_seconds = show_seconds
        self.blink_enabled = blink_enabled
        self.boxed = boxed
        self.color = color
        self.analog = analog
        self.countdown_seconds = countdown
        self.countdown_end = time.time() + countdown if countdown > 0 else None
        self.renderer = TerminalRenderer()
        self.segments = SevenSegmentRenderer()
        self._running = True
        self._blink = False
        self._prev_time_str = ''
        self._prev_now = 0

    def _build_format(self) -> str:
        if self.fmt24:
            fmt = '%H:%M'
        else:
            fmt = '%I:%M'
        if self.show_seconds:
            fmt += ':%S'
        return fmt

    def _get_time_str(self, now: float) -> str:
        if self.countdown_end:
            left = self.countdown_end - now
            if left <= 0:
                return None
            return duration_str(left, self.show_seconds)
        return time.strftime(self._build_format(), time.localtime(now))

    def _handle_key(self) -> bool:
        while _key_pressed():
            k = _read_key()
            if k in ('q', '\x03'):
                return False
        return True

    def _loop_digital(self):
        self.renderer.hide_cursor()
        try:
            while self._running:
                if not self._handle_key():
                    break

                now = time.time()
                now_trunc = int(now)

                time_str = self._get_time_str(now)
                if time_str is None:
                    self.renderer.write('\n\n\aTime\'s up!\n')
                    self.renderer.flush()
                    break

                needs_redraw = False
                if time_str != self._prev_time_str:
                    needs_redraw = True
                if now_trunc != self._prev_now and self.blink_enabled:
                    self._blink = not self._blink
                    needs_redraw = True

                if needs_redraw:
                    self._prev_time_str = time_str
                    self._prev_now = now_trunc
                    rendered = self.segments.render(time_str, self._blink)
                    lines = rendered.split('\n')
                    self.renderer.clear()
                    if self.boxed:
                        self.renderer.draw_boxed(lines, self.color)
                    else:
                        self.renderer.draw_centered(lines, 0, self.color)
                    self.renderer.flush()

                time.sleep(0.2)
        finally:
            self.renderer.show_cursor()
            self.renderer.reset_style()

    def _loop_analog(self):
        self.renderer.hide_cursor()
        try:
            while self._running:
                if not self._handle_key():
                    break
                t = time.localtime()
                self.renderer._detect_size()
                art = _draw_analog(t.tm_hour, t.tm_min, t.tm_sec,
                                   self.renderer.width, self.renderer.height)
                lines = art.split('\n')
                self.renderer.clear()
                self.renderer.draw_centered(lines, 0, self.color)
                self.renderer.flush()
                time.sleep(0.5)
        finally:
            self.renderer.show_cursor()
            self.renderer.reset_style()

    def run(self):
        _init_reader()

        def _on_sigint(sig, frame):
            self._running = False

        signal.signal(signal.SIGINT, _on_sigint)

        if self.analog:
            self._loop_analog()
        else:
            self._loop_digital()