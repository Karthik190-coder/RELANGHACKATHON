def get_defaults():
    return {
        "async": False,
        "breaks": False,
        "extensions": None,
        "gfm": True,
        "hooks": None,
        "pedantic": False,
        "renderer": None,
        "silent": False,
        "tokenizer": None,
        "walkTokens": None,
    }

defaults = get_defaults()

def change_defaults(new_defaults):
    global defaults
    defaults = new_defaults
