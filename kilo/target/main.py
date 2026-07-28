import sys
import os
import termios
import tty
import signal
import time
import re

KILO_VERSION = "0.0.1"

HL_NORMAL = 0
HL_NONPRINT = 1
HL_COMMENT = 2
HL_MLCOMMENT = 3
HL_KEYWORD1 = 4
HL_KEYWORD2 = 5
HL_STRING = 6
HL_NUMBER = 7
HL_MATCH = 8

KEY_NULL = 0
CTRL_C = 3
CTRL_D = 4
CTRL_F = 6
CTRL_H = 8
TAB = 9
CTRL_L = 12
ENTER = 13
CTRL_Q = 17
CTRL_S = 19
CTRL_U = 21
ESC = 27
BACKSPACE = 127
ARROW_LEFT = 1000
ARROW_RIGHT = 1001
ARROW_UP = 1002
ARROW_DOWN = 1003
DEL_KEY = 1004
HOME_KEY = 1005
END_KEY = 1006
PAGE_UP = 1007
PAGE_DOWN = 1008

C_HL_extensions = [".c", ".h", ".cpp", ".hpp", ".cc"]
C_HL_keywords = [
    "auto", "break", "case", "continue", "default", "do", "else", "enum",
    "extern", "for", "goto", "if", "register", "return", "sizeof", "static",
    "struct", "switch", "typedef", "union", "volatile", "while", "NULL",
    "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor", "class",
    "compl", "constexpr", "const_cast", "deltype", "delete", "dynamic_cast",
    "explicit", "export", "false", "friend", "inline", "mutable", "namespace",
    "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq",
    "private", "protected", "public", "reinterpret_cast", "static_assert",
    "static_cast", "template", "this", "thread_local", "throw", "true", "try",
    "typeid", "typename", "virtual", "xor", "xor_eq",
    "int|", "long|", "double|", "float|", "char|", "unsigned|", "signed|",
    "void|", "short|", "auto|", "const|", "bool|",
]

HLDB = [
    {
        "filematch": C_HL_extensions,
        "keywords": C_HL_keywords,
        "scs": "//",
        "mcs": "/*",
        "mce": "*/",
        "flags": (1 << 0) | (1 << 1),
    }
]

class E:
    cx = 0
    cy = 0
    rowoff = 0
    coloff = 0
    screenrows = 24
    screencols = 80
    numrows = 0
    row = []
    dirty = 0
    filename = None
    statusmsg = ""
    statusmsg_time = 0
    syntax = None

orig_termios = None

def enable_raw_mode():
    global orig_termios
    if orig_termios is not None:
        return
    if not sys.stdin.isatty():
        print("Not a terminal", file=sys.stderr)
        sys.exit(1)
    fd = sys.stdin.fileno()
    orig_termios = termios.tcgetattr(fd)
    raw = termios.tcgetattr(fd)
    raw[0] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
    raw[1] &= ~(termios.OPOST)
    raw[2] |= termios.CS8
    raw[3] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
    raw[6][termios.VMIN] = 0
    raw[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSAFLUSH, raw)

def disable_raw_mode():
    global orig_termios
    if orig_termios is not None:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, orig_termios)
        orig_termios = None

def editor_at_exit():
    disable_raw_mode()
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()

def read_byte():
    return os.read(sys.stdin.fileno(), 1)

