from .defaults import defaults
from .renderer import _Renderer
from .text_renderer import _TextRenderer

class _Parser:
    def __init__(self, options=None):
        self.options = options or defaults
        if not self.options.get("renderer"):
            self.options["renderer"] = _Renderer()
        self.renderer = self.options["renderer"]
        self.renderer.options = self.options
        self.renderer.parser = self
        self.textRenderer = _TextRenderer()

    def parse(self, tokens=None):
        if not isinstance(self, _Parser):
            # Called as _Parser.parse(tokens, options)
            tokens_arg = self
            options_arg = tokens
            parser = _Parser(options_arg)
            return parser.parse_val(tokens_arg)
        return self.parse_val(tokens)

    def parseInline(self, tokens, renderer=None):
        if not isinstance(self, _Parser):
            # Called as _Parser.parseInline(tokens, options)
            tokens_arg = self
            options_arg = tokens
            parser = _Parser(options_arg)
            return parser.parseInline_val(tokens_arg)
        return self.parseInline_val(tokens, renderer)

    # Let's map parse method names
    def parse_val(self, tokens):
        self.renderer.parser = self
        out = ""
        for token in tokens:
            t_type = token["type"]
            
            # Extensions renderer checks omitted for standard usage
            
            if t_type == "space":
                out += self.renderer.space(token)
            elif t_type == "hr":
                out += self.renderer.hr(token)
            elif t_type == "heading":
                out += self.renderer.heading(token)
            elif t_type == "code":
                out += self.renderer.code(token)
            elif t_type == "table":
                out += self.renderer.table(token)
            elif t_type == "blockquote":
                out += self.renderer.blockquote(token)
            elif t_type == "list":
                out += self.renderer.list(token)
            elif t_type == "checkbox":
                out += self.renderer.checkbox(token)
            elif t_type == "html":
                out += self.renderer.html(token)
            elif t_type == "def":
                out += self.renderer.def_val(token)
            elif t_type == "paragraph":
                out += self.renderer.paragraph(token)
            elif t_type == "text":
                out += self.renderer.text(token)
            else:
                errMsg = f"Token with \"{t_type}\" type was not found."
                if self.options.get("silent"):
                    import sys
                    sys.stderr.write(errMsg + "\n")
                else:
                    raise RuntimeError(errMsg)
        return out

    def parseInline_val(self, tokens, renderer=None):
        if renderer is None:
            renderer = self.renderer
            
        self.renderer.parser = self
        out = ""
        for token in tokens:
            t_type = token["type"]
            
            if t_type == "escape":
                out += renderer.text(token)
            elif t_type == "html":
                out += renderer.html(token)
            elif t_type == "link":
                out += renderer.link(token)
            elif t_type == "image":
                out += renderer.image(token)
            elif t_type == "checkbox":
                out += renderer.checkbox(token)
            elif t_type == "strong":
                out += renderer.strong(token)
            elif t_type == "em":
                out += renderer.em(token)
            elif t_type == "codespan":
                out += renderer.codespan(token)
            elif t_type == "br":
                out += renderer.br(token)
            elif t_type == "del":
                out += getattr(renderer, "del")(token)
            elif t_type == "text":
                out += renderer.text(token)
            else:
                errMsg = f"Token with \"{t_type}\" type was not found."
                if self.options.get("silent"):
                    import sys
                    sys.stderr.write(errMsg + "\n")
                else:
                    raise RuntimeError(errMsg)
        return out
