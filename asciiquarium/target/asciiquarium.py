#!/usr/bin/env python3
"""Original Python curses aquarium for reLang."""
import argparse
import curses
import random
import time
from dataclasses import dataclass, field

SURFACE = 4
COLOURS = ("cyan", "yellow", "green", "magenta", "blue", "red")


def lines(value):
    return value.strip("\n").splitlines()


@dataclass
class Entity:
    kind: str
    frames: list
    x: float
    y: float
    vx: float = 0
    vy: float = 0
    z: int = 10
    colour: str = "cyan"
    rate: float = 0
    ttl: float = None
    age: float = 0
    clock: float = 0
    frame: int = 0
    info: dict = field(default_factory=dict)

    @property
    def image(self):
        return self.frames[self.frame]

    @property
    def width(self):
        return max((len(row) for row in self.image), default=0)

    @property
    def height(self):
        return len(self.image)


OLD_FISH = [
    (["  ><((o>"], ["<o))><  "]),
    (lines(""" /--.
<  o )>
 \\--/"""), lines(""".--\\
< (o  >
\\--/""")),
    (lines("""  /\\
>< o )>
  \\/"""), lines("""/\\
<( o ><
\\/""")),
]
NEW_FISH = [
    (lines("""  .---.
<(( o ))>
  '--'"""), lines(""".---.
<(( o ))>
'--'""")),
    (lines("""  __
<=[o]==>
  --"""), lines("""__
<==[o]==>
--""")),
]
SHARK = [
    lines("""              __
    __..----./  \\__
<===/  _  _      o >
    \\_________    /
              \\__/"""),
    lines("""__
  /  \\ .----..__
< o       _  _  \\===>
\\    _________/
 \\__/"""),
]


