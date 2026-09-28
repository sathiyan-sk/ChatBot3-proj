import { forwardRef } from "react";

/* ============================================================
   FORM PRIMITIVES
   One definition for inputs, textareas, selects, labels and
   checkbox rows so every admin form shares the same control
   geometry (h-10, rounded-control, focus ring) and type scale.
   ============================================================ */

const CONTROL =
  "w-full h-10 px-3.5 bg-surface border border-white/[0.08] rounded-control " +
  "text-[12px] text-white placeholder:text-slate-500 outline-none " +
  "focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] transition " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

/** Field - label + hint wrapper around any control. */
export function Field({ label, htmlFor, hint, error, required, children, className = "" }) {
  return (
    <div className={className}>
      {label && (
        <label htmlFor={htmlFor} className="block text-meta text-slate-300 mb-1.5">
          {label}
          {required && <span className="text-red-400 ml-0.5">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-[10px] text-red-400 mt-1.5">{error}</p>
      ) : hint ? (
        <p className="text-[10px] text-slate-400 mt-1.5 leading-relaxed">{hint}</p>
      ) : null}
    </div>
  );
}

/** Input - single-line text control. */
export const Input = forwardRef(function Input({ className = "", icon: Icon, ...props }, ref) {
  if (Icon) {
    return (
      <div className="relative">
        <Icon
          className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none"
          aria-hidden="true"
        />
        <input ref={ref} {...props} className={`${CONTROL} pl-10 ${className}`} />
      </div>
    );
  }
  return <input ref={ref} {...props} className={`${CONTROL} ${className}`} />;
});

/** Textarea - multi-line control, matches Input geometry. */
export const Textarea = forwardRef(function Textarea({ className = "", rows = 4, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      {...props}
      className={`${CONTROL} h-auto py-2.5 resize-none leading-relaxed ${className}`}
    />
  );
});

/** Select - native dropdown styled to match inputs, with a custom chevron. */
export const Select = forwardRef(function Select({ className = "", children, ...props }, ref) {
  return (
    <select
      ref={ref}
      {...props}
      className={`${CONTROL} pr-9 cursor-pointer appearance-none bg-no-repeat ${className}`}
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E\")",
        backgroundPosition: "right 0.75rem center",
        backgroundSize: "14px",
      }}
    >
      {children}
    </select>
  );
});

/** CheckboxRow - checkbox + label laid out on one line. */
export function CheckboxRow({ id, checked, onChange, label, disabled = false, className = "" }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="h-4 w-4 rounded border-white/[0.15] bg-surface text-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] focus:ring-offset-0 accent-[#00D4FF] cursor-pointer disabled:opacity-50"
      />
      {label && (
        <label htmlFor={id} className="text-[12px] text-slate-300 cursor-pointer select-none">
          {label}
        </label>
      )}
    </div>
  );
}

/** InsetWell - dark inset container for code blocks / key displays. */
export function InsetWell({ children, className = "" }) {
  return <div className={`surface-inset rounded-control p-3 ${className}`}>{children}</div>;
}