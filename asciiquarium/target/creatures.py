"""
Spawn functions for everything that appears in the aquarium: the
waterline, castle, seaweed, fish, bubbles, and the big roaming
creatures (ship, whale, sea monster, big fish, shark).

Behavior (spawn rates, speeds, depths, respawn-on-death) mirrors the
original Perl asciiquarium; the implementation itself is a fresh
Python reimplementation built on engine.Entity / engine.Engine.
"""

from __future__ import annotations

import random
import time
from typing import List

from . import art_data as art
from .engine import Engine, Entity

# z-depth table -- larger number = further from the viewer (drawn
# first / background), smaller number = nearer (drawn last / foreground)
DEPTH = {
    "gui": 1,
    "shark": 2,
    "fish_start": 3,
    "fish_end": 20,
    "seaweed": 21,
    "castle": 22,
    "water_line3": 2,
    "water_gap3": 3,
    "water_line2": 4,
    "water_gap2": 5,
    "water_line1": 6,
    "water_gap1": 7,
    "water_line0": 8,
    "water_gap0": 9,
}

_PALETTE = list("cCrRyYbBgGmM")

# When True, only the species/behavior that shipped in the original
# Asciiquarium 1.0 are used (set by asciiquarium.py from the -c flag).
CLASSIC_MODE = False


def rand_color(mask: str) -> str:
    """Replace each digit 1-9 found in the mask with a randomly chosen
    (but consistent-per-digit) color letter, same trick the original
    used to give every fish a unique but internally-consistent palette."""
    for digit in "123456789":
        if digit in mask:
            mask = mask.replace(digit, random.choice(_PALETTE))
    return mask


# ---------------------------------------------------------------- environment
def add_environment(engine: Engine) -> None:
    segments = [
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
        "^^^^ ^^^  ^^^   ^^^    ^^^^      ",
        "^^^^      ^^^^     ^^^    ^^     ",
        "^^      ^^^^      ^^^    ^^^^^^  ",
    ]
    seg_len = len(segments[0])
    repeat = engine.width // seg_len + 1
    for i, seg in enumerate(segments):
        engine.add(Entity(
            type="waterline",
            shape_frames=[seg * repeat],
            x=0, y=i + 5, z=DEPTH[f"water_line{i}"],
            default_color="cyan",
            physical=True,
        ))


def add_castle(engine: Engine) -> None:
    engine.add(Entity(
        type="castle",
        shape_frames=[art.CASTLE_IMAGE],
        color_frames=[art.CASTLE_MASK],
        x=engine.width - 32, y=engine.height - 13, z=DEPTH["castle"],
        default_color="black",
    ))


# -------------------------------------------------------------------- seaweed
def add_seaweed(engine: Engine, _dead: Entity | None = None) -> None:
    height = random.randint(3, 6)
    frames = ["", ""]
    for i in range(1, height + 1):
        left = i % 2
        right = 0 if left else 1
        frames[left] += "(\n"
        frames[right] += " )\n"
    frames = [f.rstrip("\n") for f in frames]
    x = random.randint(1, max(1, engine.width - 2))
    y = engine.height - height
    speed = random.uniform(0.25, 0.30)
    lifetime = random.uniform(8 * 60, 12 * 60)
    engine.add(Entity(
        type="seaweed",
        shape_frames=frames,
        frame_period=speed,
        x=x, y=y, z=DEPTH["seaweed"],
        default_color="green",
        die_time=time.time() + lifetime,
        death_cb=lambda e, eng: add_seaweed(eng),
    ))


def add_all_seaweed(engine: Engine) -> None:
    count = engine.width // 15
    for _ in range(count):
        add_seaweed(engine)


# --------------------------------------------------------------------- bubble
def _bubble_collision(bubble: Entity, other: Entity, engine: Engine) -> None:
    if other.type == "waterline":
        bubble.kill()


