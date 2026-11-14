import type { Provenance } from '../data/types'

export const LABEL_TEXT: Record<string, string> = { healthy: '#63d394', discoloration: '#f0a93b', wilting: '#ef5a4c' }

const PROV: Record<string, { cls: string; text: string }> = {
  simulated: { cls: 'chip-sim', text: 'SIMULATED' },
  'real-device': { cls: 'chip-real', text: 'REAL DEVICE' },
  'public-weather': { cls: 'chip-pub', text: 'PUBLIC WEATHER' },
  imported: { cls: 'chip-pub', text: 'IMPORTED' },
  derived: { cls: '', text: 'DERIVED' },
}
export function ProvChip({ p, tiny }: { p: Provenance | 'derived'; tiny?: boolean }) {
  const d = PROV[p] ?? PROV.derived
  return <span className={`chip ${d.cls}`} style={tiny ? { fontSize: 9, padding: '1px 6px' } : undefined}>{d.text}</span>
}

export function ScoreRing({ value, label, size = 62 }: { value: number; label: string; size?: number }) {
  const r = size / 2 - 5, c = 2 * Math.PI * r
  const color = value >= 70 ? '#63d394' : value >= 45 ? '#f0a93b' : '#ef5a4c'
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1b2831" strokeWidth="5" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="num text-lg font-semibold" style={{ color }}>{value}</span>
        <span className="mt-0.5 text-[8.5px] uppercase tracking-wider text-mist-400">{label}</span>
      </div>
    </div>
  )
}

export const fmtDate = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
export const fmtTime = (iso: string) => new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
export function fmtAgo(iso: string | number) {
  const s = Math.max(0, (Date.now() - (typeof iso === 'number' ? iso : Date.parse(iso))) / 1000)
  if (s < 60) return `${Math.floor(s)} s ago`
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}
