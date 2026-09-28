import { Card, Skeleton } from "@/components/ui/Primitives";

/* ============================================================
   STAT CARD + EMPTY STATE
   ============================================================ */

/** StatCard - metric tile for the dashboard metrics band. */
export function StatCard({ label, value, hint, icon: Icon, tone = "default", loading = false }) {
  const toneColor =
    tone === "accent"
      ? "text-[#00D4FF]"
      : tone === "success"
        ? "text-emerald-400"
        : tone === "warning"
          ? "text-amber-400"
          : tone === "danger"
            ? "text-red-400"
            : "text-slate-300";

  return (
    <Card className="p-5 flex flex-col justify-between min-h-[118px] group">
      <div className="flex items-start justify-between gap-3">
        <p className="text-eyebrow text-slate-400">{label}</p>
        {Icon && (
          <span className="p-1.5 rounded-[10px] bg-white/[0.04] border border-white/[0.07] text-slate-400 group-hover:text-[#00D4FF] group-hover:border-[#00D4FF]/25 transition">
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </span>
        )}
      </div>

      {loading ? (
        <Skeleton className="h-8 w-16 my-1" />
      ) : (
        <p className={`text-[28px] leading-none font-semibold font-mono ${toneColor} my-1`}>
          {value}
        </p>
      )}

      {hint && <p className="text-meta text-slate-400 truncate">{hint}</p>}
    </Card>
  );
}

/**
 * EmptyState - two distinct copies:
 *  - first run: offers a primary CTA
 *  - filtered result: offers to clear filters
 */
export function EmptyState({ icon: Icon, title, message, action, compact = false, className = "" }) {
  return (
    <div
      className={`surface-card border-dashed text-center ${
        compact ? "px-5 py-9" : "px-6 py-14"
      } ${className}`}
    >
      {Icon && (
        <div
          className={`mx-auto rounded-full bg-white/[0.04] border border-white/[0.08] grid place-items-center ${
            compact ? "h-10 w-10 mb-3" : "h-12 w-12 mb-4"
          }`}
        >
          <Icon
            className={compact ? "h-4 w-4 text-slate-400" : "h-5 w-5 text-slate-400"}
            aria-hidden="true"
          />
        </div>
      )}
      <h3 className={`text-card-title ${compact ? "text-slate-300 text-[14px]" : "text-slate-200"}`}>
        {title}
      </h3>
      {message && (
        <p
          className={`text-body mt-2 mx-auto ${
            compact ? "text-slate-400 max-w-sm" : "text-slate-400 max-w-md"
          }`}
        >
          {message}
        </p>
      )}
      {action && <div className={`flex justify-center ${compact ? "mt-4" : "mt-5"}`}>{action}</div>}
    </div>
  );
}
