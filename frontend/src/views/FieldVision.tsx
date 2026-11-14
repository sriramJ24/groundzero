import { useMemo, useState } from 'react'
import { useStore } from '../store'
import type { Provenance } from '../data/types'

const provChip = (p: Provenance) =>
  p === 'real-device' ? <span className="chip chip-real">REAL DEVICE</span>
  : p === 'public-weather' ? <span className="chip chip-pub">PUBLIC DATA</span>
  : p === 'imported' ? <span className="chip chip-pub">IMPORTED</span>
  : <span className="chip chip-sim">SIMULATED</span>

const labelColor = (l: string) => (l === 'healthy' ? 'bg-leaf-500' : l === 'wilting' ? 'bg-red-alert' : 'bg-amber-warn')

function Sel({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <label className="flex items-center gap-2 text-[12px] text-mist-400">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="bg-ink-800 border border-ink-600 rounded px-2 py-1 text-mist-100 text-[12px]">
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}

export default function FieldVision() {
  const captures = useStore((s) => s.captures)
  const set = useStore((s) => s.set)
  const [label, setLabel] = useState('all')
  const [status, setStatus] = useState('all')
  const [prov, setProv] = useState('all')
  const [sort, setSort] = useState('newest')

  const list = useMemo(() => {
    const out = captures.filter((c) =>
      (label === 'all' || c.edge_prediction.label === label) &&
      (status === 'all' || c.review.status === status) &&
      (prov === 'all' || c.provenance === prov))
    out.sort((a, b) => sort === 'newest' ? (a.received_at < b.received_at ? 1 : -1)
      : sort === 'oldest' ? (a.received_at > b.received_at ? 1 : -1)
      : b.edge_prediction.confidence - a.edge_prediction.confidence)
    return out
  }, [captures, label, status, prov, sort])

  return (
    <div className="h-full overflow-y-auto p-5 space-y-4">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-semibold">Field Vision</h1>
          <span className="chip chip-real">REAL DEVICE</span>
          <span className="chip chip-sim">SIMULATED</span>
        </div>
        <p className="text-[13px] text-mist-300">Camera captures by zone, with the on-device label and your review.</p>
        <p className="text-[12px] text-mist-400 mt-1">Labels describe visible leaf appearance only, not cause. The device uploads only frames that pass its on-device plant check.</p>
        <p className="text-[12px] text-mist-400">Seeded demo captures are marked SIMULATED; only captures from the device carry REAL DEVICE.</p>
      </div>
      <div className="panel p-3 flex flex-wrap gap-4 items-center">
        <Sel label="Label" value={label} onChange={setLabel} options={['all', 'healthy', 'discoloration', 'wilting']} />
        <Sel label="Review" value={status} onChange={setStatus} options={['all', 'unreviewed', 'approved', 'rejected', 'needs-review']} />
        <Sel label="Provenance" value={prov} onChange={setProv} options={['all', 'real-device', 'simulated', 'imported']} />
        <Sel label="Sort" value={sort} onChange={setSort} options={['newest', 'oldest', 'confidence']} />
        <span className="ml-auto num text-[12px] text-mist-400">{list.length} of {captures.length}</span>
      </div>
      {list.length === 0 && <div className="panel p-6 text-center text-mist-400 text-[13px]">No captures match these filters.</div>}
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))' }}>
        {list.map((c) => (
          <button key={c.id} onClick={() => set({ modalCapture: c.id })} className="panel overflow-hidden text-left hover:border-ink-500 transition-colors">
            <img src={c.image_url} alt={`Capture ${c.id}`} loading="lazy" className="w-full object-cover bg-ink-950" style={{ aspectRatio: '4/3' }} />
            <div className="p-2.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="num text-[13px] font-semibold">{c.zone_id}</span>
                {provChip(c.provenance)}
              </div>
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-mist-100">{c.edge_prediction.label}</span>
                <span className="num text-mist-300">{(c.edge_prediction.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 rounded bg-ink-700 overflow-hidden">
                <div className={`h-full ${labelColor(c.edge_prediction.label)}`} style={{ width: `${Math.round(c.edge_prediction.confidence * 100)}%` }} />
              </div>
              <div className="flex items-center justify-between text-[11px] text-mist-400">
                <span>{c.review.status}</span>
                <span className="num">{new Date(c.received_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
