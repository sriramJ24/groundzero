import { create } from 'zustand'
import { BACKEND_FIELD, loadAll, loadDataFile, postCapture, postReview, subscribe, type Mode, type UploadInput } from './data/api'
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
  weatherNow: Weather
  weatherHeat: Weather | null
  scenario: 'now' | 'heat'
  setScenario: (sc: 'now' | 'heat') => void
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

  init: (fieldId?: string) => Promise<void>
  loadedFieldId: string | null
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

let unsubscribe: (() => void) | null = null

export const useStore = create<State>((set, get) => ({
  ready: false, loadedFieldId: null, mode: 'demo', sseOk: false, field: null, baseZones: [], zones: [], zoneById: {}, risks: {}, captures: [], machine: null,
  actions: [], doneActions: {}, weather: FALLBACK_WEATHER, weatherNow: FALLBACK_WEATHER, weatherHeat: null, scenario: 'now', ndvi: null,
  evals: { forecast: null, outcome: null, droughtImage: null, soilForecast: null, soilHistory: null },
  view: 'overview', layer: 'health', extrude: true, hovered: null, pinned: null, zoneTab: 'Health',
  replayT: 0, playing: true, liveZone: null, simOpen: false, modalCapture: null, lastSync: Date.now(), resetTick: 0,

  set: (p) => set(p),
  setHovered: (id) => { if (get().hovered !== id) set({ hovered: id }) },
  togglePin: (id) => set((s) => ({ pinned: id && s.pinned !== id ? id : null })),
  focusZone: (id, tab) => set({ pinned: id, view: 'overview', ...(tab ? { zoneTab: tab } : {}) }),

  init: async (fieldId) => {
    unsubscribe?.(); unsubscribe = null
    set({ ready: false, pinned: null, hovered: null, liveZone: null, modalCapture: null, doneActions: {}, sseOk: false })
    const { mode, data } = await loadAll(fieldId)
    const d = derive(data.zones, data.captures, get().weather)
    set((s) => ({ ready: true, loadedFieldId: data.field.id, mode, field: data.field, baseZones: data.zones, captures: data.captures, machine: data.machine, replayT: data.machine.duration_s * 0.55, playing: true,
      ndvi: null, layer: s.layer === 'ndvi' ? 'health' : s.layer, ...d, lastSync: Date.now() }))
    if (mode === 'live') {
      unsubscribe = subscribe(
        (c) => get().addCapture(c),
        (c) => set((s) => { const captures = s.captures.map((x) => (x.id === c.id ? { ...x, review: c.review } : x)); return { captures, ...derive(s.baseZones, captures, s.weather) } }),
        (ok) => set({ sseOk: ok }),
      )
    }
    // Optional real-data files; each one is independent and may be absent.
    loadDataFile<Weather>('weather.json').then((w) => { if (w?.daily?.length) { const weatherNow = { ...w, provenance: 'public-weather' as const }; set({ weatherNow }); if (get().scenario === 'now') get().setScenario('now') } })
    loadDataFile<Weather>('weather_scenario_heat.json').then((w) => { if (w?.daily?.length) set({ weatherHeat: { ...w, provenance: 'public-weather' as const } }) })
    if (data.field.id === BACKEND_FIELD) loadDataFile<NdviData>('ndvi_zones.json').then((n) => { if (n?.latest?.zones && n.status !== 'failed' && get().loadedFieldId === BACKEND_FIELD) set({ ndvi: n }) })
    const ev = (key: keyof State['evals'], file: string) => loadDataFile<any>(file).then((v) => { if (v) set((s) => ({ evals: { ...s.evals, [key]: v } })) })
    ev('forecast', 'forecast_eval.json'); ev('outcome', 'outcome_eval.json'); ev('droughtImage', 'drought_image_eval.json'); ev('soilForecast', 'soil_forecast.json'); ev('soilHistory', 'soil_history.json')
  },

  setScenario: (sc) => set((s) => {
    const weather = sc === 'heat' && s.weatherHeat ? s.weatherHeat : s.weatherNow
    return { scenario: sc === 'heat' && s.weatherHeat ? 'heat' : 'now', weather, ...derive(s.baseZones, s.captures, weather) }
  }),

  addCapture: (c) => set((s) => {
    if (s.captures.some((x) => x.id === c.id)) return {}
    const captures = [c, ...s.captures]
    return { captures, liveZone: c.zone_id, playing: false, lastSync: Date.now(), ...derive(s.baseZones, captures, s.weather) }
  }),
  upload: async (input) => {
    const c = await postCapture(get().mode, { ...input, fieldId: get().field?.id })
    get().addCapture(c)
    return c
  },
  review: (id, status) => {
    set((s) => { const captures = s.captures.map((x) => (x.id === id ? { ...x, review: { ...x.review, status, reviewed_at: new Date().toISOString() } } : x)); return { captures, ...derive(s.baseZones, captures, s.weather) } })
    postReview(get().mode, id, status)
  },
}))

export const activeZoneId = (s: State) => s.pinned ?? s.hovered
