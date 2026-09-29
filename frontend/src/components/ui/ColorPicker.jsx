import { useRef } from "react";
import { Check, Pipette } from "lucide-react";
import {
  ACCENT_PRESETS,
  DEFAULT_WIDGET_ACCENT,
  normalizeHex,
  readableTextOn,
} from "@/components/ui/colorUtils";

/* ============================================================
   COLOR PICKER
   Preset swatches + native custom color input + hex field.
   Controlled: `value` is a hex string (e.g. "#00D4FF").
   `defaultValue` renders a "Default" swatch that resets.
   ============================================================ */

export function ColorPicker({
  value,
  onChange,
  presets = ACCENT_PRESETS,
  defaultValue = DEFAULT_WIDGET_ACCENT,
  className = "",
}) {
  const colorRef = useRef(null);

  const current = normalizeHex(value) || defaultValue;
  const isDefault = current.toUpperCase() === normalizeHex(defaultValue)?.toUpperCase();

  const commitHex = (raw) => {
    const normalised = normalizeHex(raw);
    if (normalised) onChange(normalised);
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Swatches: Default + presets */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Default swatch */}
        <button
          type="button"
          onClick={() => onChange(defaultValue)}
          title="Default brand colour"
          aria-label="Use default colour"
          aria-pressed={isDefault}
          className={`relative h-8 w-8 rounded-[10px] grid place-items-center border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF] ${
            isDefault ? "border-[#00D4FF]" : "border-white/[0.15] hover:border-white/[0.30]"
          }`}
          style={{ backgroundColor: defaultValue }}
        >
          {isDefault && <Check className="h-4 w-4" style={{ color: readableTextOn(defaultValue) }} />}
        </button>

        <span className="h-5 w-px bg-white/[0.10]" aria-hidden="true" />

        {presets
          .filter((c) => c.toUpperCase() !== normalizeHex(defaultValue)?.toUpperCase())
          .map((color) => {
            const active = current.toUpperCase() === color.toUpperCase();
            return (
              <button
                key={color}
                type="button"
                onClick={() => onChange(color)}
                title={color}
                aria-label={`Select colour ${color}`}
                aria-pressed={active}
                className={`h-8 w-8 rounded-[10px] grid place-items-center border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF] ${
                  active ? "border-white scale-105" : "border-white/[0.15] hover:border-white/[0.30]"
                }`}
                style={{ backgroundColor: color }}
              >
                {active && <Check className="h-4 w-4" style={{ color: readableTextOn(color) }} />}
              </button>
            );
          })}
      </div>

      {/* Custom picker + hex input */}
      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={() => colorRef.current?.click()}
          title="Pick a custom colour"
          aria-label="Pick a custom colour"
          className="h-9 w-9 rounded-[10px] grid place-items-center border border-white/[0.15] hover:border-white/[0.30] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
          style={{ backgroundColor: current }}
        >
          <Pipette className="h-3.5 w-3.5" style={{ color: readableTextOn(current) }} />
        </button>

        <input
          ref={colorRef}
          type="color"
          value={current}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
        />

        <div className="flex items-center gap-1.5">
          <span className="text-meta text-slate-400">Hex</span>
          <input
            /* Remounting on external value changes keeps this uncontrolled
               field in sync without a setState-in-effect. */
            key={current}
            type="text"
            defaultValue={current}
            onBlur={(e) => commitHex(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commitHex(e.target.value);
              }
            }}
            spellCheck={false}
            placeholder="#00D4FF"
            aria-label="Accent colour hex value"
            className="w-24 h-9 px-2.5 bg-surface border border-white/[0.08] rounded-[10px] text-[12px] text-white font-mono uppercase placeholder:text-slate-500 outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] transition"
          />
        </div>

        {!isDefault && (
          <button
            type="button"
            onClick={() => onChange(defaultValue)}
            className="text-[11px] font-semibold text-slate-400 hover:text-[#00D4FF] transition focus-visible:outline-none focus-visible:underline"
          >
            Reset to default
          </button>
        )}
      </div>
    </div>
  );
}