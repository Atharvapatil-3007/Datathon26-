import { Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import UploadPage from "./pages/UploadPage";
import DatasetsPage from "./pages/DatasetsPage";
import DashboardPage from "./pages/DashboardPage";
import AnalysisPickerPage from "./pages/AnalysisPickerPage";
import SelfAnalysisPage from "./pages/SelfAnalysisPage";
import MergerAnalysisPage from "./pages/MergerAnalysisPage";
import BenchmarkAnalysisPage from "./pages/BenchmarkAnalysisPage";
import AssistantPage from "./pages/AssistantPage";

export default function App() {
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
