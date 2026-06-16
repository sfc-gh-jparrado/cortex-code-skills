"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme, CATEGORICAL } from "@/lib/theme"
import { formatNumberShort } from "@/lib/format"
import type { AgentChartSpec } from "@/lib/types"

interface Props { spec: AgentChartSpec; accent?: string }

/** Lightweight renderer for the agent's data_to_chart output (bar / line / donut). */
export function AgentChart({ spec, accent = theme.primary }: Props) {
  const { ref, width } = useChartSize(260)
  const height = 260
  const [hover, setHover] = useState<{ x: number; y: number; label: string; val: number } | null>(null)

  const { rows } = useMemo(() => {
    const values = spec.values ?? []
    const sample = values[0] ?? {}
    const keys = Object.keys(sample)
    const isNum = (k: string) => values.slice(0, 5).every((v) => v[k] !== "" && v[k] != null && !isNaN(Number(v[k])))
    const numKeys = keys.filter(isNum)
    const strKeys = keys.filter((k) => !numKeys.includes(k))
    // Category = a string field (fallback to spec.x); Value = a numeric field (fallback to spec.y).
    const labelField = strKeys[0] ?? (spec.x && keys.includes(spec.x) ? spec.x : keys[0])
    const valField = numKeys[0] ?? (spec.y && keys.includes(spec.y) ? spec.y : keys[1] ?? keys[0])
    const rows = values
      .map((v) => ({ label: String(v[labelField] ?? ""), val: Number(v[valField]) }))
      .filter((r) => !isNaN(r.val))
    return { rows }
  }, [spec])

  const mark = (spec.mark || "bar").toLowerCase()
  if (!rows.length) return <div className="h-full grid place-items-center text-xs text-[var(--muted-foreground)]">Sin datos para graficar</div>

  const m = { top: 12, right: 14, bottom: 56, left: 56 }
  const iw = Math.max(10, width - m.left - m.right)
  const ih = height - m.top - m.bottom

  const isDonut = mark === "arc" || mark === "pie"

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && !isDonut && (() => {
        const x = d3.scaleBand<string>().domain(rows.map((r) => r.label)).range([0, iw]).padding(0.25)
        const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.val) ?? 1]).nice().range([ih, 0])
        const line = d3.line<{ label: string; val: number }>().x((r) => (x(r.label) ?? 0) + x.bandwidth() / 2).y((r) => y(r.val)).curve(d3.curveMonotoneX)
        return (
          <svg width={width} height={height}>
            <g transform={`translate(${m.left},${m.top})`}>
              {y.ticks(5).map((t) => (
                <g key={t} transform={`translate(0,${y(t)})`}>
                  <line x1={0} x2={iw} stroke="#1a2540" />
                  <text x={-8} dy="0.32em" textAnchor="end" fill={theme.textMuted} fontSize={10}>{formatNumberShort(t)}</text>
                </g>
              ))}
              {rows.map((r, i) => {
                const cx = (x(r.label) ?? 0)
                return (
                  <g key={r.label}
                     onMouseMove={(e) => { const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, label: r.label, val: r.val }) }}
                     onMouseLeave={() => setHover(null)}>
                    {mark === "line" ? null : (
                      <motion.rect x={cx} width={x.bandwidth()} fill={accent} rx={4}
                        initial={{ y: ih, height: 0 }} animate={{ y: y(r.val), height: ih - y(r.val) }}
                        transition={{ delay: i * 0.03, duration: 0.5 }} />
                    )}
                    <rect x={cx} y={0} width={x.bandwidth()} height={ih} fill="transparent" />
                    <text x={cx + x.bandwidth() / 2} y={ih + 14} textAnchor="middle" fill={theme.textMuted} fontSize={9} transform={rows.length > 6 ? `rotate(35,${cx + x.bandwidth() / 2},${ih + 14})` : undefined}>
                      {r.label.length > 12 ? r.label.slice(0, 11) + "…" : r.label}
                    </text>
                  </g>
                )
              })}
              {mark === "line" && (
                <motion.path d={line(rows) ?? ""} fill="none" stroke={accent} strokeWidth={2.5}
                  initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8 }} />
              )}
              {mark === "line" && rows.map((r) => (
                <circle key={r.label} cx={(x(r.label) ?? 0) + x.bandwidth() / 2} cy={y(r.val)} r={3} fill={accent} />
              ))}
            </g>
          </svg>
        )
      })()}

      {width > 0 && isDonut && (() => {
        const radius = Math.min(iw, ih) / 2
        const cx = width / 2, cy = height / 2 - 10
        const pie = d3.pie<{ label: string; val: number }>().value((r) => r.val).sort(null)
        const arc = d3.arc<d3.PieArcDatum<{ label: string; val: number }>>().innerRadius(radius * 0.6).outerRadius(radius)
        const arcs = pie(rows)
        return (
          <svg width={width} height={height}>
            <g transform={`translate(${cx},${cy})`}>
              {arcs.map((a, i) => (
                <motion.path key={a.data.label} d={arc(a) ?? ""} fill={CATEGORICAL[i % CATEGORICAL.length]}
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }}
                  onMouseMove={(e) => { const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect(); setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, label: a.data.label, val: a.data.val }) }}
                  onMouseLeave={() => setHover(null)} />
              ))}
            </g>
          </svg>
        )
      })()}

      {hover && (
        <div className="pointer-events-none absolute z-20 panel px-2.5 py-1.5 text-xs" style={{ left: Math.min(hover.x + 10, width - 130), top: hover.y + 10 }}>
          <div className="font-semibold">{hover.label}</div>
          <div className="text-[var(--muted-foreground)]">{formatNumberShort(hover.val)}</div>
        </div>
      )}
    </div>
  )
}
