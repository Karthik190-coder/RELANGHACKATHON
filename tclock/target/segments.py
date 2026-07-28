HEIGHT = 5
WIDTH = 4

SEGMENTS = [
    [' ━━', '┃  ┃', '    ', '┃  ┃', ' ━━'],
    ['    ', '   ┃', '    ', '   ┃', '    '],
    [' ━━', '   ┃', ' ━━', '┃   ', ' ━━'],
    [' ━━', '   ┃', ' ━━', '   ┃', ' ━━'],
    ['    ', '┃  ┃', ' ━━', '   ┃', '    '],
    [' ━━', '┃   ', ' ━━', '   ┃', ' ━━'],
    [' ━━', '┃   ', ' ━━', '┃  ┃', ' ━━'],
    [' ━━', '   ┃', '    ', '   ┃', '    '],
    [' ━━', '┃  ┃', ' ━━', '┃  ┃', ' ━━'],
    [' ━━', '┃  ┃', ' ━━', '   ┃', ' ━━'],
]

COLON_BLINK = [' ::', '    ', '    ', '    ', '    ']
COLON_DOT = [' ..', '    ', '    ', '    ', '    ']


class SevenSegmentRenderer:
    def __init__(self):
        self.segments = SEGMENTS
        self.colon_on = COLON_BLINK
        self.colon_off = COLON_DOT
        self.height = HEIGHT
        self.width = WIDTH

    def render(self, num_str: str, blink: bool) -> str:
        lines = ['' for _ in range(self.height)]
        for ch in num_str:
            d = self._digit(ch, blink)
            for i in range(self.height):
                lines[i] += d[i].ljust(self.width)
        return '\n'.join(lines)

    def _digit(self, ch: str, blink: bool):
        if ch == ':':
            return self.colon_on if blink else self.colon_off
        idx = ord(ch) - 48
        if idx < 0 or idx > 9:
            return self.colon_on if blink else self.colon_off
        return self.segments[idx]