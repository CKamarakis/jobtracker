import { useEffect, useState } from "react";
import { listSources, triggerFetch } from "@/api/client";
import { useAsync } from "@/hooks/useAsync";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// The "Go fetch" flow: pick sources + a freshness window, then POST /fetch. The run
// happens in a background thread on the server; this dialog fires it and closes. The
// dashboard reads /fetch/status on load to reflect the run's state — we deliberately
// do NOT poll (single-user local app; a heartbeat every second buys nothing).
//
// `onStarted` lets the dashboard refresh its status line once, right after the POST.

const DURATIONS = [
  { value: "1d", label: "1 day" },
  { value: "3d", label: "3 days" },
  { value: "1w", label: "1 week" },
] as const;

export function GoFetchDialog({
  open,
  onOpenChange,
  onStarted,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onStarted?: () => void;
}) {
  const { data: sources, loading: sourcesLoading, error: sourcesError } = useAsync(listSources, [open]);

  // Form state. `selected === null` means "all sources" — the default. This avoids
  // seeding a set from async data via an effect: until the user deselects something,
  // null is the answer, and we materialise a set lazily on the first toggle.
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [duration, setDuration] = useState<string>("1d");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<Error | null>(null);

  // Clear any prior submit error each time the dialog (re)opens. (Mirrors the codebase's
  // accepted setState-in-effect pattern, e.g. useAsync — resetting transient state when a
  // controlling prop flips. Could be a parent `key` remount instead.)
  useEffect(() => {
    if (open) setSubmitError(null);
  }, [open]);

  const isOn = (src: string) => selected === null || selected.has(src);

  function toggle(src: string) {
    setSelected((prev) => {
      // First toggle materialises the implicit "all" into a concrete set.
      const next = new Set(prev ?? sources ?? []);
      if (next.has(src)) next.delete(src);
      else next.add(src);
      return next;
    });
  }

  // null (all) is fine to submit; an explicit empty set is not.
  const noneSelected = selected !== null && selected.size === 0;

  async function start() {
    if (noneSelected) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Omit `sources` when "all" is selected → backend treats null as every source.
      const all = selected === null || (sources != null && selected.size === sources.length);
      await triggerFetch({ sources: all ? null : [...selected!], duration });
      onStarted?.();
      onOpenChange(false);
    } catch (e) {
      setSubmitError(e as Error);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Fetch new jobs</DialogTitle>
          <DialogDescription>
            Pull fresh listings from the selected sources, then triage them against your criteria.
            This runs in the background and replaces the current pool.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* Sources multiselect */}
          <div className="space-y-2">
            <p className="text-sm font-medium">Sources</p>
            {sourcesLoading && <p className="text-sm text-muted-foreground">Loading sources…</p>}
            {sourcesError && <p className="text-sm text-destructive">{sourcesError.message}</p>}
            <div className="flex flex-wrap gap-2">
              {sources?.map((src) => {
                const on = isOn(src);
                return (
                  <Button
                    key={src}
                    type="button"
                    size="sm"
                    variant={on ? "default" : "outline"}
                    onClick={() => toggle(src)}
                    className="capitalize"
                  >
                    {src}
                  </Button>
                );
              })}
            </div>
          </div>

          {/* Duration single-select */}
          <div className="space-y-2">
            <p className="text-sm font-medium">Freshness window</p>
            <div className="flex gap-2">
              {DURATIONS.map((d) => (
                <Button
                  key={d.value}
                  type="button"
                  size="sm"
                  variant={duration === d.value ? "default" : "outline"}
                  onClick={() => setDuration(d.value)}
                >
                  {d.label}
                </Button>
              ))}
            </div>
          </div>
        </div>

        {submitError && (
          <p className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {submitError.message}
          </p>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={start} disabled={noneSelected || sourcesLoading || submitting}>
            {submitting ? "Starting…" : "Go fetch"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
