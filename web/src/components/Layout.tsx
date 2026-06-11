import { Link, Outlet } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { useShortlist } from "@/shortlist/ShortlistContext";

// The app shell: a header that's present on every route, then <Outlet/> where the
// router swaps in the matched page (list or detail). The shortlist count in the
// header reads the same Context the pages write to, so it updates live as you
// toggle jobs anywhere in the app.
export function Layout() {
  const { count } = useShortlist();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            Job-Hunt
          </Link>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Shortlist</span>
            <Badge variant={count > 0 ? "default" : "secondary"}>{count}</Badge>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
