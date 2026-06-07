import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const COLORS = {
  INFO:  '#6366f1',
  WARN:  '#f59e0b',
  ERROR: '#ef4444',
}

export default function LevelPieChart({ data }) {
  if (!data?.length) return <Empty />

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-base font-semibold text-white mb-4">Logs by Level</h2>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="level"
            cx="50%"
            cy="50%"
            outerRadius={85}
            label={({ level, percent }) =>
              `${level} ${(percent * 100).toFixed(0)}%`
            }
          >
            {data.map((entry) => (
              <Cell
                key={entry.level}
                fill={COLORS[entry.level] ?? '#6b7280'}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#f9fafb' }}
          />
          <Legend
            formatter={(value) => (
              <span style={{ color: '#9ca3af', fontSize: 12 }}>{value}</span>
            )}
          />
        </PieChart>
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
