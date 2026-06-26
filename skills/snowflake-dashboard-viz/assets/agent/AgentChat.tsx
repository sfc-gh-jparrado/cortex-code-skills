"use client"

// Floating Cortex Agent chat panel (FAB + draggable window).
// Reusable across Snowflake Apps. Pairs with two API routes (see templates in this folder):
//   GET  /api/agents -> { agents: [{ name, display_name }] }   (SHOW AGENTS)
//   POST /api/agent  { agent, messages } -> { text, citations, chartSpec, tables }  (Cortex Agent REST, stream:false)
// Auth from SPCS: the /api/agent route uses the service OAuth token + account host (see lib/snowflake.ts
// getServiceToken()/getAccountHost()) and calls
//   POST https://<host>/api/v2/databases/{db}/schemas/{schema}/agents/{name}:run
// with headers Authorization: Bearer <token> and X-Snowflake-Authorization-Token-Type: OAUTH.
//
// Props let you rebrand without editing the body. Colors default to Snowflake blue.

import { useState, useRef, useEffect, useCallback, Component, type ReactNode } from "react"
import { Sparkles, Send, X, Minus, Maximize2, GripVertical, MessageSquare, FileText } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { AgentVega } from "./AgentVega"

/** Local error boundary so a markdown/chart render failure degrades gracefully
 *  inside the chat bubble instead of bubbling to the app-level error page. */
class ChatErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode; fallback?: ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch(err: unknown) {
    console.error("[AgentChat] render error", err)
  }
  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <div style={{ fontSize: 12, color: "#8FA0C2" }}>No se pudo mostrar parte de la respuesta.</div>
    }
    return this.props.children
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isValidVegaSpec(spec: any): boolean {
  return !!spec && typeof spec === "object" &&
    (spec.mark || spec.layer || spec.encoding || spec.facet || spec.hconcat || spec.vconcat || spec.spec)
}

type ContentItem = { type: "text"; text: string }
type ApiMessage = { role: "user" | "assistant"; content: ContentItem[] }
type Cita = { title: string; text: string }
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UiMsg = { role: "user" | "assistant"; text: string; citations?: Cita[]; charts?: any[]; suggestions?: string[]; tables?: any[] }
type Agente = { name: string; display_name: string }

type Props = {
  title?: string
  fabLabel?: string
  defaultAgent?: string
  suggestions?: string[]
  primary?: string
  primarySoft?: string
}

// Resize bounds. The panel is pinned bottom-right, so it grows up/left.
const MIN_W = 340
const MIN_H = 380
const DEFAULT_SIZE = { w: 440, h: 640 }

/** Parse the "Preguntas sugeridas" section from assistant text. */
function parseSuggestions(text: string): { body: string; questions: string[] } {
  const lines = text.split("\n")
  let splitIdx = -1
  for (let i = 0; i < lines.length; i++) {
    if (/preguntas?\s+sugeridas?/i.test(lines[i])) { splitIdx = i; break }
  }
  if (splitIdx === -1) return { body: text, questions: [] }
  const body = lines.slice(0, splitIdx).join("\n").trimEnd()
  const questions: string[] = []
  for (let i = splitIdx + 1; i < lines.length && questions.length < 3; i++) {
    const line = lines[i].trim()
    const m = line.match(/^(?:[-*]|\d+[.)]\s*)(.+)/)
    if (m) questions.push(m[1].trim())
  }
  return { body, questions }
}

