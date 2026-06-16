"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"
import { formatCOP, formatPct, formatNumber } from "@/lib/format"
import type { PeerPunto } from "@/lib/types"

interface Props {
  data: PeerPunto[]
  accent?: string
}

export function BubbleScatter({ data, accent = theme.primary }: Props) {
  const HEIGHT = 340
  const { ref, width } = useChartSize(HEIGHT)
  const [hover, setHover] = useState<{ x: number; y: number; d: PeerPunto } | null>(null)

  const margin = { top: 20, right: 24, bottom: 44, left: 70 }

  const { xScale, yScale, rScale, peers, self } = useMemo(() => {
    if (!data.length || width === 0)
      return { xScale: null, yScale: null, rScale: null, peers: [] as PeerPunto[], self: null as PeerPunto | null }

    const innerW = width - margin.left - margin.right
    const innerH = HEIGHT - margin.top - margin.bottom

    const xScale = d3.scaleLinear()
      .domain([0, d3.max(data, (d) => d.ticket)! * 1.1])
      .range([0, innerW])
      .nice()

    const yScale = d3.scaleLinear()
      .domain([0, d3.max(data, (d) => d.monto)! * 1.1])
      .range([innerH, 0])
      .nice()

    const rScale = d3.scaleSqrt()
      .domain([0, d3.max(data, (d) => d.num_tx) ?? 1])
      .range([5, 34])

    const peers = data.filter((d) => !d.es_self)
    const self = data.find((d) => d.es_self) ?? null

    return { xScale, yScale, rScale, peers, self }
  }, [data, width])

  if (!data.length) {
    return (
      <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
        <div className="absolute inset-0 grid place-items-center text-sm text-[var(--muted-foreground)]">Sin datos</div>
      </div>
    )
  }

  const innerW = width - margin.left - margin.right
  const innerH = HEIGHT - margin.top - margin.bottom

  return (
    <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
      {width > 0 && xScale && yScale && rScale && (
        <svg width={width} height={HEIGHT} role="img" aria-label="Scatter peers">
          <defs>
            <filter id="scatter-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          <g transform={`translate(${margin.left},${margin.top})`}>
            {/* Grid */}
            {yScale.ticks(5).map((t) => (
              <line key={`gy-${t}`} x1={0} x2={innerW} y1={yScale(t)} y2={yScale(t)} stroke="#1a2540" strokeDasharray="2,3" />
            ))}
            {xScale.ticks(5).map((t) => (
              <line key={`gx-${t}`} x1={xScale(t)} x2={xScale(t)} y1={0} y2={innerH} stroke="#1a2540" strokeDasharray="2,3" />
            ))}

            {/* X axis */}
            {xScale.ticks(5).map((t) => (
              <text key={`xl-${t}`} x={xScale(t)} y={innerH + 16} fill={theme.textMuted} fontSize={10} textAnchor="middle">{formatCOP(t)}</text>
            ))}
            <text x={innerW / 2} y={innerH + 36} fill={theme.textMuted} fontSize={11} textAnchor="middle">Ticket promedio</text>

            {/* Y axis */}
            {yScale.ticks(5).map((t) => (
              <text key={`yl-${t}`} x={-10} y={yScale(t) + 4} fill={theme.textMuted} fontSize={10} textAnchor="end">{formatCOP(t)}</text>
            ))}
            <text x={-margin.left + 14} y={innerH / 2} fill={theme.textMuted} fontSize={11} textAnchor="middle" transform={`rotate(-90, ${-margin.left + 14}, ${innerH / 2})`}>Volumen anual</text>

            {/* Peer bubbles */}
            {peers.map((p, i) => (
              <motion.circle
                key={p.comercio_id}
                cx={xScale(p.ticket)}
                cy={yScale(p.monto)}
                r={rScale(p.num_tx)}
                fill={theme.teal}
                fillOpacity={hover?.d.comercio_id === p.comercio_id ? 0.8 : 0.45}
                stroke={hover?.d.comercio_id === p.comercio_id ? accent : theme.teal}
                strokeWidth={hover?.d.comercio_id === p.comercio_id ? 1.5 : 0.8}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: i * 0.04, type: "spring", stiffness: 180, damping: 14 }}
                style={{ cursor: "pointer", transformOrigin: `${xScale(p.ticket)}px ${yScale(p.monto)}px` }}
                onMouseMove={(e) => {
                  const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                  setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, d: p })
                }}
                onMouseLeave={() => setHover(null)}
              />
            ))}

            {/* Self bubble — rendered last (on top) */}
            {self && (
              <g>
                <motion.circle
                  cx={xScale(self.ticket)}
                  cy={yScale(self.monto)}
                  r={rScale(self.num_tx)}
                  fill={accent}
                  fillOpacity={0.85}
                  stroke="#ffffff"
                  strokeWidth={2}
                  filter="url(#scatter-glow)"
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.5, type: "spring", stiffness: 160, damping: 12 }}
                  style={{ transformOrigin: `${xScale(self.ticket)}px ${yScale(self.monto)}px`, cursor: "pointer" }}
                  onMouseMove={(e) => {
                    const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                    setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, d: self })
                  }}
                  onMouseLeave={() => setHover(null)}
                />
                <text
                  x={xScale(self.ticket) + rScale(self.num_tx) + 6}
                  y={yScale(self.monto) + 4}
                  fill={accent}
                  fontSize={12}
                  fontWeight={700}
                  pointerEvents="none"
                >Tú</text>
              </g>
            )}
          </g>
        </svg>
      )}

      {hover && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{ left: Math.min(hover.x + 14, width - 200), top: Math.min(hover.y + 14, HEIGHT - 90) }}
        >
          <div className="font-semibold" style={{ color: hover.d.es_self ? accent : theme.teal }}>{hover.d.alias}</div>
          <div className="text-[var(--muted-foreground)] mt-1">Ticket: {formatCOP(hover.d.ticket)}</div>
          <div className="text-[var(--muted-foreground)]">Volumen: {formatCOP(hover.d.monto)}</div>
          <div className="text-[var(--muted-foreground)]">Aprobación: {formatPct(hover.d.tasa_aprob)}</div>
          <div className="text-[var(--muted-foreground)]">Transacciones: {formatNumber(hover.d.num_tx)}</div>
        </div>
      )}
    </div>
  )
}
