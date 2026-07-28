import sys
import os
import json

# Ensure target can be imported from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from target.instance import Marked
from target.defaults import defaults
from target.lexer import _Lexer

def camelize(text):
    import re
    return re.sub(r'(\w)-(\w)', lambda m: m.group(1) + m.group(2).upper(), text)

def get_stdin():
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()

def main():
    marked_instance = Marked()
    
    argv = sys.argv[1:]
    files = []
    options = {}
    
    output_file = None
    input_file = None
    string_input = None
    tokens_only = False
    noclobber = False
    
    def get_arg():
        arg = argv.pop(0)
        if arg.startswith('--'):
            parts = arg.split('=', 1)
            if len(parts) > 1:
                argv.insert(0, parts[1])
            arg = parts[0]
        elif arg.startswith('-') and len(arg) > 2:
            # e.g. -abc -> -a -b -c
            expanded = []
            for ch in arg[1:]:
                expanded.append('-' + ch)
            for item in reversed(expanded):
                argv.insert(0, item)
            arg = argv.pop(0)
        return arg

    while argv:
        arg = get_arg()
        if arg in ('-o', '--output'):
            output_file = argv.pop(0) if argv else None
        elif arg in ('-i', '--input'):
            input_file = argv.pop(0) if argv else None
        elif arg in ('-s', '--string'):
            string_input = argv.pop(0) if argv else None
        elif arg in ('-t', '--tokens'):
            tokens_only = True
        elif arg in ('-n', '--no-clobber'):
            noclobber = True
        elif arg in ('-h', '--help'):
            print("Marked CLI Parser (Python Port)")
            sys.exit(0)
        elif arg in ('-v', '--version'):
            print("18.0.5")
            sys.exit(0)
        elif arg.startswith('--'):
            opt = camelize(arg.replace('--no-', '').replace('--', ''))
            # Check if this option exists in defaults
            if opt in defaults:
                if arg.startswith('--no-'):
                    options[opt] = False if isinstance(defaults[opt], bool) else None
                else:
                    options[opt] = True if isinstance(defaults[opt], bool) else (argv.pop(0) if argv else None)
            else:
                pass
        else:
            files.append(arg)
            
    # Load data
    if string_input is not None:
        data = string_input
    elif input_file is not None:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = f.read()
    elif len(files) > 0:
        with open(files[-1], 'r', encoding='utf-8') as f:
            data = f.read()
    else:
        data = get_stdin()
        
    marked_instance.setOptions(options)
    
    if tokens_only:
        # Lexer tokens
        tokens = marked_instance.lexer(data)
        # JS format is 2 spaces indent
        html = json.dumps(tokens, indent=2)
    else:
        html = marked_instance.parse(data)
        
    if output_file:
        if noclobber and os.path.exists(output_file):
            sys.stderr.write(f"marked: output file '{output_file}' already exists\n")
            sys.exit(1)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
    else:
        # Match process.stdout.write(html + '\n')
        # Wait, Python print() adds a newline by default, but to be safe we can use sys.stdout.write
        # Note: sys.stdout.write needs encoded bytes or correct encoding
        # Since we run with -X utf8 or PYTHONUTF8=1, writing unicode characters will work perfectly.
        sys.stdout.write(html + '\n')
        sys.stdout.flush()

if __name__ == '__main__':
    main()
