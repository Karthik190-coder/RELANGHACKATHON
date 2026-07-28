from .defaults import get_defaults
from .lexer import _Lexer
from .parser import _Parser

class Marked:
    def __init__(self, *args):
        self.defaults = get_defaults()

    def setOptions(self, opt):
        self.defaults.update(opt)
        return self

    def lexer(self, src, options=None):
        return _Lexer.lex(src, options or self.defaults)

    def parser(self, tokens, options=None):
        return _Parser.parse(tokens, options or self.defaults)

    def parse(self, src, opt=None):
        options = {**self.defaults, **(opt or {})}
        
        if src is None:
            raise ValueError("marked(): input parameter is undefined or null")
            
        if not isinstance(src, str):
            raise TypeError(f"marked(): input parameter is of type {type(src)}, string expected")

        tokens = _Lexer.lex(src, options)
        html = _Parser.parse(tokens, options)
        return html

    def parseInline(self, src, opt=None):
        options = {**self.defaults, **(opt or {})}
        
        if src is None:
            raise ValueError("marked(): input parameter is undefined or null")
            
        if not isinstance(src, str):
            raise TypeError(f"marked(): input parameter is of type {type(src)}, string expected")

        tokens = _Lexer.lexInline(src, options)
        html = _Parser.parseInline(tokens, options)
        return html