def add_bubble(fish: Entity, engine: Engine) -> None:
    fw, fh = fish.size()
    x = fish.x + (fw if fish.dx > 0 else 0)
    y = fish.y + fh / 2
    engine.add(Entity(
        type="bubble",
        shape_frames=[".", "o", "O", "O", "O"],
        frame_period=0.1,
        x=x, y=y, z=fish.z - 1,
        dx=0, dy=-1,
        die_offscreen=True,
        physical=True,
        coll_handler=_bubble_collision,
        default_color="CYAN",
    ))


# ----------------------------------------------------------------------- fish
def _fish_callback(entity: Entity, engine: Engine) -> None:
    if random.randint(1, 100) > 97:
        add_bubble(entity, engine)


def _fish_collision(fish: Entity, other: Entity, engine: Engine) -> None:
    if other.type == "teeth" and fish.size()[1] <= 5:
        fx, fy, _, _ = fish.bbox()
        add_splat(engine, fx, fy, fish.z)
        fish.kill()


def _add_fish_entity(engine: Engine, species: List[tuple]) -> None:
    fish_num = random.randint(0, len(species) - 1)
    image, mask = species[fish_num]
    mask = mask.replace("4", "W")
    mask = rand_color(mask)
    speed = random.uniform(0.25, 2.25)
    depth = random.randint(DEPTH["fish_start"], DEPTH["fish_end"] - 1)
    if fish_num % 2:
        speed *= -1

    lines = image.split("\n")
    w = max((len(l) for l in lines), default=0)
    h = len(lines)

    max_height = 9
    min_height = engine.height - h
    y = random.randint(min(max_height, min_height), max(max_height, min_height))
    if fish_num % 2:
        x = engine.width - 2
    else:
        x = 1 - w

    engine.add(Entity(
        type="fish",
        shape_frames=[image],
        color_frames=[mask],
        x=x, y=y, z=depth,
        dx=speed, dy=0,
        die_offscreen=True,
        death_cb=lambda e, eng: add_fish(eng),
        physical=True,
        update_hook=_fish_callback,
        coll_handler=_fish_collision,
    ))


def add_fish(engine: Engine, _dead: Entity | None = None) -> None:
    if not CLASSIC_MODE and random.randint(0, 11) > 8:
        _add_fish_entity(engine, art.NEW_FISH)
    else:
        _add_fish_entity(engine, art.OLD_FISH)


def add_all_fish(engine: Engine) -> None:
    screen_size = max(0, engine.height - 9) * engine.width
    count = screen_size // 350
    for _ in range(count):
        add_fish(engine)


# ---------------------------------------------------------------------- splat
def add_splat(engine: Engine, x: float, y: float, z: int) -> None:
    engine.add(Entity(
        type="splat",
        shape_frames=list(art.SPLAT_FRAMES),
        frame_period=0.25,
        x=x - 4, y=y - 2, z=z - 2,
        default_color="RED",
        die_frame=15,
    ))


# ---------------------------------------------------------------------- shark
def _shark_death(shark: Entity, engine: Engine) -> None:
    for teeth in engine.entities_of_type("teeth"):
        engine.remove(teeth)
    random_object(engine)


def add_shark(engine: Engine, _dead: Entity | None = None) -> None:
    direction = random.randint(0, 1)
    x = -53
    y = random.randint(9, max(9, engine.height - 19))
    teeth_x = -9
    teeth_y = y + 7
    speed = 2.0
    if direction:
        speed *= -1
        x = engine.width - 2
        teeth_x = x + 9

    engine.add(Entity(
        type="teeth",
        shape_frames=["*"],
        x=teeth_x, y=teeth_y, z=DEPTH["shark"] + 1,
        dx=speed, dy=0,
        physical=True,
    ))
    engine.add(Entity(
        type="shark",
        shape_frames=[art.SHARK_IMAGE[direction]],
        color_frames=[art.SHARK_MASK[direction]],
        x=x, y=y, z=DEPTH["shark"],
        dx=speed, dy=0,
        die_offscreen=True,
        death_cb=_shark_death,
        default_color="CYAN",
    ))


