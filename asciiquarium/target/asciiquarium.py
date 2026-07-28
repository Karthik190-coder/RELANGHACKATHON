#!/usr/bin/env python3
"""Python curses aquarium matching reference art."""
import argparse
import curses
import random
import time
from dataclasses import dataclass, field

SURFACE = 5
COLOUR_LETTERS = ['c','C','r','R','y','Y','b','B','g','G','m','M']

WATER_LINE_IMAGES = [
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "^^^^ ^^^  ^^^   ^^^    ^^^^      ",
    "^^^^      ^^^^     ^^^    ^^     ",
    "^^      ^^^^      ^^^    ^^^^^^  ",
]


def lines(value):
    return value.strip("\n").splitlines()


def rand_color(mask_lines):
    result = []
    for line in mask_lines:
        out = ""
        for ch in line:
            if "1" <= ch <= "9":
                out += random.choice(COLOUR_LETTERS)
            else:
                out += ch
        result.append(out)
    return result


def prepare_masks(mask_pair):
    right, left = mask_pair
    eye_right = [ln.replace("4", "W") for ln in right]
    eye_left = [ln.replace("4", "W") for ln in left]
    return [rand_color(eye_right), rand_color(eye_left)]


FISH_OLD = [
    (
        lines("""       \\
     ...\\..,
\\  /'       \\
 >=     (  ' >
/  \\      / /
    `\"'\"'/''
"""),
        lines("""      /
  ,../...
 /       '\\  /
< '  )     =<
 \\ \\      /  \\
  `'\\'\"'\"'
"""),
    ),
    (
        lines("""    \\
\\ /--\\
>=  (o>
/ \\__/
    /
"""),
        lines("""  /
 /--\\ /
<o)  =<
 \\__/ \\
  \\
"""),
    ),
    (
        lines("""       \\:.
\\;,   ,;\\\\\\\\\\,
  \\\\\\\\\\\\;;:::::::o
  ///;;::::::::<
 /;` ``/////``
"""),
        lines("""      .:/
   ,,///;,   ,;/
 o:::::::;;///
>::::::::;;\\\\\\\\\\
  ''\\\\\\\\\\\\\\'' ';\\
"""),
    ),
    (
        lines("""  __
><_'>
   '
"""),
        lines(""" __
<'_><
 `
"""),
    ),
    (
        lines("""   ..\\,
>='   ('>
  '''/''
"""),
        lines("""  ,/..
<')   `=<
 ``\\```
"""),
    ),
    (
        lines("""   \\
  / \\
>=_('>
  \\_/
   /
"""),
        lines("""  /
 / \\
<')_=<
 \\_/
  \\
"""),
    ),
    (
        lines("""  ,\\
>=('>
  '/
"""),
        lines(""" /,
<')=<
 \\`
"""),
    ),
    (
        lines("""  __
\\/ o\\
/\\__/
"""),
        lines(""" __
/o \\/
\\__/\\
"""),
    ),
]

FISH_NEW = [
    (
        lines("""   \\\\
  / \\\\
>=_('>
  \\\\_/
   /
"""),
        lines("""  /
 / \\\\
<')_=<
 \\\\_/
  \\\\
"""),
    ),
    (
        lines("""     ,
     \\}\\}
\\\\  .'  `\\
\\}\\}<   ( 6>
/  `,  .'
     \\}/
     '
"""),
        lines("""    ,
   /\\{
 /'  `.  /
<6 )   >{{
 `.  ,'  \\\\
   \\{
    `
"""),
    ),
    (
        lines(r"""            \\'.
             )  \\
(`.??????_.-`' ' '`-.
 \\ `.??.`        (o) \\_
  >  ><     (((       (
 / .`??`._      /_|  /'
(.`???????`-. _  _.-`
            /__/'
"""),
        lines(r"""       .'`/
      /  (
  .-'` ` `'-._??????.')
_/ (o)        '.??.' /
)       )))     ><  <
`\\  |_\\      _.'??'. \\
  '-._  _ .-'???????'.)
      `__\\
"""),
    ),
    (
        lines("""       ,--,_
__    _\\.---'-.
\\ '.-"     // o\\
/_.'-._    \\\\  /
        `\"--(/\""
"""),
        lines("""    _,--,
 .-'---./_    __
/o \\\\     \"-.' /
\\  //    _.-'.\\_\\
 `\"\\--)--\"
"""),
    ),
]

