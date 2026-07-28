from .defaults import defaults
from .helpers import (
    rtrim,
    splitCells,
    findClosingBracket,
    expandTabs,
    trimTrailingBlankLines,
)
from .js_regex import js_replace, JSMatch

def output_link(cap, link, raw, lexer, rules):
    href = link.get("href")
    title = link.get("title") or None
    text = js_replace(cap[1], rules.other["outputLinkReplace"], r"\1")

    lexer.state["inLink"] = True
    token = {
        "type": "image" if cap[0].startswith("!") else "link",
        "raw": raw,
        "href": href,
        "title": title,
        "text": text,
        "tokens": lexer.inlineTokens(text)
    }
    lexer.state["inLink"] = False
    return token

def indentCodeCompensation(raw, text, rules):
    matchIndentToCode = rules.other["indentCodeCompensation"].exec(raw)
    if matchIndentToCode is None:
        return text
    indentToCode = matchIndentToCode[1]
    
    lines = text.split('\n')
    new_lines = []
    for node in lines:
        matchIndentInNode = rules.other["beginningSpace"].exec(node)
        if matchIndentInNode is None:
            new_lines.append(node)
        else:
            indentInNode = matchIndentInNode[0]
            if len(indentInNode) >= len(indentToCode):
                new_lines.append(node[len(indentToCode):])
            else:
                new_lines.append(node)
    return '\n'.join(new_lines)

