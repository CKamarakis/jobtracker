import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { DashboardPage } from "@/pages/DashboardPage";
import { JobListPage } from "@/pages/JobListPage";
import { JobDetailPage } from "@/pages/JobDetailPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { StubPage } from "@/pages/StubPage";

// Route table. The parent <Layout> route renders the header + <Outlet>; the nested
// routes fill the outlet. `index` is the default child for the parent's path ("/").
//   /              → DashboardPage  (home: greeting + Go-fetch + applications)
//   /search        → JobListPage    (browse/filter the triaged pool)
//   /jobs/:id      → JobDetailPage  (":id" is read via useParams in the page)
//   /applications  → stub (apply flow not built yet)
//   /saved         → stub (shortlist view not built yet)
//   *              → simple not-found
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="search" element={<JobListPage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route path="jobs/:id" element={<JobDetailPage />} />
        <Route path="applications" element={<StubPage title="Applications" />} />
        <Route path="saved" element={<StubPage title="Saved" />} />
        <Route path="*" element={<p className="text-muted-foreground">Not found.</p>} />
      </Route>
    </Routes>
  );
}