# ----------------------------------------------------------------------- ship
def add_ship(engine: Engine, _dead: Entity | None = None) -> None:
    direction = random.randint(0, 1)
    x = -24
    speed = 1.0
    if direction:
        speed *= -1
        x = engine.width - 2
    engine.add(Entity(
        type="ship",
        shape_frames=[art.SHIP_IMAGE[direction]],
        color_frames=[art.SHIP_MASK[direction]],
        x=x, y=0, z=DEPTH["water_gap1"],
        dx=speed, dy=0,
        die_offscreen=True,
        death_cb=lambda e, eng: random_object(eng),
        default_color="white",
    ))


# ---------------------------------------------------------------------- whale
def add_whale(engine: Engine, _dead: Entity | None = None) -> None:
    direction = random.randint(0, 1)
    speed = 1.0
    if direction:
        speed *= -1
        x = engine.width - 2
        spout_align = 1
    else:
        x = -18
        spout_align = 11

    frames = []
    masks = []
    for _ in range(5):
        frames.append("\n\n\n" + art.WHALE_IMAGE[direction])
        masks.append(art.WHALE_MASK[direction])
    for spout in art.WATER_SPOUT_FRAMES:
        aligned = ("\n" + " " * spout_align).join(spout.split("\n"))
        frames.append(aligned + art.WHALE_IMAGE[direction])
        masks.append(art.WHALE_MASK[direction])

    engine.add(Entity(
        type="whale",
        shape_frames=frames,
        color_frames=masks,
        frame_period=1.0,
        x=x, y=0, z=DEPTH["water_gap2"],
        dx=speed, dy=0,
        die_offscreen=True,
        death_cb=lambda e, eng: random_object(eng),
        default_color="white",
    ))


# -------------------------------------------------------------------- monster
def add_monster(engine: Engine, _dead: Entity | None = None) -> None:
    new_style = (not CLASSIC_MODE) and random.random() < 0.5
    direction = random.randint(0, 1)
    speed = 2.0
    if new_style:
        images = art.MONSTER_NEW_IMAGE[direction]
        mask = art.MONSTER_NEW_MASK[direction]
        width = 54
    else:
        images = art.MONSTER_OLD_IMAGE[direction]
        mask = art.MONSTER_OLD_MASK[direction]
        width = 64
    if direction:
        speed *= -1
        x = engine.width - 2
    else:
        x = -width

    engine.add(Entity(
        type="monster",
        shape_frames=list(images),
        color_frames=[mask] * len(images),
        frame_period=0.25,
        x=x, y=2, z=DEPTH["water_gap2"],
        dx=speed, dy=0,
        die_offscreen=True,
        death_cb=lambda e, eng: random_object(eng),
        default_color="green",
    ))


# -------------------------------------------------------------------- bigfish
def _add_big_fish(engine: Engine, images, masks, speed: float, x_off: float,
                   max_height: int, min_height_offset: int) -> None:
    direction = random.randint(0, 1)
    speed = abs(speed)
    if direction:
        x = engine.width - 1
        speed *= -1
    else:
        x = -x_off
    min_height = max(max_height + 1, engine.height - min_height_offset)
    y = random.randint(max_height, min_height)
    mask = rand_color(masks[direction])
    engine.add(Entity(
        type="big_fish",
        shape_frames=[images[direction]],
        color_frames=[mask],
        x=x, y=y, z=DEPTH["shark"],
        dx=speed, dy=0,
        die_offscreen=True,
        death_cb=lambda e, eng: random_object(eng),
        default_color="yellow",
    ))


def add_big_fish(engine: Engine, _dead: Entity | None = None) -> None:
    if random.randint(0, 2) > 1:
        _add_big_fish(engine, art.BIG_FISH_2_IMAGE, art.BIG_FISH_2_MASK,
                       2.5, 33, 9, 14)
    else:
        _add_big_fish(engine, art.BIG_FISH_1_IMAGE, art.BIG_FISH_1_MASK,
                       3.0, 34, 9, 15)


# ----------------------------------------------------------- random big object
_RANDOM_OBJECTS = [add_ship, add_whale, add_monster, add_big_fish, add_shark]


def random_object(engine: Engine, _dead: Entity | None = None) -> None:
    random.choice(_RANDOM_OBJECTS)(engine)
