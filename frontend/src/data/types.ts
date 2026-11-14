export type Label = 'healthy' | 'discoloration' | 'wilting'
export type Provenance = 'real-device' | 'simulated' | 'public-weather' | 'imported'
export type ReviewStatus = 'unreviewed' | 'approved' | 'rejected' | 'needs-review'

export interface Sensors {
  soil_moisture_pct: number | null
  air_temp_c: number | null
  humidity_pct: number | null
  light_lux: number | null
}

export interface Capture {
  id: string
  device_id: string
  field_id: string
  zone_id: string
  reported_zone_id?: string | null
  captured_at: string | null
  received_at: string
  capture_uptime_ms: number | null
  position: null | { lat: number; lon: number }
  image_url: string
  image_file?: string
  image?: { width: number | null; height: number | null; bytes: number | null }
  edge_prediction: { label: string; confidence: number; model_version: string | null; label_known?: boolean }
  inference_ms: number | null
  ingest_ms: number | null
  sensors: Sensors
  review: { status: ReviewStatus; note?: string | null; reviewed_at?: string | null }
  provenance: Provenance
  /** replay time (s) for seeded captures; undefined for live ones */
  t?: number | null
  live?: boolean
}

export interface IrrigationEvent { at: string; mm: number; source: string }
export interface SprayEvent { at: string; product_class: string; rate_l_ha: number; coverage_pct: number }

export interface Zone {
  id: string
  row: number
  col: number
  elevation: number
  soil: string
  water_holding: number
  exposure: number
  crop_stage: string
  health: { score: number; last_label: string; last_confidence: number; n_captures: number; label_mix: Record<string, number>; method: string }
  history: { weeks_ago: number; score: number }[]
  water: { applied_mm_7d: number; applied_mm_30d: number; last_irrigation_at: string; events: IrrigationEvent[] }
  spray: { coverage_pct: number; events: SprayEvent[] }
  sensors: Sensors
  provenance: Provenance
}

export interface Field {
  id: string; name: string; farm: string; crop: string
  center: { lat: number; lon: number }
  rows: number; cols: number; zone_size_m: number
  area_ha: number; area_acres: number
  provenance: Provenance; note: string
}

export interface Machine {
  id: string; type: string; step_s: number; duration_s: number
  path: { t: number; zone_id: string }[]
  provenance: Provenance
}

export interface DemoData { generated_at: string; field: Field; zones: Zone[]; machine: Machine; captures: Capture[] }

// ---- optional real-data files in /data (produced by pipelines/) ----
export interface WeatherDay { date: string; tmax_c: number; tmin_c: number; precip_mm: number; et0_mm: number; radiation_mj_m2: number | null; rh_mean_pct: number | null; wind_max_kmh: number | null }
export interface Weather {
  source: string; fetched_at: string; daily: WeatherDay[]
  hourly_next_72h?: { time: string; temp_c: number; rh_pct: number; precip_mm: number; radiation_w_m2: number }[]
  provenance?: Provenance
}
export interface NdviData {
  source: string; status?: string; caveat?: string; method?: string
  latest: { scene_id: string; date: string; cloud_cover?: number; zones: Record<string, number>; min: number; max: number; mean: number }
  series?: { scene_id: string; date: string; mean: number; zones: Record<string, number> }[]
}

// ---- derived ----
export interface Factor { name: string; points: number; detail: string; source: Provenance | 'derived' }
export interface Risk {
  drought: number; heat: number; forecast_impact: number
  factors: Factor[]
  missing_inputs: string[]
  needs_sensor_validation: boolean
}
export interface ActionItem {
  id: string; zone_id: string; priority: 1 | 2 | 3
  kind: 'inspect' | 'validate_sensor' | 'review_irrigation' | 'review_images' | 'scout'
  title: string; why: string[]; score: number
}

export type LayerId = 'health' | 'drought' | 'water' | 'spray' | 'forecast' | 'ndvi'
