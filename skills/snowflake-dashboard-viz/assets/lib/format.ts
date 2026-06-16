// Colombian-locale formatting helpers (es-CO: "." thousands, "," decimals).

const nf0 = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Abbreviated COP: $1,2 B / $845 M / $12,7 mil M (mil millones). */
export function formatCOP(value: number): string {
  if (value == null || isNaN(value)) return "—"
  const abs = Math.abs(value)
  if (abs >= 1e12) return `$${nf1.format(value / 1e12)} B`
  if (abs >= 1e9) return `$${nf1.format(value / 1e9)} mil M`
  if (abs >= 1e6) return `$${nf0.format(value / 1e6)} M`
  if (abs >= 1e3) return `$${nf0.format(value / 1e3)} mil`
  return `$${nf0.format(value)}`
}

/** Full COP with thousands separators: $613.745 */
export function formatCOPFull(value: number): string {
  if (value == null || isNaN(value)) return "—"
  return `$${nf0.format(value)}`
}

export function formatNumber(value: number): string {
  if (value == null || isNaN(value)) return "—"
  return nf0.format(value)
}

/** Compact integer: 24.462 -> 24,5 mil ; 1.250.000 -> 1,3 M */
export function formatNumberShort(value: number): string {
  if (value == null || isNaN(value)) return "—"
  const abs = Math.abs(value)
  if (abs >= 1e6) return `${nf1.format(value / 1e6)} M`
  if (abs >= 1e3) return `${nf1.format(value / 1e3)} mil`
  return nf0.format(value)
}

/** Percent: value is already a percentage (94.1 -> "94,1%"). */
export function formatPct(value: number, decimals = 1): string {
  if (value == null || isNaN(value)) return "—"
  const n = decimals === 0 ? nf0 : nf1
  return `${n.format(value)}%`
}

/** Signed percent for deltas: +3,2% / -1,4% */
export function formatDelta(value: number): string {
  if (value == null || isNaN(value)) return "—"
  const sign = value > 0 ? "+" : ""
  return `${sign}${nf1.format(value)}%`
}

/** "2025-11" -> "Nov 25" */
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
export function formatMesCorto(ym: string): string {
  if (!ym) return ""
  const [y, m] = ym.split("-")
  const mi = parseInt(m, 10) - 1
  if (mi < 0 || mi > 11) return ym
  return `${MESES[mi]} ${y.slice(2)}`
}
