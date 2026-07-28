try:
    import regex as re
except ImportError:
    import re

class JSMatch:
    def __init__(self, match_obj, string):
        self._match = match_obj
        self.input = string
        self.index = match_obj.start() if match_obj else 0
        self._groups = []
        if match_obj:
            self._groups.append(match_obj.group(0))
            num_groups = match_obj.re.groups if hasattr(match_obj.re, 'groups') else len(match_obj.groups())
            for i in range(1, 1 + num_groups):
                try:
                    self._groups.append(match_obj.group(i))
                except IndexError:
                    self._groups.append(None)
        else:
            self._groups.append("")

    def __getitem__(self, idx):
        if idx < len(self._groups):
            val = self._groups[idx]
            return val if val is not None else ""
        return ""

    def __setitem__(self, idx, val):
        while len(self._groups) <= idx:
            self._groups.append("")
        self._groups[idx] = val

    def __len__(self):
        return len(self._groups)

    def __repr__(self):
        return repr(self._groups)

class RegExp:
    def __init__(self, pattern, flags_str=""):
        if isinstance(pattern, RegExp):
            self.pattern_str = pattern.pattern_str
            self.flags_str = pattern.flags_str or flags_str
            self.regex = pattern.regex
            self.global_flag = pattern.global_flag
            self.sticky_flag = pattern.sticky_flag
        else:
            self.pattern_str = pattern
            self.flags_str = flags_str
            
            flags = 0
            if 'i' in flags_str:
                flags |= re.IGNORECASE
            if 'm' in flags_str:
                flags |= re.MULTILINE
                
            self.regex = re.compile(pattern, flags)
            self.global_flag = 'g' in flags_str
            self.sticky_flag = 'y' in flags_str
            
        self.lastIndex = 0

    @property
    def source(self):
        return self.pattern_str

    def exec(self, s):
        if self.lastIndex > len(s):
            self.lastIndex = 0
            return None
        
        if self.sticky_flag:
            match = self.regex.match(s, self.lastIndex)
        else:
            match = self.regex.search(s, self.lastIndex)
            
        if match:
            js_match = JSMatch(match, s)
            if self.global_flag or self.sticky_flag:
                self.lastIndex = match.end()
            return js_match
        else:
            if self.global_flag or self.sticky_flag:
                self.lastIndex = 0
            return None

    def test(self, s):
        return self.exec(s) is not None

def js_replace(s, pattern, replacement):
    if isinstance(pattern, RegExp):
        count = 0 if pattern.global_flag else 1
        if callable(replacement):
            def repl_wrapper(m):
                js_match = JSMatch(m, s)
                args = [val if val is not None else "" for val in js_match._groups]
                args.append(js_match.index)
                args.append(s)
                res = replacement(*args)
                return str(res) if res is not None else ""
            return pattern.regex.sub(repl_wrapper, s, count=count)
        else:
            repl_str = replacement
            if isinstance(repl_str, str):
                repl_str = repl_str.replace('\\', '\\\\')
                repl_str = re.sub(r'\$(?=[1-9])', r'\\', repl_str)
                repl_str = repl_str.replace('$&', r'\g<0>')
                repl_str = repl_str.replace('$$', '$')
            return pattern.regex.sub(repl_str, s, count=count)
    else:
        pattern_str = str(pattern)
        if callable(replacement):
            idx = s.find(pattern_str)
            if idx != -1:
                res = replacement(pattern_str, idx, s)
                return s[:idx] + str(res) + s[idx + len(pattern_str):]
            return s
        else:
            return s.replace(pattern_str, str(replacement), 1)
