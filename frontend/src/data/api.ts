// Two adapters, one schema. "live" talks to the FastAPI backend; "demo" runs fully in the browser
// from the bundled simulated dataset (used for the hosted demo and when the backend is not running).
import demoJson from './demo/field.json'
import { BASE } from '../config'
import type { Capture, DemoData, Label, ReviewStatus } from './types'

export type Mode = 'live' | 'demo'
const demo = demoJson as unknown as DemoData

async function tryJson<T>(url: string, ms = 1500): Promise<T | null> {
  try {
    const ctl = new AbortController()
    const t = setTimeout(() => ctl.abort(), ms)
    const r = await fetch(url, { signal: ctl.signal })
    clearTimeout(t)
    if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) return null
    return (await r.json()) as T
  } catch { return null }
}

/** Optional real-data files written by pipelines/ into public/data. Missing files return null. */
export const loadDataFile = <T,>(name: string) => tryJson<T>(`${BASE}data/${name}`, 4000)

const normalise = (c: Capture, seededMax: number): Capture => ({
  ...c,
  image_url: c.image_url ?? `${BASE}demo/images/${c.image_file}`,
  live: !(c.t != null && c.t <= seededMax && c.provenance === 'simulated' && c.device_id === 'fieldos-sim-01'),
})

export async function loadAll(): Promise<{ mode: Mode; data: DemoData }> {
  const seededMax = demo.machine.duration_s
  const live = await tryJson<DemoData>('/api/demo')
  if (live?.zones?.length) {
    // Zone baselines always come from the bundled demo file (same file the backend seeds from); the backend supplies captures.
    return { mode: 'live', data: { ...demo, captures: live.captures.map((c) => normalise(c, seededMax)) } }
  }
  return { mode: 'demo', data: { ...demo, captures: demo.captures.map((c) => normalise({ ...c, image_url: `${BASE}demo/images/${c.image_file}` }, seededMax)) } }
}

export interface UploadInput { file: Blob; zoneId: string; label: Label; confidence: number; deviceId?: string; inferenceMs?: number }

export async function postCapture(mode: Mode, input: UploadInput): Promise<Capture> {
  const jpeg = await toJpeg(input.file)
  if (mode === 'live') {
    const t0 = performance.now()
    const r = await fetch('/api/captures', {
      method: 'POST', body: jpeg,
      headers: {
        'Content-Type': 'image/jpeg', 'X-Device-ID': input.deviceId ?? 'fieldos-simulator', 'X-Field-ID': 'field-A', 'X-Zone-ID': input.zoneId,
        'X-Edge-Label': input.label, 'X-Edge-Confidence': input.confidence.toFixed(4), 'X-Capture-Uptime-Ms': String(Math.round(performance.now())),
        'X-Timestamp-Unix': String(Math.floor(Date.now() / 1000)), 'X-Model-Version': 'manual-simulator', 'X-Provenance': 'simulated',
        ...(input.inferenceMs ? { 'X-Inference-Ms': String(input.inferenceMs) } : {}),
      },
    })
    if (!r.ok) throw new Error(`Upload failed (${r.status}): ${await r.text()}`)
    const { capture_id } = await r.json()
    const list = await tryJson<Capture[]>(`/api/captures?limit=5`, 3000)
    const c = list?.find((x) => x.id === capture_id)
    if (!c) throw new Error('Uploaded, but the capture was not returned by the API')
    return { ...c, live: true, ingest_ms: c.ingest_ms ?? Math.round(performance.now() - t0) }
  }
  const dims = await imageDims(jpeg)
  return {
    id: `capture_local_${Date.now()}`, device_id: input.deviceId ?? 'fieldos-simulator', field_id: 'field-A', zone_id: input.zoneId, reported_zone_id: input.zoneId,
    captured_at: new Date().toISOString(), received_at: new Date().toISOString(), capture_uptime_ms: Math.round(performance.now()), position: null,
    image_url: URL.createObjectURL(jpeg), image: { ...dims, bytes: jpeg.size },
    edge_prediction: { label: input.label, confidence: input.confidence, model_version: 'manual-simulator', label_known: true },
    inference_ms: input.inferenceMs ?? null, ingest_ms: null,
    sensors: { soil_moisture_pct: null, air_temp_c: null, humidity_pct: null, light_lux: null },
    review: { status: 'unreviewed' }, provenance: 'simulated', t: null, live: true,
  }
}

export async function postReview(mode: Mode, id: string, status: ReviewStatus, note?: string) {
  if (mode !== 'live' || id.startsWith('capture_local_')) return
  await fetch(`/api/captures/${id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, note: note ?? null }) })
}

export function subscribe(onCapture: (c: Capture) => void, onReview: (c: Capture) => void, onState: (ok: boolean) => void) {
  const es = new EventSource('/api/events')
  es.addEventListener('capture', (e) => onCapture({ ...JSON.parse((e as MessageEvent).data), live: true }))
  es.addEventListener('review', (e) => onReview(JSON.parse((e as MessageEvent).data)))
  es.onopen = () => onState(true)
  es.onerror = () => onState(false)
  return () => es.close()
}

/** Re-encode any picked image to a 320x240-ish JPEG, matching what the camera sends. */
async function toJpeg(file: Blob): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(file)
    const W = 320, H = 240
    const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H
    const ctx = canvas.getContext('2d')!
    const s = Math.max(W / bmp.width, H / bmp.height)
    ctx.drawImage(bmp, (W - bmp.width * s) / 2, (H - bmp.height * s) / 2, bmp.width * s, bmp.height * s)
    return await new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error('encode failed'))), 'image/jpeg', 0.82))
  } catch { return file }
}
async function imageDims(b: Blob) {
  try { const bmp = await createImageBitmap(b); return { width: bmp.width, height: bmp.height } } catch { return { width: null, height: null } }
}