def editor_read_key():
    while True:
        c = read_byte()
        if len(c) == 0:
            continue
        c = c[0]
        break

    while True:
        if c != ESC:
            return c

        seq1 = read_byte()
        if len(seq1) == 0:
            return ESC
        seq2 = read_byte()
        if len(seq2) == 0:
            return ESC

        seq = [seq1[0], seq2[0]]

        if seq[0] == ord('['):
            if seq[1] >= ord('0') and seq[1] <= ord('9'):
                seq3 = read_byte()
                if len(seq3) == 0:
                    return ESC
                if seq3[0] == ord('~'):
                    if seq[1] == ord('3'):
                        return DEL_KEY
                    elif seq[1] == ord('5'):
                        return PAGE_UP
                    elif seq[1] == ord('6'):
                        return PAGE_DOWN
            else:
                if seq[1] == ord('A'):
                    return ARROW_UP
                elif seq[1] == ord('B'):
                    return ARROW_DOWN
                elif seq[1] == ord('C'):
                    return ARROW_RIGHT
                elif seq[1] == ord('D'):
                    return ARROW_LEFT
                elif seq[1] == ord('H'):
                    return HOME_KEY
                elif seq[1] == ord('F'):
                    return END_KEY
        elif seq[0] == ord('O'):
            if seq[1] == ord('H'):
                return HOME_KEY
            elif seq[1] == ord('F'):
                return END_KEY

        return ESC

def get_cursor_position():
    sys.stdout.write("\x1b[6n")
    sys.stdout.flush()
    buf = b""
    while True:
        b = read_byte()
        if len(b) == 0:
            break
        buf += b
        if b[0] == ord('R'):
            break
    if len(buf) < 3 or buf[0] != ESC or buf[1:2] != b"[":
        return None
    m = re.match(rb"\[(\d+);(\d+)R", buf)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def get_window_size():
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        import shutil
        sz = shutil.get_terminal_size()
        E.screencols = sz.columns
        E.screenrows = sz.lines
        return 0
    return -1

def is_separator(c):
    return c == "\0" or c == " " or c in ",.()+-/*=~%[];"

def editor_row_has_open_comment(row):
    if row["hl"] and row["rsize"] > 0 and row["hl"][row["rsize"] - 1] == HL_MLCOMMENT:
        if row["rsize"] < 2 or row["render"][row["rsize"] - 2] != "*" or row["render"][row["rsize"] - 1] != "/":
            return True
    return False

def editor_update_syntax(row):
    row["hl"] = bytearray([HL_NORMAL]) * row["rsize"]

    if E.syntax is None:
        return

    keywords = E.syntax["keywords"]
    scs = E.syntax["scs"]
    mcs = E.syntax["mcs"]
    mce = E.syntax["mce"]

    p = row["render"]
    i = 0
    while i < len(p) and (p[i] == " " or p[i] == "\t"):
        i += 1

    prev_sep = True
    in_string = 0
    in_comment = False

    if row["idx"] > 0 and editor_row_has_open_comment(E.row[row["idx"] - 1]):
        in_comment = True

    while i < len(p):
        if prev_sep and i + 1 < len(p) and p[i] == scs[0] and p[i + 1] == scs[1]:
            for j in range(i, len(p)):
                row["hl"][j] = HL_COMMENT
            break

        if in_comment:
            row["hl"][i] = HL_MLCOMMENT
            if i + 1 < len(p) and p[i] == mce[0] and p[i + 1] == mce[1]:
                row["hl"][i + 1] = HL_MLCOMMENT
                i += 2
                prev_sep = True
                in_comment = False
                continue
            else:
                prev_sep = False
                i += 1
                continue
        elif i + 1 < len(p) and p[i] == mcs[0] and p[i + 1] == mcs[1]:
            row["hl"][i] = HL_MLCOMMENT
            row["hl"][i + 1] = HL_MLCOMMENT
            i += 2
            in_comment = True
            prev_sep = False
            continue

        if in_string:
            row["hl"][i] = HL_STRING
            if p[i] == "\\":
                if i + 1 < len(p):
                    row["hl"][i + 1] = HL_STRING
                    i += 2
                    prev_sep = False
                    continue
            if p[i] == chr(in_string):
                in_string = 0
            i += 1
            continue
        else:
            if p[i] == '"' or p[i] == "'":
                in_string = ord(p[i])
                row["hl"][i] = HL_STRING
                i += 1
                prev_sep = False
                continue

        ch = ord(p[i])
        if ch < 32 or ch == 127:
            row["hl"][i] = HL_NONPRINT
            i += 1
            prev_sep = False
            continue

        if (48 <= ch <= 57 and (prev_sep or (i > 0 and row["hl"][i - 1] == HL_NUMBER))) or \
           (ch == 0x2e and i > 0 and row["hl"][i - 1] == HL_NUMBER):
            row["hl"][i] = HL_NUMBER
            i += 1
            prev_sep = False
            continue

        if prev_sep:
            matched = False
            for kw in keywords:
                kw2 = kw.endswith("|")
                klen = len(kw) - 1 if kw2 else len(kw)
                if klen == 0:
                    continue
                kw_start = kw[:-1] if kw2 else kw

                if p[i:i + klen] == kw_start:
                    next_char = p[i + klen] if i + klen < len(p) else "\0"
                    if is_separator(next_char):
                        hl_type = HL_KEYWORD2 if kw2 else HL_KEYWORD1
                        for k in range(klen):
                            row["hl"][i + k] = hl_type
                        i += klen
                        matched = True
                        break
            if matched:
                prev_sep = False
                continue

        prev_sep = is_separator(p[i])
        i += 1

    oc = editor_row_has_open_comment(row)
    if row["hl_oc"] != oc and row["idx"] + 1 < E.numrows:
        editor_update_syntax(E.row[row["idx"] + 1])
    row["hl_oc"] = oc

