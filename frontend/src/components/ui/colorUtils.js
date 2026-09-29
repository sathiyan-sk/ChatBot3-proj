/* ============================================================
   COLOUR UTILITIES
   Pure helpers + constants shared by the colour picker and any
   consumer (kept out of the component file so it only exports
   components, per fast-refresh best practice).
   ============================================================ */

export const DEFAULT_WIDGET_ACCENT = "#00D4FF";

export const ACCENT_PRESETS = [
  "#00D4FF", // brand cyan (default)
  "#2563EB", // blue
  "#10B981", // emerald
  "#F59E0B", // amber
  "#EF4444", // red
  "#A855F7", // violet
  "#EC4899", // pink
  "#84CC16", // lime
];

/** Normalise loose user input into a valid #rrggbb string, or null. */
export function normalizeHex(input) {
  if (!input) return null;
  let hex = String(input).trim().replace(/^#/, "");
  if (/^[0-9a-fA-F]{3}$/.test(hex)) {
    hex = hex
      .split("")
      .map((c) => c + c)
      .join("");
  }
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return null;
  return `#${hex.toUpperCase()}`;
}

/** Pick black/white text for best contrast against a hex background. */
export function readableTextOn(hex) {
  const safe = normalizeHex(hex) || "#000000";
  const r = parseInt(safe.slice(1, 3), 16) / 255;
  const g = parseInt(safe.slice(3, 5), 16) / 255;
  const b = parseInt(safe.slice(5, 7), 16) / 255;
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  return L > 0.55 ? "#040914" : "#FFFFFF";
}