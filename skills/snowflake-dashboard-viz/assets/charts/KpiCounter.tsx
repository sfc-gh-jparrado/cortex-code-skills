"use client"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { motion } from "framer-motion"
import { formatCOP, formatCOPFull, formatNumber, formatNumberShort, formatPct, formatDelta } from "@/lib/format"
import { theme } from "@/lib/theme"
import { TrendingUp, TrendingDown } from "lucide-react"

type Fmt = "cop" | "copfull" | "num" | "numshort" | "pct"

interface Props {
  label: string
  value: number
  format: Fmt
  delta?: number
  sublabel?: string
  icon?: ReactNode
  accent?: string
}

function fmt(v: number, f: Fmt): string {
  switch (f) {
    case "cop": return formatCOP(v)
    case "copfull": return formatCOPFull(v)
    case "num": return formatNumber(v)
    case "numshort": return formatNumberShort(v)
    case "pct": return formatPct(v)
  }
}

/** KPI tile with an animated count-up and an optional MoM delta chip. */
export function KpiCounter({ label, value, format, delta, sublabel, icon, accent = theme.primary }: Props) {
  const [display, setDisplay] = useState(0)
  const raf = useRef<number | null>(null)

  useEffect(() => {
    const start = performance.now()
    const dur = 900
    const from = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(from + (value - from) * eased)
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [value])

  const deltaUp = (delta ?? 0) >= 0
  return (
    <motion.div
      className="panel panel-hover p-4 relative overflow-hidden"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="absolute -right-6 -top-6 w-20 h-20 rounded-full opacity-20 blur-2xl" style={{ background: accent }} />
      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
        {icon && <span style={{ color: accent }}>{icon}</span>}
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight tabular-nums" style={{ color: theme.text }}>
        {fmt(display, format)}
      </div>
      <div className="mt-1 flex items-center gap-2">
        {delta != null && (
          <span className="chip" style={{ color: deltaUp ? theme.green : theme.red, borderColor: (deltaUp ? theme.green : theme.red) + "55" }}>
            {deltaUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {formatDelta(delta)}
          </span>
        )}
        {sublabel && <span className="text-[11px] text-[var(--muted-foreground)]">{sublabel}</span>}
      </div>
    </motion.div>
  )
}