def editor_syntax_to_color(hl):
    if hl == HL_COMMENT or hl == HL_MLCOMMENT:
        return 36
    elif hl == HL_KEYWORD1:
        return 33
    elif hl == HL_KEYWORD2:
        return 32
    elif hl == HL_STRING:
        return 35
    elif hl == HL_NUMBER:
        return 31
    elif hl == HL_MATCH:
        return 34
    return 37

def editor_select_syntax_highlight(filename):
    for s in HLDB:
        for pat in s["filematch"]:
            idx = filename.rfind(pat)
            if idx != -1:
                if pat[0] != "." or idx + len(pat) == len(filename):
                    E.syntax = s
                    return

def editor_update_row(row):
    render = ""
    for ch in row["chars"]:
        if ch == "\t":
            render += " "
            while (len(render) + 1) % 8 != 0:
                render += " "
        else:
            render += ch

    row["render"] = render
    row["rsize"] = len(render)
    editor_update_syntax(row)

def editor_insert_row(at, s):
    if at > E.numrows:
        return
    new_row = {"idx": at, "chars": s, "size": len(s), "render": "", "rsize": 0, "hl": None, "hl_oc": False}
    E.row.insert(at, new_row)
    for j in range(at + 1, E.numrows + 1):
        E.row[j]["idx"] += 1
    editor_update_row(new_row)
    E.numrows += 1
    E.dirty += 1

def editor_free_row(row):
    row["render"] = None
    row["chars"] = None
    row["hl"] = None

def editor_del_row(at):
    if at >= E.numrows:
        return
    editor_free_row(E.row[at])
    E.row.pop(at)
    for j in range(at, E.numrows - 1):
        E.row[j]["idx"] += 1
    E.numrows -= 1
    E.dirty += 1

def editor_rows_to_string():
    lines = []
    for j in range(E.numrows):
        lines.append(E.row[j]["chars"])
    return "\n".join(lines)

def editor_row_insert_char(row, at, c):
    if at > row["size"]:
        padlen = at - row["size"]
        row["chars"] += " " * padlen + c
        row["size"] = len(row["chars"])
    else:
        row["chars"] = row["chars"][:at] + c + row["chars"][at:]
        row["size"] += 1
    editor_update_row(row)
    E.dirty += 1

def editor_row_append_string(row, s):
    row["chars"] += s
    row["size"] = len(row["chars"])
    editor_update_row(row)
    E.dirty += 1

def editor_row_del_char(row, at):
    if row["size"] <= at:
        return
    row["chars"] = row["chars"][:at] + row["chars"][at + 1:]
    editor_update_row(row)
    row["size"] -= 1
    E.dirty += 1