FISH_OLD_MASK = [
    (
        lines("""       2
     1112111
6  11       1
 66     7  4 5
6  1      3 1
    11111311
"""),
        lines("""      2
  1112111
 1       11  6
5 4  7     66
 1 3      1  6
  11311111
"""),
    ),
    (
        lines("""    2
6 1111
66  745
6 1111
    3
"""),
        lines("""  2
 1111 6
547  66
 1111 6
  3
"""),
    ),
    (
        lines("""       222
666   1122211
  6661111111114
  66611111111115
 666 113333311
"""),
        lines("""      222
   1122211   666
 4111111111666
51111111111666
  113333311 666
"""),
    ),
    (
        lines("""  11
61145
   3
"""),
        lines(""" 11
54116
 3
"""),
    ),
    (
        lines("""   1121
661   745
  111311
"""),
        lines("""  1211
547   166
 113111
"""),
    ),
    (
        lines("""   2
  1 1
661745
  111
   3
"""),
        lines("""  2
 1 1
547166
 111
  3
"""),
    ),
    (
        lines("""  12
66745
  13
"""),
        lines(""" 21
54766
 31
"""),
    ),
    (
        lines("""  11
61 41
61111
"""),
        lines(""" 11
14 16
11116
"""),
    ),
]

FISH_NEW_MASK = [
    (
        lines("""   1
  1 1
663745
  111
   3
"""),
        lines("""  2
 111
547366
 111
  3
"""),
    ),
    (
        lines("""     2
     22
6  11  11
661   7 45
6  11  11
     33
     3
"""),
        lines("""    2
   22
 11  11  6
54 7   166
 11  11  6
   33
    3
"""),
    ),
    (
        lines("""            1111
             1  1
111      11111 1 1111
 1 11  11        141 11
  1  11     777       5
 1 11  111      333  11
111       111 1  1111
            11111
"""),
        lines("""       1111
      1  1
  1111 1 11111      111
11 141        11  11 1
5       777     11  1
11  333      111  11 1
  1111  1 111       111
      11111
"""),
    ),
    (
        lines("""       22222
66    121111211
6 6111     77 41
6661111    77  1
       11113311
"""),
        lines("""    22222
 112111121    66
14 77     1116 6
1  77    1111666
 11331111
"""),
    ),
]

SHARK_IMAGES = [
    lines("""                              __
                             ( `\\
  ,??????????????????????????)   `\\
;' `.????????????????????????(     `\\__
 ;   `.?????????????__..---''          `~~~~-._
  `.   `.____...--''                       (b  `--._
    >                     _.-'      .((      ._     )
  .`.-`--...__         .-'     -.___.....-(|/|/|/|/'
 ;.'?????????`. ...----`.___.',,,_______......---'
 '???????????'-'
"""),
    lines("""                      __
                     /' )
                   /'   (??????????????????????????,
               __/'     )????????????????????????.' `;
       _.-~~~~'          ``---..__?????????????.'   ;
 _.--'  b)                       ``--...____.'   .'
(     _.      )).      `-._                     <
 `\\|\\|\\|\\|)-.....___.-     `-.         __...--'-.'.
   `---......_______,,,`.___.'----... .'?????????`.;
                                      `-`???????????`
"""),
]

SHARK_MASKS = [
    lines("""                                     cR
                                  cWWWWWWWW
"""),
    lines("""        Rc
  WWWWWWWWc
"""),
]

SHIP_IMAGES = [
    lines("""     |    |    |
    )_)  )_)  )_)
   )___))___))___)\\
  )____)____)_____)\\\\
_____|____|____|____\\\\\\\\\\__
\\                   /
"""),
    lines("""         |    |    |
        (_(  (_(  (_(
      /(___((___((___(
    //(_____(____(____(
__///____|____|____|_____
    \\                   /
"""),
]

