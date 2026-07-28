import random

# Constants from sl.h
D51HEIGHT = 10
D51FUNNEL = 7
D51LENGTH = 83
D51PATTERNS = 6

D51STR1 = "      ====        ________                ___________ "
D51STR2 = "  _D _|  |_______/        \\__I_I_____===__|_________| "
D51STR3 = "   |(_)---  |   H\\________/ |   |        =|___ ___|   "
D51STR4 = "   /     |  |   H  |  |     |   |         ||_| |_||   "
D51STR5 = "  |      |  |   H  |__--------------------| [___] |   "
D51STR6 = "  | ________|___H__/__|_____/[][]~\\_______|       |   "
D51STR7 = "  |/ |   |-----------I_____I [][] []  D   |=======|__ "

D51WHL11 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ "
D51WHL12 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        "
D51WHL13 = "  \\_/      \\O=====O=====O=====O_/      \\_/            "

D51WHL21 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ "
D51WHL22 = " |/-=|___|=O=====O=====O=====O   |_____/~\\___/        "
D51WHL23 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "

D51WHL31 = "__/ =| o |=-O=====O=====O=====O \\ ____Y___________|__ "
D51WHL32 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        "
D51WHL33 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "

D51WHL41 = "__/ =| o |=-~O=====O=====O=====O\\ ____Y___________|__ "
D51WHL42 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        "
D51WHL43 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "

D51WHL51 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ "
D51WHL52 = " |/-=|___|=   O=====O=====O=====O|_____/~\\___/        "
D51WHL53 = "  \\_/      \\__/  \\__/  \\__/  \\__/      \\_/            "

D51WHL61 = "__/ =| o |=-~~\\  /~~\\  /~~\\  /~~\\ ____Y___________|__ "
D51WHL62 = " |/-=|___|=    ||    ||    ||    |_____/~\\___/        "
D51WHL63 = "  \\_/      \\_O=====O=====O=====O/      \\_/            "

D51DEL = "                                                      "

COAL01 = "                              "
COAL02 = "                              "
COAL03 = "    _________________         "
COAL04 = "   _|                \\_____A  "
COAL05 = " =|                        |  "
COAL06 = " -|                        |  "
COAL07 = "__|________________________|_ "
COAL08 = "|__________________________|_ "
COAL09 = "   |_D__D__D_|  |_D__D__D_|   "
COAL10 = "    \\_/   \\_/    \\_/   \\_/    "

COALDEL = "                              "

LOGOHEIGHT = 6
LOGOFUNNEL = 4
LOGOLENGTH = 84
LOGOPATTERNS = 6

LOGO1 = "     ++      +------ "
LOGO2 = "     ||      |+-+ |  "
LOGO3 = "   /---------|| | |  "
LOGO4 = "  + ========  +-+ |  "

LWHL11 = " _|--O========O~\\-+  "
LWHL12 = "//// \\_/      \\_/    "

LWHL21 = " _|--/O========O\\-+  "
LWHL22 = "//// \\_/      \\_/    "

LWHL31 = " _|--/~O========O-+  "
LWHL32 = "//// \\_/      \\_/    "

LWHL41 = " _|--/~\\------/~\\-+  "
LWHL42 = "//// \\_O========O    "

LWHL51 = " _|--/~\\------/~\\-+  "
LWHL52 = "//// \\O========O/    "

LWHL61 = " _|--/~\\------/~\\-+  "
LWHL62 = "//// O========O_/    "

LCOAL1 = "____                 "
LCOAL2 = "|   \\@@@@@@@@@@@     "
LCOAL3 = "|    \\@@@@@@@@@@@@@_ "
LCOAL4 = "|                  | "
LCOAL5 = "|__________________| "
LCOAL6 = "   (O)       (O)     "

LCAR1 = "____________________ "
LCAR2 = "|  ___ ___ ___ ___ | "
LCAR3 = "|  |_| |_| |_| |_| | "
LCAR4 = "|__________________| "
LCAR5 = "|__________________| "
LCAR6 = "   (O)        (O)    "

DELLN = "                     "

C51HEIGHT = 11
C51FUNNEL = 7
C51LENGTH = 87
C51PATTERNS = 6

C51DEL = "                                                       "