def editor_insert_char(c):
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if row is None:
        while E.numrows <= filerow:
            editor_insert_row(E.numrows, "")
    row = E.row[filerow]
    editor_row_insert_char(row, filecol, chr(c))
    if E.cx == E.screencols - 1:
        E.coloff += 1
    else:
        E.cx += 1
    E.dirty += 1

def editor_insert_newline():
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if row is None:
        if filerow == E.numrows:
            editor_insert_row(filerow, "")
            E.cx = 0
            E.coloff = 0
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1
        return

    if filecol >= row["size"]:
        filecol = row["size"]
    if filecol == 0:
        editor_insert_row(filerow, "")
    else:
        editor_insert_row(filerow + 1, row["chars"][filecol:])
        row["chars"] = row["chars"][:filecol]
        row["size"] = filecol
        editor_update_row(row)

    if E.cy == E.screenrows - 1:
        E.rowoff += 1
    else:
        E.cy += 1
    E.cx = 0
    E.coloff = 0

def editor_del_char():
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if row is None or (filecol == 0 and filerow == 0):
        return
    if filecol == 0:
        filecol = E.row[filerow - 1]["size"]
        editor_row_append_string(E.row[filerow - 1], row["chars"])
        editor_del_row(filerow)
        if E.cy == 0:
            E.rowoff -= 1
        else:
            E.cy -= 1
        E.cx = filecol
        if E.cx >= E.screencols:
            shift = E.cx - E.screencols + 1
            E.cx -= shift
            E.coloff += shift
    else:
        editor_row_del_char(row, filecol - 1)
        if E.cx == 0 and E.coloff:
            E.coloff -= 1
        else:
            E.cx -= 1
    if row:
        editor_update_row(row)
    E.dirty += 1

def editor_open(filename):
    E.dirty = 0
    E.filename = filename

    try:
        with open(filename, "r") as f:
            content = f.read()
        lines = content.split("\n")
        if len(lines) > 0 and lines[-1] == "":
            lines.pop()
        for line in lines:
            if line.endswith("\r"):
                line = line[:-1]
            editor_insert_row(E.numrows, line)
    except FileNotFoundError:
        return
    except IOError as e:
        print("Opening file:", e, file=sys.stderr)
        sys.exit(1)
    E.dirty = 0

def editor_save():
    content = editor_rows_to_string()
    buf = content.encode("utf-8")
    try:
        with open(E.filename, "wb") as f:
            f.write(buf)
    except IOError as e:
        editor_set_status_message("Can't save! I/O error: " + str(e))
        return 1
    E.dirty = 0
    editor_set_status_message("%d bytes written on disk" % len(buf))
    return 0

ab = ""

def ab_append(s):
    global ab
    ab += s

def editor_refresh_screen():
    global ab
    ab = ""

    ab_append("\x1b[?25l")
    ab_append("\x1b[H")

    for y in range(E.screenrows):
        filerow = E.rowoff + y

        if filerow >= E.numrows:
            ab_append("\x1b[0K\r\n")
            continue

        r = E.row[filerow]
        length = r["rsize"] - E.coloff
        current_color = -1

        if length > 0:
            if length > E.screencols:
                length = E.screencols
            c = r["render"][E.coloff:]
            hl = r["hl"]
            hl_offset = E.coloff

            for j in range(length):
                hl_type = hl[hl_offset + j]
                if hl_type == HL_NONPRINT:
                    ab_append("\x1b[7m")
                    code = ord(c[j])
                    if code <= 26:
                        sym = chr(0x40 + code)
                    else:
                        sym = "?"
                    ab_append(sym)
                    ab_append("\x1b[0m")
                elif hl_type == HL_NORMAL:
                    if current_color != -1:
                        ab_append("\x1b[39m")
                        current_color = -1
                    ab_append(c[j])
                else:
                    color = editor_syntax_to_color(hl_type)
                    if color != current_color:
                        ab_append("\x1b[%dm" % color)
                        current_color = color
                    ab_append(c[j])

        ab_append("\x1b[39m")
        ab_append("\x1b[0K")
        ab_append("\r\n")

    ab_append("\x1b[0K")
    ab_append("\x1b[7m")

    fname = E.filename if E.filename else "[No Name]"
    if len(fname) > 20:
        fname = fname[:20]
    status = "%s - %d lines%s" % (fname, E.numrows, " (modified)" if E.dirty else "")
    rstatus = "%d/%d" % (E.rowoff + E.cy + 1, E.numrows)
    if len(status) > E.screencols:
        status = status[:E.screencols]
    ab_append(status)
    length = len(status)
    while length < E.screencols:
        if E.screencols - length == len(rstatus):
            ab_append(rstatus)
            break
        else:
            ab_append(" ")
            length += 1

    ab_append("\x1b[0m\r\n")
    ab_append("\x1b[0K")

    if E.statusmsg and (time.time() * 1000 - E.statusmsg_time < 5000):
        msglen = len(E.statusmsg)
        ab_append(E.statusmsg if msglen <= E.screencols else E.statusmsg[:E.screencols])

    cx = 1
    filerow = E.rowoff + E.cy
    row = E.row[filerow] if filerow < E.numrows else None
    if row:
        for j in range(E.coloff, E.cx + E.coloff):
            if j < len(row["chars"]) and row["chars"][j] == "\t":
                cx += 7 - (cx % 8)
            cx += 1

    ab_append("\x1b[%d;%dH" % (E.cy + 1, cx))
    ab_append("\x1b[?25h")

    sys.stdout.write(ab)
    sys.stdout.flush()