SHIP_MASKS = [
    lines("""     y    y    y

                  w
                   ww
yyyyyyyyyyyyyyyyyyyyyywwwyy
y                   y
"""),
    lines("""          y    y    y

       w
     ww
yywwwyyyyyyyyyyyyyyyyyyyy
    y                   y
"""),
]

WHALE_IMAGES = [
    lines("""        .-----:
      .'       `.
,????/       (o) \\
\\`._/          ,__)
"""),
    lines("""    :-----.
  .'       `.
 / (o)       \\????
(__,          \\_.'/
"""),
]

WHALE_MASKS = [
    lines("""             C C
           CCCCCCC
           C  C  C
        BBBBBBB
      BB       BB
B    B       BWB B
BBBBB          BBBB
"""),
    lines("""   C C
 CCCCCCC
 C  C  C
    BBBBBBB
  BB       BB
 B BWB       B    B
BBBB          BBBBB
"""),
]

WATER_SPOUT = [
    lines("      :"),
    lines("      :\n    . : ."),
    lines("      :"),
    [""],
]

MONSTER_IMAGES_R = [
    lines("""                                                           ____
            __??????????????????????????????????????????/   o  \\
          /    \\????????_?????????????????????_???????/     ____ >
  _??????|  __  |?????/   \\????????_????????/   \\????|     |
 | \\?????|  ||  |????|     |?????/   \\?????|     |???|     |
"""),
    lines("""                                                           ____
                                             __?????????/   o  \\
             _?????????????????????_???????/    \\?????/     ____ >
   _???????/   \\????????_????????/   \\????|  __  |???|     |
  | \\?????|     |?????/   \\?????|     |???|  ||  |???|     |
"""),
    lines("""                                                           ____
                                  __????????????????????/   o  \\
 _??????????????????????_???????/    \\????????_???????/     ____ >
| \\??????????_????????/   \\????|  __  |?????/   \\????|     |
 \\ \\???????/   \\?????|     |???|  ||  |????|     |???|     |
"""),
    lines("""                                                           ____
                       __???????????????????????????????/   o  \\
  _??????????_???????/    \\????????_??????????????????/     ____ >
 | \\???????/   \\????|  __  |?????/   \\????????_??????|     |
  \\ \\?????|     |???|  ||  |????|     |?????/   \\????|     |
"""),
]

MONSTER_IMAGES_L = [
    lines("""    ____
  /  o   \\??????????????????????????????????????????__
< ____     \\???????_?????????????????????_????????/    \\
      |     |????/   \\????????_????????/   \\?????|  __  |??????_
      |     |???|     |?????/   \\?????|     |????|  ||  |?????/ |
"""),
    lines("""    ____
  /  o   \\?????????__
< ____     \\?????/    \\???????_?????????????????????_
      |     |???|  __  |????/   \\????????_????????/   \\???????_
      |     |???|  ||  |???|     |?????/   \\?????|     |?????/ |
"""),
    lines("""    ____
  /  o   \\????????????????????__
< ____     \\???????_????????/    \\???????_??????????????????????_
      |     |????/   \\?????|  __  |????/   \\????????_??????????/ |
      |     |???|     |????|  ||  |???|     |?????/   \\???????/ /
"""),
    lines("""    ____
  /  o   \\???????????????????????????????__
< ____     \\??????????????????_????????/    \\???????_??????????_
      |     |??????_????????/   \\?????|  __  |????/   \\???????/ |
      |     |????/   \\?????|     |????|  ||  |???|     |?????/ /
"""),
]

MONSTER_MASK = [
    lines("""                                                            W
"""),
    lines("""     W
"""),
]

