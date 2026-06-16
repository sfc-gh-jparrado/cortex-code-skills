// Data contracts shared between the API layer and all chart components.
// Every numeric field is a real JS number (the API coerces with Number()).

export interface ComercioDemo {
  comercio_id: number
  comercio: string
  sector: string
  ciudad: string
  tamano: string
}

export interface ResumenComercio {
  comercio_id: number
  comercio: string
  sector: string
  ciudad: string
  tamano: string
  monto_total: number
  num_tx: number
  ticket_promedio: number
  tasa_aprobacion: number
  tasa_rechazo: number
  clientes_dia_prom: number
  nuevos_clientes_total: number
  crecimiento_mom: number
  recurrencia_pct: number
}

export interface TendenciaPunto {
  mes: string // YYYY-MM
  monto: number
  num_tx: number
  ticket: number
  tasa_aprob: number
}

export interface SectorTendenciaPunto {
  mes: string // YYYY-MM
  monto_prom: number
  ticket_prom: number
  tasa_aprob_prom: number
}

export interface CanalPunto {
  canal: string
  monto: number
  num_tx: number
  share: number // %
}

export interface FamiliaPunto {
  familia: string
  monto: number
  num_tx: number
  share_comercio: number // %
  share_sector: number // %
}

export interface GeoPunto {
  depto_key: string // matches NOMBRE_DPT in the GeoJSON
  depto: string
  region: string
  monto: number
  num_tx: number
  clientes: number
  share: number // %
}

export interface BenchmarkPunto {
  metrica: string
  etiqueta: string
  valor: number
  sector_prom: number
  sector_p50: number
  sector_min: number
  sector_max: number
  percentil: number // 0..100
  ranking: number // 1 = best
  total_sector: number
}

export interface PeerPunto {
  comercio_id: number
  alias: string
  tamano: string
  es_self: boolean
  monto: number
  ticket: number
  tasa_aprob: number
  num_tx: number
  crecimiento: number
  recurrencia: number
}

export interface DiarioPunto {
  fecha: string // YYYY-MM-DD
  monto: number
  num_tx: number
}

export interface DashboardPayload {
  comercio: ResumenComercio
  tendencia: TendenciaPunto[]
  sectorTendencia: SectorTendenciaPunto[]
  canales: CanalPunto[]
  familias: FamiliaPunto[]
  geo: GeoPunto[]
  benchmark: BenchmarkPunto[]
  peers: PeerPunto[]
  diario: DiarioPunto[]
}

export interface HoraPunto {
  dia_semana: number // 1=Lun ... 7=Dom
  dia: string // Lun, Mar, ...
  hora: number // 0..23
  num_tx: number
  monto: number
}

export interface AgentChartSpec {
  mark: string
  values: Record<string, number | string>[]
  x?: string
  y?: string
  color?: string
}

export interface AgentResponse {
  texto: string
  sql?: string
  grafico?: AgentChartSpec
  citaciones: { titulo?: string; texto: string }[]
  sugerencias: string[]
  herramientas: string[]
  razonamiento: string[]
}
