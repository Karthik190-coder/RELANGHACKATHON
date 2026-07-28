import regex as re
from .js_regex import RegExp

class Edit:
    def __init__(self, regex, opt=""):
        if isinstance(regex, RegExp):
            self.source = regex.pattern_str
        elif isinstance(regex, str):
            self.source = regex
        else:
            raise TypeError("Expected string or RegExp")
        self.opt = opt

    def replace(self, name, val):
        val_source = val.pattern_str if isinstance(val, RegExp) else str(val)
        val_source = re.sub(r'(^|[^\[])\^', r'\1', val_source)
        
        name_str = name.pattern_str if isinstance(name, RegExp) else str(name)
        self.source = self.source.replace(name_str, val_source)
        return self

    def get_regex(self):
        return RegExp(self.source, self.opt)

def edit(regex, opt=""):
    return Edit(regex, opt)

def cached_indent_regex(create_regex):
    cache = {}
    def get_regex(indent):
        cache_index = max(0, min(3, indent - 1))
        if cache_index not in cache:
            cache[cache_index] = create_regex(cache_index)
        return cache[cache_index]
    return get_regex

noop_test = RegExp(r"")

# Helpers/Other regexes
other = {
    "codeRemoveIndent": RegExp(r"^(?: {1,4}| {0,3}\t)", "gm"),
    "outputLinkReplace": RegExp(r"\\([\[\]])", "g"),
    "indentCodeCompensation": RegExp(r"^(\s+)(?:```)"),
    "beginningSpace": RegExp(r"^\s+"),
    "endingHash": RegExp(r"#$"),
    "startingSpaceChar": RegExp(r"^ "),
    "endingSpaceChar": RegExp(r" $"),
    "nonSpaceChar": RegExp(r"[^ ]"),
    "newLineCharGlobal": RegExp(r"\n", "g"),
    "tabCharGlobal": RegExp(r"\t", "g"),
    "multipleSpaceGlobal": RegExp(r"\s+", "g"),
    "blankLine": RegExp(r"^[ \t]*$"),
    "doubleBlankLine": RegExp(r"\n[ \t]*\n[ \t]*$"),
    "blockquoteStart": RegExp(r"^ {0,3}>"),
    "blockquoteSetextReplace": RegExp(r"\n {0,3}((?:=+|-+) *)(?=\n|$)", "g"),
    "blockquoteSetextReplace2": RegExp(r"^ {0,3}>[ \t]?", "gm"),
    "listReplaceNesting": RegExp(r"^ {1,4}(?=( {4})*[^ ])", "g"),
    "listIsTask": RegExp(r"^\[[ xX]\] +\S"),
    "listReplaceTask": RegExp(r"^\[[ xX]\] +"),
    "listTaskCheckbox": RegExp(r"\[[ xX]\]"),
    "anyLine": RegExp(r"\n.*\n"),
    "hrefBrackets": RegExp(r"^<(.*)>$"),
    "tableDelimiter": RegExp(r"[:|]"),
    "tableAlignChars": RegExp(r"^\||\| *$", "g"),
    "tableRowBlankLine": RegExp(r"\n[ \t]*$"),
    "tableAlignRight": RegExp(r"^ *-+: *$"),
    "tableAlignCenter": RegExp(r"^ *:-+: *$"),
    "tableAlignLeft": RegExp(r"^ *:-+ *$"),
    "startATag": RegExp(r"^<a ", "i"),
    "endATag": RegExp(r"^<\/a>", "i"),
    "startPreScriptTag": RegExp(r"^<(pre|code|kbd|script)(\s|>)", "i"),
    "endPreScriptTag": RegExp(r"^<\/(pre|code|kbd|script)(\s|>)", "i"),
    "startAngleBracket": RegExp(r"^<"),
    "endAngleBracket": RegExp(r">$"),
    "pedanticHrefTitle": RegExp(r'''^([^'"]*[^\s])\s+(['"])(.*)\2'''),
    "unicodeAlphaNumeric": RegExp(r"[\p{L}\p{N}]", "u"),
    "escapeTest": RegExp(r'''[&<>"']'''),
    "escapeReplace": RegExp(r'''[&<>"']''', "g"),
    "escapeTestNoEncode": RegExp(r'''[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)'''),
    "escapeReplaceNoEncode": RegExp(r'''[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)''', "g"),
    "caret": RegExp(r"(^|[^\[])\^", "g"),
    "percentDecode": RegExp(r"%25", "g"),
    "findPipe": RegExp(r"\|", "g"),
    "splitPipe": RegExp(r" \|"),
    "slashPipe": RegExp(r"\\\|", "g"),
    "carriageReturn": RegExp(r"\r\n|\r", "g"),
    "spaceLine": RegExp(r"^ +$", "gm"),
    "notSpaceStart": RegExp(r"^\S*"),
    "endingNewline": RegExp(r"\n$"),
    
    "listItemRegex": lambda bull: RegExp(r"^( {0,3}" + bull + r")((?:[\t ][^\n]*)?(?:\n|$))"),
    "nextBulletRegex": cached_indent_regex(lambda indent: RegExp(r"^ {0," + str(indent) + r"}(?:[*+-]|\d{1,9}[.)])((?:[ \t][^\n]*)?(?:\n|$))")),
    "hrRegex": cached_indent_regex(lambda indent: RegExp(r"^ {0," + str(indent) + r"}((?:- *){3,}|(?:_ *){3,}|(?:\* *){3,})(?:\n+|$)")),
    "fencesBeginRegex": cached_indent_regex(lambda indent: RegExp(r"^ {0," + str(indent) + r"}(?:\`\`\`|~~~)")),
    "headingBeginRegex": cached_indent_regex(lambda indent: RegExp(r"^ {0," + str(indent) + r"}#")),
    "htmlBeginRegex": cached_indent_regex(lambda indent: RegExp(r"^ {0," + str(indent) + r"}<(?:[a-z].*>|!--)", "i")),
    "blockquoteBeginRegex": cached_indent_regex(lambda indent: RegExp(r"^ {0," + str(indent) + r"}>")),
}

