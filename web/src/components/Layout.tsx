import { Link, NavLink, Outlet } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useShortlist } from "@/shortlist/ShortlistContext";

// The app shell: a header (brand + primary nav + shortlist count) present on every
// route, then <Outlet/> where the router swaps in the matched page. The shortlist
// count reads the same Context the pages write to, so it updates live as you toggle
// jobs anywhere in the app.

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/search", label: "Search", end: false },
  { to: "/applications", label: "Applications", end: false },
  { to: "/saved", label: "Saved", end: false },
];

export function Layout() {
  const { count } = useShortlist();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-lg font-semibold tracking-tight">
              JobHunt
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              {NAV.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-2.5 py-1.5 transition-colors hover:text-foreground",
                      isActive ? "bg-muted font-medium text-foreground" : "text-muted-foreground",
                    )
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
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
