// TS mirror of the Phase B Pydantic contract (api/models.py). These types are the
// frontend half of the "API-as-contract" pattern: the backend publishes the shape,
// we restate it here so every fetch result is typed end-to-end. If the backend
// shape changes, this file is the one place to update (and TS errors point at the
// fallout). A generator (openapi-typescript) could derive these from /openapi.json
// automatically later — hand-written is fine while the surface is this small.

/** Triage outcome. `null` when a job hasn't been triaged yet. */
export type Verdict = "strong fit" | "fit" | "stretch" | "reject";

/** Workflow status of a job in the pipeline. */
export type Status = "new" | "shortlisted" | "applied" | "skipped";

/** List-view shape — mirrors JobSummary. No `description` (keeps list payloads small). */
export interface JobSummary {
  id: string;
  source: string[];
  company: string;
  title: string;
  location: string | null;
  remote: boolean | null;
  url: string | null;
  ats_url: string | null;
  posted_date: string | null;
  status: Status | null;
  triage_verdict: Verdict | null;
}

/** Detail-view shape — mirrors JobDetail (JobSummary + body & triage trail). */
export interface JobDetail extends JobSummary {
  description: string | null;
  triaged_date: string | null;
  skip_reason: string | null;
  alt_locations: string[] | null;
}

/** A profile / dossier / cover-letter file served as raw markdown — mirrors MarkdownDoc. */
export interface MarkdownDoc {
  slug: string;
  markdown: string;
}

// --- Fetch run (the first WRITE path) ----------------------------------------

/** Lifecycle of a fetch run. Mirrors fetch_runner._state["state"]. */
export type FetchState = "idle" | "running" | "done" | "error";

/**
 * Live status of the current/last fetch run — mirrors fetch_runner.get_status().
 * The same dict is returned by POST /fetch (the starting snapshot) and GET /fetch/status.
 * `counts` is the run summary; its shape varies by phase (ingest counts vs. final
 * summary incl. a nested `triage` block), so it's loosely typed — the UI only surfaces
 * a few known keys and otherwise shows `message`.
 */
export interface FetchStatus {
  state: FetchState;
  phase: string | null;          // starting | fetch | write | triage | done | error
  message: string | null;
  counts: Record<string, unknown> | null;
  sources: string[] | null;
  duration: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

/** Body for POST /fetch — mirrors api.main.FetchRequest. */
export interface FetchRequest {
  sources?: string[] | null;     // null/omitted → all available sources
  duration: string;              // 1d | 3d | 1w
}