# Block Grammar
newline = RegExp(r"^(?:[ \t]*(?:\n|$))+")
blockCode = RegExp(r"^((?: {4}| {0,3}\t)[^\n]+(?:\n(?:[ \t]*(?:\n|$))*)?)+")
fences = RegExp(r"^ {0,3}(`{3,}(?=[^`\n]*(?:\n|$))|~{3,})([^\n]*)(?:\n|$)(?:|([\s\S]*?)(?:\n|$))(?: {0,3}\1[~`]* *(?=\n|$)|$)")
hr = RegExp(r"^ {0,3}((?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)")
heading = RegExp(r"^ {0,3}(#{1,6})(?=\s|$)(.*)(?:\n+|$)")
bullet = r" {0,3}(?:[*+-]|\d{1,9}[.)])"
lheadingCore = r"^(?!bull |blockCode|fences|blockquote|heading|html|table)((?:.|\n(?!\s*?\n|bull |blockCode|fences|blockquote|heading|html|table))+?)\n {0,3}(=+|-+) *(?:\n+|$)"

lheading = edit(lheadingCore)\
    .replace("bull", bullet)\
    .replace("blockCode", r"(?: {4}| {0,3}\t)")\
    .replace("fences", r" {0,3}(?:`{3,}|~{3,})")\
    .replace("blockquote", r" {0,3}>")\
    .replace("heading", r" {0,3}#{1,6}")\
    .replace("html", r" {0,3}<[^\n>]+>\n")\
    .replace("|table", "")\
    .get_regex()

lheadingGfm = edit(lheadingCore)\
    .replace("bull", bullet)\
    .replace("blockCode", r"(?: {4}| {0,3}\t)")\
    .replace("fences", r" {0,3}(?:`{3,}|~{3,})")\
    .replace("blockquote", r" {0,3}>")\
    .replace("heading", r" {0,3}#{1,6}")\
    .replace("html", r" {0,3}<[^\n>]+>\n")\
    .replace("table", r" {0,3}\|?(?:[:\- ]*\|)+[\:\- ]*\n")\
    .get_regex()

_paragraph = r"^([^\n]+(?:\n(?!hr|heading|lheading|blockquote|fences|list|html|table| +\n)[^\n]+)*)"
blockText = RegExp(r"^[^\n]+")
_blockLabel = r"(?!\s*\])(?:\\[\s\S]|[^\[\]\\])+"

def_rule = edit(r"^ {0,3}\[(label)\]: *(?:\n[ \t]*)?([^<\s][^\s]*|<.*?>)(?:(?: +(?:\n[ \t]*)?| *\n[ \t]*)(title))? *(?:\n+|$)")\
    .replace("label", _blockLabel)\
    .replace("title", r'(?:"(?:\\"?|[^"\\])*"|\'[^\'\n]*(?:\n[^\'\n]+)*\n?\'|\([^()]*\))')\
    .get_regex()

