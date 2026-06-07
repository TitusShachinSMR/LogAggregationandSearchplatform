import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

export default function ErrorTrendChart({ data }) {
  if (!data?.length) return <Empty />

  const formatted = data.map((d) => {
    // API returns "2026-06-06T10:00:00+00:00" or "2026-06-06 10:00:00+00:00"
    const iso = d.hour.replace(' ', 'T')
    const date = new Date(iso)
    const label = isNaN(date)
      ? d.hour.slice(0, 13).replace('T', ' ')  // fallback: "2026-06-06 10"
      : date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    return { ...d, hour: label }
  })

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-base font-semibold text-white mb-4">Error Trend</h2>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={formatted} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="errorGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="hour"
            tick={{ fill: '#9ca3af', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#f9fafb' }}
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="#ef4444"
            strokeWidth={2}
            fill="url(#errorGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function Empty() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-center h-[300px] text-gray-600 text-sm">
      No data
    </div>
  )
}