C51STR1 = "        ___                                            "
C51STR2 = "       _|_|_  _     __       __             ___________"
C51STR3 = "    D__/   \\_(_)___|  |__H__|  |_____I_Ii_()|_________|"
C51STR4 = "     | `---'   |:: `--'  H  `--'         |  |___ ___|  "
C51STR5 = "    +|~~~~~~~~++::~~~~~~~H~~+=====+~~~~~~|~~||_| |_||  "
C51STR6 = "    ||        | ::       H  +=====+      |  |::  ...|  "
C51STR7 = "|    | _______|_::-----------------[][]-----|       |  "

C51WH61 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__"
C51WH62 = "------'|oOo|==[]=-     ||      ||      |  ||=======_|__"
C51WH63 = "/~\\____|___|/~\\_|   O=======O=======O  |__|+-/~\\_|     "
C51WH64 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "

C51WH51 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__"
C51WH52 = "------'|oOo|===[]=-    ||      ||      |  ||=======_|__"
C51WH53 = "/~\\____|___|/~\\_|    O=======O=======O |__|+-/~\\_|     "
C51WH54 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "

C51WH41 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__"
C51WH42 = "------'|oOo|===[]=- O=======O=======O  |  ||=======_|__"
C51WH43 = "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     "
C51WH44 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "

C51WH31 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__"
C51WH32 = "------'|oOo|==[]=- O=======O=======O   |  ||=======_|__"
C51WH33 = "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     "
C51WH34 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "

C51WH21 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__"
C51WH22 = "------'|oOo|=[]=- O=======O=======O    |  ||=======_|__"
C51WH23 = "/~\\____|___|/~\\_|      ||      ||      |__|+-/~\\_|     "
C51WH24 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "

C51WH11 = "| /~~ ||   |-----/~~~~\\  /[I_____I][][] --|||_______|__"
C51WH12 = "------'|oOo|=[]=-      ||      ||      |  ||=======_|__"
C51WH13 = "/~\\____|___|/~\\_|  O=======O=======O   |__|+-/~\\_|     "
C51WH14 = "\\_/         \\_/  \\____/  \\____/  \\____/      \\_/       "

# Global states
ACCIDENT = 0
LOGO = 0
FLY = 0
C51 = 0
DANCE = 0
RAND = 0

COLS = 0
LINES = 0
N = 0

output_map = bytearray()
sl_step = 0

# Smoke states
S = []
smoke_sum = 0


def count_fn():
    offset = 21
    if LOGO >= 1:
        return -LOGOLENGTH - 1 - offset * (LOGO - 1)
    elif C51 == 1:
        return -C51LENGTH - 1
    else:
        return -D51LENGTH - 1


def addchModify(y, x, c):
    if y < 0 or x < 0 or x >= COLS or y >= LINES:
        return False
    output_map[y * (COLS + 1) + x] = ord(c)
    return True


def my_mvaddstr(y, x, s):
    idx = 0
    while x < 0:
        if idx >= len(s):
            return False
        idx += 1
        x += 1
    while idx < len(s):
        addchModify(y, x, s[idx])
        idx += 1
        x += 1
    return True


def option(arg_str):
    global ACCIDENT, LOGO, FLY, C51, DANCE, RAND
    idx = 0
    while idx < len(arg_str) and arg_str[idx] != '-':
        char = arg_str[idx]
        if char == 'l':
            LOGO += 1
        elif char == 'a':
            ACCIDENT = 1
        elif char == 'F':
            FLY = 1
        elif char == 'c':
            C51 = 1
        elif char == 'd':
            DANCE = 1
        elif char == 'r':
            RAND = 1
        idx += 1


def init(c, l, arg):
    global COLS, LINES, N, ACCIDENT, LOGO, FLY, C51, DANCE, RAND, output_map, sl_step, S, smoke_sum
    COLS = c
    LINES = l

    ACCIDENT = 0
    LOGO = 0
    FLY = 0
    C51 = 0
    DANCE = 0
    RAND = 0

    idx = 0
    while idx < len(arg):
        if arg[idx] == '-':
            option(arg[idx + 1:])
            idx += 1
            # Advance until the next '-' or end of string
            while idx < len(arg) and arg[idx] != '-':
                idx += 1
        else:
            idx += 1

    if RAND == 1:
        ACCIDENT |= random.randint(0, 1)
        LOGO |= random.randint(0, 1)
        FLY |= random.randint(0, 1)
        C51 |= random.randint(0, 1)
        DANCE |= random.randint(0, 1)

    N = -count_fn() + COLS - 1

    output_map = bytearray(b' ' * (LINES * (COLS + 1)))
    for x in range(LINES):
        output_map[x * (COLS + 1) + COLS] = ord('\n')
    output_map[-1] = 0

    sl_step = 0
    S = []
    smoke_sum = 0


