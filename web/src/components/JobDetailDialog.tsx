import ReactMarkdown from "react-markdown";
import { useJob } from "@/hooks/useJobs";
import { VerdictBadge } from "@/components/VerdictBadge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

// Reusable full-screen job-detail modal. Pass a `jobId` to open it (null = closed);
// it fetches the full record itself. Built as a shared component because the same
// "peek at one job's full info" surface is wanted from several tables (rejected,
// results, …) — one dialog, many call sites. Body lives in its own component so the
// useJob hook only runs while a job is selected.
export function JobDetailDialog({
  jobId,
  onOpenChange,
}: {
  jobId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={jobId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] gap-0 overflow-y-auto p-0">
        {jobId && <JobDetailDialogBody id={jobId} />}
      </DialogContent>
    </Dialog>
  );
}

function JobDetailDialogBody({ id }: { id: string }) {
  const { data: job, loading, error } = useJob(id);

  return (
    <div className="space-y-6 p-6">
      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {error.message}
        </p>
      )}

      {job && (
        <>
          <DialogHeader className="space-y-3 text-left">
            <DialogTitle className="text-2xl">{job.title}</DialogTitle>
            <DialogDescription>
              {job.company}
              {" · "}
              {job.remote ? "Remote" : job.location ?? "Location n/a"}
            </DialogDescription>

            <div className="flex flex-wrap items-center gap-2">
              <VerdictBadge verdict={job.triage_verdict} />
              {job.status && <Badge variant="secondary">{job.status}</Badge>}
              {job.source.map((s) => (
                <Badge key={s} variant="outline" className="text-muted-foreground">
                  {s}
                </Badge>
              ))}
              {job.posted_date && (
                <span className="text-xs text-muted-foreground">posted {job.posted_date}</span>
              )}
            </div>

            <div className="flex gap-4 text-sm">
              {job.url && (
                <a className="text-primary hover:underline" href={job.url} target="_blank" rel="noreferrer">
                  Job ad ↗
                </a>
              )}
              {job.ats_url && job.ats_url !== job.url && (
                <a className="text-primary hover:underline" href={job.ats_url} target="_blank" rel="noreferrer">
                  ATS page ↗
                </a>
              )}
            </div>
          </DialogHeader>

          <Separator />

          {/* `prose` (Tailwind typography plugin) styles the rendered markdown —
              headings, lists, paragraphs — which Tailwind's reset otherwise strips. */}
          {job.description ? (
            <article className="prose prose-neutral max-w-none">
              <ReactMarkdown>{job.description}</ReactMarkdown>
            </article>
          ) : (
            <p className="text-muted-foreground">No description on this record.</p>
          )}
        </>
      )}
    </div>
  );
}