/** Render a compact data table */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DataTable({ table, colors }: { table: any; colors: { border: string; borderSoft: string; text: string; textMuted: string } }) {
  const rs = table?.result_set
  if (!rs) return null
  const headers: string[] = (rs.resultSetMetaData?.rowType || []).map((c: { name: string }) => c.name)
  const rows: string[][] = (rs.data || []).slice(0, 8)
  if (!headers.length || !rows.length) return null
  return (
    <div style={{ overflowX: "auto", marginTop: 8 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{ padding: "4px 6px", borderBottom: `1px solid ${colors.border}`, color: colors.textMuted, fontWeight: 600, textAlign: "left", whiteSpace: "nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ padding: "3px 6px", borderBottom: `1px solid ${colors.borderSoft}`, color: colors.text, whiteSpace: "nowrap" }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function AgentChat({
  title = "Asistente",
  fabLabel = "Pregúntale al agente",
  defaultAgent = "",
  suggestions = [],
  primary = "#29B5E8",
  primarySoft = "#11567F",
}: Props) {
  const C = {
    bgPanel: "#121A2E", bgPanelSoft: "#0F1626", border: "#23304D", borderSoft: "#1A2540",
    text: "#EAF0FF", textMuted: "#8FA0C2", textFaint: "#5B6B8C",
  }
  const [open, setOpen] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const [agentes, setAgentes] = useState<Agente[]>([])
  const [agente, setAgente] = useState(defaultAgent)
  const [input, setInput] = useState("")
  const [msgs, setMsgs] = useState<UiMsg[]>([])
  const [loading, setLoading] = useState(false)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const [size, setSize] = useState(DEFAULT_SIZE)
  const [dragging, setDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0 })
  const resizeRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || agentes.length > 0) return
    fetch("/api/agents").then((r) => r.json()).then((d) => {
      if (Array.isArray(d.agents) && d.agents.length) {
        setAgentes(d.agents)
        if (!agente || !d.agents.find((a: Agente) => a.name === agente)) setAgente(d.agents[0].name)
      }
    }).catch(() => {})
  }, [open, agentes.length, agente])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }) }, [msgs, loading])

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    setDragging(true); dragStart.current = { x: e.clientX - pos.x, y: e.clientY - pos.y }; e.preventDefault()
  }, [pos])
  useEffect(() => {
    if (!dragging) return
    const onMove = (e: MouseEvent) => setPos({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y })
    const onUp = () => setDragging(false)
    window.addEventListener("mousemove", onMove); window.addEventListener("mouseup", onUp)
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp) }
  }, [dragging])

  // Drag-to-resize from the top-left handle. Panel is pinned bottom-right, so we
  // grow up/left as the pointer moves up/left. Clamped to viewport + min size.
  useEffect(() => {
    function onMove(e: PointerEvent) {
      const d = resizeRef.current
      if (!d) return
      const maxW = window.innerWidth - 32
      const maxH = window.innerHeight - 48
      const w = Math.min(maxW, Math.max(MIN_W, d.startW + (d.startX - e.clientX)))
      const h = Math.min(maxH, Math.max(MIN_H, d.startH + (d.startY - e.clientY)))
      setSize({ w, h })
    }
    function onUp() { resizeRef.current = null; document.body.style.userSelect = "" }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    return () => { window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp) }
  }, [])

  function startResize(e: React.PointerEvent) {
    e.preventDefault()
    resizeRef.current = { startX: e.clientX, startY: e.clientY, startW: size.w, startH: size.h }
    document.body.style.userSelect = "none"
  }

  async function enviar(q: string) {
    const pregunta = q.trim(); if (!pregunta || loading) return
    setInput("")
    const history = [...msgs, { role: "user" as const, text: pregunta }]
    setMsgs(history); setLoading(true)
    try {
      const apiMessages: ApiMessage[] = history.map((m) => ({ role: m.role, content: [{ type: "text", text: m.text }] }))
      const res = await fetch("/api/agent", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: agente, messages: apiMessages }),
      })
      const data = await res.json()
      if (!res.ok) {
        setMsgs((m) => [...m, { role: "assistant", text: "Error: " + (data.error || "no se pudo responder") }])
      } else {
        // Accept BOTH route shapes: DATA_AGENT_RUN ({text, charts[], suggestions[]})
        // and the REST route ({text, chartSpec, citations, tables}).
        const charts = Array.isArray(data.charts) ? data.charts : data.chartSpec ? [data.chartSpec] : []
        setMsgs((m) => [...m, {
          role: "assistant",
          text: data.text || "Sin respuesta.",
          citations: data.citations || [],
          charts,
          suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
          tables: data.tables || [],
        }])
      }
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: "Error: " + (e instanceof Error ? e.message : "fallo de red") }])
    } finally { setLoading(false) }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} title={fabLabel}
        style={{ position: "fixed", bottom: 24, right: 24, zIndex: 1000, height: 56, borderRadius: 999, padding: "0 20px",
          display: "inline-flex", alignItems: "center", gap: 10, color: "#fff", fontWeight: 700, fontSize: 14, border: "none",
          cursor: "pointer", background: `linear-gradient(135deg, ${primary}, ${primarySoft})`, boxShadow: "0 10px 30px rgba(41,181,232,.45)" }}>
        <Sparkles size={18} /> {fabLabel}
      </button>
    )
  }

  return (
    <div style={{ position: "fixed", bottom: 24 - pos.y, right: 24 - pos.x, width: minimized ? 280 : size.w,
      height: minimized ? "auto" : size.h, maxHeight: minimized ? "auto" : "calc(100vh - 48px)", zIndex: 1000, borderRadius: 16, border: `1px solid ${C.border}`,
      background: C.bgPanel, boxShadow: "0 12px 48px rgba(0,0,0,.55)", display: "flex", flexDirection: "column",
      overflow: "hidden", transition: dragging || resizeRef.current ? "none" : "width .2s ease, height .2s ease" }}>
      {!minimized && (
        <div
          onPointerDown={startResize}
          title="Arrastra para redimensionar"
          aria-label="Redimensionar"
          style={{ position: "absolute", top: 0, left: 0, width: 18, height: 18, zIndex: 2, cursor: "nwse-resize",
            touchAction: "none", borderTopLeftRadius: 16,
            background: `linear-gradient(135deg, ${primary}55 0 35%, transparent 35%)` }}
        />
      )}
      <div onMouseDown={onMouseDown} onDoubleClick={() => setMinimized((v) => !v)} style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 12px", cursor: "grab", userSelect: "none", borderBottom: minimized ? "none" : `1px solid ${C.border}`,
        background: `linear-gradient(135deg, ${primarySoft}33, transparent)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <GripVertical size={14} color={C.textFaint} />
          <div style={{ width: 26, height: 26, borderRadius: 8, display: "grid", placeItems: "center",
            background: `linear-gradient(135deg, ${primary}, ${primarySoft})` }}><Sparkles size={13} color="#fff" /></div>
          <span style={{ fontWeight: 700, color: C.text, fontSize: 13 }}>{title}</span>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          <button onClick={() => setMinimized(!minimized)} aria-label={minimized ? "Expandir" : "Minimizar"} style={{ background: "none", border: "none", color: C.textMuted, padding: 4, cursor: "pointer" }}>{minimized ? <Maximize2 size={15} /> : <Minus size={16} />}</button>
          <button onClick={() => setOpen(false)} style={{ background: "none", border: "none", color: C.textMuted, padding: 4, cursor: "pointer" }}><X size={16} /></button>
        </div>
      </div>
      {!minimized && (
        <>
          {agentes.length > 0 && (
            <div style={{ padding: "8px 12px", borderBottom: `1px solid ${C.borderSoft}` }}>
              <select value={agente} onChange={(e) => setAgente(e.target.value)}
                style={{ width: "100%", background: C.bgPanelSoft, color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 8px", fontSize: 12 }}>
                {agentes.map((a) => <option key={a.name} value={a.name}>{a.display_name} ({a.name})</option>)}
              </select>
            </div>
          )}
          <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
            {msgs.length === 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ color: C.textMuted, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}><MessageSquare size={14} /> ¿En qué te ayudo?</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {suggestions.map((s) => <button key={s} className="chip" style={{ cursor: "pointer", fontSize: 11.5 }} onClick={() => enviar(s)}>{s}</button>)}
                </div>
              </div>
            )}
            {msgs.map((m, i) => {
              if (m.role === "user") {
                return (
                  <div key={i} style={{ display: "flex", justifyContent: "flex-end" }}>
                    <div style={{ maxWidth: "85%", padding: "9px 12px", borderRadius: 12, fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap",
                      color: "#fff", background: `linear-gradient(135deg, ${primary}, ${primarySoft})` }}>{m.text}</div>
                  </div>
                )
              }
              const parsed = parseSuggestions(m.text)
              const body = m.suggestions && m.suggestions.length ? m.text : parsed.body
              const questions = m.suggestions && m.suggestions.length ? m.suggestions.slice(0, 3) : parsed.questions
              const charts = (m.charts ?? []).filter(isValidVegaSpec)
              return (
                <div key={i} style={{ display: "flex", justifyContent: "flex-start" }}>
                  <div style={{ maxWidth: "85%", padding: "9px 12px", borderRadius: 12, fontSize: 13, lineHeight: 1.5,
                    color: C.text, background: C.bgPanelSoft, border: `1px solid ${C.border}`, overflow: "hidden" }}>
                    <ChatErrorBoundary>
                    <div className="agent-md">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
                    </div>
                    {charts.map((spec, ci) => (
                      <ChatErrorBoundary key={ci} fallback={<div style={{ fontSize: 11, color: C.textFaint }}>Gráfico no disponible.</div>}>
                        <AgentVega spec={spec} />
                      </ChatErrorBoundary>
                    ))}
                    {m.tables && m.tables.length > 0 && <DataTable table={m.tables[0]} colors={C} />}
                    {m.citations && m.citations.length > 0 && (
                      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: C.textFaint }}>FUENTES</div>
                        {m.citations.slice(0, 4).map((c, j) => (
                          <div key={j} style={{ fontSize: 11, color: C.textMuted, display: "flex", gap: 6 }}>
                            <FileText size={12} color={primary} style={{ flexShrink: 0, marginTop: 2 }} /><span>{c.title}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {questions.length > 0 && (
                      <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {questions.map((q, qi) => (
                          <button key={qi} className="chip" onClick={() => enviar(q)}
                            style={{ cursor: "pointer", fontSize: 11, padding: "4px 10px", borderRadius: 8,
                              background: C.borderSoft, color: C.textMuted, border: `1px solid ${C.border}` }}>{q}</button>
                        ))}
                      </div>
                    )}
                    </ChatErrorBoundary>
                  </div>
                </div>
              )
            })}
            {loading && <div style={{ color: C.textMuted, fontSize: 12.5 }}>El agente está pensando…</div>}
            <div ref={endRef} />
          </div>
          <div style={{ display: "flex", gap: 8, padding: "10px 12px", borderTop: `1px solid ${C.border}` }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") enviar(input) }}
              placeholder="Escribe tu pregunta…" disabled={loading}
              style={{ flex: 1, background: C.bgPanelSoft, color: C.text, border: `1px solid ${C.border}`, borderRadius: 10, padding: "9px 12px", fontSize: 13, outline: "none" }} />
            <button onClick={() => enviar(input)} disabled={loading || !input.trim()}
              style={{ background: `linear-gradient(135deg, ${primary}, ${primarySoft})`, border: "none", borderRadius: 10, color: "#fff", padding: "0 14px",
                cursor: loading || !input.trim() ? "default" : "pointer", opacity: loading || !input.trim() ? 0.5 : 1 }}><Send size={15} /></button>
          </div>
        </>
      )}
      <style jsx global>{`
        .agent-md { color: #EAF0FF; }
        .agent-md p { margin: 0 0 6px 0; }
        .agent-md h1, .agent-md h2, .agent-md h3, .agent-md h4 { margin: 6px 0 4px 0; font-size: 13px; font-weight: 700; color: #EAF0FF; }
        .agent-md h2 { font-size: 12.5px; } .agent-md h3 { font-size: 12px; }
        .agent-md ul, .agent-md ol { margin: 2px 0; padding-left: 16px; }
        .agent-md li { margin-bottom: 2px; }
        .agent-md code { background: rgba(255,255,255,0.07); padding: 1px 4px; border-radius: 4px; font-size: 12px; }
        .agent-md pre { background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; overflow-x: auto; margin: 4px 0; }
        .agent-md pre code { background: none; padding: 0; }
        .agent-md a { color: #29B5E8; text-decoration: underline; }
        .agent-md strong { color: #EAF0FF; }
        .agent-md table { border-collapse: collapse; margin: 4px 0; font-size: 11.5px; }
        .agent-md th, .agent-md td { border: 1px solid #23304D; padding: 3px 6px; }
        .agent-md th { background: rgba(255,255,255,0.04); font-weight: 600; }
      `}</style>
    </div>
  )
}
