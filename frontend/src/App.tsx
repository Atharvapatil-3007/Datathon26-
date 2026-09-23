import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Shell from "./components/Shell";
import LoginPage from "./pages/LoginPage";
import UploadPage from "./pages/UploadPage";
import DatasetsPage from "./pages/DatasetsPage";
import DashboardPage from "./pages/DashboardPage";
import AnalysisPickerPage from "./pages/AnalysisPickerPage";
import SelfAnalysisPage from "./pages/SelfAnalysisPage";
import MergerAnalysisPage from "./pages/MergerAnalysisPage";
import BenchmarkAnalysisPage from "./pages/BenchmarkAnalysisPage";
import AssistantPage from "./pages/AssistantPage";

export default function App() {
  const location = useLocation();
  const authenticated = window.localStorage.getItem("finsight.authenticated") === "true";

  if (!authenticated && location.pathname !== "/login") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (location.pathname === "/login") {
    return <LoginPage />;
  }

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/datasets" replace />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/datasets" element={<DatasetsPage />} />
        <Route path="/datasets/:datasetId" element={<DashboardPage />} />
        <Route
          path="/datasets/:datasetId/analysis"
          element={<AnalysisPickerPage />}
        />
        <Route
          path="/datasets/:datasetId/analysis/self"
          element={<SelfAnalysisPage />}
        />
        <Route
          path="/datasets/:datasetId/analysis/merger"
          element={<MergerAnalysisPage />}
        />
        <Route
          path="/datasets/:datasetId/analysis/benchmark"
          element={<BenchmarkAnalysisPage />}
        />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="*" element={<Navigate to="/datasets" replace />} />
      </Routes>
    </Shell>
  );
}
