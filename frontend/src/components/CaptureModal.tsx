import { useEffect } from 'react'
import { useStore } from '../store'
import type { Provenance, ReviewStatus } from '../data/types'

const provChip = (p: Provenance) =>
  p === 'real-device' ? <span className="chip chip-real">REAL DEVICE</span>
  : p === 'public-weather' ? <span className="chip chip-pub">PUBLIC DATA</span>
  : p === 'imported' ? <span className="chip chip-pub">IMPORTED</span>
  : <span className="chip chip-sim">SIMULATED</span>

const nm = (v: number | null | undefined, unit = '') => (v === null || v === undefined ? 'not measured' : `${v}${unit}`)
const nr = (v: number | string | null | undefined, unit = '') => (v === null || v === undefined ? 'not reported' : `${v}${unit}`)

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-b border-ink-700 py-1.5 text-[12.5px]">
      <span className="text-mist-400">{k}</span>
      <span className="num text-mist-100 text-right break-all">{v}</span>
    </div>
  )
}

export default function CaptureModal() {
  const id = useStore((s) => s.modalCapture)
  const captures = useStore((s) => s.captures)
  const set = useStore((s) => s.set)
  const review = useStore((s) => s.review)
  const focusZone = useStore((s) => s.focusZone)
  const c = captures.find((x) => x.id === id)

  useEffect(() => {
    if (!id) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') set({ modalCapture: null }) }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [id, set])

  if (!id || !c) return null
  const close = () => set({ modalCapture: null })
  const st = c.review.status
  const btn = (s: ReviewStatus, label: string) => (
    <button className={`btn ${st === s ? 'btn-primary' : ''}`} onClick={() => review(c.id, s)}>{label}</button>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={close}>
      <div className="panel bg-ink-900 w-full max-w-5xl max-h-[92vh] overflow-y-auto p-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Capture {c.id}</h2>
            {provChip(c.provenance)}
          </div>
          <button className="btn" onClick={close}>Close (Esc)</button>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <img src={c.image_url} alt={`Capture ${c.id}`} className="w-full rounded-md border border-ink-700 bg-ink-950 object-contain" style={{ aspectRatio: '4/3' }} />
            <div className="mt-3 flex flex-wrap gap-2">
              {btn('approved', 'Approve')}
              {btn('rejected', 'Reject')}
              {btn('needs-review', 'Needs review')}
              <button className="btn" onClick={() => { focusZone(c.zone_id, 'Images'); close() }}>Open zone {c.zone_id}</button>
            </div>
            <p className="mt-2 text-[12px] text-mist-400">Rejected images are excluded from the zone score. Current review status: <span className="text-mist-100">{st}</span>.</p>
          </div>
          <div>
            <div className="label mb-1">Edge prediction</div>
            <Row k="Label (visible appearance only)" v={`${c.edge_prediction.label}${c.edge_prediction.label_known === false ? ' (unknown label)' : ''}`} />
            <Row k="Confidence" v={`${(c.edge_prediction.confidence * 100).toFixed(0)}%`} />
            <Row k="Model version" v={nr(c.edge_prediction.model_version)} />
            <div className="label mt-3 mb-1">Metadata</div>
            <Row k="Device" v={c.device_id} />
            <Row k="Field" v={c.field_id} />
            <Row k="Zone" v={c.zone_id} />
            <Row k="Reported zone" v={c.reported_zone_id ?? 'not reported'} />
            <Row k="Received at" v={c.received_at} />
            <Row k="Captured at" v={c.captured_at ?? 'device clock not synced'} />
            <Row k="Uptime" v={c.capture_uptime_ms === null ? 'not reported' : `${c.capture_uptime_ms} ms`} />
            <Row k="Image size" v={c.image ? `${c.image.width ?? '?'}x${c.image.height ?? '?'}, ${c.image.bytes ?? '?'} B` : 'not reported'} />
            <Row k="Inference" v={nr(c.inference_ms, ' ms')} />
            <Row k="Ingest" v={nr(c.ingest_ms, ' ms')} />
            <Row k="Position" v={c.position ? `${c.position.lat}, ${c.position.lon}` : 'not measured (no GPS)'} />
            <div className="label mt-3 mb-1">Sensors</div>
            <Row k="Soil moisture" v={nm(c.sensors.soil_moisture_pct, ' %')} />
            <Row k="Air temperature" v={nm(c.sensors.air_temp_c, ' C')} />
            <Row k="Humidity" v={nm(c.sensors.humidity_pct, ' %')} />
            <Row k="Light" v={nm(c.sensors.light_lux, ' lux')} />
          </div>
        </div>
      </div>
    </div>
  )
}
