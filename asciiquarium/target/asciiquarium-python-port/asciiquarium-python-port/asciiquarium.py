#!/usr/bin/env python3
"""
Asciiquarium (Python port)

An aquarium/sea animation in ASCII art for the terminal.

Originally written in Perl by Kirk Baucom <kbaucom@schizoid.com>,
using Term::Animation + Curses. This is a from-scratch Python port
built on the standard-library `curses` module -- same idea, same
ASCII art, reimplemented animation engine.

Usage:
    python3 asciiquarium.py [-c]

    -c    "classic" mode -- only show the fish/monster species that
          shipped in the original Asciiquarium 1.0.

While running:
    q     quit
    r     redraw (recreates every entity from scratch)
    p     toggle pause
"""

from __future__ import annotations

import argparse
import curses
import sys
import time

from aquarium.engine import Engine
from aquarium import creatures


def populate(engine: Engine, classic: bool) -> None:
    creatures.CLASSIC_MODE = classic
    creatures.add_environment(engine)
    creatures.add_castle(engine)
    creatures.add_all_seaweed(engine)
    creatures.add_all_fish(engine)
    creatures.random_object(engine)


def run(stdscr, classic: bool) -> None:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.timeout(100)  # ~10 fps poll/animate cadence
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        pass

    engine = Engine(stdscr)

    while True:
        engine.clear()
        populate(engine, classic)
        engine.draw()

        last_tick = time.time()
        while True:
            ch = stdscr.getch()
            key = chr(ch).lower() if 0 <= ch < 256 else ""

            if key == "q":
                return
            elif key == "r":
                break
            elif key == "p":
                engine.paused = not engine.paused

            now = time.time()
            dt = now - last_tick
            last_tick = now
            if dt <= 0:
                dt = 0.1

            engine.animate(dt)
            engine.draw()

        engine.update_term_size()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ASCII art aquarium")
    parser.add_argument("-c", dest="classic", action="store_true",
                         help="classic mode (Asciiquarium 1.0 species only)")
    args = parser.parse_args(argv)

    try:
        curses.wrapper(run, args.classic)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
