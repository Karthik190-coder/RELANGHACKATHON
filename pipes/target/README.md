# Pipes — Kotlin Target Implementation

This is the Kotlin port of the `pipes` terminal screensaver screensaver.

## Prerequisites

- JDK 17 or higher (tested with JDK 26)
- Maven 3.6+

## Build

To compile and package the program, run the following command from the `pipes/target` directory:

```bash
# Note: On JDK 26+, you must specify properties override to compile:
mvn clean package "-Djava.version=21" "-Djava.runtime.version=21"
```

This will produce the executable fat JAR: `target/pipes-1.0-SNAPSHOT-jar-with-dependencies.jar`.

## Run

To run the screensaver:

```bash
java -jar target/pipes-1.0-SNAPSHOT-jar-with-dependencies.jar
```

### Options

All CLI arguments from the Python version are supported:

- `-p, --pipes N`         Number of pipes (default: 1)
- `-f, --fps N`           Frames per second, 20-100 (default: 75)
- `-s, --steady N`        Steadiness, 5-15 (default: 13)
- `-r, --limit N`         Character limit before screen reset
- `-R, --random`          Start pipes at random positions
- `-B, --no-bold`         Disable bold characters
- `-C, --no-color`        Disable colors
- `-P N`                  Pipe style 0-9 (default: 0)
- `-K, --keep-style`      Keep pipe style when wrapping around screen
- `-S, --save-config`     Save current settings as default
- `-v, --version`         Show version

### Interactive Keys

While running:
- `O` — Decrease steadiness (more turns)
- `P` — Increase steadiness (fewer turns)
- `D` — Decrease FPS (slower)
- `F` — Increase FPS (faster)
- `B` — Toggle bold
- `C` — Toggle color
- `K` — Toggle keep style on wrap
- `?` or `ESC` — Quit
