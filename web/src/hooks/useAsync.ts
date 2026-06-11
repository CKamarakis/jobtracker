import { useEffect, useState } from "react";

// Why a custom hook instead of TanStack Query? Phase C's goal is to *see* the
// data-fetching state machine, not hide it. Every async read is one of four
// states — idle/loading/error/success — and this hook makes that explicit.
// (TanStack Query is the natural Phase-D upgrade: it adds caching, refetching,
// and dedup that we'd otherwise hand-roll. We're deliberately not there yet.)

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

/**
 * Run an async function and track its state. Re-runs whenever `deps` change.
 *
 * The `cancelled` flag is the important bit: if the component unmounts — or deps
 * change and fire a new request — before the in-flight promise resolves, we must
 * NOT call setState with the stale result. Without this guard you get React's
 * "can't update unmounted component" warning and, worse, a fast filter change
 * could let an older response overwrite a newer one (a race).
 *
 * @param fn   the async producer (e.g. () => listJobs(filters))
 * @param deps re-fetch trigger list, like useEffect deps
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));

    fn().then(
      (data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      },
      (error: unknown) => {
        if (!cancelled) setState({ data: null, loading: false, error: error as Error });
      },
    );

    return () => {
      cancelled = true;
    };
    // fn is intentionally omitted: callers pass an inline closure (new identity each
    // render), so `deps` is the real trigger. This mirrors how useEffect deps work.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
