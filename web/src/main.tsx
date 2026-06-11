import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { ShortlistProvider } from "@/shortlist/ShortlistContext";

// Provider stack, outermost first:
//  - BrowserRouter     → enables client-side routing (URL ↔ component, no full reloads)
//  - ShortlistProvider → makes the transient shortlist available to every route
// StrictMode is dev-only and intentionally double-invokes effects to surface bugs
// like missing cleanup — our useAsync `cancelled` guard is what makes that safe.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ShortlistProvider>
        <App />
      </ShortlistProvider>
    </BrowserRouter>
  </StrictMode>,
);
