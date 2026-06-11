# Frontend Decisions — Phase C

Why the React app is built the way it is. Lightweight ADRs: each is a choice, the
reasoning, the tradeoff, and what would make us revisit. Companion to `README.md`
(which covers *how to run it* and the file layout). Dated 2026-06-11.

---

## 1. Tailwind v4 + shadcn/ui — *not* Material UI

- **Decision:** style with [Tailwind CSS v4](https://tailwindcss.com/) utilities and
  build components from [shadcn/ui](https://ui.shadcn.com/) instead of MUI.
- **Why:** higher current market/CV relevance (the combo that shows up in job ads),
  and it teaches CSS composition rather than just a component-library API.
- **Key distinction:** MUI is an installed *component library* you import. shadcn is a
  *CLI that copies component source into `src/components/ui/`* — you own and edit them.
  Built on [Base UI](https://base-ui.com/) (accessibility primitives) + Tailwind.
- **Tradeoff:** more hand-built UI than MUI's batteries-included components; the first
  hour goes to wiring rather than assembling.
- **Deviation:** ROADMAP originally locked MUI. Overridden deliberately; recorded in
  `ROADMAP.md` under "Architecture decisions."
- **Revisit if:** we want a dense data-grid / date-picker fast — MUI X is stronger there.

## 2. TypeScript — the contract's second half

- **Decision:** TypeScript, not plain JS. `src/api/types.ts` hand-mirrors the Phase B
  Pydantic models (`api/models.py`).
- **Why:** Phase B's whole premise is "the API is a typed contract." TS makes that real
  on the client — every fetch result is typed end-to-end; a backend shape change surfaces
  as TS errors at the call sites.
- **Tradeoff:** a bit more ceremony; the mirror is maintained by hand.
- **Revisit if:** the surface grows — generate types from `/openapi.json` with
  [openapi-typescript](https://github.com/openapi-ts/openapi-typescript) instead of mirroring.

## 3. Vite — build tool

- **Decision:** [Vite](https://vite.dev/) (React + TS template).
- **Why:** fast dev server / HMR, first-class Tailwind v4 plugin, and the API's CORS was
  already pre-opened for Vite's `:5173`. The modern default over CRA (deprecated).

## 4. Hand-rolled `useAsync` hook — *not* TanStack Query (yet)

- **Decision:** a small custom hook (`src/hooks/useAsync.ts`) drives every fetch's
  loading/error/data state; `useJobs`/`useJob` wrap it with domain names.
- **Why:** Phase C's goal is to *see* the data-fetching state machine, not hide it. The
  hook also carries a `cancelled` guard so a slow stale response can't overwrite a newer
  one (a real race when filters change quickly) and so unmount doesn't setState.
- **Tradeoff:** no caching, dedup, or background refetch — all of which a library gives free.
- **Revisit if / when:** caching or refetch is wanted — adopt
  [TanStack Query](https://tanstack.com/query/latest) (the natural Phase-D upgrade).

## 5. React Router — client-side routing

- **Decision:** [React Router](https://reactrouter.com/) with a parent `Layout` route
  (header + `<Outlet/>`) and nested `index` (`/`) + `jobs/:id` children.
- **Why:** list→detail with shareable URLs and no full-page reloads; the ROADMAP-locked
  routing choice. `:id` is read via `useParams` in the detail page.

## 6. React Context for the transient shortlist — *not* props, *not* persistence

- **Decision:** selection lives in `src/shortlist/ShortlistContext.tsx`, shared via Context.
- **Why:** the list page, detail page, and header badge all read/write the same set;
  Context avoids prop-drilling through every component between them. Immutable `Set`
  updates (new Set each toggle) so React re-renders.
- **Deliberately transient:** lost on refresh. That's the honest Phase-C boundary —
  durable shortlists (survive restart, write back to the store) arrive with the database
  in Phase D as a POST behind the `api/data_source` seam.
- **Revisit at:** Phase D — swap the Context's in-memory `Set` for server-backed state.

## 7. react-markdown + Tailwind Typography — rendering job descriptions

- **Decision:** render the markdown `description` with
  [react-markdown](https://github.com/remarkjs/react-markdown), styled by the
  [`@tailwindcss/typography`](https://github.com/tailwindlabs/tailwindcss-typography)
  `prose` class.
- **Why:** Tailwind's reset strips default heading/list styling; `prose` restores it for
  rendered content only, scoped to the article.

---

## Toolchain notes (gotchas)

- **Tailwind v4 is CSS-first** — no `tailwind.config.js`. Config is `@import "tailwindcss"`
  in `index.css` + the `@tailwindcss/vite` plugin. shadcn's `init` appended design tokens
  and the Geist font into `index.css`.
- **Path alias `@/* → src/*`** is declared in three places that must agree:
  `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`. No `baseUrl` (deprecated in TS 7;
  TS resolves `paths` relative to the config file).
- **`erasableSyntaxOnly`** (tsconfig) bans constructor parameter-properties — declare class
  fields explicitly (see `ApiError` in `client.ts`).
- **shadcn Select is on Base UI**, so `onValueChange` emits `string | null` (null when
  cleared) — handlers must accept null.
