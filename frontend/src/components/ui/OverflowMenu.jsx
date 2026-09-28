import { useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";

/* ============================================================
   OVERFLOW MENU
   Collapses secondary card actions into one trigger so cards
   stay clean. Closes on outside click and Escape, and supports
   full keyboard navigation (Arrow keys, Home/End, Enter/Space).
   ============================================================ */

export function OverflowMenu({ items, label = "More actions" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const triggerRef = useRef(null);
  const itemRefs = useRef([]);

  const visible = items.filter(Boolean);

  useEffect(() => {
    if (!open) return;

    // Focus the first actionable item when the menu opens.
    const firstEnabled = visible.findIndex((i) => !i.disabled);
    itemRefs.current[firstEnabled === -1 ? 0 : firstEnabled]?.focus?.();

    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const closeAndRestore = () => {
    setOpen(false);
    triggerRef.current?.focus?.();
  };

  const onMenuKeyDown = (e) => {
    const enabledIndexes = visible
      .map((item, i) => (!item.disabled ? i : -1))
      .filter((i) => i !== -1);
    if (enabledIndexes.length === 0) return;

    const current = itemRefs.current.findIndex((el) => el === document.activeElement);
    const pos = enabledIndexes.indexOf(current);

    if (e.key === "Escape") {
      e.preventDefault();
      closeAndRestore();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = enabledIndexes[(pos + 1 + enabledIndexes.length) % enabledIndexes.length];
      itemRefs.current[next]?.focus?.();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prev = enabledIndexes[(pos - 1 + enabledIndexes.length) % enabledIndexes.length];
      itemRefs.current[prev]?.focus?.();
    } else if (e.key === "Home") {
      e.preventDefault();
      itemRefs.current[enabledIndexes[0]]?.focus?.();
    } else if (e.key === "End") {
      e.preventDefault();
      itemRefs.current[enabledIndexes[enabledIndexes.length - 1]]?.focus?.();
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen((v) => !v);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
          }
        }}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        className="h-8 w-8 grid place-items-center rounded-[10px] border border-white/[0.10] text-slate-400 hover:text-white hover:bg-white/[0.08] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-9 z-40 w-44 surface-elevated shadow-overlay py-1.5 animate-scaleIn"
        >
          {visible.map((item, i) => (
            <button
              key={item.label}
              ref={(el) => (itemRefs.current[i] = el)}
              role="menuitem"
              disabled={item.disabled}
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                setOpen(false);
                item.onSelect();
              }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-[12px] text-left transition outline-none focus-visible:bg-white/[0.08] disabled:opacity-40 disabled:cursor-not-allowed ${
                item.danger
                  ? "text-red-400 hover:bg-red-500/10"
                  : "text-slate-300 hover:bg-white/[0.06] hover:text-white"
              }`}
            >
              {item.icon && <item.icon className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />}
              <span className="truncate">{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}