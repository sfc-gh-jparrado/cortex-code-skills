"use client"
import { useMemo, useState } from "react"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme, CANAL_COLORS, catColor } from "@/lib/theme"
import { formatCOP, formatPct } from "@/lib/format"
import type { CanalPunto } from "@/lib/types"

interface Props {
  data: CanalPunto[]
  accent?: string
}

export function ChannelStackBar({ data, accent = theme.primary }: Props) {
  const HEIGHT = 150
  const { ref, width } = useChartSize(HEIGHT)
  const [hover, setHover] = useState<{ x: number; y: number; d: CanalPunto } | null>(null)

  const segments = useMemo(() => {
    if (!data.length || width === 0) return []
    const total = data.reduce((s, d) => s + d.share, 0) || 100
    let xOffset = 0
    return data.map((d, i) => {
      const w = (d.share / total) * width
      const seg = { d, x: xOffset, w, color: CANAL_COLORS[d.canal] ?? catColor(i), i }
      xOffset += w
      return seg
    })
  }, [data, width])

  if (!data.length) {
    return (
      <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
        <div className="absolute inset-0 grid place-items-center text-sm text-[var(--muted-foreground)]">Sin datos</div>
      </div>
    )
  }

  const barH = 34
  const barY = 12

  return (
    <div ref={ref} className="relative w-full" style={{ height: HEIGHT }}>
      {width > 0 && (
        <>
          <svg width={width} height={barY + barH + 8} role="img" aria-label="Canales composición">
            <defs>
              <clipPath id="bar-clip">
                <rect x={0} y={barY} width={width} height={barH} rx={8} />
              </clipPath>
            </defs>
            <g clipPath="url(#bar-clip)">
              {segments.map((seg, i) => (
                <motion.rect
                  key={seg.d.canal}
                  x={seg.x}
                  y={barY}
                  height={barH}
                  fill={hover?.d.canal === seg.d.canal ? seg.color : seg.color}
                  opacity={hover && hover.d.canal !== seg.d.canal ? 0.55 : 1}
                  initial={{ width: 0 }}
                  animate={{ width: seg.w }}
                  transition={{ delay: i * 0.08, duration: 0.5, ease: "easeOut" }}
                  onMouseMove={(e) => {
                    const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
                    setHover({ x: e.clientX - rect.left, y: e.clientY - rect.top, d: seg.d })
                  }}
                  onMouseLeave={() => setHover(null)}
                  style={{ cursor: "pointer" }}
                />
              ))}
              {/* Labels inside segments */}
              {segments.map((seg) =>
                seg.w > 44 ? (
                  <text
                    key={`lbl-${seg.d.canal}`}
                    x={seg.x + seg.w / 2}
                    y={barY + barH / 2 + 4}
                    fill={theme.text}
                    fontSize={11}
                    fontWeight={600}
                    textAnchor="middle"
                    pointerEvents="none"
                  >
                    {formatPct(seg.d.share, 0)}
                  </text>
                ) : null
              )}
            </g>
          </svg>

          {/* Legend below bar */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 px-1">
            {segments.map((seg) => (
              <div key={seg.d.canal} className="flex items-center gap-1.5 text-[11px]">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ background: seg.color }} />
                <span className="text-[var(--muted-foreground)]">{seg.d.canal}</span>
                <span style={{ color: theme.text, fontWeight: 500 }}>{formatPct(seg.d.share)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {hover && (
        <div
          className="pointer-events-none absolute z-20 panel px-3 py-2 text-xs"
          style={{ left: Math.min(hover.x + 12, width - 170), top: hover.y + 20 }}
        >
          <div className="font-semibold" style={{ color: CANAL_COLORS[hover.d.canal] ?? accent }}>{hover.d.canal}</div>
          <div className="text-[var(--muted-foreground)] mt-1">{formatPct(hover.d.share)}</div>
          <div className="text-[var(--muted-foreground)]">{formatCOP(hover.d.monto)}</div>
        </div>
      )}
    </div>
  )
}
