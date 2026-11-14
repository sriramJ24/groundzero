// Transparent, rule-based INDICATIVE scores. Nothing here is a trained or validated model.
// Every score returns the factors that produced it so the UI can show its working.
import type { ActionItem, Capture, Factor, LayerId, NdviData, Risk, Weather, Zone } from './types'

export const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v))

// Used only when no weather file is available (offline). Labelled simulated in the UI.
export const FALLBACK_WEATHER: Weather = {
  source: 'Built-in sample forecast (simulated, used because no weather file was found)',
  fetched_at: '2026-11-14T18:00:00Z',
  provenance: 'simulated',
  daily: [0, 1, 2, 3, 4, 5, 6].map((d) => ({
    date: new Date(Date.parse('2026-11-14') + d * 86400000).toISOString().slice(0, 10),
    tmax_c: [24, 26, 29, 31, 30, 27, 23][d], tmin_c: [9, 10, 12, 13, 13, 11, 9][d],
    precip_mm: [0, 0, 0, 0, 0, 1.2, 4][d], et0_mm: [2.6, 2.9, 3.4, 3.8, 3.6, 2.9, 2.1][d],
    radiation_mj_m2: [12, 12.5, 13, 13.2, 12.8, 10, 7][d], rh_mean_pct: [55, 50, 42, 38, 40, 52, 66][d], wind_max_kmh: [12, 14, 18, 22, 19, 15, 16][d],
  })),
}

const PENALTY: Record<string, number> = { healthy: 0, discoloration: 35, wilting: 60 }
const RECENCY = [1, 0.8, 0.6, 0.4, 0.2]

/** Same rule as backend/scoring.py: newest five captures, recency weighted, rejected reviews ignored. */
export function healthFromCaptures(zone: Zone, captures: Capture[]): Zone['health'] {
  const cs = captures.filter((c) => c.zone_id === zone.id && c.review.status !== 'rejected')
    .sort((a, b) => (a.received_at < b.received_at ? 1 : -1))
  // Seeded demo captures already agree with the simulated baseline; only live uploads move the score.
  const live = cs.filter((c) => c.live)
  if (!live.length) return { ...zone.health, n_captures: cs.length }
  const top = cs.slice(0, 5)
  let pen = 0, wsum = 0
  top.forEach((c, i) => { const w = RECENCY[i]; pen += w * (PENALTY[c.edge_prediction.label] ?? 20) * c.edge_prediction.confidence; wsum += w })
  const mix: Record<string, number> = {}
  cs.forEach((c) => { mix[c.edge_prediction.label] = (mix[c.edge_prediction.label] ?? 0) + 1 })
  const fromImages = clamp(100 - (pen / wsum) * 1.6, 0, 100)
  const score = Math.round(0.5 * zone.health.score + 0.5 * fromImages)
  // rejected images are already filtered out above
  return { score, last_label: cs[0].edge_prediction.label, last_confidence: cs[0].edge_prediction.confidence, n_captures: cs.length, label_mix: mix, method: 'indicative rule-based (baseline + recent images)' }
}

export interface WeatherSummary { tmax3: number; et0_3: number; rain3: number; et0_7: number; rain7: number; rhMin3: number | null; days: number }
export function summarise(w: Weather): WeatherSummary {
  const d3 = w.daily.slice(0, 3), d7 = w.daily.slice(0, 7)
  const sum = (a: number[]) => a.reduce((s, v) => s + (v ?? 0), 0)
  const rh = d3.map((d) => d.rh_mean_pct).filter((v): v is number => v != null)
  return {
    tmax3: Math.max(...d3.map((d) => d.tmax_c)), et0_3: sum(d3.map((d) => d.et0_mm)), rain3: sum(d3.map((d) => d.precip_mm)),
    et0_7: sum(d7.map((d) => d.et0_mm)), rain7: sum(d7.map((d) => d.precip_mm)), rhMin3: rh.length ? Math.min(...rh) : null, days: d7.length,
  }
}

