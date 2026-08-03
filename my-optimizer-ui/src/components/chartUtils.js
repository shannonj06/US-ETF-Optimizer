// Palette + formatting helpers shared by the chart components and the Cash
// Analysis page. Kept separate from charts.jsx so that file only exports
// components (React Fast Refresh requirement).
//
// Colors use the validated categorical palette (dataviz skill, light surface):
// the slot ORDER is the colorblind-safety mechanism — assigned in fixed order,
// never cycled. A 9th+ series folds into "Other" rather than repeating a hue.

export const SERIES_PALETTE = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
];

export const POS_COLOR = "#0c8a61"; // gain (mint-600)
export const NEG_COLOR = "#d9483b"; // loss (danger)

export function seriesColor(i) {
  return SERIES_PALETTE[i % SERIES_PALETTE.length];
}

export function fmtCurrency(v, digits = 2) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtSignedCurrency(v) {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return sign + fmtCurrency(Math.abs(v));
}

export function fmtCompact(v) {
  if (v == null || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}k`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function fmtPct(v, digits = 2) {
  if (v == null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(digits)}%`;
}
