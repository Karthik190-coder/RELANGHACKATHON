# asciiquarium (Python port)

A Python 3 port of Kirk Baucom's [Asciiquarium](http://robobunny.com/projects/asciiquarium)
(originally Perl, using `Term::Animation` + `Curses`). This port uses only the
Python standard library's `curses` module — no third-party packages.

## Requirements

- Python 3.9+ (uses `dataclasses` and `from __future__ import annotations`)
- The `curses` module, which is part of the Python standard library on
  Linux/macOS. On a minimal Ubuntu 24.04 install this normally works out of
  the box; if it doesn't, install the ncurses runtime:

  ```bash
  sudo apt-get install libncursesw5-dev
  ```

No `pip install` is required.

## Run

```bash
python3 target/asciiquarium.py
```

Or, from inside `target/`:

```bash
python3 asciiquarium.py
```

Optional flag:

- `-c` — "classic" mode: only shows the fish/monster species that shipped
  in the original Asciiquarium 1.0 (drops the newer species and the
  redesigned sea monster).

## Controls

| Key | Action                                  |
|-----|------------------------------------------|
| `q` | Quit                                      |
| `r` | Redraw (recreates every entity from scratch) |
| `p` | Toggle pause                              |

## Layout

```
target/
├── asciiquarium.py      entry point: curses setup, main loop, key handling
├── aquarium/
│   ├── engine.py         generic entity/animation engine (z-depth compositing,
│   │                     collision detection, lifecycle: death/offscreen/
│   │                     timed/frame-limited, color-mask rendering)
│   ├── creatures.py       spawns everything: waterline, castle, seaweed,
│   │                     bubbles, fish, shark(+teeth), ship, whale, sea
│   │                     monster, big fish — mirrors the original's spawn
│   │                     rates, depths, and respawn-on-death behavior
│   └── art_data.py        ASCII art + color masks, transcribed from the
│                         reference Perl source
└── README.md
```

## Porting notes

- The animation engine (`engine.py`) is a fresh reimplementation of the
  entity/z-depth/collision concepts the original relied on from the
  `Term::Animation` CPAN module — not a translation of its code.
- The ASCII art assets (fish, shark, whale, ship, monster, castle, splat
  frames) are carried over from the reference source, since they're the
  visual content the animation is built around — same convention as
  porting a game while keeping its sprite assets.
- Coloring reproduces the original's per-instance random palette trick:
  each fish's color mask uses placeholder digits (body, fin, eye, etc.)
  that get replaced with a randomly chosen — but internally consistent —
  color the moment the fish is spawned, so two fish of the same species
  don't always look identical.
