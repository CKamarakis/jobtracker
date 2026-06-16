import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { listJobs } from "@/api/client";
import type { JobSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { JobDetailDialog } from "@/components/JobDetailDialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

// Read-only companion to the post-fetch review queue: the jobs triage scored `reject`,
// here only (the main results page hides them). A curiosity peek — no notes/remove/approve.
// Title-prefiltered jobs are NOT shown; only the LLM's own rejects, with its one-liner.
export function RejectedPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  // Which job's full info is open in the modal (null = closed).
  const [viewId, setViewId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listJobs({ verdict: "reject" })
      .then((data) => !cancelled && setJobs(data))
      .catch((e) => !cancelled && setError(e as Error));
    return () => {
      cancelled = true;
    };
  }, []);

  const loading = jobs === null && !error;

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" className="mb-2 -ml-2" render={<Link to="/results" />}>
          <ArrowLeftIcon />
          Back to results
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">Rejected by triage</h1>
        <p className="text-sm text-muted-foreground">
          {jobs ? `${jobs.length} job${jobs.length === 1 ? "" : "s"}` : " "} triage scored a reject
          this run · read-only
        </p>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {error.message}
        </p>
      )}

      <div className="rounded-lg border">
        {/* Cells wrap (whitespace-normal + align-top) so the table fits the container
            width instead of forcing a horizontal scroll. */}
        <Table className="[&_td]:whitespace-normal [&_td]:align-top">
          <TableHeader>
            <TableRow>
              <TableHead className="w-10 text-right">#</TableHead>
              <TableHead className="w-[22%]">Company</TableHead>
              <TableHead className="w-[34%]">Title</TableHead>
              <TableHead>Why rejected</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading &&
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 4 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!loading && (jobs?.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-12 text-center text-muted-foreground">
                  Nothing was rejected this run.
                </TableCell>
              </TableRow>
            )}

            {!loading &&
              jobs?.map((job, i) => {
                // Strip the leading "reject — " prefix the triage agent prepends, if present.
                const reason = job.triage_reason?.replace(/^reject\s*[—-]\s*/i, "") ?? "—";
                return (
                  <TableRow key={job.id}>
                    <TableCell className="text-right text-muted-foreground tabular-nums">
                      {i + 1}
                    </TableCell>
                    <TableCell>{job.company}</TableCell>
                    <TableCell className="font-medium">
                      {/* Clicking the title opens the full-info modal. */}
                      <button
                        type="button"
                        onClick={() => setViewId(job.id)}
                        className="text-left hover:underline"
                      >
                        {job.title}
                      </button>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{reason}</TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>

      <JobDetailDialog jobId={viewId} onOpenChange={(open) => !open && setViewId(null)} />
    </div>
  );
}
