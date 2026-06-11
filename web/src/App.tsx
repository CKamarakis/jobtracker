import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { JobListPage } from "@/pages/JobListPage";
import { JobDetailPage } from "@/pages/JobDetailPage";

// Route table. The parent <Layout> route renders the header + <Outlet>; the nested
// routes fill the outlet. `index` is the default child for the parent's path ("/").
//   /            → JobListPage
//   /jobs/:id    → JobDetailPage  (":id" is read via useParams in the page)
//   *            → simple not-found
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<JobListPage />} />
        <Route path="jobs/:id" element={<JobDetailPage />} />
        <Route path="*" element={<p className="text-muted-foreground">Not found.</p>} />
      </Route>
    </Routes>
  );
}
