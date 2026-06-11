import { getJob, listJobs } from "@/api/client";
import type { Status, Verdict } from "@/api/types";
import { useAsync } from "./useAsync";

// Thin, domain-named wrappers over useAsync. Components call these instead of the
// client directly, so the fetch-key (what triggers a refetch) lives in one place.

/** Job list, refetching whenever a filter changes. */
export function useJobs(filters: { status?: Status; verdict?: Verdict }) {
  return useAsync(() => listJobs(filters), [filters.status, filters.verdict]);
}

/** One job's full detail, refetching when the id changes (e.g. route param). */
export function useJob(id: string) {
  return useAsync(() => getJob(id), [id]);
}
