"""
Small terminal animation engine.

This is a from-scratch Python reimplementation of the entity/animation
concepts the original Perl asciiquarium relied on (the Term::Animation
CPAN module): named entities with a position, a z-depth, an optional
multi-frame shape/color-mask, simple velocity, collision detection, and
lifecycle callbacks. None of this is translated line-by-line from the
Perl module -- it's restructured around plain Python classes and a
curses screen buffer.

Coordinate system: x grows right, y grows down, z is "depth" where a
LARGER z is further from the viewer (drawn first / in the background)
and a SMALLER z is closer to the viewer (drawn last / in the
foreground). This matches the depth table used throughout creatures.py.
"""

from __future__ import annotations

import curses
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

Frame = str  # a single (possibly multi-line) block of ASCII art
DeathCallback = Callable[["Entity", "Engine"], None]
CollisionHandler = Callable[["Entity", "Entity", "Engine"], None]
UpdateHook = Callable[["Entity", "Engine"], None]

# Color letters used throughout the art masks. Uppercase = bold/bright.
_COLOR_MAP = {
    "c": curses.COLOR_CYAN,
    "r": curses.COLOR_RED,
    "y": curses.COLOR_YELLOW,
    "b": curses.COLOR_BLUE,
    "g": curses.COLOR_GREEN,
    "m": curses.COLOR_MAGENTA,
    "w": curses.COLOR_WHITE,
}


def _shape_size(text: str) -> Tuple[int, int]:
    """Return (width, height) of a block of ASCII art -- width is the
    longest line, height is the number of lines."""
    lines = text.split("\n")
    width = max((len(line) for line in lines), default=0)
    return width, len(lines)


class ColorPairs:
    """Lazily allocates and remembers curses color pairs for the
    letters used in our art masks and default colors."""

    def __init__(self) -> None:
        self._pairs: dict[str, int] = {}
        self._next_id = 1

    def _pair_for(self, fg: int) -> int:
        for letter, color in _COLOR_MAP.items():
            if color == fg:
                key = letter
                break
        else:
            key = str(fg)
        if key not in self._pairs:
            pair_id = self._next_id
            self._next_id += 1
            try:
                curses.init_pair(pair_id, fg, -1)
            except curses.error:
                curses.init_pair(pair_id, fg, curses.COLOR_BLACK)
            self._pairs[key] = pair_id
        return self._pairs[key]

    def attr_for_letter(self, letter: str) -> int:
        base = letter.lower()
        color = _COLOR_MAP.get(base, curses.COLOR_WHITE)
        attr = curses.color_pair(self._pair_for(color))
        if letter.isupper():
            attr |= curses.A_BOLD
        return attr

    def attr_for_name(self, name: str) -> int:
        """Accepts names like 'cyan', 'RED', 'white' etc (as used by
        default_color=...) in addition to single letters."""
        if len(name) <= 1:
            return self.attr_for_letter(name or "w")
        bold = name.isupper()
        color = _COLOR_MAP.get(name.lower()[0], curses.COLOR_WHITE)
        attr = curses.color_pair(self._pair_for(color))
        if bold:
            attr |= curses.A_BOLD
        return attr


@dataclass
class Entity:
    type: str
    x: float
    y: float
    z: int
    shape_frames: List[Frame] = field(default_factory=lambda: [""])
    color_frames: Optional[List[Frame]] = None
    default_color: str = "white"
    dx: float = 0.0
    dy: float = 0.0
    frame_period: float = 0.0  # seconds between animation frame advances
    transparent: str = " "
    physical: bool = False
    die_offscreen: bool = False
    die_time: Optional[float] = None
    die_frame: Optional[int] = None
    death_cb: Optional[DeathCallback] = None
    coll_handler: Optional[CollisionHandler] = None
    update_hook: Optional[UpdateHook] = None
    name: str = ""

    frame_index: int = 0
    _frame_clock: float = 0.0
    alive: bool = True

    def shape(self) -> str:
        return self.shape_frames[self.frame_index % len(self.shape_frames)]

    def color_mask(self) -> Optional[str]:
        if not self.color_frames:
            return None
        return self.color_frames[self.frame_index % len(self.color_frames)]

    def size(self) -> Tuple[int, int]:
        return _shape_size(self.shape())

    def bbox(self) -> Tuple[int, int, int, int]:
        w, h = self.size()
        return int(self.x), int(self.y), int(self.x) + w, int(self.y) + h

    def advance(self, dt: float) -> None:
        self.x += self.dx * dt * 10.0
        self.y += self.dy * dt * 10.0
        if self.frame_period > 0 and len(self.shape_frames) > 1:
            self._frame_clock += dt
            while self._frame_clock >= self.frame_period:
                self._frame_clock -= self.frame_period
                self.frame_index += 1

    def kill(self) -> None:
        self.alive = False


