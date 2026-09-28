import { Loader2 } from "lucide-react";

/* ============================================================
   SHARED UI PRIMITIVES
   Single definitions for buttons, badges, cards, skeletons and
   spinners so every page renders identical states. Replaces the
   per-page inline Tailwind button/badge strings.
   ============================================================ */

const BTN_BASE =
  "inline-flex items-center justify-center gap-2 font-semibold transition " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF] " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-[#040914] " +
  "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100";

const BTN_SIZE = {
  sm: "h-8 px-3 text-[11px] rounded-[10px]",
  md: "h-10 px-4 text-xs rounded-control",
  lg: "h-11 px-5 text-xs rounded-control",
};

const BTN_VARIANT = {
  primary:
    "bg-gradient-to-r from-[#2563EB] to-[#00D4FF] text-[#040914] " +
    "hover:scale-[1.02] active:scale-[0.98] shadow-[0_0_15px_rgba(0,212,255,0.2)]",
  secondary:
    "bg-white/[0.06] text-slate-200 border border-white/[0.10] " +
    "hover:bg-white/[0.10] hover:text-white",
  ghost:
    "text-slate-400 hover:text-white hover:bg-white/[0.06] border border-transparent",
  danger:
    "bg-red-500/10 text-red-400 border border-red-500/25 " +
    "hover:bg-red-500/20 hover:text-red-300",
  outline:
    "border border-white/[0.12] text-slate-300 hover:border-[#00D4FF]/40 " +
    "hover:text-[#00D4FF] hover:bg-[#00D4FF]/5",
};

/**
 * Button - one component for every action in the panel.
 * Loading state swaps in a spinner, locks width and disables the control.
 */
export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  className = "",
  ...props
}) {
  const isDisabled = disabled || loading;
  return (
    <button
      {...props}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={`${BTN_BASE} ${BTN_SIZE[size]} ${BTN_VARIANT[variant]} ${className}`}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

/* ---------------- Badge ---------------- */

const BADGE_VARIANT = {
  success: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
  danger: "bg-red-500/10 border-red-500/20 text-red-400",
  warning: "bg-amber-500/10 border-amber-500/20 text-amber-400",
  accent: "bg-[#00D4FF]/10 border-[#00D4FF]/25 text-[#00D4FF]",
  neutral: "bg-white/[0.05] border-white/[0.10] text-slate-400",
};

export function Badge({ children, variant = "neutral", className = "", ...props }) {
  return (
    <span
      {...props}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border
        text-[10px] font-semibold uppercase tracking-wider font-mono
        ${BADGE_VARIANT[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

export function StatusDot({ variant = "success" }) {
  const color =
    variant === "success"
      ? "bg-emerald-400 shadow-[0_0_8px_#10b981]"
      : variant === "danger"
        ? "bg-red-400 shadow-[0_0_8px_#ef4444]"
        : "bg-amber-400 shadow-[0_0_8px_#f59e0b]";
  return <span className={`h-1.5 w-1.5 rounded-full ${color}`} aria-hidden="true" />;
}

/* ---------------- Card ---------------- */

export function Card({ children, className = "", interactive = false, ...props }) {
  const base = interactive
    ? "surface-card hover:border-[#00D4FF]/35 hover:bg-white/[0.05] " +
      "hover:-translate-y-0.5 hover:shadow-raised transition duration-200"
    : "surface-card";
  return (
    <div {...props} className={`${base} ${className}`}>
      {children}
    </div>
  );
}

/* ---------------- Skeletons ---------------- */

export function Skeleton({ className = "" }) {
  return <div className={`shimmer rounded-[8px] bg-white/[0.05] ${className}`} aria-hidden="true" />;
}

export function SkeletonCard() {
  return (
    <Card className="p-5 min-h-[196px] flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <Skeleton className="h-9 w-9 rounded-[10px]" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-4 w-3/5" />
        <Skeleton className="h-3 w-2/5" />
      </div>
      <div className="mt-auto space-y-2 pt-4 border-t border-white/[0.05]">
        <Skeleton className="h-3 w-4/5" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </Card>
  );
}

export function SkeletonStatCard() {
  return (
    <Card className="p-5 space-y-3">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-24" />
    </Card>
  );
}

/* ---------------- Feedback states ---------------- */

export function Spinner({ className = "h-5 w-5" }) {
  return (
    <Loader2
      className={`${className} animate-spin text-[#00D4FF]`}
      aria-label="Loading"
      role="status"
    />
  );
}

/**
 * ErrorBanner - inline, actionable failure state.
 * Replaces silent toast-only errors with something the user can retry.
 */
export function ErrorBanner({ title = "Something went wrong", message, onRetry }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 p-4 rounded-card bg-red-500/[0.07] border border-red-500/25"
    >
      <span className="mt-0.5 h-4 w-4 flex-shrink-0 rounded-full bg-red-500/20 text-red-400 grid place-items-center text-[10px] font-bold">
        !
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-semibold text-red-300">{title}</p>
        {message && <p className="text-[11px] text-red-400/80 mt-1 leading-relaxed">{message}</p>}
      </div>
      {onRetry && (
        <Button variant="danger" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}