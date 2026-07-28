# Pure Python sl Target

A pure Python implementation of the `sl` (Steam Locomotive) tool, migrated from the C-extension version.

## Run

Run the target version directly using:

```bash
python3 -c "import sys; sys.path.insert(0, '.'); from slpy.command_line import main; main()"
```

Or pass any option flags:

```bash
python3 -c "import sys; sys.path.insert(0, '.'); from slpy.command_line import main; main()" -F
```

Supported flags:
- `-l`: Add more locomotives (cars)
- `-a`: Add people crying for help (accident)
- `-F`: Fly locomotive up and left
- `-c`: Use C51 instead of D51 locomotive
- `-d`: Add dance people
- `-r`: Randomize the active options
