import { create } from 'zustand'
import { loadAll, loadDataFile, postCapture, postReview, subscribe, type Mode, type UploadInput } from './data/api'
import { buildActions, computeRisk, FALLBACK_WEATHER, healthFromCaptures } from './data/scoring'
import type { ActionItem, Capture, Field, LayerId, Machine, NdviData, ReviewStatus, Risk, Weather, Zone } from './data/types'

export type ViewId = 'overview' | 'vision' | 'water' | 'protection' | 'weather' | 'actions' | 'models' | 'device'
export type ZoneTab = 'Health' | 'Water' | 'Spraying' | 'Weather' | 'Images' | 'History'

interface State {
  ready: boolean
  mode: Mode
  sseOk: boolean
  field: Field | null
  baseZones: Zone[]
  zones: Zone[]
  zoneById: Record<string, Zone>
  risks: Record<string, Risk>
  captures: Capture[]
  machine: Machine | null
  actions: ActionItem[]
  doneActions: Record<string, 'done' | 'dismissed'>
  weather: Weather
  ndvi: NdviData | null
  evals: { forecast: any | null; outcome: any | null; droughtImage: any | null; soilForecast: any | null; soilHistory: any | null }

  view: ViewId
  layer: LayerId
  extrude: boolean
  hovered: string | null
  pinned: string | null
  zoneTab: ZoneTab
  replayT: number
  playing: boolean
  liveZone: string | null
  simOpen: boolean
  modalCapture: string | null
  lastSync: number
  resetTick: number

  init: () => Promise<void>
  set: (p: Partial<State>) => void
  setHovered: (id: string | null) => void
  togglePin: (id: string | null) => void
  focusZone: (id: string, tab?: ZoneTab) => void
  addCapture: (c: Capture) => void
  upload: (input: UploadInput) => Promise<Capture>
  review: (id: string, status: ReviewStatus) => void
}

function derive(baseZones: Zone[], captures: Capture[], weather: Weather) {
  const zones = baseZones.map((z) => ({ ...z, health: healthFromCaptures(z, captures) }))
  const zoneById: Record<string, Zone> = {}
  const risks: Record<string, Risk> = {}
  for (const z of zones) { zoneById[z.id] = z; risks[z.id] = computeRisk(z, weather) }
  return { zones, zoneById, risks, actions: buildActions(zones, risks, captures) }
}

export const useStore = create<State>((set, get) => ({
  ready: false, mode: 'demo', sseOk: false, field: null, baseZones: [], zones: [], zoneById: {}, risks: {}, captures: [], machine: null,
  actions: [], doneActions: {}, weather: FALLBACK_WEATHER, ndvi: null,
  evals: { forecast: null, outcome: null, droughtImage: null, soilForecast: null, soilHistory: null },
  view: 'overview', layer: 'health', extrude: true, hovered: null, pinned: null, zoneTab: 'Health',
  replayT: 0, playing: true, liveZone: null, simOpen: false, modalCapture: null, lastSync: Date.now(), resetTick: 0,

  set: (p) => set(p),
  setHovered: (id) => { if (get().hovered !== id) set({ hovered: id }) },
  togglePin: (id) => set((s) => ({ pinned: id && s.pinned !== id ? id : null })),
  focusZone: (id, tab) => set({ pinned: id, view: 'overview', ...(tab ? { zoneTab: tab } : {}) }),

  init: async () => {
    const { mode, data } = await loadAll()
    const d = derive(data.zones, data.captures, get().weather)
    set({ ready: true, mode, field: data.field, baseZones: data.zones, captures: data.captures, machine: data.machine, replayT: data.machine.duration_s * 0.55, ...d, lastSync: Date.now() })
    if (mode === 'live') {
      subscribe(
        (c) => get().addCapture(c),
        (c) => set((s) => { const captures = s.captures.map((x) => (x.id === c.id ? { ...x, review: c.review } : x)); return { captures, ...derive(s.baseZones, captures, s.weather) } }),
        (ok) => set({ sseOk: ok }),
      )
    }
    // Optional real-data files; each one is independent and may be absent.
    loadDataFile<Weather>('weather.json').then((w) => { if (w?.daily?.length) { const weather = { ...w, provenance: 'public-weather' as const }; set((s) => ({ weather, ...derive(s.baseZones, s.captures, weather) })) } })
    loadDataFile<NdviData>('ndvi_zones.json').then((n) => { if (n?.latest?.zones && n.status !== 'failed') set({ ndvi: n }) })
    const ev = (key: keyof State['evals'], file: string) => loadDataFile<any>(file).then((v) => { if (v) set((s) => ({ evals: { ...s.evals, [key]: v } })) })
    ev('forecast', 'forecast_eval.json'); ev('outcome', 'outcome_eval.json'); ev('droughtImage', 'drought_image_eval.json'); ev('soilForecast', 'soil_forecast.json'); ev('soilHistory', 'soil_history.json')
  },

  addCapture: (c) => set((s) => {
    if (s.captures.some((x) => x.id === c.id)) return {}
    const captures = [c, ...s.captures]
    return { captures, liveZone: c.zone_id, playing: false, lastSync: Date.now(), ...derive(s.baseZones, captures, s.weather) }
  }),
  upload: async (input) => {
    const c = await postCapture(get().mode, input)
    get().addCapture(c)
    return c
  },
  review: (id, status) => {
    set((s) => { const captures = s.captures.map((x) => (x.id === id ? { ...x, review: { ...x.review, status, reviewed_at: new Date().toISOString() } } : x)); return { captures, ...derive(s.baseZones, captures, s.weather) } })
    postReview(get().mode, id, status)
  },
}))

export const activeZoneId = (s: State) => s.pinned ?? s.hovered