BIG_FISH_1_IMAGES = [
    lines(""" ______
`\"\"-.  `````-----.....__
     `.  .      .       `-.
       :     .     .       `.
 ,?????:   .    .          _ :
: `.???:                  (@) `._
 `. `..'     .     =`-.       .__)
   ;     .        =  ~  :     .-\"
 .' .'`.   .    .  =.-'  `._ .'
: .'?????:               .   .'
 '???.'  .    .     .   .-'
   .'____....----''.'=.'
   \"\"?????????????.'.'
               ''\"'`
"""),
    lines("""                           ______
          __.....-----'''''  .-\"\"'
       .-'       .      .  .'
     .'       .     .     :
    : _          .    .   :?????,
 _.' (@)                  :???.' :
(__.       .-'=     .     `..' .'
 \"-.     :  ~  =        .     ;
   `. _.'  `-.=  .    .   .'`. `.
     `.   .               :???`. :
       `-.   .     .    .  `.???`
          `.=`.``----....____`.
            `.`.?????????????\"\"
              '`\"``
"""),
]

BIG_FISH_1_MASKS = [
    lines(""" 111111
11111  11111111111111111
     11  2      2       111
       1     2     2       11
 1     1   2    2          1 1
1 11   1                  1W1 111
 11 1111     2     1111       1111
   1     2        1  1  1     111
 11 1111   2    2  1111  111 11
1 11   1               2   11
 1   11  2    2     2   111
   111111111111111111111
   11             1111
               11111
"""),
    lines("""                           111111
          11111111111111111  11111
       111       2      2  11
     11       2     2     1
    1 1          2    2   1     1
 111 1W1                  1   11 1
1111       1111     2     1111 11
 111     1  1  1        2     1
   11 111  1111  2    2   1111 11
     11   2               1   11 1
       111   2     2    2  11   1
          111111111111111111111
            1111             11
              11111
"""),
]

BIG_FISH_2_IMAGES = [
    lines(r"""                _ _ _
             .='\ \ \`"=,
           .'\ \ \ \ \ \ \
\'=._?????/ \ \ \_\_\_\_\_\
\'=._'.??/\ \,"`- _ - _ - '-.
  \`=._\|'.\/- _ - _ - _ - _- \
  ;"= ._\=./_ -_ -_ {`"=_    @ \
   ;="_-_=- _ -  _ - {"=_-"     \
   ;_=_--_.,          {_.='   .-/
  ;.="` / ';\        _.     _.-`
  /_.='/ \/ /;._ _ _\{.-;`/"`
/._=_.'???'/ / / / /\{.= /
/.=' ??????`'./_/_.=`\{_/
"""),
    lines(r"""            _ _ _
        ,="`/ / /'=.
       / / / / / / /'.
      /_/_/_/_/_/ / / \?????_.='/
   .-' - _ - _ -`"-,/ /\??.'_.='/
  / -_ - _ - _ - _ -\/.'|/_.=`/
 / @    _="`\} _- _- _\.=/_. =";
/     -"_="\} - _  - _ -=_-_"=;
\-.

  -.   '=._\}          ,._--_=_;
  `-._     ._        /;' \ `"=.;
      `"\-;-.\}_ _ _.;\/ \/'=._\
        \=.}\ \ \ \ \'???'._=_.\
         \_\}`=._\._\'`???????'=./
"""),
]

BIG_FISH_2_MASKS = [
    lines("""                1 1 1
             1111 1 11111
           111 1 1 1 1 1 1
11111     1 1 1 11111111111
1111111  11 111112 2 2 2 2 111
  111111111112 2 2 2 2 2 2 22 1
  111 1111 12 22 22 11111    W 1
   11111112 2 2  2 2 111111     1
   111111111          11111   111
  11111 11111        11     1111
  111111 11 1111 1 111111111
1111111   11 1 1 1 1111 1
1111       1111111111111
"""),
    lines("""            1 1 1
        11111 1 1111
       1 1 1 1 1 1 111
      11111111111 1 1 1     11111
   111 2 2 2 2 211111 11  1111111
  1 22 2 2 2 2 2 2 211111111111
 1 W    11111 22 22 2111111 111
1     111111 2 2  2 2 21111111
111   11111          111111111
 1111     11        111 1 11111
     111111111 1 1111 11 111111
        1 1111 1 1 1 11   1111111
         1111111111111       1111
"""),
]

