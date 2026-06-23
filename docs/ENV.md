# Tooling paths & the stale-PATH gotcha

Why CLAUDE.md insists on verbatim binary paths instead of letting Claude "find" them.

## The gotcha
`python` / `py` / `git` / `gh` / `node` / `npm` / `npx` are **not reliably on the PATH the
Claude tool inherits**. A fresh tool shell can start from a stale session environment, so a
binary that works in your integrated terminal throws "command not found" for Claude. The
failure is intermittent, which makes it a classic rabbit-hole: Claude "fixes" it by probing
with `where` / `Get-Command` / `Test-Path` / Glob, burns turns, and learns nothing reusable.

**Rule: never probe for these binaries. Use the verbatim paths.**

## Python
- Interpreter (3.14.x, deps installed): `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe`
- Prefix `$env:PYTHONUTF8=1` to avoid cp1252 errors on German text.
- Canonical: `$env:PYTHONUTF8=1; & "C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe" <args>`
- Or the thin wrapper from repo root: `./py.ps1 <args>` (same thing).

## git / gh
- They split across shells; PowerShell's git PATH is unreliable.
- **git** → run via the **Bash tool** (git is on its PATH there). Binary: `C:\Program Files\Git\cmd\git.exe`.
- **gh** → full path **from the Bash tool** so it inherits git:
  `"/c/Program Files/GitHub CLI/gh.exe" pr create --base main --head <branch> --title "…" --body "…"`
- Never run bare `gh` in PowerShell → "unable to find git executable".

## node / npm
- `npm.cmd` shells out to `node`, so finding npm isn't enough — node's dir must be on PATH too.
- Node lives at `C:\Program Files\nodejs` (on the integrated-terminal PATH via `.vscode/settings.json`).
- If a fresh shell can't find it, prepend inline:
  `$env:PATH = "C:\Program Files\nodejs;$env:PATH"; & "C:\Program Files\nodejs\npm.cmd" <args>`

## Postgres (Phase D — the durable store)
Local dev Postgres is a **portable EnterpriseDB binary build** — no installer, no Windows
service, no admin/UAC. Chosen over the installer because it's self-contained and trivially
reversible (delete one folder), and over Docker because the reproducibility payoff isn't
here for a solo local DB yet (deferred → backlog G6). SQLAlchemy is connection-string
agnostic, so moving to a service/container later is a `DATABASE_URL` change, not a rewrite.

- **Binaries:** `C:\Users\Chris\pgportable\pgsql\bin` (initdb, pg_ctl, psql). Cluster data:
  `C:\Users\Chris\pgportable\data`. Both live OUTSIDE the repo (nothing to gitignore).
- **Port 5433** (not 5432) so it never clashes with any system Postgres. Superuser `jobhunt`,
  password `jobhunt`, database `jobhunt`.
- **Control script:** `./db/pg.ps1 start | stop | status | psql | restart`.
- **Connection string** (db/engine.py default, override via `$DATABASE_URL`):
  `postgresql+psycopg://jobhunt:jobhunt@localhost:5433/jobhunt`
- **Migrations (Alembic):** `& <python> -m alembic upgrade head` from the repo root (the
  `alembic` console script isn't on PATH; invoke via `python -m alembic`). Config: `alembic.ini`
  + `alembic/env.py` (URL pulled from `$DATABASE_URL`, metadata from `db.models.Base`).
- **Seed from the old JSONL pool:** `./py.ps1 db/seed.py` (idempotent; upsert).

### Rebuilding the dev DB from scratch (if the folder is lost)
```
& <bin>\initdb.exe -D <data> -U jobhunt --pwfile=<file-with-password> -E UTF8 --auth=scram-sha-256
./db/pg.ps1 start
& <bin>\psql.exe -U jobhunt -h localhost -p 5433 -d postgres -c "CREATE DATABASE jobhunt OWNER jobhunt;"
& <python> -m alembic upgrade head
./py.ps1 db/seed.py
```

## Permanent fix in place
`.vscode/settings.json` puts these dirs on the integrated-terminal PATH. The gotcha only
bites fresh/stale tool shells — when it does, fall back to the verbatim paths above.
