"use client"

// Dark-themed Vega-Lite renderer for Cortex Agent `data_to_chart` specs.
// Auto-adapts to its container width, so it fits any chat panel size.
// Pairs with the DATA_AGENT_RUN route, which returns charts[] (parsed chart_spec objects).

import { useEffect, useState } from "react"
import { VegaLite } from "react-vega"

const DARK_CONFIG = {
  background: "transparent",
  font: "ui-sans-serif, system-ui, sans-serif",
  title: { color: "#eaf1ff", fontSize: 13 },
  axis: {
    labelColor: "#9fb2d4", titleColor: "#9fb2d4", gridColor: "rgba(148,163,184,0.14)",
    domainColor: "rgba(148,163,184,0.3)", tickColor: "rgba(148,163,184,0.3)", labelFontSize: 10, titleFontSize: 11,
  },
  legend: { labelColor: "#9fb2d4", titleColor: "#eaf1ff", labelFontSize: 10 },
  view: { stroke: "transparent" },
  range: { category: ["#22d3ee", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa", "#fb923c"] },
  mark: { color: "#22d3ee" },
}

export function AgentVega({ spec }: { spec: Record<string, any> }) {
  // Mount guard: react-vega touches the DOM, so skip the SSR pass.
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  if (!mounted) return <div className="skeleton" style={{ height: 200, marginTop: 8 }} />

  const merged: any = {
    ...spec,
    width: "container", // adapts to panel width (resizable chat)
    autosize: { type: "fit", contains: "padding", resize: true },
    config: { ...DARK_CONFIG, ...(spec.config ?? {}) },
    background: "transparent",
  }
  if (!merged.height) merged.height = 220

  return (
    <div style={{ width: "100%", marginTop: 8 }}>
      <VegaLite spec={merged} actions={false} renderer="svg" style={{ width: "100%" }} />
    </div>
  )
}
