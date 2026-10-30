import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import { MetaProvider } from "./hooks/useMeta";
import { AppShell } from "./layouts/AppShell";
import { Architecture } from "./pages/Architecture";
import { EvaluationWorkspace } from "./pages/EvaluationWorkspace";
import { FormulaRegistry } from "./pages/FormulaRegistry";
import { Landing } from "./pages/Landing";
import { T12Workspace } from "./pages/T12Workspace";
import { EmptyState } from "./components/Feedback";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MetaProvider>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/t12" element={<T12Workspace />} />
            <Route path="/evaluation" element={<EvaluationWorkspace />} />
            <Route path="/formulas" element={<FormulaRegistry />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="*" element={<EmptyState title="Page not found" description="Use the navigation to return to the workbench." />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </MetaProvider>
  </React.StrictMode>,
);
