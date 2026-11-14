import { useMemo } from 'react'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useStore } from '../store'

const TT = { contentStyle: { background: '#0f171d', border: '1px solid #263742', fontSize: 12 } }
const AX = { tick: { fill: '#7f95a1', fontSize: 11 }, stroke: '#263742' }
const nv = (v: number | null | undefined, d = 1) => (typeof v === 'number' ? v.toFixed(d) : 'not available')

export default function WeatherImpact() {
  const weather = useStore((s) => s.weather)
  const risks = useStore((s) => s.risks)
  const zones = useStore((s) => s.zones)
  const focusZone = useStore((s) => s.focusZone)
  const sim = weather.provenance === 'simulated'
  const daily = weather.daily ?? []

  const m = useMemo(() => {
    const ids = zones.map((z) => z.id)
    const cnt = (k: 'drought' | 'heat' | 'forecast_impact') => ids.filter((id) => (risks[id]?.[k] ?? 0) >= 60).length
    const top = [...ids].sort((a, b) => (risks[b]?.forecast_impact ?? 0) - (risks[a]?.forecast_impact ?? 0)).slice(0, 8)
      .map((id) => ({ id, r: risks[id], factors: [...(risks[id]?.factors ?? [])].sort((a, b) => b.points - a.points).slice(0, 2) }))
    return { n: ids.length, drought: cnt('drought'), heat: cnt('heat'), fi: cnt('forecast_impact'), top }
  }, [zones, risks])

  const chip = sim ? <span className="chip chip-sim">SIMULATED</span> : <span className="chip chip-pub">OPEN-METEO</span>

  return (
    <div className="h-full overflow-y-auto p-5 space-y-4">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-semibold">Weather Impact</h1>
          {chip}
        </div>
        <p className="text-[13px] text-mist-300">The 7-day forecast for the field location and how it moves the indicative risk scores.</p>
        <p className="text-[11px] text-mist-400 mt-1">Source: {weather.source}. Fetched at <span className="num">{weather.fetched_at}</span>.</p>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">7-day forecast</div>{chip}</div>
        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
          {daily.slice(0, 7).map((d) => (
            <div key={d.date} className="bg-ink-800 rounded-md p-2.5 text-[12px]">
              <div className="num text-mist-300">{d.date}</div>
              <div className="num text-base mt-1"><span className="text-red-alert">{nv(d.tmax_c)}</span> / <span className="text-sky-water">{nv(d.tmin_c)}</span> C</div>
              <div className="text-mist-400 mt-1">Rain <span className="num text-mist-100">{nv(d.precip_mm)}</span> mm</div>
              <div className="text-mist-400">ET0 <span className="num text-mist-100">{nv(d.et0_mm, 2)}</span> mm</div>
              <div className="text-mist-400">Rad <span className="num text-mist-100">{nv(d.radiation_mj_m2)}</span> MJ/m2</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">Temperature and ET0</div>{chip}</div>
        <div style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={daily.map((d) => ({ ...d, date: d.date.slice(5) }))}>
              <CartesianGrid stroke="#1b2831" />
              <XAxis dataKey="date" {...AX} />
              <YAxis yAxisId="t" {...AX} unit=" C" />
              <YAxis yAxisId="e" orientation="right" {...AX} unit=" mm" />
              <Tooltip {...TT} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#7f95a1' }} />
              <Bar yAxisId="e" dataKey="et0_mm" name="ET0 (mm)" fill="#4aa8e8" fillOpacity={0.55} />
              <Line yAxisId="t" type="monotone" dataKey="tmax_c" name="Tmax (C)" stroke="#ef5a4c" strokeWidth={2} dot={false} />
              <Line yAxisId="t" type="monotone" dataKey="tmin_c" name="Tmin (C)" stroke="#63d394" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">What this means for the field</div><span className="chip chip-sim">SIMULATED ZONES + {sim ? 'SAMPLE' : 'OPEN-METEO'} WEATHER</span></div>
        <div className="grid grid-cols-3 gap-3">
          {[['Drought risk 60 or more', m.drought, 'text-amber-warn'], ['Heat risk 60 or more', m.heat, 'text-red-alert'], ['Forecast impact 60 or more', m.fi, 'text-sky-water']].map(([k, v, c]) => (
            <div key={k as string} className="bg-ink-800 rounded-md p-3">
              <div className="label">{k}</div>
              <div className={`num text-2xl mt-1 ${c}`}>{v as number} <span className="text-sm text-mist-400">/ {m.n} zones</span></div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-mist-400 mt-2">Scores are transparent rule-based indicators, not a validated model.</p>
        <div className="label mt-4 mb-1">Highest forecast impact</div>
        <table className="w-full text-[12.5px]">
          <thead><tr className="text-left text-mist-400"><th className="py-1">Zone</th><th>Impact</th><th>Top factors</th><th></th></tr></thead>
          <tbody>
            {m.top.map((t) => (
              <tr key={t.id} className="border-t border-ink-700 align-top">
                <td className="py-1.5 num">{t.id}</td>
                <td className="num">{t.r?.forecast_impact ?? 'n/a'}</td>
                <td className="text-mist-300">{t.factors.length ? t.factors.map((x) => `${x.name} (+${x.points})`).join(', ') : 'no factors listed'}</td>
                <td className="text-right"><button className="btn" onClick={() => focusZone(t.id, 'Weather')}>Open zone</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