list_rule = edit(r"^(bull)([ \t][^\n]*?)?(?:\n|$)")\
    .replace("bull", bullet)\
    .get_regex()

_tag = (r"address|article|aside|base|basefont|blockquote|body|caption"
        r"|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption"
        r"|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe"
        r"|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option"
        r"|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title"
        r"|tr|track|ul")

_comment = r"<!--(?:-?>|[\s\S]*?(?:-->|$))"

html_rule = edit(
    r"^ {0,3}(?:"
    r"<(script|pre|style|textarea)[\s>][\s\S]*?(?:</\1>[^\n]*\n+|$)"
    r"|comment[^\n]*(\n+|$)"
    r"|<\?[\s\S]*?(?:\?>[^\n]*\n+|$)"
    r"|<![A-Z][\s\S]*?(?:>[^\n]*\n+|$)"
    r"|<!\[CDATA\[[\s\S]*?(?:\]\]>[^\n]*\n+|$)"
    r"|</?(tag)(?: +|\n|/?>)[\s\S]*?(?:(?:\n[ \t]*)+\n|$)"
    r"|<(?!script|pre|style|textarea)([a-z][\w-]*)(?:attribute)*? */?>(?=[ \t]*(?:\n|$))[\s\S]*?(?:(?:\n[ \t]*)+\n|$)"
    r"|</(?!script|pre|style|textarea)[a-z][\w-]*\s*>(?=[ \t]*(?:\n|$))[\s\S]*?(?:(?:\n[ \t]*)+\n|$)"
    r")", "i")\
    .replace("comment", _comment)\
    .replace("tag", _tag)\
    .replace("attribute", r" +[a-zA-Z:_][\w.:-]*(?: *= *\"[^\"]*\"| *= *'[^'\n]*'| *= *[^\s\"'=<>`]+)?")\
    .get_regex()

def create_paragraph_rule(list_interrupt):
    return edit(_paragraph)\
        .replace("hr", hr)\
        .replace("heading", r" {0,3}#{1,6}(?:\s|$)")\
        .replace("|lheading", "")\
        .replace("|table", "")\
        .replace("blockquote", r" {0,3}>")\
        .replace("fences", r" {0,3}(?:`{3,}(?=[^`\n]*\n)|~{3,})[^\n]*\n")\
        .replace("list", list_interrupt)\
        .replace("html", r"</?(?:tag)(?: +|\n|/?>)|<(?:script|pre|style|textarea|!--)")\
        .replace("tag", _tag)\
        .get_regex()

paragraph = create_paragraph_rule(r" {0,3}(?:[*+-]|1[.)])[ \t]+[^ \t\n]")
blockquoteParagraph = create_paragraph_rule(r" {0,3}(?:[*+-]|\d{1,9}[.)])[ \t]+[^ \t\n]")

blockquote = edit(r"^( {0,3}> ?(paragraph|[^\n]*)(?:\n|$))+")\
    .replace("paragraph", blockquoteParagraph)\
    .get_regex()

blockNormal = {
    "blockquote": blockquote,
    "code": blockCode,
    "def": def_rule,
    "fences": fences,
    "heading": heading,
    "hr": hr,
    "html": html_rule,
    "lheading": lheading,
    "list": list_rule,
    "newline": newline,
    "paragraph": paragraph,
    "table": noop_test,
    "text": blockText,
}

gfmTable = edit(
    r"^ *([^\n ].*)\n"
    r" {0,3}((?:\| *)?:?-+:? *(?:\| *:?-+:? *)*(?:\| *)?)"
    r"(?:\n((?:(?! *\n|hr|heading|blockquote|code|fences|list|html).*(?:\n|$))*)\n*|$)")\
    .replace("hr", hr)\
    .replace("heading", r" {0,3}#{1,6}(?:\s|$)")\
    .replace("blockquote", r" {0,3}>")\
    .replace("code", r"(?: {4}| {0,3}\t)[^\n]")\
    .replace("fences", r" {0,3}(?:`{3,}(?=[^`\n]*\n)|~{3,})[^\n]*\n")\
    .replace("list", r" {0,3}(?:[*+-]|1[.)])[ \t]")\
    .replace("html", r"</?(?:tag)(?: +|\n|/?>)|<(?:script|pre|style|textarea|!--)")\
    .replace("tag", _tag)\
    .get_regex()

