import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckIcon,
  ExternalLinkIcon,
  EyeIcon,
  Loader2Icon,
  StickyNoteIcon,
  Trash2Icon,
} from "lucide-react";
import { getFetchStatus, listJobs, waitForFetch } from "@/api/client";
import type { JobSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
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

  const visible = useMemo(
    () => (jobs ?? []).filter((j) => !removed.has(j.id)),
    [jobs, removed],
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
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Fetching and triaging…</p>
          <p className="text-sm text-muted-foreground">This takes around a minute. Hang tight.</p>
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

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10 text-right">#</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Title</TableHead>
              <TableHead className="w-12 text-center">View</TableHead>
              <TableHead className="w-12 text-center">Notes</TableHead>
              <TableHead className="w-12 text-center">Remove</TableHead>
              <TableHead className="w-12 text-center">Approve</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 7 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!loading && visible.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  Nothing to review. Run a fetch from the dashboard to pull fresh jobs.
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
                      {adUrl ? (
                        <a
                          href={adUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 hover:underline"
                        >
                          {job.title}
                          <ExternalLinkIcon className="size-3.5 text-muted-foreground" />
                        </a>
                      ) : (
                        job.title
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Button variant="ghost" size="icon-sm" title="View all info" render={<Link to={`/jobs/${job.id}`} />}>
                        <EyeIcon />
                      </Button>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        variant={hasNote ? "secondary" : "ghost"}
                        size="icon-sm"
                        title={hasNote ? "Edit note" : "Add note"}
                        onClick={() => setNotesFor(job.id)}
                      >
                        <StickyNoteIcon />
                      </Button>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Remove from review"
                        onClick={() => remove(job.id)}
                      >
                        <Trash2Icon />
                      </Button>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        variant={isApproved ? "default" : "ghost"}
                        size="icon-sm"
                        title={isApproved ? "Approved — click to undo" : "Approve"}
                        onClick={() => toggleApprove(job.id)}
                      >
                        <CheckIcon />
                      </Button>
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
