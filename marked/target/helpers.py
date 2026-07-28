import urllib.parse
from .rules import other
from .js_regex import js_replace

escapeReplacements = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}

def get_escape_replacement(ch):
    return escapeReplacements.get(ch, ch)

def escapeHtmlEntities(html, encode=False):
    if encode:
        if other["escapeTest"].test(html):
            return js_replace(html, other["escapeReplace"], lambda match, *args: get_escape_replacement(match))
    else:
        if other["escapeTestNoEncode"].test(html):
            return js_replace(html, other["escapeReplaceNoEncode"], lambda match, *args: get_escape_replacement(match))
    return html

def cleanUrl(href):
    try:
        # Emulate JavaScript's encodeURI
        href = urllib.parse.quote(href, safe=";,/?:@&=+$-_.!~*'()#")
        href = js_replace(href, other["percentDecode"], "%")
    except Exception:
        return None
    return href

def splitCells(tableRow, count=None):
    # Ensure every cell-delimiting pipe has a space before it to distinguish it from an escaped pipe
    def replace_pipe(match, offset, string):
        escaped = False
        curr = offset
        while True:
            curr -= 1
            if curr >= 0 and string[curr] == '\\':
                escaped = not escaped
            else:
                break
        if escaped:
            return '|'
        else:
            return ' |'

    row = js_replace(tableRow, other["findPipe"], replace_pipe)
    cells = row.split(' |')
    
    if not cells[0].strip():
        cells.pop(0)
    if len(cells) > 0 and not cells[-1].strip():
        cells.pop()
        
    if count is not None:
        if len(cells) > count:
            cells = cells[:count]
        else:
            while len(cells) < count:
                cells.append("")
                
    for i in range(len(cells)):
        cells[i] = js_replace(cells[i].strip(), other["slashPipe"], '|')
    return cells

def rtrim(string, c, invert=False):
    l = len(string)
    if l == 0:
        return ""
    suffLen = 0
    while suffLen < l:
        currChar = string[l - suffLen - 1]
        if currChar == c and not invert:
            suffLen += 1
        elif currChar != c and invert:
            suffLen += 1
        else:
            break
    return string[:l - suffLen]

def trimTrailingBlankLines(string):
    lines = string.split('\n')
    end = len(lines) - 1
    while end >= 0 and other["blankLine"].test(lines[end]):
        end -= 1
    if len(lines) - end <= 2:
        return string
    return '\n'.join(lines[:end + 1])

def findClosingBracket(string, b):
    if b[1] not in string:
        return -1
    level = 0
    i = 0
    while i < len(string):
        if string[i] == '\\':
            i += 1
        elif string[i] == b[0]:
            level += 1
        elif string[i] == b[1]:
            level -= 1
            if level < 0:
                return i
        i += 1
    if level > 0:
        return -2
    return -1

def expandTabs(line, indent=0):
    col = indent
    expanded = ""
    for char in line:
        if char == '\t':
            added = 4 - (col % 4)
            expanded += ' ' * added
            col += added
        else:
            expanded += char
            col += 1
    return expanded
