// Design tokens for the ACH Benchmarking app — a premium dark fintech palette.
// Charts and components import from here so the look stays cohesive.

export const theme = {
  bg: "#0A0E1A",
  bgPanel: "#121A2E",
  bgPanelSoft: "#0F1626",
  border: "#23304D",
  borderSoft: "#1A2540",
  text: "#EAF0FF",
  textMuted: "#8FA0C2",
  textFaint: "#5B6B8C",

  // ACH brand-inspired accents
  primary: "#2E6BFF", // ACH blue
  primarySoft: "#1B4DCC",
  cyan: "#22D3EE",
  green: "#16C784", // positivo
  greenSoft: "#0E9E68",
  amber: "#F5A623",
  red: "#FF5670", // negativo
  violet: "#A78BFA",
  pink: "#F472B6",
  teal: "#2DD4BF",
} as const

// Per-merchant signature color (used as the "you" accent across charts).
export const MERCHANT_COLORS: Record<number, string> = {
  1: "#22D3EE", // ModaViva — cyan
  2: "#2E6BFF", // TecnoMarket — blue
  3: "#A78BFA", // Tecnología DPrimera — violet
}
export function merchantColor(id: number): string {
  return MERCHANT_COLORS[id] ?? theme.primary
}

// Categorical palette for channels / families / generic series.
export const CATEGORICAL = [
  "#2E6BFF",
  "#22D3EE",
  "#16C784",
  "#F5A623",
  "#A78BFA",
  "#F472B6",
  "#2DD4BF",
  "#FF8A5B",
]

// Fixed channel colors (consistent across all charts).
export const CANAL_COLORS: Record<string, string> = {
  PSE: "#2E6BFF",
  "Bre-B": "#22D3EE",
  "Tarjeta Crédito": "#16C784",
  "Tarjeta Débito": "#2DD4BF",
  QR: "#F5A623",
  "TESO PSE Empresarial": "#A78BFA",
}

// Sequential ramp for the choropleth (low -> high).
export const CHORO_RAMP = ["#0F1B3A", "#16336E", "#1E54B8", "#2E6BFF", "#22D3EE", "#7BE8FF"]

export function catColor(i: number): string {
  return CATEGORICAL[i % CATEGORICAL.length]
}
