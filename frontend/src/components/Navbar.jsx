import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Layers, Database, MessageSquare, Activity, LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/Primitives";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

/* ============================================================
   NAVBAR
   Global admin navigation. Uses the shared surface + type
   tokens so it lines up with every page shell (max-w-[1400px]).
   ============================================================ */

export default function Navbar({ onLogout }) {
  const location = useLocation();
  const currentPath = location.pathname;
  const [health, setHealth] = useState(null);

  // Read admin username from stored session
  const getAdminUser = () => {
    try {
      const session = JSON.parse(localStorage.getItem("oceanrag_admin_session") || "{}");
      return session.username || null;
    } catch {
      return null;
    }
  };
  const adminUser = getAdminUser();
  const isLoggedIn = !!adminUser;

  // Check backend health once when the frontend-backend connection is established
  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/health`);
        const data = await res.json();
        if (isMounted) setHealth(data.status === "OK" ? "ok" : "degraded");
      } catch {
        if (isMounted) setHealth("down");
      }
    };
    checkHealth();
    return () => {
      isMounted = false;
    };
  }, []);

  const healthTone =
    health === "ok" ? "text-emerald-400" : health === "down" ? "text-red-400" : "text-amber-400";
  const healthLabel = health === "ok" ? "OK" : health === "down" ? "OFFLINE" : "...";

  const navLinkClass = (active) =>
    `flex items-center gap-2 px-4 h-8 rounded-[10px] text-[12px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF] ${
      active
        ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.25)]"
        : "text-slate-400 hover:text-white hover:bg-white/[0.06]"
    }`;

  return (
    <header className="sticky top-0 z-50 w-full px-4 sm:px-6 lg:px-8 pt-4">
      <div
        className="mx-auto max-w-[1400px] surface-card rounded-card px-4 sm:px-6 py-2.5 flex items-center justify-between gap-4 shadow-raised backdrop-blur-md bg-white/[0.04]"
        data-testid="navbar-container"
      >
        {/* Brand Logo */}
        <Link
          to="/admin/applications"
          className="flex items-center gap-2.5 group focus-visible:outline-none rounded-[10px] flex-shrink-0"
          data-testid="nav-brand"
        >
          <span className="relative flex-shrink-0">
            <span className="absolute -inset-0.5 rounded-[10px] bg-gradient-to-r from-[#00D4FF] to-[#2563EB] opacity-60 blur-[6px] group-hover:opacity-90 transition duration-300" />
            <span className="relative block bg-[#0B1221] p-1.5 rounded-[10px] border border-white/[0.10]">
              <Layers className="h-4 w-4 text-[#00D4FF]" />
            </span>
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-white hidden sm:inline">
            RENAI<span className="text-[#00D4FF]">CHATBOT</span>
          </span>
        </Link>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 p-0.5 bg-white/[0.03] border border-white/[0.07] rounded-[12px]">
          <Link
            to="/admin/applications"
            className={navLinkClass(
              currentPath.startsWith("/admin") || currentPath.startsWith("/dashboard")
            )}
            data-testid="nav-dashboard"
          >
            <Database className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Admin Console</span>
          </Link>

          <Link
            to="/chat"
            className={navLinkClass(currentPath === "/chat")}
            data-testid="nav-chat"
          >
            <MessageSquare className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Chat</span>
          </Link>
        </nav>

        {/* Right controls: health + user + logout */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Health Status Indicator */}
          <div
            className={`hidden sm:flex items-center gap-1.5 text-[10px] font-mono font-medium ${healthTone}`}
            title={`Backend health: ${health || "checking..."}`}
            data-testid="health-indicator"
          >
            <Activity className="h-3.5 w-3.5" />
            <span>{healthLabel}</span>
          </div>

          {/* User + Logout (only when logged in) */}
          {isLoggedIn && (
            <div
              className="flex items-center gap-3 pl-3 border-l border-white/[0.08]"
              data-testid="user-menu"
            >
              <span className="hidden md:flex items-center gap-1.5 text-[12px] font-semibold text-slate-300">
                <User className="h-3.5 w-3.5 text-[#00D4FF]" />
                {adminUser}
              </span>
              <Button
                variant="danger"
                size="sm"
                onClick={onLogout}
                title="Logout"
                data-testid="logout-btn"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}