def windowDestroy():
    global output_map
    output_map = bytearray()


def len_fn():
    return N


def step():
    global sl_step
    if sl_step < N:
        mapModify(sl_step)
        sl_step += 1
        null_idx = output_map.find(0)
        if null_idx != -1:
            return output_map[:null_idx].decode('utf-8', errors='replace')
        return output_map.decode('utf-8', errors='replace')
    elif sl_step == N:
        windowDestroy()
        sl_step += 1
        return None
    else:
        return None


def mapModify(mod):
    x = -mod + COLS - 1
    if LOGO >= 1:
        add_sl(x)
    elif C51 == 1:
        add_C51(x)
    else:
        add_D51(x)


def add_sl(x):
    sl_patterns = [
        [LOGO1, LOGO2, LOGO3, LOGO4, LWHL11, LWHL12, DELLN],
        [LOGO1, LOGO2, LOGO3, LOGO4, LWHL21, LWHL22, DELLN],
        [LOGO1, LOGO2, LOGO3, LOGO4, LWHL31, LWHL32, DELLN],
        [LOGO1, LOGO2, LOGO3, LOGO4, LWHL41, LWHL42, DELLN],
        [LOGO1, LOGO2, LOGO3, LOGO4, LWHL51, LWHL52, DELLN],
        [LOGO1, LOGO2, LOGO3, LOGO4, LWHL61, LWHL62, DELLN]
    ]

    coal = [LCOAL1, LCOAL2, LCOAL3, LCOAL4, LCOAL5, LCOAL6, DELLN]
    car = [LCAR1, LCAR2, LCAR3, LCAR4, LCAR5, LCAR6, DELLN]

    offset = 21
    py1 = 0
    py2 = 0
    py3 = 0

    y = LINES // 2 - 3

    if FLY == 1:
        y = int(x / 6) + LINES - int(COLS / 6) - LOGOHEIGHT
        py1 = 2
        py2 = 4
        py3 = 6

    for i in range(7):
        idx = int((LOGOLENGTH + offset * (LOGO - 1) + x) / 3) % LOGOPATTERNS
        my_mvaddstr(y + i, x, sl_patterns[idx][i])
        my_mvaddstr(y + i + py1, x + 21, coal[i])
        for j in range(LOGO + 1):
            yoffset = 2 * j * FLY
            my_mvaddstr(y + i + py3 + yoffset, x + 42 + offset * j, car[i])

    if ACCIDENT == 1:
        add_man(y + 1, x + 14)
        for j in range(LOGO + 1):
            yoffset = FLY * (2 + 2 * j)
            add_man(y + 1 + py2 + yoffset, x + 45 + offset * j)
            add_man(y + 1 + py2 + yoffset, x + 53 + offset * j)

    if DANCE == 1 and ACCIDENT == 0 and FLY == 0:
        add_mdancer(y - 2, x + 21)
        for j in range(LOGO + 1):
            add_mdancer(y + py2 - 2, x + 45 + offset * j)
            add_mdancer(y + py2 - 2, x + 50 + offset * j)
            add_mdancer(y + py2 - 2, x + 55 + offset * j)

    add_smoke(y - 1, x + LOGOFUNNEL)


def add_D51(x):
    d51_patterns = [
        [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL11, D51WHL12, D51WHL13, D51DEL],
        [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL21, D51WHL22, D51WHL23, D51DEL],
        [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL31, D51WHL32, D51WHL33, D51DEL],
        [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL41, D51WHL42, D51WHL43, D51DEL],
        [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL51, D51WHL52, D51WHL53, D51DEL],
        [D51STR1, D51STR2, D51STR3, D51STR4, D51STR5, D51STR6, D51STR7, D51WHL61, D51WHL62, D51WHL63, D51DEL]
    ]

    coal = [COAL01, COAL02, COAL03, COAL04, COAL05, COAL06, COAL07, COAL08, COAL09, COAL10, COALDEL]

    dy = 0
    y = LINES // 2 - 5

    if FLY == 1:
        y = int(x / 7) + LINES - int(COLS / 7) - D51HEIGHT
        dy = 1

    for i in range(11):
        idx = (D51LENGTH + x) % D51PATTERNS
        my_mvaddstr(y + i, x, d51_patterns[idx][i])
        my_mvaddstr(y + i + dy, x + 53, coal[i])

    if ACCIDENT == 1:
        add_man(y + 2, x + 43)
        add_man(y + 2, x + 47)

    if DANCE == 1 and ACCIDENT == 0 and FLY == 0:
        add_mdancer(y - 2, x + 43)
        add_fdancer(y - 2, x + 48)

    add_smoke(y - 1, x + D51FUNNEL)