/** Zone risk for the next ~72 h. Weights are stated in the factor list; they are assumptions, not fitted. */
export function computeRisk(zone: Zone, w: Weather): Risk {
  const s = summarise(w)
  const wxSource = w.provenance ?? 'public-weather'
  const visual = clamp((100 - zone.health.score) / 100)
  // crude water balance for the coming week: demand (ET0) minus rain minus half of last week's irrigation carry-over
  const deficitMm = s.et0_7 - s.rain7 - 0.5 * zone.water.applied_mm_7d
  const deficit = clamp((deficitMm + 10) / 35)
  const holding = 1 - zone.water_holding
  const heatIdx = clamp((s.tmax3 - 28) / 12)

  const f: Factor[] = []
  const dPts = { deficit: 45 * deficit, soil: 20 * holding, visual: 25 * visual, exposure: 10 * zone.exposure }
  f.push({ name: 'Water balance, next 7 days', points: dPts.deficit, source: wxSource, detail: `ET₀ ${s.et0_7.toFixed(0)} mm − rain ${s.rain7.toFixed(0)} mm − carry-over of ${zone.water.applied_mm_7d.toFixed(0)} mm applied last week → ${deficitMm.toFixed(0)} mm shortfall` })
  f.push({ name: 'Soil water-holding', points: dPts.soil, source: 'simulated', detail: `${zone.soil}; holding index ${zone.water_holding.toFixed(2)}` })
  f.push({ name: 'Visible stress in images', points: dPts.visual, source: zone.provenance, detail: `health score ${zone.health.score}/100, last label “${zone.health.last_label}”` })
  f.push({ name: 'Exposure (slope/ridge)', points: dPts.exposure, source: 'simulated', detail: `exposure index ${zone.exposure.toFixed(2)}` })
  const drought = Math.round(clamp((dPts.deficit + dPts.soil + dPts.visual + dPts.exposure) / 100) * 100)

  const hPts = { heat: 40 * heatIdx, exposure: 35 * zone.exposure * heatIdx, visual: 25 * visual * heatIdx }
  f.push({ name: 'Forecast heat, next 72 h', points: hPts.heat, source: wxSource, detail: `max ${s.tmax3.toFixed(1)} °C (index starts at 28 °C)` })
  const heat = Math.round(clamp((hPts.heat + hPts.exposure + hPts.visual) / 100) * 100)

  const relief = clamp(s.rain3 / 15) * 20
  const forecast_impact = Math.round(clamp((0.65 * drought + 0.35 * heat - relief) / 100) * 100)
  if (relief > 0.5) f.push({ name: 'Rain relief, next 72 h', points: -relief, source: wxSource, detail: `${s.rain3.toFixed(1)} mm forecast` })

  const missing: string[] = []
  if (zone.sensors.soil_moisture_pct == null) missing.push('in-field soil moisture')
  if (zone.sensors.air_temp_c == null) missing.push('in-canopy temperature')
  return { drought, heat, forecast_impact, factors: f, missing_inputs: missing, needs_sensor_validation: zone.sensors.soil_moisture_pct == null }
}

// ---------- layers ----------
export interface LayerDef {
  id: LayerId; name: string; unit: string; lowLabel: string; highLabel: string
  /** colour stops from low to high */
  ramp: string[]
  source: string
}
export const LAYERS: LayerDef[] = [
  { id: 'health', name: 'Crop health', unit: '/100', lowLabel: 'stressed', highLabel: 'healthy', ramp: ['#d9483b', '#e9a23b', '#d8cf55', '#58b56b', '#2f8f5b'], source: 'Camera labels → indicative score. Simulated baseline until real captures arrive.' },
  { id: 'drought', name: 'Drought / heat risk', unit: '/100', lowLabel: 'low', highLabel: 'high', ramp: ['#1f6f6b', '#3d9a82', '#d8c45a', '#e88b3a', '#d9483b'], source: 'Rule-based: forecast water balance + soil + visible stress. Indicative only.' },
  { id: 'water', name: 'Water applied', unit: 'mm / 7 d', lowLabel: 'less', highLabel: 'more', ramp: ['#1a2a3a', '#1f4f7a', '#2f7fc0', '#4aa8e8', '#9fd6ff'], source: 'Irrigation log by zone (simulated machine records).' },
  { id: 'spray', name: 'Pesticide coverage', unit: '% of zone', lowLabel: 'none', highLabel: 'full', ramp: ['#1c2029', '#3b3466', '#6a57b8', '#a487f2', '#d7c9ff'], source: 'Application log by zone (simulated). Coverage, not efficacy.' },
  { id: 'forecast', name: 'Forecast impact', unit: '/100', lowLabel: 'low', highLabel: 'high', ramp: ['#24506b', '#3f8f8a', '#cdbf55', '#ea8f3c', '#d44a3a'], source: 'Next-72 h weather translated to zone impact. Rule-based, indicative.' },
  { id: 'ndvi', name: 'Satellite NDVI', unit: 'NDVI', lowLabel: 'bare', highLabel: 'dense', ramp: ['#6b4a2b', '#a58446', '#d6cf6a', '#6fb55c', '#1f7a43'], source: 'Sentinel-2 L2A, real imagery of the reference location.' },
]

