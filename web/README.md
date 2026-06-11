# Job-Hunt Frontend — Phase C

React + TypeScript single-page app that consumes the Phase B API (`../api`). Living
documentation — **update as the UI changes** (new pages, the TanStack Query swap,
write-back when the DB lands in Phase D).

- **Status:** Phase C — read-only UI over the API. Built 2026-06-11.
- **Stack:** Vite + React 19 + TypeScript · **Tailwind v4** + **shadcn/ui** · React Router · `react-markdown`.
- **Talks to:** the FastAPI server at `VITE_API_BASE` (default `http://127.0.0.1:8000`).

## Run it

The API must be running first (it's the data source):

```powershell
./api/serve.ps1 start          # from repo root — starts FastAPI on :8000
```

Then the frontend (from `web/`):

```powershell
npm install                    # first time only
npm run dev                    # Vite dev server on http://localhost:5173
npm run build                  # tsc typecheck + production build into dist/
```

Open **http://localhost:5173**. The API's CORS is pre-opened for this origin.

## What it does

- **Job list (`/`)** — table of all jobs, **strongest verdict first** (the API sorts;
  the UI doesn't re-sort). Filter by verdict and status via dropdowns; changing a
  filter refetches. Each row links to detail; each has a shortlist toggle.
- **Job detail (`/jobs/:id`)** — full record: title/company/location, verdict +
  status + source badges, links to the job ad / ATS page, and the markdown description
  rendered with Tailwind `prose`.
- **Transient shortlist** — star any job; the header badge counts them live. **Lost on
  refresh by design** — durable shortlists arrive with the DB in Phase D.

## Layout (the why behind the structure)

```
src/
  api/
    types.ts      TS mirror of the Pydantic contract (api/models.py). The frontend
                  half of "API-as-contract" — one place to update on a shape change.
    client.ts     The only module that calls fetch. Base URL + JSON + error mapping
                  centralised; named, typed functions per endpoint.
  hooks/
    useAsync.ts   Generic async state machine (idle/loading/error/data) with a
                  stale-result guard. The teaching core — we hand-roll what TanStack
                  Query would later hide.
    useJobs.ts    Domain wrappers (useJobs/useJob) over useAsync; own the fetch keys.
  shortlist/
    ShortlistContext.tsx  Selection shared across pages via Context (no prop-drilling),
                  intentionally not persisted.
  components/     VerdictBadge, ShortlistButton, Layout (header + <Outlet/>), ui/ (shadcn).
  pages/          JobListPage, JobDetailPage — composition only; logic lives in hooks.
  lib/
    verdict.ts    Verdict → colour/label presentation map (ordering is the API's job).
    utils.ts      shadcn's `cn` class-merge helper.
  App.tsx         Route table.   main.tsx  Provider stack (Router → Shortlist → App).
```

## Config / env

- `.env.development` sets `VITE_API_BASE`. Vite only exposes `VITE_`-prefixed vars to
  the browser. Point it elsewhere to hit a deployed API later.
- Path alias `@/*` → `src/*` (mirrored in `vite.config.ts`, `tsconfig.json`,
  `tsconfig.app.json`). shadcn components import via it.

## Known follow-ups

- [ ] **TanStack Query** — replace `useAsync` once caching/refetch/dedup is wanted (Phase D-ish).
- [ ] **Write-back** — shortlist/status become `POST`s behind the `api/data_source` seam (Phase D).
- [ ] Profiles / dossiers / cover-letter viewers — endpoints exist; no UI yet.
- [ ] Code-split the bundle (single chunk >500 kB warns on build).
