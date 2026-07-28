from .defaults import defaults
from .rules import block, inline, other
from .tokenizer import _Tokenizer
from .js_regex import RegExp

class RulesObject(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"No such rule: {name}")
    def __setattr__(self, name, val):
        self[name] = val

class TokensList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.links = {}

class _Lexer:
    def __init__(self, options=None):
        self.tokens = TokensList()
        self.options = options or defaults
        if not self.options.get("tokenizer"):
            self.options["tokenizer"] = _Tokenizer()
        self.tokenizer = self.options["tokenizer"]
        self.tokenizer.options = self.options
        self.tokenizer.lexer = self
        self.inlineQueue = []
        self.state = {
            "inLink": False,
            "inRawBlock": False,
            "top": True,
        }

        rules = RulesObject({
            "other": RulesObject(other),
            "block": RulesObject(block["normal"]),
            "inline": RulesObject(inline["normal"]),
        })

        if self.options.get("pedantic"):
            rules["block"] = RulesObject(block["pedantic"])
            rules["inline"] = RulesObject(inline["pedantic"])
        elif self.options.get("gfm"):
            rules["block"] = RulesObject(block["gfm"])
            if self.options.get("breaks"):
                rules["inline"] = RulesObject(inline["breaks"])
            else:
                rules["inline"] = RulesObject(inline["gfm"])
                
        self.tokenizer.rules = rules

    @staticmethod
    def lex(src, options=None):
        lexer = _Lexer(options)
        return lexer.lex_val(src)

    @staticmethod
    def lexInline(src, options=None):
        lexer = _Lexer(options)
        return lexer.inlineTokens(src)

    # Let's map lex method name
    def lex_val(self, src):
        src = other["carriageReturn"].regex.sub('\n', src)
        self.blockTokens(src, self.tokens)

        for i in range(len(self.inlineQueue)):
            next_item = self.inlineQueue[i]
            self.inlineTokens(next_item["src"], next_item["tokens"])
            
        self.inlineQueue = []
        return self.tokens

    def blockTokens(self, src, tokens=None, lastParagraphClipped=False):
        if tokens is None:
            tokens = []
        self.tokenizer.lexer = self
        
        if self.options.get("pedantic"):
            src = other["tabCharGlobal"].regex.sub('    ', src)
            src = other["spaceLine"].regex.sub('', src)

        srcLength = float('inf')
        while src:
            if len(src) < srcLength:
                srcLength = len(src)
            else:
                self.infiniteLoopError(ord(src[0]))
                break

            token = None

            # extensions block tokenizer omitted unless needed (we don't have custom extensions in standard marked CLI)

            # newline/space
            token = self.tokenizer.space(src)
            if token:
                src = src[len(token["raw"]):]
                lastToken = tokens[-1] if tokens else None
                if len(token["raw"]) == 1 and lastToken is not None:
                    lastToken["raw"] += '\n'
                else:
                    tokens.append(token)
                continue

            # code
            token = self.tokenizer.code(src)
            if token:
                src = src[len(token["raw"]):]
                lastToken = tokens[-1] if tokens else None
                if lastToken and lastToken["type"] in ("paragraph", "text"):
                    lastToken["raw"] += ('' if lastToken["raw"].endswith('\n') else '\n') + token["raw"]
                    lastToken["text"] += '\n' + token["text"]
                    self.inlineQueue[-1]["src"] = lastToken["text"]
                else:
                    tokens.append(token)
                continue

            # fences
            token = self.tokenizer.fences(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # heading
            token = self.tokenizer.heading(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # hr
            token = self.tokenizer.hr(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # blockquote
            token = self.tokenizer.blockquote(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # list
            token = self.tokenizer.list(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # html
            token = self.tokenizer.html(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # def
            token = self.tokenizer.def_val(src)
            if token:
                src = src[len(token["raw"]):]
                lastToken = tokens[-1] if tokens else None
                if lastToken and lastToken["type"] in ("paragraph", "text"):
                    lastToken["raw"] += ('' if lastToken["raw"].endswith('\n') else '\n') + token["raw"]
                    lastToken["text"] += '\n' + token["raw"]
                    self.inlineQueue[-1]["src"] = lastToken["text"]
                elif token["tag"] not in self.tokens.links:
                    self.tokens.links[token["tag"]] = {
                        "href": token["href"],
                        "title": token["title"],
                    }
                    tokens.append(token)
                continue

            # table
            token = self.tokenizer.table(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # lheading
            token = self.tokenizer.lheading(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # paragraph
            cutSrc = src
            if self.state["top"]:
                token = self.tokenizer.paragraph(cutSrc)
                if token:
                    lastToken = tokens[-1] if tokens else None
                    if lastParagraphClipped and lastToken and lastToken["type"] == "paragraph":
                        lastToken["raw"] += ('' if lastToken["raw"].endswith('\n') else '\n') + token["raw"]
                        lastToken["text"] += '\n' + token["text"]
                        self.inlineQueue.pop()
                        self.inlineQueue[-1]["src"] = lastToken["text"]
                    else:
                        tokens.append(token)
                    lastParagraphClipped = len(cutSrc) != len(src)
                    src = src[len(token["raw"]):]
                    continue

            # text
            token = self.tokenizer.text(src)
            if token:
                src = src[len(token["raw"]):]
                lastToken = tokens[-1] if tokens else None
                if lastToken and lastToken["type"] == "text":
                    lastToken["raw"] += ('' if lastToken["raw"].endswith('\n') else '\n') + token["raw"]
                    lastToken["text"] += '\n' + token["text"]
                    self.inlineQueue.pop()
                    self.inlineQueue[-1]["src"] = lastToken["text"]
                else:
                    tokens.append(token)
                continue

            if src:
                self.infiniteLoopError(ord(src[0]))
                break

        self.state["top"] = True
        return tokens

    def inline(self, src, tokens=None):
        if tokens is None:
            tokens = []
        self.inlineQueue.append({"src": src, "tokens": tokens})
        return tokens

    def inlineTokens(self, src, tokens=None):
        if tokens is None:
            tokens = []
        self.tokenizer.lexer = self
        
        maskedSrc = src
        match = None

        # Mask out reflinks
        if self.tokens.links:
            links = list(self.tokens.links.keys())
            if len(links) > 0:
                self.tokenizer.rules["inline"]["reflinkSearch"].lastIndex = 0
                while True:
                    match = self.tokenizer.rules["inline"]["reflinkSearch"].exec(maskedSrc)
                    if match is None:
                        break
                    last_bracket_idx = match[0].rfind('[')
                    reflink_key = match[0][last_bracket_idx + 1:-1]
                    if reflink_key.lower() in self.tokens.links:
                        maskedSrc = maskedSrc[:match.index] + '[' + 'a' * (len(match[0]) - 2) + ']' + maskedSrc[self.tokenizer.rules["inline"]["reflinkSearch"].lastIndex:]

        # Mask out escaped characters
        self.tokenizer.rules["inline"]["anyPunctuation"].lastIndex = 0
        while True:
            match = self.tokenizer.rules["inline"]["anyPunctuation"].exec(maskedSrc)
            if match is None:
                break
            maskedSrc = maskedSrc[:match.index] + '++' + maskedSrc[self.tokenizer.rules["inline"]["anyPunctuation"].lastIndex:]

        # Mask out other blocks
        self.tokenizer.rules["inline"]["blockSkip"].lastIndex = 0
        while True:
            match = self.tokenizer.rules["inline"]["blockSkip"].exec(maskedSrc)
            if match is None:
                break
            offset = len(match[2]) if match[2] else 0
            maskedSrc = maskedSrc[:match.index + offset] + '[' + 'a' * (len(match[0]) - offset - 2) + ']' + maskedSrc[self.tokenizer.rules["inline"]["blockSkip"].lastIndex:]

        keepPrevChar = False
        prevChar = ""
        srcLength = float('inf')

        while src:
            if len(src) < srcLength:
                srcLength = len(src)
            else:
                self.infiniteLoopError(ord(src[0]))
                break

            if not keepPrevChar:
                prevChar = ""
            keepPrevChar = False

            token = None

            # escape
            token = self.tokenizer.escape(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # tag
            token = self.tokenizer.tag(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # link
            token = self.tokenizer.link(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # reflink, nolink
            token = self.tokenizer.reflink(src, self.tokens.links)
            if token:
                src = src[len(token["raw"]):]
                lastToken = tokens[-1] if tokens else None
                if token["type"] == "text" and lastToken and lastToken["type"] == "text":
                    lastToken["raw"] += token["raw"]
                    lastToken["text"] += token["text"]
                else:
                    tokens.append(token)
                continue

            # emStrong
            token = self.tokenizer.emStrong(src, maskedSrc, prevChar)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # codespan
            token = self.tokenizer.codespan(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # br
            token = self.tokenizer.br(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # del
            token = self.tokenizer.del_val(src, maskedSrc, prevChar)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # autolink
            token = self.tokenizer.autolink(src)
            if token:
                src = src[len(token["raw"]):]
                tokens.append(token)
                continue

            # url
            if not self.state["inLink"]:
                token = self.tokenizer.url(src)
                if token:
                    src = src[len(token["raw"]):]
                    tokens.append(token)
                    continue

            # text
            token = self.tokenizer.inlineText(src)
            if token:
                src = src[len(token["raw"]):]
                if token["raw"][-1] != '_':
                    prevChar = token["raw"][-1]
                keepPrevChar = True
                lastToken = tokens[-1] if tokens else None
                if lastToken and lastToken["type"] == "text":
                    lastToken["raw"] += token["raw"]
                    lastToken["text"] += token["text"]
                else:
                    tokens.append(token)
                continue

            if src:
                self.infiniteLoopError(ord(src[0]))
                break

        return tokens

    def infiniteLoopError(self, byte):
        errMsg = f"Infinite loop on byte: {byte}"
        if self.options.get("silent"):
            import sys
            sys.stderr.write(errMsg + "\n")
        else:
            raise RuntimeError(errMsg)