blockGfm = {**blockNormal}
blockGfm["lheading"] = lheadingGfm
blockGfm["table"] = gfmTable
blockGfm["paragraph"] = edit(_paragraph)\
    .replace("hr", hr)\
    .replace("heading", r" {0,3}#{1,6}(?:\s|$)")\
    .replace("|lheading", "")\
    .replace("table", gfmTable)\
    .replace("blockquote", r" {0,3}>")\
    .replace("fences", r" {0,3}(?:`{3,}(?=[^`\n]*\n)|~{3,})[^\n]*\n")\
    .replace("list", r" {0,3}(?:[*+-]|1[.)])[ \t]+[^ \t\n]")\
    .replace("html", r"</?(?:tag)(?: +|\n|/?>)|<(?:script|pre|style|textarea|!--)")\
    .replace("tag", _tag)\
    .get_regex()

blockPedantic = {**blockNormal}
blockPedantic["html"] = edit(
    r"^ *(?:comment *(?:\n|\s*$)"
    r"|<(tag)[\s\S]+?</\1> *(?:\n{2,}|\s*$)"
    r"|<tag(?:\"[^\"]*\"|'[^']*'|\s[^'\n\"/>\s]*)*?/?> *(?:\n{2,}|\s*$))")\
    .replace("comment", _comment)\
    .replace("tag", r"(?!(?:"
                    r"a|em|strong|small|s|cite|q|dfn|abbr|data|time|code|var|samp|kbd|sub"
                    r"|sup|i|b|u|mark|ruby|rt|rp|bdi|bdo|span|br|wbr|ins|del|img)"
                    r"\b)\w+(?!:|[^\w\s@]*@)\b")\
    .get_regex()
blockPedantic["def"] = RegExp(r"^ *\[([^\]]+)\]: *<?([^\s>]+)>?(?: +([\"(][^\n]+[\")]))? *(?:\n+|$)")
blockPedantic["heading"] = RegExp(r"^(#{1,6})(.*)(?:\n+|$)")
blockPedantic["fences"] = noop_test
blockPedantic["lheading"] = RegExp(r"^(.+?)\n {0,3}(=+|-+) *(?:\n+|$)")
blockPedantic["paragraph"] = edit(_paragraph)\
    .replace("hr", hr)\
    .replace("heading", r" *#{1,6} *[^\n]")\
    .replace("lheading", lheading)\
    .replace("|table", "")\
    .replace("blockquote", r" {0,3}>")\
    .replace("|fences", "")\
    .replace("|list", "")\
    .replace("|html", "")\
    .replace("|tag", "")\
    .get_regex()

# Inline Grammar
escape = RegExp(r"^\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])")
inlineCode = RegExp(r"^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)")
br = RegExp(r"^( {2,}|\\)\n(?!\s*$)")
inlineText = RegExp(r"^(`+|[^`])(?:(?= {2,}\n)|[\s\S]*?(?:(?=[\\<!\[`*_]|\b_|$)|[^ ](?= {2,}\n)))")

_punctuation = r"[\p{P}\p{S}]"
_punctuationOrSpace = r"[\s\p{P}\p{S}]"
_notPunctuationOrSpace = r"[^\s\p{P}\p{S}]"

punctuation = edit(r"^((?![*_])punctSpace)", "u")\
    .replace("punctSpace", _punctuationOrSpace)\
    .get_regex()

_punctuationGfmStrongEm = r"(?!~)[\p{P}\p{S}]"
_punctuationOrSpaceGfmStrongEm = r"(?!~)[\s\p{P}\p{S}]"
_notPunctuationOrSpaceGfmStrongEm = r"(?:[^\s\p{P}\p{S}]|~)"

supports_lookbehind = True

blockSkip = edit(r"link|precode-code|html", "g")\
    .replace("link", r"\[(?:[^\[\]`]|(?P<a>`+)[^`]+(?P=a)(?!`))*?\]\((?:\\[\s\S]|[^\\\(\)]|\((?:\\[\s\S]|[^\\\(\)])*\))*\)")\
    .replace("precode-", r"(?<!`)()" if supports_lookbehind else r"(^^|[^`])")\
    .replace("code", r"(?P<b>`+)[^`]+(?P=b)(?!`)")\
    .replace("html", r"<(?! )[^<>]*?>")\
    .get_regex()

emStrongLDelimCore = r"^(?:\*+(?:((?!\*)punct)|([^\s*]))?)|^_+(?:((?!_)punct)|([^\s_]))?"

emStrongLDelim = edit(emStrongLDelimCore, "u")\
    .replace("punct", _punctuation)\
    .get_regex()

