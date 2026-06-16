import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  Loader2Icon,
  StickyNoteIcon,
  Trash2Icon,
} from "lucide-react";
import { getFetchStatus, listJobs, waitForFetch } from "@/api/client";
import type { JobSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { JobDetailDialog } from "@/components/JobDetailDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// Post-fetch review queue. Flow: land here from "Go fetch", wait for the background
// run to finish (one long-poll — no client polling), then show the fresh pool as a
// flat table the user works through: open the ad, jot a note, drop it, or approve it.
//
// The notes / remove / approve actions are UX-ONLY for now: they mutate LOCAL component
// state (ephemeral, reset on reload) and hit no backend. Persistence (write endpoints)
// lands in a later pass. The view + external-link actions are real.

export function ResultsPage() {
  // One mount-time flow, no polling: read run state → if a run is in flight, await it
  // (server holds /fetch/wait open until it finishes) → load the pool. `fetching` drives
  // the spinner; `jobs === null && !error` before that means we're still resolving.
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await getFetchStatus();
        if (cancelled) return;
        if (status.state === "running") {
          setFetching(true);
          await waitForFetch(); // resolves when the run completes (or the 90s cap)
        }
        if (cancelled) return;
        const data = await listJobs();
        if (cancelled) return;
        setJobs(data);
      } catch (e) {
        if (!cancelled) setError(e as Error);
      } finally {
        if (!cancelled) setFetching(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loading = jobs === null && !error;

  // Local-only review state (ephemeral — see header note).
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [notesFor, setNotesFor] = useState<string | null>(null);
  // Which job's full info is open in the detail modal (null = closed).
  const [viewId, setViewId] = useState<string | null>(null);

  // The review queue is only what PASSED triage (strong fit / fit / stretch). Triage
  // rejects are split off to their own page (linked via the CTA below); title-prefiltered
  // jobs never reach the UI. `rejectedCount` drives that CTA.
  const passed = useMemo(
    () => (jobs ?? []).filter((j) => j.triage_verdict != null && j.triage_verdict !== "reject"),
    [jobs],
  );
  const rejectedCount = useMemo(
    () => (jobs ?? []).filter((j) => j.triage_verdict === "reject").length,
    [jobs],
  );
  const visible = useMemo(
    () => passed.filter((j) => !removed.has(j.id)),
    [passed, removed],
  );

  function remove(id: string) {
    setRemoved((prev) => new Set(prev).add(id));
  }
  function toggleApprove(id: string) {
    setApproved((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // While the background run is in flight, the whole view is just the wait state —
  // there's no stale table to show, so we don't render one.
  if (fetching) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 text-center md:gap-6">
        <Loader2Icon className="size-6 animate-spin text-muted-foreground md:size-12" />
        <div className="space-y-1 md:space-y-2">
          <p className="text-sm font-medium md:text-lg">Fetching and triaging…</p>
          <p className="text-sm text-muted-foreground md:text-base">This takes around a minute. Hang tight.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Fetch results</h1>
          <p className="text-sm text-muted-foreground">
            {jobs ? `${visible.length} to review` : " "} · strongest verdict first
          </p>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {error.message}
        </p>
      )}

      {rejectedCount > 0 && (
        <Link
          to="/rejected-ads"
          className="flex items-center justify-between rounded-lg border border-dashed px-4 py-3 text-sm transition-colors hover:bg-muted/50"
        >
          <span className="text-muted-foreground">
            <span className="font-medium text-foreground">{rejectedCount}</span> rejected ads today —{" "}
            take a look
          </span>
          <ChevronRightIcon className="size-4 text-muted-foreground" />
        </Link>
      )}

      <div className="rounded-lg border">
        {/* Cells wrap (whitespace-normal + align-top) so long company/title text fits
            the container width instead of forcing a horizontal scroll. */}
        <Table className="[&_td]:whitespace-normal [&_td]:align-top">
          <TableHeader>
            <TableRow>
              <TableHead className="w-10 text-right">#</TableHead>
              <TableHead className="w-[28%]">Company</TableHead>
              <TableHead>Title</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 4 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!loading && visible.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-12 text-center text-muted-foreground">
                  {rejectedCount > 0
                    ? "Nothing passed triage this run — the rejected jobs are linked above."
                    : "Nothing to review. Run a fetch from the dashboard to pull fresh jobs."}
                </TableCell>
              </TableRow>
            )}

            {!loading &&
              visible.map((job, i) => {
                const adUrl = job.url ?? job.ats_url;
                const isApproved = approved.has(job.id);
                const hasNote = Boolean(notes[job.id]?.trim());
                return (
                  <TableRow key={job.id} className={cn(isApproved && "bg-emerald-50/60")}>
                    <TableCell className="text-right text-muted-foreground tabular-nums">
                      {i + 1}
                    </TableCell>
                    <TableCell>{job.company}</TableCell>
                    <TableCell className="font-medium">
                      {/* Clicking the title opens the full-info modal (same as the eye
                          action did before). The external-ad link moved to its own icon. */}
                      <button
                        type="button"
                        onClick={() => setViewId(job.id)}
                        className="text-left hover:underline"
                      >
                        {job.title}
                      </button>
                    </TableCell>
                    {/* All four row actions live in one column; nowrap keeps them on a
                        single line while the Company/Title cells above are free to wrap. */}
                    <TableCell className="whitespace-nowrap align-middle text-right">
                      <div className="flex items-center justify-end gap-1">
                        {adUrl && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            title="Open job ad in a new tab"
                            render={
                              <a href={adUrl} target="_blank" rel="noopener noreferrer" />
                            }
                          >
                            <ExternalLinkIcon />
                          </Button>
                        )}
                        <Button
                          variant={hasNote ? "secondary" : "ghost"}
                          size="icon-sm"
                          title={hasNote ? "Edit note" : "Add note"}
                          onClick={() => setNotesFor(job.id)}
                        >
                          <StickyNoteIcon />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title="Remove from review"
                          onClick={() => remove(job.id)}
                        >
                          <Trash2Icon />
                        </Button>
                        <Button
                          variant={isApproved ? "default" : "ghost"}
                          size="icon-sm"
                          title={isApproved ? "Approved — click to undo" : "Approve"}
                          onClick={() => toggleApprove(job.id)}
                        >
                          <CheckIcon />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>

      {/* `key` remounts the editor per row so its draft state seeds from that row's note. */}
      <NotesDialog
        key={notesFor ?? "none"}
        open={notesFor !== null}
        initial={notesFor ? notes[notesFor] ?? "" : ""}
        onOpenChange={(o) => !o && setNotesFor(null)}
        onSave={(text) => {
          if (notesFor) setNotes((prev) => ({ ...prev, [notesFor]: text }));
          setNotesFor(null);
        }}
      />

      {/* The View action opens the shared detail modal (same one RejectedPage uses);
          it shows the full ad plus the triage verdict + reasoning. */}
      <JobDetailDialog jobId={viewId} onOpenChange={(open) => !open && setViewId(null)} />
    </div>
  );
}

/** Local-only note editor. The text lives in the parent's state (not persisted yet). */
function NotesDialog({
  open,
  initial,
  onOpenChange,
  onSave,
}: {
  open: boolean;
  initial: string;
  onOpenChange: (o: boolean) => void;
  onSave: (text: string) => void;
}) {
  // Seeded once on mount; the parent remounts this per row via `key`, so `initial`
  // is always this row's note.
  const [draft, setDraft] = useState(initial);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Note</DialogTitle>
          <DialogDescription>Not saved to the server yet — local to this session.</DialogDescription>
        </DialogHeader>
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={5}
          placeholder="Why this one's interesting, who to ping, follow-ups…"
          className="w-full resize-none rounded-lg border border-input bg-transparent p-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => onSave(draft)}>Save note</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
