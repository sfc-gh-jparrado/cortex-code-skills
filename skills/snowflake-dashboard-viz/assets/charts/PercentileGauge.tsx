"use client"
import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { useChartSize } from "./useChartSize"
import { theme } from "@/lib/theme"

interface Props {
  value: number
  label: string
  sublabel?: string
  accent?: string
}

export function PercentileGauge({ value, label, sublabel, accent = theme.primary }: Props) {
  const height = 220
  const { ref, width } = useChartSize(height)
  const [displayVal, setDisplayVal] = useState(0)
  const raf = useRef<number | null>(null)

  useEffect(() => {
    const start = performance.now()
    const dur = 1100
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplayVal(eased * value)
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [value])

  const cx = width / 2
  const cy = height / 2 + 12
  const r = Math.min(cx, cy) - 30
  const startAngle = -135
  const totalAngle = 270
  const strokeW = 14

  const toRad = (deg: number) => (deg * Math.PI) / 180
  const polarToCart = (angleDeg: number, radius: number) => ({
    x: cx + radius * Math.cos(toRad(angleDeg)),
    y: cy + radius * Math.sin(toRad(angleDeg)),
  })

  const describeArc = (startDeg: number, endDeg: number, arcR: number) => {
    const s = polarToCart(startDeg, arcR)
    const e = polarToCart(endDeg, arcR)
    const sweep = endDeg - startDeg
    const largeArc = sweep > 180 ? 1 : 0
    return `M ${s.x} ${s.y} A ${arcR} ${arcR} 0 ${largeArc} 1 ${e.x} ${e.y}`
  }

  const valAngle = startAngle + (Math.min(displayVal, 100) / 100) * totalAngle
  const ticks = [0, 25, 50, 75, 100]

  if (value == null || isNaN(value)) {
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
          <defs>
            <linearGradient id="gauge-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={accent} stopOpacity={0.6} />
              <stop offset="100%" stopColor={accent} stopOpacity={1} />
            </linearGradient>
          </defs>

          {/* Background track */}
          <path
            d={describeArc(startAngle, startAngle + totalAngle, r)}
            fill="none"
            stroke={theme.border}
            strokeWidth={strokeW}
            strokeLinecap="round"
          />

          {/* Value arc */}
          {displayVal > 0.5 && (
            <motion.path
              d={describeArc(startAngle, valAngle, r)}
              fill="none"
              stroke="url(#gauge-grad)"
              strokeWidth={strokeW}
              strokeLinecap="round"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          )}

          {/* Tick marks */}
          {ticks.map((t) => {
            const angle = startAngle + (t / 100) * totalAngle
            const inner = polarToCart(angle, r - strokeW / 2 - 3)
            const outer = polarToCart(angle, r - strokeW / 2 - 9)
            return (
              <g key={t}>
                <line x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} stroke={theme.textMuted} strokeWidth={1.2} />
                <text
                  x={polarToCart(angle, r - strokeW / 2 - 16).x}
                  y={polarToCart(angle, r - strokeW / 2 - 16).y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="var(--muted-foreground)"
                  fontSize={9}
                >
                  {t}
                </text>
              </g>
            )
          })}

          {/* Center big number */}
          <text x={cx} y={cy - 8} textAnchor="middle" dominantBaseline="middle" fill={theme.text} fontSize={36} fontWeight="bold" className="tabular-nums">
            {Math.round(displayVal)}
          </text>
          <text x={cx} y={cy + 16} textAnchor="middle" dominantBaseline="middle" fill="var(--muted-foreground)" fontSize={11}>
            percentil
          </text>

          {/* Label below */}
          <text x={cx} y={cy + 40} textAnchor="middle" dominantBaseline="middle" fill={theme.text} fontSize={13} fontWeight="600">
            {label}
          </text>
          {sublabel && (
            <text x={cx} y={cy + 56} textAnchor="middle" dominantBaseline="middle" fill="var(--muted-foreground)" fontSize={11}>
              {sublabel}
            </text>
          )}
        </svg>
      )}
    </div>
  )
}