emStrongLDelimGfm = edit(emStrongLDelimCore, "u")\
    .replace("punct", _punctuationGfmStrongEm)\
    .get_regex()

emStrongRDelimAstCore = (
    r"^[^_*]*?__[^_*]*?\*[^_*]*?(?=__)"
    r"|[^*]+(?=[^*])"
    r"|(?!\*)\p{Punctuation}(\*+)(?=[\s]|$)" # Note: we use \p{Punctuation} for punct here or replace
    r"|notPunctSpace(\*+)(?!\*)(?=punctSpace|$)"
    r"|(?!\*)punctSpace(\*+)(?=notPunctSpace)"
    r"|[\s](\*+)(?!\*)(?=punct)"
    r"|(?!\*)punct(\*+)(?!\*)(?=punct)"
    r"|notPunctSpace(\*+)(?=notPunctSpace)"
)

emStrongRDelimAst = edit(emStrongRDelimAstCore, "gu")\
    .replace("notPunctSpace", _notPunctuationOrSpace)\
    .replace("punctSpace", _punctuationOrSpace)\
    .replace("punct", _punctuation)\
    .get_regex()

emStrongRDelimAstGfm = edit(emStrongRDelimAstCore, "gu")\
    .replace("notPunctSpace", _notPunctuationOrSpaceGfmStrongEm)\
    .replace("punctSpace", _punctuationOrSpaceGfmStrongEm)\
    .replace("punct", _punctuationGfmStrongEm)\
    .get_regex()

emStrongRDelimUnd = edit(
    r"^[^_*]*?\*\*[^_*]*?_[^_*]*?(?=\*\*)"
    r"|[^_]+(?=[^_])"
    r"|(?!_)punct(_+)(?=[\s]|$)"
    r"|notPunctSpace(_+)(?!_)(?=punctSpace|$)"
    r"|(?!_)punctSpace(_+)(?=notPunctSpace)"
    r"|[\s](_+)(?!_)(?=punct)"
    r"|(?!_)punct(_+)(?!_)(?=punct)", "gu")\
    .replace("notPunctSpace", _notPunctuationOrSpace)\
    .replace("punctSpace", _punctuationOrSpace)\
    .replace("punct", _punctuation)\
    .get_regex()

delLDelim = edit(r"^~~?(?:((?!~)punct)|[^\s~])", "u")\
    .replace("punct", _punctuation)\
    .get_regex()

delRDelimCore = (
    r"^[^~]+(?=[^~])"
    r"|(?!~)punct(~~?)(?=[\s]|$)"
    r"|notPunctSpace(~~?)(?!~)(?=punctSpace|$)"
    r"|(?!~)punctSpace(~~?)(?=notPunctSpace)"
    r"|[\s](~~?)(?!~)(?=punct)"
    r"|(?!~)punct(~~?)(?!~)(?=punct)"
    r"|notPunctSpace(~~?)(?=notPunctSpace)"
)

delRDelim = edit(delRDelimCore, "gu")\
    .replace("notPunctSpace", _notPunctuationOrSpace)\
    .replace("punctSpace", _punctuationOrSpace)\
    .replace("punct", _punctuation)\
    .get_regex()

anyPunctuation = edit(r"\\(punct)", "gu")\
    .replace("punct", _punctuation)\
    .get_regex()

