#!/usr/bin/env python3
import argparse
import sys

from clock import Clock, parse_duration


def main():
    parser = argparse.ArgumentParser(
        prog='tclock',
        description='Terminal clock with large seven-segment display.',
        add_help=False,
    )
    parser.add_argument('-h', '--help', action='store_true')
    parser.add_argument('-analog', action='store_true',
                        help='Analog clock with hour, minute, second hands')
    parser.add_argument('-aa', action='store_true',
                        help='Alias for -analog (anti-aliased not separately implemented)')
    parser.add_argument('-24', action='store_true', dest='fmt24',
                        help='Use 24-hour time format')
    parser.add_argument('-no-seconds', action='store_true',
                        help='Hide seconds')
    parser.add_argument('-no-blink', action='store_true',
                        help='Disable colon blinking')
    parser.add_argument('-box', action='store_true',
                        help='Draw a box around the clock')
    parser.add_argument('-color', type=str, default='red',
                        help='Clock color (red, green, yellow, blue, magenta, cyan, white)')
    parser.add_argument('-countdown', type=str, default='',
                        help='Countdown duration (e.g. 5m, 1h30m, 2d)')
    parser.add_argument('-tail', type=str, default='',
                        help='Tail a file while showing the clock')
    parser.add_argument('-c', action='store_true', dest='continuous',
                        help='Continuous update mode (for analog)')
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()

    if args.help:
        print('Usage: tclock [-analog] [-24] [-countdown DURATION] [-no-seconds]')
        print('              [-no-blink] [-box] [-color COLOR]')
        print()
        print('Terminal clock. Displays current time in large 7-segment digits.')
        print('Press q or Ctrl-C to quit.')
        sys.exit(0)

    countdown_seconds = 0
    if args.countdown:
        total = parse_duration(args.countdown)
        if total is None:
            print(f'error: invalid duration: {args.countdown}')
            sys.exit(1)
        countdown_seconds = total

    clock = Clock(
        fmt24=args.fmt24,
        show_seconds=not args.no_seconds,
        blink_enabled=not args.no_blink,
        boxed=args.box,
        color=args.color,
        analog=args.analog or args.aa,
        countdown=countdown_seconds,
    )
    clock.run()


if __name__ == '__main__':
    main()