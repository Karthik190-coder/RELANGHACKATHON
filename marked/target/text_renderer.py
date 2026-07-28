class _TextRenderer:
    def strong(self, token):
        return token["text"]

    def em(self, token):
        return token["text"]

    def codespan(self, token):
        return token["text"]

    def del_val(self, token):
        return token["text"]

    # del name mapping
    def del_(self, token):
        return self.del_val(token)

    def __getattr__(self, name):
        if name == "del":
            return self.del_val
        raise AttributeError(f"'_TextRenderer' object has no attribute '{name}'")

    def html(self, token):
        return token["text"]

    def text(self, token):
        return token["text"]

    def link(self, token):
        return "" + token["text"]

    def image(self, token):
        return "" + token["text"]

    def br(self, token=None):
        return ""

    def checkbox(self, token):
        return token["raw"]