def add_C51(x):
    c51_patterns = [
        [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH11, C51WH12, C51WH13, C51WH14, C51DEL],
        [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH21, C51WH22, C51WH23, C51WH24, C51DEL],
        [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH31, C51WH32, C51WH33, C51WH34, C51DEL],
        [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH41, C51WH42, C51WH43, C51WH44, C51DEL],
        [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH51, C51WH52, C51WH53, C51WH54, C51DEL],
        [C51STR1, C51STR2, C51STR3, C51STR4, C51STR5, C51STR6, C51STR7, C51WH61, C51WH62, C51WH63, C51WH64, C51DEL]
    ]

    coal = [COALDEL, COAL01, COAL02, COAL03, COAL04, COAL05, COAL06, COAL07, COAL08, COAL09, COAL10, COALDEL]

    dy = 0
    y = LINES // 2 - 5

    if FLY == 1:
        y = int(x / 7) + LINES - int(COLS / 7) - C51HEIGHT
        dy = 1

    for i in range(12):
        idx = (C51LENGTH + x) % C51PATTERNS
        my_mvaddstr(y + i, x, c51_patterns[idx][i])
        my_mvaddstr(y + i + dy, x + 55, coal[i])

    if ACCIDENT == 1:
        add_man(y + 3, x + 45)
        add_man(y + 3, x + 49)

    if DANCE == 1 and ACCIDENT == 0 and FLY == 0:
        add_mdancer(y - 1, x + 45)
        add_fdancer(y - 1, x + 50)

    add_smoke(y - 1, x + C51FUNNEL)


def add_man(y, x):
    man = [["", "(O)"], ["Help!", "\\O/"]]
    for i in range(2):
        idx = int((LOGOLENGTH + x) / 12) % 2
        my_mvaddstr(y + i, x, man[idx][i])


def add_fdancer(y, x):
    fdancer = [["\\\\0", "/\\", "|\\"], ["0//", "/\\", "/|"]]
    Efdancer = [["   ", "  ", "  "], ["   ", "  ", "  "]]
    for i in range(3):
        idx = int((LOGOLENGTH + x) / 12) % 2
        my_mvaddstr(y + i, x + 1, Efdancer[idx][i])
        my_mvaddstr(y + i, x, fdancer[idx][i])


def add_mdancer(y, x):
    mdancer = [["_O_", " #", "/\\"], ["(0)", " #", "/\\"], ["(O_", " #", "/\\"]]
    Emdancer = [["   ", "  ", "  "], ["   ", "  ", "  "], ["   ", "  ", "  "]]
    for i in range(3):
        idx = int((LOGOLENGTH + x) / 12) % 3
        my_mvaddstr(y + i, x + 1, Emdancer[idx][i])
        my_mvaddstr(y + i, x, mdancer[idx][i])


def add_smoke(y, x):
    global smoke_sum
    Smoke = [
        ["(   )", "(    )", "(    )", "(   )", "(  )", "(  )", "( )", "( )", "()", "()", "O", "O", "O", "O", "O", " "],
        ["(@@@)", "(@@@@)", "(@@@@)", "(@@@)", "(@@)", "(@@)", "(@)", "(@)", "@@", "@@", "@", "@", "@", "@", "@", " "]
    ]
    Eraser = ["     ", "      ", "      ", "     ", "    ", "    ", "   ", "   ", "  ", "  ", " ", " ", " ", " ", " ", " "]
    dy = [2, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    dx = [-2, -1, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3]

    if x % 4 == 0:
        for i in range(smoke_sum):
            my_mvaddstr(S[i]['y'], S[i]['x'], Eraser[S[i]['ptrn']])
            S[i]['y'] -= dy[S[i]['ptrn']]
            S[i]['x'] += dx[S[i]['ptrn']]
            if S[i]['ptrn'] < 15:
                S[i]['ptrn'] += 1
            my_mvaddstr(S[i]['y'], S[i]['x'], Smoke[S[i]['kind']][S[i]['ptrn']])

        my_mvaddstr(y, x, Smoke[smoke_sum % 2][0])
        S.append({
            'y': y,
            'x': x,
            'ptrn': 0,
            'kind': smoke_sum % 2
        })
        smoke_sum += 1
