#!/usr/bin/env python3
import argparse
import os
import random
import sys


FACES = {
    'b': ('==', '  '),
    'd': ('xx', 'U '),
    'g': ('$$', '  '),
    'p': ('@@', '  '),
    's': ('**', 'U '),
    't': ('--', '  '),
    'w': ('OO', '  '),
    'y': ('..', '  '),
}

COWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cows')


def list_cows():
    names = []
    for entry in os.listdir(COWS_DIR):
        if entry.endswith('.cow'):
            names.append(entry[:-4])
    names.sort()
    return names


def get_cow(name_or_path):
    if os.path.isfile(name_or_path):
        path = name_or_path
    else:
        path = os.path.join(COWS_DIR, name_or_path + '.cow')
        if not os.path.isfile(path):
            path = os.path.join(COWS_DIR, 'default.cow')
    with open(path, 'r', encoding='utf-8') as f:
        return parse_cow(f.read())


def parse_cow(text):
    lines = text.split('\n')
    body_start = -1
    body_end = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if '$the_cow' in stripped and ('<<' in stripped):
            body_start = i + 1
        if body_start >= 0 and stripped == 'EOC':
            body_end = i
            break
    if body_start < 0 or body_end < 0:
        return lambda face: ''

    template_lines = lines[body_start:body_end]

    def render(face):
        result = []
        for line in template_lines:
            line = line.replace('$thoughts', face['thoughts'])
            line = line.replace('$eyes', face['eyes'])
            line = line.replace('$eye', face['eyes'])
            line = line.replace('$tongue', face['tongue'])
            result.append(line.rstrip('\n'))
        return '\n'.join(result)

    return render


def make_balloon(text, wrap_width):
    if wrap_width:
        lines = []
        for para in text.split('\n'):
            if not para:
                lines.append('')
            else:
                words = para.split()
                cur = ''
                for w in words:
                    cand = (cur + ' ' + w).strip()
                    if len(cand) <= wrap_width:
                        cur = cand
                    else:
                        if cur:
                            lines.append(cur)
                        cur = w
                if cur:
                    lines.append(cur)
    else:
        lines = text.split('\n')

    if not lines:
        lines = ['']

    max_len = max(len(l) for l in lines)

    if len(lines) == 1:
        return f"< {lines[0]} >"
    else:
        parts = []
        for i, line in enumerate(lines):
            padded = line.ljust(max_len)
            if i == 0:
                parts.append(f"/ {padded} \\")
            elif i == len(lines) - 1:
                parts.append(f"\\ {padded} /")
            else:
                parts.append(f"| {padded} |")
        return '\n'.join(parts)


def do_it(text, eyes, tongue, cow_name, say_aloud, wrap_width, random_cow):
    if random_cow:
        all_cows = list_cows()
        cow_name = random.choice(all_cows)

    face = {'eyes': eyes, 'tongue': tongue, 'thoughts': '\\' if say_aloud else 'o'}
    render = get_cow(cow_name)
    balloon = make_balloon(text, wrap_width)
    return balloon + '\n' + render(face)


USAGE = """\
Usage: cowsay.py [-e eye_string] [-f cowfile] [-h] [-l] [-n] [-T tongue_string] [-W column] [-bdgpstwy] text

If any command-line arguments are left over after all switches have been
processed, they become the cow's message.

If --think is used, the cow will think its message instead of saying it.
"""


def main():
    parser = argparse.ArgumentParser(
        prog='cowsay',
        usage='%(prog)s [-e eye_string] [-f cowfile] [-h] [-l] [-n] [-T tongue_string] [-W column] [-bdgpstwy] text',
        add_help=False,
    )
    parser.add_argument('-e', default='oo')
    parser.add_argument('-T', default='  ')
    parser.add_argument('-W', default=40, type=int)
    parser.add_argument('-f', default='default')
    parser.add_argument('-n', action='store_true')
    parser.add_argument('-r', action='store_true')
    parser.add_argument('-l', action='store_true')
    parser.add_argument('-h', '--help', action='store_true')
    parser.add_argument('--think', action='store_true')
    parser.add_argument('-b', action='store_true')
    parser.add_argument('-d', action='store_true')
    parser.add_argument('-g', action='store_true')
    parser.add_argument('-p', action='store_true')
    parser.add_argument('-s', action='store_true')
    parser.add_argument('-t', action='store_true')
    parser.add_argument('-w', action='store_true')
    parser.add_argument('-y', action='store_true')
    parser.add_argument('text', nargs='*')

    args = parser.parse_args()

    if args.help:
        print(USAGE)
        return

    if args.l:
        cows = list_cows()
        print('  '.join(cows))
        return

    eyes = args.e
    tongue = args.T

    for mode_flag in ('b', 'd', 'g', 'p', 's', 't', 'w', 'y'):
        if getattr(args, mode_flag):
            eyes, tongue = FACES[mode_flag]

    wrap_width = None if args.n else args.W

    text = ' '.join(args.text) if args.text else None

    if text is None:
        stdin_data = sys.stdin.read()
        text = stdin_data.strip()
        if not text:
            print(USAGE)
            return

    result = do_it(
        text=text,
        eyes=eyes,
        tongue=tongue,
        cow_name=args.f,
        say_aloud=not args.think,
        wrap_width=wrap_width,
        random_cow=args.r,
    )
    print(result)


if __name__ == '__main__':
    main()