BUBBLE_SHAPE = [".", "o", "O", "O", "O"]

SEAWEED_SWAY_L = ["(", " )", "(", " )", "(", " )", "(", " )", "(", " )"]
SEAWEED_SWAY_R = [" )", "(", " )", "(", " )", "(", " )", "(", " )", "("]

SPLAT_IMAGES = [
    lines("""   .
  ***
   '
"""),
    lines(""" ",*;`
 "*,**
 *\"'~'
"""),
    lines("""  , ,
 " ","'
 *\" *'\"
  \" ; .
"""),
    lines(r"""* ' , ' `
' ` * . '
 ' `' ",'
* ' " * .
" * ', '
"""),
]

CASTLE_IMAGE = lines("""               T~~
               |
              /^\\
             /   \\
 _   _   _  /     \\  _   _   _
[ ]_[ ]_[ ]/ _   _ \\[ ]_[ ]_[ ]
|_=__-_ =_|_[ ]_[ ]_|_=-___-__|
 | _- =  | =_ = _    |= _=   |
 |= -[]  |- = _ =    |_-=_[] |
 | =_    |= - ___    | =_ =  |
 |=  []- |-  /| |\\   |=_ =[] |
 |- =_   | =| | | |  |- = -  |
 |_______|__|_|_|_|__|_______|
""")

CASTLE_MASK = lines("""                RR

              yyy
             y   y
            y     y
           y       y

              yyy
             yy yy
            y y y y
            yyyyyyy
""")


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
    masks: list = None
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
    def cur_mask(self):
        if self.masks:
            idx = min(self.frame, len(self.masks) - 1)
            return self.masks[idx]
        return None

    @property
    def width(self):
        return max((len(row) for row in self.image), default=0)

    @property
    def height(self):
        return len(self.image)