def editor_set_status_message(fmt, *args):
    E.statusmsg = fmt % args
    E.statusmsg_time = time.time() * 1000

KILO_QUERY_LEN = 256

def editor_find():
    query = ""
    last_match = -1
    find_next = 0
    saved_hl_line = -1
    saved_hl = None

    saved_cx = E.cx
    saved_cy = E.cy
    saved_coloff = E.coloff
    saved_rowoff = E.rowoff

    def find_restore_hl():
        nonlocal saved_hl, saved_hl_line
        if saved_hl is not None:
            E.row[saved_hl_line]["hl"] = saved_hl
            saved_hl = None

    while True:
        editor_set_status_message("Search: %s (Use ESC/Arrows/Enter)" % query)
        editor_refresh_screen()

        c = editor_read_key()
        if c == DEL_KEY or c == CTRL_H or c == BACKSPACE:
            if len(query) > 0:
                query = query[:-1]
                last_match = -1
        elif c == ESC or c == ENTER:
            if c == ESC:
                E.cx = saved_cx
                E.cy = saved_cy
                E.coloff = saved_coloff
                E.rowoff = saved_rowoff
            find_restore_hl()
            editor_set_status_message("")
            return
        elif c == ARROW_RIGHT or c == ARROW_DOWN:
            find_next = 1
        elif c == ARROW_LEFT or c == ARROW_UP:
            find_next = -1
        elif 32 <= c < 127:
            if len(query) < KILO_QUERY_LEN:
                query += chr(c)
                last_match = -1

        if last_match == -1:
            find_next = 1
        if find_next:
            match = None
            match_offset = 0
            current = last_match

            for i in range(E.numrows):
                current += find_next
                if current == -1:
                    current = E.numrows - 1
                elif current == E.numrows:
                    current = 0
                idx = E.row[current]["render"].find(query)
                if idx != -1:
                    match = True
                    match_offset = idx
                    break

            find_next = 0
            find_restore_hl()

            if match:
                row = E.row[current]
                last_match = current
                if row["hl"] is not None:
                    saved_hl_line = current
                    saved_hl = bytearray(row["hl"])
                    for k in range(len(query)):
                        row["hl"][match_offset + k] = HL_MATCH
                E.cy = 0
                E.cx = match_offset
                E.rowoff = current
                E.coloff = 0
                if E.cx > E.screencols:
                    diff = E.cx - E.screencols
                    E.cx -= diff
                    E.coloff += diff