export interface LayerValue { v: number; display: string; missing?: boolean }
export function layerValue(layer: LayerId, zone: Zone, risk: Risk, ndvi: NdviData | null, maxWater: number): LayerValue {
  switch (layer) {
    case 'health': return { v: zone.health.score / 100, display: `${zone.health.score}` }
    case 'drought': { const r = Math.round(0.6 * risk.drought + 0.4 * risk.heat); return { v: r / 100, display: `${r}` } }
    case 'water': return { v: clamp(zone.water.applied_mm_7d / maxWater), display: `${zone.water.applied_mm_7d.toFixed(1)}` }
    case 'spray': return { v: zone.spray.coverage_pct / 100, display: `${zone.spray.coverage_pct}%` }
    case 'forecast': return { v: risk.forecast_impact / 100, display: `${risk.forecast_impact}` }
    case 'ndvi': {
      const n = ndvi?.latest?.zones?.[zone.id]
      if (n == null || !ndvi) return { v: 0, display: 'n/a', missing: true }
      const span = Math.max(0.05, ndvi.latest.max - ndvi.latest.min)
      return { v: clamp((n - ndvi.latest.min) / span), display: n.toFixed(2) }
    }
  }
}

export function rampColor(ramp: string[], v: number): [number, number, number] {
  const x = clamp(v) * (ramp.length - 1)
  const i = Math.min(ramp.length - 2, Math.floor(x)), t = x - i
  const a = hex(ramp[i]), b = hex(ramp[i + 1])
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
}
const hex = (h: string): [number, number, number] => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255]
export const rampCss = (ramp: string[]) => `linear-gradient(90deg, ${ramp.join(',')})`

// ---------- recommendations ----------
export function buildActions(zones: Zone[], risks: Record<string, Risk>, captures: Capture[]): ActionItem[] {
  const out: ActionItem[] = []
  const sorted = zones.map((z) => z.water.applied_mm_7d).sort((a, b) => a - b)
  const medianWater = sorted[Math.floor(sorted.length / 2)] ?? 0
  for (const z of zones) {
    const r = risks[z.id]
    const cs = captures.filter((c) => c.zone_id === z.id)
    const latest = cs.sort((a, b) => (a.received_at < b.received_at ? 1 : -1))[0]
    const underWatered = z.water.applied_mm_7d < 0.7 * medianWater
    if (z.health.last_label === 'wilting' && (r.drought >= 50 || underWatered)) {
      out.push({ id: `irr-${z.id}`, zone_id: z.id, priority: 1, kind: 'review_irrigation', score: r.drought + (100 - z.health.score),
        title: `Check irrigation reach in ${z.id} and inspect for water stress`,
        why: [latest ? `Images labelled “wilting” (${cs.length} capture${cs.length === 1 ? '' : 's'}; latest confidence ${Math.round(latest.edge_prediction.confidence * 100)}%)` : 'Simulated baseline marks this zone as wilting; no camera image yet, so scan it first',
          `${z.water.applied_mm_7d.toFixed(0)} mm logged in the last 7 days against a field median of ${medianWater.toFixed(0)} mm`, `Drought risk ${r.drought}/100 from the forecast water balance`,
          'No soil moisture probe in this zone, so confirm on the ground before changing the schedule'] })
    } else if (z.health.last_label === 'discoloration' && z.health.score < 70) {
      out.push({ id: `scout-${z.id}`, zone_id: z.id, priority: z.health.score < 45 ? 1 : 2, kind: 'scout', score: 60 + (100 - z.health.score),
        title: `Scout ${z.id}: leaf discoloration flagged`,
        why: [`Images labelled “discoloration” — the camera sees appearance, not cause`,
          z.spray.events.length ? `Last application logged ${new Date(z.spray.events.at(-1)!.at).toLocaleDateString()} at ${z.spray.coverage_pct}% coverage; compare images before and after` : 'No application logged for this zone',
          'Have an agronomist confirm the cause before any treatment decision'] })
    } else if (r.needs_sensor_validation && r.drought >= 62) {
      out.push({ id: `probe-${z.id}`, zone_id: z.id, priority: 2, kind: 'validate_sensor', score: r.drought,
        title: `Take a soil moisture reading in ${z.id}`,
        why: [`Drought risk ${r.drought}/100 is estimated without a soil sensor`, `Soil: ${z.soil}`, 'A probe reading would confirm or clear this flag'] })
    }
    const lowConf = cs.filter((c) => c.review.status === 'unreviewed' && c.edge_prediction.confidence < 0.6)
    if (lowConf.length >= 2) out.push({ id: `rev-${z.id}`, zone_id: z.id, priority: 3, kind: 'review_images', score: 30 + lowConf.length,
      title: `Review ${lowConf.length} low-confidence images from ${z.id}`, why: ['Edge label confidence below 60%', 'Your approve/reject feedback removes rejected images from the zone score'] })
  }
  return out.sort((a, b) => a.priority - b.priority || b.score - a.score).slice(0, 14)
}
