// Generates the deterministic SIMULATED demo field used by both the frontend (mock mode)
// and the backend (seed). Run: node shared/gen_demo.mjs
// Everything produced here is synthetic and labelled provenance: "simulated".
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../frontend/src/data/demo')
const ROWS = 12, COLS = 12
const LETTERS = 'ABCDEFGHIJKL'

let seed = 20261114
const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296 }
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v))
const blob = (c, r, cx, cy, s) => Math.exp(-((c - cx) ** 2 + (r - cy) ** 2) / (2 * s * s))
const round = (v, d = 1) => Number(v.toFixed(d))

const NOW = Date.parse('2026-11-14T18:00:00Z')
const iso = (msAgo) => new Date(NOW - msAgo).toISOString()
const DAY = 86400000

function build(cfg) {
seed = cfg.seed
const zones = []
for (let r = 0; r < ROWS; r++) {
  for (let c = 0; c < COLS; c++) {
    const id = `${LETTERS[c]}${r + 1}`
    // Smooth synthetic terrain: a low ridge in the north-east, shallow swale in the south-west.
    const elevation = clamp(0.35 + 0.45 * blob(c, r, cfg.ridge[0], cfg.ridge[1], 3.2) - 0.25 * blob(c, r, 2, 9.5, 2.8) + 0.08 * Math.sin(c * 0.9) * Math.cos(r * 0.7))
    // Irrigation under-reaches the north-east corner (demo scenario: uneven coverage).
    const reach = clamp(1 - 0.75 * blob(c, r, cfg.dry[0], cfg.dry[1], cfg.drySize) - 0.15 * blob(c, r, 0, 0, 1.5))
    // A discoloration hot spot in the south-west (demo scenario).
    const disease = clamp(0.95 * blob(c, r, cfg.disease[0], cfg.disease[1], cfg.diseaseSize))
    const dry = clamp(1 - reach)
    const waterHolding = clamp(0.75 - 0.45 * elevation + 0.1 * (rnd() - 0.5)) // sandy on the ridge
    const exposure = clamp(0.3 + 0.6 * elevation + 0.1 * (rnd() - 0.5))

    const stress = clamp(1.25 * dry + 0.95 * disease + 0.07 * rnd())
    const score = Math.round(clamp(1 - stress, 0.12, 0.98) * 100)

    // Irrigation log (simulated machine records)
    const events = []
    for (const d of [2, 6, 11, 17, 24]) {
      const mm = round(clamp(reach + 0.08 * (rnd() - 0.5), 0.1, 1.1) * 18, 1)
      events.push({ at: iso(d * DAY + Math.floor(rnd() * 6) * 3600000), mm, source: 'pivot-1 (simulated log)' })
    }
    const applied7 = round(events.filter((_, i) => i < 2).reduce((s, e) => s + e.mm, 0))
    const applied30 = round(events.reduce((s, e) => s + e.mm, 0))

    // Crop protection log: one pass over the west half 9 days ago, a spot pass on the hot spot 3 days ago.
    const sprayEvents = []
    if (c <= 5) sprayEvents.push({ at: iso(9 * DAY), product_class: 'Fungicide (demo record)', rate_l_ha: 150, coverage_pct: Math.round(clamp(0.82 + 0.15 * rnd()) * 100) })
    if (disease > 0.35) sprayEvents.push({ at: iso(3 * DAY), product_class: 'Fungicide (demo record)', rate_l_ha: 150, coverage_pct: Math.round(clamp(0.7 + 0.25 * rnd()) * 100) })
    const coverage = sprayEvents.length ? Math.max(...sprayEvents.map((e) => e.coverage_pct)) : 0

    const last_label = dry > 0.3 ? 'wilting' : disease > 0.25 ? 'discoloration' : 'healthy'
    zones.push({
      id, row: r, col: c,
      elevation: round(elevation, 3),
      soil: waterHolding < 0.45 ? 'sandy loam (demo)' : 'silt loam (demo)',
      water_holding: round(waterHolding, 3),
      exposure: round(exposure, 3),
      crop_stage: 'V12 (demo)',
      health: { score, last_label, last_confidence: round(0.55 + 0.4 * rnd(), 2), n_captures: 0, label_mix: {}, method: 'simulated baseline' },
      // weekly history of the indicative score, oldest first (simulated)
      history: [5, 4, 3, 2, 1, 0].map((w) => ({ weeks_ago: w, score: Math.round(clamp(score / 100 + stress * 0.09 * w + 0.03 * (rnd() - 0.5), 0.1, 0.99) * 100) })),
      water: { applied_mm_7d: applied7, applied_mm_30d: applied30, last_irrigation_at: events[0].at, events },
      spray: { coverage_pct: coverage, events: sprayEvents },
      sensors: { soil_moisture_pct: null, air_temp_c: null, humidity_pct: null, light_lux: null },
      provenance: 'simulated',
    })
  }
}

// Machine path: back-and-forth passes, one zone per step.
const STEP_S = 4
const path = []
let t = 0
for (let r = 0; r < ROWS; r++) {
  const cols = [...Array(COLS).keys()]
  if (r % 2) cols.reverse()
  for (const c of cols) { path.push({ t, zone_id: `${LETTERS[c]}${r + 1}` }); t += STEP_S }
}
const machine = { id: 'sprayer-1', type: 'Self-propelled sprayer (simulated)', step_s: STEP_S, duration_s: t, path, provenance: 'simulated' }

// Seed captures: real public-dataset leaf photos assigned to simulated zones.
const IMG = { healthy: 8, discoloration: 8, wilting: 6 }
const counters = { healthy: 0, discoloration: 0, wilting: 0 }
const captures = []
path.forEach((p, i) => {
  const z = zones.find((q) => q.id === p.zone_id)
  const interesting = z.health.last_label !== 'healthy'
  if (!(i % 5 === 2 || (interesting && i % 2 === 0))) return
  const label = z.health.last_label
  const n = (counters[label]++ % IMG[label]) + 1
  const conf = round(label === 'healthy' ? 0.78 + 0.2 * rnd() : 0.52 + 0.42 * rnd(), 2)
  const id = `capture_${String(captures.length + 1).padStart(3, '0')}`
  captures.push({
    id, device_id: 'groundzero-sim-01', field_id: cfg.id, zone_id: z.id, reported_zone_id: z.id,
    captured_at: null, received_at: iso((machine.duration_s - p.t) * 1000 + 20 * 60000),
    capture_uptime_ms: 12000 + p.t * 1000, position: null,
    image_file: `${label}_${String(n).padStart(2, '0')}.jpg`,
    image: { width: 320, height: 240, bytes: null },
    edge_prediction: { label, confidence: conf, model_version: 'simulated-label', label_known: true },
    inference_ms: null, ingest_ms: null,
    sensors: { soil_moisture_pct: null, air_temp_c: null, humidity_pct: null, light_lux: null },
    review: { status: 'unreviewed', note: null, reviewed_at: null },
    provenance: 'simulated', t: p.t,
  })
})
for (const z of zones) {
  const cs = captures.filter((c) => c.zone_id === z.id)
  z.health.n_captures = cs.length
  if (cs.length) { z.health.last_label = cs.at(-1).edge_prediction.label; z.health.last_confidence = cs.at(-1).edge_prediction.confidence }
}

const field = {
  id: cfg.id, name: cfg.name, farm_id: cfg.farmId, farm: cfg.farm, crop: cfg.crop,
  center: cfg.center, rows: ROWS, cols: COLS, zone_size_m: 30,
  area_ha: round((ROWS * 30 * COLS * 30) / 10000, 2), area_acres: round((ROWS * 30 * COLS * 30) / 4046.86, 1),
  provenance: 'simulated',
  note: 'Synthetic field. Zone values, irrigation and application logs and the machine path are invented demo data.',
}

mkdirSync(DIR, { recursive: true })
const OUT = resolve(DIR, cfg.file)
writeFileSync(OUT, JSON.stringify({ generated_at: new Date(NOW).toISOString(), field, zones, machine, captures }))
console.log(`wrote ${OUT}: ${zones.length} zones, ${path.length} path steps, ${captures.length} captures`)
}

