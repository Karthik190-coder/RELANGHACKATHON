import os
import sys

CSI = '\033['


class TerminalRenderer:
    def __init__(self):
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
        self.width = 80
        self.height = 24
        self._detect_size()

    def _detect_size(self):
        try:
            self.width, self.height = os.get_terminal_size()
        except (ValueError, OSError):
            self.width, self.height = 80, 24

    def clear(self):
        self.write(CSI + '2J' + CSI + 'H')

    def hide_cursor(self):
        self.write(CSI + '?25l')

    def show_cursor(self):
        self.write(CSI + '?25h')

    def cursor_to(self, x: int, y: int):
        self.write(CSI + f'{y};{x}H')

    def set_color(self, color: str):
        idx = self._color_index(color)
        self.write(CSI + f'38;5;{idx}m')

    def reset_style(self):
        self.write(CSI + '0m')

    def set_bg(self, color_idx: int):
        self.write(CSI + f'48;5;{color_idx}m')

    def write(self, text: str):
        sys.stdout.write(text)

    def flush(self):
        sys.stdout.flush()

    def draw_centered(self, lines, y_offset=0, color='red'):
        self._detect_size()
        self.set_color(color)
        line_h = len(lines)
        max_w = max(len(l) for l in lines)
        start_y = max(1, (self.height - line_h) // 2 + y_offset)
        start_x = max(1, (self.width - max_w) // 2)
        for i, line in enumerate(lines):
            self.cursor_to(start_x + 1, start_y + i + 1)
            self.write(line)
        self.reset_style()

    def draw_boxed(self, lines, color='red'):
        self._detect_size()
        self.set_color(color)
        line_h = len(lines)
        max_w = max(len(l) for l in lines)
        start_y = max(1, (self.height - line_h) // 2)
        start_x = max(1, (self.width - max_w) // 2)
        y = start_y + 1
        box_w = max_w + 2
        self.cursor_to(start_x + 1, y - 1)
        self.write('┌' + '─' * max_w + '┐')
        for line in lines:
            self.cursor_to(start_x + 1, y)
            self.write('│' + line + '│')
            y += 1
        self.cursor_to(start_x + 1, y)
        self.write('└' + '─' * max_w + '┘')
        self.reset_style()

    @staticmethod
    def _color_index(color: str) -> int:
        palette = {
            'red': 196, 'green': 46, 'yellow': 226, 'blue': 21,
            'magenta': 201, 'cyan': 51, 'white': 15, 'black': 0,
        }
        return palette.get(color.lower(), 196)