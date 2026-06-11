// The single place the frontend talks to the Phase B API. One `request` helper
// centralises the base URL, JSON parsing, and error-to-Error mapping; the named
// functions below are the typed surface the rest of the app calls. Mirrors the
// route list in api/main.py one-to-one.

import type { JobDetail, JobSummary, MarkdownDoc, Status, Verdict } from "./types";

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

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`);
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

// --- Markdown docs -----------------------------------------------------------

export const listProfiles = () => request<string[]>("/profile");
export const getProfile = (name: string) => request<MarkdownDoc>(`/profile/${encodeURIComponent(name)}`);
export const listDossiers = () => request<string[]>("/dossiers");
export const getDossier = (slug: string) => request<MarkdownDoc>(`/dossiers/${encodeURIComponent(slug)}`);
