import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import Navbar from "@/components/Navbar";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import ApplicationDetail from "@/pages/ApplicationDetail";
import Chat from "@/pages/Chat";
import { Toaster } from "sonner";

const SESSION_KEY = "oceanrag_admin_session";

const isAuthenticated = () => {
  return !!localStorage.getItem(SESSION_KEY);
};

// Route guard: redirects to /login if no admin session exists
function ProtectedRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function AppContent() {
  const navigate = useNavigate();

  const handleLoginSuccess = () => {
    navigate("/admin/applications");
  };

  const handleLogout = () => {
    localStorage.removeItem(SESSION_KEY);
    navigate("/login");
  };

  return (
    <>
      <Toaster
        richColors
        closeButton
        theme="dark"
        position="top-right"
        offset={{ top: 88, right: 24 }}
        mobileOffset={{ top: 76, right: 12 }}
      />
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <Navbar onLogout={handleLogout} />
      <Routes>
        <Route path="/login" element={<Login onLoginSuccess={handleLoginSuccess} />} />
        {/* Admin routes (canonical) - protected */}
        <Route
          path="/admin/applications"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/applications/:id"
          element={
            <ProtectedRoute>
              <ApplicationDetail />
            </ProtectedRoute>
          }
        />
        {/* Legacy aliases */}
        <Route path="/" element={<Navigate to="/admin/applications" replace />} />
        <Route path="/dashboard" element={<Navigate to="/admin/applications" replace />} />
        <Route path="/dashboard/:id" element={<Navigate to={`/admin/applications/${window.location.pathname.split("/")[2]}`} replace />} />
        {/* Chat */}
        <Route path="/chat" element={<Chat />} />
        <Route path="*" element={<Navigate to="/admin/applications" replace />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </div>
  );
}

export default App;