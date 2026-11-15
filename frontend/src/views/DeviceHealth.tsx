import { useMemo, useState } from 'react'
import { useStore } from '../store'
import type { Provenance } from '../data/types'

const CURL = `curl -X POST http://<LAPTOP_LAN_IP>:8000/api/captures -H "Content-Type: image/jpeg" -H "X-Device-ID: groundzero-esp32-01" -H "X-Field-ID: field-A" -H "X-Zone-ID: demo-zone-1" -H "X-Edge-Label: discoloration" -H "X-Edge-Confidence: 0.72" -H "X-Capture-Uptime-Ms: 31415" --data-binary @plant.jpg`

const HEADERS: [string, string, string][] = [
  ['X-Device-ID', 'required', 'Device identifier'],
  ['X-Field-ID', 'required', 'Field identifier'],
  ['X-Zone-ID', 'required', 'Zone assigned manually'],
  ['X-Edge-Label', 'required', 'healthy | discoloration | wilting'],
  ['X-Edge-Confidence', 'required', 'Edge model confidence, 0 to 1'],
  ['X-Capture-Uptime-Ms', 'required', 'Device uptime at capture'],
  ['X-Timestamp-Unix', 'optional', 'Capture time, if the clock is synced'],
  ['X-Inference-Ms', 'optional', 'On-device inference time'],
  ['X-Model-Version', 'optional', 'Edge model version string'],
]

const provChip = (p: Provenance) =>
  p === 'real-device' ? <span className="chip chip-real">REAL DEVICE</span> : <span className="chip chip-sim">SIMULATED</span>

export default function DeviceHealth() {
  const captures = useStore((s) => s.captures)
  const mode = useStore((s) => s.mode)
  const sseOk = useStore((s) => s.sseOk)
  const [copied, setCopied] = useState(false)

  const devices = useMemo(() => {
    const g: Record<string, typeof captures> = {}
    captures.forEach((c) => (g[c.device_id] ??= []).push(c))
    const mean = (xs: (number | null)[]) => { const v = xs.filter((x): x is number => typeof x === 'number'); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null }
    return Object.entries(g).map(([id, cs]) => {
      const sorted = [...cs].sort((a, b) => (a.received_at < b.received_at ? 1 : -1))
      return {
        id, n: cs.length, last: sorted[0].received_at, uptime: sorted[0].capture_uptime_ms,
        inf: mean(cs.map((c) => c.inference_ms)), ing: mean(cs.map((c) => c.ingest_ms)),
        prov: cs.some((c) => c.provenance === 'real-device') ? 'real-device' as Provenance : sorted[0].provenance,
      }
    }).sort((a, b) => (a.last < b.last ? 1 : -1))
  }, [captures])

  const copy = () => { navigator.clipboard?.writeText(CURL).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) }).catch(() => {}) }
  const ms = (v: number | null) => (v === null ? 'not reported' : `${v.toFixed(0)} ms`)

  return (
    <div className="h-full overflow-y-auto p-5 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Device Health</h1>
        <p className="text-[13px] text-mist-300">What the capture devices have sent, the connection state, and how to send a capture.</p>
      </div>

      <div className="panel p-4">
        <div className="label mb-2">Connection</div>
        <div className="flex flex-wrap items-center gap-3 text-[13px]">
          <span className={`chip ${mode === 'live' ? 'chip-real' : 'chip-sim'}`}>{mode === 'live' ? 'LIVE: BACKEND CONNECTED' : 'DEMO: IN-BROWSER DEMO DATA'}</span>
          <span className={`chip ${sseOk ? 'chip-real' : ''}`}>{sseOk ? 'EVENT STREAM CONNECTED' : 'EVENT STREAM NOT CONNECTED'}</span>
        </div>
        <p className="text-[12px] text-mist-400 mt-2">In demo mode no backend is reached and no device can upload; all captures shown are seeded.</p>
      </div>

      <div className="panel p-4">
        <div className="label mb-2">Devices</div>
        {devices.length === 0 ? <p className="text-[12.5px] text-mist-400">No captures received.</p> : (
          <table className="w-full text-[12.5px]">
            <thead><tr className="text-left text-mist-400"><th className="py-1">Device</th><th>Last seen</th><th>Captures</th><th>Last uptime</th><th>Mean inference</th><th>Mean ingest</th><th>Provenance</th></tr></thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id} className="border-t border-ink-700">
                  <td className="py-1.5 num">{d.id}</td>
                  <td className="num">{new Date(d.last).toLocaleString()}</td>
                  <td className="num">{d.n}</td>
                  <td className="num">{d.uptime === null ? 'not reported' : `${(d.uptime / 1000).toFixed(0)} s`}</td>
                  <td className="num">{ms(d.inf)}</td>
                  <td className="num">{ms(d.ing)}</td>
                  <td>{provChip(d.prov)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel p-4">
        <div className="label mb-2">Capture contract: POST /api/captures</div>
        <table className="w-full text-[12.5px]">
          <thead><tr className="text-left text-mist-400"><th className="py-1">Header</th><th>Status</th><th>Meaning</th></tr></thead>
          <tbody>
            {HEADERS.map(([h, r, d]) => (
              <tr key={h} className="border-t border-ink-700"><td className="py-1 num">{h}</td><td className={r === 'required' ? 'text-amber-warn' : 'text-mist-400'}>{r}</td><td className="text-mist-300">{d}</td></tr>
            ))}
          </tbody>
        </table>
        <ul className="list-disc ml-5 mt-3 text-[12px] text-mist-300 space-y-0.5">
          <li>Body: raw image/jpeg, 320x240.</li>
          <li>Labels: healthy, discoloration, wilting.</li>
          <li>The board has no GPS; the zone is assigned manually. <span className="num">demo-zone-1</span> maps to zone F6.</li>
        </ul>
        <div className="flex items-center justify-between mt-4 mb-1"><div className="label">Example</div><button className="btn" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button></div>
        <pre className="num text-[11.5px] bg-ink-950 border border-ink-700 rounded-md p-3 whitespace-pre-wrap break-all text-mist-200">{CURL}</pre>
      </div>
    </div>
  )
}
