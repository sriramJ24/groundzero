import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { BASE } from '../config'
import type { Label } from '../data/types'

const SAMPLES: { file: string; label: Label }[] = [
  { file: 'healthy_03.jpg', label: 'healthy' }, { file: 'discoloration_02.jpg', label: 'discoloration' },
  { file: 'discoloration_05.jpg', label: 'discoloration' }, { file: 'wilting_02.jpg', label: 'wilting' },
]
const LETTERS = 'ABCDEFGHIJKL'

/** Manual upload path for demos without the ESP32. Uses the same POST /api/captures endpoint as the camera. */
export default function Simulator() {
  const open = useStore((s) => s.simOpen)
  const set = useStore((s) => s.set)
  const mode = useStore((s) => s.mode)
  const pinned = useStore((s) => s.pinned)
  const upload = useStore((s) => s.upload)
  const [file, setFile] = useState<Blob | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [zone, setZone] = useState('F6')
  const [label, setLabel] = useState<Label>('wilting')
  const [conf, setConf] = useState(0.72)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => { if (open && pinned) setZone(pinned) }, [open, pinned])
  useEffect(() => { if (!file) return setPreview(null); const u = URL.createObjectURL(file); setPreview(u); return () => URL.revokeObjectURL(u) }, [file])
  if (!open) return null

  const pickSample = async (s: (typeof SAMPLES)[number]) => {
    try { const r = await fetch(`${BASE}demo/images/${s.file}`); if (!r.ok) throw new Error(); setFile(await r.blob()); setLabel(s.label); setMsg(null) }
    catch { setMsg({ ok: false, text: 'Sample image not found.' }) }
  }
  const send = async () => {
    if (!file) return
    setBusy(true); setMsg(null)
    try {
      const c = await upload({ file, zoneId: zone, label, confidence: conf })
      setMsg({ ok: true, text: `Stored as ${c.id} in zone ${c.zone_id}${c.ingest_ms != null ? ` · ${c.ingest_ms} ms` : ''}` })
      set({ pinned: c.zone_id, zoneTab: 'Images', view: 'overview' })
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }) }
    setBusy(false)
  }

  return (
    <div className="slide-in fixed bottom-4 right-4 z-40 w-[360px] rounded-xl border border-ink-600 bg-ink-850 shadow-2xl shadow-black/60">
      <div className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
        <div><div className="text-[13.5px] font-semibold">Capture simulator</div><div className="text-[11px] text-amber-warn">Marks the upload as simulated</div></div>
        <button className="btn" onClick={() => set({ simOpen: false })} aria-label="Close simulator">Close</button>
      </div>
      <div className="space-y-3 p-4 text-[12.5px]">
        <label className="grid aspect-[4/3] w-full cursor-pointer place-items-center overflow-hidden rounded-lg border border-dashed border-ink-500 bg-ink-900 text-mist-400 hover:border-leaf-500">
          {preview ? <img src={preview} alt="Selected upload" className="h-full w-full object-cover" /> : <span>Choose a plant photo</span>}
          <input type="file" accept="image/*" className="hidden" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setMsg(null) }} />
        </label>
        <div>
          <div className="label mb-1">Or use a sample</div>
          <div className="grid grid-cols-4 gap-1.5">
            {SAMPLES.map((s) => (
              <button key={s.file} onClick={() => pickSample(s)} className="overflow-hidden rounded border border-ink-600 hover:border-leaf-500" title={s.label}>
                <img src={`${BASE}demo/images/${s.file}`} alt={`${s.label} sample`} className="aspect-[4/3] w-full object-cover" onError={(e) => { (e.currentTarget.parentElement!.style.display = 'none') }} />
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="label mb-1">Zone</div>
            <select value={zone} onChange={(e) => setZone(e.target.value)} className="w-full rounded-md border border-ink-600 bg-ink-900 px-2 py-1.5">
              {[...LETTERS].flatMap((l) => [...Array(12)].map((_, r) => <option key={`${l}${r + 1}`}>{`${l}${r + 1}`}</option>))}
            </select>
          </div>
          <div>
            <div className="label mb-1">Edge label</div>
            <select value={label} onChange={(e) => setLabel(e.target.value as Label)} className="w-full rounded-md border border-ink-600 bg-ink-900 px-2 py-1.5">
              <option>healthy</option><option>discoloration</option><option>wilting</option>
            </select>
          </div>
        </div>
        <div>
          <div className="label mb-1 flex justify-between"><span>Confidence</span><span className="num normal-case">{conf.toFixed(2)}</span></div>
          <input type="range" min={0.3} max={0.99} step={0.01} value={conf} onChange={(e) => setConf(Number(e.target.value))} className="w-full" />
        </div>
        <button className="btn btn-primary w-full" disabled={!file || busy} onClick={send}>{busy ? 'Sending…' : mode === 'live' ? 'POST to /api/captures' : 'Add capture (in-browser demo)'}</button>
        {msg && <div className={`rounded border px-2 py-1.5 text-[11.5px] ${msg.ok ? 'border-leaf-600/50 bg-leaf-600/10 text-leaf-300' : 'border-red-alert/40 bg-red-alert/10 text-red-alert'}`}>{msg.text}</div>}
        <div className="text-[11px] leading-snug text-mist-400">{mode === 'live' ? 'Sends raw JPEG bytes with the same X-* headers as the ESP32, plus X-Provenance: simulated.' : 'Backend not running: the capture is added in the browser only. Start the backend to exercise the real endpoint.'}</div>
      </div>
    </div>
  )
}
