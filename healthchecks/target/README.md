# healthchecks — TypeScript/Node.js Implementation

A faithful re-implementation of the [Healthchecks](https://github.com/nicowillis/healthchecks) uptime monitoring web server, originally written in Python/Django, ported to **TypeScript (Node.js + Express + SQLite)**.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | TypeScript |
| Runtime | Node.js |
| HTTP Framework | Express |
| Database | SQLite (via `better-sqlite3`) |
| Cron parsing | `cron-parser` |

## Prerequisites

- **Node.js** v18 or later
- **npm**

## Build

```bash
cd target/
npm install
npm run build
```

## Run

```bash
cd target/
PORT=8000 npm run start
```

The server starts on port `8000` by default. Set the `PORT` environment variable to use a different port:

```bash
PORT=8200 npm run start
```

## Validate (local)

With the server running, from the `healthchecks/` directory:

```bash
python3 relang/validate.py http://localhost:8000
```

## Submit

With the server running:

```bash
# Windows (PowerShell)
..\setup.bat
relang http://localhost:8000

# Linux / macOS
source ../setup.sh
relang "http://localhost:8000"
```

## Project Structure

```
target/
├── src/
│   ├── server.ts       # Express app setup, body parsing, reset endpoint
│   ├── api.ts          # REST API routes (/api/v1/...)
│   ├── front.ts        # Web UI routes (login, checks, integrations...)
│   ├── ping.ts         # Ping ingestion routes (/ping/...)
│   ├── auth.ts         # Session auth, CSRF, API key middleware
│   ├── db.ts           # SQLite schema, seeding, reset logic
│   ├── check_model.ts  # Check serialization helpers
│   └── tz.ts           # Timezone validation data
├── dist/               # Compiled JavaScript output
├── package.json
└── tsconfig.json
```

## Notes

- All state is stored in an in-memory SQLite database that is seeded fresh on startup and can be reset via `GET /__test/reset/`.
- The implementation targets API compatibility with the Django reference, including exact error message strings, redirect behaviours, and CSRF handling.