// Field A is the reference demo field (also seeded into the backend). B and C are separate demo fixtures
// with their own simulated patterns so the three fields never show the same data.
const FARM = 'Demo Farm — Yolo County, CA'
;[
  { file: 'field.json', id: 'field-A', name: 'Demo Field A', farmId: 'farm-demo-1', farm: FARM, crop: 'Maize', center: { lat: 38.543, lon: -121.872 }, seed: 20261114, ridge: [9.5, 2], dry: [10.5, 1], drySize: 2.6, disease: [2.5, 8.5], diseaseSize: 1.7 },
  { file: 'field-B.json', id: 'field-B', name: 'Demo Field B', farmId: 'farm-demo-1', farm: FARM, crop: 'Maize', center: { lat: 38.5712, lon: -121.908 }, seed: 7741, ridge: [2, 3], dry: [1, 10.5], drySize: 2.2, disease: [8.5, 4], diseaseSize: 1.3 },
  { file: 'field-C.json', id: 'field-C', name: 'Demo Field C', farmId: 'farm-demo-2', farm: 'Demo Farm South — Yolo County, CA', crop: 'Maize', center: { lat: 38.5105, lon: -121.839 }, seed: 99173, ridge: [6, 9], dry: [6, 0], drySize: 1.8, disease: [10, 10], diseaseSize: 2.3 },
].forEach(build)
