"use client"
import { useMemo, useState } from "react"
import * as d3 from "d3"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme, catColor } from "@/lib/theme"
import { formatCOP, formatPct } from "@/lib/format"
import type { FamiliaPunto } from "@/lib/types"

interface Props {
  data: FamiliaPunto[]
  accent?: string
}

export function Treemap({ data, accent = theme.primary }: Props) {
  const HEIGHT = 330
  const { ref, width } = useChartSize(HEIGHT)
  const [hover, setHover] = useState<{ x: number; y: number; idx: number } | null>(null)

  const cells = useMemo(() => {
    if (!data.length || width === 0) return []
    const root = d3
      .hierarchy({ children: data } as any)
      .sum((d: any) => d.monto ?? 0)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))

    d3.treemap<any>().size([width, HEIGHT]).padding(2).round(true)(root)

    return (root.leaves() as any[]).map((leaf, i) => {
      const d = leaf.data as FamiliaPunto
      const x0: number = leaf.x0
      const y0: number = leaf.y0
      const x1: number = leaf.x1
      const y1: number = leaf.y1
      const w = x1 - x0
      const h = y1 - y0
      return { d, x0, y0, w, h, color: catColor(i), i }
    })
  }, [data, width])

  if (!data.length) {
    return (
      <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
        <div className="absolute inset-0 grid place-items-center text-sm text-[var(--muted-foreground)]">Sin datos</div>
      </div>
    )
  }

  const hovered = hover != null ? cells[hover.idx] : null

  return (
    <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
      {width > 0 && (
        <svg width={width} height={HEIGHT} role="img" aria-label="Treemap familias">
          {cells.map((c, i) => (
            <motion.g
              key={c.d.familia}
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.04, duration: 0.4, type: "spring", stiffness: 200, damping: 18 }}
              style={{ transformOrigin: `${c.x0 + c.w / 2}px ${c.y0 + c.h / 2}px` }}
            >
              <rect
                x={c.x0}
                y={c.y0}
                width={c.w}
                height={c.h}
                rx={4}
                fill={hover?.idx === i ? d3.color(c.color)!.brighter(0.5).formatHex() : c.color}
                stroke={hover?.idx === i ? accent : "none"}
                strokeWidth={hover?.idx === i ? 1.5 : 0}
                opacity={0.9}
                onMouseMove={(e) => {
                  const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                  setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, idx: i })
                }}
                onMouseLeave={() => setHover(null)}
                style={{ cursor: "pointer" }}
              />
              {/* Label inside cell if big enough */}
              {c.w > 60 && c.h > 40 && (
                <foreignObject x={c.x0 + 6} y={c.y0 + 6} width={c.w - 12} height={c.h - 12} pointerEvents="none">
                  <div style={{ color: theme.text, fontSize: 11, lineHeight: 1.3, overflow: "hidden" }}>
                    <div style={{ fontWeight: 600, marginBottom: 2, whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>{c.d.familia}</div>
                    {c.h > 56 && <div style={{ opacity: 0.8 }}>{formatCOP(c.d.monto)}</div>}
                    {c.h > 72 && <div style={{ opacity: 0.6 }}>{formatPct(c.d.share_comercio)}</div>}
                  </div>
                </foreignObject>
              )}
            </motion.g>
          ))}
        </svg>
      )}

      {hover && hovered && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{ left: Math.min(hover.x + 12, width - 190), top: Math.min(hover.y + 12, HEIGHT - 80) }}
        >
          <div className="font-semibold" style={{ color: hovered.color }}>{hovered.d.familia}</div>
          <div className="text-[var(--muted-foreground)] mt-1">{formatCOP(hovered.d.monto)}</div>
          <div className="text-[var(--muted-foreground)]">Participación {formatPct(hovered.d.share_comercio)}</div>
          <div className="text-[var(--muted-foreground)]">Sector {formatPct(hovered.d.share_sector)}</div>
        </div>
      )}
    </div>
  )
}
