"use client"
import type React from "react"

interface ChartFrameProps {
  title: string
  subtitle?: string
  right?: React.ReactNode
  className?: string
  bodyClassName?: string
  children: React.ReactNode
}

/** Consistent panel wrapper for every chart: title, optional subtitle + right slot, body. */
export function ChartFrame({ title, subtitle, right, className, bodyClassName, children }: ChartFrameProps) {
  return (
    <section className={`panel panel-hover p-4 sm:p-5 flex flex-col ${className ?? ""}`}>
      <header className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-[var(--foreground)]">{title}</h3>
          {subtitle && <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{subtitle}</p>}
        </div>
        {right && <div className="shrink-0">{right}</div>}
      </header>
      <div className={`flex-1 min-h-0 ${bodyClassName ?? ""}`}>{children}</div>
    </section>
  )
}
