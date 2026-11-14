import { useStore } from '../store'

const KIND: Record<string, string> = { review_irrigation: 'Irrigation', scout: 'Scouting', validate_sensor: 'Sensor check', review_images: 'Image review', inspect: 'Inspect' }
const PR = ['', 'text-red-alert border-red-alert/40 bg-red-alert/10', 'text-amber-warn border-amber-warn/40 bg-amber-warn/10', 'text-mist-300 border-ink-600 bg-ink-800']

export default function Actions() {
  const actions = useStore((s) => s.actions)
  const done = useStore((s) => s.doneActions)
  const risks = useStore((s) => s.risks)
  const zoneById = useStore((s) => s.zoneById)
  const focus = useStore((s) => s.focusZone)
  const set = useStore((s) => s.set)
  const mark = (id: string, v: 'done' | 'dismissed') => set({ doneActions: { ...done, [id]: v } })
  const open = actions.filter((a) => !done[a.id])
  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Action Center</h1>
          <p className="mt-0.5 max-w-3xl text-[13px] text-mist-300">Ranked suggestions for a person to review. Each one lists the evidence that produced it. Nothing here is sent to machinery, and no product or dosage is ever recommended.</p>
        </div>
        <div className="flex gap-1.5"><span className="chip">RULE-BASED · INDICATIVE</span><span className="chip chip-sim">SIMULATED ZONE DATA</span></div>
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        {open.map((a, i) => {
          const z = zoneById[a.zone_id], r = risks[a.zone_id]
          return (
            <div key={a.id} className="panel p-4">
              <div className="flex items-start gap-3">
                <div className="num grid h-9 w-9 shrink-0 place-items-center rounded-md border border-ink-600 bg-ink-800 text-sm font-semibold text-mist-300">{i + 1}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className={`chip ${PR[a.priority]}`}>PRIORITY {a.priority}</span><span className="chip">{KIND[a.kind]}</span>
                    {r.needs_sensor_validation && <span className="chip chip-sim">NEEDS SENSOR VALIDATION</span>}
                  </div>
                  <div className="mt-1.5 text-[14.5px] font-semibold leading-snug">{a.title}</div>
                  <div className="label mt-3">Why this was generated</div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] text-mist-300">{a.why.map((w) => <li key={w}>{w}</li>)}</ul>
                  <div className="num mt-2 text-[11.5px] text-mist-400">health {z.health.score} · drought {r.drought} · heat {r.heat} · water 7 d {z.water.applied_mm_7d.toFixed(0)} mm</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button className="btn btn-primary" onClick={() => focus(a.zone_id, a.kind === 'review_images' ? 'Images' : a.kind === 'review_irrigation' ? 'Water' : 'Health')}>Open zone {a.zone_id}</button>
                    <button className="btn" onClick={() => mark(a.id, 'done')}>Mark done</button>
                    <button className="btn" onClick={() => mark(a.id, 'dismissed')}>Dismiss</button>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
        {open.length === 0 && <div className="panel p-8 text-center text-mist-400">No open actions.</div>}
      </div>
      {Object.keys(done).length > 0 && (
        <div className="mt-5 text-[12px] text-mist-400">
          {Object.values(done).filter((v) => v === 'done').length} done · {Object.values(done).filter((v) => v === 'dismissed').length} dismissed
          <button className="ml-3 underline hover:text-mist-200" onClick={() => set({ doneActions: {} })}>restore all</button>
        </div>
      )}
    </div>
  )
}
