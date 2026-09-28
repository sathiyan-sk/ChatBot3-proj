import { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";
import { Button } from "@/components/ui/Primitives";

/* ============================================================
   OVERLAYS
   Modal with proper header/body/footer zones, plus a styled
   ConfirmDialog that replaces window.confirm().
   Both trap focus, focus the first control on open, restore
   focus to the trigger on close, and lock body scroll.
   ============================================================ */

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * useDialog - Escape to close, focus trap, initial focus and
 * focus restore + body scroll lock while open.
 */
function useDialog(onClose, enabled) {
  const ref = useRef(null);
  const restoreRef = useRef(null);
  // Keep the latest onClose in a ref so the trap effect only re-runs
  // when the dialog opens/closes (re-running on every render would steal
  // focus while the user is typing into a form inside the dialog).
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!enabled) return;

    restoreRef.current = document.activeElement;
    const node = ref.current;

    // Move focus to the first meaningful control inside the dialog.
    const focusables = node ? node.querySelectorAll(FOCUSABLE) : [];
    (focusables[0] || node)?.focus?.();

    const onKey = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !node) return;

      const items = Array.from(node.querySelectorAll(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null
      );
      if (items.length === 0) return;

      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKey, true);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.body.style.overflow = prevOverflow;
      restoreRef.current?.focus?.();
    };
  }, [enabled]);

  return ref;
}

export function Modal({ open, onClose, title, description, children, footer, size = "md" }) {
  const dialogRef = useDialog(onClose, open);

  if (!open) return null;

  const width = size === "lg" ? "max-w-2xl" : size === "sm" ? "max-w-sm" : "max-w-md";

  return (
    <div
      className="fixed inset-0 z-50 bg-[#040914]/80 backdrop-blur-md flex items-center justify-center p-4 animate-fadeIn"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`w-full ${width} surface-elevated shadow-overlay animate-scaleIn flex flex-col max-h-[90vh] overflow-hidden focus:outline-none`}
      >
        <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-white/[0.07]">
          <div className="min-w-0">
            <h3 className="text-card-title text-white">{title}</h3>
            {description && (
              <p className="text-meta text-slate-400 mt-1.5 leading-relaxed">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 -mr-1.5 rounded-[10px] text-slate-500 hover:text-white hover:bg-white/[0.06] transition flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-6 py-5 overflow-y-auto flex-1">{children}</div>

        {footer && (
          <div className="px-6 py-4 border-t border-white/[0.07] flex items-center justify-end gap-2.5 bg-white/[0.01]">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * ConfirmDialog - styled destructive confirmation.
 * Holds its own pending state so it stays open (with a spinner)
 * until the async action resolves.
 */
export function ConfirmDialog({
  open,
  onCancel,
  onConfirm,
  title = "Are you sure?",
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  pending = false,
  tone = "danger",
}) {
  const dialogRef = useDialog(onCancel, open && !pending);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] bg-[#040914]/80 backdrop-blur-md flex items-center justify-center p-4 animate-fadeIn">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="w-full max-w-sm surface-elevated shadow-overlay animate-scaleIn p-6 focus:outline-none"
      >
        <div className="flex items-start gap-3">
          <span
            className={`p-2 rounded-[10px] flex-shrink-0 ${
              tone === "danger"
                ? "bg-red-500/10 border border-red-500/20 text-red-400"
                : "bg-amber-500/10 border border-amber-500/20 text-amber-400"
            }`}
          >
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="text-card-title text-white">{title}</h3>
            {message && <p className="text-meta text-slate-400 mt-2 leading-relaxed">{message}</p>}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2.5 mt-6">
          <Button variant="ghost" onClick={onCancel} disabled={pending}>
            {cancelLabel}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            loading={pending}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}