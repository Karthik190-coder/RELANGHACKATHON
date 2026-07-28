# cowsay (Python port)

Configurable talking cow that displays a message. Ported from JavaScript/Node.js to Python 3.

| Field | Value |
|-------|-------|
| **Type** | Easy |
| **Score** | 100 |
| **Language** | Python 3 (stdlib only) |

## Prerequisites

- Python 3.8+

## Run

```bash
python3 cowsay/target/cowsay.py "Hello, world!"
```

## Usage

```
Usage: cowsay.py [-e eye_string] [-f cowfile] [-h] [-l] [-n] [-T tongue_string] [-W column] [-bdgpstwy] text
```

| Flag | Description |
|------|-------------|
| `-e` | Set cow's eyes (default: `oo`) |
| `-T` | Set cow's tongue (default: two spaces) |
| `-W` | Wrap width in columns (default: 40) |
| `-f` | Cowfile name or path (default: `default`) |
| `-n` | Disable word wrapping |
| `-r` | Random cow |
| `-l` | List all available cow names |
| `-h` | Print this help |
| `--think` | Think mode (uses `o` tail instead of `\`) |
| `-b` | Borg mode (eyes: `==`) |
| `-d` | Dead mode (eyes: `xx`, tongue: `U`) |
| `-g` | Greedy mode (eyes: `$$`) |
| `-p` | Paranoia mode (eyes: `@@`) |
| `-s` | Stoned mode (eyes: `**`, tongue: `U`) |
| `-t` | Tired mode (eyes: `--`) |
| `-w` | Wired mode (eyes: `OO`) |
| `-y` | Youthful mode (eyes: `..`) |

## Examples

```bash
# Default cow
python3 cowsay/target/cowsay.py "Hello!"

# Custom eyes and tongue
python3 cowsay/target/cowsay.py -e ^^ -T "U " "Custom face"

# Dead mode
python3 cowsay/target/cowsay.py -d "I'm dead"

# Think mode
python3 cowsay/target/cowsay.py --think "Hmm..."

# Different cow file
python3 cowsay/target/cowsay.py -f fox "What does the fox say?"

# Random cow
python3 cowsay/target/cowsay.py -r "Surprise me!"

# List cows
python3 cowsay/target/cowsay.py -l

# Read from stdin
echo "Hello from stdin" | python3 cowsay/target/cowsay.py
```

## Adding Cow Files

Place `.cow` files in `cowsay/target/cows/`. They will be automatically detected by `-l` and `-f`.

## Submit

```bash
relang "python3 cowsay/target/cowsay.py"
```