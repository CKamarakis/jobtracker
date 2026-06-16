import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CircleCheckIcon, CircleXIcon, SearchIcon, SparklesIcon } from "lucide-react";
import { getFetchStatus } from "@/api/client";
import type { FetchStatus } from "@/api/types";
import { useAsync } from "@/hooks/useAsync";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { GoFetchDialog } from "@/components/GoFetchDialog";

// The home screen. Two jobs: (1) the "Go fetch" CTA that drives a fresh
// ingest+triage run, and (2) an "applications" table that's an empty state for now —
// there's no apply flow yet, so this is a placeholder the apply pipeline will fill.

export function DashboardPage() {
  const navigate = useNavigate();
  const [fetchOpen, setFetchOpen] = useState(false);
  // Read the last/current run state once on load. No polling: a fresh page load
  // reflects the latest state, which is all a local single-user app needs.
  const { data: status } = useAsync(getFetchStatus, []);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bonjour, Sunshine! Naa?</h1>
          <p className="text-sm text-muted-foreground">
            Pull a fresh batch of roles, or pick up where you left off.
          </p>
          <FetchStatusLine status={status} />
        </div>
        <div className="flex flex-col items-end gap-2">
          <Button
            size="lg"
            className="px-6 text-base"
            onClick={() => setFetchOpen(true)}
            disabled={status?.state === "running"}
          >
            <SparklesIcon />
            {status?.state === "running" ? "Fetching…" : "Go fetch"}
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" render={<Link to="/search" />}>
              <SearchIcon />
              Browse jobs
            </Button>
            <Button variant="outline" render={<Link to="/results" />}>
              <CircleCheckIcon />
              Review approved
            </Button>
            <Button variant="outline" render={<Link to="/rejected-ads" />}>
              <CircleXIcon />
              Rejected ads
            </Button>
          </div>
        </div>
      </div>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Applications</h2>
          <p className="text-sm text-muted-foreground">Roles you've moved forward on.</p>
        </div>
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Role</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell colSpan={4} className="py-12 text-center text-muted-foreground">
                  No applications yet. Browse jobs and shortlist the ones worth pursuing.
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </section>

      <GoFetchDialog
        open={fetchOpen}
        onOpenChange={setFetchOpen}
        onStarted={() => navigate("/results")}
      />
    </div>
  );
}

/** One-line summary of the last/current fetch run. Reload the page to refresh it. */
function FetchStatusLine({ status }: { status: FetchStatus | null }) {
  if (!status || status.state === "idle") return null;
  if (status.state === "running") {
    return <p className="mt-1 text-sm text-muted-foreground">A fetch is running… reload to see progress.</p>;
  }
  if (status.state === "error") {
    return <p className="mt-1 text-sm text-destructive">Last fetch failed: {status.error ?? "unknown error"}</p>;
  }
  // done
  const pool = (status.counts as { pool?: number } | null)?.pool;
  return (
    <p className="mt-1 text-sm text-muted-foreground">
      Last fetch: {pool != null ? `${pool} jobs in the pool` : "complete"}.
    </p>
  );
}
