import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

/* ============================================================
   PAGE LAYOUT
   One place that owns page width, the header hierarchy
   (eyebrow -> title -> subtitle), section headers, and the
   toolbar strip that sits directly above content.
   ============================================================ */

/** PageShell - single source of page width + vertical rhythm. */
export function PageShell({ children, className = "", maxWidth = "max-w-[1400px]" }) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className={`${maxWidth} mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 focus:outline-none`}
    >
      <div className={className}>{children}</div>
    </main>
  );
}

/** PageHeader - breadcrumb/eyebrow/title/subtitle left, actions right. */
export function PageHeader({ eyebrow, title, subtitle, breadcrumb, actions, className = "" }) {
  return (
    <div className={`flex flex-col lg:flex-row lg:items-end justify-between gap-5 ${className}`}>
      <div className="min-w-0">
        {breadcrumb && (
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 mb-3 text-[11px]">
            {breadcrumb.map((crumb, i) => (
              <span key={crumb.label} className="flex items-center gap-1.5 min-w-0">
                {i > 0 && (
                  <ChevronRight className="h-3 w-3 text-slate-600 flex-shrink-0" aria-hidden="true" />
                )}
                {crumb.to && i < breadcrumb.length - 1 ? (
                  <Link
                    to={crumb.to}
                    className="text-slate-500 hover:text-[#00D4FF] transition truncate font-medium"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-slate-400 font-medium truncate">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}

        {eyebrow && <p className="text-eyebrow text-[#00D4FF] mb-2">{eyebrow}</p>}
        <h1 className="text-page-title text-white truncate">{title}</h1>
        {subtitle && (
          <p className="text-[13px] text-slate-400 mt-2 leading-relaxed max-w-2xl">{subtitle}</p>
        )}
      </div>

      {actions && <div className="flex items-center gap-2.5 flex-shrink-0">{actions}</div>}
    </div>
  );
}

/** SectionHeader - label + count on the left, controls on the right. */
export function SectionHeader({ title, count, hint, actions, className = "" }) {
  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 ${className}`}>
      <div className="flex items-baseline gap-3 min-w-0">
        <h2 className="text-card-title text-white">{title}</h2>
        {count !== undefined && count !== null && (
          <span className="text-meta text-slate-500 font-mono">{count}</span>
        )}
        {hint && <span className="text-meta text-slate-500 truncate">{hint}</span>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Toolbar - the control strip between the page header and content. */
export function Toolbar({ children, className = "" }) {
  return (
    <div
      role="toolbar"
      className={`surface-card px-3 py-2.5 flex flex-wrap items-center gap-2.5 ${className}`}
    >
      {children}
    </div>
  );
}