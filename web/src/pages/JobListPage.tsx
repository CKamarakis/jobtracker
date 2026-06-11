import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Status, Verdict } from "@/api/types";
import { useJobs } from "@/hooks/useJobs";
import { VERDICTS } from "@/lib/verdict";
import { VerdictBadge } from "@/components/VerdictBadge";
import { ShortlistButton } from "@/components/ShortlistButton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

const STATUSES: Status[] = ["new", "shortlisted", "applied", "skipped"];
// Radix Select forbids an empty-string item value, so "all" is the sentinel for
// "no filter" and we map it back to `undefined` (= omit the query param).
const ALL = "all";

export function JobListPage() {
  // Filter state lives here and is the single source of truth; changing it re-runs
  // useJobs (its deps are these values), which refetches from the API.
  const [verdict, setVerdict] = useState<Verdict | undefined>();
  const [status, setStatus] = useState<Status | undefined>();
  const { data: jobs, loading, error } = useJobs({ verdict, status });
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
          <p className="text-sm text-muted-foreground">
            {jobs ? `${jobs.length} shown` : " "} · strongest verdict first
          </p>
        </div>
        <div className="flex gap-3">
          <FilterSelect
            label="Verdict"
            value={verdict ?? ALL}
            options={VERDICTS}
            onChange={(v) => setVerdict(!v || v === ALL ? undefined : (v as Verdict))}
          />
          <FilterSelect
            label="Status"
            value={status ?? ALL}
            options={STATUSES}
            onChange={(v) => setStatus(!v || v === ALL ? undefined : (v as Status))}
          />
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
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Verdict</TableHead>
              <TableHead className="text-right">Shortlist</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!loading && jobs?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  No jobs match these filters.
                </TableCell>
              </TableRow>
            )}

            {!loading &&
              jobs?.map((job) => (
                <TableRow
                  key={job.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  <TableCell className="font-medium">{job.title}</TableCell>
                  <TableCell>{job.company}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {job.remote ? "Remote" : job.location ?? "—"}
                  </TableCell>
                  <TableCell>
                    <VerdictBadge verdict={job.triage_verdict} />
                  </TableCell>
                  <TableCell className="text-right">
                    <ShortlistButton id={job.id} />
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/** A labelled dropdown with an "All" option prepended. */
function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  // shadcn's Select (Base UI) emits `string | null` — null when cleared.
  onChange: (value: string | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-40 capitalize">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All</SelectItem>
          {options.map((opt) => (
            <SelectItem key={opt} value={opt} className="capitalize">
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
