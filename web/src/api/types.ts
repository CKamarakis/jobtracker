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
