import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

// The "transient shortlist" from the ROADMAP. Selection lives in React state and
// is shared via Context so the list page, detail page, and header badge all read
// the same set without prop-drilling through every component in between.
//
// It is DELIBERATELY not persisted — refresh clears it. That's the honest boundary
// of Phase C: durable shortlists (survive restart, write back to the store) arrive
// with the database in Phase D as a POST behind the api/data_source seam. Building
// it transient first keeps the UI state and the persistence concern cleanly separate.

interface ShortlistContextValue {
  ids: Set<string>;
  isShortlisted: (id: string) => boolean;
  toggle: (id: string) => void;
  count: number;
}

// Created with `undefined` so the hook below can detect "used outside the provider"
// and fail loudly instead of silently handing back a broken default.
const ShortlistContext = createContext<ShortlistContextValue | undefined>(undefined);

export function ShortlistProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<Set<string>>(new Set());

  // useCallback so `toggle`'s identity is stable across renders — lets consumers
  // that depend on it (memoised rows, effects) avoid needless re-runs.
  const toggle = useCallback((id: string) => {
    setIds((prev) => {
      // Always build a NEW Set. Mutating `prev` in place wouldn't change its
      // reference, so React would skip the re-render. Immutable update = re-render.
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const value = useMemo<ShortlistContextValue>(
    () => ({
      ids,
      isShortlisted: (id) => ids.has(id),
      toggle,
      count: ids.size,
    }),
    [ids, toggle],
  );

  return <ShortlistContext.Provider value={value}>{children}</ShortlistContext.Provider>;
}

/** Access the shortlist. Throws if used outside <ShortlistProvider>. */
export function useShortlist(): ShortlistContextValue {
  const ctx = useContext(ShortlistContext);
  if (ctx === undefined) {
    throw new Error("useShortlist must be used within a <ShortlistProvider>");
  }
  return ctx;
}
