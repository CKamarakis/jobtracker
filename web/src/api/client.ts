// The single place the frontend talks to the Phase B API. One `request` helper
// centralises the base URL, JSON parsing, and error-to-Error mapping; the named
// functions below are the typed surface the rest of the app calls. Mirrors the
// route list in api/main.py one-to-one.

import type {
  FetchRequest,
  FetchStatus,
  JobActionPatch,
  JobDetail,
  JobSummary,
  MarkdownDoc,
  Status,
  Verdict,
} from "./types";

// Configured per-environment via Vite env (.env.development). Fallback keeps it
// working if the var is missing. import.meta.env is Vite's build-time env object.
const BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

/** Thrown on any non-2xx response, carrying the status so callers can branch (404 vs 500). */
export class ApiError extends Error {
  // Declared explicitly (not as a constructor parameter-property) because the
  // tsconfig sets `erasableSyntaxOnly`, which bans param-properties — they emit
  // runtime code and so aren't purely type syntax.
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    // fetch only rejects on network failure (server down, CORS, DNS) — surface a
    // human message instead of the opaque "Failed to fetch".
    throw new ApiError(0, `Can't reach the API at ${BASE}. Is it running? (./api/serve.ps1 start)`);
  }
  if (!res.ok) {
    // FastAPI puts the reason in { detail }. Best-effort parse; fall back to status text.
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

/** POST JSON and parse the JSON response. Thin wrapper over `request` so the error/network
 * handling stays in one place — the only difference from a GET is method + body + header. */
function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** PATCH JSON (same error/network handling as post). Used for partial job-action updates. */
function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Build a query string from defined params only (skip undefined/null). */
function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v != null && v !== "");
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries as [string, string][]).toString();
}

// --- Jobs --------------------------------------------------------------------

export function listJobs(filters: { status?: Status; verdict?: Verdict } = {}): Promise<JobSummary[]> {
  return request<JobSummary[]>(`/jobs${qs(filters)}`);
}

export function getJob(id: string): Promise<JobDetail> {
  return request<JobDetail>(`/jobs/${encodeURIComponent(id)}`);
}

/** Persist a review action (status / notes / applied-date). Phase D's first WRITE on a job —
 * what makes the review actions survive a refresh. Returns the updated detail record. */
export function patchJob(id: string, body: JobActionPatch): Promise<JobDetail> {
  return patch<JobDetail>(`/jobs/${encodeURIComponent(id)}`, body);
}

// --- Fetch run (WRITE path) --------------------------------------------------

/** Source ids the user can toggle in the Go-fetch dialog (don't hardcode in the UI). */
export const listSources = () => request<string[]>("/sources");

/** Start a fetch (wipe + refill the pool) in the background. Returns the starting snapshot.
 * Throws ApiError(409) if a run is already in flight, ApiError(400) on bad sources/duration. */
export const triggerFetch = (req: FetchRequest) => post<FetchStatus>("/fetch", req);

/** Read the current/last run state (one shot). The dashboard reads this once on load. */
export const getFetchStatus = () => request<FetchStatus>("/fetch/status");

/** Long-poll: resolves when the in-flight run finishes (server holds the request open).
 * Returns immediately if nothing is running. The results view awaits this, then loads. */
export const waitForFetch = () => request<FetchStatus>("/fetch/wait");

// --- Markdown docs -----------------------------------------------------------

export const listProfiles = () => request<string[]>("/profile");
export const getProfile = (name: string) => request<MarkdownDoc>(`/profile/${encodeURIComponent(name)}`);
export const listDossiers = () => request<string[]>("/dossiers");
export const getDossier = (slug: string) => request<MarkdownDoc>(`/dossiers/${encodeURIComponent(slug)}`);