class Aquarium:
    def __init__(self, window, classic):
        self.window = window
        self.classic = classic
        self.entities = []
        self.palette = {}
        self.paused = False
        self.next_visitor = 0
        self.reset()

    def dimensions(self):
        height, width = self.window.getmaxyx()
        return max(height, 1), max(width, 1)

    def reset(self):
        self.entities = []
        height, width = self.dimensions()
        if height >= 9 and width >= 12:
            self.add_environment()
            for _ in range(max(2, width // 17)):
                self.add_seaweed()
            for _ in range(max(1, (height - SURFACE) * width // 360)):
                self.add_fish()
        self.next_visitor = time.monotonic() + random.uniform(4, 8)

    def add_environment(self):
        height, width = self.dimensions()
        castle = lines("""             /\\
        /\\  /  \\  /\\
       /  \\/____\\/  \\
  ____| []  _[]_  [] |____
 |__[]___| |____| |___[]__|
 |  _  _ |   ||   | _  _  |
 |________________________|""")
        self.entities.append(Entity("castle", [castle], max(0, width - 27),
            max(SURFACE + 1, height - len(castle) - 1), z=30, colour="yellow"))
        for row, wave in enumerate(("~ ~ ~~   ~ ~~~  ~~ ", " ~~~  ~ ~  ~~   ~ ~~", "~  ~~ ~~~  ~  ~~  ~ ")):
            self.entities.append(Entity("water", [[wave * (width // len(wave) + 2)]],
                0, row, z=25, colour="cyan"))

    def add_seaweed(self):
        height, width = self.dimensions()
        length = random.randint(3, max(3, min(7, height - SURFACE - 1)))
        left = ["/" if n % 2 else "\\" for n in range(length)]
        right = ["\\" if n % 2 else "/" for n in range(length)]
        self.entities.append(Entity("seaweed", [left, right],
            random.randrange(max(1, width)), height - length - 1, z=29,
            colour="green", rate=random.uniform(.3, .7)))

    def add_fish(self):
        height, width = self.dimensions()
        family = OLD_FISH if self.classic or random.random() < .72 else NEW_FISH
        forward, backward = random.choice(family)
        right = random.choice((True, False))
        frame_set = [forward, backward] if right else [backward, forward]
        max_y = max(SURFACE, height - len(frame_set[0]) - 1)
        size = max(map(len, frame_set[0]))
        self.entities.append(Entity("fish", frame_set, -size if right else width,
            random.randint(SURFACE, max_y), random.uniform(5, 13) * (1 if right else -1),
            z=random.randint(8, 23), colour=random.choice(COLOURS),
            info={"bubble": random.uniform(1, 5)}))

    def add_bubble(self, fish):
        self.entities.append(Entity("bubble", [["."], ["o"], ["O"]],
            fish.x + (fish.width if fish.vx > 0 else -1), fish.y + fish.height // 2,
            vy=-3, z=fish.z - 1, colour="cyan", rate=.25))

    def add_splat(self, x, y):
        self.entities.append(Entity("splat", [lines("""  . * .
 * * * *
  ' * '""")], x - 3, y - 1, z=1, colour="red", ttl=.7))

    def add_shark(self):
        height, width = self.dimensions()
        right = random.choice((True, False))
        self.entities.append(Entity("shark", SHARK if right else [SHARK[1], SHARK[0]],
            -30 if right else width, random.randint(SURFACE, max(SURFACE, height - 6)),
            11 * (1 if right else -1), z=3, colour="cyan",
            info={"tooth": (24 if right else 3, 2)}))

    def add_ship(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        drawing = lines("""        |    |
       /|\\  /|\\
      /_|_\\/_|_\\
  ____\\_________/____
  \\__________________/""")
        if not right:
            drawing = [row[::-1] for row in drawing]
        self.entities.append(Entity("ship", [drawing], -len(max(drawing, key=len)) if right else width,
            0, 4 * (1 if right else -1), z=7, colour="yellow"))

    def add_whale(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        body = lines("""       .--.
  ____/ o  \\___
<____        __)
     '------'""")
        if not right:
            body = [row[::-1] for row in body]
        frames = [["      :"] + body, ["    . : ."] + body, ["      :"] + body, [""] + body]
        self.entities.append(Entity("whale", frames, -18 if right else width, 0,
            4.5 * (1 if right else -1), z=6, colour="blue", rate=.35))

    def add_monster(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        drawing = lines("""       __
  ____/  \\____
 /  _  o  _   \\
<__/ \\___/ \\___>""") if self.classic else lines("""      _   _   _
  ___/ \\_/ \\_/ \\___
 /  o               \\
<_____/\\___/\\_______>""")
        if not right:
            drawing = [row[::-1] for row in drawing]
        self.entities.append(Entity("monster", [drawing], -len(max(drawing, key=len)) if right else width,
            1, 8 * (1 if right else -1), z=5, colour="green"))

    def add_big_fish(self):
        height, width = self.dimensions()
        right = random.choice((True, False))
        drawing = lines("""       ____
  _..-      -.._
<    o   .--.   >
 -._  .(   ).-.
     -' -'""") if self.classic or random.random() < .5 else lines("""      ______________
  ___/  o       _   -.
<    _      .--' --   >
 -.___..--'       --'""")
        if not right:
            drawing = [row[::-1] for row in drawing]
        self.entities.append(Entity("big_fish", [drawing], -len(max(drawing, key=len)) if right else width,
            random.randint(SURFACE, max(SURFACE, height - len(drawing) - 1)),
            7 * (1 if right else -1), z=4, colour=random.choice(COLOURS)))

    def add_visitor(self):
        random.choice((self.add_ship, self.add_whale, self.add_monster, self.add_big_fish, self.add_shark))()

    def update(self, dt):
        if self.paused:
            return
        now = time.monotonic()
        height, width = self.dimensions()
        for ent in self.entities:
            ent.age += dt
            ent.clock += dt
            ent.x += ent.vx * dt
            ent.y += ent.vy * dt
            if ent.rate and ent.clock >= ent.rate:
                ent.frame = (ent.frame + 1) % len(ent.frames)
                ent.clock = 0
            if ent.kind == "fish":
                ent.info["bubble"] -= dt
                if ent.info["bubble"] <= 0:
                    self.add_bubble(ent)
                    ent.info["bubble"] = random.uniform(2, 7)
        sharks = [ent for ent in self.entities if ent.kind == "shark"]
        for fish in [ent for ent in self.entities if ent.kind == "fish"]:
            for shark in sharks:
                dx, dy = shark.info["tooth"]
                tx, ty = shark.x + dx, shark.y + dy
                if fish.x <= tx <= fish.x + fish.width and fish.y <= ty <= fish.y + fish.height:
                    fish.ttl = 0
                    self.add_splat(tx, ty)
                    break

        def remains(ent):
            if ent.ttl is not None and ent.age >= ent.ttl:
                return False
            if ent.kind == "bubble":
                return ent.y > SURFACE - 1
            if ent.vx > 0:
                return ent.x < width + 2
            if ent.vx < 0:
                return ent.x + ent.width > -2
            return True

        self.entities = [ent for ent in self.entities if remains(ent)]
        target = max(1, max(0, height - SURFACE) * width // 360)
        while len([ent for ent in self.entities if ent.kind == "fish"]) < target:
            self.add_fish()
        visitors = {"shark", "ship", "whale", "monster", "big_fish"}
        if now >= self.next_visitor and not any(ent.kind in visitors for ent in self.entities):
            self.add_visitor()
            self.next_visitor = now + random.uniform(9, 18)

    def write(self, y, x, text, colour):
        height, width = self.dimensions()
        if not 0 <= y < height or x >= width:
            return
        skip = max(0, -x)
        visible = text[skip:max(skip, width - x - 1)]
        if visible:
            try:
                self.window.addstr(y, max(0, x), visible, self.palette.get(colour, 0))
            except curses.error:
                pass

    def draw(self):
        height, width = self.dimensions()
        self.window.erase()
        if height < 9 or width < 12:
            self.write(0, 0, "Resize terminal (minimum 12x9)", "yellow")
        else:
            for ent in sorted(self.entities, key=lambda item: item.z, reverse=True):
                for row, text in enumerate(ent.image):
                    self.write(int(ent.y) + row, int(ent.x), text, ent.colour)
            label = "PAUSED - p resumes" if self.paused else "q quit  p pause  r reset"
            self.write(height - 1, 1, label[:max(0, width - 2)], "yellow" if self.paused else "cyan")
        self.window.refresh()


def make_palette():
    values = {"cyan": curses.COLOR_CYAN, "yellow": curses.COLOR_YELLOW, "green": curses.COLOR_GREEN,
              "magenta": curses.COLOR_MAGENTA, "blue": curses.COLOR_BLUE, "red": curses.COLOR_RED}
    if not curses.has_colors():
        return {name: 0 for name in values}
    curses.start_color()
    curses.use_default_colors()
    result = {}
    for pair, (name, value) in enumerate(values.items(), 1):
        curses.init_pair(pair, value, -1)
        result[name] = curses.color_pair(pair)
    return result


def run(window, classic):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    window.keypad(True)
    window.nodelay(True)
    aquarium = Aquarium(window, classic)
    aquarium.palette = make_palette()
    previous = time.monotonic()
    while True:
        current = time.monotonic()
        elapsed = min(.15, current - previous)
        previous = current
        key = window.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key in (ord("r"), ord("R")):
            aquarium.reset()
        if key in (ord("p"), ord("P")):
            aquarium.paused = not aquarium.paused
        aquarium.update(elapsed)
        aquarium.draw()
        time.sleep(1 / 30)


def main():
    parser = argparse.ArgumentParser(description="Original Python ASCII aquarium")
    parser.add_argument("-c", "--classic", action="store_true", help="use classic creature variants")
    args = parser.parse_args()
    try:
        curses.wrapper(run, args.classic)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