class _Tokenizer:
    def __init__(self, options=None):
        self.options = options or defaults
        self.rules = None  # set by lexer
        self.lexer = None  # set by lexer

    def space(self, src):
        cap = self.rules.block["newline"].exec(src)
        if cap and len(cap[0]) > 0:
            return {
                "type": "space",
                "raw": cap[0],
            }

    def code(self, src):
        cap = self.rules.block["code"].exec(src)
        if cap:
            raw = cap[0] if self.options.get("pedantic") else trimTrailingBlankLines(cap[0])
            text = js_replace(raw, self.rules.other["codeRemoveIndent"], "")
            return {
                "type": "code",
                "raw": raw,
                "codeBlockStyle": "indented",
                "text": text,
            }

    def fences(self, src):
        cap = self.rules.block["fences"].exec(src)
        if cap:
            raw = cap[0]
            text = indentCodeCompensation(raw, cap[3] or "", self.rules)
            
            lang = None
            if cap[2]:
                lang = js_replace(cap[2].strip(), self.rules.inline["anyPunctuation"], r"\1")
                
            return {
                "type": "code",
                "raw": raw,
                "lang": lang,
                "text": text,
            }

    def heading(self, src):
        cap = self.rules.block["heading"].exec(src)
        if cap:
            text = cap[2].strip()
            if self.rules.other["endingHash"].test(text):
                trimmed = rtrim(text, "#")
                if self.options.get("pedantic"):
                    text = trimmed.strip()
                elif not trimmed or self.rules.other["endingSpaceChar"].test(trimmed):
                    text = trimmed.strip()
            return {
                "type": "heading",
                "raw": rtrim(cap[0], "\n"),
                "depth": len(cap[1]),
                "text": text,
                "tokens": self.lexer.inline(text),
            }

    def hr(self, src):
        cap = self.rules.block["hr"].exec(src)
        if cap:
            return {
                "type": "hr",
                "raw": rtrim(cap[0], "\n"),
            }

    def blockquote(self, src):
        cap = self.rules.block["blockquote"].exec(src)
        if cap:
            lines = rtrim(cap[0], "\n").split('\n')
            raw = ""
            text = ""
            tokens = []
            
            while len(lines) > 0:
                inBlockquote = False
                currentLines = []
                
                i = 0
                while i < len(lines):
                    if self.rules.other["blockquoteStart"].test(lines[i]):
                        currentLines.append(lines[i])
                        inBlockquote = True
                    elif not inBlockquote:
                        currentLines.append(lines[i])
                    else:
                        break
                    i += 1
                lines = lines[i:]
                
                currentRaw = '\n'.join(currentLines)
                currentText = js_replace(currentRaw, self.rules.other["blockquoteSetextReplace"], "\n    \\1")
                currentText = js_replace(currentText, self.rules.other["blockquoteSetextReplace2"], "")
                
                raw = f"{raw}\n{currentRaw}" if raw else currentRaw
                text = f"{text}\n{currentText}" if text else currentText
                
                top = self.lexer.state["top"]
                self.lexer.state["top"] = True
                self.lexer.blockTokens(currentText, tokens, True)
                self.lexer.state["top"] = top
                
                if len(lines) == 0:
                    break
                    
                lastToken = tokens[-1] if tokens else None
                if lastToken and lastToken["type"] == "code":
                    break
                elif lastToken and lastToken["type"] == "blockquote":
                    newText = lastToken["raw"] + "\n" + '\n'.join(lines)
                    newToken = self.blockquote(newText)
                    tokens[-1] = newToken
                    raw = raw[:-len(lastToken["raw"])] + newToken["raw"]
                    text = text[:-len(lastToken["text"])] + newToken["text"]
                    break
                elif lastToken and lastToken["type"] == "list":
                    newText = lastToken["raw"] + "\n" + '\n'.join(lines)
                    newToken = self.list(newText)
                    tokens[-1] = newToken
                    raw = raw[:-len(lastToken["raw"])] + newToken["raw"]
                    text = text[:-len(lastToken["raw"])] + newToken["raw"]
                    lines = newText[len(tokens[-1]["raw"]):].split('\n')
                    continue
                    
            return {
                "type": "blockquote",
                "raw": raw,
                "tokens": tokens,
                "text": text,
            }

    def list(self, src):
        cap = self.rules.block["list"].exec(src)
        if cap:
            bull = cap[1].strip()
            isordered = len(bull) > 1
            
            list_token = {
                "type": "list",
                "raw": "",
                "ordered": isordered,
                "start": int(bull[:-1]) if isordered else "",
                "loose": False,
                "items": [],
            }
            
            bull_esc = f"\\d{{1,9}}\\{bull[-1]}" if isordered else f"\\{bull}"
            if self.options.get("pedantic"):
                bull_esc = bull_esc if isordered else "[*+-]"
                
            itemRegex = self.rules.other["listItemRegex"](bull_esc)
            endsWithBlankLine = False
            
            while src:
                endEarly = False
                raw = ""
                itemContents = ""
                
                cap = itemRegex.exec(src)
                if not cap:
                    break
                    
                if self.rules.block["hr"].test(src):
                    break
                    
                raw = cap[0]
                src = src[len(raw):]
                
                line = expand_tabs_helper = expandTabs(cap[2].split('\n', 1)[0], len(cap[1]))
                nextLine = src.split('\n', 1)[0]
                blankLine = not line.strip()
                
                indent = 0
                if self.options.get("pedantic"):
                    indent = 2
                    itemContents = line.lstrip()
                elif blankLine:
                    indent = len(cap[1]) + 1
                else:
                    # find first non-space char
                    match = self.rules.other["nonSpaceChar"].exec(line)
                    indent = match.index if match else 0
                    indent = 1 if indent > 4 else indent
                    itemContents = line[indent:]
                    indent += len(cap[1])
                    
                if blankLine and self.rules.other["blankLine"].test(nextLine):
                    raw += nextLine + "\n"
                    src = src[len(nextLine) + 1:]
                    endEarly = True
                    
                if not endEarly:
                    nextBulletRegex = self.rules.other["nextBulletRegex"](indent)
                    hrRegex = self.rules.other["hrRegex"](indent)
                    fencesBeginRegex = self.rules.other["fencesBeginRegex"](indent)
                    headingBeginRegex = self.rules.other["headingBeginRegex"](indent)
                    htmlBeginRegex = self.rules.other["htmlBeginRegex"](indent)
                    blockquoteBeginRegex = self.rules.other["blockquoteBeginRegex"](indent)
                    
                    while src:
                        rawLine = src.split('\n', 1)[0]
                        nextLine = rawLine
                        
                        if self.options.get("pedantic"):
                            nextLine = js_replace(nextLine, self.rules.other["listReplaceNesting"], "  ")
                            nextLineWithoutTabs = nextLine
                        else:
                            nextLineWithoutTabs = js_replace(nextLine, self.rules.other["tabCharGlobal"], "    ")
                            
                        if fencesBeginRegex.test(nextLine):
                            break
                        if headingBeginRegex.test(nextLine):
                            break
                        if htmlBeginRegex.test(nextLine):
                            break
                        if blockquoteBeginRegex.test(nextLine):
                            break
                        if nextBulletRegex.test(nextLine):
                            break
                        if hrRegex.test(nextLine):
                            break
                            
                        # find non space index
                        match = self.rules.other["nonSpaceChar"].exec(nextLineWithoutTabs)
                        non_space_idx = match.index if match else 0
                        if non_space_idx >= indent or not nextLine.strip():
                            itemContents += '\n' + nextLineWithoutTabs[indent:]
                        else:
                            if blankLine:
                                break
                            
                            # continuation check
                            line_replaced = js_replace(line, self.rules.other["tabCharGlobal"], "    ")
                            match_line = self.rules.other["nonSpaceChar"].exec(line_replaced)
                            line_non_space_idx = match_line.index if match_line else 0
                            if line_non_space_idx >= 4:
                                break
                            if fencesBeginRegex.test(line):
                                break
                            if headingBeginRegex.test(line):
                                break
                            if hrRegex.test(line):
                                break
                                
                            itemContents += '\n' + nextLine
                            
                        blankLine = not nextLine.strip()
                        raw += rawLine + "\n"
                        src = src[len(rawLine) + 1:]
                        line = nextLineWithoutTabs[indent:]
                        
                if not list_token["loose"]:
                    if endsWithBlankLine:
                        list_token["loose"] = True
                    elif self.rules.other["doubleBlankLine"].test(raw):
                        endsWithBlankLine = True
                        
                list_token["items"].append({
                    "type": "list_item",
                    "raw": raw,
                    "task": bool(self.options.get("gfm")) and self.rules.other["listIsTask"].test(itemContents),
                    "loose": False,
                    "text": itemContents,
                    "tokens": [],
                })
                
                list_token["raw"] += raw
                
            if not list_token["items"]:
                return None
                
            lastItem = list_token["items"][-1]
            lastItem["raw"] = lastItem["raw"].rstrip('\n')
            lastItem["text"] = lastItem["text"].rstrip('\n')
            list_token["raw"] = list_token["raw"].rstrip('\n')
            
            for item in list_token["items"]:
                self.lexer.state["top"] = False
                item["tokens"] = self.lexer.blockTokens(item["text"], [])
                itemToken = item["tokens"][0] if item["tokens"] else None
                
                if item["task"] and itemToken and itemToken["type"] in ("text", "paragraph"):
                    item["text"] = js_replace(item["text"], self.rules.other["listReplaceTask"], "")
                    itemToken["raw"] = js_replace(itemToken["raw"], self.rules.other["listReplaceTask"], "")
                    itemToken["text"] = js_replace(itemToken["text"], self.rules.other["listReplaceTask"], "")
                    
                    for i in range(len(self.lexer.inlineQueue) - 1, -1, -1):
                        if self.rules.other["listIsTask"].test(self.lexer.inlineQueue[i]["src"]):
                            self.lexer.inlineQueue[i]["src"] = js_replace(self.lexer.inlineQueue[i]["src"], self.rules.other["listReplaceTask"], "")
                            break
                            
                    taskRawMatch = self.rules.other["listTaskCheckbox"].exec(item["raw"])
                    if taskRawMatch:
                        checkboxToken = {
                            "type": "checkbox",
                            "raw": taskRawMatch[0] + " ",
                            "checked": taskRawMatch[0] != "[ ]",
                        }
                        item["checked"] = checkboxToken["checked"]
                        if list_token["loose"]:
                            firstTok = item["tokens"][0] if item["tokens"] else None
                            if firstTok and firstTok["type"] in ("paragraph", "text") and "tokens" in firstTok:
                                firstTok["raw"] = checkboxToken["raw"] + firstTok["raw"]
                                firstTok["text"] = checkboxToken["raw"] + firstTok["text"]
                                firstTok["tokens"].insert(0, checkboxToken)
                            else:
                                item["tokens"].insert(0, {
                                    "type": "paragraph",
                                    "raw": checkboxToken["raw"],
                                    "text": checkboxToken["raw"],
                                    "tokens": [checkboxToken],
                                })
                        else:
                            item["tokens"].insert(0, checkboxToken)
                elif item["task"]:
                    item["task"] = False
                    
                if not list_token["loose"]:
                    spacers = [t for t in item["tokens"] if t["type"] == "space"]
                    hasMultipleLineBreaks = len(spacers) > 0 and any(self.rules.other["anyLine"].test(t["raw"]) for t in spacers)
                    list_token["loose"] = hasMultipleLineBreaks
                    
            if list_token["loose"]:
                for item in list_token["items"]:
                    item["loose"] = True
                    for tok in item["tokens"]:
                        if tok["type"] == "text":
                            tok["type"] = "paragraph"
                            
            return list_token

    def html(self, src):
        cap = self.rules.block["html"].exec(src)
        if cap:
            raw = trimTrailingBlankLines(cap[0])
            return {
                "type": "html",
                "block": True,
                "raw": raw,
                "pre": cap[1] in ("pre", "script", "style"),
                "text": raw,
            }

    def def_val(self, src):
        cap = self.rules.block["def"].exec(src)
        if cap:
            tag = js_replace(cap[1].lower(), self.rules.other["multipleSpaceGlobal"], " ")
            
            href = ""
            if cap[2]:
                href = js_replace(cap[2], self.rules.other["hrefBrackets"], r"\1")
                href = js_replace(href, self.rules.inline["anyPunctuation"], r"\1")
                
            title = cap[3]
            if cap[3]:
                title = title[1:-1]
                title = js_replace(title, self.rules.inline["anyPunctuation"], r"\1")
                
            return {
                "type": "def",
                "tag": tag,
                "raw": rtrim(cap[0], "\n"),
                "href": href,
                "title": title,
            }

    def table(self, src):
        cap = self.rules.block["table"].exec(src)
        if not cap:
            return None
            
        if not self.rules.other["tableDelimiter"].test(cap[2]):
            return None
            
        headers = splitCells(cap[1])
        aligns = js_replace(cap[2], self.rules.other["tableAlignChars"], "").split('|')
        
        rows = []
        if cap[3] and cap[3].strip():
            rows = js_replace(cap[3], self.rules.other["tableRowBlankLine"], "").split('\n')
            
        item = {
            "type": "table",
            "raw": rtrim(cap[0], "\n"),
            "header": [],
            "align": [],
            "rows": [],
        }
        
        if len(headers) != len(aligns):
            return None
            
        for align in aligns:
            if self.rules.other["tableAlignRight"].test(align):
                item["align"].append("right")
            elif self.rules.other["tableAlignCenter"].test(align):
                item["align"].append("center")
            elif self.rules.other["tableAlignLeft"].test(align):
                item["align"].append("left")
            else:
                item["align"].append(None)
                
        for i in range(len(headers)):
            item["header"].append({
                "text": headers[i],
                "tokens": self.lexer.inline(headers[i]),
                "header": True,
                "align": item["align"][i],
            })
            
        for row in rows:
            row_cells = splitCells(row, len(item["header"]))
            row_tokens = []
            for i, cell in enumerate(row_cells):
                row_tokens.append({
                    "text": cell,
                    "tokens": self.lexer.inline(cell),
                    "header": False,
                    "align": item["align"][i] if i < len(item["align"]) else None,
                })
            item["rows"].append(row_tokens)
            
        return item

    def lheading(self, src):
        cap = self.rules.block["lheading"].exec(src)
        if cap:
            text = cap[1].strip()
            return {
                "type": "heading",
                "raw": rtrim(cap[0], "\n"),
                "depth": 1 if cap[2][0] == '=' else 2,
                "text": text,
                "tokens": self.lexer.inline(text),
            }

    def paragraph(self, src):
        cap = self.rules.block["paragraph"].exec(src)
        if cap:
            text = cap[1][:-1] if cap[1].endswith('\n') else cap[1]
            return {
                "type": "paragraph",
                "raw": cap[0],
                "text": text,
                "tokens": self.lexer.inline(text),
            }

    def text(self, src):
        cap = self.rules.block["text"].exec(src)
        if cap:
            return {
                "type": "text",
                "raw": cap[0],
                "text": cap[0],
                "tokens": self.lexer.inline(cap[0]),
            }

    def escape(self, src):
        cap = self.rules.inline["escape"].exec(src)
        if cap:
            return {
                "type": "escape",
                "raw": cap[0],
                "text": cap[1],
            }

    def tag(self, src):
        cap = self.rules.inline["tag"].exec(src)
        if cap:
            if not self.lexer.state["inLink"] and self.rules.other["startATag"].test(cap[0]):
                self.lexer.state["inLink"] = True
            elif self.lexer.state["inLink"] and self.rules.other["endATag"].test(cap[0]):
                self.lexer.state["inLink"] = False
                
            if not self.lexer.state["inRawBlock"] and self.rules.other["startPreScriptTag"].test(cap[0]):
                self.lexer.state["inRawBlock"] = True
            elif self.lexer.state["inRawBlock"] and self.rules.other["endPreScriptTag"].test(cap[0]):
                self.lexer.state["inRawBlock"] = False
                
            return {
                "type": "html",
                "raw": cap[0],
                "inLink": self.lexer.state["inLink"],
                "inRawBlock": self.lexer.state["inRawBlock"],
                "block": False,
                "text": cap[0],
            }

    def link(self, src):
        cap = self.rules.inline["link"].exec(src)
        if cap:
            trimmedUrl = cap[2].strip()
            if not self.options.get("pedantic") and self.rules.other["startAngleBracket"].test(trimmedUrl):
                if not self.rules.other["endAngleBracket"].test(trimmedUrl):
                    return None
                    
                rtrimSlash = rtrim(trimmedUrl[:-1], '\\')
                if (len(trimmedUrl) - len(rtrimSlash)) % 2 == 0:
                    return None
            else:
                lastParenIndex = findClosingBracket(cap[2], '()')
                if lastParenIndex == -2:
                    return None
                if lastParenIndex > -1:
                    start = 5 if cap[0].startswith('!') else 4
                    linkLen = start + len(cap[1]) + lastParenIndex
                    cap[2] = cap[2][:lastParenIndex]
                    cap[0] = cap[0][:linkLen].strip()
                    cap[3] = ""
                    
            href = cap[2]
            title = ""
            if self.options.get("pedantic"):
                link_match = self.rules.other["pedanticHrefTitle"].exec(href)
                if link_match:
                    href = link_match[1]
                    title = link_match[3]
            else:
                title = cap[3][1:-1] if cap[3] else ""
                
            href = href.strip()
            if self.rules.other["startAngleBracket"].test(href):
                if self.options.get("pedantic") and not self.rules.other["endAngleBracket"].test(trimmedUrl):
                    href = href[1:]
                else:
                    href = href[1:-1]
                    
            return output_link(cap, {
                "href": js_replace(href, self.rules.inline["anyPunctuation"], r"\1") if href else href,
                "title": js_replace(title, self.rules.inline["anyPunctuation"], r"\1") if title else title,
            }, cap[0], self.lexer, self.rules)

    def reflink(self, src, links):
        cap = self.rules.inline["reflink"].exec(src)
        if not cap:
            cap = self.rules.inline["nolink"].exec(src)
            
        if cap:
            linkString = js_replace(cap[2] or cap[1], self.rules.other["multipleSpaceGlobal"], " ")
            link = links.get(linkString.lower())
            if not link:
                text = cap[0][0]
                return {
                    "type": "text",
                    "raw": text,
                    "text": text,
                }
            return output_link(cap, link, cap[0], self.lexer, self.rules)

    def emStrong(self, src, maskedSrc, prevChar=""):
        match = self.rules.inline["emStrongLDelim"].exec(src)
        if not match:
            return None
        if not match[1] and not match[2] and not match[3] and not match[4]:
            return None
            
        if match[4] and self.rules.other["unicodeAlphaNumeric"].test(prevChar):
            return None
            
        nextChar = match[1] or match[3] or ""
        if not nextChar or not prevChar or self.rules.inline["punctuation"].exec(prevChar):
            lLength = len(match[0]) - 1
            rDelim, rLength = None, 0
            delimTotal = lLength
            midDelimTotal = 0
            
            endReg = self.rules.inline["emStrongRDelimAst"] if match[0][0] == '*' else self.rules.inline["emStrongRDelimUnd"]
            endReg.lastIndex = 0
            
            maskedSrc = maskedSrc[-1 * len(src) + lLength:]
            
            while True:
                m = endReg.exec(maskedSrc)
                if m is None:
                    break
                    
                rDelim = m[1] or m[2] or m[3] or m[4] or m[5] or m[6]
                if not rDelim:
                    continue
                    
                rLength = len(rDelim)
                if m[3] or m[4]:
                    delimTotal += rLength
                    continue
                elif m[5] or m[6]:
                    if (lLength % 3) and not ((lLength + rLength) % 3):
                        midDelimTotal += rLength
                        continue
                        
                delimTotal -= rLength
                if delimTotal > 0:
                    continue
                    
                rLength = min(rLength, rLength + delimTotal + midDelimTotal)
                lastCharLength = len(m[0][0])
                raw = src[:lLength + m.index + lastCharLength + rLength]
                
                if min(lLength, rLength) % 2:
                    text = raw[1:-1]
                    return {
                        "type": "em",
                        "raw": raw,
                        "text": text,
                        "tokens": self.lexer.inlineTokens(text),
                    }
                    
                text = raw[2:-2]
                return {
                    "type": "strong",
                    "raw": raw,
                    "text": text,
                    "tokens": self.lexer.inlineTokens(text),
                }

    def codespan(self, src):
        cap = self.rules.inline["code"].exec(src)
        if cap:
            text = js_replace(cap[2], self.rules.other["newLineCharGlobal"], " ")
            hasNonSpaceChars = self.rules.other["nonSpaceChar"].test(text)
            hasSpaceCharsOnBothEnds = self.rules.other["startingSpaceChar"].test(text) and self.rules.other["endingSpaceChar"].test(text)
            if hasNonSpaceChars and hasSpaceCharsOnBothEnds:
                text = text[1:-1]
            return {
                "type": "codespan",
                "raw": cap[0],
                "text": text,
            }

    def br(self, src):
        cap = self.rules.inline["br"].exec(src)
        if cap:
            return {
                "type": "br",
                "raw": cap[0],
            }

    def del_val(self, src, maskedSrc, prevChar=""):
        match = self.rules.inline["delLDelim"].exec(src)
        if not match:
            return None
            
        nextChar = match[1] or ""
        if not nextChar or not prevChar or self.rules.inline["punctuation"].exec(prevChar):
            lLength = len(match[0]) - 1
            rDelim, rLength = None, 0
            delimTotal = lLength
            
            endReg = self.rules.inline["delRDelim"]
            endReg.lastIndex = 0
            
            maskedSrc = maskedSrc[-1 * len(src) + lLength:]
            
            while True:
                m = endReg.exec(maskedSrc)
                if m is None:
                    break
                    
                rDelim = m[1] or m[2] or m[3] or m[4] or m[5] or m[6]
                if not rDelim:
                    continue
                    
                rLength = len(rDelim)
                if rLength != lLength:
                    continue
                    
                if m[3] or m[4]:
                    delimTotal += rLength
                    continue
                    
                delimTotal -= rLength
                if delimTotal > 0:
                    continue
                    
                rLength = min(rLength, rLength + delimTotal)
                lastCharLength = len(m[0][0])
                raw = src[:lLength + m.index + lastCharLength + rLength]
                text = raw[lLength:-lLength]
                return {
                    "type": "del",
                    "raw": raw,
                    "text": text,
                    "tokens": self.lexer.inlineTokens(text),
                }

    def del_rule(self, src, maskedSrc, prevChar=""):
        return self.del_val(src, maskedSrc, prevChar)

    def del_opt(self, src, maskedSrc, prevChar=""):
        # Emulate JS del
        return self.del_val(src, maskedSrc, prevChar)

    def del_func(self, src, maskedSrc, prevChar=""):
        return self.del_val(src, maskedSrc, prevChar)

    # Let's map both del names
    def del_(self, src, maskedSrc, prevChar=""):
        return self.del_val(src, maskedSrc, prevChar)

    # We must support del method when tokenizer calls .del()
    # In python, del is a keyword, so we must be careful. We can name the method "del_val" and in lexer/elsewhere map "del" to del_val or implement __getattr__ or a map!
    # Let's define:
    def __getattr__(self, name):
        if name == "del":
            return self.del_val
        raise AttributeError(f"'_Tokenizer' object has no attribute '{name}'")

    def autolink(self, src):
        cap = self.rules.inline["autolink"].exec(src)
        if cap:
            if cap[2] == "@":
                text = cap[1]
                href = "mailto:" + text
            else:
                text = cap[1]
                href = text
            return {
                "type": "link",
                "raw": cap[0],
                "text": text,
                "href": href,
                "tokens": [
                    {
                        "type": "text",
                        "raw": text,
                        "text": text,
                    }
                ]
            }

    def url(self, src):
        cap = self.rules.inline["url"].exec(src)
        if cap:
            if cap[2] == "@":
                text = cap[0]
                href = "mailto:" + text
            else:
                prevCapZero = None
                while prevCapZero != cap[0]:
                    prevCapZero = cap[0]
                    backpedal_match = self.rules.inline["_backpedal"].exec(cap[0])
                    cap[0] = backpedal_match[0] if backpedal_match else ""
                text = cap[0]
                if cap[1] == "www.":
                    href = "http://" + cap[0]
                else:
                    href = cap[0]
            return {
                "type": "link",
                "raw": cap[0],
                "text": text,
                "href": href,
                "tokens": [
                    {
                        "type": "text",
                        "raw": text,
                        "text": text,
                    }
                ]
            }

    def inlineText(self, src):
        cap = self.rules.inline["text"].exec(src)
        if cap:
            escaped = self.lexer.state["inRawBlock"]
            return {
                "type": "text",
                "raw": cap[0],
                "text": cap[0],
                "escaped": escaped,
            }
