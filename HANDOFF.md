# HANDOFF — 2026-06-11 (Phase C React frontend shipped; next = Phase D Postgres)

Transient note for the next session. Full rationale persisted in memory:
`project_state_2026-06-11.md` / `-phase-c.md` (+ `project_app_roadmap.md` for the plan).

## Where we are (good state — nothing broken)
- **Phase B (API) DONE & merged** (PR #5, `24b5001`). Read-only FastAPI in `api/`;
  `api/data_source.py` = THE SEAM (swap to Postgres in D, nothing else changes).
  Run: `./api/serve.ps1 start` → :8000, `/docs` for Swagger. `api/README.md` = living docs.
- **Phase C (React frontend) SHIPPED this session** — `web/`, NOT yet committed/PR'd.
  - **Stack DEVIATION from ROADMAP:** Tailwind v4 + **shadcn/ui**, *not* MUI. Chris's
    call — higher market/CV relevance + teaches CSS composition. Recorded in ROADMAP.
  - Vite + React 19 + **TypeScript**. `npm run dev` → http://localhost:5173 (CORS pre-open).
  - **API-as-contract, frontend half:** `src/api/types.ts` hand-mirrors the Pydantic
    models; `src/api/client.ts` is the only `fetch` caller (typed fns per endpoint).
  - **Data fetching = hand-rolled `useAsync` hook** (`src/hooks/`) on purpose — see the
    loading/error/data state machine + stale-result guard before TanStack Query hides it.
    TanStack Query is the noted Phase-D upgrade.
  - **Transient shortlist** = React Context (`src/shortlist/`), header badge counts live,
    lost on refresh BY DESIGN (persistence = Phase D write-back behind the seam).
  - Pages: list (`/`, verdict/status filters → refetch, strongest-first table, row→detail,
    star toggle) + detail (`/jobs/:id`, full record + markdown desc via react-markdown `prose`).
  - `web/README.md` = run + file-layout living docs. `web/DECISIONS.md` = ADR-style
    rationale for every stack choice (Tailwind/shadcn, TS, useAsync-vs-TanStack, Context,
    routing) with external reference links.
  - **Verified:** `npm run build` clean (tsc+vite); API returns 3 strong/2 fit/5 stretch
    sorted; CORS allows :5173. **NOT visually eyeballed in a browser** — open :5173 to confirm render.
  - Both dev servers were started then **stopped** at end of session (clean state).
- **Pool:** 193 jobs in `data/jobs.jsonl`, triaged. From ~06-10; NOT re-fetched on purpose.

## Run the whole thing
```powershell
./api/serve.ps1 start          # API on :8000 (data source — start first)
cd web; npm install; npm run dev   # frontend on :5173
```

## DO THIS NEXT
1. **Eyeball the app** at http://localhost:5173 — confirm list/detail/filters/shortlist
   render (build passed but no browser screenshot was taken). Fix any runtime issues.
2. **Commit + PR `web/`** (branch off main; `git`→Bash tool, `gh`→full path from Bash).
3. Then **Phase D**: Postgres behind `api/data_source.py`; add write endpoints (shortlist/
   status/notes) → swap the frontend's transient Context for real persistence; consider
   TanStack Query. SQLAlchemy + Alembic + local PG via Docker (see ROADMAP).

## Env / gotchas
- Node 24 / npm 11. Tailwind **v4** = CSS-first (`@import "tailwindcss"` in index.css,
  `@tailwindcss/vite` plugin) — no tailwind.config.js. shadcn init wrote design tokens
  + Geist font into index.css; kept the `@plugin typography` line (markdown `prose`).
- Path alias `@/*`→`src/*` lives in 3 files (vite.config + 2 tsconfigs); NO `baseUrl`
  (deprecated TS7). tsconfig has `erasableSyntaxOnly` → no constructor param-properties.
- shadcn Select (Base UI) `onValueChange` gives `string | null` — handlers must accept null.
- Python: `C:\Users\Chris\AppData\Local\Programs\Python\Python314\python.exe` (full path).
  git → Bash tool. gh → `"/c/Program Files/GitHub CLI/gh.exe"` from Bash tool.
