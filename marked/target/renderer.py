from .defaults import defaults
from .helpers import cleanUrl, escapeHtmlEntities
from .rules import other

class _Renderer:
    def __init__(self, options=None):
        self.options = options or defaults
        self.parser = None  # set by parser

    def space(self, token):
        return ""

    def code(self, token):
        text = token.get("text")
        lang = token.get("lang")
        escaped = token.get("escaped", False)
        
        match = other["notSpaceStart"].exec(lang or "")
        langString = match[0] if match else ""
        
        code_str = (text[:-1] if text.endswith('\n') else text) + '\n' if text else '\n'
        
        if not langString:
            return "<pre><code>" + (code_str if escaped else escapeHtmlEntities(code_str, True)) + "</code></pre>\n"
            
        return ('<pre><code class="language-' 
                + escapeHtmlEntities(langString) 
                + '">' 
                + (code_str if escaped else escapeHtmlEntities(code_str, True)) 
                + "</code></pre>\n")

    def blockquote(self, token):
        body = self.parser.parse(token["tokens"])
        return f"<blockquote>\n{body}</blockquote>\n"

    def html(self, token):
        return token["text"]

    def def_val(self, token):
        return ""


    def heading(self, token):
        depth = token["depth"]
        content = self.parser.parseInline(token["tokens"])
        return f"<h{depth}>{content}</h{depth}>\n"

    def hr(self, token):
        return "<hr>\n"

    def list(self, token):
        ordered = token["ordered"]
        start = token["start"]
        
        body = ""
        for item in token["items"]:
            body += self.listitem(item)
            
        tag_type = "ol" if ordered else "ul"
        startAttr = f' start="{start}"' if (ordered and start != 1) else ''
        return f"<{tag_type}{startAttr}>\n{body}</{tag_type}>\n"

    def listitem(self, item):
        return f"<li>{self.parser.parse(item['tokens'])}</li>\n"

    def checkbox(self, token):
        checked = token["checked"]
        checked_attr = 'checked="" ' if checked else ''
        return f'<input {checked_attr}disabled="" type="checkbox"> '

    def paragraph(self, token):
        return f"<p>{self.parser.parseInline(token['tokens'])}</p>\n"

    def table(self, token):
        header = ""
        cell = ""
        for h_cell in token["header"]:
            cell += self.tablecell(h_cell)
        header += self.tablerow({"text": cell})
        
        body = ""
        for row in token["rows"]:
            cell = ""
            for r_cell in row:
                cell += self.tablecell(r_cell)
            body += self.tablerow({"text": cell})
            
        if body:
            body = f"<tbody>{body}</tbody>"
            
        return f"<table>\n<thead>\n{header}</thead>\n{body}</table>\n"

    def tablerow(self, token):
        return f"<tr>\n{token['text']}</tr>\n"

    def tablecell(self, token):
        content = self.parser.parseInline(token["tokens"])
        cell_type = "th" if token["header"] else "td"
        align = token["align"]
        tag = f'<{cell_type} align="{align}">' if align else f'<{cell_type}>'
        return f"{tag}{content}</{cell_type}>\n"

    def strong(self, token):
        return f"<strong>{self.parser.parseInline(token['tokens'])}</strong>"

    def em(self, token):
        return f"<em>{self.parser.parseInline(token['tokens'])}</em>"

    def codespan(self, token):
        return f"<code>{escapeHtmlEntities(token['text'], True)}</code>"

    def br(self, token):
        return "<br>"

    def del_val(self, token):
        return f"<del>{self.parser.parseInline(token['tokens'])}</del>"

    # del name mapping
    def del_(self, token):
        return self.del_val(token)

    def __getattr__(self, name):
        if name == "del":
            return self.del_val
        raise AttributeError(f"'_Renderer' object has no attribute '{name}'")

    def link(self, token):
        text = self.parser.parseInline(token["tokens"])
        cleanHref = cleanUrl(token["href"])
        if cleanHref is None:
            return text
        href = cleanHref
        out = f'<a href="{href}"'
        if token.get("title"):
            out += f' title="{escapeHtmlEntities(token["title"])}"'
        out += f'>{text}</a>'
        return out

    def image(self, token):
        text = token["text"]
        if token.get("tokens"):
            text = self.parser.parseInline(token["tokens"], self.parser.textRenderer)
        cleanHref = cleanUrl(token["href"])
        if cleanHref is None:
            return escapeHtmlEntities(text)
        href = cleanHref
        out = f'<img src="{href}" alt="{escapeHtmlEntities(text)}"'
        if token.get("title"):
            out += f' title="{escapeHtmlEntities(token["title"])}"'
        out += ">"
        return out

    def text(self, token):
        if "tokens" in token and token["tokens"]:
            return self.parser.parseInline(token["tokens"])
        if token.get("escaped"):
            return token["text"]
        return escapeHtmlEntities(token["text"])
