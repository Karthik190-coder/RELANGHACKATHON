# Python asciiquarium

An original Python/curses terminal aquarium for the reLang hackathon. It uses
only the Python standard library; no third-party packages or the Perl reference
program are used.

## Prerequisites

- Python 3.10 or newer.
- A terminal with curses support. This is built into Python on Linux and macOS.
  On Windows, run it in WSL; standard CPython on Windows does not include curses.

## Run

From the repository root on Linux/macOS/WSL:

\`\`\`bash
python3 asciiquarium/target/asciiquarium.py
\`\`\`

Classic mode limits the fish, sea-monster, and large-fish variants:

\`\`\`bash
python3 asciiquarium/target/asciiquarium.py -c
\`\`\`

Controls: \`q\` quits, \`p\` pauses/resumes, and \`r\` rebuilds the scene. Use a
terminal at least 12 columns by 9 rows. The terminal is restored by
\`curses.wrapper\` on normal exit and Ctrl+C.

Submission command:

\`\`\`bash
relang "python3 asciiquarium/target/asciiquarium.py"
\`\`\`

