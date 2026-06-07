import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, Cell,
} from 'recharts'
import api from '../api'

const LEVEL_COLORS = { INFO: '#6366f1', WARN: '#f59e0b', ERROR: '#ef4444' }

function CustomDayTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-xs">
      <p className="text-gray-300 font-semibold mb-1">{label}</p>
      <p className="text-gray-400">{payload[0]?.value} logs</p>
      <p className="text-indigo-400 mt-1">Click to see hourly breakdown</p>
    </div>
  )
}

function CustomHourTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-xs space-y-1">
      <p className="text-gray-300 font-semibold mb-1">{`${label}:00`}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.fill }} />
          <span style={{ color: p.fill }}>{p.dataKey}</span>
          <span className="text-gray-300 ml-auto">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function LogsPerDayChart({ data, tenantId }) {
  const [drillDay, setDrillDay]     = useState(null)
  const [hourData, setHourData]     = useState([])
  const [loading, setLoading]       = useState(false)

  async function handleDayClick(entry) {
    if (!entry?.activePayload?.[0]) return
    const day = entry.activePayload[0].payload.day
    setDrillDay(day)
    setLoading(true)
    try {
      const { data: rows } = await api.get(
        `/analytics/day-breakdown?date=${day}`,
        { headers: { 'X-Tenant-ID': tenantId } }
      )
      setHourData(rows)
    } catch {
      setHourData([])
    } finally {
      setLoading(false)
    }
  }

  if (!data?.length) return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-center h-[300px] text-gray-600 text-sm">
      No data
    </div>
  )

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 col-span-2">

      {/* Top bar */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-white">
          {drillDay
            ? <>
                <button onClick={() => setDrillDay(null)} className="text-indigo-400 hover:text-indigo-300 mr-2 text-sm">← All days</button>
                Hourly breakdown — <span className="text-indigo-300">{drillDay}</span>
              </>
            : 'Logs per Day'}
        </h2>
        {!drillDay && (
          <span className="text-xs text-gray-500">Click a bar to drill in</span>
        )}
      </div>

      {/* Day overview */}
      {!drillDay && (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data} onClick={handleDayClick} style={{ cursor: 'pointer' }}
            margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="day" tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }}
              axisLine={false} tickLine={false} />
            <Tooltip content={<CustomDayTooltip />} cursor={{ fill: '#1f2937' }} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {data.map((_, i) => <Cell key={i} fill="#6366f1" />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      {/* Hourly drill-down */}
      {drillDay && (
        loading
          ? <div className="h-[240px] flex items-center justify-center text-gray-500 text-sm">Loading...</div>
          : hourData.length === 0
            ? <div className="h-[240px] flex items-center justify-center text-gray-600 text-sm">No logs on this day</div>
            : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={hourData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="hour" tickFormatter={(h) => `${h}:00`}
                    tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }}
                    axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomHourTooltip />} cursor={{ fill: '#1f2937' }} />
                  <Legend formatter={(v) => <span style={{ color: LEVEL_COLORS[v], fontSize: 12 }}>{v}</span>} />
                  <Bar dataKey="INFO"  stackId="a" fill={LEVEL_COLORS.INFO}  radius={[0, 0, 0, 0]} />
                  <Bar dataKey="WARN"  stackId="a" fill={LEVEL_COLORS.WARN}  radius={[0, 0, 0, 0]} />
                  <Bar dataKey="ERROR" stackId="a" fill={LEVEL_COLORS.ERROR} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )
      )}
    </div>
  )
}