class Engine:
    """Owns the entity list, drives the animate/draw cycle, and offers
    the handful of spawn-time helpers creatures.py needs."""

    def __init__(self, stdscr) -> None:
        self.stdscr = stdscr
        self.entities: List[Entity] = []
        self.colors = ColorPairs()
        self.paused = False
        self.height, self.width = stdscr.getmaxyx()

    # -- screen -----------------------------------------------------
    def update_term_size(self) -> None:
        self.height, self.width = self.stdscr.getmaxyx()

    # -- entity management -------------------------------------------
    def add(self, entity: Entity) -> Entity:
        self.entities.append(entity)
        return entity

    def remove(self, entity: Entity) -> None:
        entity.alive = False

    def entities_of_type(self, type_: str) -> List[Entity]:
        return [e for e in self.entities if e.alive and e.type == type_]

    def clear(self) -> None:
        self.entities.clear()

    # -- main tick ----------------------------------------------------
    def animate(self, dt: float) -> None:
        if self.paused:
            return

        now = time.time()
        for e in self.entities:
            if not e.alive:
                continue
            e.advance(dt)
            if e.update_hook:
                e.update_hook(e, self)
            if e.die_time is not None and now >= e.die_time:
                e.kill()
            if e.die_frame is not None and e.frame_index >= e.die_frame:
                e.kill()
            if e.die_offscreen:
                x0, y0, x1, y1 = e.bbox()
                if x1 < 0 or x0 > self.width or y1 < 0 or y0 > self.height:
                    e.kill()

        self._handle_collisions()

        # run death callbacks and drop dead entities
        still_alive = []
        for e in self.entities:
            if e.alive:
                still_alive.append(e)
            elif e.death_cb:
                e.death_cb(e, self)
        self.entities = still_alive

    def _handle_collisions(self) -> None:
        physical = [e for e in self.entities if e.alive and e.physical]
        n = len(physical)
        for i in range(n):
            a = physical[i]
            if not a.coll_handler:
                continue
            ax0, ay0, ax1, ay1 = a.bbox()
            for j in range(n):
                if i == j:
                    continue
                b = physical[j]
                bx0, by0, bx1, by1 = b.bbox()
                if ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0:
                    a.coll_handler(a, b, self)

    # -- rendering ------------------------------------------------------
    def draw(self) -> None:
        h, w = self.height, self.width
        char_buf = [[" "] * w for _ in range(h)]
        attr_buf = [[0] * w for _ in range(h)]

        # Paint back-to-front: larger z (background) first, smaller z
        # (foreground) last, so foreground entities occlude background
        # ones wherever their glyphs are non-transparent.
        for e in sorted((e for e in self.entities if e.alive), key=lambda e: -e.z):
            shape = e.shape()
            mask = e.color_mask()
            default_attr = self.colors.attr_for_name(e.default_color)
            ox, oy = int(e.x), int(e.y)
            mask_lines = mask.split("\n") if mask else None
            for row, line in enumerate(shape.split("\n")):
                sy = oy + row
                if sy < 0 or sy >= h:
                    continue
                mask_line = mask_lines[row] if mask_lines and row < len(mask_lines) else ""
                for col, ch in enumerate(line):
                    if ch == e.transparent:
                        continue
                    sx = ox + col
                    if sx < 0 or sx >= w:
                        continue
                    char_buf[sy][sx] = ch
                    mch = mask_line[col] if col < len(mask_line) else " "
                    if mch != " ":
                        attr_buf[sy][sx] = self.colors.attr_for_letter(mch)
                    else:
                        attr_buf[sy][sx] = default_attr

        self.stdscr.erase()
        for y in range(h):
            row_chars = char_buf[y]
            row_attrs = attr_buf[y]
            x = 0
            while x < w:
                attr = row_attrs[x]
                start = x
                chunk = []
                while x < w and row_attrs[x] == attr:
                    chunk.append(row_chars[x])
                    x += 1
                text = "".join(chunk)
                # avoid writing into the terminal's very last cell,
                # which makes some curses implementations scroll
                if y == h - 1 and start + len(text) >= w:
                    text = text[: max(0, w - start - 1)]
                if text:
                    try:
                        self.stdscr.addstr(y, start, text, attr)
                    except curses.error:
                        pass
        self.stdscr.refresh()
