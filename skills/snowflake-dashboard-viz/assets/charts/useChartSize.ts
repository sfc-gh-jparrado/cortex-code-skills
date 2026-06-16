"use client"
import { useEffect, useRef, useState } from "react"

/**
 * Observe a container's size. Returns a ref to attach and the measured size.
 * Use for responsive D3 SVGs: const { ref, width, height } = useChartSize()
 */
export function useChartSize(initialHeight = 320) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [size, setSize] = useState({ width: 0, height: initialHeight })

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const w = Math.floor(e.contentRect.width)
        const h = Math.floor(e.contentRect.height) || initialHeight
        setSize((s) => (s.width === w && s.height === h ? s : { width: w, height: h }))
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [initialHeight])

  return { ref, width: size.width, height: size.height }
}
