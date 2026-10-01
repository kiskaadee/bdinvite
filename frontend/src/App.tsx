import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout } from "./admin/AdminLayout";
import { ConfigEditor } from "./admin/ConfigEditor";
import { RsvpTable } from "./admin/RsvpTable";
import { Invitation } from "./invitation/Invitation";

export function App() {
  return (
    <BrowserRouter basename="/birthday">
      <Routes>
        {/* Guest Public Route */}
        <Route path="/" element={<Invitation />} />

        {/* Authelia-Protected Admin Dashboard */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<RsvpTable />} />
          <Route path="config" element={<ConfigEditor />} />
        </Route>

        {/* Catch-all fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
