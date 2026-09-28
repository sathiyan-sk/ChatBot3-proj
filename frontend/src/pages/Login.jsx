import { useState } from "react";
import { ShieldCheck, ArrowRight, Lock } from "lucide-react";
import { toast } from "sonner";

import { Card, Button } from "@/components/ui/Primitives";
import { Field, Input } from "@/components/ui/Form";

/* ============================================================
   LOGIN
   Administrator authentication screen. Shares the same surface
   card, control geometry and button tokens as the rest of the
   admin console so the entry point feels part of one product.
   ============================================================ */

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim() || isLoading) return;

    setIsLoading(true);

    try {
      // Use HTTP Basic Auth
      const credentials = btoa(`${username.trim()}:${password.trim()}`);

      const response = await fetch(
        `${import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"}/api/admin/applications`,
        {
          headers: {
            Authorization: `Basic ${credentials}`,
          },
        }
      );

      if (response.ok) {
        const userSession = {
          username: username.trim(),
          password: password.trim(),
          authenticatedAt: new Date().toISOString(),
        };

        localStorage.setItem("oceanrag_admin_session", JSON.stringify(userSession));
        onLoginSuccess(userSession);
        toast.success("Welcome back, Administrator!");
      } else {
        toast.error("Invalid credentials. Please try again.");
      }
    } catch (error) {
      console.error("Authentication failed:", error);
      toast.error("Connection error. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-80px)] flex items-center justify-center px-4 py-10 relative overflow-hidden">
      {/* Decorative brand glow */}
      <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-[#2563EB]/10 rounded-full blur-[80px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-72 h-72 bg-[#00D4FF]/10 rounded-full blur-[80px] pointer-events-none" />

      <div className="w-full max-w-md relative" data-testid="login-container">
        {/* Brand Header */}
        <div className="text-center mb-7">
          <div className="inline-flex p-3 rounded-card bg-white/[0.04] border border-white/[0.10] glow-cyan mb-4">
            <ShieldCheck className="h-7 w-7 text-[#00D4FF]" />
          </div>
          <h1 className="text-page-title text-white">
            RENAI<span className="text-[#00D4FF]">ADMIN</span> Console
          </h1>
          <p className="text-meta text-slate-400 mt-2">
            AI Knowledge Platform Administrator Portal
          </p>
        </div>

        {/* Login Form Card */}
        <Card className="p-7 relative overflow-hidden shadow-overlay">
          <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-[#2563EB] to-[#00D4FF]" />

          <div className="flex items-center gap-2 text-eyebrow text-[#00D4FF] mb-6">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            <span>Secure Access Control</span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
            <Field label="Username" htmlFor="login-username">
              <Input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                icon={Lock}
                autoComplete="username"
                className="h-11"
                data-testid="login-username-input"
                required
              />
            </Field>

            <Field label="Password" htmlFor="login-password">
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                icon={Lock}
                autoComplete="current-password"
                className="h-11"
                data-testid="login-password-input"
                required
              />
            </Field>

            <Button
              type="submit"
              size="lg"
              loading={isLoading}
              className="w-full h-12 tracking-widest uppercase mt-1"
              data-testid="login-submit-btn"
            >
              {isLoading ? (
                <span>AUTHORIZING...</span>
              ) : (
                <>
                  <span>LOGIN</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}