def editor_move_cursor(key):
    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None

    if key == ARROW_LEFT:
        if E.cx == 0:
            if E.coloff:
                E.coloff -= 1
            elif filerow > 0:
                E.cy -= 1
                E.cx = E.row[filerow - 1]["size"]
                if E.cx > E.screencols - 1:
                    E.coloff = E.cx - E.screencols + 1
                    E.cx = E.screencols - 1
        else:
            E.cx -= 1
    elif key == ARROW_RIGHT:
        if row and filecol < row["size"]:
            if E.cx == E.screencols - 1:
                E.coloff += 1
            else:
                E.cx += 1
        elif row and filecol == row["size"]:
            E.cx = 0
            E.coloff = 0
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1
    elif key == ARROW_UP:
        if E.cy == 0:
            if E.rowoff:
                E.rowoff -= 1
        else:
            E.cy -= 1
    elif key == ARROW_DOWN:
        if filerow < E.numrows:
            if E.cy == E.screenrows - 1:
                E.rowoff += 1
            else:
                E.cy += 1

    filerow = E.rowoff + E.cy
    filecol = E.coloff + E.cx
    row = E.row[filerow] if filerow < E.numrows else None
    rowlen = row["size"] if row else 0
    if filecol > rowlen:
        E.cx -= filecol - rowlen
        if E.cx < 0:
            E.coloff += E.cx
            E.cx = 0

KILO_QUIT_TIMES = 3
quit_times = KILO_QUIT_TIMES

def editor_process_keypress():
    global quit_times
    c = editor_read_key()

    if c == ENTER:
        editor_insert_newline()
    elif c == CTRL_C:
        pass
    elif c == CTRL_Q:
        if E.dirty and quit_times > 0:
            editor_set_status_message(
                "WARNING!!! File has unsaved changes. Press Ctrl-Q %d more times to quit." % quit_times
            )
            quit_times -= 1
            return
        editor_at_exit()
        sys.exit(0)
    elif c == CTRL_S:
        editor_save()
    elif c == CTRL_F:
        editor_find()
    elif c == BACKSPACE or c == CTRL_H or c == DEL_KEY:
        editor_del_char()
    elif c == PAGE_UP or c == PAGE_DOWN:
        if c == PAGE_UP and E.cy != 0:
            E.cy = 0
        elif c == PAGE_DOWN and E.cy != E.screenrows - 1:
            E.cy = E.screenrows - 1
        times = E.screenrows
        while times > 0:
            editor_move_cursor(ARROW_UP if c == PAGE_UP else ARROW_DOWN)
            times -= 1
    elif c == ARROW_UP or c == ARROW_DOWN or c == ARROW_LEFT or c == ARROW_RIGHT:
        editor_move_cursor(c)
    elif c == CTRL_L:
        pass
    elif c == ESC:
        pass
    else:
        editor_insert_char(c)

    quit_times = KILO_QUIT_TIMES

def update_window_size():
    if get_window_size() == -1:
        print("Unable to query the screen for size (columns / rows)", file=sys.stderr)
        sys.exit(1)
    E.screenrows -= 2

def handle_sigwinch(signum, frame):
    update_window_size()
    if E.cy > E.screenrows:
        E.cy = E.screenrows - 1
    if E.cx > E.screencols:
        E.cx = E.screencols - 1
    editor_refresh_screen()

def init_editor():
    E.cx = 0
    E.cy = 0
    E.rowoff = 0
    E.coloff = 0
    E.numrows = 0
    E.row = []
    E.dirty = 0
    E.filename = None
    E.syntax = None
    update_window_size()

def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <filename>", file=sys.stderr)
        sys.exit(1)

    init_editor()
    editor_select_syntax_highlight(sys.argv[1])
    editor_open(sys.argv[1])
    enable_raw_mode()

    signal.signal(signal.SIGWINCH, handle_sigwinch)

    editor_set_status_message("HELP: Ctrl-S = save | Ctrl-Q = quit | Ctrl-F = find")

    while True:
        editor_refresh_screen()
        editor_process_keypress()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        editor_at_exit()
        print(e, file=sys.stderr)
        sys.exit(1)
