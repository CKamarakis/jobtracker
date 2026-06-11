import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { useJob } from "@/hooks/useJobs";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ShortlistButton } from "@/components/ShortlistButton";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

export function JobDetailPage() {
  // useParams reads the ":id" segment defined in the route table (App.tsx).
  // It's always present here because the route only matches /jobs/:id.
  const { id } = useParams<{ id: string }>();
  const { data: job, loading, error } = useJob(id!);

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-muted-foreground hover:underline">
        ← Back to jobs
      </Link>

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
          <header className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">{job.title}</h1>
                <p className="text-muted-foreground">
                  {job.company}
                  {" · "}
                  {job.remote ? "Remote" : job.location ?? "Location n/a"}
                </p>
              </div>
              <ShortlistButton id={job.id} size="default" />
            </div>

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
          </header>

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
