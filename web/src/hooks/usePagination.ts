import { useEffect, useMemo, useState } from "react";

// Client-side pagination over an in-memory array. Reusable across tables: feed it the
// full list + a page size, get back the current slice and the controls. State lives
// here (not in the page) so any table gets identical clamp/reset behaviour for free.
export function usePagination<T>(items: T[], pageSize: number) {
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));

  // If the list shrinks (e.g. a refetch) past the current page, clamp back in range.
  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const startIndex = (page - 1) * pageSize;
  const pageItems = useMemo(
    () => items.slice(startIndex, startIndex + pageSize),
    [items, startIndex, pageSize],
  );

  return { page, setPage, pageCount, pageItems, startIndex };
}