class Aquarium:
    def __init__(self, window, classic):
        self.window = window
        self.classic = classic
        self.entities = []
        self.palette = {}
        self.mask_palette = {}
        self.paused = False
        self.next_visitor = 0
        self.next_centerpiece = 0
        self.reset()

    def dimensions(self):
        height, width = self.window.getmaxyx()
        return max(height, 1), max(width, 1)

    def reset(self):
        self.entities = []
        height, width = self.dimensions()
        if height >= 9 and width >= 12:
            self.add_environment()
            self.add_castle()
            for _ in range(max(2, width // 15)):
                self.add_seaweed()
            for _ in range(max(1, (height - 9) * width // 350)):
                self.add_fish()
        self.next_visitor = time.monotonic() + random.uniform(4, 8)
        self.next_centerpiece = time.monotonic() + random.uniform(7, 12)

    def add_environment(self):
        height, width = self.dimensions()
        seg_repeat = width // len(WATER_LINE_IMAGES[0]) + 2
        for i, seg in enumerate(WATER_LINE_IMAGES):
            tiled = seg * seg_repeat
            self.entities.append(Entity(
                "waterline", [[tiled]], 0, i + SURFACE,
                z=25, colour="cyan"
            ))

    def add_castle(self):
        height, width = self.dimensions()
        mask = rand_color(CASTLE_MASK)
        self.entities.append(Entity(
            "castle", [CASTLE_IMAGE],
            max(0, width - 32), height - len(CASTLE_IMAGE) - 1,
            z=22, colour="black", masks=[mask]
        ))

    def add_seaweed(self):
        height, width = self.dimensions()
        h = min(random.randint(3, 6), max(2, height - 9 - 1))
        left = SEAWEED_SWAY_L[:h]
        right = SEAWEED_SWAY_R[:h]
        self.entities.append(Entity(
            "seaweed", [left, right],
            random.randrange(max(1, width - 3)),
            height - h - 1, z=21, colour="green",
            rate=random.uniform(0.25, 0.6)
        ))

    def add_fish(self):
        height, width = self.dimensions()
        if self.classic or random.random() < 0.72:
            family, masks = FISH_OLD, FISH_OLD_MASK
        else:
            family, masks = FISH_NEW, FISH_NEW_MASK
        i = random.randrange(len(family))
        fwd, bwd = family[i]
        mfwd, mbwd = prepare_masks(masks[i])
        right = random.choice((True, False))
        frames = [fwd, bwd] if right else [bwd, fwd]
        mask_list = [mfwd, mbwd] if right else [mbwd, mfwd]
        size = max(map(len, frames[0]))
        max_y = max(9, height - len(frames[0]) - 1)
        self.entities.append(Entity(
            "fish", frames,
            -size if right else width,
            random.randint(9, max_y),
            random.uniform(5, 13) * (1 if right else -1),
            z=random.randint(3, 20), colour="white",
            masks=mask_list,
            info={"bubble": random.uniform(1, 5)}
        ))

    def add_bubble(self, fish):
        x = fish.x + (fish.width if fish.vx > 0 else -1)
        y = fish.y + fish.height // 2
        self.entities.append(Entity(
            "bubble",
            [[c] for c in BUBBLE_SHAPE],
            x, y, vy=-1, z=fish.z - 1, colour="cyan",
            rate=0.1
        ))

    def add_splat(self, x, y):
        self.entities.append(Entity(
            "splat", SPLAT_IMAGES,
            x - 4, y - 2, z=1, colour="red",
            ttl=1.0, rate=0.25
        ))

    def add_shark(self):
        height, width = self.dimensions()
        right = random.choice((True, False))
        img = SHARK_IMAGES[0] if right else SHARK_IMAGES[1]
        mask = SHARK_MASKS[0] if right else SHARK_MASKS[1]
        tooth_x = 58 if right else 6
        self.entities.append(Entity(
            "shark", [img],
            -53 if right else width,
            random.randint(9, max(9, height - 10)),
            3.8 * (1 if right else -1), z=2,
            colour="cyan", masks=[mask],
            info={"tooth": (tooth_x, 7)}
        ))

    def add_ship(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        img = SHIP_IMAGES[0] if right else SHIP_IMAGES[1]
        mask = rand_color(SHIP_MASKS[0] if right else SHIP_MASKS[1])
        size = max(map(len, img))
        self.entities.append(Entity(
            "ship", [img],
            -size if right else width,
            0, 3 * (1 if right else -1), z=7,
            colour="yellow", masks=[mask]
        ))

    def add_whale(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        img = WHALE_IMAGES[0] if right else WHALE_IMAGES[1]
        mask = WHALE_MASKS[0] if right else WHALE_MASKS[1]
        mask_processed = rand_color(mask)
        spout_align = 1 if right else 11
        frames = []
        masks = []
        for _ in range(5):
            frames.append(img)
            masks.append(mask_processed)
        for spout in WATER_SPOUT:
            spout_text = "\n".join(" " * spout_align + ln for ln in spout)
            spout_lines = spout_text.splitlines() if spout_text.strip() else []
            frames.append(spout_lines + img)
            masks.append(([""] * len(spout_lines) if spout_text.strip() else []) + mask_processed)
        self.entities.append(Entity(
            "whale", frames,
            -18 if right else width,
            0, 2.6 * (1 if right else -1), z=5,
            colour="white", masks=masks, rate=1.0
        ))

    def add_monster(self):
        if self.classic or random.random() < 0.5:
            self.add_old_monster()
        else:
            self.add_new_monster()

    def add_old_monster(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        images = MONSTER_IMAGES_R if right else MONSTER_IMAGES_L
        mask = rand_color(MONSTER_MASK[0] if right else MONSTER_MASK[1])
        masks = [mask] * 4
        size = max(map(len, images[0]))
        self.entities.append(Entity(
            "monster", images,
            -size if right else width,
            2, 2 * (1 if right else -1), z=4,
            colour="green", masks=masks, rate=0.25
        ))

    def add_new_monster(self):
        _, width = self.dimensions()
        right = random.choice((True, False))
        if right:
            images = [
                lines("""         _???_?????????????????????_???_???????_a_a
       _{.`=`.}_??????_???_??????_{.`=`.}_????{/ ''\\_
 _????{.'  _  '.}????{.`'`.}????{.'  _  '.}??{|  ._oo)
{ \\??{/  .'?'.  \\}??{/ .-. \\}??{/  .'?'.  \\}?{/  |
"""),
                lines("""                       _???_????????????????????_a_a
  _??????_???_??????_{.`=`.}_??????_???_??????{/ ''\\_
 { \\????{.`'`.}????{.'  _  '.}????{.`'`.}????{|  ._oo)
  \\ \\??{/ .-. \\}??{/  .'?'.  \\}??{/ .-. \\}???{/  |
"""),
            ]
        else:
            images = [
                lines("""   a_a_???????_???_?????????????????????_???_
 _/'' \\}????_{.`=`.}_??????_???_??????_{.`=`.}_
(oo_.  |}??{.'  _  '.}????{.`'`.}????{.'  _  '.}????_
    |  \\}?{/  .'?'.  \\}??{/ .-. \\}??{/  .'?'.  \\}??/ }
"""),
                lines("""   a_a_????????????????????_   _
 _/'' \\}??????_???_??????_{.`=`.}_??????_???_??????_
(oo_.  |}????{.`'`.}????{.'  _  '.}????{.`'`.}????/ }
    |  \\}???{/ .-. \\}??{/  .'?'.  \\}??{/ .-. \\}??/ /
"""),
            ]
        mask = rand_color(MONSTER_MASK[0] if right else MONSTER_MASK[1])
        masks = [mask] * len(images)
        size = max(map(len, images[0]))
        self.entities.append(Entity(
            "new_monster", images,
            -size if right else width,
            2, 2 * (1 if right else -1), z=4,
            colour="green", masks=masks, rate=0.25
        ))

    def add_big_fish(self):
        if self.classic or random.random() < 0.5:
            self.add_big_fish_1()
        else:
            self.add_big_fish_2()

    def add_big_fish_1(self):
        height, width = self.dimensions()
        right = random.choice((True, False))
        img = BIG_FISH_1_IMAGES[0] if right else BIG_FISH_1_IMAGES[1]
        mask = rand_color(BIG_FISH_1_MASKS[0] if right else BIG_FISH_1_MASKS[1])
        size = max(map(len, img))
        max_y = 9
        min_y = height - len(img) - 1
        self.entities.append(Entity(
            "big_fish", [img],
            -size if right else width,
            random.randint(max_y, max(max_y, min_y)),
            3 * (1 if right else -1), z=2,
            colour="yellow", masks=[mask]
        ))

    def add_big_fish_2(self):
        height, width = self.dimensions()
        right = random.choice((True, False))
        img = BIG_FISH_2_IMAGES[0] if right else BIG_FISH_2_IMAGES[1]
        mask = rand_color(BIG_FISH_2_MASKS[0] if right else BIG_FISH_2_MASKS[1])
        size = max(map(len, img))
        max_y = 9
        min_y = height - len(img) - 1
        self.entities.append(Entity(
            "big_fish2", [img],
            -size if right else width,
            random.randint(max_y, max(max_y, min_y)),
            2.5 * (1 if right else -1), z=2,
            colour="yellow", masks=[mask]
        ))

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
        sharks = [ent for ent in self.entities if ent.kind in ("shark",)]
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
        target = max(1, max(0, height - 9) * width // 350)
        while len([ent for ent in self.entities if ent.kind == "fish"]) < target:
            self.add_fish()
        visitors = {"shark", "ship", "whale", "monster", "new_monster", "big_fish", "big_fish2"}
        centerpieces = {"shark", "whale"}
        if now >= self.next_centerpiece and not any(ent.kind in centerpieces for ent in self.entities):
            random.choice((self.add_shark, self.add_whale))()
            self.next_centerpiece = now + random.uniform(38, 58)
            return
        if now >= self.next_visitor and not any(ent.kind in visitors for ent in self.entities):
            self.add_visitor()
            self.next_visitor = now + random.uniform(9, 18)

    def write_char(self, y, x, ch, colour_pair, width_limit):
        if y < 0 or x < 0 or x >= width_limit:
            return
        try:
            self.window.addch(y, x, ch, colour_pair)
        except curses.error:
            pass

    def draw(self):
        height, width = self.dimensions()
        self.window.erase()
        if height < 9 or width < 12:
            self.write_str(0, 0, "Resize terminal (minimum 12x9)", "yellow", width)
        else:
            for ent in sorted(self.entities, key=lambda item: item.z, reverse=True):
                mask = ent.cur_mask
                for row, text in enumerate(ent.image):
                    y = int(ent.y) + row
                    if mask and row < len(mask):
                        for col, ch in enumerate(text):
                            mch = mask[row][col] if col < len(mask[row]) else " "
                            if ch == " ":
                                continue
                            if mch != " ":
                                pair = self.mask_palette.get(mch, 0)
                                self.write_char(y, int(ent.x) + col, ch, pair, width)
                            else:
                                pair = self.palette.get(ent.colour, 0)
                                self.write_char(y, int(ent.x) + col, ch, pair, width)
                    else:
                        self.write_str(y, int(ent.x), text, ent.colour, width)
            label = "PAUSED - p resumes" if self.paused else "q quit  p pause  r reset"
            self.write_str(height - 1, 1, label[:max(0, width - 2)], "yellow" if self.paused else "cyan", width)
        self.window.refresh()

    def write_str(self, y, x, text, colour, width_limit):
        height, _ = self.dimensions()
        if not 0 <= y < height:
            return
        if x >= width_limit:
            return
        skip = max(0, -x)
        visible = text[skip:max(skip, width_limit - x)]
        if visible:
            try:
                self.window.addstr(y, max(0, x), visible, self.palette.get(colour, 0))
            except curses.error:
                pass


def make_palette():
    values = {
        "cyan": curses.COLOR_CYAN,
        "yellow": curses.COLOR_YELLOW,
        "green": curses.COLOR_GREEN,
        "magenta": curses.COLOR_MAGENTA,
        "blue": curses.COLOR_BLUE,
        "red": curses.COLOR_RED,
        "white": curses.COLOR_WHITE,
        "black": -1,
    }
    if not curses.has_colors():
        return {name: 0 for name in values}
    curses.start_color()
    curses.use_default_colors()
    result = {}
    for pair, (name, value) in enumerate(values.items(), 1):
        curses.init_pair(pair, value, -1)
        result[name] = curses.color_pair(pair)
    return result


def make_mask_palette():
    letter_colour = {
        "c": curses.COLOR_CYAN, "C": curses.COLOR_CYAN,
        "r": curses.COLOR_RED, "R": curses.COLOR_RED,
        "y": curses.COLOR_YELLOW, "Y": curses.COLOR_YELLOW,
        "b": curses.COLOR_BLUE, "B": curses.COLOR_BLUE,
        "g": curses.COLOR_GREEN, "G": curses.COLOR_GREEN,
        "m": curses.COLOR_MAGENTA, "M": curses.COLOR_MAGENTA,
        "W": curses.COLOR_WHITE,
    }
    if not curses.has_colors():
        return {ch: 0 for ch in letter_colour}
    result = {}
    for pair, (ch, value) in enumerate(letter_colour.items(), 100):
        curses.init_pair(pair, value, -1)
        result[ch] = curses.color_pair(pair)
    return result


def run(window, classic):
    height, width = window.getmaxyx()
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    window.keypad(True)
    window.nodelay(True)
    aquarium = Aquarium(window, classic)
    aquarium.palette = make_palette()
    aquarium.mask_palette = make_mask_palette()
    previous = time.monotonic()
    while True:
        current = time.monotonic()
        elapsed = min(0.15, current - previous)
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
    parser = argparse.ArgumentParser(description="ASCII aquarium matching reference art")
    parser.add_argument("-c", "--classic", action="store_true", help="use classic creature variants")
    args = parser.parse_args()
    try:
        curses.wrapper(run, args.classic)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