autolink = edit(r"^<(scheme:[^\s\x00-\x1f<>]*|email)>")\
    .replace("scheme", r"[a-zA-Z][a-zA-Z0-9+.-]{1,31}")\
    .replace("email", r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+(@)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(?![-_])")\
    .get_regex()

_inlineComment = edit(_comment).replace(r"(?:-->|$)", "-->").get_regex()

tag = edit(
    r"^comment"
    r"|^</[a-zA-Z][\w:-]*\s*>"
    r"|^<[a-zA-Z][\w-]*(?:attribute)*?\s*/?>"
    r"|^<\?[\s\S]*?\?>"
    r"|^<![a-zA-Z]+\s[\s\S]*?>"
    r"|^<!\[CDATA\[[\s\S]*?\]\]>")\
    .replace("comment", _inlineComment)\
    .replace("attribute", r"\s+[a-zA-Z:_][\w.:-]*(?:\s*=\s*\"[^\"]*\"|\s*=\s*'[^']*'|\s*=\s*[^\s\"'=<>`]+)?")\
    .get_regex()

_inlineLabel = r"(?:\[(?:\\[\s\S]|[^\[\]\\])*\]|\\[\s\S]|`+(?!`)[^`]*?`+(?!`)|``+(?=\])|[^\[\]\\`])*?"

link = edit(r"^!?\[(label)\]\(\s*(href)(?:(?:[ \t]+(?:\n[ \t]*)?|\n[ \t]*)(title))?\s*\)")\
    .replace("label", _inlineLabel)\
    .replace("href", r"<(?:\\.|[^\n<>\\])+>|[^ \t\n\x00-\x1f]*")\
    .replace("title", r'"(?:\\"?|[^"\\])*"|\'(?:\\\'?|[^\'\\])*\'|\((?:\\\)?|[^)\\])*\)')\
    .get_regex()

reflink = edit(r"^!?\[(label)\]\[(ref)\]")\
    .replace("label", _inlineLabel)\
    .replace("ref", _blockLabel)\
    .get_regex()

nolink = edit(r"^!?\[(ref)\](?:\[\])?")\
    .replace("ref", _blockLabel)\
    .get_regex()

reflinkSearch = edit(r"reflink|nolink(?!\()", "g")\
    .replace("reflink", reflink)\
    .replace("nolink", nolink)\
    .get_regex()

_caseInsensitiveProtocol = r"[hH][tT][tT][pP][sS]?|[fF][tT][pP]"

inlineNormal = {
    "_backpedal": noop_test,
    "anyPunctuation": anyPunctuation,
    "autolink": autolink,
    "blockSkip": blockSkip,
    "br": br,
    "code": inlineCode,
    "del": noop_test,
    "delLDelim": noop_test,
    "delRDelim": noop_test,
    "emStrongLDelim": emStrongLDelim,
    "emStrongRDelimAst": emStrongRDelimAst,
    "emStrongRDelimUnd": emStrongRDelimUnd,
    "escape": escape,
    "link": link,
    "nolink": nolink,
    "punctuation": punctuation,
    "reflink": reflink,
    "reflinkSearch": reflinkSearch,
    "tag": tag,
    "text": inlineText,
    "url": noop_test,
}

inlinePedantic = {**inlineNormal}
inlinePedantic["link"] = edit(r"^!?\[(label)\]\((.*?)\)")\
    .replace("label", _inlineLabel)\
    .get_regex()
inlinePedantic["reflink"] = edit(r"^!?\[(label)\]\s*\[([^\]]*)\]")\
    .replace("label", _inlineLabel)\
    .get_regex()

inlineGfm = {**inlineNormal}
inlineGfm["emStrongRDelimAst"] = emStrongRDelimAstGfm
inlineGfm["emStrongLDelim"] = emStrongLDelimGfm
inlineGfm["delLDelim"] = delLDelim
inlineGfm["delRDelim"] = delRDelim
inlineGfm["url"] = edit(r"^((?:protocol):\/\/|www\.)(?:[a-zA-Z0-9\-]+\.?)+[^\s<]*|^email")\
    .replace("protocol", _caseInsensitiveProtocol)\
    .replace("email", r"[A-Za-z0-9._+-]+(@)[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![-_])")\
    .get_regex()
inlineGfm["_backpedal"] = RegExp(r"(?:[^?!.,:;*_'" + r'"' + r"~()&]+|\([^)]*\)|&(?![a-zA-Z0-9]+;$)|[?!.,:;*_'" + r'"' + r"~)]+(?!$))+")
inlineGfm["del"] = RegExp(r"^(~~?)(?=[^\s~])((?:\\[\s\S]|[^\\])*?(?:\\[\s\S]|[^\s~\\]))\1(?=[^~]|$)")
inlineGfm["text"] = edit(r"^([`~]+|[^`~])(?:(?= {2,}\n)|(?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)|[\s\S]*?(?:(?=[\\<!\[`*~_]|\b_|protocol:\/\/|www\.|$)|[^ ](?= {2,}\n)|[^a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-](?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)))")\
    .replace("protocol", _caseInsensitiveProtocol)\
    .get_regex()

inlineBreaks = {**inlineGfm}
inlineBreaks["br"] = edit(br).replace("{2,}", "*").get_regex()
inlineBreaks["text"] = edit(inlineGfm["text"])\
    .replace(r"\b_", r"\b_| {2,}\n")\
    .replace(r"\{2,\}", "*")\
    .get_regex()

block = {
    "normal": blockNormal,
    "gfm": blockGfm,
    "pedantic": blockPedantic,
}

inline = {
    "normal": inlineNormal,
    "gfm": inlineGfm,
    "breaks": inlineBreaks,
    "pedantic": inlinePedantic,
}
