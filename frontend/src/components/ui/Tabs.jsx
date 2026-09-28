/* ============================================================
   TABS
   Segmented pill navigation used by the application detail
   screen. Keeps tab geometry and active/inactive states in one
   place instead of repeating the long conditional class string.
   ============================================================ */

export function Tabs({ tabs, value, onChange, className = "" }) {
  return (
    <div
      role="tablist"
      className={`flex items-center gap-1.5 p-1.5 surface-card rounded-card overflow-x-auto w-full ${className}`}
    >
      {tabs.map((tab) => {
        const active = value === tab.key;
        const Icon = tab.icon;
        return (
          <button
            key={tab.key}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.key)}
            data-testid={tab.testId}
            className={`flex items-center gap-2 px-4 py-2 rounded-[10px] text-[11px] font-semibold tracking-wider uppercase transition flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF] ${
              active
                ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.25)]"
                : "text-slate-400 hover:text-white hover:bg-white/[0.06]"
            }`}
          >
            {Icon && <Icon className="h-3.5 w-3.5" aria-hidden="true" />}
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}