"use client"
import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"
import { formatPct, formatCOP } from "@/lib/format"
import type { FamiliaPunto } from "@/lib/types"

interface Props {
  data: FamiliaPunto[]
  accent?: string
}

export function FamilyCompareBars({ data, accent = theme.primary }: Props) {
  const height = 330
  const { ref, width } = useChartSize(height)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  const sorted = useMemo(
    () => [...data].sort((a, b) => b.share_comercio - a.share_comercio),
    [data]
  )

  const maxVal = useMemo(
    () => Math.max(...sorted.map((d) => Math.max(d.share_comercio, d.share_sector)), 1),
    [sorted]
  )

  const marginLeft = 110
  const marginRight = 60
  const marginTop = 28
  const marginBottom = 20
  const barGroupH = Math.min(42, (height - marginTop - marginBottom) / Math.max(sorted.length, 1))
  const barH = (barGroupH - 6) / 2
  const chartW = width - marginLeft - marginRight

  if (!data || data.length === 0) {
    return (
      <div ref={ref} className="relative w-full" style={{ height }}>
        <div className="absolute inset-0 grid place-items-center text-sm text-[var(--muted-foreground)]">Sin datos</div>
      </div>
    )
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height}>
          {/* Legend */}
          <circle cx={marginLeft} cy={12} r={4} fill={accent} />
          <text x={marginLeft + 8} y={12} dominantBaseline="middle" fill="var(--muted-foreground)" fontSize={10}>Tu comercio</text>
          <circle cx={marginLeft + 90} cy={12} r={4} fill={theme.textMuted} />
          <text x={marginLeft + 98} y={12} dominantBaseline="middle" fill="var(--muted-foreground)" fontSize={10}>Promedio sector</text>

          {sorted.map((d, i) => {
            const y = marginTop + i * barGroupH
            const wComercio = (d.share_comercio / maxVal) * chartW
            const wSector = (d.share_sector / maxVal) * chartW
            const isHovered = hoverIdx === i

            return (
              <g
                key={d.familia}
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Background highlight */}
                {isHovered && (
                  <rect
                    x={0}
                    y={y - 2}
                    width={width}
                    height={barGroupH}
                    fill={accent}
                    opacity={0.05}
                    rx={4}
                  />
                )}

                {/* Label */}
                <text
                  x={marginLeft - 8}
                  y={y + barGroupH / 2}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fill={isHovered ? theme.text : "var(--muted-foreground)"}
                  fontSize={11}
                >
                  {d.familia.length > 14 ? d.familia.slice(0, 13) + "…" : d.familia}
                </text>

                {/* Comercio bar */}
                <motion.rect
                  x={marginLeft}
                  y={y}
                  height={barH}
                  rx={3}
                  fill={accent}
                  initial={{ width: 0 }}
                  animate={{ width: Math.max(wComercio, 2) }}
                  transition={{ duration: 0.6, delay: i * 0.05, ease: "easeOut" }}
                />
                <text
                  x={marginLeft + wComercio + 4}
                  y={y + barH / 2}
                  dominantBaseline="middle"
                  fill={accent}
                  fontSize={10}
                  fontWeight={600}
                >
                  {formatPct(d.share_comercio, 1)}
                </text>

                {/* Sector bar */}
                <motion.rect
                  x={marginLeft}
                  y={y + barH + 3}
                  height={barH}
                  rx={3}
                  fill={theme.textMuted}
                  fillOpacity={0.5}
                  initial={{ width: 0 }}
                  animate={{ width: Math.max(wSector, 2) }}
                  transition={{ duration: 0.6, delay: i * 0.05 + 0.1, ease: "easeOut" }}
                />
                <text
                  x={marginLeft + wSector + 4}
                  y={y + barH + 3 + barH / 2}
                  dominantBaseline="middle"
                  fill={theme.textMuted}
                  fontSize={10}
                >
                  {formatPct(d.share_sector, 1)}
                </text>
              </g>
            )
          })}
        </svg>
      )}

      {/* Tooltip */}
      {hoverIdx != null && sorted[hoverIdx] && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{
            left: Math.min(marginLeft + 60, width - 200),
            top: marginTop + hoverIdx * barGroupH + barGroupH + 4,
          }}
        >
          <div className="font-semibold" style={{ color: accent }}>{sorted[hoverIdx].familia}</div>
          <div className="text-[var(--muted-foreground)]">
            Tú: {formatPct(sorted[hoverIdx].share_comercio)} · Sector: {formatPct(sorted[hoverIdx].share_sector)}
          </div>
          <div>{formatCOP(sorted[hoverIdx].monto)}</div>
        </div>
      )}
    </div>
  )
}
